"""
WTForms Form Definitions for Authentication, Profiles, and Account Settings.
"""
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    TextAreaField,
    FloatField,
    SubmitField
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    EqualTo,
    Optional,
    URL,
    Regexp,
    ValidationError
)
from app.models.models import User, Organization


class LoginForm(FlaskForm):
    """User login form."""
    email = StringField(
        "Email Address",
        validators=[DataRequired(message="Email address is required."), Email(message="Enter a valid email address.")]
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Password is required.")]
    )
    remember = BooleanField("Remember Me")
    submit = SubmitField("Sign In")


class CandidateRegistrationForm(FlaskForm):
    """Candidate account registration form."""
    full_name = StringField(
        "Full Name",
        validators=[DataRequired(message="Full name is required."), Length(min=2, max=128)]
    )
    email = StringField(
        "Email Address",
        validators=[DataRequired(message="Email address is required."), Email(message="Enter a valid email address."), Length(max=120)]
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, message="Password must be at least 8 characters long.")
        ]
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords must match.")
        ]
    )
    agree_terms = BooleanField(
        "I agree to the Terms of Service and Privacy Notice",
        validators=[DataRequired(message="You must accept the terms and privacy notice to continue.")]
    )
    submit = SubmitField("Create Candidate Account")

    def validate_email(self, field):
        norm_email = field.data.strip().lower()
        if User.query.filter_by(email=norm_email).first():
            raise ValidationError("An account with this email address already exists.")


class RecruiterRegistrationForm(FlaskForm):
    """Recruiter and organization registration form."""
    full_name = StringField(
        "Full Name",
        validators=[DataRequired(message="Full name is required."), Length(min=2, max=128)]
    )
    email = StringField(
        "Work Email",
        validators=[DataRequired(message="Work email is required."), Email(message="Enter a valid email address."), Length(max=120)]
    )
    organization_name = StringField(
        "Organization / Company Name",
        validators=[DataRequired(message="Organization name is required."), Length(min=2, max=128)]
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, message="Password must be at least 8 characters long.")
        ]
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords must match.")
        ]
    )
    agree_terms = BooleanField(
        "I agree to the Terms of Service and Privacy Notice",
        validators=[DataRequired(message="You must accept the terms and privacy notice to continue.")]
    )
    submit = SubmitField("Create Recruiter Account")

    def validate_email(self, field):
        norm_email = field.data.strip().lower()
        if User.query.filter_by(email=norm_email).first():
            raise ValidationError("An account with this email address already exists.")


class ForgotPasswordForm(FlaskForm):
    """Password reset request form."""
    email = StringField(
        "Email Address",
        validators=[DataRequired(message="Email address is required."), Email(message="Enter a valid email address.")]
    )
    submit = SubmitField("Send Password Reset Link")


class ResetPasswordForm(FlaskForm):
    """Set new password using reset token."""
    password = PasswordField(
        "New Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, message="Password must be at least 8 characters long.")
        ]
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(message="Please confirm your password."),
            EqualTo("password", message="Passwords must match.")
        ]
    )
    submit = SubmitField("Reset Password")


class CandidateProfileForm(FlaskForm):
    """Candidate profile edit form."""
    headline = StringField("Professional Headline", validators=[Optional(), Length(max=255)])
    location = StringField("Location", validators=[Optional(), Length(max=128)])
    phone = StringField("Phone Number", validators=[Optional(), Length(max=32)])
    years_of_experience = FloatField("Years of Experience", validators=[Optional()])
    skills = TextAreaField("Key Skills (comma separated)", validators=[Optional()])
    professional_summary = TextAreaField("Professional Summary", validators=[Optional(), Length(max=2000)])
    portfolio_url = StringField("Portfolio Website", validators=[Optional(), URL(message="Invalid portfolio URL.")])
    linkedin_url = StringField("LinkedIn Profile URL", validators=[Optional(), URL(message="Invalid LinkedIn URL.")])
    github_url = StringField("GitHub Profile URL", validators=[Optional(), URL(message="Invalid GitHub URL.")])
    submit = SubmitField("Save Profile")


class RecruiterProfileForm(FlaskForm):
    """Recruiter profile edit form."""
    job_title = StringField("Job Title", validators=[Optional(), Length(max=128)])
    department = StringField("Department", validators=[Optional(), Length(max=64)])
    phone = StringField("Phone Number", validators=[Optional(), Length(max=32)])
    company_name = StringField("Company Name", validators=[Optional(), Length(max=128)])
    submit = SubmitField("Save Profile")


class ChangePasswordForm(FlaskForm):
    """Change password form in account settings."""
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(),
            Length(min=8, message="New password must be at least 8 characters.")
        ]
    )
    confirm_new_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(),
            EqualTo("new_password", message="Passwords must match.")
        ]
    )
    submit = SubmitField("Update Password")


class AccountSettingsForm(FlaskForm):
    """Account basic info update form."""
    full_name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=128)])
    submit = SubmitField("Save Account Changes")
