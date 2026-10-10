"""
RecruitFlow AI - Application Entrypoint.
Enables running the application server via python run.py or flask run.
"""
import os
from app import create_app
from app.core.extensions import db
from app.models.models import (
    User,
    RecruiterProfile,
    CandidateProfile,
    Job,
    Resume,
    Application,
    Interview,
    InterviewAssignment,
    InterviewFeedback,
    ApplicationStageHistory,
    Notification,
    MatchResult,
    ResumeAnalysis
)

app = create_app(os.getenv("FLASK_ENV", "development"))


@app.shell_context_processor
def make_shell_context():
    """Provides interactive REPL context with db and domain models."""
    return {
        "db": db,
        "User": User,
        "RecruiterProfile": RecruiterProfile,
        "CandidateProfile": CandidateProfile,
        "Job": Job,
        "Resume": Resume,
        "Application": Application,
        "Interview": Interview,
        "InterviewAssignment": InterviewAssignment,
        "InterviewFeedback": InterviewFeedback,
        "ApplicationStageHistory": ApplicationStageHistory,
        "Notification": Notification,
        "MatchResult": MatchResult,
        "ResumeAnalysis": ResumeAnalysis,
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1")
    app.run(host="127.0.0.1", port=port, debug=debug)
