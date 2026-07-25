"""
Main entry point — now also serves the frontend UI.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.core.config import settings
from app.core.database import engine
from app.models.models import Base
from app.api.routes import candidates, jobs, matching


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting AI Recruitment Intelligence Platform...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables initialized")
    yield
    print("👋 Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Recruitment Intelligence Platform — FastAPI + Google Gemini",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(candidates.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(matching.router, prefix="/api/v1")


# ── Serve frontend UI ─────────────────────────────────────────────────────────
@app.get("/ui", include_in_schema=False)
def serve_frontend():
    """Serve the RecruitIQ frontend dashboard."""
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    return FileResponse(frontend_path)


@app.get("/", include_in_schema=False)
def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "ui": "http://localhost:8000/ui",
        "api_docs": "http://localhost:8000/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
