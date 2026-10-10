"""
WTForms definitions for Job Management and Candidate Applications (Phase 3).
"""
from datetime import datetime, timezone
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    DecimalField,
    FloatField,
    DateTimeField,
    BooleanField,
    SubmitField
)
from wtforms.validators import (
    DataRequired,
    Length,
    Optional,
    NumberRange,
    ValidationError
)


class JobForm(FlaskForm):
    """Job creation and editing form for recruiters."""
    title = StringField(
        "Job Title",
        validators=[DataRequired(message="Job title is required."), Length(max=128)]
    )
    department = StringField(
        "Department",
        validators=[Optional(), Length(max=64)]
    )
    location = StringField(
        "Location",
        validators=[Optional(), Length(max=128)]
    )
    workplace_type = SelectField(
        "Workplace Type",
        choices=[("hybrid", "Hybrid"), ("remote", "Remote"), ("onsite", "On-site")],
        default="hybrid",
        validators=[DataRequired()]
    )
    employment_type = SelectField(
        "Employment Type",
        choices=[
            ("full-time", "Full-time"),
            ("part-time", "Part-time"),
            ("contract", "Contract"),
            ("internship", "Internship")
        ],
        default="full-time",
        validators=[DataRequired()]
    )
    status = SelectField(
        "Status",
        choices=[
            ("draft", "Draft (Hidden from candidates)"),
            ("published", "Published (Accepting applications)"),
            ("closed", "Closed (No new applications)"),
            ("archived", "Archived")
        ],
        default="published",
        validators=[DataRequired()]
    )
    minimum_experience_years = FloatField(
        "Minimum Experience (Years)",
        default=0.0,
        validators=[NumberRange(min=0.0, max=50.0, message="Experience must be between 0 and 50 years.")]
    )
    maximum_experience_years = FloatField(
        "Maximum Experience (Years)",
        validators=[Optional(), NumberRange(min=0.0, max=50.0)]
    )
    minimum_qualification = StringField(
        "Minimum Qualification",
        validators=[Optional(), Length(max=128)]
    )
    salary_min = DecimalField(
        "Minimum Salary",
        places=2,
        validators=[Optional(), NumberRange(min=0, message="Salary cannot be negative.")]
    )
    salary_max = DecimalField(
        "Maximum Salary",
        places=2,
        validators=[Optional(), NumberRange(min=0, message="Salary cannot be negative.")]
    )
    salary_currency = SelectField(
        "Currency",
        choices=[("USD", "USD ($)"), ("EUR", "EUR (€)"), ("GBP", "GBP (£)"), ("INR", "INR (₹)")],
        default="USD",
        validators=[DataRequired()]
    )
    required_skills = TextAreaField(
        "Required Skills (Comma or line separated)",
        validators=[DataRequired(message="Please specify at least one required skill.")]
    )
    preferred_skills = TextAreaField(
        "Preferred Skills",
        validators=[Optional()]
    )
    description = TextAreaField(
        "Job Description & Overview",
        validators=[DataRequired(message="Job description is required.")]
    )
    responsibilities = TextAreaField(
        "Key Responsibilities",
        validators=[Optional()]
    )
    application_deadline = DateTimeField(
        "Application Deadline (Optional, YYYY-MM-DD HH:MM)",
        format="%Y-%m-%d %H:%M",
        validators=[Optional()]
    )
    submit = SubmitField("Save Job Requisition")

    def validate_maximum_experience_years(self, field):
        if field.data is not None and self.minimum_experience_years.data is not None:
            if field.data < self.minimum_experience_years.data:
                raise ValidationError("Maximum experience cannot be less than minimum experience.")

    def validate_salary_max(self, field):
        if field.data is not None and self.salary_min.data is not None:
            if field.data < self.salary_min.data:
                raise ValidationError("Maximum salary cannot be less than minimum salary.")


class ApplicationForm(FlaskForm):
    """Job application submission form for candidates."""
    cover_letter = TextAreaField(
        "Cover Letter / Candidate Note",
        validators=[
            Optional(),
            Length(max=5000, message="Cover letter cannot exceed 5000 characters.")
        ]
    )
    submit = SubmitField("Submit Application")


class ApplicationStatusUpdateForm(FlaskForm):
    """Form for recruiters to update candidate pipeline stage and notes."""
    status = SelectField(
        "Application Status",
        choices=[
            ("submitted", "Submitted"),
            ("under_review", "Under Review"),
            ("shortlisted", "Shortlisted"),
            ("interview", "Interview Scheduled"),
            ("interview_completed", "Interview Completed"),
            ("offered", "Offer Extended"),
            ("hired", "Hired"),
            ("rejected", "Rejected")
        ],
        validators=[DataRequired()]
    )
    notes = TextAreaField(
        "Recruiter Assessment / Internal Notes",
        validators=[Optional(), Length(max=3000)]
    )
    rejection_reason_code = SelectField(
        "Rejection Reason Category",
        choices=[
            ("", "-- Select Reason (if rejecting) --"),
            ("skill_gap", "Required skill not demonstrated"),
            ("experience_gap", "Relevant experience requirement not met"),
            ("qualification_gap", "Qualification requirement not met"),
            ("role_changed", "Role requirements or priorities changed"),
            ("position_filled", "Position filled by another candidate"),
            ("other", "Other recruitment consideration")
        ],
        validators=[Optional()]
    )
    rejection_reason_text = TextAreaField(
        "Candidate-Facing Rejection Explanation",
        validators=[Optional(), Length(max=2000)]
    )
    rejection_feedback_published = BooleanField(
        "Publish structured feedback to candidate"
    )
    submit = SubmitField("Update Status")
