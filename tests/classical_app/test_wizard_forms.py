"""
Unit tests for the WTForms form classes in the delegate wizard.

Tests cover field-level validation, custom validators, and
structural properties of Step1PersonalInfoForm, Step2CommitteesForm,
and DARRowForm without requiring a full Flask application context.
"""

import pytest
from flask import Flask

from classical_app.forms.delegate_wizard import (
    DARRowForm,
    Step1PersonalInfoForm,
    Step2CommitteesForm,
)


@pytest.fixture
def app() -> Flask:
    """Minimal Flask app with CSRF disabled for form unit tests."""
    flask_app = Flask(__name__)
    flask_app.config["WTF_CSRF_ENABLED"] = False
    flask_app.config["SECRET_KEY"] = "test-secret"
    return flask_app


class TestStep1Form:
    """Validation rules for Step1PersonalInfoForm."""

    def test_email_format_invalid(self, app: Flask) -> None:
        """Non-email string fails Email() validator."""
        with app.test_request_context(
            "/",
            method="POST",
            data={
                "full_name": "Alice",
                "email": "notanemail",
                "function": "Attaché",
            },
        ):
            form = Step1PersonalInfoForm()
            assert not form.validate()
            assert form.email.errors

    def test_email_required(self, app: Flask) -> None:
        """Empty email fails DataRequired validator."""
        with app.test_request_context(
            "/",
            method="POST",
            data={
                "full_name": "Alice",
                "email": "",
                "function": "Attaché",
            },
        ):
            form = Step1PersonalInfoForm()
            assert not form.validate()
            assert form.email.errors

    def test_full_name_required(self, app: Flask) -> None:
        """Empty full_name fails DataRequired validator."""
        with app.test_request_context(
            "/",
            method="POST",
            data={
                "full_name": "",
                "email": "alice@example.com",
                "function": "Attaché",
            },
        ):
            form = Step1PersonalInfoForm()
            assert not form.validate()
            assert form.full_name.errors

    def test_title_optional(self, app: Flask) -> None:
        """Form is valid when title is omitted."""
        with app.test_request_context(
            "/",
            method="POST",
            data={
                "full_name": "Alice",
                "email": "alice@example.com",
                "function": "Attaché",
            },
        ):
            form = Step1PersonalInfoForm()
            assert form.validate(), form.errors

    def test_function_required(self, app: Flask) -> None:
        """Empty function fails DataRequired validator."""
        with app.test_request_context(
            "/",
            method="POST",
            data={
                "full_name": "Alice",
                "email": "alice@example.com",
                "function": "",
            },
        ):
            form = Step1PersonalInfoForm()
            assert not form.validate()
            assert form.function.errors


class TestStep2Form:
    """Validation rules for Step2CommitteesForm."""

    def test_zero_selection_fails(self, app: Flask) -> None:
        """Empty committee_ids list triggers custom ValidationError."""
        with app.test_request_context(
            "/",
            method="POST",
            data={},
        ):
            form = Step2CommitteesForm()
            # Provide valid choices so SelectMultipleField accepts them.
            form.committee_ids.choices = [("c1", "Committee 1")]
            assert not form.validate()
            assert form.committee_ids.errors
            assert any(
                "at least one committee" in e
                for e in form.committee_ids.errors
            )

    def test_one_selection_passes(self, app: Flask) -> None:
        """Selecting one committee satisfies the custom validator."""
        with app.test_request_context(
            "/",
            method="POST",
            data={"committee_ids": ["c1"]},
        ):
            form = Step2CommitteesForm()
            form.committee_ids.choices = [("c1", "Committee 1")]
            assert form.validate(), form.errors


class TestDARRowForm:
    """Structural properties of DARRowForm."""

    def test_fields_present(self, app: Flask) -> None:
        """DARRowForm exposes committee_id, access_level, retroactive."""
        with app.test_request_context("/"):
            form = DARRowForm()
            assert hasattr(form, "committee_id")
            assert hasattr(form, "access_level")
            assert hasattr(form, "retroactive")

    def test_no_csrf(self) -> None:
        """DARRowForm.Meta.csrf is False (safe for FieldList embedding)."""
        assert DARRowForm.Meta.csrf is False
