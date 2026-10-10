"""
Interview Scheduling and Feedback WTForms for RecruitFlow AI (Phase 6).
"""
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    SelectMultipleField,
    BooleanField,
    SubmitField,
    DateTimeLocalField
)
from wtforms.validators import DataRequired, Optional, Length, URL


COMMON_TIMEZONES = [
    ("UTC", "UTC (Coordinated Universal Time)"),
    ("America/New_York", "America/New York (Eastern Time)"),
    ("America/Chicago", "America/Chicago (Central Time)"),
    ("America/Denver", "America/Denver (Mountain Time)"),
    ("America/Los_Angeles", "America/Los Angeles (Pacific Time)"),
    ("Europe/London", "Europe/London (GMT/BST)"),
    ("Europe/Berlin", "Europe/Berlin (CET/CEST)"),
    ("Asia/Kolkata", "Asia/Kolkata (IST - UTC+5:30)"),
    ("Asia/Dubai", "Asia/Dubai (GST - UTC+4)"),
    ("Asia/Singapore", "Asia/Singapore (SGT - UTC+8)"),
    ("Asia/Tokyo", "Asia/Tokyo (JST - UTC+9)"),
    ("Australia/Sydney", "Australia/Sydney (AEST - UTC+10)"),
]

INTERVIEW_FORMATS = [
    ("online", "Online Video Meeting (Zoom, Google Meet, Teams)"),
    ("phone", "Phone Screening"),
    ("in_person", "In-Person Onsite Interview"),
]

RATING_CHOICES = [
    ("", "-- Select Rating (1 - 5) --"),
    ("1", "1 - Far Below Expectations"),
    ("2", "2 - Below Expectations"),
    ("3", "3 - Meets Expectations"),
    ("4", "4 - Exceeds Expectations"),
    ("5", "5 - Exceptional"),
]

RECOMMENDATION_CHOICES = [
    ("strong_hire", "Strong Hire (Top Candidate)"),
    ("hire", "Hire (Meets Requisition Bar)"),
    ("neutral", "Neutral / Undecided"),
    ("no_hire", "No Hire"),
    ("strong_no_hire", "Strong No Hire (Major Deficiencies)"),
]


class InterviewScheduleForm(FlaskForm):
    """Form to schedule candidate interview rounds."""
    round_name = StringField(
        "Interview Round Name",
        validators=[DataRequired(message="Round name is required."), Length(max=64)],
        default="Technical Round 1"
    )
    interview_type = SelectField(
        "Interview Format",
        choices=INTERVIEW_FORMATS,
        default="online",
        validators=[DataRequired()]
    )
    scheduled_at = DateTimeLocalField(
        "Start Date & Time",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="Start date and time is required.")]
    )
    end_time = DateTimeLocalField(
        "End Date & Time",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="End date and time is required.")]
    )
    timezone = SelectField(
        "Time Zone",
        choices=COMMON_TIMEZONES,
        default="UTC",
        validators=[DataRequired()]
    )
    meeting_link = StringField(
        "Meeting URL / Video Link (Required for Online)",
        validators=[Optional(), Length(max=512)]
    )
    location = StringField(
        "Physical Location / Office Address (Required for In-Person)",
        validators=[Optional(), Length(max=255)]
    )
    interviewer_ids = SelectMultipleField(
        "Assign Interviewers",
        coerce=int,
        validators=[Optional()]
    )
    instructions = TextAreaField(
        "Interview Instructions / Agenda for Candidate",
        validators=[Optional(), Length(max=2000)]
    )
    submit = SubmitField("Schedule Interview")


class InterviewRescheduleForm(FlaskForm):
    """Form to edit or reschedule an interview."""
    round_name = StringField(
        "Interview Round Name",
        validators=[DataRequired(), Length(max=64)]
    )
    interview_type = SelectField(
        "Interview Format",
        choices=INTERVIEW_FORMATS,
        validators=[DataRequired()]
    )
    scheduled_at = DateTimeLocalField(
        "Start Date & Time",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired()]
    )
    end_time = DateTimeLocalField(
        "End Date & Time",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired()]
    )
    timezone = SelectField(
        "Time Zone",
        choices=COMMON_TIMEZONES,
        validators=[DataRequired()]
    )
    meeting_link = StringField(
        "Meeting URL / Video Link",
        validators=[Optional(), Length(max=512)]
    )
    location = StringField(
        "Physical Location",
        validators=[Optional(), Length(max=255)]
    )
    interviewer_ids = SelectMultipleField(
        "Assigned Interviewers",
        coerce=int,
        validators=[Optional()]
    )
    instructions = TextAreaField(
        "Instructions",
        validators=[Optional(), Length(max=2000)]
    )
    submit = SubmitField("Update & Reschedule")


class InterviewCancelForm(FlaskForm):
    """Form to cancel an interview session."""
    cancellation_reason = TextAreaField(
        "Cancellation Reason (Sent to candidate)",
        validators=[DataRequired(message="Please provide a reason for cancellation."), Length(max=1000)]
    )
    submit = SubmitField("Confirm Cancellation")


class InterviewFeedbackForm(FlaskForm):
    """Form for interviewers to submit structured evaluations."""
    technical_rating = SelectField("Technical Skills (1 - 5)", choices=RATING_CHOICES, validators=[Optional()])
    problem_solving_rating = SelectField("Problem Solving (1 - 5)", choices=RATING_CHOICES, validators=[Optional()])
    communication_rating = SelectField("Communication & Soft Skills (1 - 5)", choices=RATING_CHOICES, validators=[Optional()])
    role_relevant_rating = SelectField("Domain Knowledge & Relevant Experience (1 - 5)", choices=RATING_CHOICES, validators=[Optional()])

    overall_recommendation = SelectField(
        "Hiring Recommendation",
        choices=RECOMMENDATION_CHOICES,
        default="hire",
        validators=[DataRequired()]
    )
    strengths = TextAreaField(
        "Key Strengths & Demonstrations",
        validators=[Optional(), Length(max=3000)]
    )
    areas_for_improvement = TextAreaField(
        "Areas for Improvement / Growth",
        validators=[Optional(), Length(max=3000)]
    )
    notes = TextAreaField(
        "Internal Recruiter / Hiring Team Notes (Confidential)",
        validators=[Optional(), Length(max=5000)]
    )

    is_candidate_facing = BooleanField("Publish Candidate-Facing Summary")
    candidate_feedback = TextAreaField(
        "Constructive Feedback for Candidate (Visible to candidate if published)",
        validators=[Optional(), Length(max=2000)]
    )

    is_draft = BooleanField("Save as Draft (Don't submit yet)")
    submit = SubmitField("Submit Feedback")
