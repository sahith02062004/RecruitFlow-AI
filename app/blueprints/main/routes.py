from flask import Blueprint, render_template, jsonify
from app.models.models import Job, Application, CandidateProfile, User
from app.core.extensions import db

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    """Marketing and Landing page."""
    return render_template("main/index.html")


@main_bp.route("/dashboard")
def dashboard():
    """Consolidated recruiter dashboard view with accurate real counts (zero-state on fresh setup)."""
    # Count actual database records without inventing mock numbers
    total_jobs = Job.query.count()
    active_jobs = Job.query.filter_by(status="active").count()
    total_applications = Application.query.count()
    total_candidates = CandidateProfile.query.count()
    
    # Empty querysets for empty-state verification
    recent_jobs = Job.query.order_by(Job.created_at.desc()).limit(5).all()
    recent_applications = Application.query.order_by(Application.applied_at.desc()).limit(5).all()

    return render_template(
        "main/dashboard.html",
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        total_applications=total_applications,
        total_candidates=total_candidates,
        recent_jobs=recent_jobs,
        recent_applications=recent_applications
    )


@main_bp.route("/health")
def health_check():
    """Service health-check endpoint verifying DB connectivity."""
    db_status = "healthy"
    db_error = None
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception as exc:
        db_status = "unhealthy"
        db_error = str(exc)

    status_code = 200 if db_status == "healthy" else 503
    return jsonify({
        "status": "UP" if db_status == "healthy" else "DOWN",
        "service": "RecruitFlow AI",
        "version": "1.0.0-phase1",
        "database": {
            "status": db_status,
            "engine": db.engine.name if hasattr(db, "engine") and db.engine else "unknown",
            "error": db_error
        }
    }), status_code
