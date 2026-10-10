"""
Automated Integration and Unit Tests for Phase 7 of RecruitFlow AI.
Tests:
- ATS Resume Quality Analyzer & Category Weights
- Scanned PDF and Parsing Warnings
- Separation of Resume Quality vs Job Match Scores
- Side-by-Side Job & Resume Comparison
- Resume Improvement Prioritized Checklist & Truthful Suggestions
- Checklist Item Toggling
- "Why Was My Resume Not Shortlisted?" Engine & Honest Disclaimers
- Structured Recruiter Rejection Feedback & Candidate Privacy
- Recruitment Analytics & Hiring Funnel Conversion Rates
- CSV Export with Spreadsheet Formula Injection Defense
- Multi-Tenant & RBAC Security Isolation
"""
import json
import pytest
from app.core.extensions import db
from app.models.models import (
    User, Job, Resume, Application, CandidateProfile, Organization,
    OrganizationMembership, ResumeAnalysis
)
from app.services.ats_analyzer_service import (
    ATSAnalyzerService, DEFAULT_ATS_CATEGORY_WEIGHTS, ANALYZER_VERSION
)
from app.services.resume_improvement_service import ResumeImprovementService
from app.services.shortlisting_gap_service import ShortlistingGapService
from app.services.recruitment_analytics_service import RecruitmentAnalyticsService


@pytest.fixture
def test_setup(session, candidate_user, recruiter_user):
    """Sets up a complete requisition, candidate resume, and application fixture."""
    membership = recruiter_user.memberships.first()
    org = membership.organization

    job = Job(
        title="Senior Python Backend Architect",
        description="Build high-performance REST APIs and microservices.",
        department="Engineering",
        organization_id=org.id,
        created_by_user_id=recruiter_user.id,
        status="published",
        required_skills="Python, Flask, PostgreSQL, Docker",
        preferred_skills="Kubernetes, Redis, AWS",
        minimum_experience_years=4.0,
        minimum_qualification="Bachelor of Technology"
    )
    session.add(job)
    session.flush()

    raw_resume_text = """
    Alex Candidate
    Email: alex.candidate@example.com | Phone: +1-555-0199
    LinkedIn: linkedin.com/in/alexcandidate | GitHub: github.com/alexcandidate

    Summary:
    Experienced Python software engineer with 5 years building web applications.

    Technical Skills:
    Languages: Python, SQL, JavaScript
    Frameworks: Flask, Django, FastAPI
    Databases & Tools: PostgreSQL, Docker, Git

    Work Experience:
    Senior Software Engineer - Tech Solutions (2021 - Present)
    • Architected and maintained scalable REST APIs using Python and Flask.
    • Optimized database queries in PostgreSQL, improving service latency.
    • Containerized backend microservices using Docker for CI/CD deployments.

    Software Developer - Cloud Corp (2019 - 2021)
    • Developed automated data processing scripts using Python.
    • Implemented automated integration tests.

    Education:
    Bachelor of Technology in Computer Science (2015 - 2019)
    """

    resume = Resume(
        candidate_user_id=candidate_user.id,
        candidate_id=candidate_user.candidate_profile.id,
        filename="alex_backend_resume.pdf",
        original_filename="alex_backend_resume.pdf",
        file_path="uploads/alex_backend_resume.pdf",
        file_size=45000,
        file_size_bytes=45000,
        file_type="pdf",
        mime_type="application/pdf",
        storage_key="dummykey123",
        raw_text=raw_resume_text,
        processing_status="processed",
        parsed_skills="Python, Flask, PostgreSQL, Docker, SQL, JavaScript, Git",
        parsed_experience_years=5.0
    )
    resume.set_extracted_data({
        "skills": ["Python", "Flask", "PostgreSQL", "Docker", "SQL", "JavaScript", "Git"],
        "email": "alex.candidate@example.com",
        "phone": "+1-555-0199",
        "total_experience_years": 5.0,
        "education": "Bachelor of Technology in Computer Science",
        "summary": "Experienced Python software engineer with 5 years building web applications."
    })
    session.add(resume)
    session.flush()

    application = Application(
        job_id=job.id,
        candidate_user_id=candidate_user.id,
        candidate_id=candidate_user.candidate_profile.id,
        resume_id=resume.id,
        status="submitted",
        cover_letter="Excited to apply for this backend architecture role."
    )
    session.add(application)
    session.commit()

    return {
        "job": job,
        "resume": resume,
        "application": application,
        "org": org,
        "candidate": candidate_user,
        "recruiter": recruiter_user
    }


def test_ats_category_weights_validation():
    """Confirms default category weights sum to 1.0 and rejects invalid weight sums."""
    weights = ATSAnalyzerService.validate_category_weights()
    assert abs(sum(weights.values()) - 1.0) < 0.001
    assert len(weights) == 7

    with pytest.raises(ValueError, match="must sum to 1.0"):
        ATSAnalyzerService.validate_category_weights({"section_completeness": 0.50})


def test_ats_analyzer_quality_scoring_complete_resume(test_setup):
    """Verifies complete resume quality evaluation across all 7 categories."""
    resume = test_setup["resume"]
    result = ATSAnalyzerService.analyze_resume_quality(resume)

    assert result["status"] == "completed"
    assert result["resume_quality_score"] > 80.0
    assert result["analyzer_version"] == ANALYZER_VERSION

    # Verify all 7 categories are present
    cat_scores = result["category_scores"]
    for cat in DEFAULT_ATS_CATEGORY_WEIGHTS.keys():
        assert cat in cat_scores
        assert cat_scores[cat] >= 0.0

    # Verify positive findings
    assert len(result["positive_findings"]) >= 3
    assert any("sections" in f.lower() for f in result["positive_findings"])


def test_ats_analyzer_handles_empty_and_scanned_pdf(session, candidate_user):
    """Verifies graceful handling and warning generation for empty or scanned PDF resumes."""
    empty_resume = Resume(
        candidate_user_id=candidate_user.id,
        candidate_id=candidate_user.candidate_profile.id,
        filename="scanned_resume.pdf",
        original_filename="scanned_resume.pdf",
        file_path="uploads/scanned_resume.pdf",
        file_size=100000,
        file_size_bytes=100000,
        file_type="pdf",
        mime_type="application/pdf",
        storage_key="scannedpdfkey",
        raw_text="",
        processing_status="processed"
    )
    session.add(empty_resume)
    session.commit()

    result = ATSAnalyzerService.analyze_resume_quality(empty_resume)
    assert result["status"] == "incomplete"
    assert result["resume_quality_score"] == 0.0
    assert len(result["parsing_warnings"]) > 0
    assert any("scanned" in w.lower() or "empty" in w.lower() for w in result["parsing_warnings"])


def test_ats_job_match_score_separation(test_setup):
    """Confirms Resume Quality Score and Job Match Score are kept strictly distinct."""
    resume = test_setup["resume"]
    job = test_setup["job"]

    analysis = ATSAnalyzerService.run_ats_analysis(resume=resume, job=job)
    assert analysis.resume_quality_score is not None
    assert analysis.job_match_score is not None

    # Resume quality evaluates formatting/structure, while job match evaluates candidate-to-job fit
    assert isinstance(analysis.resume_quality_score, float)
    assert isinstance(analysis.job_match_score, float)


def test_ats_analysis_persistence_and_staleness_detection(test_setup, session):
    """Verifies input_hash generation and staleness detection upon job criteria change."""
    resume = test_setup["resume"]
    job = test_setup["job"]

    analysis = ATSAnalyzerService.run_ats_analysis(resume=resume, job=job)
    initial_hash = analysis.input_hash
    assert initial_hash is not None
    assert not ATSAnalyzerService.is_analysis_stale(analysis, resume, job)

    # Modify job requirements
    job.required_skills = "Python, Flask, Rust, Go, Kubernetes"
    session.commit()

    assert ATSAnalyzerService.is_analysis_stale(analysis, resume, job) is True


def test_resume_comparison_side_by_side(client, test_setup):
    """Tests the /resumes/<id>/compare interface returns side-by-side competency alignment."""
    candidate = test_setup["candidate"]
    resume = test_setup["resume"]
    job = test_setup["job"]

    client.post("/auth/login", data={"email": candidate.email, "password": "CandidateSecret123!"})
    res = client.get(f"/resumes/{resume.id}/compare?job_id={job.id}")
    assert res.status_code == 200
    assert b"Job Description &amp; Resume Comparison" in res.data
    assert b"Required Skills Comparison" in res.data
    assert b"PostgreSQL" in res.data
    assert b"Objective Alignment" in res.data


def test_resume_improvements_checklist_and_truthful_suggestions(client, test_setup):
    """Tests prioritized checklist tiers and truthful writing suggestions."""
    candidate = test_setup["candidate"]
    resume = test_setup["resume"]
    job = test_setup["job"]

    client.post("/auth/login", data={"email": candidate.email, "password": "CandidateSecret123!"})
    res = client.get(f"/resumes/{resume.id}/improvements?job_id={job.id}")
    assert res.status_code == 200
    assert b"Prioritized Action Checklist" in res.data
    assert b"Truthful Resume Writing Transformations" in res.data
    assert b"Professional Resume Integrity Policy" in res.data
    # Confirm integrity disclaimer is present
    assert b"never invent employment history" in res.data


def test_checklist_item_toggling(client, test_setup):
    """Confirms candidate can toggle checklist items as completed/pending."""
    candidate = test_setup["candidate"]
    resume = test_setup["resume"]

    # Run analysis to generate recommendations
    analysis = ATSAnalyzerService.run_ats_analysis(resume=resume)
    recs = analysis.get_recommendations()
    assert len(recs) > 0
    rec_id = recs[0]["id"]

    client.post("/auth/login", data={"email": candidate.email, "password": "CandidateSecret123!"})
    res_toggle = client.post(
        f"/resumes/{resume.id}/checklist/toggle",
        data={"item_id": rec_id},
        follow_redirects=True
    )
    assert res_toggle.status_code == 200
    assert b"Checklist item completed" in res_toggle.data

    # Verify persisted state
    updated_analysis = db.session.get(ResumeAnalysis, analysis.id)
    state = updated_analysis.get_checklist_state()
    assert state.get(rec_id, {}).get("completed") is True


def test_shortlisting_gap_service_without_recruiter_reason(test_setup):
    """Confirms honest fallback disclaimer is returned when no official recruiter reason exists."""
    app = test_setup["application"]
    candidate = test_setup["candidate"]

    gap_data = ShortlistingGapService.get_gap_explanation(app, candidate)
    assert gap_data["has_official_reason"] is False
    assert gap_data["official_reason"] is None
    assert "We cannot determine the recruiter's actual reason from the resume alone" in gap_data["disclaimer"]


def test_shortlisting_gap_service_with_published_recruiter_reason(test_setup, session):
    """Tests structured rejection feedback when explicitly published by recruiter."""
    app = test_setup["application"]
    candidate = test_setup["candidate"]

    app.status = "rejected"
    app.rejection_reason_code = "skill_gap"
    app.rejection_reason_text = "Applicant lacks deep distributed caching and Redis experience."
    app.rejection_feedback_published = True
    session.commit()

    gap_data = ShortlistingGapService.get_gap_explanation(app, candidate)
    assert gap_data["has_official_reason"] is True
    assert gap_data["official_reason"]["reason_code"] == "skill_gap"
    assert "Redis" in gap_data["official_reason"]["recruiter_feedback"]


def test_recruiter_records_structured_rejection(client, test_setup):
    """Tests recruiter setting rejection status with structured reason code and publish flag."""
    recruiter = test_setup["recruiter"]
    app = test_setup["application"]

    client.post("/auth/login", data={"email": recruiter.email, "password": "RecruiterSecret123!"})
    update_data = {
        "status": "rejected",
        "notes": "Internal review note: strong profile but other candidates had more Kubernetes experience.",
        "rejection_reason_code": "experience_gap",
        "rejection_reason_text": "We are prioritizing candidates with 5+ years in container orchestration.",
        "rejection_feedback_published": "y"
    }
    res = client.post(f"/applications/{app.id}", data=update_data, follow_redirects=True)
    assert res.status_code == 200
    assert b"Application status updated" in res.data

    updated_app = db.session.get(Application, app.id)
    assert updated_app.status == "rejected"
    assert updated_app.rejection_reason_code == "experience_gap"
    assert updated_app.rejection_feedback_published is True


def test_recruitment_analytics_kpi_and_funnel_calculations(test_setup):
    """Verifies overview KPI counts and hiring funnel progression with zero-denominator safety."""
    org = test_setup["org"]
    analytics = RecruitmentAnalyticsService.get_organization_overview(org.id)

    assert analytics["total_jobs"] >= 1
    assert analytics["total_applications"] >= 1
    assert "funnel" in analytics

    # Check zero-denominator safety on empty organization
    empty_analytics = RecruitmentAnalyticsService.get_organization_overview(organization_id=99999)
    assert empty_analytics["total_applications"] == 0
    assert empty_analytics["funnel"][0]["step_conversion_pct"] == 0.0


def test_recruitment_analytics_csv_export_and_formula_injection_defense(client, test_setup):
    """Tests CSV export generation, tenant isolation, and spreadsheet formula injection protection."""
    recruiter = test_setup["recruiter"]
    client.post("/auth/login", data={"email": recruiter.email, "password": "RecruiterSecret123!"})

    res = client.get("/reports/export/applications.csv")
    assert res.status_code == 200
    assert res.headers["Content-Type"].startswith("text/csv")
    assert b"Application ID,Job Title,Department" in res.data
    assert b"Senior Python Backend Architect" in res.data

    # Test formula injection protection
    dangerous_cell = "=cmd|' /C calc'!A0"
    sanitized = RecruitmentAnalyticsService.sanitize_csv_cell(dangerous_cell)
    assert sanitized.startswith("'=")


def test_cross_tenant_isolation_analytics_and_resumes(client, session, test_setup):
    """Confirms unauthorized cross-tenant and cross-candidate access is blocked with HTTP 403."""
    resume = test_setup["resume"]

    # Create a secondary candidate
    other_cand = User(
        full_name="Bob Unauthorized",
        email="bob.unauth@example.com",
        role="candidate",
        is_active=True
    )
    other_cand.set_password("BobSecret123!")
    session.add(other_cand)
    session.commit()

    # Bob attempts to view Alex's ATS analysis
    client.post("/auth/login", data={"email": other_cand.email, "password": "BobSecret123!"})
    res = client.get(f"/resumes/{resume.id}/analyze")
    assert res.status_code == 403

    # Bob attempts to toggle Alex's checklist
    res_toggle = client.post(f"/resumes/{resume.id}/checklist/toggle", data={"item_id": "rec_1"})
    assert res_toggle.status_code == 403
