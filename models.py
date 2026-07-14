"""
WHAT THIS FILE DOES:
────────────────────
Defines your database tables as Python classes using SQLAlchemy.
Each class = one table. Each class attribute = one column.

SKILL LEARNED — SQL Database Design:
  Good database design separates concerns into tables linked by foreign keys.
  
  Our schema:
    candidates     — stores candidate profiles
    job_postings   — stores job descriptions
    resume_analyses — stores LLM analysis results (links to candidates)
    job_matches    — stores match scores (links candidates ↔ jobs)

  This is a "relational" design: instead of duplicating data, we store IDs
  and JOIN tables when we need combined data. This is fundamental SQL thinking.

SKILL LEARNED — SQLAlchemy Column Types:
  String  = VARCHAR  (text up to N chars)
  Text    = TEXT     (unlimited text — good for resume content, LLM outputs)
  Integer = INTEGER
  Float   = FLOAT / REAL
  Boolean = BOOLEAN
  DateTime = TIMESTAMP
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Candidate(Base):
    """
    Represents a job candidate in the system.
    
    SQL TABLE: candidates
    Think of this as a row in a spreadsheet where each attribute is a column.
    """
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    # index=True creates a DB index — makes queries like "find by email" much faster
    
    name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    
    # We store the raw resume text so the LLM can analyze it
    resume_text = Column(Text, nullable=True)
    
    # Years of experience — extracted by the LLM from resume text
    years_experience = Column(Float, nullable=True)
    
    # Comma-separated skills extracted by LLM: "Python,FastAPI,SQL,Docker"
    skills = Column(Text, nullable=True)
    
    # The LLM-generated summary of the candidate
    ai_summary = Column(Text, nullable=True)
    
    # Automatic timestamps — set automatically by SQLAlchemy
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ─────────────────────────────────────────────────────────
    # These are Python-level relationships, not actual columns.
    # They let you do: candidate.analyses to get all their analyses.
    analyses = relationship("ResumeAnalysis", back_populates="candidate")
    matches = relationship("JobMatch", back_populates="candidate")


class JobPosting(Base):
    """
    Represents a job opening that candidates can be matched against.
    
    SQL TABLE: job_postings
    """
    __tablename__ = "job_postings"

    id = Column(Integer, primary_key=True, index=True)
    
    title = Column(String(200), nullable=False)
    company = Column(String(200), nullable=False)
    
    # The full job description text (can be human-written or LLM-generated)
    description = Column(Text, nullable=False)
    
    # Required skills as comma-separated list: "Python,Docker,AWS"
    required_skills = Column(Text, nullable=True)
    
    min_experience_years = Column(Float, nullable=True)
    location = Column(String(200), nullable=True)
    is_remote = Column(Boolean, default=False)
    
    # Whether this JD was AI-generated or manually entered
    ai_generated = Column(Boolean, default=False)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship: a job can have many matches
    matches = relationship("JobMatch", back_populates="job")


class ResumeAnalysis(Base):
    """
    Stores the LLM's analysis of a candidate's resume.
    
    SQL TABLE: resume_analyses
    
    WHY A SEPARATE TABLE?
    Resume analysis can be re-run (LLM models improve over time).
    Keeping it separate means we can store multiple analyses per candidate
    and track which model/prompt generated each one.
    
    FOREIGN KEY CONCEPT:
    candidate_id links this row to a row in the candidates table.
    This is how SQL "relates" tables — instead of copying the candidate's
    data here, we just store their ID and JOIN when needed.
    """
    __tablename__ = "resume_analyses"

    id = Column(Integer, primary_key=True, index=True)
    
    # ForeignKey("candidates.id") = this column references the id column of candidates table
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    
    # The complete JSON output from the LLM, stored as text
    # Example: {"skills": ["Python"], "experience_years": 3, "strengths": [...]}
    analysis_json = Column(Text, nullable=False)
    
    # Individual extracted fields for easy querying without parsing JSON every time
    extracted_skills = Column(Text, nullable=True)
    experience_years = Column(Float, nullable=True)
    education_level = Column(String(100), nullable=True)
    
    # Suitability scores (0-100) from the LLM
    overall_score = Column(Float, nullable=True)
    
    # Which LLM model was used — important for reproducibility
    model_used = Column(String(100), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # This enables: analysis.candidate to get the Candidate object
    candidate = relationship("Candidate", back_populates="analyses")


class JobMatch(Base):
    """
    Stores match scores between a candidate and a job posting.
    
    SQL TABLE: job_matches
    
    This is a "junction table" (also called association table or bridge table).
    It connects candidates and job_postings in a many-to-many relationship:
      - One candidate can be matched to MANY jobs
      - One job can have MANY candidate matches
    """
    __tablename__ = "job_matches"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_postings.id"), nullable=False)
    
    # The overall match score from 0 to 100
    match_score = Column(Float, nullable=False)
    
    # Individual dimension scores — breakdown of WHY the score is what it is
    skills_score = Column(Float, nullable=True)         # Do skills match?
    experience_score = Column(Float, nullable=True)     # Is experience right?
    education_score = Column(Float, nullable=True)      # Education fit?
    
    # LLM's reasoning for the score — human-readable explanation
    match_reasoning = Column(Text, nullable=True)
    
    # Key missing skills for this candidate-job pair
    missing_skills = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    candidate = relationship("Candidate", back_populates="matches")
    job = relationship("JobPosting", back_populates="matches")
