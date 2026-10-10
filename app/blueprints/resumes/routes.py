"""
Resumes Blueprint Routes for RecruitFlow AI (Phase 4).
Handles:
- Viewing uploaded resumes (role-filtered)
- Secure resume file uploads (PDF & DOCX) with magic-byte validation
- Extraction detail view with quality warnings and skills badges
- Candidate corrections and profile synchronization
- Secure, authorized file downloads
- Resume deletion
"""
from pathlib import Path
from flask import Blueprint, render_template, request, flash, redirect, url_for, abort, send_file
from flask_login import current_user, login_required
from app.core.extensions import db
from app.models.models import Resume, Application, Job, OrganizationMembership, ResumeAnalysis
from app.services.resume_storage_service import ResumeStorageService, ResumeStorageError
from app.services.resume_processing_service import ResumeProcessingService
from app.services.ats_analyzer_service import ATSAnalyzerService
from app.services.resume_improvement_service import ResumeImprovementService
from app.services.shortlisting_gap_service import ShortlistingGapService
from app.blueprints.resumes.forms import ResumeUploadForm, ResumeCorrectionForm

resumes_bp = Blueprint("resumes", __name__, url_prefix="/resumes")


def get_recruiter_organization_ids(user):
    """Returns list of active organization IDs associated with recruiter."""
    memberships = user.memberships.filter_by(is_active=True).all()
    return [m.organization_id for m in memberships]


def can_access_resume(resume: Resume, user) -> bool:
    """
    Checks if a user has permission to view or download a resume:
    - Platform admin: Full access.
    - Owner candidate: Has access if resume belongs to user.
    - Recruiter: Has access if resume is linked to an application for a job in recruiter's organization,
      or was uploaded by the recruiter.
    """
    if not user.is_authenticated:
        return False

    if user.role == "platform_admin":
        return True

    if resume.candidate_user_id == user.id:
        return True

    if user.role in ("recruiter", "organization_admin"):
        org_ids = get_recruiter_organization_ids(user)
        if not org_ids:
            return False

        # Check if an application with this resume belongs to an organization job
        has_app = Application.query.join(Job).filter(
            Job.organization_id.in_(org_ids),
            db.or_(
                Application.resume_id == resume.id,
                Application.candidate_user_id == resume.candidate_user_id
            )
        ).first()
        if has_app:
            return True

    return False


@resumes_bp.route("/")
@login_required
def index():
    """
    List resumes:
    - Candidates see their own uploaded resumes.
    - Recruiters see resumes submitted to their organization's job openings.
    - Platform admins see all resumes.
    """
    if current_user.role == "candidate":
        resumes = Resume.query.filter_by(candidate_user_id=current_user.id).order_by(Resume.created_at.desc()).all()
    elif current_user.role == "platform_admin":
        resumes = Resume.query.order_by(Resume.created_at.desc()).all()
    elif current_user.role in ("recruiter", "organization_admin"):
        org_ids = get_recruiter_organization_ids(current_user)
        if org_ids:
            # Query resumes linked via applications to recruiter's jobs, or uploaded by recruiter
            resumes = Resume.query.join(Application, Application.resume_id == Resume.id).join(Job, Application.job_id == Job.id).filter(
                Job.organization_id.in_(org_ids)
            ).order_by(Resume.created_at.desc()).all()
            
            # If empty, also check for any resume uploaded by this recruiter directly
            if not resumes:
                resumes = Resume.query.filter_by(candidate_user_id=current_user.id).order_by(Resume.created_at.desc()).all()
        else:
            resumes = []
    else:
        resumes = []

    return render_template("resumes/index.html", resumes=resumes)


@resumes_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """
    Secure resume upload endpoint.
    Processes PDF and DOCX files, validates headers, runs deterministic extraction,
    and enriches the candidate profile.
    """
    form = ResumeUploadForm()

    if form.validate_on_submit():
        file_storage = form.resume_file.data
        sync_profile = form.sync_profile.data

        result = ResumeProcessingService.process_upload(
            file_storage=file_storage,
            user=current_user,
            sync_profile=sync_profile
        )

        if not result["success"]:
            flash(f"Upload failed: {result['error']}", "danger")
            return render_template("resumes/upload.html", form=form)

        resume = result["resume"]
        flash(f"Resume '{resume.original_filename}' uploaded and parsed successfully!", "success")
        return redirect(url_for("resumes.detail", resume_id=resume.id))

    return render_template("resumes/upload.html", form=form)


@resumes_bp.route("/<int:resume_id>")
@login_required
def detail(resume_id):
    """
    Displays parsed resume details, structured sections, skills tags,
    quality diagnostics, and candidate correction form.
    """
    resume = db.session.get(Resume, resume_id)
    if not resume:
        abort(404)

    if not can_access_resume(resume, current_user):
        abort(403)

    is_owner = (resume.candidate_user_id == current_user.id)
    extracted = resume.get_extracted_data()
    correction_form = ResumeCorrectionForm()

    # Pre-populate correction form for owner candidate
    if is_owner:
        correction_form.name.data = extracted.get("name") or (resume.candidate_user.full_name if resume.candidate_user else "")
        correction_form.email.data = extracted.get("email") or (resume.candidate_user.email if resume.candidate_user else "")
        correction_form.phone.data = extracted.get("phone", "")
        skills_list = extracted.get("skills") or resume.skills_list
        correction_form.skills.data = ", ".join(skills_list) if isinstance(skills_list, list) else str(skills_list)
        correction_form.total_experience_years.data = extracted.get("total_experience_years") or resume.parsed_experience_years or 0.0
        links = extracted.get("links", {})
        correction_form.linkedin_url.data = links.get("linkedin", "")
        correction_form.github_url.data = links.get("github", "")
        correction_form.portfolio_url.data = links.get("portfolio", "")
        correction_form.summary.data = extracted.get("summary", "")

    return render_template(
        "resumes/detail.html",
        resume=resume,
        extracted=extracted,
        is_owner=is_owner,
        correction_form=correction_form
    )


@resumes_bp.route("/<int:resume_id>/correct", methods=["POST"])
@login_required
def correct(resume_id):
    """
    Processes candidate corrections to parsed skills, experience, and contact info.
    """
    resume = db.session.get(Resume, resume_id)
    if not resume:
        abort(404)

    # Only owner candidate or platform admin can correct
    if resume.candidate_user_id != current_user.id and current_user.role != "platform_admin":
        abort(403)

    form = ResumeCorrectionForm()
    if form.validate_on_submit():
        raw_skills = form.skills.data or ""
        skills_list = [s.strip() for s in raw_skills.split(",") if s.strip()]

        links = {}
        if form.linkedin_url.data:
            links["linkedin"] = form.linkedin_url.data.strip()
        if form.github_url.data:
            links["github"] = form.github_url.data.strip()
        if form.portfolio_url.data:
            links["portfolio"] = form.portfolio_url.data.strip()

        updated_data = {
            "name": form.name.data.strip() if form.name.data else "",
            "email": form.email.data.strip() if form.email.data else "",
            "phone": form.phone.data.strip() if form.phone.data else "",
            "skills": skills_list,
            "skills_count": len(skills_list),
            "total_experience_years": form.total_experience_years.data or 0.0,
            "links": links,
            "summary": form.summary.data.strip() if form.summary.data else "",
        }

        ResumeProcessingService.update_resume_extraction(resume, updated_data)

        # Profile sync
        if form.sync_profile.data and current_user.candidate_profile:
            ResumeProcessingService.sync_extracted_data_to_profile(current_user.candidate_profile, updated_data)

        flash("Resume details updated successfully!", "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field.capitalize()}: {error}", "danger")

    return redirect(url_for("resumes.detail", resume_id=resume.id))


@resumes_bp.route("/<int:resume_id>/download")
@login_required
def download(resume_id):
    """
    Secure file download endpoint.
    Enforces authorization check and streams the original document safely.
    """
    resume = db.session.get(Resume, resume_id)
    if not resume:
        abort(404)

    if not can_access_resume(resume, current_user):
        abort(403)

    try:
        resolved_path = ResumeStorageService.get_absolute_path(resume.filename)
    except ResumeStorageError:
        flash("Resume file could not be found on storage disk.", "warning")
        return redirect(url_for("resumes.detail", resume_id=resume.id))

    return send_file(
        str(resolved_path),
        as_attachment=True,
        download_name=resume.original_filename,
        mimetype=resume.mime_type or "application/octet-stream"
    )


@resumes_bp.route("/<int:resume_id>/delete", methods=["POST"])
@login_required
def delete(resume_id):
    """
    Deletes resume from disk and database.
    Only permitted for the owning candidate or platform admin.
    """
    resume = db.session.get(Resume, resume_id)
    if not resume:
        abort(404)

    if resume.candidate_user_id != current_user.id and current_user.role != "platform_admin":
        abort(403)

    # Delete physical file
    ResumeStorageService.delete_file(resume.filename)

    # Delete database record
    db.session.delete(resume)
    db.session.commit()

    flash("Resume document deleted successfully.", "info")
    return redirect(url_for("resumes.index"))


# =========================================================================
# Phase 7: ATS Resume Analyzer, Comparison & Improvement Assistant Routes
# =========================================================================

@resumes_bp.route("/<int:resume_id>/analyze", methods=["GET", "POST"])
@login_required
def analyze(resume_id):
    """
    ATS Resume Analyzer view.
    Calculates and displays separate Resume Quality (0-100) and Job Match (0-100) scores.
    """
    resume = db.session.get(Resume, resume_id)
    if not resume:
        abort(404)

    if not can_access_resume(resume, current_user):
        abort(403)

    job_id = request.args.get("job_id", type=int) or request.form.get("job_id", type=int)
    job = db.session.get(Job, job_id) if job_id else None

    force_refresh = (request.method == "POST")
    analysis = ATSAnalyzerService.run_ats_analysis(
        resume=resume,
        job=job,
        candidate_user=current_user,
        force_refresh=force_refresh
    )

    # Available jobs for job-specific match dropdown (if candidate)
    available_jobs = Job.query.filter(Job.status.in_(["published", "active"])).order_by(Job.created_at.desc()).all()

    # Detailed match breakdown if job is selected
    job_match_data = None
    if job:
        job_match_data = ATSAnalyzerService.evaluate_job_match(
            resume=resume,
            job=job,
            candidate_profile=current_user.candidate_profile if hasattr(current_user, "candidate_profile") else None
        )

    return render_template(
        "resumes/ats_analysis.html",
        resume=resume,
        analysis=analysis,
        selected_job=job,
        available_jobs=available_jobs,
        job_match_data=job_match_data
    )


@resumes_bp.route("/<int:resume_id>/compare", methods=["GET", "POST"])
@login_required
def compare(resume_id):
    """
    Job Description & Resume Comparison interface.
    Provides side-by-side evaluation of skills, experience, qualifications, and gaps.
    """
    resume = db.session.get(Resume, resume_id)
    if not resume:
        abort(404)

    if not can_access_resume(resume, current_user):
        abort(403)

    job_id = request.args.get("job_id", type=int) or request.form.get("job_id", type=int)
    job = db.session.get(Job, job_id) if job_id else None

    # Available active jobs for comparison
    available_jobs = Job.query.filter(Job.status.in_(["published", "active"])).order_by(Job.title.asc()).all()

    comparison_data = None
    analysis = None
    if job:
        analysis = ATSAnalyzerService.run_ats_analysis(resume=resume, job=job, candidate_user=current_user)
        comparison_data = ATSAnalyzerService.evaluate_job_match(
            resume=resume,
            job=job,
            candidate_profile=current_user.candidate_profile if hasattr(current_user, "candidate_profile") else None
        )

    return render_template(
        "resumes/compare.html",
        resume=resume,
        selected_job=job,
        available_jobs=available_jobs,
        comparison_data=comparison_data,
        analysis=analysis
    )


@resumes_bp.route("/<int:resume_id>/improvements")
@login_required
def improvements(resume_id):
    """
    Resume Error Correction and Improvement Assistant.
    Provides prioritized checklist (High, Medium, Low) and truthful writing suggestions.
    """
    resume = db.session.get(Resume, resume_id)
    if not resume:
        abort(404)

    if not can_access_resume(resume, current_user):
        abort(403)

    job_id = request.args.get("job_id", type=int)
    job = db.session.get(Job, job_id) if job_id else None

    analysis = ATSAnalyzerService.run_ats_analysis(resume=resume, job=job, candidate_user=current_user)
    checklist = ResumeImprovementService.get_prioritized_checklist(analysis)
    writing_suggestions = ResumeImprovementService.generate_truthful_writing_suggestions(resume, job)

    return render_template(
        "resumes/improvements.html",
        resume=resume,
        analysis=analysis,
        selected_job=job,
        checklist=checklist,
        writing_suggestions=writing_suggestions
    )


@resumes_bp.route("/<int:resume_id>/checklist/toggle", methods=["POST"])
@login_required
def toggle_checklist(resume_id):
    """Toggles completion state of a recommendation checklist item."""
    resume = db.session.get(Resume, resume_id)
    if not resume:
        abort(404)

    # Only owner candidate or platform admin can modify checklist
    if resume.candidate_user_id != current_user.id and current_user.role != "platform_admin":
        abort(403)

    item_id = request.form.get("item_id")
    if not item_id:
        flash("Invalid checklist item specified.", "warning")
        return redirect(url_for("resumes.improvements", resume_id=resume.id))

    analysis = ResumeAnalysis.query.filter_by(resume_id=resume.id).first()
    if not analysis:
        analysis = ATSAnalyzerService.run_ats_analysis(resume=resume, candidate_user=current_user)

    is_now_completed = ResumeImprovementService.toggle_checklist_item(analysis, item_id)
    status_label = "completed" if is_now_completed else "marked pending"
    flash(f"Checklist item {status_label}.", "success")

    return redirect(url_for("resumes.improvements", resume_id=resume.id))


@resumes_bp.route("/<int:resume_id>/why-not-shortlisted/<int:job_id>")
@login_required
def why_not_shortlisted(resume_id, job_id):
    """
    Candidate-facing 'Why Was My Resume Not Shortlisted?' feature.
    Provides transparent, evidence-based gap analysis and published recruiter feedback.
    """
    resume = db.session.get(Resume, resume_id)
    job = db.session.get(Job, job_id)
    if not resume or not job:
        abort(404)

    if not can_access_resume(resume, current_user):
        abort(403)

    # Find the application linking this candidate and job
    application = Application.query.filter_by(job_id=job.id, candidate_user_id=resume.candidate_user_id).first()
    if not application:
        flash("No active application found linking this resume to the selected job.", "info")
        return redirect(url_for("resumes.compare", resume_id=resume.id, job_id=job.id))

    gap_data = ShortlistingGapService.get_gap_explanation(application, current_user)

    return render_template(
        "resumes/why_not_shortlisted.html",
        resume=resume,
        job=job,
        application=application,
        gap_data=gap_data
    )

