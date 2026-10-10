"""
Interview Scheduling and Management Service for RecruitFlow AI (Phase 6).
Handles:
- Validation for dates, times, URLs, locations, and timezones
- Single and multi-interviewer assignment with organization tenant checks
- Interleaving/overlap collision checking for interviewers
- Rescheduling and cancellation workflows with audit reasons
- In-app notification emissions to candidates and interviewers
"""
from datetime import datetime, timezone
from urllib.parse import urlparse
import logging
from app.core.extensions import db
from app.models.models import (
    Interview,
    InterviewAssignment,
    Application,
    Job,
    User,
    OrganizationMembership,
    utc_now
)
from app.services.notification_service import create_notification

logger = logging.getLogger(__name__)


class InterviewValidationError(ValueError):
    """Raised when interview scheduling validation fails."""
    pass


def validate_interview_schedule_data(
    interview_type: str,
    scheduled_at: datetime,
    end_time: datetime,
    meeting_link: str = None,
    location: str = None,
    allow_past: bool = False
):
    """
    Validates interview timing, type requirements, meeting URL, and in-person location.
    """
    if not scheduled_at:
        raise InterviewValidationError("Interview start date and time is required.")

    if not end_time:
        raise InterviewValidationError("Interview end date and time is required.")

    # Convert to UTC or ensure timezone-awareness
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    if end_time <= scheduled_at:
        raise InterviewValidationError("Interview end time must be later than start time.")

    # Format-specific validations
    norm_type = (interview_type or "").lower().strip()
    if norm_type not in Interview.VALID_TYPES:
        raise InterviewValidationError(f"Invalid interview format '{interview_type}'. Choose from {sorted(list(Interview.VALID_TYPES))}.")

    if norm_type in ("online", "technical", "cultural", "hr"):
        if not meeting_link or not meeting_link.strip():
            raise InterviewValidationError("A meeting link or video room URL is required for online interviews.")
        parsed = urlparse(meeting_link.strip())
        if not parsed.scheme or parsed.scheme not in ("http", "https"):
            raise InterviewValidationError("Meeting link must be a valid HTTP or HTTPS URL.")

    if norm_type == "in_person":
        if not location or not location.strip():
            raise InterviewValidationError("A physical address or room location is required for in-person interviews.")


def to_utc(dt: datetime) -> datetime:
    """Ensures datetime is timezone-aware UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def check_interviewer_conflicts(
    interviewer_ids: list[int],
    scheduled_at: datetime,
    end_time: datetime,
    exclude_interview_id: int = None
) -> list[str]:
    """
    Checks if any assigned interviewers have overlapping active interviews.
    Returns a list of warning messages detailing conflicts.
    """
    conflicts = []
    if not interviewer_ids:
        return conflicts

    sched_start = to_utc(scheduled_at)
    sched_end = to_utc(end_time)
    active_statuses = {"scheduled", "confirmed"}

    for uid in interviewer_ids:
        # Find active interviews assigned to this user
        assignments = (
            InterviewAssignment.query.join(Interview)
            .filter(
                InterviewAssignment.interviewer_user_id == uid,
                Interview.status.in_(active_statuses)
            )
        )
        if exclude_interview_id:
            assignments = assignments.filter(Interview.id != exclude_interview_id)

        for assign in assignments.all():
            other = assign.interview
            other_start = to_utc(other.scheduled_at)
            other_end = to_utc(other.end_time or other.scheduled_at)

            # Check interval overlap: max(start1, start2) < min(end1, end2)
            if max(sched_start, other_start) < min(sched_end, other_end):
                interviewer = assign.interviewer
                name = interviewer.full_name if interviewer else f"User #{uid}"
                conflicts.append(
                    f"{name} already has an active interview '{other.round_name}' "
                    f"scheduled between {other_start.strftime('%Y-%m-%d %H:%M')} and {other_end.strftime('%H:%M')} UTC."
                )

    return conflicts


def schedule_interview(
    application_id: int,
    round_name: str,
    interview_type: str,
    scheduled_at: datetime,
    end_time: datetime,
    timezone_str: str = "UTC",
    meeting_link: str = None,
    location: str = None,
    instructions: str = None,
    interviewer_ids: list[int] = None,
    created_by_user_id: int = None
) -> tuple[Interview, list[str]]:
    """
    Schedules an interview session for an application.
    Enforces tenant boundaries, timing rules, and emits notifications.
    Returns (interview, warnings).
    """
    application = db.session.get(Application, application_id)
    if not application:
        raise InterviewValidationError("Application not found.")

    if application.status in ("withdrawn", "rejected"):
        raise InterviewValidationError(f"Cannot schedule an interview for an application in '{application.status}' status.")

    job = application.job
    if not job:
        raise InterviewValidationError("Associated job opening not found.")

    # Timing and format validation
    validate_interview_schedule_data(
        interview_type=interview_type,
        scheduled_at=scheduled_at,
        end_time=end_time,
        meeting_link=meeting_link,
        location=location
    )

    # Validate interviewer tenant membership
    interviewer_ids = interviewer_ids or []
    valid_interviewers = []
    if interviewer_ids:
        org_members = (
            OrganizationMembership.query.filter(
                OrganizationMembership.organization_id == job.organization_id,
                OrganizationMembership.user_id.in_(interviewer_ids),
                OrganizationMembership.is_active == True
            ).all()
        )
        valid_org_user_ids = {m.user_id for m in org_members}
        invalid_ids = set(interviewer_ids) - valid_org_user_ids
        if invalid_ids:
            raise InterviewValidationError("Assigned interviewers must be active members of the job's organization.")
        valid_interviewers = [db.session.get(User, uid) for uid in interviewer_ids]

    # Check for schedule overlap conflicts
    warnings = check_interviewer_conflicts(interviewer_ids, scheduled_at, end_time)

    # Display name cache
    if valid_interviewers:
        names = ", ".join([u.full_name for u in valid_interviewers])
    else:
        names = "Hiring Team"

    interview = Interview(
        application_id=application.id,
        job_id=job.id,
        round_name=round_name.strip() if round_name else "Interview Round",
        interview_type=interview_type.strip().lower(),
        scheduled_at=scheduled_at,
        end_time=end_time,
        timezone=timezone_str or "UTC",
        interviewer_name=names,
        meeting_link=meeting_link.strip() if meeting_link else None,
        location=location.strip() if location else None,
        instructions=instructions.strip() if instructions else None,
        status="scheduled",
        created_by_user_id=created_by_user_id
    )
    db.session.add(interview)
    db.session.flush()

    # Assign interviewers
    for uid in interviewer_ids:
        assignment = InterviewAssignment(
            interview_id=interview.id,
            interviewer_user_id=uid
        )
        db.session.add(assignment)

    # Notify candidate
    create_notification(
        recipient_user_id=application.candidate_user_id,
        notification_type="interview_scheduled",
        title=f"Interview Scheduled: {interview.round_name}",
        message=f"An interview for position '{job.title}' has been scheduled for {scheduled_at.strftime('%b %d, %Y at %H:%M')} {interview.timezone}.",
        link_url=f"/interviews/{interview.id}",
        application_id=application.id,
        interview_id=interview.id
    )

    # Notify assigned interviewers
    for u in valid_interviewers:
        if u.id != created_by_user_id:
            create_notification(
                recipient_user_id=u.id,
                notification_type="interviewer_assigned",
                title=f"New Interview Assignment: {interview.round_name}",
                message=f"You have been assigned to evaluate candidate {application.candidate_user.full_name} for '{job.title}'.",
                link_url=f"/interviews/{interview.id}",
                application_id=application.id,
                interview_id=interview.id
            )

    db.session.commit()
    return interview, warnings


def reschedule_interview(
    interview_id: int,
    scheduled_at: datetime,
    end_time: datetime,
    timezone_str: str = "UTC",
    round_name: str = None,
    interview_type: str = None,
    meeting_link: str = None,
    location: str = None,
    instructions: str = None,
    interviewer_ids: list[int] = None,
    updated_by_user_id: int = None
) -> tuple[Interview, list[str]]:
    """
    Reschedules an existing interview. Emits notifications to candidate and interviewers.
    """
    interview = db.session.get(Interview, interview_id)
    if not interview:
        raise InterviewValidationError("Interview not found.")

    if interview.status == "cancelled":
        raise InterviewValidationError("Cannot reschedule a cancelled interview. Please schedule a new interview.")

    validate_interview_schedule_data(
        interview_type=interview_type or interview.interview_type,
        scheduled_at=scheduled_at,
        end_time=end_time,
        meeting_link=meeting_link if meeting_link is not None else interview.meeting_link,
        location=location if location is not None else interview.location
    )

    warnings = check_interviewer_conflicts(
        interviewer_ids or [a.interviewer_user_id for a in interview.assignments],
        scheduled_at,
        end_time,
        exclude_interview_id=interview.id
    )

    interview.scheduled_at = scheduled_at
    interview.end_time = end_time
    interview.timezone = timezone_str or interview.timezone
    if round_name:
        interview.round_name = round_name.strip()
    if interview_type:
        interview.interview_type = interview_type.strip().lower()
    if meeting_link is not None:
        interview.meeting_link = meeting_link.strip() if meeting_link else None
    if location is not None:
        interview.location = location.strip() if location else None
    if instructions is not None:
        interview.instructions = instructions.strip() if instructions else None
    interview.status = "scheduled"

    # Re-assign interviewers if supplied
    if interviewer_ids is not None:
        job = interview.application.job
        org_members = (
            OrganizationMembership.query.filter(
                OrganizationMembership.organization_id == job.organization_id,
                OrganizationMembership.user_id.in_(interviewer_ids),
                OrganizationMembership.is_active == True
            ).all()
        )
        valid_user_ids = {m.user_id for m in org_members}
        if set(interviewer_ids) - valid_user_ids:
            raise InterviewValidationError("All assigned interviewers must be active members of the job's organization.")

        # Replace assignments
        InterviewAssignment.query.filter_by(interview_id=interview.id).delete()
        for uid in interviewer_ids:
            db.session.add(InterviewAssignment(interview_id=interview.id, interviewer_user_id=uid))
        users = [db.session.get(User, uid) for uid in interviewer_ids]
        interview.interviewer_name = ", ".join([u.full_name for u in users]) if users else "Hiring Team"

    # Notify candidate of rescheduled time
    create_notification(
        recipient_user_id=interview.application.candidate_user_id,
        notification_type="interview_rescheduled",
        title=f"Interview Rescheduled: {interview.round_name}",
        message=f"Your interview for '{interview.application.job.title}' has been rescheduled to {scheduled_at.strftime('%b %d, %Y at %H:%M')} {interview.timezone}.",
        link_url=f"/interviews/{interview.id}",
        application_id=interview.application_id,
        interview_id=interview.id
    )

    db.session.commit()
    return interview, warnings


def cancel_interview(interview_id: int, cancellation_reason: str, cancelled_by_user_id: int = None) -> Interview:
    """
    Cancels an interview session with audit reason.
    Emits cancellation notifications.
    """
    interview = db.session.get(Interview, interview_id)
    if not interview:
        raise InterviewValidationError("Interview not found.")

    if interview.status == "completed":
        raise InterviewValidationError("Cannot cancel an interview that has already been completed.")

    interview.status = "cancelled"
    interview.cancellation_reason = cancellation_reason.strip() if cancellation_reason else "Cancelled by recruiter."
    
    # Notify candidate
    create_notification(
        recipient_user_id=interview.application.candidate_user_id,
        notification_type="interview_cancelled",
        title=f"Interview Cancelled: {interview.round_name}",
        message=f"Your scheduled interview for '{interview.application.job.title}' has been cancelled. Reason: {interview.cancellation_reason}",
        link_url=f"/interviews/{interview.id}",
        application_id=interview.application_id,
        interview_id=interview.id
    )

    db.session.commit()
    return interview


def update_interview_status(interview_id: int, new_status: str, updated_by_user_id: int = None) -> Interview:
    """
    Updates status to completed or no_show.
    """
    interview = db.session.get(Interview, interview_id)
    if not interview:
        raise InterviewValidationError("Interview not found.")

    norm_status = new_status.strip().lower()
    if norm_status not in Interview.VALID_STATUSES:
        raise InterviewValidationError(f"Invalid status '{new_status}'. Allowed: {sorted(list(Interview.VALID_STATUSES))}")

    interview.status = norm_status
    db.session.commit()
    return interview
