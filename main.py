"""
WHAT THIS FILE DOES:
────────────────────
The main entry point of your FastAPI application.
This is where everything gets assembled together.

SKILL LEARNED — Application Lifecycle:
  FastAPI apps have a startup event where you can run initialization code
  (like creating DB tables). Without this, your tables wouldn't exist and
  every DB operation would crash.

SKILL LEARNED — FastAPI App Structure:
  FastAPI(
    title=...          → Shows in auto-docs at /docs
    description=...    → Explains the API
    version=...        → API versioning
  )
  
  app.include_router(router, prefix="/api/v1")
    → All routes from that router get the /api/v1 prefix
    → Keeps your URL structure organized and versionable

SKILL LEARNED — CORS:
  CORS (Cross-Origin Resource Sharing) controls which websites can call
  your API from a browser. You need this if you build a frontend.
  allow_origins=["*"] is for development only — restrict in production!
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine
from app.models.models import Base
from app.api.routes import candidates, jobs, matching


# ── Lifespan: runs at app startup and shutdown ────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: create all database tables if they don't exist.
    
    Base.metadata.create_all(bind=engine) scans all classes that inherit
    from Base (your models) and creates the corresponding SQL tables.
    
    This is equivalent to running: CREATE TABLE IF NOT EXISTS candidates (...)
    for every model you've defined.
    """
    print("🚀 Starting AI Recruitment Intelligence Platform...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables initialized")
    yield  # App runs here
    print("👋 Shutting down...")


# ── Create FastAPI app ────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    description="""
    ## AI-Powered Recruitment Intelligence Platform
    
    An intelligent recruitment assistant that uses Large Language Models to:
    
    * **Analyze Resumes** — Extract skills, experience, and score candidates
    * **Match Candidates to Jobs** — AI-powered fit scoring with detailed reasoning
    * **Rank Candidates** — Get a ranked list of best candidates for any job
    * **Generate Job Descriptions** — Professional JDs from minimal input
    * **Screen Candidates** — Personalized interview questions
    * **Analytics** — Platform-wide recruitment insights
    
    Built with: FastAPI · SQLAlchemy · OpenAI GPT-4o · Pydantic
    """,
    version="1.0.0",
    lifespan=lifespan
)

# ── CORS Middleware ────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # In production: specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register all route modules ─────────────────────────────────────────────────
# Each router is a set of related routes (candidates, jobs, matching)
# prefix="/api/v1" means all routes become /api/v1/candidates, /api/v1/jobs, etc.
app.include_router(candidates.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(matching.router, prefix="/api/v1")


# ── Root endpoint ─────────────────────────────────────────────────────────────
@app.get("/")
def root():
    """Health check and API info."""
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


# ── Run directly with: python main.py ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    # uvicorn is the ASGI server that serves FastAPI
    # reload=True means the server auto-restarts when you change code (dev only)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
