import anthropic
import json
import os
import re
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


def get_anthropic_client() -> anthropic.Anthropic:
    """
    Retrieves an initialized Anthropic client.
    Raises ValueError if the API key is not configured.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key.startswith("sk-ant-your-key"):
        raise ValueError("ANTHROPIC_API_KEY is not configured properly in .env")
    return anthropic.Anthropic(api_key=api_key)


def _extract_json(text: str) -> dict:
    """
    Extracts and parses JSON from text, handling markdown code blocks or surrounding text.
    """
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]

    return json.loads(text)


def _heuristic_parse_email(subject: str, sender: str, body: str) -> Dict[str, Any]:
    """
    Rule-based extraction fallback for job confirmation emails when Anthropic API key is not set.
    """
    full_text = f"{subject} {sender} {body}"
    lower_text = full_text.lower()

    is_job = any(
        k in lower_text
        for k in [
            "application",
            "applied",
            "received your application",
            "thank you for applying",
            "interview",
            "job opening",
            "candidate",
            "position",
            "recruiting",
            "talent acquisition",
            "globallogic",
        ]
    )

    if not is_job:
        return {
            "is_job_email": False,
            "company": None,
            "role": None,
            "status": "applied",
            "email_type": "other",
            "summary": "Non-job email",
            "action_required": False,
        }

    status = "applied"
    email_type = "confirmation"
    if any(k in lower_text for k in ["interview", "schedule a time", "phone screen", "technical discussion"]):
        status = "interview"
        email_type = "interview_invite"
    elif any(k in lower_text for k in ["offer of employment", "pleased to offer", "job offer"]):
        status = "offer"
        email_type = "offer"
    elif any(k in lower_text for k in ["not moving forward", "other candidates", "unfortunately", "decided to pursue other"]):
        status = "rejected"
        email_type = "rejection"

    # Extract company name
    company = None
    if "globallogic" in lower_text:
        company = "GlobalLogic"
    elif "stripe" in lower_text:
        company = "Stripe"
    elif "google" in lower_text:
        company = "Google"
    elif "netflix" in lower_text:
        company = "Netflix"
    elif "amazon" in lower_text:
        company = "Amazon"
    elif "meta" in lower_text:
        company = "Meta"
    elif "microsoft" in lower_text:
        company = "Microsoft"
    elif "apple" in lower_text:
        company = "Apple"
    else:
        m = re.search(
            r"(?:applying to|interest in joining|joining|application with|application at|welcome to|team at)\s+([A-Za-z0-9&]+)",
            full_text,
            re.IGNORECASE,
        )
        if m and m.group(1).lower() not in ["joining", "the", "a", "an", "our"]:
            company = m.group(1).strip()
        elif "@" in sender:
            domain = sender.split("@")[-1].split(".")[0]
            if domain not in ["gmail", "yahoo", "outlook", "hotmail", "icloud", "mail", "no-reply", "greenhouse", "lever", "workday", "careers"]:
                company = domain.capitalize()

    if not company:
        company = "Job Application"

    # Extract role
    role = "Applicant"
    role_m = re.search(
        r"(?:role of|position of|application for the|application for|for the position of|for the)\s+([A-Za-z0-9\s]+?)(?:role|position|\.|\n|$|—|-|!|,)",
        full_text,
        re.IGNORECASE,
    )
    if role_m and len(role_m.group(1).strip()) < 50:
        cleaned_role = role_m.group(1).strip()
        if cleaned_role.lower().startswith("the "):
            cleaned_role = cleaned_role[4:].strip()
        if cleaned_role:
            role = cleaned_role

    return {
        "is_job_email": True,
        "company": company,
        "role": role,
        "status": status,
        "email_type": email_type,
        "summary": f"{email_type.replace('_', ' ').capitalize()} for {role} at {company}",
        "action_required": (status == "interview"),
    }


def parse_job_email(subject: str, sender: str, body: str) -> Dict[str, Any]:
    """
    Analyzes an incoming email to identify whether it's related to a job application.
    Uses Claude when API key is present, otherwise uses smart rule-based extraction.
    """
    try:
        client = get_anthropic_client()
    except Exception:
        return _heuristic_parse_email(subject, sender, body)

    prompt = f"""
You are an intelligent email assistant for a job application tracker.
Analyze this email to determine if it is related to a job application (e.g. confirmation of submission, interview invite, assessment, offer, or rejection).

Return ONLY valid JSON — no markdown, no backticks, no commentary.
Use exactly this structure:

{{
  "is_job_email": true or false,
  "company": "Clean company name (e.g. Stripe, GlobalLogic, Google) or null",
  "role": "Job role title (e.g. Senior Backend Engineer) or 'Applicant' if unspecified",
  "status": "one of: 'applied', 'interview', 'offer', 'rejected', 'saved'",
  "email_type": "one of: 'confirmation', 'interview_invite', 'assessment', 'offer', 'rejection', 'status_update', 'newsletter_or_other'",
  "summary": "Clean 1-sentence summary of the email",
  "action_required": true or false
}}

EMAIL SENDER:
{sender}

EMAIL SUBJECT:
{subject}

EMAIL BODY:
{body[:3000]}
"""
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_response = message.content[0].text
        data = _extract_json(raw_response)
        valid_statuses = {"saved", "applied", "interview", "offer", "rejected"}
        if data.get("status") not in valid_statuses:
            data["status"] = "applied"
        return data
    except Exception:
        return _heuristic_parse_email(subject, sender, body)


def analyze_resume(resume_text: str, job_description: str) -> dict:
    """
    Compares the user's resume against the job description.
    """
    client = get_anthropic_client()

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
    message = client.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_response = message.content[0].text
    try:
        return _extract_json(raw_response)
    except Exception:
        return {
            "match_score": 50,
            "matched_skills": [],
            "missing_skills": [],
            "section_feedback": {
                "experience": "Could not parse detailed feedback.",
                "skills": "Could not parse detailed feedback.",
                "education": "Could not parse detailed feedback.",
            },
            "summary": raw_response[:200] if raw_response else "Failed to parse analysis response.",
        }


def generate_cover_letter(
    resume_text: str, job_description: str, company: str, role: str
) -> str:
    """
    Generates a professional, tailored 3-paragraph cover letter.
    """
    client = get_anthropic_client()

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
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()
