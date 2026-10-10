"""
Candidate Blueprint Routes for RecruitFlow AI.
Includes:
- Candidate personal dashboard
- View and update own candidate profile
- RBAC protected candidate routes
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, abort
from flask_login import current_user
from app.core.extensions import db
from app.core.security import candidate_required
from app.models.models import CandidateProfile, Application, Resume, ResumeAnalysis, Job
from app.services.ats_analyzer_service import ATSAnalyzerService
from app.blueprints.auth.forms import CandidateProfileForm

candidates_bp = Blueprint("candidates", __name__, url_prefix="/candidates")


@candidates_bp.route("/dashboard")
@candidate_required
def dashboard():
    """Candidate personal dashboard with real application stats, ATS scores, and profile completion."""
    profile = current_user.candidate_profile
    applications = profile.applications.order_by(Application.applied_at.desc()).all() if profile else []
    resumes = profile.resumes.order_by(Resume.created_at.desc()).all() if profile else []

    # Calculate profile completion percentage
    completion_items = [
        bool(profile.headline if profile else False),
        bool(profile.professional_summary if profile else False),
        bool(profile.location if profile else False),
        bool(profile.skills if profile else False),
        bool((profile.linkedin_url or profile.github_url or profile.portfolio_url) if profile else False),
        bool(resumes)
    ]
    completion_pct = int((sum(completion_items) / len(completion_items)) * 100) if profile else 0

    # Fetch latest ATS analysis for candidate's primary resume
    primary_resume = resumes[0] if resumes else None
    latest_analysis = None
    if primary_resume:
        latest_analysis = primary_resume.analyses.order_by(ResumeAnalysis.created_at.desc()).first()
        if not latest_analysis and primary_resume.raw_text:
            latest_analysis = ATSAnalyzerService.run_ats_analysis(primary_resume, candidate_user=current_user)

    available_jobs = Job.query.filter(Job.status.in_(["published", "active"])).order_by(Job.created_at.desc()).limit(5).all()

    return render_template(
        "candidates/dashboard.html",
        profile=profile,
        applications=applications,
        resumes=resumes,
        completion_pct=completion_pct,
        primary_resume=primary_resume,
        latest_analysis=latest_analysis,
        available_jobs=available_jobs
    )


@candidates_bp.route("/profile", methods=["GET", "POST"])
@candidate_required
def profile():
    """View and edit own candidate profile."""
    profile_record = current_user.candidate_profile
    if not profile_record:
        profile_record = CandidateProfile(user_id=current_user.id)
        db.session.add(profile_record)
        db.session.commit()

    form = CandidateProfileForm(obj=profile_record)

    if form.validate_on_submit():
        form.populate_obj(profile_record)
        db.session.commit()
        flash("Your profile has been updated successfully.", "success")
        return redirect(url_for("candidates.profile"))

    return render_template("candidates/profile.html", form=form, profile=profile_record)


@candidates_bp.route("/")
def list_candidates():
    """Public/Recruiter candidate directory."""
    candidates = CandidateProfile.query.all()
    return render_template("candidates/index.html", candidates=candidates)


@candidates_bp.route("/<int:candidate_id>")
def view_candidate(candidate_id):
    """View candidate profile by ID."""
    candidate = db.session.get(CandidateProfile, candidate_id)
    if not candidate:
        abort(404)
    return render_template("candidates/detail.html", candidate=candidate)
