from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Response
from backend.database import get_pool, close_pool
from backend.models import (
    JobCreate, JobResponse, JobStatusUpdate,
    AnalyzeRequest, CoverLetterRequest
)
from backend.ai import analyze_resume, generate_cover_letter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the startup and shutdown lifecycle events.
    Initializes the database pool at startup, and closes it on shutdown.
    """
    await get_pool()
    yield
    await close_pool()


# Initialize the FastAPI application
app = FastAPI(title="SmartApply API", lifespan=lifespan)


# ── Health check ──────────────────────────────────────────
@app.get("/health")
async def health():
    """
    Basic health check endpoint to verify if the server is running.
    """
    return {"status": "ok"}


# ── Create a job ──────────────────────────────────────────
@app.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(job: JobCreate):
    """
    Saves a new job application.
    Notice the parameters:
      - response_model=JobResponse: Automatically converts the SQL dictionary 
        result into our validated output Pydantic model.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO jobs (company, role, job_url, job_description, notes)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
            """, job.company, job.role, job.job_url,
                job.job_description, job.notes)
        return dict(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── List all jobs ─────────────────────────────────────────
@app.get("/jobs", response_model=list[JobResponse])
async def list_jobs(status: str = None):
    """
    Retrieves all job applications, optionally filtered by stage status.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    "SELECT * FROM jobs WHERE status=$1 ORDER BY applied_date DESC",
                    status
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM jobs ORDER BY applied_date DESC"
                )
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Update job status ─────────────────────────────────────
@app.patch("/jobs/{job_id}/status", response_model=JobResponse)
async def update_status(job_id: str, update: JobStatusUpdate):
    """
    Updates the Kanban pipeline stage of a job.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE jobs SET status=$1 WHERE id=$2 RETURNING *
            """, update.status, job_id)
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Delete a job ──────────────────────────────────────────
@app.delete("/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str):
    """
    Deletes a job application record.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM jobs WHERE id=$1", job_id
            )
        if result == "DELETE 0":
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
    Triggers Claude to evaluate a resume against a saved job description.
    Updates the job's match_score in the database and returns the feedback.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            job = await conn.fetchrow(
                "SELECT * FROM jobs WHERE id=$1", req.job_id
            )
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if not job["job_description"]:
            raise HTTPException(status_code=400,
                                detail="This job has no description saved")

        # Call the Claude API wrapper from ai.py
        result = analyze_resume(req.resume_text, job["job_description"])

        # Save the match score in the database
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE jobs SET match_score=$1 WHERE id=$2",
                result["match_score"], req.job_id
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Generate cover letter ─────────────────────────────────
@app.post("/cover-letter")
async def cover_letter(req: CoverLetterRequest):
    """
    Triggers Claude to write a customized cover letter.
    Saves the letter text to the database and returns it to the client.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            job = await conn.fetchrow(
                "SELECT * FROM jobs WHERE id=$1", req.job_id
            )
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if not job["job_description"]:
            raise HTTPException(status_code=400,
                                detail="This job has no description saved")

        # Call the Claude API wrapper from ai.py
        letter = generate_cover_letter(
            req.resume_text, job["job_description"],
            job["company"], job["role"]
        )

        # Save the cover letter to the database
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE jobs SET cover_letter=$1 WHERE id=$2",
                letter, req.job_id
            )
        return {"cover_letter": letter}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
