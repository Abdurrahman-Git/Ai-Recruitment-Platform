# 🤖 AI Recruitment Intelligence Platform

> An AI-powered recruitment assistant built with FastAPI, OpenAI GPT-4o, SQLAlchemy, and Pydantic. Automatically analyzes resumes, matches candidates to jobs, generates job descriptions, and ranks applicants — all via a REST API.

---

## 🏗️ Architecture

```
ai-recruitment-platform/
├── main.py                          # FastAPI app entry point
├── requirements.txt
├── .env.example                     # Copy to .env and add your API key
│
└── app/
    ├── core/
    │   ├── config.py                # Settings loaded from .env (Pydantic Settings)
    │   └── database.py              # SQLAlchemy engine + session management
    │
    ├── models/
    │   └── models.py                # Database tables (Candidate, JobPosting, etc.)
    │
    ├── schemas/
    │   └── schemas.py               # Pydantic request/response validation schemas
    │
    ├── services/
    │   └── llm_service.py           # All LLM (OpenAI) calls + prompt engineering
    │
    └── api/routes/
        ├── candidates.py            # Candidate CRUD + resume analysis
        ├── jobs.py                  # Job CRUD + AI job description generation
        └── matching.py              # AI matching, ranking, screening questions
```

---

## 🚀 Quick Start

### 1. Clone and install dependencies
```bash
git clone <your-repo>
cd ai-recruitment-platform
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key:
# OPENAI_API_KEY=sk-your-key-here
```

### 3. Run the server
```bash
python main.py
# OR
uvicorn main:app --reload
```

### 4. Open interactive API docs
```
http://localhost:8000/docs
```

---

## 📡 API Endpoints

### Candidates
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/candidates/` | Create a new candidate |
| GET | `/api/v1/candidates/` | List all candidates |
| GET | `/api/v1/candidates/{id}` | Get a specific candidate |
| POST | `/api/v1/candidates/analyze-resume` | **[AI]** Analyze resume with LLM |

### Jobs
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/jobs/` | Create a job posting |
| GET | `/api/v1/jobs/` | List all jobs |
| GET | `/api/v1/jobs/{id}` | Get a specific job |
| POST | `/api/v1/jobs/generate-jd` | **[AI]** Generate job description |
| PATCH | `/api/v1/jobs/{id}/deactivate` | Deactivate a job |

### AI Intelligence
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/match` | Match one candidate to one job |
| POST | `/api/v1/rank-candidates` | **[AI]** Rank all candidates for a job |
| POST | `/api/v1/screening-questions` | **[AI]** Generate interview questions |
| GET | `/api/v1/analytics/summary` | Platform analytics dashboard |

---

## 💡 Example API Usage

### 1. Create a Candidate
```bash
curl -X POST http://localhost:8000/api/v1/candidates/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alice Johnson",
    "email": "alice@example.com",
    "resume_text": "5 years experience in Python, FastAPI, SQL, Docker. Led a team of 4 engineers at TechCorp building microservices. B.S. Computer Science, MIT 2018."
  }'
```

### 2. Analyze the Resume with AI
```bash
curl -X POST http://localhost:8000/api/v1/candidates/analyze-resume \
  -H "Content-Type: application/json" \
  -d '{"candidate_id": 1}'
```

Response:
```json
{
  "overall_score": 84,
  "extracted_skills": ["Python", "FastAPI", "SQL", "Docker"],
  "experience_years": 5.0,
  "strengths": ["Strong Python ecosystem knowledge", "Team leadership"],
  "summary": "Senior Python developer with 5 years experience building production APIs..."
}
```

### 3. Generate a Job Description with AI
```bash
curl -X POST http://localhost:8000/api/v1/jobs/generate-jd \
  -H "Content-Type: application/json" \
  -d '{
    "job_title": "Senior Python Developer",
    "company_name": "DataTech Inc",
    "required_skills": ["Python", "FastAPI", "SQL"],
    "experience_years": 3,
    "is_remote": true
  }'
```

### 4. Rank All Candidates for a Job
```bash
curl -X POST http://localhost:8000/api/v1/rank-candidates \
  -H "Content-Type: application/json" \
  -d '{"job_id": 1, "top_n": 5}'
```

Response:
```json
[
  {"rank": 1, "candidate_name": "Alice Johnson", "match_score": 88, "missing_skills": []},
  {"rank": 2, "candidate_name": "Bob Smith", "match_score": 72, "missing_skills": ["Docker"]},
  ...
]
```

---

## 🧪 Running Tests
```bash
pytest tests/ -v
```

---

## 🧠 Skills Demonstrated

| Skill | Where Used |
|-------|------------|
| **FastAPI** | All route handlers, dependency injection, middleware |
| **Prompt Engineering** | `llm_service.py` — 4 carefully crafted prompts for different tasks |
| **LLM Integration** | OpenAI API calls with JSON mode, temperature control |
| **SQLAlchemy ORM** | Models, relationships, foreign keys, queries, aggregations |
| **Pydantic** | Schema validation, settings management, type safety |
| **REST API Design** | Proper HTTP methods, status codes, error handling |
| **SQL** | Relational schema design, pagination, aggregations |
| **Testing** | pytest + mocking for LLM calls |
| **Python Best Practices** | Service layer pattern, dependency injection, config management |

---

## 🔧 Production Improvements (for interviews)

When asked about scaling/production, mention:

1. **Async LLM calls**: Use `asyncio` + `httpx` to call LLM for multiple candidates in parallel (10x speed improvement for bulk matching)
2. **Caching**: Redis to cache analysis results — don't re-analyze the same resume
3. **Background tasks**: Use FastAPI BackgroundTasks or Celery for long-running bulk operations
4. **PostgreSQL**: Switch `DATABASE_URL` in .env — code is already compatible
5. **Rate limiting**: Add slowapi middleware to prevent API abuse
6. **Authentication**: JWT tokens with FastAPI-Users for multi-tenant use
7. **Vector search**: Embed resumes with text-embedding-3 and use pgvector for semantic matching (much faster than LLM for large scale)
