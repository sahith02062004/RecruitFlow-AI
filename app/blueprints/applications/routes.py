"""
Applications Blueprint Routes for RecruitFlow AI (Phase 3).
Handles:
- Candidate application submission to published, active jobs
- Candidate viewing their own applications
- Candidate withdrawing applications
- Recruiter viewing applications for their organization's jobs
- Recruiter reviewing candidate application details and updating statuses
- Organization isolation & cross-account security defenses
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from flask_login import current_user, login_required
from app.core.extensions import db
from app.core.security import candidate_required, recruiter_required
from app.models.models import Application, Job, Resume, Interview, utc_now
from app.blueprints.jobs.forms import ApplicationForm, ApplicationStatusUpdateForm

applications_bp = Blueprint("applications", __name__, url_prefix="/applications")


@applications_bp.route("/")
@login_required
def index():
    """
    Displays applications list:
    - If Candidate: Shows their own submitted applications.
    - If Recruiter: Shows applications submitted to their organization's jobs.
    """
    status_filter = request.args.get("status")

    if current_user.role == "candidate":
        query = Application.query.filter_by(candidate_user_id=current_user.id)
        if status_filter:
            query = query.filter_by(status=status_filter)
        applications = query.order_by(Application.applied_at.desc()).all()
        return render_template("applications/candidate_list.html", applications=applications, current_status=status_filter)

    elif current_user.role in ("recruiter", "organization_admin", "platform_admin"):
        # Recruiter gets applications for their organization
        if current_user.role == "platform_admin":
            query = Application.query
        else:
            membership = current_user.memberships.filter_by(is_active=True).first()
            if not membership:
                return render_template("applications/index.html", applications=[], current_status=status_filter)
            query = Application.query.join(Job).filter(Job.organization_id == membership.organization_id)

        if status_filter:
            query = query.filter(Application.status == status_filter)

        job_id = request.args.get("job_id", type=int)
        if job_id:
            query = query.filter(Application.job_id == job_id)

        applications = query.order_by(Application.applied_at.desc()).all()
        return render_template("applications/index.html", applications=applications, current_status=status_filter, job_id=job_id)

    abort(403)


@applications_bp.route("/apply/<int:job_id>", methods=["GET", "POST"])
@candidate_required
def apply(job_id):
    """Candidate submits application to a published, open job."""
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    # Validate job is open and accepting applications
    if not job.is_open:
        flash("This job opening is closed, draft, or no longer accepting applications.", "warning")
        return redirect(url_for("jobs.detail", job_id=job.id))

    # Check for duplicate submission
    existing = Application.query.filter_by(
        job_id=job.id,
        candidate_user_id=current_user.id
    ).first()

    if existing:
        flash("You have already submitted an application for this position.", "info")
        return redirect(url_for("applications.detail", application_id=existing.id))

    form = ApplicationForm()
    candidate_profile = current_user.candidate_profile
    res_filter = [Resume.candidate_user_id == current_user.id]
    if candidate_profile:
        res_filter.append(Resume.candidate_id == candidate_profile.id)
    resumes = Resume.query.filter(db.or_(*res_filter)).order_by(Resume.created_at.desc()).all()

    if form.validate_on_submit():
        resume_id = request.form.get("resume_id", type=int)
        if resume_id and not Resume.query.filter(Resume.id == resume_id, db.or_(*res_filter)).first():
            resume_id = None

        application = Application(
            job_id=job.id,
            candidate_user_id=current_user.id,
            candidate_id=candidate_profile.id if candidate_profile else None,
            resume_id=resume_id,
            cover_letter=form.cover_letter.data.strip() if form.cover_letter.data else None,
            status="submitted",
            match_score=0.0  # Initial unscored state before AI processing
        )
        db.session.add(application)
        db.session.commit()

        flash(f"Application submitted successfully for '{job.title}'!", "success")
        return redirect(url_for("applications.detail", application_id=application.id))

    return render_template("applications/apply.html", form=form, job=job, resumes=resumes)


@applications_bp.route("/pipeline")
@recruiter_required
def pipeline():
    """
    Interactive Hiring Pipeline Kanban Board.
    Visualizes candidate flow through stages:
    Submitted -> Under Review -> Shortlisted -> Interview Scheduled -> Interview Completed -> Offer -> Hired / Rejected.
    """
    job_id = request.args.get("job_id", type=int)

    # Scoped to recruiter's organization
    if current_user.role == "platform_admin":
        jobs = Job.query.all()
    else:
        membership = current_user.memberships.filter_by(is_active=True).first()
        if not membership:
            return render_template("applications/pipeline.html", jobs=[], current_job=None, board_data={})
        jobs = Job.query.filter_by(organization_id=membership.organization_id).all()

    current_job = None
    if job_id:
        current_job = db.session.get(Job, job_id)
    elif jobs:
        current_job = jobs[0]

    from app.services.hiring_pipeline_service import get_pipeline_stages_for_job
    board_data = get_pipeline_stages_for_job(current_job.id) if current_job else {}

    return render_template(
        "applications/pipeline.html",
        jobs=jobs,
        current_job=current_job,
        board_data=board_data
    )


@applications_bp.route("/<int:application_id>", methods=["GET", "POST"])
@login_required
def detail(application_id):
    """
    View application details.
    - Candidate: can only view their own application.
    - Recruiter: can view applications belonging to their organization, update status, and manage interviews.
    """
    application = db.session.get(Application, application_id)
    if not application:
        abort(404)

    is_owner_candidate = current_user.role == "candidate" and application.candidate_user_id == current_user.id
    is_authorized_recruiter = False

    if current_user.role == "platform_admin":
        is_authorized_recruiter = True
    elif current_user.role in ("recruiter", "organization_admin"):
        membership = current_user.memberships.filter_by(organization_id=application.job.organization_id, is_active=True).first()
        if membership:
            is_authorized_recruiter = True

    if not is_owner_candidate and not is_authorized_recruiter:
        abort(403)

    from app.services.hiring_pipeline_service import transition_application_stage, StageTransitionError

    status_form = None
    if is_authorized_recruiter:
        status_form = ApplicationStatusUpdateForm(obj=application)
        if status_form.validate_on_submit():
            new_status = status_form.status.data
            notes = status_form.notes.data.strip() if status_form.notes.data else None
            try:
                if application.status != new_status:
                    transition_application_stage(
                        application_id=application.id,
                        new_stage=new_status,
                        changed_by_user=current_user,
                        reason=notes or f"Updated via application review"
                    )
                if notes:
                    application.notes = notes
                if status_form.rejection_reason_code.data:
                    application.rejection_reason_code = status_form.rejection_reason_code.data
                    application.rejection_reason_text = status_form.rejection_reason_text.data
                    application.rejection_feedback_published = bool(status_form.rejection_feedback_published.data)
                db.session.commit()
                flash(f"Application status updated to '{new_status.replace('_', ' ').capitalize()}'.", "success")
                return redirect(url_for("applications.detail", application_id=application.id))
            except StageTransitionError as e:
                flash(str(e), "danger")

    # Fetch stage history and interviews
    stage_history = application.stage_history.all()
    interviews = application.interviews.order_by(Interview.scheduled_at.desc()).all()

    return render_template(
        "applications/detail.html",
        application=application,
        is_owner_candidate=is_owner_candidate,
        is_authorized_recruiter=is_authorized_recruiter,
        status_form=status_form,
        stage_history=stage_history,
        interviews=interviews
    )


@applications_bp.route("/<int:application_id>/stage", methods=["POST"])
@recruiter_required
def update_stage(application_id):
    """
    Direct stage transition endpoint for pipeline board and quick actions.
    """
    from app.services.hiring_pipeline_service import transition_application_stage, StageTransitionError

    new_stage = request.form.get("new_stage", "").strip()
    reason = request.form.get("reason", "").strip() or None

    try:
        app_obj, _ = transition_application_stage(
            application_id=application_id,
            new_stage=new_stage,
            changed_by_user=current_user,
            reason=reason
        )
        flash(f"Application progressed to '{new_stage.replace('_', ' ').capitalize()}'.", "success")
    except StageTransitionError as e:
        flash(str(e), "danger")

    redirect_to = request.form.get("redirect_to")
    if redirect_to and redirect_to.startswith("/"):
        return redirect(redirect_to)
    return redirect(url_for("applications.detail", application_id=application_id))


@applications_bp.route("/<int:application_id>/withdraw", methods=["POST"])
@candidate_required
def withdraw(application_id):
    """Candidate withdraws their submitted application."""
    application = db.session.get(Application, application_id)
    if not application:
        abort(404)

    # Must be own application
    if application.candidate_user_id != current_user.id:
        abort(403)

    if application.status == "withdrawn":
        flash("Application is already withdrawn.", "info")
    else:
        from app.services.hiring_pipeline_service import transition_application_stage, StageTransitionError
        try:
            transition_application_stage(
                application_id=application.id,
                new_stage="withdrawn",
                changed_by_user=current_user,
                reason="Withdrawn by candidate"
            )
            flash("Your application has been withdrawn.", "info")
        except StageTransitionError as e:
            flash(str(e), "danger")

    return redirect(url_for("applications.detail", application_id=application.id))

