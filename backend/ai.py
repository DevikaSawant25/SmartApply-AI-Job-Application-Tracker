import anthropic
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize the Anthropic client using the API key loaded from .env
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def analyze_resume(resume_text: str, job_description: str) -> dict:
    """
    Compares the user's resume against the job description.
    Instructs Claude to return ONLY valid JSON matching a specific schema.
    """
    prompt = f"""
You are a resume expert. Compare this resume against the job description.
Return ONLY valid JSON — no extra text, no markdown, no backticks.
Use exactly this structure:

{{
  "match_score": <integer 0-100>,
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill1", "skill2"],
  "section_feedback": {{
    "experience": "one sentence feedback",
    "skills": "one sentence feedback",
    "education": "one sentence feedback"
  }},
  "summary": "one sentence overall summary"
}}

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}
"""
    # Using 'claude-3-5-sonnet-latest' as it is the current state-of-the-art model
    message = client.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    # Parse the response text directly into a Python dictionary
    return json.loads(message.content[0].text)


def generate_cover_letter(resume_text: str, job_description: str,
                           company: str, role: str) -> str:
    """
    Generates a professional, tailored 3-paragraph cover letter
    referencing specific matching skills between the resume and job description.
    """
    prompt = f"""
Write a professional, tailored 3-paragraph cover letter for this job application.
Be specific — reference actual skills and experience from the resume that match the JD.
Do not include a subject line or any commentary — return only the letter text.

Company: {company}
Role: {role}

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}
"""
    message = client.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text
