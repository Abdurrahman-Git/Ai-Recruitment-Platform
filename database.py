"""
WHAT THIS FILE DOES:
────────────────────
Sets up the database connection and session management.

SKILL LEARNED — SQLAlchemy ORM:
  ORM = Object Relational Mapper. It lets you work with databases using
  Python classes instead of raw SQL strings.

  WITHOUT ORM (raw SQL):
    cursor.execute("INSERT INTO candidates VALUES (?, ?)", (name, email))
    cursor.execute("SELECT * FROM candidates WHERE id = ?", (id,))

  WITH SQLAlchemy ORM:
    db.add(Candidate(name=name, email=email))
    db.query(Candidate).filter(Candidate.id == id).first()

  Benefits:
    - No SQL injection vulnerabilities
    - Database-agnostic (same code works for SQLite AND PostgreSQL)
    - Python-style querying with autocomplete

SKILL LEARNED — Dependency Injection with FastAPI:
  get_db() is a "dependency." FastAPI calls it automatically for each
  request, gives your route a database session, and closes it when done.
  This prevents connection leaks (very common bug in production).
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# ── Engine ────────────────────────────────────────────────────────────────────
# The engine is the low-level connection to your database.
# connect_args is SQLite-specific: allows multiple threads to use same connection.
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}  # Only needed for SQLite
)

# ── Session Factory ────────────────────────────────────────────────────────────
# SessionLocal is a "factory" — calling SessionLocal() creates a new DB session.
# Think of a session as a single "unit of work" with the database.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── Base Class ─────────────────────────────────────────────────────────────────
# All your SQLAlchemy models (database tables) must inherit from this Base.
# It's how SQLAlchemy knows which Python classes represent DB tables.
Base = declarative_base()


def get_db():
    """
    FastAPI Dependency: provides a database session per request.

    HOW IT WORKS — Python Generator with 'yield':
      This is a generator function. The 'yield' pauses execution and
      gives the db session to the route handler. When the request finishes
      (success OR error), execution resumes after yield and db.close() runs.

      This pattern ensures the connection is ALWAYS closed, even if there's
      an exception. Without this, you'd leak connections and crash under load.
    """
    db = SessionLocal()
    try:
        yield db          # ← Give the session to whoever asked for it
    finally:
        db.close()        # ← Always runs, even on exceptions
