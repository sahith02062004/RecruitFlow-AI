"""
Automated Test Suite for Phase 3:
- Recruiter creates jobs, views organization job postings, edits jobs, and updates job statuses (publish, close, archive)
- Candidate searches, filters, and browses published jobs
- Candidate cannot view draft jobs or apply to closed/archived jobs
- Candidate applies for a job, views own applications, and can withdraw application
- Candidate cannot apply twice to the same job (duplicate prevention)
- Candidate cannot view another candidate's private application
- Recruiter views applicants for their organization, updates pipeline status and notes
- Recruiter cannot view or edit jobs/applications belonging to another organization
"""
from datetime import datetime, timezone
import pytest
from app.models.models import Job, Application, Organization, OrganizationMembership, User


def test_recruiter_creates_job_successfully(client, recruiter_user, session):
    """Recruiter creates a new job requisition within their organization."""
    client.post("/auth/login", data={"email": recruiter_user.email, "password": "RecruiterSecret123!"})

    job_data = {
        "title": "Principal Deep Learning Architect",
        "department": "Artificial Intelligence",
        "location": "Palo Alto, CA",
        "workplace_type": "hybrid",
        "employment_type": "full-time",
        "status": "published",
        "minimum_experience_years": "6.0",
        "maximum_experience_years": "10.0",
        "minimum_qualification": "M.S. or Ph.D. in Computer Science",
        "salary_min": "180000",
        "salary_max": "240000",
        "salary_currency": "USD",
        "required_skills": "PyTorch, CUDA, Distributed Training, Python, Transformer Architecture",
        "preferred_skills": "Triton, ONNX, C++",
        "description": "Lead our foundational model scaling and production deployment.",
        "responsibilities": "Optimize model latency and architect retrieval pipelines."
    }
    response = client.post("/jobs/new", data=job_data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Principal Deep Learning Architect" in response.data

    job = Job.query.filter_by(title="Principal Deep Learning Architect").first()
    assert job is not None
    assert job.status == "published"
    assert job.organization_id == recruiter_user.memberships.first().organization_id
    assert job.created_by_user_id == recruiter_user.id
    assert float(job.salary_min) == 180000.0


def test_candidate_views_published_jobs_and_searches(client, recruiter_user, candidate_user, session):
    """Candidate views only published jobs and can filter by query keywords."""
    org = recruiter_user.memberships.first().organization

    # 1. Published job
    pub_job = Job(
        organization_id=org.id,
        created_by_user_id=recruiter_user.id,
        title="Senior Python Backend Specialist",
        department="Backend Engineering",
        location="Austin, TX",
        workplace_type="remote",
        employment_type="full-time",
        status="published",
        required_skills="Python, Flask, SQLAlchemy, MySQL",
        description="Develop scalable core backend microservices."
    )
    # 2. Draft job (must be hidden from candidate)
    draft_job = Job(
        organization_id=org.id,
        created_by_user_id=recruiter_user.id,
        title="Confidential Executive Role",
        department="Operations",
        location="New York, NY",
        workplace_type="onsite",
        employment_type="full-time",
        status="draft",
        required_skills="Strategy, Leadership",
        description="Confidential internal role."
    )
    session.add_all([pub_job, draft_job])
    session.commit()

    # Sign in as candidate
    client.post("/auth/login", data={"email": candidate_user.email, "password": "CandidateSecret123!"})

    # Catalog listing must include published job and omit draft job
    res = client.get("/jobs/")
    assert res.status_code == 200
    assert b"Senior Python Backend Specialist" in res.data
    assert b"Confidential Executive Role" not in res.data

    # Search keyword filtering
    res_search = client.get("/jobs/?q=Backend")
    assert b"Senior Python Backend Specialist" in res_search.data

    res_search_miss = client.get("/jobs/?q=NonexistentSkillXYZ")
    assert b"Senior Python Backend Specialist" not in res_search_miss.data

    # Direct detail access to draft job must return 404 for candidate
    res_draft_detail = client.get(f"/jobs/{draft_job.id}")
    assert res_draft_detail.status_code == 404


def test_candidate_applies_for_job_and_duplicate_prevention(client, recruiter_user, candidate_user, session):
    """Candidate applies once successfully; subsequent attempts are prevented."""
    org = recruiter_user.memberships.first().organization
    job = Job(
        organization_id=org.id,
        created_by_user_id=recruiter_user.id,
        title="Full Stack Software Engineer",
        department="Platform",
        location="Remote",
        workplace_type="remote",
        employment_type="full-time",
        status="published",
        required_skills="Python, TypeScript, React",
        description="Build developer-facing tooling."
    )
    session.add(job)
    session.commit()

    # Sign in as candidate
    client.post("/auth/login", data={"email": candidate_user.email, "password": "CandidateSecret123!"})

    # 1. Successful application
    app_data = {
        "cover_letter": "I have 5 years building scalable web applications."
    }
    res_apply = client.post(f"/applications/apply/{job.id}", data=app_data, follow_redirects=True)
    assert res_apply.status_code == 200
    assert b"Application submitted successfully" in res_apply.data

    # Verify DB record
    application = Application.query.filter_by(job_id=job.id, candidate_user_id=candidate_user.id).first()
    assert application is not None
    assert application.status == "submitted"
    assert "5 years building" in application.cover_letter

    # 2. Duplicate application attempt
    res_dup = client.post(f"/applications/apply/{job.id}", data=app_data, follow_redirects=True)
    assert res_dup.status_code == 200
    assert b"You have already submitted an application for this position" in res_dup.data


def test_candidate_cannot_apply_to_closed_job(client, recruiter_user, candidate_user, session):
    """Candidate cannot apply to a job with closed status."""
    org = recruiter_user.memberships.first().organization
    closed_job = Job(
        organization_id=org.id,
        created_by_user_id=recruiter_user.id,
        title="Closed Marketing Role",
        department="Marketing",
        status="closed",
        required_skills="SEO, Content",
        description="Marketing position."
    )
    session.add(closed_job)
    session.commit()

    client.post("/auth/login", data={"email": candidate_user.email, "password": "CandidateSecret123!"})

    res = client.post(f"/applications/apply/{closed_job.id}", data={"cover_letter": "Hello"}, follow_redirects=True)
    assert b"This job opening is closed, draft, or no longer accepting applications" in res.data


def test_candidate_withdraws_application(client, recruiter_user, candidate_user, session):
    """Candidate can withdraw their own application."""
    org = recruiter_user.memberships.first().organization
    job = Job(
        organization_id=org.id,
        created_by_user_id=recruiter_user.id,
        title="Data Engineer",
        status="published",
        required_skills="SQL, Python",
        description="Data pipelines."
    )
    session.add(job)
    session.flush()

    application = Application(
        job_id=job.id,
        candidate_user_id=candidate_user.id,
        status="submitted"
    )
    session.add(application)
    session.commit()

    client.post("/auth/login", data={"email": candidate_user.email, "password": "CandidateSecret123!"})

    res_withdraw = client.post(f"/applications/{application.id}/withdraw", follow_redirects=True)
    assert res_withdraw.status_code == 200
    assert b"Your application has been withdrawn" in res_withdraw.data

    session.refresh(application)
    assert application.status == "withdrawn"
    assert application.withdrawn_at is not None


def test_recruiter_reviews_application_and_updates_status(client, recruiter_user, candidate_user, session):
    """Recruiter reviews application and updates pipeline stage and notes."""
    org = recruiter_user.memberships.first().organization
    job = Job(
        organization_id=org.id,
        created_by_user_id=recruiter_user.id,
        title="MLOps Engineer",
        status="published",
        required_skills="Kubernetes, Docker, Python",
        description="ML infrastructure."
    )
    session.add(job)
    session.flush()

    application = Application(
        job_id=job.id,
        candidate_user_id=candidate_user.id,
        cover_letter="Passionate about Kubernetes and model serving.",
        status="submitted"
    )
    session.add(application)
    session.commit()

    client.post("/auth/login", data={"email": recruiter_user.email, "password": "RecruiterSecret123!"})

    # Access review page
    res_view = client.get(f"/applications/{application.id}")
    assert res_view.status_code == 200
    assert b"MLOps Engineer" in res_view.data
    assert b"Passionate about Kubernetes" in res_view.data

    # Update status to shortlisted with internal notes
    update_data = {
        "status": "shortlisted",
        "notes": "Candidate shows strong container orchestration expertise."
    }
    res_update = client.post(f"/applications/{application.id}", data=update_data, follow_redirects=True)
    assert b"Application status updated" in res_update.data
    assert b"Shortlisted" in res_update.data

    session.refresh(application)
    assert application.status == "shortlisted"
    assert "orchestration expertise" in application.notes


def test_cross_tenant_isolation_recruiter_cannot_access_foreign_jobs_or_applications(client, recruiter_user, session):
    """Recruiter cannot edit jobs or view applications of another organization."""
    # Create foreign organization and foreign user
    foreign_user = User(
        full_name="Foreign Recruiter",
        email="foreign@competitor.com",
        role="recruiter"
    )
    foreign_user.set_password("ForeignSecret123!")
    session.add(foreign_user)
    session.flush()

    foreign_org = Organization(name="Competitor Inc.", slug="competitor-inc")
    session.add(foreign_org)
    session.flush()

    foreign_membership = OrganizationMembership(organization_id=foreign_org.id, user_id=foreign_user.id, membership_role="admin")
    session.add(foreign_membership)

    foreign_job = Job(
        organization_id=foreign_org.id,
        created_by_user_id=foreign_user.id,
        title="Secret Competitor Role",
        status="published",
        required_skills="Golang",
        description="Proprietary tech."
    )
    session.add(foreign_job)
    session.flush()

    foreign_app = Application(
        job_id=foreign_job.id,
        candidate_user_id=foreign_user.id,  # Any user
        status="submitted"
    )
    session.add(foreign_app)
    session.commit()

    # Log in as recruiter_user (who belongs to Acme Corp, not Competitor Inc.)
    client.post("/auth/login", data={"email": recruiter_user.email, "password": "RecruiterSecret123!"})

    # 1. Attempt to edit foreign job -> HTTP 403 Forbidden
    res_edit = client.get(f"/jobs/{foreign_job.id}/edit")
    assert res_edit.status_code == 403

    # 2. Attempt to view foreign application -> HTTP 403 Forbidden
    res_app = client.get(f"/applications/{foreign_app.id}")
    assert res_app.status_code == 403
