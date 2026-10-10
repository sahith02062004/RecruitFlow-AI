"""
Comprehensive Automated Test Suite for Phase 5: Candidate Matching & Ranking Engine.
Tests:
- Skill normalization, alias resolution, and strict distinct language boundaries (Java != JavaScript)
- Category scoring: required skills, preferred skills, experience, qualification
- Weight validation and dynamic redistribution for inapplicable categories
- Missing evidence handling and evidence coverage calculation
- Deterministic ranking and tie-breaking policy
- Staleness detection upon requirement or resume modification
- Multi-tenant organization isolation and RBAC defense
- Integration with real Phase 3 jobs and Phase 4 parsed resume applications
"""
import io
import json
import pytest
from app.core.extensions import db
from app.models.models import Job, Application, Resume, MatchResult, Organization, OrganizationMembership, User, CandidateProfile
from app.services.matching_config import (
    DEFAULT_WEIGHTS,
    SCORING_VERSION,
    validate_weights,
    MatchingConfigError
)
from app.services.skill_normalizer import SkillNormalizer
from app.services.scoring_service import ScoringService
from app.services.matching_service import MatchingService
from app.services.ranking_service import RankingService


# -------------------------------------------------------------
# 1. Skill Normalization & Comparison Tests
# -------------------------------------------------------------

def test_skill_normalizer_exact_and_case_insensitive():
    """Verify skills match regardless of case and surrounding whitespace."""
    matched, missing = SkillNormalizer.match_skills(
        candidate_skills=["python", "flask", "  docker  "],
        target_skills=["Python", "Flask", "Docker"]
    )
    assert matched == ["Docker", "Flask", "Python"]
    assert missing == []


def test_skill_normalizer_alias_resolution():
    """Verify aliases resolve to canonical names."""
    matched, missing = SkillNormalizer.match_skills(
        candidate_skills=["js", "postgres", "py", "k8s", "aws", "rest api"],
        target_skills=["JavaScript", "PostgreSQL", "Python", "Kubernetes", "AWS", "REST API"]
    )
    assert "JavaScript" in matched
    assert "PostgreSQL" in matched
    assert "Python" in matched
    assert "Kubernetes" in matched
    assert "AWS" in matched
    assert "REST API" in matched
    assert missing == []


def test_skill_normalizer_strict_distinction_java_vs_javascript():
    """Verify Java does NOT match JavaScript and C does NOT match C++ or C#."""
    # Candidate only has Java
    matched, missing = SkillNormalizer.match_skills(
        candidate_skills=["Java"],
        target_skills=["JavaScript"]
    )
    assert "JavaScript" not in matched
    assert "JavaScript" in missing

    # Candidate has C, job requires C++ and C#
    matched_c, missing_c = SkillNormalizer.match_skills(
        candidate_skills=["C"],
        target_skills=["C++", "C#"]
    )
    assert matched_c == []
    assert "C++" in missing_c
    assert "C#" in missing_c


def test_skill_normalizer_handles_empty_and_duplicate_inputs():
    """Verify deduplication and safe empty handling."""
    skills = SkillNormalizer.parse_skills_input("Python, python, PYTHON, , , Flask; Docker|Docker")
    assert skills == ["Docker", "Flask", "Python"]

    empty_res = SkillNormalizer.parse_skills_input("")
    assert empty_res == []

    none_res = SkillNormalizer.parse_skills_input(None)
    assert none_res == []


# -------------------------------------------------------------
# 2. Category Scoring & Mathematical Rules Tests
# -------------------------------------------------------------

def test_weight_validation():
    """Verify weights must sum to 1.0 (100%) and reject invalid configs."""
    valid = {"required_skills": 0.5, "preferred_skills": 0.2, "experience": 0.2, "qualification": 0.1}
    assert validate_weights(valid) == valid

    # Sum > 1.0
    with pytest.raises(MatchingConfigError):
        validate_weights({"required_skills": 0.6, "preferred_skills": 0.2, "experience": 0.2, "qualification": 0.1})

    # Missing category
    with pytest.raises(MatchingConfigError):
        validate_weights({"required_skills": 0.7, "preferred_skills": 0.3})

    # Negative weight
    with pytest.raises(MatchingConfigError):
        validate_weights({"required_skills": 1.1, "preferred_skills": -0.1, "experience": 0.0, "qualification": 0.0})


def test_required_and_preferred_skills_scoring():
    """Test required and preferred skills calculation formula."""
    # 3 of 4 required matched -> 75.0%
    req = ScoringService.score_required_skills(
        job_required_skills="Python, Flask, MySQL, Docker",
        candidate_skills=["Python", "Flask", "MySQL", "React"]
    )
    assert req["is_applicable"] is True
    assert req["score"] == 75.0
    assert "Docker" in req["missing"]

    # Inapplicable when job has no required skills
    no_req = ScoringService.score_required_skills(
        job_required_skills="",
        candidate_skills=["Python"]
    )
    assert no_req["is_applicable"] is False
    assert no_req["score"] is None


def test_experience_scoring():
    """Test experience alignment scoring under various candidate scenarios."""
    # Candidate exceeds minimum requirement (5 >= 3 years) -> 100%
    exp1 = ScoringService.score_experience(job_min_experience=3.0, job_max_experience=None, candidate_experience_years=5.0)
    assert exp1["score"] == 100.0

    # Candidate has partial experience (1.5 of 3 years) -> 50.0%
    exp2 = ScoringService.score_experience(job_min_experience=3.0, job_max_experience=None, candidate_experience_years=1.5)
    assert exp2["score"] == 50.0

    # Job is entry-level (0 years min requirement) -> 100%
    exp3 = ScoringService.score_experience(job_min_experience=0.0, job_max_experience=None, candidate_experience_years=0.0)
    assert exp3["score"] == 100.0

    # Candidate experience is missing/unextracted for a non-zero requirement
    exp4 = ScoringService.score_experience(job_min_experience=2.0, job_max_experience=None, candidate_experience_years=None, has_evidence=False)
    assert exp4["has_evidence"] is False
    assert exp4["score"] is None


def test_qualification_scoring():
    """Test education degree hierarchy evaluation."""
    # Candidate has Master's, role requires Bachelor's -> 100%
    q1 = ScoringService.score_qualification(job_min_qualification="Bachelor's", candidate_degrees=["M.S. in Computer Science"])
    assert q1["score"] == 100.0

    # Role specifies no qualification requirement -> Not applicable
    q2 = ScoringService.score_qualification(job_min_qualification=None, candidate_degrees=["B.Tech"])
    assert q2["is_applicable"] is False
    assert q2["score"] is None

    # Candidate degree evidence missing -> Not scored
    q3 = ScoringService.score_qualification(job_min_qualification="Bachelor's", candidate_degrees=[], has_evidence=False)
    assert q3["has_evidence"] is False
    assert q3["score"] is None


# -------------------------------------------------------------
# 3. Dynamic Weight Redistribution & Evidence Coverage Tests
# -------------------------------------------------------------

def test_dynamic_weight_redistribution_without_penalty():
    """
    When a category is not applicable (e.g., job specifies no preferred skills
    and no qualification requirement), candidate is NOT penalized;
    the applicable categories (required skills 50% + experience 20%) are normalized proportionally.
    """
    job_data = {
        "required_skills": "Python, Flask",
        "preferred_skills": None,  # Not applicable
        "minimum_experience_years": 2.0,
        "minimum_qualification": None,  # Not applicable
    }
    candidate_data = {
        "skills": ["Python", "Flask"],  # 100% on required skills
        "total_experience_years": 2.0,   # 100% on experience
        "has_experience_evidence": True,
        "education_degrees": [],
        "has_education_evidence": False,
    }

    result = ScoringService.calculate_overall_match(job_data, candidate_data)

    # Both applicable categories scored 100% -> Overall score must be 100.0%
    assert result["overall_score"] == 100.0
    assert result["evidence_coverage"] == 100.0
    assert result["category_scores"]["preferred_skills"]["is_applicable"] is False
    assert result["category_scores"]["qualification"]["is_applicable"] is False


def test_missing_evidence_coverage_and_unavailable_status():
    """
    When evidence is completely missing, overall score is marked 'unavailable'
    rather than fabricating a zero or random number.
    """
    job_data = {
        "required_skills": "Python, React",
        "preferred_skills": "AWS",
        "minimum_experience_years": 3.0,
        "minimum_qualification": "Bachelor's",
    }
    candidate_empty = {
        "skills": [],
        "total_experience_years": None,
        "has_experience_evidence": False,
        "education_degrees": [],
        "has_education_evidence": False,
    }

    result = ScoringService.calculate_overall_match(job_data, candidate_empty)
    # Required skills had empty match (0%), preferred skills (0%), but experience and qual lacked evidence
    assert result["evidence_coverage"] < 100.0
    assert result["overall_score"] is not None  # Required skills had evidence of 0 matches

    # Test complete zero evidence (e.g. no applicable requirements have evidence)
    job_data_exp_only = {
        "required_skills": None,
        "preferred_skills": None,
        "minimum_experience_years": 4.0,
        "minimum_qualification": None,
    }
    cand_no_exp = {
        "skills": [],
        "total_experience_years": None,
        "has_experience_evidence": False,
    }
    res_unavail = ScoringService.calculate_overall_match(job_data_exp_only, cand_no_exp)
    assert res_unavail["overall_score"] is None
    assert res_unavail["status"] == "unavailable"
    assert res_unavail["evidence_coverage"] == 0.0


# -------------------------------------------------------------
# 4. Deterministic Ranking & Tie-Breaking Tests
# -------------------------------------------------------------

def test_ranking_service_deterministic_ordering_and_tie_breaking(session, recruiter_user):
    """
    Verify ranking order:
    1. Overall score DESC
    2. Tie-break: Evidence coverage DESC
    3. Tie-break: Earlier application timestamp ASC
    4. Unavailable scores sorted to the bottom
    """
    org = recruiter_user.memberships.first().organization
    job = Job(
        organization_id=org.id,
        created_by_user_id=recruiter_user.id,
        title="Senior Python Architect",
        status="published",
        required_skills="Python, Flask, Docker",
        minimum_experience_years=3.0,
        description="Lead backend architecture."
    )
    session.add(job)
    session.flush()

    # Create 3 candidate users
    c1 = User(full_name="Alice Candidate", email="alice@test.com", role="candidate")
    c1.set_password("Secret123!")
    c2 = User(full_name="Bob Candidate", email="bob@test.com", role="candidate")
    c2.set_password("Secret123!")
    c3 = User(full_name="Charlie Candidate", email="charlie@test.com", role="candidate")
    c3.set_password("Secret123!")
    session.add_all([c1, c2, c3])
    session.flush()

    # Application 1: Score 90.0%
    app1 = Application(job_id=job.id, candidate_user_id=c1.id, status="submitted", match_score=90.0)
    # Application 2: Score 90.0% (TIE with app1, but lower evidence coverage)
    app2 = Application(job_id=job.id, candidate_user_id=c2.id, status="submitted", match_score=90.0)
    # Application 3: Score 60.0%
    app3 = Application(job_id=job.id, candidate_user_id=c3.id, status="submitted", match_score=60.0)
    session.add_all([app1, app2, app3])
    session.flush()

    # MatchResult 1: 90% score, 100% evidence coverage
    mr1 = MatchResult(
        application_id=app1.id,
        job_id=job.id,
        candidate_user_id=c1.id,
        overall_score=90.0,
        evidence_coverage=100.0,
        status="current",
        scoring_weights_snapshot=json.dumps(DEFAULT_WEIGHTS),
        category_scores=json.dumps({})
    )
    # MatchResult 2: 90% score, 80% evidence coverage (loses tie-break to app1)
    mr2 = MatchResult(
        application_id=app2.id,
        job_id=job.id,
        candidate_user_id=c2.id,
        overall_score=90.0,
        evidence_coverage=80.0,
        status="current",
        scoring_weights_snapshot=json.dumps(DEFAULT_WEIGHTS),
        category_scores=json.dumps({})
    )
    # MatchResult 3: 60% score
    mr3 = MatchResult(
        application_id=app3.id,
        job_id=job.id,
        candidate_user_id=c3.id,
        overall_score=60.0,
        evidence_coverage=100.0,
        status="current",
        scoring_weights_snapshot=json.dumps(DEFAULT_WEIGHTS),
        category_scores=json.dumps({})
    )
    session.add_all([mr1, mr2, mr3])
    session.commit()

    ranking = RankingService.get_ranked_candidates(job)
    ranked_items = ranking["items"]

    assert len(ranked_items) == 3
    # First: Alice (90% score, 100% coverage)
    assert ranked_items[0]["candidate_user"].email == "alice@test.com"
    assert ranked_items[0]["rank"] == 1
    # Second: Bob (90% score, 80% coverage)
    assert ranked_items[1]["candidate_user"].email == "bob@test.com"
    assert ranked_items[1]["rank"] == 2
    # Third: Charlie (60% score)
    assert ranked_items[2]["candidate_user"].email == "charlie@test.com"
    assert ranked_items[2]["rank"] == 3


# -------------------------------------------------------------
# 5. Staleness Hashing & On-Demand Recalculation Tests
# -------------------------------------------------------------

def test_staleness_detection_upon_job_requirement_change(session, recruiter_user, candidate_user):
    """Verify that updating a job's required skills marks the existing MatchResult as stale."""
    org = recruiter_user.memberships.first().organization
    job = Job(
        organization_id=org.id,
        created_by_user_id=recruiter_user.id,
        title="Backend Engineer",
        status="published",
        required_skills="Python, Flask",
        minimum_experience_years=2.0,
        description="Backend API role"
    )
    session.add(job)
    session.flush()

    app = Application(job_id=job.id, candidate_user_id=candidate_user.id, status="submitted")
    session.add(app)
    session.commit()

    # Evaluate initial match
    mr = MatchingService.evaluate_application(app)
    assert mr.status == "current"
    assert MatchingService.check_staleness(mr) is False

    # Modify job requirements
    job.required_skills = "Python, Flask, PyTorch, Kubernetes"
    session.commit()

    # Staleness check should now return True and update status to 'stale'
    is_stale = MatchingService.check_staleness(mr)
    assert is_stale is True
    assert mr.status == "stale"

    # Recalculate resets status to current
    updated_mr = MatchingService.evaluate_application(app)
    assert updated_mr.status == "current"
    assert MatchingService.check_staleness(updated_mr) is False


# -------------------------------------------------------------
# 6. Security & Multi-Tenant Authorization Tests
# -------------------------------------------------------------

def test_unauthorized_recruiter_cannot_access_foreign_job_rankings(client, candidate_user, recruiter_user, session):
    """Recruiter receives HTTP 403 when trying to access or run matching for another organization's job."""
    # Create foreign organization and job
    foreign_org = Organization(name="Competitor Inc", slug="competitor-inc", is_active=True, is_verified=True)
    foreign_user = User(full_name="Competitor Recruiter", email="recruiter@competitor.com", role="recruiter")
    foreign_user.set_password("Secret123!")
    session.add_all([foreign_org, foreign_user])
    session.flush()

    foreign_membership = OrganizationMembership(organization_id=foreign_org.id, user_id=foreign_user.id, is_active=True)
    foreign_job = Job(
        organization_id=foreign_org.id,
        created_by_user_id=foreign_user.id,
        title="Security Lead",
        status="published",
        required_skills="Rust, Cryptography",
        description="Lead security."
    )
    session.add_all([foreign_membership, foreign_job])
    session.commit()

    # Log in as recruiter_user (belongs to Acme Corp, NOT Competitor Inc)
    client.post("/auth/login", data={"email": recruiter_user.email, "password": "RecruiterSecret123!"})

    # Attempt to view foreign job rankings -> HTTP 403
    res_rankings = client.get(f"/matching/jobs/{foreign_job.id}")
    assert res_rankings.status_code == 403

    # Attempt to trigger matching on foreign job -> HTTP 403
    res_run = client.post(f"/matching/jobs/{foreign_job.id}/run")
    assert res_run.status_code == 403


def test_candidate_cannot_access_recruiter_matching_endpoints(client, candidate_user, recruiter_user, session):
    """Candidate receives HTTP 403 if attempting to access recruiter ranking or explanation routes."""
    org = recruiter_user.memberships.first().organization
    job = Job(
        organization_id=org.id,
        created_by_user_id=recruiter_user.id,
        title="ML Engineer",
        status="published",
        required_skills="Python, PyTorch",
        description="Machine learning role."
    )
    session.add(job)
    session.flush()

    app = Application(job_id=job.id, candidate_user_id=candidate_user.id, status="submitted")
    session.add(app)
    session.commit()

    mr = MatchingService.evaluate_application(app)

    # Log in as candidate
    client.post("/auth/login", data={"email": candidate_user.email, "password": "CandidateSecret123!"})

    # Matching overview -> 403
    assert client.get("/matching/").status_code == 403
    # Job rankings -> 403
    assert client.get(f"/matching/jobs/{job.id}").status_code == 403
    # Explanation -> 403
    assert client.get(f"/matching/applications/{app.id}/explanation").status_code == 403
    # Recalculate -> 403
    assert client.post(f"/matching/applications/{app.id}/recalculate").status_code == 403


# -------------------------------------------------------------
# 7. End-to-End Integration Flow Tests
# -------------------------------------------------------------

def test_end_to_end_matching_with_phase4_resume(client, recruiter_user, candidate_user, session):
    """
    Tests complete integration:
    - Candidate with Phase 4 parsed resume applies to recruiter job
    - Recruiter triggers batch matching via UI
    - Leaderboard and explanation page render transparently with HTTP 200
    """
    org = recruiter_user.memberships.first().organization
    job = Job(
        organization_id=org.id,
        created_by_user_id=recruiter_user.id,
        title="Full Stack Software Engineer",
        status="published",
        required_skills="Python, Flask, PostgreSQL, Docker",
        preferred_skills="Kubernetes, AWS",
        minimum_experience_years=2.0,
        minimum_qualification="Bachelor's",
        description="Build full stack web apps."
    )
    session.add(job)
    session.flush()

    # Create Phase 4 Resume for candidate with extracted data payload
    extracted_data = {
        "name": candidate_user.full_name,
        "email": candidate_user.email,
        "phone": "+1 (555) 123-4567",
        "skills": ["Python", "Flask", "PostgreSQL", "Docker", "AWS"],
        "total_experience_years": 3.5,
        "education": [{"degree": "B.Tech in Computer Science", "year": "2018 - 2022"}],
        "summary": "Passionate software builder."
    }
    resume = Resume(
        candidate_user_id=candidate_user.id,
        filename="candidate_cv.pdf",
        original_filename="candidate_cv.pdf",
        file_path="uploads/resumes/candidate_cv.pdf",
        file_type="pdf",
        file_size=1024,
        processing_status="processed",
        parsing_status="completed"
    )
    resume.set_extracted_data(extracted_data)
    session.add(resume)
    session.flush()

    app = Application(
        job_id=job.id,
        candidate_user_id=candidate_user.id,
        resume_id=resume.id,
        status="submitted"
    )
    session.add(app)
    session.commit()

    # Recruiter logs in
    client.post("/auth/login", data={"email": recruiter_user.email, "password": "RecruiterSecret123!"})

    # 1. Matching Index View
    res_index = client.get("/matching/")
    assert res_index.status_code == 200
    assert b"Full Stack Software Engineer" in res_index.data

    # 2. Trigger Batch Matching
    res_run = client.post(f"/matching/jobs/{job.id}/run", follow_redirects=True)
    assert res_run.status_code == 200
    assert b"Matching evaluation completed" in res_run.data

    # 3. View Candidate Rankings
    res_rank = client.get(f"/matching/jobs/{job.id}")
    assert res_rank.status_code == 200
    assert b"Applicant Leaderboard" in res_rank.data
    assert candidate_user.full_name.encode() in res_rank.data
    # Required skills matched: Python, Flask, PostgreSQL, Docker (4/4 -> 100%)
    # Preferred: AWS (1/2 -> 50%)
    # Experience: 3.5 >= 2.0 -> 100%
    # Qualification: B.Tech meets Bachelor's -> 100%
    # Score = 0.5*100 + 0.2*50 + 0.2*100 + 0.1*100 = 50 + 10 + 20 + 10 = 90.0%
    assert b"90" in res_rank.data

    # 4. View Transparent Explanation Page
    res_explain = client.get(f"/matching/applications/{app.id}/explanation")
    assert res_explain.status_code == 200
    assert b"Transparent Calculation Formula" in res_explain.data
    assert b"Required Skills (50%)" in res_explain.data
    assert b"Responsible AI &amp; Fair Recruitment Safeguards" in res_explain.data
