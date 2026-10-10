"""
Role-Based Access Control and Cross-Organization Isolation Tests.
Tests:
- Candidate cannot access recruiter dashboard or organization settings
- Recruiter cannot access platform admin pages
- Recruiter cannot access another organization's settings
- Platform admin can access admin dashboard
- Unauthenticated requests to protected endpoints redirect to login
"""
from app.models.models import Organization, OrganizationMembership


def test_unauthenticated_protected_route_redirects_to_login(client):
    """Unauthenticated users must be redirected to login when visiting protected pages."""
    res_cand = client.get("/candidates/dashboard")
    assert res_cand.status_code == 302
    assert "/auth/login" in res_cand.headers["Location"]

    res_rec = client.get("/recruiters/dashboard")
    assert res_rec.status_code == 302
    assert "/auth/login" in res_rec.headers["Location"]

    res_admin = client.get("/admin/")
    assert res_admin.status_code == 302
    assert "/auth/login" in res_admin.headers["Location"]


def test_candidate_cannot_access_recruiter_pages(client, candidate_user):
    """Candidate attempting to access recruiter dashboard receives 403 Forbidden."""
    client.post("/auth/login", data={"email": candidate_user.email, "password": "CandidateSecret123!"})
    
    response = client.get("/recruiters/dashboard")
    assert response.status_code == 403
    assert b"403 - Access Forbidden" in response.data


def test_candidate_cannot_access_admin_pages(client, candidate_user):
    """Candidate attempting to access platform administration receives 403 Forbidden."""
    client.post("/auth/login", data={"email": candidate_user.email, "password": "CandidateSecret123!"})
    
    response = client.get("/admin/")
    assert response.status_code == 403


def test_recruiter_cannot_access_admin_pages(client, recruiter_user):
    """Recruiter attempting to access platform administration receives 403 Forbidden."""
    client.post("/auth/login", data={"email": recruiter_user.email, "password": "RecruiterSecret123!"})
    
    response = client.get("/admin/")
    assert response.status_code == 403


def test_recruiter_cannot_access_other_organization(client, recruiter_user, session):
    """Recruiter cannot access an organization where they do not hold active membership."""
    # Create an unrelated second organization
    other_org = Organization(
        name="Other Enterprise Inc.",
        slug="other-enterprise-inc",
        is_active=True
    )
    session.add(other_org)
    session.commit()

    # Log in as Morgan Recruiter (who only belongs to Acme Corp)
    client.post("/auth/login", data={"email": recruiter_user.email, "password": "RecruiterSecret123!"})

    # Access own org (should succeed 200)
    my_membership = recruiter_user.memberships.first()
    res_own = client.get(f"/recruiters/organization/{my_membership.organization_id}")
    assert res_own.status_code == 200
    assert b"Acme Corp" in res_own.data

    # Access other org (must be rejected 403)
    res_other = client.get(f"/recruiters/organization/{other_org.id}")
    assert res_other.status_code == 403


def test_platform_admin_can_access_admin_dashboard(client, platform_admin_user):
    """Platform administrator successfully accesses admin panel."""
    client.post("/auth/login", data={"email": platform_admin_user.email, "password": "AdminMasterKey123!"})
    
    response = client.get("/admin/")
    assert response.status_code == 200
    assert b"Platform Administration" in response.data
