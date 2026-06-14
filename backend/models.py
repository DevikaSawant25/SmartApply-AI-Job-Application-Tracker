from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

# --- Input Models (What the client sends to the server) ---

class JobCreate(BaseModel):
    """
    Schema for creating a new job application.
    Notice that 'id', 'status', and 'applied_date' are missing 
    because the database handles generating them.
    """
    company: str
    role: str
    job_url: Optional[str] = None
    job_description: Optional[str] = None
    notes: Optional[str] = None

class JobStatusUpdate(BaseModel):
    """
    Schema for updating only the pipeline status of a job.
    """
    status: str

class AnalyzeRequest(BaseModel):
    """
    Schema for requesting resume analysis.
    Requires the job database ID and the raw resume text.
    """
    job_id: str
    resume_text: str

class CoverLetterRequest(BaseModel):
    """
    Schema for requesting cover letter generation.
    Requires the job database ID and the raw resume text.
    """
    job_id: str
    resume_text: str


# --- Output Models (What the server sends back to the client) ---

class JobResponse(BaseModel):
    """
    Schema representing a complete job application record.
    FastAPI will automatically serialize database rows matching this structure.
    """
    id: uuid.UUID
    company: str
    role: str
    job_url: Optional[str] = None
    status: str
    job_description: Optional[str] = None
    notes: Optional[str] = None
    match_score: Optional[int] = None
    cover_letter: Optional[str] = None
    applied_date: datetime
