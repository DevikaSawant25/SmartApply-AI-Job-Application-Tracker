CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS jobs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company          TEXT NOT NULL,
    role             TEXT NOT NULL,
    job_url          TEXT,
    status           TEXT NOT NULL DEFAULT 'saved'
                     CHECK (status IN ('saved', 'applied', 'interview', 'offer', 'rejected')),
    job_description  TEXT,
    notes            TEXT,
    match_score      INTEGER,
    cover_letter     TEXT,
    applied_date     TIMESTAMP DEFAULT NOW()
);
