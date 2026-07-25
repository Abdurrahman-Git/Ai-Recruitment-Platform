"""
WHAT THIS FILE DOES:
────────────────────
Tests for the AI Recruitment Platform using pytest.

SKILL LEARNED — Testing in Python:
  Testing is what separates a hobby project from a professional one.
  Recruiters LOVE seeing test coverage in portfolios.

  pytest: The standard Python testing framework
    - Functions named test_xxx() are automatically discovered + run
    - 'assert' statements check correctness
    - Fixtures (the @pytest.fixture functions) set up test environments

SKILL LEARNED — Mocking:
  We can't call the real OpenAI API in tests (costs money, requires internet,
  is slow, gives non-deterministic results). Instead we "mock" it:
  
  unittest.mock.patch() replaces the real function with a fake one
  that returns a predefined value. Tests run fast and cost nothing.

  This is a critical professional skill — knowing how to test code that
  depends on external services.

SKILL LEARNED — Test Database:
  We use a separate in-memory SQLite database for tests.
  Each test gets a fresh, clean database. This prevents test pollution
  (one test's data affecting another test's results).

HOW TO RUN TESTS:
  cd ai-recruitment-platform
  pytest tests/ -v           # verbose output
  pytest tests/ -v --tb=short  # shorter error traces
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# We need to set a fake API key before importing the app
# Otherwise the settings validation fails
import os
os.environ["GEMINI_API_KEY"] = "fake-gemini-key-for-testing"

from main import app
from app.core.database import Base, get_db

# ── Test Database Setup ───────────────────────────────────────────────────────
# Use a fresh in-memory SQLite database for each test run
TEST_DATABASE_URL = "sqlite:///./test_recruitment.db"

test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """Replace the real DB session with a test DB session."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override the database dependency for all tests
app.dependency_overrides[get_db] = override_get_db

# Create test client — simulates real HTTP requests without running a server
client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def setup_database():
    """
    This fixture runs BEFORE every test.
    autouse=True means it runs automatically for every test in this file.
    
    It creates all tables, runs the test, then drops all tables.
    This ensures complete test isolation.
    """
    Base.metadata.create_all(bind=test_engine)
    yield  # Test runs here
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def sample_candidate():
    """Create a candidate for use in multiple tests."""
    response = client.post("/api/v1/candidates/", json={
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "phone": "+1-555-0100",
        "resume_text": """
        Alice Johnson - Senior Software Engineer
        
        Experience: 5 years at TechCorp as Python Developer.
        Built microservices using FastAPI, Docker, Kubernetes.
        Led team of 4 engineers. Managed PostgreSQL databases.
        
        Skills: Python, FastAPI, SQL, Docker, Kubernetes, REST APIs, Git
        
        Education: B.S. Computer Science, MIT, 2018
        """
    })
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def sample_job():
    """Create a job posting for use in multiple tests."""
    response = client.post("/api/v1/jobs/", json={
        "title": "Senior Python Developer",
        "company": "DataTech Inc",
        "description": "We need an experienced Python developer to build data pipelines.",
        "required_skills": "Python,FastAPI,SQL,Docker",
        "min_experience_years": 3.0,
        "location": "Remote",
        "is_remote": True
    })
    assert response.status_code == 201
    return response.json()


# ── Candidate Tests ───────────────────────────────────────────────────────────

class TestCandidateEndpoints:
    """Tests for candidate CRUD operations."""

    def test_create_candidate_success(self):
        """Test creating a new candidate."""
        response = client.post("/api/v1/candidates/", json={
            "name": "Bob Smith",
            "email": "bob@example.com",
            "resume_text": "Experienced developer..."
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Bob Smith"
        assert data["email"] == "bob@example.com"
        assert "id" in data
        assert "created_at" in data

    def test_create_candidate_invalid_email(self):
        """Test that invalid email is rejected with 422."""
        response = client.post("/api/v1/candidates/", json={
            "name": "Bad User",
            "email": "not-an-email"  # Invalid!
        })
        # Pydantic validates email format automatically
        assert response.status_code == 422

    def test_create_duplicate_email_fails(self, sample_candidate):
        """Test that duplicate emails are rejected."""
        response = client.post("/api/v1/candidates/", json={
            "name": "Alice Clone",
            "email": "alice@example.com"  # Already used by sample_candidate
        })
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_get_candidate_by_id(self, sample_candidate):
        """Test fetching a specific candidate."""
        candidate_id = sample_candidate["id"]
        response = client.get(f"/api/v1/candidates/{candidate_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Alice Johnson"

    def test_get_nonexistent_candidate_returns_404(self):
        """Test that missing candidates return 404."""
        response = client.get("/api/v1/candidates/99999")
        assert response.status_code == 404

    def test_list_candidates(self, sample_candidate):
        """Test listing candidates."""
        response = client.get("/api/v1/candidates/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1


class TestJobEndpoints:
    """Tests for job posting operations."""

    def test_create_job_posting(self):
        """Test creating a job posting."""
        response = client.post("/api/v1/jobs/", json={
            "title": "Data Engineer",
            "company": "AnalyticsCo",
            "description": "Build data pipelines and ETL processes.",
            "required_skills": "Python,Spark,SQL",
            "min_experience_years": 2.0
        })
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Data Engineer"
        assert data["ai_generated"] == False

    def test_list_active_jobs(self, sample_job):
        """Test that inactive jobs are filtered out."""
        job_id = sample_job["id"]
        # Deactivate the job
        client.patch(f"/api/v1/jobs/{job_id}/deactivate")

        # Should not appear in active-only list
        response = client.get("/api/v1/jobs/?active_only=true")
        assert response.status_code == 200
        active_ids = [j["id"] for j in response.json()]
        assert job_id not in active_ids

    def test_get_job_by_id(self, sample_job):
        """Test getting a specific job."""
        job_id = sample_job["id"]
        response = client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["company"] == "DataTech Inc"


class TestAIFeatures:
    """
    Tests for AI-powered endpoints.
    
    IMPORTANT: These tests MOCK the LLM calls.
    The mock returns a predefined response, so:
    - Tests are fast (no HTTP calls)
    - Tests are free (no API usage)
    - Tests are deterministic (same result every run)
    """

    @patch("app.services.llm_service.llm_service.analyze_resume")
    def test_resume_analysis(self, mock_analyze, sample_candidate):
        """Test that resume analysis calls LLM and saves results."""
        # Define what the mocked LLM should return
        mock_analyze.return_value = {
            "skills": ["Python", "FastAPI", "SQL", "Docker"],
            "experience_years": 5.0,
            "education_level": "Bachelor's",
            "strengths": ["Strong Python skills", "Leadership experience"],
            "areas_for_improvement": ["Could add cloud certifications"],
            "overall_score": 82,
            "summary": "Experienced Python developer with team leadership background.",
            "career_level": "Senior",
            "key_technologies": ["Python", "FastAPI", "PostgreSQL"],
            "industry_domains": ["SaaS", "FinTech"]
        }

        response = client.post("/api/v1/candidates/analyze-resume", json={
            "candidate_id": sample_candidate["id"],
            "force_reanalyze": False
        })

        assert response.status_code == 200
        data = response.json()
        
        # Verify the LLM was called once
        mock_analyze.assert_called_once()
        
        # Verify response structure
        assert data["overall_score"] == 82
        assert "Python" in data["extracted_skills"]
        assert data["experience_years"] == 5.0
        assert len(data["strengths"]) > 0

    @patch("app.services.llm_service.llm_service.generate_job_description")
    def test_jd_generation(self, mock_gen_jd):
        """Test AI job description generation."""
        mock_gen_jd.return_value = """
        Senior Python Developer at TechCorp
        
        We're looking for a seasoned Python developer to join our growing team...
        
        Responsibilities:
        - Build scalable APIs using FastAPI
        - Design SQL database schemas
        - Lead code reviews
        
        Requirements:
        - 5+ years Python experience
        - Strong SQL skills
        - FastAPI experience preferred
        """

        response = client.post("/api/v1/jobs/generate-jd", json={
            "job_title": "Senior Python Developer",
            "company_name": "TechCorp",
            "required_skills": ["Python", "FastAPI", "SQL"],
            "experience_years": 5,
            "is_remote": True,
            "save_to_db": True
        })

        assert response.status_code == 200
        data = response.json()
        assert data["job_title"] == "Senior Python Developer"
        assert len(data["generated_description"]) > 50
        assert data["job_posting_id"] is not None  # Was saved to DB

        mock_gen_jd.assert_called_once()

    @patch("app.services.llm_service.llm_service.match_candidate_to_job")
    def test_candidate_job_matching(self, mock_match, sample_candidate, sample_job):
        """Test the core matching feature."""
        mock_match.return_value = {
            "overall_match_score": 88,
            "skills_score": 90,
            "experience_score": 85,
            "education_score": 90,
            "match_reasoning": "Alice has strong Python skills and 5 years experience matching the 3-year requirement. All core required skills are present.",
            "missing_skills": [],
            "matching_skills": ["Python", "FastAPI", "SQL", "Docker"],
            "recommendation": "Strong Match",
            "hiring_notes": "Top candidate, recommend fast-tracking interview"
        }

        response = client.post("/api/v1/match", json={
            "candidate_id": sample_candidate["id"],
            "job_id": sample_job["id"]
        })

        assert response.status_code == 200
        data = response.json()
        assert data["match_score"] == 88
        assert data["skills_score"] == 90
        assert len(data["missing_skills"]) == 0

    def test_analytics_summary(self, sample_candidate, sample_job):
        """Test the analytics endpoint returns correct counts."""
        response = client.get("/api/v1/analytics/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_candidates"] >= 1
        assert data["total_jobs"] >= 1
        assert "top_candidate_skills" in data


# ── Run this file directly to execute all tests ───────────────────────────────
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
