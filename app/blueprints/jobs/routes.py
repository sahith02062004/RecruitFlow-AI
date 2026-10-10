"""
Jobs Blueprint Routes for RecruitFlow AI (Phase 3).
Handles:
- Public/Candidate job search, filtering, and detail views
- Recruiter job creation, editing, publishing, closing, and archiving
- Multi-tenant organization isolation
"""
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user, login_required
from sqlalchemy import or_
from app.core.extensions import db
from app.core.security import recruiter_required
from app.models.models import Job, Application, Organization, OrganizationMembership, utc_now
from app.blueprints.jobs.forms import JobForm

jobs_bp = Blueprint("jobs", __name__, url_prefix="/jobs")


@jobs_bp.route("/")
def index():
    """
    Job catalog.
    - For candidates/public: Shows only published/active open jobs with search & filters.
    - For recruiters: If viewing organization filter, or toggling statuses.
    """
    search_query = request.args.get("q", "").strip()
    department = request.args.get("department", "").strip()
    workplace_type = request.args.get("workplace", "").strip()
    employment_type = request.args.get("employment", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = Job.query

    # Public and candidates only see published/active jobs
    is_recruiter = current_user.is_authenticated and current_user.role in ("recruiter", "organization_admin", "platform_admin")

    if not is_recruiter:
        query = query.filter(Job.status.in_(["published", "active"]))
    else:
        if status_filter:
            query = query.filter(Job.status == status_filter)

    # Search by keyword across title, required_skills, department, location
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                Job.title.ilike(search_pattern),
                Job.required_skills.ilike(search_pattern),
                Job.department.ilike(search_pattern),
                Job.location.ilike(search_pattern)
            )
        )

    if department:
        query = query.filter(Job.department.ilike(f"%{department}%"))

    if workplace_type:
        query = query.filter(Job.workplace_type == workplace_type)

    if employment_type:
        query = query.filter(Job.employment_type == employment_type)

    jobs = query.order_by(Job.created_at.desc()).all()

    # Collect available departments for filter pills
    all_departments = db.session.query(Job.department).filter(Job.department.isnot(None)).distinct().all()
    departments_list = [d[0] for d in all_departments if d[0]]

    return render_template(
        "jobs/index.html",
        jobs=jobs,
        search_query=search_query,
        selected_department=department,
        selected_workplace=workplace_type,
        selected_employment=employment_type,
        status_filter=status_filter,
        departments_list=departments_list,
        is_recruiter=is_recruiter
    )


@jobs_bp.route("/<int:job_id>")
def detail(job_id):
    """View job details and application options."""
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    is_recruiter = current_user.is_authenticated and current_user.role in ("recruiter", "organization_admin", "platform_admin")
    is_author_or_org_member = False
    existing_application = None

    if current_user.is_authenticated:
        if is_recruiter:
            if current_user.role == "platform_admin":
                is_author_or_org_member = True
            else:
                membership = current_user.memberships.filter_by(organization_id=job.organization_id, is_active=True).first()
                if membership:
                    is_author_or_org_member = True

        if current_user.role == "candidate":
            existing_application = Application.query.filter_by(
                job_id=job.id,
                candidate_user_id=current_user.id
            ).first()

    # If job is draft or archived, only authorized recruiters or platform admins may view it
    if job.status not in ("published", "active") and not is_author_or_org_member:
        abort(404)

    return render_template(
        "jobs/detail.html",
        job=job,
        is_author_or_org_member=is_author_or_org_member,
        existing_application=existing_application
    )


@jobs_bp.route("/new", methods=["GET", "POST"])
@recruiter_required
def create():
    """Create a new job opening for recruiter's authorized organization."""
    # Identify recruiter's primary active organization
    membership = current_user.memberships.filter_by(is_active=True).first()
    if not membership:
        flash("You do not belong to an active organization. Please contact an administrator.", "danger")
        return redirect(url_for("recruiters.dashboard"))

    organization = membership.organization
    if not organization.is_active:
        flash("Your organization is currently inactive.", "danger")
        return redirect(url_for("recruiters.dashboard"))

    form = JobForm()
    if form.validate_on_submit():
        # Build formatted salary range if min/max provided
        salary_range_str = None
        if form.salary_min.data or form.salary_max.data:
            c = form.salary_currency.data
            if form.salary_min.data and form.salary_max.data:
                salary_range_str = f"{c} {form.salary_min.data:,.0f} - {form.salary_max.data:,.0f}"
            elif form.salary_min.data:
                salary_range_str = f"From {c} {form.salary_min.data:,.0f}"
            else:
                salary_range_str = f"Up to {c} {form.salary_max.data:,.0f}"

        published_time = utc_now() if form.status.data == "published" else None

        job = Job(
            organization_id=organization.id,
            created_by_user_id=current_user.id,
            recruiter_id=current_user.recruiter_profile.id if current_user.recruiter_profile else None,
            title=form.title.data.strip(),
            department=form.department.data.strip() if form.department.data else None,
            location=form.location.data.strip() if form.location.data else None,
            workplace_type=form.workplace_type.data,
            employment_type=form.employment_type.data,
            status=form.status.data,
            description=form.description.data.strip(),
            responsibilities=form.responsibilities.data.strip() if form.responsibilities.data else None,
            required_skills=form.required_skills.data.strip(),
            preferred_skills=form.preferred_skills.data.strip() if form.preferred_skills.data else None,
            minimum_experience_years=form.minimum_experience_years.data or 0.0,
            maximum_experience_years=form.maximum_experience_years.data,
            minimum_qualification=form.minimum_qualification.data.strip() if form.minimum_qualification.data else None,
            salary_min=form.salary_min.data,
            salary_max=form.salary_max.data,
            salary_currency=form.salary_currency.data,
            salary_range=salary_range_str,
            application_deadline=form.application_deadline.data,
            published_at=published_time
        )
        db.session.add(job)
        db.session.commit()

        flash(f"Job requisition '{job.title}' created successfully!", "success")
        return redirect(url_for("jobs.detail", job_id=job.id))

    return render_template("jobs/create.html", form=form, organization=organization)


@jobs_bp.route("/<int:job_id>/edit", methods=["GET", "POST"])
@recruiter_required
def edit(job_id):
    """Edit an existing job opening within authorized organization."""
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    # Enforce organization isolation
    if current_user.role != "platform_admin":
        membership = current_user.memberships.filter_by(organization_id=job.organization_id, is_active=True).first()
        if not membership:
            abort(403)

    form = JobForm(obj=job)

    if form.validate_on_submit():
        form.populate_obj(job)
        job.title = form.title.data.strip()
        job.description = form.description.data.strip()
        job.required_skills = form.required_skills.data.strip()

        # Update formatted salary cache
        if form.salary_min.data or form.salary_max.data:
            c = form.salary_currency.data
            if form.salary_min.data and form.salary_max.data:
                job.salary_range = f"{c} {form.salary_min.data:,.0f} - {form.salary_max.data:,.0f}"
            elif form.salary_min.data:
                job.salary_range = f"From {c} {form.salary_min.data:,.0f}"
            else:
                job.salary_range = f"Up to {c} {form.salary_max.data:,.0f}"
        else:
            job.salary_range = None

        if job.status in ("published", "active") and not job.published_at:
            job.published_at = utc_now()
        elif job.status == "closed" and not job.closed_at:
            job.closed_at = utc_now()

        db.session.commit()
        flash("Job requisition updated successfully.", "success")
        return redirect(url_for("jobs.detail", job_id=job.id))

    return render_template("jobs/edit.html", form=form, job=job)


@jobs_bp.route("/<int:job_id>/status/<new_status>", methods=["POST"])
@recruiter_required
def set_status(job_id, new_status):
    """Fast status toggle: publish, close, reopen, archive."""
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    if current_user.role != "platform_admin":
        membership = current_user.memberships.filter_by(organization_id=job.organization_id, is_active=True).first()
        if not membership:
            abort(403)

    if new_status not in Job.VALID_STATUSES:
        abort(400)

    job.status = new_status
    if new_status in ("published", "active") and not job.published_at:
        job.published_at = utc_now()
    elif new_status == "closed":
        job.closed_at = utc_now()

    db.session.commit()
    flash(f"Job '{job.title}' status changed to {new_status.capitalize()}.", "info")
    return redirect(url_for("jobs.detail", job_id=job.id))
