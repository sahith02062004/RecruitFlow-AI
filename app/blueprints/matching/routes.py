"""
Matching Blueprint Routes for RecruitFlow AI (Phase 5).
Handles:
- Organization job matching overview
- Candidate ranking dashboard with transparent tie-breaking and filters
- Batch job matching evaluation
- Deep-dive match explanation and evidence audit view
- On-demand score recalculation
- Multi-tenant recruiter authorization checks
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from flask_login import current_user, login_required
from app.core.extensions import db
from app.core.security import recruiter_required
from app.models.models import Job, Application, MatchResult, OrganizationMembership
from app.services.matching_service import MatchingService
from app.services.ranking_service import RankingService

matching_bp = Blueprint("matching", __name__, url_prefix="/matching")


def check_recruiter_job_access(job: Job, user) -> bool:
    """Verifies user has permission to manage and view matching results for the job's organization."""
    if not user.is_authenticated:
        return False
    if user.role == "platform_admin":
        return True
    if user.role not in ("recruiter", "organization_admin"):
        return False

    membership = user.memberships.filter_by(organization_id=job.organization_id, is_active=True).first()
    return membership is not None


@matching_bp.route("/")
@login_required
@recruiter_required
def index():
    """
    Overview of active and published jobs eligible for AI candidate matching.
    Shows applicant volume and evaluation readiness.
    """
    if current_user.role == "platform_admin":
        jobs = Job.query.order_by(Job.created_at.desc()).all()
    else:
        memberships = current_user.memberships.filter_by(is_active=True).all()
        org_ids = [m.organization_id for m in memberships]
        if not org_ids:
            return render_template("matching/index.html", jobs=[])
        jobs = Job.query.filter(Job.organization_id.in_(org_ids)).order_by(Job.created_at.desc()).all()

    # Pre-calculate match metrics per job
    job_summaries = []
    for job in jobs:
        total_apps = job.applications.filter(Application.status != "withdrawn").count()
        scored_apps = (
            db.session.query(MatchResult)
            .filter(MatchResult.job_id == job.id, MatchResult.overall_score.isnot(None))
            .count()
        )
        highest_score_rec = (
            db.session.query(MatchResult)
            .filter(MatchResult.job_id == job.id, MatchResult.overall_score.isnot(None))
            .order_by(MatchResult.overall_score.desc())
            .first()
        )
        job_summaries.append({
            "job": job,
            "total_apps": total_apps,
            "scored_apps": scored_apps,
            "top_score": highest_score_rec.overall_score if highest_score_rec else None,
        })

    return render_template("matching/index.html", job_summaries=job_summaries)


@matching_bp.route("/jobs/<int:job_id>")
@login_required
@recruiter_required
def job_rankings(job_id):
    """
    Candidate ranking page for a specific job requisition.
    Displays deterministically ranked applicants, evidence coverage,
    matched vs missing skills, and tie-breaking indicators.
    """
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    if not check_recruiter_job_access(job, current_user):
        abort(403)

    status_filter = request.args.get("status", "all")
    search_query = request.args.get("q", "")
    page = request.args.get("page", 1, type=int)

    ranked_data = RankingService.get_ranked_candidates(
        job=job,
        status_filter=status_filter,
        search_query=search_query,
        page=page,
        per_page=15
    )

    return render_template("matching/job_rankings.html", **ranked_data)


@matching_bp.route("/jobs/<int:job_id>/run", methods=["POST"])
@login_required
@recruiter_required
def run_job_matching(job_id):
    """
    Batch evaluation action running deterministic matching across all active
    applicants for the selected job requisition.
    """
    job = db.session.get(Job, job_id)
    if not job:
        abort(404)

    if not check_recruiter_job_access(job, current_user):
        abort(403)

    result = MatchingService.evaluate_job_applications(job, force_recalculate=True)
    flash(
        f"Matching evaluation completed for {result['evaluated']} applicant(s). "
        f"{result['unavailable_evidence']} candidate(s) have limited/unavailable evidence.",
        "success"
    )
    return redirect(url_for("matching.job_rankings", job_id=job.id))


@matching_bp.route("/applications/<int:application_id>/explanation")
@login_required
@recruiter_required
def explanation(application_id):
    """
    Transparent breakdown of a candidate's match score against stated job requirements.
    Shows scoring weights snapshot, category scores, matched/missing skills,
    experience alignment, qualification proof, and evidence coverage.
    """
    application = db.session.get(Application, application_id)
    if not application:
        abort(404)

    if not check_recruiter_job_access(application.job, current_user):
        abort(403)

    # If not evaluated yet, compute on the fly
    match_result = application.match_result
    if not match_result:
        match_result = MatchingService.evaluate_application(application)

    # Check for input staleness
    is_stale = MatchingService.check_staleness(match_result)

    category_scores = match_result.get_category_scores()
    weights_snapshot = match_result.get_scoring_weights()
    missing_evidence = match_result.get_missing_evidence()

    return render_template(
        "matching/explanation.html",
        application=application,
        job=application.job,
        match_result=match_result,
        category_scores=category_scores,
        weights_snapshot=weights_snapshot,
        missing_evidence=missing_evidence,
        is_stale=is_stale,
    )


@matching_bp.route("/applications/<int:application_id>/recalculate", methods=["POST"])
@login_required
@recruiter_required
def recalculate(application_id):
    """On-demand recalculation of an individual candidate's match score."""
    application = db.session.get(Application, application_id)
    if not application:
        abort(404)

    if not check_recruiter_job_access(application.job, current_user):
        abort(403)

    MatchingService.evaluate_application(application)
    flash("Candidate match score recalculated using latest requirements and resume data.", "success")
    return redirect(url_for("matching.explanation", application_id=application.id))
