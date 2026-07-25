"""
WHAT THIS FILE DOES:
────────────────────
FastAPI routes for job posting management and AI-powered JD generation.

KEY FEATURE: The /generate-jd endpoint shows the full power of LLMs in
a product context — taking minimal structured input and producing a 
professional, human-quality job description.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.models import JobPosting
from app.schemas.schemas import (
    JobPostingCreate, JobPostingResponse,
    JDGenerationRequest, JDGenerationResponse
)
from app.services.llm_service import llm_service

router = APIRouter(prefix="/jobs", tags=["Job Postings"])


# ─── CREATE JOB POSTING ───────────────────────────────────────────────────────

@router.post("/", response_model=JobPostingResponse, status_code=status.HTTP_201_CREATED)
def create_job_posting(job_data: JobPostingCreate, db: Session = Depends(get_db)):
    """Create a job posting manually (non-AI)."""
    new_job = JobPosting(
        title=job_data.title,
        company=job_data.company,
        description=job_data.description,
        required_skills=job_data.required_skills,
        min_experience_years=job_data.min_experience_years,
        location=job_data.location,
        is_remote=job_data.is_remote,
        ai_generated=False
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return new_job


# ─── LIST ALL JOBS ────────────────────────────────────────────────────────────

@router.get("/", response_model=List[JobPostingResponse])
def get_jobs(
    active_only: bool = True,   # Query parameter: ?active_only=true
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    List job postings.
    
    SKILL LEARNED — Query Parameters:
      Unlike path params (/jobs/{id}), query params come after '?':
        GET /jobs?active_only=true&limit=10&skip=0
      
      FastAPI reads them directly from the function signature.
      They're optional (have defaults) unless you use = ... (no default).
    """
    query = db.query(JobPosting)
    if active_only:
        query = query.filter(JobPosting.is_active == True)
    return query.offset(skip).limit(limit).all()


# ─── GET SINGLE JOB ───────────────────────────────────────────────────────────

@router.get("/{job_id}", response_model=JobPostingResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get a single job posting by ID."""
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


# ─── AI: GENERATE JOB DESCRIPTION ────────────────────────────────────────────

@router.post("/generate-jd", response_model=JDGenerationResponse)
def generate_job_description(request: JDGenerationRequest, db: Session = Depends(get_db)):
    """
    Use AI to generate a professional job description.
    
    THIS IS A KEY PORTFOLIO FEATURE. It demonstrates:
    1. Taking structured input (title, skills, experience level)
    2. Engineering a prompt that produces high-quality output
    3. Optionally persisting the result to the database
    4. Returning the result via a typed API response
    
    REAL-WORLD USE CASE:
    HR teams spend 2-3 hours writing each JD. This generates one in 10 seconds.
    Companies like Workday, Greenhouse, and Lever charge for this exact feature.
    """
    try:
        # Step 1: Generate the JD text using LLM
        generated_text = llm_service.generate_job_description(
            job_title=request.job_title,
            company_name=request.company_name,
            required_skills=request.required_skills,
            experience_years=request.experience_years,
            location=request.location,
            is_remote=request.is_remote,
            extra_context=request.extra_context
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"JD generation failed: {str(e)}")

    job_posting_id = None

    # Step 2: Optionally save to DB as a job posting
    if request.save_to_db:
        skills_str = ", ".join(request.required_skills)
        new_job = JobPosting(
            title=request.job_title,
            company=request.company_name,
            description=generated_text,
            required_skills=skills_str,
            min_experience_years=float(request.experience_years),
            location=request.location,
            is_remote=request.is_remote,
            ai_generated=True  # Flag that this was AI-generated
        )
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        job_posting_id = new_job.id

    return JDGenerationResponse(
        job_title=request.job_title,
        company_name=request.company_name,
        generated_description=generated_text,
        job_posting_id=job_posting_id
    )


# ─── DEACTIVATE JOB ───────────────────────────────────────────────────────────

@router.patch("/{job_id}/deactivate", response_model=JobPostingResponse)
def deactivate_job(job_id: int, db: Session = Depends(get_db)):
    """
    Soft-delete a job posting by marking it inactive.
    
    SKILL LEARNED — Soft Delete:
      Instead of deleting rows (irreversible, can break foreign key references),
      we set is_active=False. This is standard practice in production systems:
      - Data is preserved for analytics
      - Accidental deletion can be reversed
      - Historical match data remains intact
    """
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    job.is_active = False
    db.commit()
    db.refresh(job)
    return job
