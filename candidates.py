"""
WHAT THIS FILE DOES:
────────────────────
FastAPI route handlers for candidate management and resume analysis.

SKILL LEARNED — FastAPI Routes:
  A "route" maps an HTTP method + URL path to a Python function.
  
  @router.post("/candidates")      → handles POST /api/v1/candidates
  @router.get("/candidates/{id}")  → handles GET /api/v1/candidates/5
  
  FastAPI does magic with the function signature:
  - Parameters in the path (like {id})? → extract from URL
  - Annotated as a Pydantic schema? → parse from request body + validate
  - Annotated as Depends(get_db)? → call the dependency and inject result
  - Return type annotated? → serialize to JSON automatically

SKILL LEARNED — HTTP Status Codes:
  200 OK         → success (GET, successful PUT)
  201 Created    → new resource created (POST)
  400 Bad Request → client sent invalid data
  404 Not Found  → resource doesn't exist
  422 Unprocessable → Pydantic validation failed (FastAPI automatic)
  500 Server Error → something crashed on our end

SKILL LEARNED — Dependency Injection:
  db: Session = Depends(get_db) → FastAPI calls get_db(), passes the session to us.
  FastAPI's DI system manages lifecycle (open → inject → close after request).
  This is the professional way to share resources like DB connections.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import json

from app.core.database import get_db
from app.models.models import Candidate, ResumeAnalysis
from app.schemas.schemas import (
    CandidateCreate, CandidateResponse,
    ResumeAnalysisRequest, ResumeAnalysisResponse
)
from app.services.llm_service import llm_service

# APIRouter is like a mini-app for a subset of routes
# prefix="/candidates" means all routes here start with /candidates
router = APIRouter(prefix="/candidates", tags=["Candidates"])


# ─── CREATE CANDIDATE ──────────────────────────────────────────────────────────

@router.post("/", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
def create_candidate(candidate_data: CandidateCreate, db: Session = Depends(get_db)):
    """
    Create a new candidate profile.
    
    HOW FASTAPI HANDLES THIS:
    1. Receives POST body as JSON
    2. Validates against CandidateCreate schema (wrong types → 422 auto)
    3. Calls this function with a validated Python object
    4. We save to DB and return CandidateResponse
    5. FastAPI serializes the return value to JSON

    WHAT 'db' IS:
    A SQLAlchemy Session. Think of it as a "transaction context" —
    changes you make inside it aren't saved until you call db.commit().
    """
    # Check if email already exists — business logic validation
    existing = db.query(Candidate).filter(Candidate.email == candidate_data.email).first()
    if existing:
        # HTTPException becomes a proper HTTP error response automatically
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Candidate with email {candidate_data.email} already exists"
        )

    # Create the SQLAlchemy model instance (not saved yet)
    new_candidate = Candidate(
        name=candidate_data.name,
        email=candidate_data.email,
        phone=candidate_data.phone,
        resume_text=candidate_data.resume_text
    )

    db.add(new_candidate)    # Stage the INSERT
    db.commit()              # Execute the INSERT and commit the transaction
    db.refresh(new_candidate) # Load the auto-generated id, created_at, etc.

    return new_candidate  # FastAPI serializes using CandidateResponse schema


# ─── GET ALL CANDIDATES ───────────────────────────────────────────────────────

@router.get("/", response_model=List[CandidateResponse])
def get_candidates(
    skip: int = 0,    # For pagination: how many records to skip
    limit: int = 50,  # For pagination: how many records to return
    db: Session = Depends(get_db)
):
    """
    List all candidates with pagination.
    
    SKILL LEARNED — SQL Pagination:
      Without pagination, large tables = slow queries + huge responses.
      skip + limit is the simplest pagination strategy:
        Page 1: skip=0, limit=10  → rows 1-10
        Page 2: skip=10, limit=10 → rows 11-20
        etc.
      
      SQL equivalent: SELECT * FROM candidates LIMIT 10 OFFSET 0
    """
    candidates = db.query(Candidate).offset(skip).limit(limit).all()
    return candidates


# ─── GET SINGLE CANDIDATE ─────────────────────────────────────────────────────

@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    """
    Get a specific candidate by ID.
    
    Path parameters (like {candidate_id}) are extracted from the URL automatically.
    GET /candidates/42 → candidate_id = 42
    """
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate {candidate_id} not found"
        )
    return candidate


# ─── ANALYZE RESUME (AI FEATURE) ──────────────────────────────────────────────

@router.post("/analyze-resume", response_model=ResumeAnalysisResponse)
def analyze_resume(request: ResumeAnalysisRequest, db: Session = Depends(get_db)):
    """
    Trigger LLM analysis of a candidate's resume.
    
    THIS IS THE CORE AI FEATURE. Flow:
    1. Fetch candidate from DB
    2. Send resume text to LLM service
    3. LLM returns structured JSON analysis
    4. Save analysis results to DB
    5. Return response to API caller
    
    WHAT MAKES THIS INTERESTING FOR YOUR PORTFOLIO:
    You're combining traditional software engineering (DB operations, REST API)
    with AI (LLM calls, prompt engineering) — that's the full "AI Engineer" stack.
    """
    # Step 1: Get the candidate
    candidate = db.query(Candidate).filter(Candidate.id == request.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {request.candidate_id} not found")

    if not candidate.resume_text:
        raise HTTPException(
            status_code=400,
            detail="Candidate has no resume text. Upload resume first."
        )

    # Step 2: Check if analysis already exists (avoid redundant LLM API calls)
    if not request.force_reanalyze:
        existing_analysis = db.query(ResumeAnalysis).filter(
            ResumeAnalysis.candidate_id == candidate.id
        ).first()
        if existing_analysis:
            # Return cached analysis
            analysis_data = json.loads(existing_analysis.analysis_json)
            return _build_analysis_response(candidate, existing_analysis, analysis_data)

    # Step 3: Call the LLM — this is where the AI magic happens
    try:
        analysis_data = llm_service.analyze_resume(
            resume_text=candidate.resume_text,
            candidate_name=candidate.name
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM analysis failed: {str(e)}"
        )

    # Step 4: Save the analysis to DB
    analysis_record = ResumeAnalysis(
        candidate_id=candidate.id,
        analysis_json=json.dumps(analysis_data),  # Store full JSON as text
        extracted_skills=", ".join(analysis_data.get("skills", [])),
        experience_years=analysis_data.get("experience_years"),
        education_level=analysis_data.get("education_level"),
        overall_score=analysis_data.get("overall_score"),
        model_used=llm_service.model_name
    )
    db.add(analysis_record)

    # Also update the candidate's profile with extracted data
    candidate.skills = ", ".join(analysis_data.get("skills", []))
    candidate.years_experience = analysis_data.get("experience_years")
    candidate.ai_summary = analysis_data.get("summary")

    db.commit()
    db.refresh(analysis_record)

    return _build_analysis_response(candidate, analysis_record, analysis_data)


def _build_analysis_response(candidate, analysis_record, analysis_data) -> ResumeAnalysisResponse:
    """Helper to build the response object from DB records + LLM data."""
    return ResumeAnalysisResponse(
        candidate_id=candidate.id,
        candidate_name=candidate.name,
        extracted_skills=analysis_data.get("skills", []),
        experience_years=analysis_data.get("experience_years"),
        education_level=analysis_data.get("education_level"),
        strengths=analysis_data.get("strengths", []),
        areas_for_improvement=analysis_data.get("areas_for_improvement", []),
        overall_score=analysis_data.get("overall_score", 0),
        summary=analysis_data.get("summary", ""),
        model_used=analysis_record.model_used or "unknown",
        analysis_id=analysis_record.id
    )
