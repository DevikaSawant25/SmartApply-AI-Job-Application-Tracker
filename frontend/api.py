import os
from typing import Optional, List, Dict, Any
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
DEFAULT_TIMEOUT = 10.0
AI_TIMEOUT = 60.0


class APIError(Exception):
    """Custom exception for API errors with status code and detail message."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _handle_response(response: httpx.Response) -> Any:
    """Helper to check response status and extract JSON or raise APIError."""
    try:
        response.raise_for_status()
        if response.status_code == 204:
            return True
        return response.json()
    except httpx.HTTPStatusError as e:
        detail = "Unknown error"
        try:
            body = response.json()
            detail = body.get("detail", str(body))
        except Exception:
            detail = response.text or str(e)
        raise APIError(f"API Error ({response.status_code}): {detail}", status_code=response.status_code)
    except httpx.RequestError as e:
        raise APIError(f"Could not connect to backend at {BASE_URL}. Is the server running? Details: {e}")


def check_health() -> bool:
    """Checks if the FastAPI backend service is reachable and responding."""
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{BASE_URL}/health")
            return resp.status_code == 200
    except Exception:
        return False


def get_jobs(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches list of job applications, optionally filtered by status."""
    params = {"status": status} if status else {}
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.get(f"{BASE_URL}/jobs", params=params)
            return _handle_response(resp)
    except httpx.RequestError as e:
        raise APIError(f"Failed to fetch jobs: {e}")


def get_job(job_id: str) -> Dict[str, Any]:
    """Fetches single job application by ID."""
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.get(f"{BASE_URL}/jobs/{job_id}")
            return _handle_response(resp)
    except httpx.RequestError as e:
        raise APIError(f"Failed to fetch job {job_id}: {e}")


def create_job(
    company: str,
    role: str,
    job_url: Optional[str] = None,
    job_description: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Creates a new job application."""
    payload = {
        "company": company.strip(),
        "role": role.strip(),
        "job_url": job_url.strip() if job_url else None,
        "job_description": job_description.strip() if job_description else None,
        "notes": notes.strip() if notes else None,
    }
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.post(f"{BASE_URL}/jobs", json=payload)
            return _handle_response(resp)
    except httpx.RequestError as e:
        raise APIError(f"Failed to create job: {e}")


def update_job_status(job_id: str, status: str) -> Dict[str, Any]:
    """Updates the pipeline status of a job."""
    payload = {"status": status}
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.patch(f"{BASE_URL}/jobs/{job_id}/status", json=payload)
            return _handle_response(resp)
    except httpx.RequestError as e:
        raise APIError(f"Failed to update job status: {e}")


def delete_job(job_id: str) -> bool:
    """Deletes a job application record."""
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.delete(f"{BASE_URL}/jobs/{job_id}")
            return _handle_response(resp)
    except httpx.RequestError as e:
        raise APIError(f"Failed to delete job: {e}")


def analyze_resume(job_id: str, resume_text: str) -> Dict[str, Any]:
    """Sends resume text and job ID to backend for AI fit analysis."""
    payload = {"job_id": str(job_id), "resume_text": resume_text}
    try:
        with httpx.Client(timeout=AI_TIMEOUT) as client:
            resp = client.post(f"{BASE_URL}/analyze", json=payload)
            return _handle_response(resp)
    except httpx.RequestError as e:
        raise APIError(f"Failed to run resume analysis: {e}")


def generate_cover_letter(job_id: str, resume_text: str) -> str:
    """Sends resume text and job ID to backend to generate tailored cover letter."""
    payload = {"job_id": str(job_id), "resume_text": resume_text}
    try:
        with httpx.Client(timeout=AI_TIMEOUT) as client:
            resp = client.post(f"{BASE_URL}/cover-letter", json=payload)
            data = _handle_response(resp)
            return data.get("cover_letter", "")
    except httpx.RequestError as e:
        raise APIError(f"Failed to generate cover letter: {e}")


# ── Email Automation API Methods ──────────────────────────

def parse_raw_email(body: str, subject: str = "Job Application", sender: str = "careers@company.com") -> Dict[str, Any]:
    """Sends raw email content to backend for Claude AI parsing and DB update."""
    payload = {
        "subject": subject.strip() if subject else "Job Application",
        "sender": sender.strip() if sender else "careers@company.com",
        "body": body.strip(),
    }
    try:
        with httpx.Client(timeout=AI_TIMEOUT) as client:
            resp = client.post(f"{BASE_URL}/emails/parse-raw", json=payload)
            return _handle_response(resp)
    except httpx.RequestError as e:
        raise APIError(f"Failed to parse email: {e}")


def sync_inbox_emails(limit: int = 10) -> Dict[str, Any]:
    """Triggers IMAP inbox synchronization on backend."""
    try:
        with httpx.Client(timeout=AI_TIMEOUT) as client:
            resp = client.post(f"{BASE_URL}/emails/sync", params={"limit": limit})
            return _handle_response(resp)
    except httpx.RequestError as e:
        raise APIError(f"Inbox sync failed: {e}")


def get_email_logs(limit: int = 30) -> List[Dict[str, Any]]:
    """Fetches recent email sync activity logs."""
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            resp = client.get(f"{BASE_URL}/emails/logs", params={"limit": limit})
            return _handle_response(resp)
    except httpx.RequestError as e:
        raise APIError(f"Failed to fetch email logs: {e}")
