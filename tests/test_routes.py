from fastapi.testclient import TestClient

from lead_generation_app.backend.app import app
from lead_generation_app.backend.auth import create_access_token

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "lead-engine"


def test_login_success():
    response = client.post("/api/v1/auth/login", json={"password": "leadengine123"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_failure():
    response = client.post("/api/v1/auth/login", json={"password": "wrong"})
    assert response.status_code == 401


def test_unauthorized_access():
    response = client.get("/api/v1/jobs")
    assert response.status_code == 401


def test_authorized_access():
    token = create_access_token({"sub": "admin"})
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/system/info", headers=headers)
    assert response.status_code != 401


def test_campaigns_requires_auth():
    response = client.get("/api/v1/campaigns")
    assert response.status_code == 401


def test_dashboard_metrics_requires_auth():
    response = client.get("/api/v1/dashboard/metrics")
    assert response.status_code == 401


def test_companies_requires_auth():
    response = client.get("/api/v1/companies")
    assert response.status_code == 401


def test_leads_requires_auth():
    response = client.get("/api/v1/leads")
    assert response.status_code == 401


def test_invalid_token():
    headers = {"Authorization": "Bearer invalid_token_here"}
    response = client.get("/api/v1/jobs", headers=headers)
    assert response.status_code == 401


def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200


def test_system_info_requires_auth():
    response = client.get("/api/v1/system/info")
    assert response.status_code == 401


def test_system_info_with_token():
    token = create_access_token({"sub": "admin"})
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/system/info", headers=headers)
    assert response.status_code != 401
    data = response.json()
    assert data["version"] == "4.0.0"


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200


def test_leads_search_requires_auth():
    response = client.get("/api/v1/leads/search")
    assert response.status_code == 401


def test_location_zipcodes_requires_auth():
    response = client.get("/api/v1/locations/zipcodes?state=CA")
    assert response.status_code == 401


def test_credits_requires_auth():
    response = client.get("/api/v1/dashboard/credits")
    assert response.status_code == 401
