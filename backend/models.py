from pydantic import BaseModel
from typing import Optional, Union
from datetime import datetime
import uuid

# --- Input Models (What the client sends to the server) ---

class JobCreate(BaseModel):
    company: str
    role: str
    job_url: Optional[str] = None
    job_description: Optional[str] = None
    notes: Optional[str] = None

class JobStatusUpdate(BaseModel):
    status: str

class AnalyzeRequest(BaseModel):
    job_id: str
    resume_text: str

class CoverLetterRequest(BaseModel):
    job_id: str
    resume_text: str

class RawEmailParseRequest(BaseModel):
    subject: str = "Application Confirmation"
    sender: str = "careers@company.com"
    body: str


# --- Output Models (What the server sends back to the client) ---

class JobResponse(BaseModel):
    id: Union[uuid.UUID, str]
    company: str
    role: str
    job_url: Optional[str] = None
    status: str
    job_description: Optional[str] = None
    notes: Optional[str] = None
    match_score: Optional[int] = None
    cover_letter: Optional[str] = None
    applied_date: Optional[Union[datetime, str]] = None
