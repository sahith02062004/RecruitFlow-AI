"""
Recruitment Reports & Analytics Blueprint for RecruitFlow AI (Phase 7).
Handles:
- Organization-scoped recruitment KPI overview
- Hiring funnel pass-through metrics & conversion rates
- Per-job requisition breakdowns
- Date and status filtering
- Secure, formula-injection-protected CSV export
"""
from datetime import datetime
from flask import Blueprint, render_template, request, Response, abort, flash, redirect, url_for
from flask_login import current_user
from app.core.security import recruiter_required
from app.models.models import Job, Organization, OrganizationMembership
from app.services.recruitment_analytics_service import RecruitmentAnalyticsService

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def get_user_organization(user):
    """Retrieves active organization for current recruiter or admin."""
    if user.role == "platform_admin":
        # Admin can view the first organization or one specified
        org = Organization.query.first()
        return org
    membership = user.memberships.filter_by(is_active=True).first()
    return membership.organization if membership else None


@reports_bp.route("/")
@recruiter_required
def index():
    """Recruitment Analytics & Reporting dashboard."""
    org = get_user_organization(current_user)
    if not org:
        flash("You are not currently linked to an active organization context.", "warning")
        return render_template(
            "reports/index.html",
            org=None,
            analytics=None,
            job_breakdown=[],
            jobs=[]
        )

    # Filter parameters
    job_id = request.args.get("job_id", type=int)
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")

    start_date = None
    end_date = None
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        except ValueError:
            pass
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        except ValueError:
            pass

    analytics = RecruitmentAnalyticsService.get_organization_overview(
        organization_id=org.id,
        job_id=job_id,
        start_date=start_date,
        end_date=end_date
    )

    job_breakdown = RecruitmentAnalyticsService.get_job_level_analytics(org.id)
    jobs = Job.query.filter_by(organization_id=org.id).order_by(Job.title.asc()).all()

    return render_template(
        "reports/index.html",
        org=org,
        analytics=analytics,
        job_breakdown=job_breakdown,
        jobs=jobs,
        selected_job_id=job_id,
        start_date=start_date_str,
        end_date=end_date_str
    )


@reports_bp.route("/export/applications.csv")
@recruiter_required
def export_applications_csv():
    """
    Exports organization-isolated, formula-injection-safe CSV of applications.
    Protected against unauthorized cross-tenant export and formula injection.
    """
    org = get_user_organization(current_user)
    if not org:
        abort(403)

    job_id = request.args.get("job_id", type=int)
    status = request.args.get("status")

    csv_data = RecruitmentAnalyticsService.generate_applications_csv(
        organization_id=org.id,
        job_id=job_id,
        status=status
    )

    filename = f"recruitflow_applications_{org.slug or 'export'}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv; charset=utf-8"
        }
    )
