"""Database initialization script for ONE-MP Agent PoC."""

from pathlib import Path
from sqlalchemy.orm import Session

from shared.database import get_engine, init_db
from shared.seed_data import seed_all


def main() -> None:
    """
    Initialize the database and seed it with demo data.

    Creates all tables and populates with 4 delegations, 5 committees,
    9 delegates, 2 framework agreements, 18 documents, 24 document access
    rights, 5 meetings, and 19 agenda items.
    """
    db_path = Path(__file__).parent.parent / "one_agent.db"
    engine = get_engine(str(db_path))
    init_db(engine)

    with Session(engine) as session:
        seed_all(session)
        session.commit()

    print(f"Database initialized at {db_path}")


if __name__ == "__main__":
    main()
