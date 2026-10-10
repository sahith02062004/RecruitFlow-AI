"""
Hiring Pipeline Service for RecruitFlow AI (Phase 6).
Handles:
- State machine for candidate application stages
- Valid stage transition enforcement
- Immutable audit history recording in ApplicationStageHistory
- Human-in-the-loop governance: AI scores never automatically transition stages
- Tenant isolation and recruiter authorization
- Candidate in-app notifications on permissible stage changes
- Kanban pipeline data aggregation
"""
import logging
from app.core.extensions import db
from app.models.models import (
    Application,
    ApplicationStageHistory,
    OrganizationMembership,
    User,
    utc_now
)
from app.services.notification_service import create_notification

logger = logging.getLogger(__name__)


class StageTransitionError(ValueError):
    """Raised when an application stage transition violates workflow rules."""
    pass


# Directed workflow transition graph
VALID_STAGE_TRANSITIONS = {
    "submitted": {"under_review", "shortlisted", "rejected", "withdrawn"},
    "under_review": {"submitted", "shortlisted", "interview", "rejected", "withdrawn"},
    "shortlisted": {"under_review", "interview", "rejected", "withdrawn"},
    "interview": {"interview_completed", "interview", "shortlisted", "rejected", "withdrawn"},
    "interview_completed": {"interview", "offered", "rejected", "withdrawn"},
    "offered": {"hired", "rejected", "withdrawn"},
    "rejected": {"under_review", "submitted"},  # Admin/Recruiter reconsideration
    "withdrawn": set(),  # Terminal state
    "hired": set(),      # Successful terminal state
}

STAGE_DISPLAY_NAMES = {
    "submitted": "Submitted",
    "under_review": "Under Review",
    "shortlisted": "Shortlisted",
    "interview": "Interview Scheduled",
    "interview_completed": "Interview Completed",
    "offered": "Offer Extended",
    "hired": "Hired",
    "rejected": "Rejected",
    "withdrawn": "Withdrawn"
}

# Stages that candidates receive notification updates for
CANDIDATE_NOTIFIED_STAGES = {
    "under_review",
    "shortlisted",
    "interview",
    "interview_completed",
    "offered",
    "hired",
    "rejected"
}


def transition_application_stage(
    application_id: int,
    new_stage: str,
    changed_by_user: User,
    reason: str = None
) -> tuple[Application, ApplicationStageHistory]:
    """
    Executes a validated stage transition for an application.
    Enforces RBAC, tenant organization isolation, state machine transitions,
    and records an immutable ApplicationStageHistory entry.
    """
    application = db.session.get(Application, application_id)
    if not application:
        raise StageTransitionError("Application not found.")

    new_stage = (new_stage or "").strip().lower()
    if new_stage not in Application.VALID_STATUSES:
        raise StageTransitionError(f"Invalid application stage '{new_stage}'.")

    current_stage = application.status

    # Candidates can only withdraw their own application
    if changed_by_user.role == "candidate":
        if changed_by_user.id != application.candidate_user_id:
            raise StageTransitionError("Unauthorized access to candidate application.")
        if new_stage != "withdrawn":
            raise StageTransitionError("Candidates are only permitted to withdraw their application.")

    # Recruiters must belong to the job's organization
    elif changed_by_user.role in ("recruiter", "organization_admin"):
        job = application.job
        membership = OrganizationMembership.query.filter_by(
            organization_id=job.organization_id,
            user_id=changed_by_user.id,
            is_active=True
        ).first()
        if not membership:
            raise StageTransitionError("Unauthorized: Recruiter does not belong to the requisition's organization.")

    elif changed_by_user.role != "platform_admin":
        raise StageTransitionError("Unauthorized role for application stage management.")

    # Prevent changing withdrawn applications
    if current_stage == "withdrawn" and changed_by_user.role != "platform_admin":
        raise StageTransitionError("Cannot change stage of a withdrawn application.")

    # If same stage and not interview-to-interview re-entry, no-op
    if current_stage == new_stage and current_stage != "interview":
        return application, None

    # Validate transition against state machine
    allowed = VALID_STAGE_TRANSITIONS.get(current_stage, set())
    if new_stage not in allowed and changed_by_user.role != "platform_admin":
        curr_disp = STAGE_DISPLAY_NAMES.get(current_stage, current_stage)
        new_disp = STAGE_DISPLAY_NAMES.get(new_stage, new_stage)
        raise StageTransitionError(
            f"Invalid stage transition from '{curr_disp}' to '{new_disp}'. "
            f"Permitted next stages: {[STAGE_DISPLAY_NAMES.get(s, s) for s in allowed]}"
        )

    # Record history
    history = ApplicationStageHistory(
        application_id=application.id,
        previous_stage=current_stage,
        new_stage=new_stage,
        changed_by_user_id=changed_by_user.id,
        reason=reason.strip() if reason else None
    )
    db.session.add(history)

    # Update application
    application.status = new_stage
    if new_stage == "withdrawn":
        application.withdrawn_at = utc_now()

    # Emit notification to candidate if appropriate
    if new_stage in CANDIDATE_NOTIFIED_STAGES and changed_by_user.role != "candidate":
        stage_label = STAGE_DISPLAY_NAMES.get(new_stage, new_stage)
        create_notification(
            recipient_user_id=application.candidate_user_id,
            notification_type="stage_changed",
            title=f"Application Update: {application.job.title}",
            message=f"Your application status for '{application.job.title}' has progressed to '{stage_label}'.",
            link_url=f"/applications/{application.id}",
            application_id=application.id
        )

    db.session.commit()
    return application, history


def get_pipeline_stages_for_job(job_id: int):
    """
    Returns applications grouped by stage for a specific requisition kanban board.
    """
    stages = ["submitted", "under_review", "shortlisted", "interview", "interview_completed", "offered", "hired", "rejected"]
    board_data = {stage: [] for stage in stages}

    applications = (
        Application.query.filter_by(job_id=job_id)
        .filter(Application.status != "withdrawn")
        .order_by(Application.applied_at.desc())
        .all()
    )

    for app in applications:
        stage = app.status
        if stage in board_data:
            board_data[stage].append(app)

    return board_data
