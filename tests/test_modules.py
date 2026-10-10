"""
Automated Tests for Module Blueprint Routes.
Ensures all 10 architectural modules mount cleanly and return HTTP 200.
"""


def test_all_module_routes(client, recruiter_user):
    """Verify that all core functional routes respond cleanly with HTTP 200."""
    # Authenticate first so protected routes like /applications/ respond cleanly
    client.post("/auth/login", data={"email": recruiter_user.email, "password": "RecruiterSecret123!"})

    routes = [
        "/",
        "/dashboard",
        "/jobs/",
        "/candidates/",
        "/applications/",
        "/resumes/",
        "/resumes/upload",
        "/matching/",
        "/interviews/",
        "/reports/",
    ]
    for route in routes:
        response = client.get(route)
        assert response.status_code == 200, f"Failed on route {route}"


def test_job_creation_and_listing(client, recruiter_user):
    """Test authenticated job creation flow."""
    # Log in first
    client.post("/auth/login", data={"email": recruiter_user.email, "password": "RecruiterSecret123!"})

    job_data = {
        "title": "Senior AI Systems Engineer",
        "department": "Engineering",
        "location": "Remote",
        "workplace_type": "remote",
        "employment_type": "full-time",
        "minimum_experience_years": "4.5",
        "required_skills": "Python, PyTorch, LangChain, MySQL",
        "description": "Architect and scale resilient AI pipeline systems.",
        "salary_currency": "USD",
        "status": "published"
    }
    response = client.post("/jobs/new", data=job_data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Senior AI Systems Engineer" in response.data

    # Check that job listing contains the newly created record
    res_list = client.get("/jobs/")
    assert b"Senior AI Systems Engineer" in res_list.data
    assert b"Engineering" in res_list.data
