import pytest
from fastapi.testclient import TestClient
from app.main import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "ScoreSight API"

def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_list_exam_types(client):
    """Test listing exam types."""
    response = client.get("/api/v1/exams/types/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_list_exams(client):
    """Test listing exams."""
    response = client.get("/api/v1/exams/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_create_exam_type(client):
    """Test creating an exam type."""
    exam_type_data = {
        "name": "QUIZ",
        "description": "Quick quiz assessment"
    }
    response = client.post("/api/v1/exams/types/", json=exam_type_data)
    assert response.status_code == 200
    assert response.json()["name"] == "QUIZ"

def test_pdf_upload_without_file(client):
    """Test PDF upload endpoint without file."""
    response = client.post("/api/v1/exams/uploads/pdf/")
    assert response.status_code == 422  # Validation error

def test_job_status_invalid_id(client):
    """Test job status with invalid ID."""
    response = client.get("/api/v1/exams/jobs/invalid-job-id")
    assert response.status_code == 500  # Should handle gracefully

def test_list_jobs(client):
    """Test listing all jobs."""
    response = client.get("/api/v1/exams/jobs/")
    assert response.status_code == 200
    assert "jobs" in response.json()
    assert "total" in response.json()

def test_list_workers(client):
    """Test listing Celery workers."""
    response = client.get("/api/v1/exams/workers/")
    assert response.status_code == 200
    assert "workers" in response.json()
