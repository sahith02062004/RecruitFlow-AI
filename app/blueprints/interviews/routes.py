"""
Interviews Blueprint Routes for RecruitFlow AI (Phase 6).
Handles:
- Recruiter interview management, scheduling, rescheduling, and cancellation
- Candidate interview schedule visibility and meeting details
- Multi-interviewer assignment and conflict alerts
- Confidential interviewer feedback rubric submissions
- Role-based authorization and tenant organization data isolation
"""
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from flask_login import current_user, login_required
from app.core.extensions import db
from app.core.security import candidate_required, recruiter_required
from app.models.models import (
    Interview,
    InterviewAssignment,
    InterviewFeedback,
    Application,
    Job,
    User,
    OrganizationMembership,
    utc_now
)
from app.blueprints.interviews.forms import (
    InterviewScheduleForm,
    InterviewRescheduleForm,
    InterviewCancelForm,
    InterviewFeedbackForm
)
from app.services.interview_service import (
    schedule_interview,
    reschedule_interview,
    cancel_interview,
    update_interview_status,
    InterviewValidationError
)
from app.services.interview_feedback_service import (
    submit_or_update_feedback,
    get_candidate_visible_feedback,
    FeedbackValidationError
)
from app.services.hiring_pipeline_service import transition_application_stage

interviews_bp = Blueprint("interviews", __name__, url_prefix="/interviews")


def get_recruiter_organization_id():
    """Returns active organization ID for current recruiter user, or None."""
    if current_user.role == "platform_admin":
        return None
    membership = current_user.memberships.filter_by(is_active=True).first()
    return membership.organization_id if membership else None


def check_recruiter_interview_access(interview: Interview) -> bool:
    """Verifies that current user is an authorized recruiter for the interview's requisition."""
    if current_user.role == "platform_admin":
        return True
    if current_user.role not in ("recruiter", "organization_admin"):
        return False
    job = interview.application.job
    membership = current_user.memberships.filter_by(
        organization_id=job.organization_id,
        is_active=True
    ).first()
    return membership is not None


@interviews_bp.route("/")
@login_required
def index():
    """
    Recruiter interview dashboard.
    Displays interviews for jobs in the recruiter's organization.
    Candidates accessing this endpoint are redirected to their personalized interview list.
    """
    if current_user.role == "candidate":
        return redirect(url_for("interviews.my_interviews"))

    status_filter = request.args.get("status")
    job_id = request.args.get("job_id", type=int)

    query = Interview.query.join(Application).join(Job)

    if current_user.role != "platform_admin":
        org_id = get_recruiter_organization_id()
        if not org_id:
            return render_template("interviews/index.html", interviews=[], current_status=status_filter)
        query = query.filter(Job.organization_id == org_id)

    if status_filter:
        query = query.filter(Interview.status == status_filter)
    if job_id:
        query = query.filter(Interview.job_id == job_id)

    interviews = query.order_by(Interview.scheduled_at.desc()).all()

    # Load recruiter's jobs for filter dropdown
    if current_user.role == "platform_admin":
        jobs = Job.query.all()
    else:
        org_id = get_recruiter_organization_id()
        jobs = Job.query.filter_by(organization_id=org_id).all() if org_id else []

    return render_template(
        "interviews/index.html",
        interviews=interviews,
        jobs=jobs,
        current_status=status_filter,
        current_job_id=job_id
    )


@interviews_bp.route("/my-interviews")
@login_required
def my_interviews():
    """
    Candidate or assigned interviewer personal interview schedule.
    - If Candidate: shows interviews scheduled for their submitted applications.
    - If Interviewer/Recruiter: shows interviews assigned to them.
    """
    if current_user.role == "candidate":
        interviews = (
            Interview.query.join(Application)
            .filter(Application.candidate_user_id == current_user.id)
            .order_by(Interview.scheduled_at.desc())
            .all()
        )
        return render_template("interviews/my_interviews.html", interviews=interviews, is_candidate=True)

    # For recruiters / team members: interviews they are assigned to
    assignments = InterviewAssignment.query.filter_by(interviewer_user_id=current_user.id).all()
    interview_ids = [a.interview_id for a in assignments]
    interviews = (
        Interview.query.filter(Interview.id.in_(interview_ids))
        .order_by(Interview.scheduled_at.desc())
        .all()
    ) if interview_ids else []

    return render_template("interviews/my_interviews.html", interviews=interviews, is_candidate=False)


@interviews_bp.route("/schedule/<int:application_id>", methods=["GET", "POST"])
@recruiter_required
def schedule(application_id):
    """
    Schedules an interview for a candidate application.
    Enforces organization boundaries and populates team members.
    """
    application = db.session.get(Application, application_id)
    if not application:
        abort(404)

    job = application.job
    # Organization access check
    if current_user.role != "platform_admin":
        membership = current_user.memberships.filter_by(
            organization_id=job.organization_id,
            is_active=True
        ).first()
        if not membership:
            abort(403)

    form = InterviewScheduleForm()

    # Populate interviewer choices with active organization members
    org_members = (
        OrganizationMembership.query.filter_by(
            organization_id=job.organization_id,
            is_active=True
        ).all()
    )
    form.interviewer_ids.choices = [
        (m.user_id, f"{m.user.full_name} ({m.membership_role.capitalize()})")
        for m in org_members if m.user
    ]

    if form.validate_on_submit():
        try:
            scheduled_at = form.scheduled_at.data
            end_time = form.end_time.data
            # Attach UTC timezone if naive
            if scheduled_at and scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
            if end_time and end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)

            interview, warnings = schedule_interview(
                application_id=application.id,
                round_name=form.round_name.data,
                interview_type=form.interview_type.data,
                scheduled_at=scheduled_at,
                end_time=end_time,
                timezone_str=form.timezone.data,
                meeting_link=form.meeting_link.data,
                location=form.location.data,
                instructions=form.instructions.data,
                interviewer_ids=form.interviewer_ids.data,
                created_by_user_id=current_user.id
            )

            # Automatically advance application to 'interview' stage if not already
            if application.status in ("submitted", "under_review", "shortlisted"):
                try:
                    transition_application_stage(
                        application_id=application.id,
                        new_stage="interview",
                        changed_by_user=current_user,
                        reason=f"Interview '{interview.round_name}' scheduled"
                    )
                except Exception:
                    pass

            if warnings:
                for w in warnings:
                    flash(f"Scheduling Warning: {w}", "warning")
            flash(f"Interview '{interview.round_name}' scheduled successfully!", "success")
            return redirect(url_for("interviews.detail", interview_id=interview.id))

        except InterviewValidationError as e:
            flash(str(e), "danger")

    return render_template("interviews/schedule.html", form=form, application=application, job=job)


@interviews_bp.route("/<int:interview_id>", methods=["GET"])
@login_required
def detail(interview_id):
    """
    Detailed interview view with strict role authorization:
    - Candidate: sees time, round, format, instructions, meeting link, and candidate-facing summary.
    - Recruiter: sees all details, assigned team, actions, and internal interviewer feedback.
    - Assigned Interviewer: sees session details, candidate application, and feedback action.
    """
    interview = db.session.get(Interview, interview_id)
    if not interview:
        abort(404)

    application = interview.application
    is_candidate_owner = current_user.role == "candidate" and application.candidate_user_id == current_user.id
    is_recruiter = check_recruiter_interview_access(interview)
    is_assigned = (
        InterviewAssignment.query.filter_by(
            interview_id=interview.id,
            interviewer_user_id=current_user.id
        ).first() is not None
    )

    if not is_candidate_owner and not is_recruiter and not is_assigned:
        abort(403)

    # Filter feedback records according to role
    if is_candidate_owner:
        feedback_list = get_candidate_visible_feedback(interview.id)
    else:
        feedback_list = interview.feedback_records.all()

    # Pre-populate forms for recruiters
    cancel_form = InterviewCancelForm() if is_recruiter else None

    # Check if current user has already submitted feedback
    user_feedback = None
    if is_assigned or is_recruiter:
        user_feedback = InterviewFeedback.query.filter_by(
            interview_id=interview.id,
            interviewer_user_id=current_user.id
        ).first()

    return render_template(
        "interviews/detail.html",
        interview=interview,
        application=application,
        is_candidate_owner=is_candidate_owner,
        is_recruiter=is_recruiter,
        is_assigned=is_assigned,
        feedback_list=feedback_list,
        cancel_form=cancel_form,
        user_feedback=user_feedback
    )


@interviews_bp.route("/<int:interview_id>/reschedule", methods=["GET", "POST"])
@recruiter_required
def reschedule(interview_id):
    """Reschedules an interview with new timing or format."""
    interview = db.session.get(Interview, interview_id)
    if not interview:
        abort(404)

    if not check_recruiter_interview_access(interview):
        abort(403)

    form = InterviewRescheduleForm(obj=interview)
    job = interview.application.job

    # Populate interviewer choices
    org_members = OrganizationMembership.query.filter_by(
        organization_id=job.organization_id,
        is_active=True
    ).all()
    form.interviewer_ids.choices = [
        (m.user_id, f"{m.user.full_name} ({m.membership_role.capitalize()})")
        for m in org_members if m.user
    ]

    if request.method == "GET":
        form.interviewer_ids.data = [a.interviewer_user_id for a in interview.assignments]

    if form.validate_on_submit():
        try:
            scheduled_at = form.scheduled_at.data
            end_time = form.end_time.data
            if scheduled_at and scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
            if end_time and end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)

            _, warnings = reschedule_interview(
                interview_id=interview.id,
                scheduled_at=scheduled_at,
                end_time=end_time,
                timezone_str=form.timezone.data,
                round_name=form.round_name.data,
                interview_type=form.interview_type.data,
                meeting_link=form.meeting_link.data,
                location=form.location.data,
                instructions=form.instructions.data,
                interviewer_ids=form.interviewer_ids.data,
                updated_by_user_id=current_user.id
            )

            if warnings:
                for w in warnings:
                    flash(f"Scheduling Warning: {w}", "warning")
            flash("Interview rescheduled successfully and candidate notified.", "success")
            return redirect(url_for("interviews.detail", interview_id=interview.id))

        except InterviewValidationError as e:
            flash(str(e), "danger")

    return render_template("interviews/reschedule.html", form=form, interview=interview)


@interviews_bp.route("/<int:interview_id>/cancel", methods=["POST"])
@recruiter_required
def cancel(interview_id):
    """Cancels an interview with reason."""
    interview = db.session.get(Interview, interview_id)
    if not interview:
        abort(404)

    if not check_recruiter_interview_access(interview):
        abort(403)

    form = InterviewCancelForm()
    if form.validate_on_submit():
        try:
            cancel_interview(
                interview_id=interview.id,
                cancellation_reason=form.cancellation_reason.data,
                cancelled_by_user_id=current_user.id
            )
            flash("Interview cancelled and candidate notified.", "info")
        except InterviewValidationError as e:
            flash(str(e), "danger")
    else:
        flash("Please provide a valid cancellation reason.", "warning")

    return redirect(url_for("interviews.detail", interview_id=interview.id))


@interviews_bp.route("/<int:interview_id>/status", methods=["POST"])
@recruiter_required
def update_status(interview_id):
    """Updates interview status to 'completed' or 'no_show'."""
    interview = db.session.get(Interview, interview_id)
    if not interview:
        abort(404)

    if not check_recruiter_interview_access(interview):
        abort(403)

    new_status = request.form.get("status", "").strip().lower()
    if new_status not in ("completed", "no_show"):
        flash("Invalid status update.", "danger")
        return redirect(url_for("interviews.detail", interview_id=interview.id))

    try:
        update_interview_status(interview.id, new_status, updated_by_user_id=current_user.id)
        flash(f"Interview marked as '{new_status.replace('_', ' ').capitalize()}'.", "success")
    except InterviewValidationError as e:
        flash(str(e), "danger")

    return redirect(url_for("interviews.detail", interview_id=interview.id))


@interviews_bp.route("/<int:interview_id>/feedback", methods=["GET", "POST"])
@login_required
def feedback(interview_id):
    """
    Interviewer rubric feedback submission.
    Authorized for assigned interviewers, organization admins, or platform admins.
    Candidates are strictly forbidden (HTTP 403).
    """
    interview = db.session.get(Interview, interview_id)
    if not interview:
        abort(404)

    if current_user.role == "candidate":
        abort(403)

    job = interview.application.job
    is_assigned = (
        InterviewAssignment.query.filter_by(
            interview_id=interview.id,
            interviewer_user_id=current_user.id
        ).first() is not None
    )
    is_org_admin = (
        OrganizationMembership.query.filter_by(
            organization_id=job.organization_id,
            user_id=current_user.id,
            membership_role="admin",
            is_active=True
        ).first() is not None
        or current_user.role == "platform_admin"
    )

    if not is_assigned and not is_org_admin:
        abort(403)

    existing = InterviewFeedback.query.filter_by(
        interview_id=interview.id,
        interviewer_user_id=current_user.id
    ).first()

    form = InterviewFeedbackForm(obj=existing)

    if form.validate_on_submit():
        try:
            tech_r = int(form.technical_rating.data) if form.technical_rating.data else None
            prob_r = int(form.problem_solving_rating.data) if form.problem_solving_rating.data else None
            comm_r = int(form.communication_rating.data) if form.communication_rating.data else None
            role_r = int(form.role_relevant_rating.data) if form.role_relevant_rating.data else None

            submit_or_update_feedback(
                interview_id=interview.id,
                interviewer_user_id=current_user.id,
                technical_rating=tech_r,
                problem_solving_rating=prob_r,
                communication_rating=comm_r,
                role_relevant_rating=role_r,
                strengths=form.strengths.data,
                areas_for_improvement=form.areas_for_improvement.data,
                notes=form.notes.data,
                overall_recommendation=form.overall_recommendation.data,
                is_candidate_facing=form.is_candidate_facing.data,
                candidate_feedback=form.candidate_feedback.data,
                is_draft=form.is_draft.data
            )

            status_str = "draft saved" if form.is_draft.data else "submitted"
            flash(f"Interview evaluation {status_str} successfully.", "success")
            return redirect(url_for("interviews.detail", interview_id=interview.id))

        except FeedbackValidationError as e:
            flash(str(e), "danger")

    return render_template(
        "interviews/feedback.html",
        form=form,
        interview=interview,
        existing_feedback=existing
    )


@interviews_bp.route("/<int:interview_id>/feedback/<int:feedback_id>", methods=["GET"])
@login_required
def view_feedback(interview_id, feedback_id):
    """
    View complete interviewer evaluation.
    Only authorized for recruiters/reviewers in the organization or the authoring interviewer.
    Candidates receive HTTP 403 Forbidden.
    """
    if current_user.role == "candidate":
        abort(403)

    interview = db.session.get(Interview, interview_id)
    if not interview:
        abort(404)

    feedback_record = db.session.get(InterviewFeedback, feedback_id)
    if not feedback_record or feedback_record.interview_id != interview.id:
        abort(404)

    is_author = feedback_record.interviewer_user_id == current_user.id
    is_recruiter = check_recruiter_interview_access(interview)

    if not is_author and not is_recruiter:
        abort(403)

    return render_template(
        "interviews/view_feedback.html",
        interview=interview,
        feedback=feedback_record
    )
