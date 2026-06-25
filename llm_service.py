"""
LLM Service — updated to use google-genai (new Google SDK).

WHY THE CHANGE:
  google-generativeai (old) → deprecated, removed support for v1beta API
  google-genai (new)        → current official SDK, uses v1 API

WHAT CHANGED IN THE CODE:
  Old: import google.generativeai as genai
       model = genai.GenerativeModel(model_name=...)
       response = model.generate_content(prompt)
       answer = response.text

  New: from google import genai
       client = genai.Client(api_key=...)
       response = client.models.generate_content(model=..., contents=...)
       answer = response.text

Everything else — prompts, logic, parsing — is identical.
"""

import json
import re
from typing import Optional
from google import genai
from google.genai import types
from app.core.config import settings


class LLMService:

    def __init__(self):
        # New SDK: create a Client object with your API key
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = settings.LLM_MODEL   # string: "gemini-2.0-flash"

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        """
        Makes the actual API call using the new google-genai SDK.

        New SDK call structure:
          client.models.generate_content(
              model="gemini-2.0-flash",
              contents="your prompt here",
              config=types.GenerateContentConfig(...)
          )
        """
        # Combine system + user prompts (Gemini handles them as one string)
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
        )

        return response.text

    def _parse_json_response(self, raw_response: str) -> dict:
        """Safely parse Gemini's JSON response, stripping markdown fences."""
        cleaned = re.sub(r"```json\s*|\s*```", "", raw_response).strip()
        cleaned = re.sub(r"^json\s*", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Gemini returned invalid JSON: {e}\n"
                f"Raw response (first 300 chars): {raw_response[:300]}"
            )

    # ── Resume Analysis ────────────────────────────────────────────────────────

    def analyze_resume(self, resume_text: str, candidate_name: str) -> dict:
        system_prompt = """You are a senior HR analyst and talent acquisition specialist 
with 15+ years of experience evaluating candidates.

CRITICAL: Respond with ONLY a valid JSON object. No explanation, no markdown, 
no extra text. Start with { and end with }.

Use EXACTLY this schema:
{
  "skills": ["skill1", "skill2"],
  "experience_years": 3.5,
  "education_level": "Bachelor's",
  "strengths": ["strength1", "strength2"],
  "areas_for_improvement": ["area1"],
  "overall_score": 72,
  "summary": "Two sentence professional summary",
  "career_level": "Mid-level",
  "key_technologies": ["Python", "SQL"],
  "industry_domains": ["FinTech", "SaaS"]
}

education_level: "High School","Associate's","Bachelor's","Master's","PhD","Bootcamp","Self-taught","Unknown"
career_level: "Entry-level","Mid-level","Senior","Lead","Executive"
overall_score 0-100: 90+=Exceptional, 70-89=Strong, 50-69=Decent, 30-49=Gaps, 0-29=Poor"""

        user_prompt = f"""Analyze the resume for: {candidate_name}

RESUME:
{resume_text}

Return ONLY the JSON object."""

        raw = self._call_llm(system_prompt, user_prompt, temperature=0.2)
        return self._parse_json_response(raw)

    # ── Job Matching ───────────────────────────────────────────────────────────

    def match_candidate_to_job(
        self,
        candidate_name: str,
        resume_text: str,
        candidate_skills: str,
        job_title: str,
        job_description: str,
        required_skills: str,
        min_experience: Optional[float]
    ) -> dict:
        system_prompt = """You are an expert technical recruiter for candidate-job fit.

CRITICAL: Respond with ONLY a valid JSON object.

Schema:
{
  "overall_match_score": 75,
  "skills_score": 80,
  "experience_score": 70,
  "education_score": 75,
  "match_reasoning": "3-4 sentence explanation",
  "missing_skills": ["Kubernetes"],
  "matching_skills": ["Python", "SQL"],
  "recommendation": "Strong Match",
  "hiring_notes": "One sentence for hiring manager"
}

recommendation: "Strong Match","Good Match","Partial Match","Poor Match"
overall = (skills×0.5) + (experience×0.35) + (education×0.15)"""

        user_prompt = f"""Evaluate candidate for job:

CANDIDATE: {candidate_name}
SKILLS: {candidate_skills}
RESUME: {resume_text[:1500]}

JOB: {job_title}
REQUIRED SKILLS: {required_skills}
MIN EXPERIENCE: {min_experience} years
DESCRIPTION: {job_description[:1500]}

Return ONLY the JSON."""

        raw = self._call_llm(system_prompt, user_prompt, temperature=0.2)
        return self._parse_json_response(raw)

    # ── Job Description Generation ─────────────────────────────────────────────

    def generate_job_description(
        self,
        job_title: str,
        company_name: str,
        required_skills: list,
        experience_years: int,
        location: Optional[str],
        is_remote: bool,
        extra_context: Optional[str]
    ) -> str:
        skills_str = ", ".join(required_skills)
        remote_str = "fully remote" if is_remote else f"based in {location or 'our office'}"

        system_prompt = """You are a senior talent acquisition specialist.
Write compelling, inclusive job descriptions (400-600 words).
Structure: Company intro → Role overview → Responsibilities → Requirements → Nice to have → Benefits
Use gender-neutral language. Return plain text only."""

        user_prompt = f"""Write a job description:
Title: {job_title}
Company: {company_name}
Skills: {skills_str}
Experience: {experience_years}+ years
Location: {remote_str}
{f'Context: {extra_context}' if extra_context else ''}"""

        return self._call_llm(system_prompt, user_prompt, temperature=0.7, max_tokens=1000)

    # ── Screening Questions ────────────────────────────────────────────────────

    def generate_screening_questions(
        self,
        candidate_name: str,
        candidate_skills: str,
        resume_summary: str,
        job_title: str,
        job_description: str,
        num_questions: int
    ) -> dict:
        system_prompt = f"""You are an expert technical interviewer.
Generate exactly {num_questions} targeted screening questions.

CRITICAL: Respond with ONLY valid JSON:
{{
  "questions": ["Question 1?", "Question 2?"],
  "focus_areas": ["Technical depth", "Leadership"],
  "interview_tips": "One sentence tip"
}}

Mix: technical verification, behavioral (STAR), scenario, culture fit."""

        user_prompt = f"""Generate {num_questions} questions for:
CANDIDATE: {candidate_name}
SKILLS: {candidate_skills}
BACKGROUND: {resume_summary[:500]}
ROLE: {job_title}
JOB: {job_description[:800]}

Return ONLY the JSON."""

        raw = self._call_llm(system_prompt, user_prompt, temperature=0.5)
        return self._parse_json_response(raw)


llm_service = LLMService()

