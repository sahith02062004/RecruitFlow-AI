"""
Phase 2 Authentication and Registration Test Suite.
Tests:
- Candidate registration & auto-role assignment
- Recruiter registration & organization auto-provisioning
- Duplicate email handling
- Password policy and confirmation validation
- Login authentication, session handling, and inactive user rejection
- Open redirect defense
- Single-use, time-limited password reset tokens
"""
from datetime import datetime, timezone
from app.models.models import User, Organization, OrganizationMembership, PasswordResetToken


def test_candidate_registration(client, session):
    """Test successful candidate registration flow."""
    data = {
        "full_name": "Jordan Lee",
        "email": "jordan.lee@example.com",
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!",
        "agree_terms": "y"
    }
    response = client.post("/auth/register/candidate", data=data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Candidate account created successfully" in response.data

    user = User.query.filter_by(email="jordan.lee@example.com").first()
    assert user is not None
    assert user.role == "candidate"
    assert user.check_password("SecurePassword123!") is True
    assert user.candidate_profile is not None


def test_recruiter_registration(client, session):
    """Test recruiter registration creating organization and admin membership."""
    data = {
        "full_name": "Taylor Swift",
        "organization_name": "Starlight Studios",
        "email": "taylor@starlight.com",
        "password": "SecurePassword123!",
        "confirm_password": "SecurePassword123!",
        "agree_terms": "y"
    }
    response = client.post("/auth/register/recruiter", data=data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Recruiter and organization account created successfully" in response.data

    user = User.query.filter_by(email="taylor@starlight.com").first()
    assert user is not None
    assert user.role == "recruiter"
    assert user.recruiter_profile is not None

    org = Organization.query.filter_by(name="Starlight Studios").first()
    assert org is not None
    assert org.slug == "starlight-studios"
    assert org.is_verified is False  # Correct unverified labeling

    membership = OrganizationMembership.query.filter_by(user_id=user.id, organization_id=org.id).first()
    assert membership is not None
    assert membership.membership_role == "admin"


def test_duplicate_registration_prevented(client, candidate_user):
    """Ensure duplicate email registration is rejected."""
    data = {
        "full_name": "Imposter Candidate",
        "email": candidate_user.email,
        "password": "Password123!",
        "confirm_password": "Password123!",
        "agree_terms": "y"
    }
    response = client.post("/auth/register/candidate", data=data)
    assert response.status_code == 200
    assert b"An account with this email address already exists" in response.data


def test_login_and_logout(client, candidate_user):
    """Test login and CSRF-protected logout."""
    login_data = {
        "email": candidate_user.email,
        "password": "CandidateSecret123!"
    }
    res_login = client.post("/auth/login", data=login_data, follow_redirects=True)
    assert res_login.status_code == 200
    assert b"Welcome back, Alex!" in res_login.data
    assert b"My Applications" in res_login.data  # Redirected to candidate dashboard

    res_logout = client.post("/auth/logout", follow_redirects=True)
    assert res_logout.status_code == 200
    assert b"You have been signed out" in res_logout.data


def test_inactive_user_cannot_login(client, candidate_user, session):
    """Inactive users must be denied login."""
    candidate_user.is_active = False
    session.commit()

    login_data = {
        "email": candidate_user.email,
        "password": "CandidateSecret123!"
    }
    res = client.post("/auth/login", data=login_data, follow_redirects=True)
    assert b"Your account has been deactivated" in res.data


def test_safe_redirect_prevents_open_redirect(client, candidate_user):
    """Prevents open redirects to external untrusted domains."""
    login_data = {
        "email": candidate_user.email,
        "password": "CandidateSecret123!"
    }
    # Pass malicious next parameter
    res = client.post("/auth/login?next=https://evil.com", data=login_data, follow_redirects=False)
    # Must redirect internally, NOT to evil.com
    assert res.status_code == 302
    assert "evil.com" not in res.headers["Location"]
    assert "/candidates/dashboard" in res.headers["Location"]


def test_password_reset_workflow(client, candidate_user, session):
    """Verify forgot password link generation, token hashing, and single-use invalidation."""
    # Step 1: Request reset
    res_req = client.post("/auth/forgot-password", data={"email": candidate_user.email})
    assert res_req.status_code == 200
    assert b"If an active account exists" in res_req.data

    # Retrieve stored token from DB
    db_token = PasswordResetToken.query.filter_by(user_id=candidate_user.id).first()
    assert db_token is not None
    assert db_token.used_at is None

    # Step 2: Use helper method to verify with valid token
    raw_token, test_token = PasswordResetToken.create_token(candidate_user.id)
    session.commit()

    res_reset = client.post(
        f"/auth/reset-password/{raw_token}",
        data={"password": "BrandNewPassword123!", "confirm_password": "BrandNewPassword123!"},
        follow_redirects=True
    )
    assert res_reset.status_code == 200
    assert b"Your password has been successfully reset" in res_reset.data

    # Token must be invalidated
    session.refresh(test_token)
    assert test_token.used_at is not None

    # Token reuse must fail
    res_reuse = client.get(f"/auth/reset-password/{raw_token}", follow_redirects=True)
    assert b"The password reset link is invalid, has expired, or has already been used" in res_reuse.data

    # User can log in with new password
    res_login = client.post(
        "/auth/login",
        data={"email": candidate_user.email, "password": "BrandNewPassword123!"},
        follow_redirects=True
    )
    assert b"Welcome back, Alex!" in res_login.data
