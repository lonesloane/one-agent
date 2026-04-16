"""
Classical Flask app — click-heavy status quo for UC1 read flows.

Implements a traditional multi-page Flask application that demonstrates
the committee meeting document access workflow. All data comes from the
shared SQLAlchemy ORM layer. Use create_app() to get a configured Flask
application; for convenience a module-level ``app`` is also provided.
"""

import os
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    session,
    request,
)
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import scoped_session, sessionmaker

from shared.database import (
    get_engine,
    init_db,
    Delegate,
    Committee,
    Document,
    Meeting,
    MeetingAgendaItem,
)
from shared.business_rules import (
    is_document_visible,
    get_visible_agenda_documents,
)
from classical_app.helpers import get_current_delegate, get_now_utc

# Default DB path — two levels up from this file (project root).
# Override via ONE_AGENT_DB_PATH env var when running from a worktree.
_DEFAULT_DB = str(Path(__file__).parent.parent / "one_agent.db")


def create_app(db_url: str | None = None) -> Flask:
    """
    Create and configure the Flask application.

    Args:
        db_url: SQLAlchemy database URL. If None, uses the
            ONE_AGENT_DB_PATH env var or the default project-root path.

    Returns:
        Configured Flask application instance
    """
    flask_app = Flask(__name__)
    flask_app.secret_key = "demo-secret-key-not-for-production"
    flask_app.config["WTF_CSRF_ENABLED"] = False

    if db_url is None:
        raw_path = os.environ.get("ONE_AGENT_DB_PATH", _DEFAULT_DB)
        db_url = f"sqlite:///{raw_path}"

    logger.info("Database URL: {}", db_url)
    engine = get_engine(db_url.removeprefix("sqlite:///"))
    init_db(engine)

    session_factory = sessionmaker(bind=engine)
    db_session = scoped_session(session_factory)
    flask_app.extensions["db_session"] = db_session

    # ------------------------------------------------------------------
    # Context processor
    # ------------------------------------------------------------------

    @flask_app.context_processor
    def inject_delegate_info() -> dict:
        """Inject navbar vars into all templates."""
        delegate_id = session.get("delegate_id")
        if not delegate_id:
            return {
                "current_delegate_name": "",
                "current_delegation_name": "",
            }
        try:
            delegate = get_current_delegate(db_session)
            return {
                "current_delegate_name": delegate.full_name,
                "current_delegation_name": delegate.delegation.name,
            }
        except RuntimeError:
            return {
                "current_delegate_name": "",
                "current_delegation_name": "",
            }

    from classical_app.permissions import (
        is_editor_of as _is_editor_of,
    )

    @flask_app.context_processor
    def inject_editor_check() -> dict:
        """Inject is_editor_of_delegation into all templates."""
        def is_editor_of_delegation(delegation_id: str) -> bool:
            delegate_id = session.get("delegate_id")
            if not delegate_id:
                return False
            return _is_editor_of(
                flask_app.extensions["db_session"],
                delegate_id,
                delegation_id,
            )
        return {"is_editor_of_delegation": is_editor_of_delegation}

    # ------------------------------------------------------------------
    # Request lifecycle
    # ------------------------------------------------------------------

    @flask_app.before_request
    def check_delegate_session() -> Any:
        """Redirect to delegate picker if no delegate in session."""
        if request.endpoint and request.endpoint.startswith("static"):
            return None
        if "delegate_id" not in session:
            if request.endpoint not in (
                "switch_delegate",
                "switch_delegate_post",
            ):
                logger.info("No delegate in session — redirecting to picker")
                return redirect(url_for("switch_delegate"))
        return None

    @flask_app.teardown_appcontext
    def teardown_db(exception: Any = None) -> None:
        """Remove scoped DB session after each request."""
        db_session.remove()

    # ------------------------------------------------------------------
    # Error handlers
    # ------------------------------------------------------------------

    @flask_app.errorhandler(403)
    def handle_forbidden(error: Any) -> tuple[str, int]:
        """Return 403 access-denied page."""
        logger.warning("Access forbidden: {}", error)
        return render_template("403.html"), 403

    @flask_app.errorhandler(404)
    def handle_not_found(error: Any) -> tuple[str, int]:
        """Return 404 not-found page."""
        logger.warning("Not found: {}", error)
        return render_template("404.html"), 404

    # ------------------------------------------------------------------
    # Routes — Delegate picker
    # ------------------------------------------------------------------

    @flask_app.route("/switch-delegate", methods=["GET"])
    def switch_delegate() -> str:
        """Render the delegate selection page."""
        stmt = select(Delegate)
        delegates = db_session.scalars(stmt).all()
        logger.info(
            "Rendering switch_delegate with {} delegates", len(delegates)
        )
        return render_template("switch_delegate.html", delegates=delegates)

    @flask_app.route("/switch-delegate", methods=["POST"])
    def switch_delegate_post() -> Any:
        """Store selected delegate in session and redirect to dashboard."""
        delegate_id = request.form.get("delegate_id", "").strip()
        if not delegate_id:
            logger.warning("Empty delegate_id in POST /switch-delegate")
            return redirect(url_for("switch_delegate"))
        session["delegate_id"] = delegate_id
        logger.info("Delegate switched to: {}", delegate_id)
        return redirect(url_for("dashboard"))

    # ------------------------------------------------------------------
    # Routes — Dashboard
    # ------------------------------------------------------------------

    @flask_app.route("/", methods=["GET"])
    def dashboard() -> str:
        """Render delegate dashboard with navigation cards."""
        delegate = get_current_delegate(db_session)
        logger.info("Dashboard for delegate: {}", delegate.id)
        return render_template(
            "dashboard.html",
            delegate=delegate,
            delegation=delegate.delegation,
        )

    # ------------------------------------------------------------------
    # Routes — Committees
    # ------------------------------------------------------------------

    @flask_app.route("/committees", methods=["GET"])
    def committees_list() -> str:
        """
        Render list of delegate's committees with next meeting dates.

        Returns:
            Rendered committees.html template
        """
        delegate = get_current_delegate(db_session)
        now = get_now_utc()
        committees_data = []
        for committee in delegate.committees:
            stmt = (
                select(Meeting)
                .where(
                    Meeting.committee_id == committee.id,
                    Meeting.date > now,
                )
                .order_by(Meeting.date.asc())
            )
            next_meeting = db_session.scalars(stmt).first()
            committees_data.append(
                {
                    "committee": committee,
                    "next_meeting_date": (
                        next_meeting.date if next_meeting else None
                    ),
                }
            )
        logger.info(
            "Committees for delegate {}: {}",
            delegate.id,
            len(committees_data),
        )
        return render_template("committees.html", committees=committees_data)

    @flask_app.route("/committees/<committee_id>", methods=["GET"])
    def committee_detail(committee_id: str) -> Any:
        """
        Render committee detail page.

        Args:
            committee_id: The committee identifier

        Returns:
            Rendered committee_detail.html or 404 if not found/not member
        """
        delegate = get_current_delegate(db_session)
        stmt = select(Committee).where(Committee.id == committee_id)
        committee = db_session.scalars(stmt).first()
        if not committee:
            logger.warning("Committee not found: {}", committee_id)
            return render_template("404.html"), 404
        if committee not in delegate.committees:
            logger.warning(
                "Delegate {} not a member of committee {}",
                delegate.id,
                committee_id,
            )
            return render_template("404.html"), 404
        return render_template(
            "committee_detail.html",
            committee=committee,
            delegate=delegate,
        )

    # ------------------------------------------------------------------
    # Routes — Meetings
    # ------------------------------------------------------------------

    @flask_app.route(
        "/committees/<committee_id>/meetings", methods=["GET"]
    )
    def upcoming_meetings(committee_id: str) -> Any:
        """
        Render upcoming meetings for a committee with visible doc counts.

        Args:
            committee_id: The committee identifier

        Returns:
            Rendered upcoming_meetings.html or 404
        """
        delegate = get_current_delegate(db_session)
        now = get_now_utc()
        stmt = select(Committee).where(Committee.id == committee_id)
        committee = db_session.scalars(stmt).first()
        if not committee:
            return render_template("404.html"), 404

        stmt = (
            select(Meeting)
            .where(
                Meeting.committee_id == committee_id,
                Meeting.date > now,
            )
            .order_by(Meeting.date.asc())
        )
        meetings = db_session.scalars(stmt).all()
        meetings_data = [
            {
                "meeting": mtg,
                "visible_doc_count": len(
                    get_visible_agenda_documents(
                        delegate.id, mtg.id, db_session
                    )
                ),
            }
            for mtg in meetings
        ]
        return render_template(
            "upcoming_meetings.html",
            committee=committee,
            meetings=meetings_data,
        )

    @flask_app.route("/meetings/<meeting_id>", methods=["GET"])
    def meeting_detail(meeting_id: str) -> Any:
        """
        Render meeting detail with filtered agenda documents.

        Args:
            meeting_id: The meeting identifier

        Returns:
            Rendered meeting_detail.html or 404
        """
        delegate = get_current_delegate(db_session)
        stmt = select(Meeting).where(Meeting.id == meeting_id)
        meeting = db_session.scalars(stmt).first()
        if not meeting:
            return render_template("404.html"), 404

        stmt = (
            select(MeetingAgendaItem)
            .where(MeetingAgendaItem.meeting_id == meeting_id)
            .order_by(MeetingAgendaItem.item_order)
        )
        all_items = db_session.scalars(stmt).all()
        agenda_items = [
            {"document": item.document, "item_order": item.item_order}
            for item in all_items
            if is_document_visible(delegate.id, item.document, db_session)
        ]
        logger.info(
            "Meeting {}: {} visible documents for delegate {}",
            meeting_id,
            len(agenda_items),
            delegate.id,
        )
        return render_template(
            "meeting_detail.html",
            meeting=meeting,
            committee=meeting.committee,
            agenda_items=agenda_items,
        )

    # ------------------------------------------------------------------
    # Routes — Documents
    # ------------------------------------------------------------------

    @flask_app.route("/documents/<document_id>", methods=["GET"])
    def document_detail(document_id: str) -> Any:
        """
        Render document detail page; 403 if not visible to delegate.

        Args:
            document_id: The document identifier

        Returns:
            Rendered document_detail.html, 403, or 404
        """
        delegate = get_current_delegate(db_session)
        stmt = select(Document).where(Document.id == document_id)
        document = db_session.scalars(stmt).first()
        if not document:
            return render_template("404.html"), 404
        if not is_document_visible(delegate.id, document, db_session):
            logger.warning(
                "Delegate {} cannot access document {}",
                delegate.id,
                document_id,
            )
            return render_template("403.html"), 403
        return render_template(
            "document_detail.html",
            document=document,
            committee=document.committee,
        )

    from classical_app.routes.delegations import delegations_bp

    flask_app.register_blueprint(delegations_bp)

    return flask_app


# Module-level app for production use and `flask run`
app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
