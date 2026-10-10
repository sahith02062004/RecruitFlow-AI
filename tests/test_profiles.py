"""
Candidate & Recruiter Profile Management Tests.
Tests:
- Candidate profile updates and validations
- Recruiter profile updates
- Account settings and password change verification
"""
from app.models.models import CandidateProfile, RecruiterProfile


def test_candidate_profile_update(client, candidate_user, session):
    """Candidate can update their own profile fields."""
    client.post("/auth/login", data={"email": candidate_user.email, "password": "CandidateSecret123!"})

    update_data = {
        "headline": "Lead Full Stack Architect",
        "location": "San Francisco, CA",
        "years_of_experience": "7.5",
        "phone": "+1 (555) 123-4567",
        "skills": "Python, Flask, Docker, Kubernetes, MySQL",
        "professional_summary": "10 years building distributed applications.",
        "linkedin_url": "https://linkedin.com/in/alex",
        "github_url": "https://github.com/alex",
        "portfolio_url": "https://alex.dev"
    }
    response = client.post("/candidates/profile", data=update_data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Your profile has been updated successfully" in response.data

    # Check DB
    profile = CandidateProfile.query.filter_by(user_id=candidate_user.id).first()
    assert profile.headline == "Lead Full Stack Architect"
    assert profile.years_of_experience == 7.5
    assert profile.location == "San Francisco, CA"


def test_recruiter_profile_update(client, recruiter_user, session):
    """Recruiter can update their profile information."""
    client.post("/auth/login", data={"email": recruiter_user.email, "password": "RecruiterSecret123!"})

    update_data = {
        "job_title": "Director of Technical Talent",
        "department": "Engineering Recruiting",
        "company_name": "Acme Global Enterprise",
        "phone": "+1 (555) 987-6543"
    }
    response = client.post("/recruiters/profile", data=update_data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Your recruiter profile has been updated" in response.data

    profile = RecruiterProfile.query.filter_by(user_id=recruiter_user.id).first()
    assert profile.job_title == "Director of Technical Talent"
    assert profile.department == "Engineering Recruiting"


def test_account_password_change(client, candidate_user, session):
    """Authenticated user can change their password through settings."""
    client.post("/auth/login", data={"email": candidate_user.email, "password": "CandidateSecret123!"})

    change_data = {
        "pwd-current_password": "CandidateSecret123!",
        "pwd-new_password": "UpdatedPassword456!",
        "pwd-confirm_new_password": "UpdatedPassword456!",
        "pwd-submit": "Update Password"
    }
    response = client.post("/auth/settings", data=change_data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Your password has been changed successfully" in response.data

    # Verify old password fails and new password works
    assert candidate_user.check_password("CandidateSecret123!") is False
    assert candidate_user.check_password("UpdatedPassword456!") is True
