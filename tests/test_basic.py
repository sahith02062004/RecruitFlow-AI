"""
Automated Tests for Health-Check and Core Application Routes.
"""
import json


def test_health_check_endpoint(client):
    """Test health check returns UP with 200 HTTP status code."""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert data["status"] == "UP"
    assert data["service"] == "RecruitFlow AI"
    assert data["database"]["status"] == "healthy"
    assert "sqlite" in data["database"]["engine"].lower()


def test_landing_page(client):
    """Test landing page renders properly with key enterprise value propositions."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"RecruitFlow" in response.data
    assert b"AI-Powered Resume Screening" in response.data


def test_dashboard_empty_state(client, session):
    """Test dashboard correctly displays zero-states without mock records."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"Recruitment Overview" in response.data
    assert b"No job requisitions created yet" in response.data
    assert b"No active applications received" in response.data


def test_error_handler_404_html(client):
    """Test 404 handler returns customized enterprise error page."""
    response = client.get("/nonexistent-endpoint-404")
    assert response.status_code == 404
    assert b"404 - Page Not Found" in response.data


def test_error_handler_404_json(client):
    """Test API requests receive structured JSON error payloads."""
    response = client.get("/api/v1/invalid-route", headers={"Accept": "application/json"})
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data["status"] == "error"
    assert data["code"] == 404
