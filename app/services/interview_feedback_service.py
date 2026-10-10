"""
Interview Feedback Service for RecruitFlow AI (Phase 6).
Handles:
- Structured rubric evaluations (1-5 ratings across 4 technical/competency dimensions)
- Validation of ratings and overall recommendations
- Strict feedback privacy: candidates can never view internal ratings or notes
- Safe candidate-facing feedback filtering
- Interviewer authorization checks: only assigned interviewers or org admins can submit feedback
"""
from datetime import datetime, timezone
import logging
from app.core.extensions import db
from app.models.models import (
    Interview,
    InterviewFeedback,
    InterviewAssignment,
    User,
    OrganizationMembership,
    utc_now
)

logger = logging.getLogger(__name__)


class FeedbackValidationError(ValueError):
    """Raised when interview feedback validation fails."""
    pass


def validate_ratings(
    technical: int = None,
    problem_solving: int = None,
    communication: int = None,
    role_relevant: int = None
):
    """Validates that provided rating integers are strictly between 1 and 5 inclusive."""
    ratings = {
        "Technical knowledge": technical,
        "Problem solving": problem_solving,
        "Communication": communication,
        "Role relevance": role_relevant
    }
    for name, r in ratings.items():
        if r is not None:
            if not isinstance(r, int) or r < 1 or r > 5:
                raise FeedbackValidationError(f"{name} rating must be an integer between 1 and 5.")


def submit_or_update_feedback(
    interview_id: int,
    interviewer_user_id: int,
    technical_rating: int = None,
    problem_solving_rating: int = None,
    communication_rating: int = None,
    role_relevant_rating: int = None,
    strengths: str = None,
    areas_for_improvement: str = None,
    notes: str = None,
    overall_recommendation: str = "neutral",
    is_candidate_facing: bool = False,
    candidate_feedback: str = None,
    is_draft: bool = False
) -> InterviewFeedback:
    """
    Creates or updates structured feedback for an interview session.
    Validates rating scale 1-5, authorization, and recommendation values.
    """
    interview = db.session.get(Interview, interview_id)
    if not interview:
        raise FeedbackValidationError("Interview session not found.")

    # Validate interviewer assignment or org admin permission
    interviewer = db.session.get(User, interviewer_user_id)
    if not interviewer:
        raise FeedbackValidationError("Interviewer user not found.")

    is_assigned = (
        InterviewAssignment.query.filter_by(
            interview_id=interview.id,
            interviewer_user_id=interviewer_user_id
        ).first() is not None
    )

    job = interview.application.job
    is_org_admin = (
        OrganizationMembership.query.filter_by(
            organization_id=job.organization_id,
            user_id=interviewer_user_id,
            membership_role="admin",
            is_active=True
        ).first() is not None
        or interviewer.role == "platform_admin"
    )

    if not is_assigned and not is_org_admin:
        raise FeedbackValidationError("User is not authorized to submit feedback for this interview.")

    # Validate ratings
    validate_ratings(
        technical=technical_rating,
        problem_solving=problem_solving_rating,
        communication=communication_rating,
        role_relevant=role_relevant_rating
    )

    norm_rec = (overall_recommendation or "neutral").strip().lower()
    if norm_rec not in InterviewFeedback.VALID_RECOMMENDATIONS:
        raise FeedbackValidationError(
            f"Invalid recommendation '{overall_recommendation}'. Allowed: {sorted(list(InterviewFeedback.VALID_RECOMMENDATIONS))}"
        )

    # Find existing feedback or create new
    feedback = InterviewFeedback.query.filter_by(
        interview_id=interview.id,
        interviewer_user_id=interviewer_user_id
    ).first()

    if not feedback:
        feedback = InterviewFeedback(
            interview_id=interview.id,
            interviewer_user_id=interviewer_user_id
        )
        db.session.add(feedback)

    feedback.technical_rating = technical_rating
    feedback.problem_solving_rating = problem_solving_rating
    feedback.communication_rating = communication_rating
    feedback.role_relevant_rating = role_relevant_rating
    feedback.strengths = strengths.strip() if strengths else None
    feedback.areas_for_improvement = areas_for_improvement.strip() if areas_for_improvement else None
    feedback.notes = notes.strip() if notes else None
    feedback.overall_recommendation = norm_rec
    feedback.is_candidate_facing = bool(is_candidate_facing)
    feedback.candidate_feedback = candidate_feedback.strip() if candidate_feedback else None
    feedback.status = "draft" if is_draft else "submitted"
    if not is_draft and not feedback.submitted_at:
        feedback.submitted_at = utc_now()

    feedback.calculate_overall_score()
    db.session.commit()
    return feedback


def get_candidate_visible_feedback(interview_id: int) -> list[dict]:
    """
    Returns only explicitly candidate-facing feedback summaries for an interview.
    Never exposes internal ratings, private notes, or internal recommendations.
    """
    records = InterviewFeedback.query.filter_by(
        interview_id=interview_id,
        status="submitted",
        is_candidate_facing=True
    ).all()

    results = []
    for f in records:
        if f.candidate_feedback:
            results.append({
                "candidate_feedback": f.candidate_feedback,
                "submitted_at": f.submitted_at.strftime("%b %d, %Y") if f.submitted_at else None
            })
    return results
