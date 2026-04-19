"""
WTForms form classes for the 4-step delegate-creation wizard.

Each step is represented by a dedicated FlaskForm subclass.
Choices for dynamic fields (committee_ids, access_level) are
populated by the route handler, not hardcoded here.
"""

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    FieldList,
    FormField,
    HiddenField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
)
from wtforms.validators import DataRequired, Email, ValidationError


class Step1PersonalInfoForm(FlaskForm):
    """Step 1 of the delegate wizard: personal information."""

    full_name = StringField(
        "Full Name",
        validators=[DataRequired()],
    )
    email = StringField(
        "Email",
        validators=[DataRequired(), Email()],
    )
    function = StringField(
        "Function",
        validators=[DataRequired()],
    )
    title = StringField("Title")
    submit = SubmitField("Next")


class Step2CommitteesForm(FlaskForm):
    """Step 2 of the delegate wizard: committee selection.

    Choices for committee_ids are set dynamically in the route
    handler before form rendering or validation.
    """

    committee_ids = SelectMultipleField(
        "Committees",
        coerce=str,
    )
    submit = SubmitField("Next")

    def validate_committee_ids(
        self, field: SelectMultipleField
    ) -> None:
        """Ensure at least one committee is selected.

        Args:
            field: The committee_ids field being validated.

        Raises:
            ValidationError: If no committees are selected.
        """
        if not field.data:
            raise ValidationError(
                "Please select at least one committee."
            )


class DARRowForm(FlaskForm):
    """Subform representing one Document Access Right row.

    Choices for access_level are set dynamically in the route
    handler. No CSRF token is needed as this is embedded via
    FieldList in Step3DARsForm.
    """

    class Meta:
        """Disable CSRF for the embedded subform."""

        csrf = False

    committee_id = HiddenField("Committee ID")
    access_level = SelectField(
        "Access Level",
        coerce=str,
    )
    retroactive = BooleanField("Retroactive")


class Step3DARsForm(FlaskForm):
    """Step 3 of the delegate wizard: document access rights.

    Contains a dynamic list of DARRowForm subforms, one per
    committee selected in step 2.
    """

    rows = FieldList(FormField(DARRowForm), min_entries=0)
    submit = SubmitField("Next")


class Step4ReviewForm(FlaskForm):
    """Step 4 of the delegate wizard: review and submit.

    Bare form providing CSRF protection for the final submission.
    All data is read from the session; no additional fields are
    required here.
    """

    submit = SubmitField("Submit")
