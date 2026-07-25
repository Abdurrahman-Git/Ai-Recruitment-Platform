"""
WHAT THIS FILE DOES:
────────────────────
The most sophisticated set of routes — AI-powered candidate-job matching.

This is what makes the platform genuinely intelligent:
  - Match ONE candidate to ONE job → get a score + explanation
  - Match ALL candidates to ONE job → get a ranked list (the holy grail for recruiters)
  - Generate tailored screening questions for any candidate-job pair

SKILL LEARNED — Business Logic in APIs:
  The /rank-candidates endpoint orchestrates multiple DB queries +
  multiple LLM calls + scoring + sorting. This is what a senior
  engineer means by "business logic" — code that implements the
  core value proposition of the product.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
import json

from app.core.database import get_db
from app.models.models import Candidate, JobPosting, JobMatch, ResumeAnalysis
from app.schemas.schemas import (
    JobMatchRequest, JobMatchResponse,
    BulkMatchRequest, RankedCandidateResponse,
    ScreeningRequest, ScreeningResponse,
    AnalyticsSummary
)
from app.services.llm_service import llm_service

router = APIRouter(tags=["Matching & Intelligence"])


# ─── MATCH ONE CANDIDATE TO ONE JOB ──────────────────────────────────────────

@router.post("/match", response_model=JobMatchResponse)
def match_candidate_to_job(request: JobMatchRequest, db: Session = Depends(get_db)):
    """
    Score a single candidate against a single job posting using AI.
    
    Returns a detailed match report with score breakdown and reasoning.
    """
    # Fetch candidate and job — both must exist
    candidate = db.query(Candidate).filter(Candidate.id == request.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate {request.candidate_id} not found")

    job = db.query(JobPosting).filter(JobPosting.id == request.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")

    if not candidate.resume_text:
        raise HTTPException(status_code=400, detail="Candidate has no resume. Add resume text first.")

    # Call the LLM matching service
    try:
        match_data = llm_service.match_candidate_to_job(
            candidate_name=candidate.name,
            resume_text=candidate.resume_text,
            candidate_skills=candidate.skills or "",
            job_title=job.title,
            job_description=job.description,
            required_skills=job.required_skills or "",
            min_experience=job.min_experience_years
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Matching failed: {str(e)}")

    # Save the match result to DB
    match_record = JobMatch(
        candidate_id=candidate.id,
        job_id=job.id,
        match_score=match_data.get("overall_match_score", 0),
        skills_score=match_data.get("skills_score"),
        experience_score=match_data.get("experience_score"),
        education_score=match_data.get("education_score"),
        match_reasoning=match_data.get("match_reasoning", ""),
        missing_skills=json.dumps(match_data.get("missing_skills", []))
    )
    db.add(match_record)
    db.commit()
    db.refresh(match_record)

    return JobMatchResponse(
        match_id=match_record.id,
        candidate_id=candidate.id,
        candidate_name=candidate.name,
        job_id=job.id,
        job_title=job.title,
        match_score=match_record.match_score,
        skills_score=match_record.skills_score,
        experience_score=match_record.experience_score,
        education_score=match_record.education_score,
        match_reasoning=match_record.match_reasoning,
        missing_skills=match_data.get("missing_skills", [])
    )


# ─── RANK ALL CANDIDATES FOR A JOB (Bulk AI Matching) ────────────────────────

@router.post("/rank-candidates", response_model=List[RankedCandidateResponse])
def rank_candidates_for_job(request: BulkMatchRequest, db: Session = Depends(get_db)):
    """
    Rank multiple candidates for a job posting. Returns top N candidates sorted by fit.
    
    THIS IS THE KILLER FEATURE of the platform.
    
    WHAT MAKES THIS COMPLEX:
    1. Fetch all eligible candidates
    2. For each candidate, call the LLM to score them (N LLM API calls)
    3. Sort all results by score
    4. Return top N

    PRODUCTION CONSIDERATIONS (explain in interviews!):
    - For 100+ candidates, you'd want to run LLM calls in parallel (asyncio)
    - You'd cache results so re-ranking is instant
    - You'd pre-filter candidates (e.g., must have Python skill) before LLM calls
      to reduce cost
    - You might use a cheaper model for initial filtering, then GPT-4 for top 20
    
    This is synchronous for simplicity. Mention async optimization in your portfolio.
    """
    # Fetch the job
    job = db.query(JobPosting).filter(JobPosting.id == request.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")

    # Fetch candidates to evaluate
    if request.candidate_ids:
        # Specific candidates requested
        candidates = db.query(Candidate).filter(
            Candidate.id.in_(request.candidate_ids),
            Candidate.resume_text.isnot(None)
        ).all()
    else:
        # All candidates with resumes
        candidates = db.query(Candidate).filter(
            Candidate.resume_text.isnot(None)
        ).limit(50).all()  # Cap at 50 to control LLM costs

    if not candidates:
        raise HTTPException(status_code=404, detail="No eligible candidates found with resumes")

    ranked_results = []

    # Score each candidate against the job
    for candidate in candidates:
        try:
            match_data = llm_service.match_candidate_to_job(
                candidate_name=candidate.name,
                resume_text=candidate.resume_text,
                candidate_skills=candidate.skills or "",
                job_title=job.title,
                job_description=job.description,
                required_skills=job.required_skills or "",
                min_experience=job.min_experience_years
            )

            # Save each match to DB
            match_record = JobMatch(
                candidate_id=candidate.id,
                job_id=job.id,
                match_score=match_data.get("overall_match_score", 0),
                skills_score=match_data.get("skills_score"),
                experience_score=match_data.get("experience_score"),
                education_score=match_data.get("education_score"),
                match_reasoning=match_data.get("match_reasoning", ""),
                missing_skills=json.dumps(match_data.get("missing_skills", []))
            )
            db.add(match_record)

            ranked_results.append({
                "candidate": candidate,
                "match_data": match_data
            })

        except Exception as e:
            # Don't fail entire request if one candidate fails — skip and continue
            print(f"Scoring failed for candidate {candidate.id}: {e}")
            continue

    db.commit()

    # Sort by match score descending, take top N
    ranked_results.sort(key=lambda x: x["match_data"].get("overall_match_score", 0), reverse=True)
    top_results = ranked_results[:request.top_n]

    # Build response
    response = []
    for rank, result in enumerate(top_results, start=1):
        c = result["candidate"]
        m = result["match_data"]
        response.append(RankedCandidateResponse(
            rank=rank,
            candidate_id=c.id,
            candidate_name=c.name,
            candidate_email=c.email,
            match_score=m.get("overall_match_score", 0),
            skills_score=m.get("skills_score"),
            experience_score=m.get("experience_score"),
            match_reasoning=m.get("match_reasoning", ""),
            missing_skills=m.get("missing_skills", [])
        ))

    return response


# ─── GENERATE SCREENING QUESTIONS ─────────────────────────────────────────────

@router.post("/screening-questions", response_model=ScreeningResponse)
def generate_screening_questions(request: ScreeningRequest, db: Session = Depends(get_db)):
    """
    Generate personalized screening questions for a candidate-job interview.
    
    SKILL LEARNED — LLM Chaining:
      This endpoint uses the candidate's AI summary (generated by analyze_resume)
      as context. This is "LLM chaining" — the output of one LLM call becomes
      input to another. This is the foundation of more advanced AI pipelines.
    """
    candidate = db.query(Candidate).filter(Candidate.id == request.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    job = db.query(JobPosting).filter(JobPosting.id == request.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Use AI summary if available, fall back to raw resume
    candidate_context = candidate.ai_summary or candidate.resume_text or "No resume provided"

    try:
        screening_data = llm_service.generate_screening_questions(
            candidate_name=candidate.name,
            candidate_skills=candidate.skills or "",
            resume_summary=candidate_context,
            job_title=job.title,
            job_description=job.description,
            num_questions=request.num_questions
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Question generation failed: {str(e)}")

    return ScreeningResponse(
        candidate_name=candidate.name,
        job_title=job.title,
        questions=screening_data.get("questions", []),
        focus_areas=screening_data.get("focus_areas", [])
    )


# ─── ANALYTICS DASHBOARD ──────────────────────────────────────────────────────

@router.get("/analytics/summary", response_model=AnalyticsSummary)
def get_analytics_summary(db: Session = Depends(get_db)):
    """
    Get platform-wide analytics.
    
    SKILL LEARNED — SQLAlchemy Aggregations:
      func.count() → SQL COUNT()
      func.avg()   → SQL AVG()
      
      SQLAlchemy: db.query(func.count(Candidate.id)).scalar()
      SQL equiv:  SELECT COUNT(id) FROM candidates
      
      'scalar()' retrieves a single value (not a list of rows).
    """
    total_candidates = db.query(func.count(Candidate.id)).scalar() or 0
    total_jobs = db.query(func.count(JobPosting.id)).scalar() or 0
    total_matches = db.query(func.count(JobMatch.id)).scalar() or 0
    avg_score = db.query(func.avg(JobMatch.match_score)).scalar()

    # Extract most common skills across all candidates
    all_candidates = db.query(Candidate).filter(Candidate.skills.isnot(None)).all()
    skill_counts = {}
    for c in all_candidates:
        if c.skills:
            for skill in c.skills.split(","):
                skill = skill.strip()
                if skill:
                    skill_counts[skill] = skill_counts.get(skill, 0) + 1
    top_candidate_skills = sorted(skill_counts, key=skill_counts.get, reverse=True)[:10]

    # Most demanded skills from job postings
    all_jobs = db.query(JobPosting).filter(JobPosting.required_skills.isnot(None)).all()
    demand_counts = {}
    for j in all_jobs:
        if j.required_skills:
            for skill in j.required_skills.split(","):
                skill = skill.strip()
                if skill:
                    demand_counts[skill] = demand_counts.get(skill, 0) + 1
    top_demanded_skills = sorted(demand_counts, key=demand_counts.get, reverse=True)[:10]

    return AnalyticsSummary(
        total_candidates=total_candidates,
        total_jobs=total_jobs,
        total_matches=total_matches,
        avg_match_score=round(avg_score, 1) if avg_score else None,
        top_skills_in_demand=top_demanded_skills,
        top_candidate_skills=top_candidate_skills
    )
