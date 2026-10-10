"""
Resume Upload and Correction Forms for RecruitFlow AI (Phase 4).
Includes CSRF validation and file constraints.
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, FloatField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, NumberRange, Email


class ResumeUploadForm(FlaskForm):
    """Secure form for uploading resume document."""
    resume_file = FileField(
        "Resume Document (PDF or DOCX)",
        validators=[
            FileRequired(message="Please select a resume file to upload."),
            FileAllowed(["pdf", "docx"], message="Only PDF (.pdf) and Word (.docx) documents are permitted.")
        ]
    )
    sync_profile = BooleanField(
        "Auto-sync extracted skills, experience, and contact details to candidate profile",
        default=True
    )
    submit = SubmitField("Upload & Process Resume")


class ResumeCorrectionForm(FlaskForm):
    """Allows candidate to review, correct, and save extracted resume data."""
    name = StringField("Full Name", validators=[Optional(), Length(max=128)])
    email = StringField("Email Address", validators=[Optional(), Length(max=120)])
    phone = StringField("Phone Number", validators=[Optional(), Length(max=32)])
    skills = StringField("Skills (comma-separated)", validators=[Optional(), Length(max=1024)])
    total_experience_years = FloatField(
        "Years of Experience",
        validators=[Optional(), NumberRange(min=0.0, max=50.0, message="Experience must be between 0 and 50 years.")]
    )
    linkedin_url = StringField("LinkedIn Profile URL", validators=[Optional(), Length(max=255)])
    github_url = StringField("GitHub Profile URL", validators=[Optional(), Length(max=255)])
    portfolio_url = StringField("Portfolio / Personal Website", validators=[Optional(), Length(max=255)])
    summary = TextAreaField("Professional Summary", validators=[Optional(), Length(max=2000)])
    sync_profile = BooleanField("Also sync these corrections to your Candidate Profile", default=True)
    submit = SubmitField("Save Corrections")
