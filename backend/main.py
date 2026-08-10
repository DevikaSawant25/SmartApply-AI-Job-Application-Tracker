import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from backend.database import (
    init_db,
    close_db,
    insert_job,
    list_jobs,
    get_job_by_id,
    update_job_status,
    update_job_score,
    update_job_cover_letter,
    delete_job,
    get_email_logs,
)
from backend.models import (
    JobCreate,
    JobResponse,
    JobStatusUpdate,
    AnalyzeRequest,
    CoverLetterRequest,
    RawEmailParseRequest,
)
from backend.ai import analyze_resume, generate_cover_letter
from backend.email_sync import process_email_content, fetch_and_sync_imap_emails


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages startup and shutdown lifecycle events.
    Initializes the database and creates tables automatically.
    """
    await init_db()
    yield
    await close_db()


# Initialize the FastAPI application
app = FastAPI(title="SmartApply API", lifespan=lifespan)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health check ──────────────────────────────────────────
@app.get("/health")
async def health():
    """Basic health check endpoint to verify server is running."""
    return {"status": "ok", "service": "SmartApply API"}


# ── Create a job ──────────────────────────────────────────
@app.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job_endpoint(job: JobCreate):
    """Saves a new job application."""
    try:
        created = await insert_job(
            company=job.company,
            role=job.role,
            job_url=job.job_url,
            job_description=job.job_description,
            notes=job.notes,
        )
        return created
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── List all jobs ─────────────────────────────────────────
@app.get("/jobs", response_model=list[JobResponse])
async def list_jobs_endpoint(status: Optional[str] = Query(default=None)):
    """Retrieves all job applications, optionally filtered by status."""
    try:
        rows = await list_jobs(status=status)
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Get single job ────────────────────────────────────────
@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_endpoint(job_id: str):
    """Retrieves a single job application by ID."""
    try:
        job = await get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Update job status ─────────────────────────────────────
@app.patch("/jobs/{job_id}/status", response_model=JobResponse)
async def update_status_endpoint(job_id: str, update: JobStatusUpdate):
    """Updates the pipeline status of a job."""
    valid_statuses = {"saved", "applied", "interview", "offer", "rejected"}
    if update.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{update.status}'. Must be one of: {', '.join(valid_statuses)}",
        )

    try:
        updated = await update_job_status(job_id, update.status)
        if not updated:
            raise HTTPException(status_code=404, detail="Job not found")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Delete a job ──────────────────────────────────────────
@app.delete("/jobs/{job_id}", status_code=204)
async def delete_job_endpoint(job_id: str):
    """Deletes a job application record."""
    try:
        success = await delete_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")
        return Response(status_code=204)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Analyze resume vs JD ──────────────────────────────────
@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """
    Evaluates resume against job description using Claude.
    Updates match_score and returns feedback.
    """
    if not req.resume_text.strip():
        raise HTTPException(status_code=400, detail="Resume text cannot be empty")

    try:
        job = await get_job_by_id(req.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if not job.get("job_description") or not job["job_description"].strip():
            raise HTTPException(
                status_code=400, detail="This job has no description saved"
            )

        # Call Claude API wrapper
        result = analyze_resume(req.resume_text, job["job_description"])

        # Update database with match score
        if "match_score" in result:
            await update_job_score(req.job_id, result["match_score"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Generate cover letter ─────────────────────────────────
@app.post("/cover-letter")
async def cover_letter(req: CoverLetterRequest):
    """
    Generates a tailored cover letter using Claude.
    Saves to database and returns to client.
    """
    if not req.resume_text.strip():
        raise HTTPException(status_code=400, detail="Resume text cannot be empty")

    try:
        job = await get_job_by_id(req.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if not job.get("job_description") or not job["job_description"].strip():
            raise HTTPException(
                status_code=400, detail="This job has no description saved"
            )

        # Call Claude API wrapper
        letter = generate_cover_letter(
            req.resume_text,
            job["job_description"],
            job["company"],
            job["role"],
        )

        # Save to database
        await update_job_cover_letter(req.job_id, letter)

        return {"cover_letter": letter}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Automated Email Ingestion Endpoints ────────────────────

@app.post("/emails/parse-raw")
async def parse_raw_email_endpoint(req: RawEmailParseRequest):
    """
    Directly parses raw email content and updates/creates the corresponding application.
    Useful for quick manual pasting, test sandbox, or inbound email webhooks.
    """
    if not req.body.strip():
        raise HTTPException(status_code=400, detail="Email body cannot be empty.")

    try:
        result = await process_email_content(
            subject=req.subject,
            sender=req.sender,
            body=req.body,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/emails/sync")
async def sync_emails_endpoint(limit: int = Query(default=10, ge=1, le=50)):
    """
    Fetches recent emails from the configured IMAP inbox, evaluates them with Claude,
    and updates/creates job applications in SmartApply.
    """
    try:
        # Run IMAP network fetch in background thread to avoid blocking event loop
        fetched_emails = await asyncio.to_thread(fetch_and_sync_imap_emails, limit)
        if not fetched_emails:
            return {"status": "success", "processed_count": 0, "actions": [], "message": "No emails found or processed."}

        actions = []
        for em in fetched_emails:
            res = await process_email_content(
                subject=em["subject"],
                sender=em["sender"],
                body=em["body"],
                email_id=em["email_id"],
            )
            actions.append(res)

        return {
            "status": "success",
            "processed_count": len(fetched_emails),
            "actions": actions,
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/emails/logs")
async def get_email_logs_endpoint(limit: int = Query(default=30, ge=1, le=100)):
    """Returns recent email sync and processing history."""
    try:
        logs = await get_email_logs(limit=limit)
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
