import os
import uuid
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import aiosqlite
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DB_DIR = Path(__file__).resolve().parent.parent / "database"
SQLITE_DB_PATH = DB_DIR / "smartapply.db"

# Connection handles
_pg_pool: Optional[asyncpg.Pool] = None
_db_engine = "sqlite"  # 'postgres' or 'sqlite'


async def init_db():
    """
    Initializes the database connection.
    Attempts PostgreSQL if configured, otherwise falls back to SQLite.
    Automatically creates the jobs and email_logs tables if missing.
    """
    global _pg_pool, _db_engine

    db_url = os.getenv("DATABASE_URL", "").strip()

    if db_url.startswith(("postgresql://", "postgres://")) and "yourpassword" not in db_url:
        try:
            _pg_pool = await asyncpg.create_pool(db_url, timeout=5.0)
            _db_engine = "postgres"
            async with _pg_pool.acquire() as conn:
                await conn.execute(
                    """
                    CREATE EXTENSION IF NOT EXISTS "pgcrypto";
                    CREATE TABLE IF NOT EXISTS jobs (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        company TEXT NOT NULL,
                        role TEXT NOT NULL,
                        job_url TEXT,
                        status TEXT NOT NULL DEFAULT 'saved'
                               CHECK (status IN ('saved', 'applied', 'interview', 'offer', 'rejected')),
                        job_description TEXT,
                        notes TEXT,
                        match_score INTEGER,
                        cover_letter TEXT,
                        applied_date TIMESTAMP DEFAULT NOW()
                    );
                    CREATE TABLE IF NOT EXISTS email_logs (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        email_id TEXT UNIQUE,
                        sender TEXT,
                        subject TEXT,
                        company TEXT,
                        role TEXT,
                        detected_status TEXT,
                        summary TEXT,
                        action_taken TEXT,
                        processed_at TIMESTAMP DEFAULT NOW()
                    );
                    """
                )
            print("Connected to PostgreSQL database successfully.")
            return
        except Exception as e:
            print(f"PostgreSQL connection failed ({e}). Falling back to local SQLite.")

    # Fallback / Default: SQLite
    _db_engine = "sqlite"
    DB_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(SQLITE_DB_PATH)) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                company TEXT NOT NULL,
                role TEXT NOT NULL,
                job_url TEXT,
                status TEXT NOT NULL DEFAULT 'saved',
                job_description TEXT,
                notes TEXT,
                match_score INTEGER,
                cover_letter TEXT,
                applied_date TEXT
            );
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS email_logs (
                id TEXT PRIMARY KEY,
                email_id TEXT UNIQUE,
                sender TEXT,
                subject TEXT,
                company TEXT,
                role TEXT,
                detected_status TEXT,
                summary TEXT,
                action_taken TEXT,
                processed_at TEXT
            );
            """
        )
        await db.commit()
    print(f"Using local SQLite database at: {SQLITE_DB_PATH}")


async def close_db():
    """Closes active database connections/pools."""
    global _pg_pool
    if _pg_pool:
        await _pg_pool.close()
        _pg_pool = None


async def insert_job(
    company: str,
    role: str,
    job_url: Optional[str] = None,
    job_description: Optional[str] = None,
    notes: Optional[str] = None,
    status: str = "saved",
) -> Dict[str, Any]:
    global _pg_pool, _db_engine

    if _db_engine == "postgres" and _pg_pool:
        async with _pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO jobs (company, role, job_url, status, job_description, notes)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                company,
                role,
                job_url,
                status,
                job_description,
                notes,
            )
            return dict(row)

    # SQLite implementation
    job_id = str(uuid.uuid4())
    applied_date = datetime.datetime.now(datetime.timezone.utc).isoformat()
    async with aiosqlite.connect(str(SQLITE_DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            """
            INSERT INTO jobs (id, company, role, job_url, status, job_description, notes, match_score, cover_letter, applied_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            """,
            (job_id, company, role, job_url, status, job_description, notes, applied_date),
        )
        await db.commit()
        async with db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else {}


async def list_jobs(status: Optional[str] = None) -> List[Dict[str, Any]]:
    global _pg_pool, _db_engine

    if _db_engine == "postgres" and _pg_pool:
        async with _pg_pool.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    "SELECT * FROM jobs WHERE status=$1 ORDER BY applied_date DESC",
                    status,
                )
            else:
                rows = await conn.fetch("SELECT * FROM jobs ORDER BY applied_date DESC")
            return [dict(r) for r in rows]

    # SQLite implementation
    async with aiosqlite.connect(str(SQLITE_DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        if status:
            async with db.execute(
                "SELECT * FROM jobs WHERE status=? ORDER BY applied_date DESC", (status,)
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute("SELECT * FROM jobs ORDER BY applied_date DESC") as cursor:
                rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    global _pg_pool, _db_engine

    if _db_engine == "postgres" and _pg_pool:
        try:
            job_uuid = uuid.UUID(str(job_id))
        except ValueError:
            return None
        async with _pg_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM jobs WHERE id=$1", job_uuid)
            return dict(row) if row else None

    # SQLite implementation
    async with aiosqlite.connect(str(SQLITE_DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM jobs WHERE id=?", (str(job_id),)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_job_status(job_id: str, status: str) -> Optional[Dict[str, Any]]:
    global _pg_pool, _db_engine

    if _db_engine == "postgres" and _pg_pool:
        job_uuid = uuid.UUID(str(job_id))
        async with _pg_pool.acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE jobs SET status=$1 WHERE id=$2 RETURNING *",
                status,
                job_uuid,
            )
            return dict(row) if row else None

    # SQLite implementation
    async with aiosqlite.connect(str(SQLITE_DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE jobs SET status=? WHERE id=?",
            (status, str(job_id)),
        )
        await db.commit()
        async with db.execute("SELECT * FROM jobs WHERE id=?", (str(job_id),)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_job_score(job_id: str, score: int) -> None:
    global _pg_pool, _db_engine

    if _db_engine == "postgres" and _pg_pool:
        job_uuid = uuid.UUID(str(job_id))
        async with _pg_pool.acquire() as conn:
            await conn.execute(
                "UPDATE jobs SET match_score=$1 WHERE id=$2",
                score,
                job_uuid,
            )
        return

    # SQLite implementation
    async with aiosqlite.connect(str(SQLITE_DB_PATH)) as db:
        await db.execute(
            "UPDATE jobs SET match_score=? WHERE id=?",
            (score, str(job_id)),
        )
        await db.commit()


async def update_job_cover_letter(job_id: str, letter: str) -> None:
    global _pg_pool, _db_engine

    if _db_engine == "postgres" and _pg_pool:
        job_uuid = uuid.UUID(str(job_id))
        async with _pg_pool.acquire() as conn:
            await conn.execute(
                "UPDATE jobs SET cover_letter=$1 WHERE id=$2",
                letter,
                job_uuid,
            )
        return

    # SQLite implementation
    async with aiosqlite.connect(str(SQLITE_DB_PATH)) as db:
        await db.execute(
            "UPDATE jobs SET cover_letter=? WHERE id=?",
            (letter, str(job_id)),
        )
        await db.commit()


async def delete_job(job_id: str) -> bool:
    global _pg_pool, _db_engine

    if _db_engine == "postgres" and _pg_pool:
        job_uuid = uuid.UUID(str(job_id))
        async with _pg_pool.acquire() as conn:
            result = await conn.execute("DELETE FROM jobs WHERE id=$1", job_uuid)
            return result != "DELETE 0"

    # SQLite implementation
    async with aiosqlite.connect(str(SQLITE_DB_PATH)) as db:
        cursor = await db.execute("DELETE FROM jobs WHERE id=?", (str(job_id),))
        await db.commit()
        return cursor.rowcount > 0


# ── Email Logging & Job Matching ────────────────────────────

async def is_email_processed(email_id: str) -> bool:
    """Checks if an email UID has already been parsed and logged."""
    if not email_id:
        return False
    global _pg_pool, _db_engine

    if _db_engine == "postgres" and _pg_pool:
        async with _pg_pool.acquire() as conn:
            val = await conn.fetchval("SELECT 1 FROM email_logs WHERE email_id=$1", str(email_id))
            return val is not None

    async with aiosqlite.connect(str(SQLITE_DB_PATH)) as db:
        async with db.execute("SELECT 1 FROM email_logs WHERE email_id=?", (str(email_id),)) as cursor:
            row = await cursor.fetchone()
            return row is not None


async def log_email_action(
    email_id: Optional[str],
    sender: str,
    subject: str,
    company: Optional[str],
    role: Optional[str],
    detected_status: Optional[str],
    summary: str,
    action_taken: str,
) -> None:
    """Records an email processing event in email_logs."""
    global _pg_pool, _db_engine
    log_id = str(uuid.uuid4())
    processed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if _db_engine == "postgres" and _pg_pool:
        async with _pg_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO email_logs (id, email_id, sender, subject, company, role, detected_status, summary, action_taken)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (email_id) DO NOTHING
                """,
                uuid.UUID(log_id),
                email_id,
                sender,
                subject,
                company,
                role,
                detected_status,
                summary,
                action_taken,
            )
        return

    async with aiosqlite.connect(str(SQLITE_DB_PATH)) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO email_logs (id, email_id, sender, subject, company, role, detected_status, summary, action_taken, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (log_id, email_id, sender, subject, company, role, detected_status, summary, action_taken, processed_at),
        )
        await db.commit()


async def get_email_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves recent email synchronization records."""
    global _pg_pool, _db_engine

    if _db_engine == "postgres" and _pg_pool:
        async with _pg_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM email_logs ORDER BY processed_at DESC LIMIT $1", limit)
            return [dict(r) for r in rows]

    async with aiosqlite.connect(str(SQLITE_DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM email_logs ORDER BY processed_at DESC LIMIT ?", (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def find_or_create_job_from_email(
    company: str,
    role: str,
    status: str,
    summary: str,
    sender: str,
) -> Dict[str, Any]:
    """
    Looks for an existing job by company name.
    If found, updates the stage (e.g. saved -> applied, applied -> interview) and adds a note.
    If not found, creates a new job record with the detected status.
    """
    company_clean = (company or "").strip()
    role_clean = (role or "Applicant").strip()
    timestamp_str = datetime.datetime.now().strftime("%b %d, %Y %I:%M %p")

    # Fetch all jobs to find matches
    all_jobs = await list_jobs()
    matched_job = None
    for j in all_jobs:
        if j.get("company", "").strip().lower() == company_clean.lower():
            matched_job = j
            break

    if matched_job:
        job_id = str(matched_job["id"])
        existing_notes = matched_job.get("notes") or ""
        new_note_entry = f"[{timestamp_str} Email Sync]: {summary}"
        updated_notes = f"{existing_notes}\n{new_note_entry}".strip()

        # Update status and notes
        global _pg_pool, _db_engine
        if _db_engine == "postgres" and _pg_pool:
            async with _pg_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "UPDATE jobs SET status=$1, notes=$2 WHERE id=$3 RETURNING *",
                    status,
                    updated_notes,
                    uuid.UUID(job_id),
                )
                return {"action": "updated", "job": dict(row)}
        else:
            async with aiosqlite.connect(str(SQLITE_DB_PATH)) as db:
                db.row_factory = aiosqlite.Row
                await db.execute(
                    "UPDATE jobs SET status=?, notes=? WHERE id=?",
                    (status, updated_notes, job_id),
                )
                await db.commit()
                async with db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)) as cursor:
                    row = await cursor.fetchone()
                    return {"action": "updated", "job": dict(row) if row else {}}

    # If no existing job was found, create a new one
    note_content = f"[Auto-detected from Email ({sender}) on {timestamp_str}]: {summary}"
    created_job = await insert_job(
        company=company_clean,
        role=role_clean,
        job_url=None,
        job_description=None,
        notes=note_content,
        status=status,
    )
    return {"action": "created", "job": created_job}
