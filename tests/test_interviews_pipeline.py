"""
Unit and Integration Tests for Phase 6:
Interview Scheduling, Multi-Stage Pipeline Rubrics, Feedback Privacy, and Notifications.
"""
from datetime import datetime, timezone, timedelta
import pytest
from app.core.extensions import db
from app.models.models import (
    User,
    Organization,
    OrganizationMembership,
    CandidateProfile,
    Job,
    Application,
    Interview,
    InterviewAssignment,
    InterviewFeedback,
    ApplicationStageHistory,
    Notification
)
from app.services.interview_service import (
    schedule_interview,
    reschedule_interview,
    cancel_interview,
    update_interview_status,
    InterviewValidationError
)
from app.services.interview_feedback_service import (
    submit_or_update_feedback,
    get_candidate_visible_feedback,
    FeedbackValidationError
)
from app.services.hiring_pipeline_service import (
    transition_application_stage,
    StageTransitionError
)
from app.services.notification_service import (
    get_unread_count,
    mark_notification_as_read,
    mark_all_notifications_as_read
)


@pytest.fixture
def phase6_setup(session):
    """
    Sets up an isolated test fixture with:
    - 2 Organizations (Acme Corp, Beta Ltd)
    - 2 Recruiters (Recruiter 1 in Acme, Recruiter 2 in Beta)
    - 1 Reviewer/Interviewer in Acme
    - 2 Candidates (Charlie, Diana)
    - 1 Published Job at Acme
    - 1 Application from Charlie
    """
    # Users
    r1 = User(full_name="Alice Recruiter", email="recruiter1@acme.com", role="recruiter")
    r1.set_password("SecurePass123!")
    r2 = User(full_name="Bob Recruiter", email="recruiter2@beta.com", role="recruiter")
    r2.set_password("SecurePass123!")
    interviewer1 = User(full_name="Dave Engineer", email="dave@acme.com", role="recruiter")
    interviewer1.set_password("SecurePass123!")

    cand1 = User(full_name="Charlie Candidate", email="charlie@candidate.com", role="candidate")
    cand1.set_password("SecurePass123!")
    cand2 = User(full_name="Diana Candidate", email="diana@candidate.com", role="candidate")
    cand2.set_password("SecurePass123!")

    session.add_all([r1, r2, interviewer1, cand1, cand2])
    session.commit()

    # Candidate Profiles
    cp1 = CandidateProfile(user_id=cand1.id, headline="Backend Python Developer")
    cp2 = CandidateProfile(user_id=cand2.id, headline="Full Stack Developer")
    session.add_all([cp1, cp2])
    session.commit()

    # Organizations
    org1 = Organization(name="Acme Corp", slug="acme-corp")
    org2 = Organization(name="Beta Ltd", slug="beta-ltd")
    session.add_all([org1, org2])
    session.commit()

    # Memberships
    m1 = OrganizationMembership(organization_id=org1.id, user_id=r1.id, membership_role="admin")
    m2 = OrganizationMembership(organization_id=org2.id, user_id=r2.id, membership_role="admin")
    m_int = OrganizationMembership(organization_id=org1.id, user_id=interviewer1.id, membership_role="reviewer")
    session.add_all([m1, m2, m_int])
    session.commit()

    # Job
    job = Job(
        organization_id=org1.id,
        created_by_user_id=r1.id,
        title="Senior Python Backend Engineer",
        status="published",
        description="Build scalable distributed APIs",
        required_skills="Python, Flask, SQL, Docker",
        minimum_experience_years=3.0
    )
    session.add(job)
    session.commit()

    # Application from cand1
    app1 = Application(
        job_id=job.id,
        candidate_user_id=cand1.id,
        status="submitted",
        match_score=85.0
    )
    session.add(app1)
    session.commit()

    return {
        "r1_id": r1.id,
        "r2_id": r2.id,
        "interviewer1_id": interviewer1.id,
        "cand1_id": cand1.id,
        "cand2_id": cand2.id,
        "org1_id": org1.id,
        "org2_id": org2.id,
        "job_id": job.id,
        "app1_id": app1.id
    }


# =========================================================================
# 1. Interview Scheduling & Timing Validation
# =========================================================================

def test_valid_interview_scheduling(session, phase6_setup):
    """Verifies valid interview creation, assignment, and notification emission."""
    app1 = db.session.get(Application, phase66_id := phase6_setup["app1_id"])
    r1 = db.session.get(User, phase6_setup["r1_id"])
    interviewer1 = db.session.get(User, phase6_setup["interviewer1_id"])

    now = datetime.now(timezone.utc) + timedelta(days=2)
    start = now.replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=1)

    interview, warnings = schedule_interview(
        application_id=app1.id,
        round_name="Technical Screening Round",
        interview_type="online",
        scheduled_at=start,
        end_time=end,
        timezone_str="UTC",
        meeting_link="https://meet.google.com/abc-defg-hij",
        instructions="Please be ready to share code and test API queries.",
        interviewer_ids=[interviewer1.id],
        created_by_user_id=r1.id
    )

    assert interview.id is not None
    assert interview.round_name == "Technical Screening Round"
    assert interview.status == "scheduled"
    assert len(warnings) == 0

    # Verify InterviewAssignment record
    assignments = InterviewAssignment.query.filter_by(interview_id=interview.id).all()
    assert len(assignments) == 1
    assert assignments[0].interviewer_user_id == interviewer1.id

    # Verify candidate received notification
    cand_notifs = Notification.query.filter_by(
        recipient_user_id=phase6_setup["cand1_id"],
        notification_type="interview_scheduled"
    ).all()
    assert len(cand_notifs) == 1
    assert "Technical Screening Round" in cand_notifs[0].title


def test_invalid_interview_timing_rejected(session, phase6_setup):
    """Rejects interviews where end time is before or equal to start time."""
    app1 = db.session.get(Application, phase6_setup["app1_id"])
    r1 = db.session.get(User, phase6_setup["r1_id"])
    now = datetime.now(timezone.utc) + timedelta(days=1)

    # End time before start time
    with pytest.raises(InterviewValidationError, match="end time must be later"):
        schedule_interview(
            application_id=app1.id,
            round_name="Invalid Round",
            interview_type="online",
            scheduled_at=now + timedelta(hours=2),
            end_time=now + timedelta(hours=1),
            meeting_link="https://meet.google.com/test",
            created_by_user_id=r1.id
        )


def test_missing_meeting_link_or_location_rejected(session, phase6_setup):
    """Rejects online interviews without meeting URL or in-person without location."""
    app1 = db.session.get(Application, phase6_setup["app1_id"])
    r1 = db.session.get(User, phase6_setup["r1_id"])
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=1)

    # Online missing URL
    with pytest.raises(InterviewValidationError, match="meeting link"):
        schedule_interview(
            application_id=app1.id,
            round_name="Online No Link",
            interview_type="online",
            scheduled_at=start,
            end_time=end,
            meeting_link="",
            created_by_user_id=r1.id
        )

    # In-person missing location
    with pytest.raises(InterviewValidationError, match="location is required"):
        schedule_interview(
            application_id=app1.id,
            round_name="Onsite No Location",
            interview_type="in_person",
            scheduled_at=start,
            end_time=end,
            location="",
            created_by_user_id=r1.id
        )


def test_interviewer_schedule_overlap_warning(session, phase6_setup):
    """Detects when an assigned interviewer has an overlapping interview session."""
    app1 = db.session.get(Application, phase6_setup["app1_id"])
    r1 = db.session.get(User, phase6_setup["r1_id"])
    interviewer1 = db.session.get(User, phase6_setup["interviewer1_id"])

    start = datetime.now(timezone.utc) + timedelta(days=3)
    end = start + timedelta(hours=1)

    # First interview
    schedule_interview(
        application_id=app1.id,
        round_name="Round 1",
        interview_type="online",
        scheduled_at=start,
        end_time=end,
        meeting_link="https://meet.google.com/r1",
        interviewer_ids=[interviewer1.id],
        created_by_user_id=r1.id
    )

    # Overlapping second interview at same time for same interviewer
    _, warnings = schedule_interview(
        application_id=app1.id,
        round_name="Round 2 Overlap",
        interview_type="online",
        scheduled_at=start + timedelta(minutes=15),
        end_time=end + timedelta(minutes=15),
        meeting_link="https://meet.google.com/r2",
        interviewer_ids=[interviewer1.id],
        created_by_user_id=r1.id
    )

    assert len(warnings) > 0
    assert "already has an active interview" in warnings[0]


def test_reschedule_and_cancel_interview(session, phase6_setup):
    """Verifies interview rescheduling and cancellation with notification emission."""
    app1 = db.session.get(Application, phase6_setup["app1_id"])
    r1 = db.session.get(User, phase6_setup["r1_id"])
    start = datetime.now(timezone.utc) + timedelta(days=2)
    end = start + timedelta(hours=1)

    interview, _ = schedule_interview(
        application_id=app1.id,
        round_name="Initial Tech Call",
        interview_type="online",
        scheduled_at=start,
        end_time=end,
        meeting_link="https://meet.google.com/call",
        created_by_user_id=r1.id
    )

    # Reschedule to next day
    new_start = start + timedelta(days=1)
    new_end = end + timedelta(days=1)
    reschedule_interview(
        interview_id=interview.id,
        scheduled_at=new_start,
        end_time=new_end,
        round_name="Rescheduled Tech Call",
        updated_by_user_id=r1.id
    )

    refreshed = db.session.get(Interview, interview.id)
    assert refreshed.round_name == "Rescheduled Tech Call"
    sched_utc = refreshed.scheduled_at.replace(tzinfo=timezone.utc) if refreshed.scheduled_at.tzinfo is None else refreshed.scheduled_at
    assert sched_utc == new_start

    # Cancel interview
    cancel_interview(
        interview_id=interview.id,
        cancellation_reason="Requisition paused by executive leadership",
        cancelled_by_user_id=r1.id
    )
    assert refreshed.status == "cancelled"
    assert "paused" in refreshed.cancellation_reason

    # Candidate receives cancel notification
    cancel_notifs = Notification.query.filter_by(
        recipient_user_id=phase6_setup["cand1_id"],
        notification_type="interview_cancelled"
    ).all()
    assert len(cancel_notifs) == 1


def test_complete_and_noshow_status_updates(session, phase6_setup):
    """Verifies marking interview as completed or no-show."""
    app1 = db.session.get(Application, phase6_setup["app1_id"])
    r1 = db.session.get(User, phase6_setup["r1_id"])
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=1)

    interview, _ = schedule_interview(
        application_id=app1.id,
        round_name="Completed Round",
        interview_type="online",
        scheduled_at=start,
        end_time=end,
        meeting_link="https://meet.google.com/test",
        created_by_user_id=r1.id
    )

    update_interview_status(interview.id, "completed")
    assert db.session.get(Interview, interview.id).status == "completed"

    # Cannot cancel completed interview
    with pytest.raises(InterviewValidationError, match="already been completed"):
        cancel_interview(interview.id, "Attempt cancel")


# =========================================================================
# 2. Authorization Boundaries & Cross-Tenant Isolation
# =========================================================================

def test_unauthorized_recruiter_cannot_schedule_or_access_foreign_interviews(client, session, phase6_setup):
    """Recruiter in Beta Ltd cannot schedule or access interviews for Acme Corp job."""
    app1_id = phase6_setup["app1_id"]

    # Login as r2 (Beta Ltd)
    client.post("/auth/login", data={"email": "recruiter2@beta.com", "password": "SecurePass123!"}, follow_redirects=True)

    # Attempt to open scheduling page for Acme application
    resp = client.get(f"/interviews/schedule/{app1_id}")
    assert resp.status_code == 403


def test_candidate_sees_own_interview_cannot_see_others(client, session, phase6_setup):
    """Candidate can only view their own interviews and gets 403 for other candidates' interviews."""
    app1 = db.session.get(Application, phase6_setup["app1_id"])
    r1 = db.session.get(User, phase6_setup["r1_id"])
    start = datetime.now(timezone.utc) + timedelta(days=2)
    end = start + timedelta(hours=1)

    interview, _ = schedule_interview(
        application_id=app1.id,
        round_name="Charlie's Round",
        interview_type="online",
        scheduled_at=start,
        end_time=end,
        meeting_link="https://meet.google.com/charlie",
        created_by_user_id=r1.id
    )

    # Login as Charlie (cand1) -> Success
    client.post("/auth/login", data={"email": "charlie@candidate.com", "password": "SecurePass123!"}, follow_redirects=True)
    resp = client.get(f"/interviews/{interview.id}")
    assert resp.status_code == 200
    assert b"Charlie" in resp.data
    assert b"Scheduled" in resp.data

    # Login as Diana (cand2) -> Forbidden 403
    client.get("/auth/logout", follow_redirects=True)
    client.post("/auth/login", data={"email": "diana@candidate.com", "password": "SecurePass123!"}, follow_redirects=True)
    resp2 = client.get(f"/interviews/{interview.id}")
    assert resp2.status_code == 403


# =========================================================================
# 3. Interview Feedback Rubric & Privacy
# =========================================================================

def test_interview_feedback_submission_and_rating_validation(session, phase6_setup):
    """Validates rubric ratings (1-5), recommendation, and average calculation."""
    app1 = db.session.get(Application, phase6_setup["app1_id"])
    r1 = db.session.get(User, phase6_setup["r1_id"])
    interviewer1 = db.session.get(User, phase6_setup["interviewer1_id"])
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=1)

    interview, _ = schedule_interview(
        application_id=app1.id,
        round_name="Technical Architecture",
        interview_type="online",
        scheduled_at=start,
        end_time=end,
        meeting_link="https://meet.google.com/arch",
        interviewer_ids=[interviewer1.id],
        created_by_user_id=r1.id
    )

    # Invalid rating: 6 (must be 1-5)
    with pytest.raises(FeedbackValidationError, match="between 1 and 5"):
        submit_or_update_feedback(
            interview_id=interview.id,
            interviewer_user_id=interviewer1.id,
            technical_rating=6
        )

    # Valid submission
    feedback = submit_or_update_feedback(
        interview_id=interview.id,
        interviewer_user_id=interviewer1.id,
        technical_rating=5,
        problem_solving_rating=4,
        communication_rating=4,
        role_relevant_rating=5,
        strengths="Excellent understanding of REST APIs and PostgreSQL indexing.",
        areas_for_improvement="Could deepen knowledge on Kubernetes ingress controllers.",
        notes="Strong candidate for Senior backend role. Recommend hiring.",
        overall_recommendation="strong_hire",
        is_candidate_facing=True,
        candidate_feedback="Outstanding technical depth; strengthen container orchestration."
    )

    assert feedback.id is not None
    assert feedback.overall_score == 4.5  # Mean of [5, 4, 4, 5]
    assert feedback.overall_recommendation == "strong_hire"

    # Check candidate visibility filtering
    cand_visible = get_candidate_visible_feedback(interview.id)
    assert len(cand_visible) == 1
    assert "Outstanding technical depth" in cand_visible[0]["candidate_feedback"]
    # Ensure private ratings & notes are NOT in candidate dictionary
    assert "overall_score" not in cand_visible[0]
    assert "notes" not in cand_visible[0]


def test_candidate_cannot_access_internal_feedback_view(client, session, phase6_setup):
    """Candidates are strictly blocked from internal feedback review endpoints (HTTP 403)."""
    app1 = db.session.get(Application, phase6_setup["app1_id"])
    r1 = db.session.get(User, phase6_setup["r1_id"])
    interviewer1 = db.session.get(User, phase6_setup["interviewer1_id"])
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=1)

    interview, _ = schedule_interview(
        application_id=app1.id,
        round_name="Coding Round",
        interview_type="online",
        scheduled_at=start,
        end_time=end,
        meeting_link="https://meet.google.com/code",
        interviewer_ids=[interviewer1.id],
        created_by_user_id=r1.id
    )

    fb = submit_or_update_feedback(
        interview_id=interview.id,
        interviewer_user_id=interviewer1.id,
        technical_rating=4,
        notes="Confidential: Expects $140k base."
    )

    client.post("/auth/login", data={"email": "charlie@candidate.com", "password": "SecurePass123!"}, follow_redirects=True)

    # Candidate attempts to access internal feedback details
    resp = client.get(f"/interviews/{interview.id}/feedback/{fb.id}")
    assert resp.status_code == 403


# =========================================================================
# 4. Hiring Pipeline & State Transitions
# =========================================================================

def test_valid_pipeline_stage_transitions(session, phase6_setup):
    """Verifies allowed transitions: submitted -> under_review -> shortlisted -> interview -> interview_completed -> offered -> hired."""
    app1 = db.session.get(Application, phase6_setup["app1_id"])
    r1 = db.session.get(User, phase6_setup["r1_id"])

    # 1. submitted -> under_review
    transition_application_stage(app1.id, "under_review", r1, reason="Screening resume credentials")
    assert app1.status == "under_review"

    # 2. under_review -> shortlisted
    transition_application_stage(app1.id, "shortlisted", r1, reason="Shortlisted for technical interviews")
    assert app1.status == "shortlisted"

    # 3. shortlisted -> interview
    transition_application_stage(app1.id, "interview", r1, reason="Invited to technical round")
    assert app1.status == "interview"

    # 4. interview -> interview_completed
    transition_application_stage(app1.id, "interview_completed", r1, reason="All rounds completed")
    assert app1.status == "interview_completed"

    # 5. interview_completed -> offered
    transition_application_stage(app1.id, "offered", r1, reason="Formal offer approved")
    assert app1.status == "offered"

    # 6. offered -> hired
    transition_application_stage(app1.id, "hired", r1, reason="Offer accepted by candidate")
    assert app1.status == "hired"

    # Check ApplicationStageHistory records
    history_records = ApplicationStageHistory.query.filter_by(application_id=app1.id).all()
    assert len(history_records) == 6


def test_invalid_stage_transition_rejected(session, phase6_setup):
    """Rejects illegal jumps (e.g. submitted directly to hired or offered)."""
    app1 = db.session.get(Application, phase6_setup["app1_id"])
    r1 = db.session.get(User, phase6_setup["r1_id"])

    assert app1.status == "submitted"

    # Cannot jump from submitted to hired
    with pytest.raises(StageTransitionError, match="Invalid stage transition"):
        transition_application_stage(app1.id, "hired", r1)


def test_candidate_cannot_change_pipeline_stage_except_withdraw(session, phase6_setup):
    """Candidates cannot self-promote to shortlisted, offered, or hired."""
    app1 = db.session.get(Application, phase6_setup["app1_id"])
    cand1 = db.session.get(User, phase6_setup["cand1_id"])

    # Candidate attempts to self-shortlist
    with pytest.raises(StageTransitionError, match="only permitted to withdraw"):
        transition_application_stage(app1.id, "shortlisted", cand1)

    # Candidate withdraws own application -> Allowed
    transition_application_stage(app1.id, "withdrawn", cand1, reason="Accepted another offer")
    assert app1.status == "withdrawn"


# =========================================================================
# 5. Notifications & User Isolation
# =========================================================================

def test_notification_workflow_and_user_isolation(client, session, phase6_setup):
    """Verifies notification center, unread counters, mark as read, and user isolation."""
    cand1 = db.session.get(User, phase6_setup["cand1_id"])
    cand2 = db.session.get(User, phase6_setup["cand2_id"])

    from app.services.notification_service import create_notification
    n1 = create_notification(cand1.id, "test_notif", "Alert 1", "Message 1")
    n2 = create_notification(cand1.id, "test_notif", "Alert 2", "Message 2")
    n_diana = create_notification(cand2.id, "test_notif", "Diana Alert", "Message for Diana")
    db.session.commit()

    assert get_unread_count(cand1.id) == 2
    assert get_unread_count(cand2.id) == 1

    # Cand1 marks n1 as read
    mark_notification_as_read(n1.id, cand1.id)
    assert get_unread_count(cand1.id) == 1

    # Cand1 cannot mark Diana's notification as read (returns False)
    assert mark_notification_as_read(n_diana.id, cand1.id) is False

    # Cand1 marks all as read
    mark_all_notifications_as_read(cand1.id)
    assert get_unread_count(cand1.id) == 0
    assert get_unread_count(cand2.id) == 1  # Diana's remains unread
