-- S3.2 Migration: Create eventos_job table for real-time job progress streaming
--
-- Purpose: Track job lifecycle events (created, started, progress, completed, failed)
-- for WebSocket streaming to frontend without polling.
--
-- Run with: psql $DATABASE_URL -f migrations/003_create_eventos_job.sql

BEGIN;

-- Main events table
CREATE TABLE IF NOT EXISTS eventos_job (
    event_id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    job_id BIGINT,
    evento VARCHAR(50) NOT NULL,  -- 'created', 'started', 'progress', 'completed', 'failed'
    data_json JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT evento_valid CHECK (evento IN ('created', 'started', 'progress', 'completed', 'failed'))
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_eventos_job_run_id_timestamp
    ON eventos_job (run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_eventos_job_job_id
    ON eventos_job (job_id);

CREATE INDEX IF NOT EXISTS idx_eventos_job_evento
    ON eventos_job (evento);

-- Comments for clarity
COMMENT ON TABLE eventos_job IS 'Job execution events for real-time progress tracking';
COMMENT ON COLUMN eventos_job.run_id IS 'Unique execution identifier (links to consultas or runs table)';
COMMENT ON COLUMN eventos_job.job_id IS 'Procrastinate job ID (from procrastinate_jobs.id)';
COMMENT ON COLUMN eventos_job.evento IS 'Event type: created, started, progress, completed, failed';
COMMENT ON COLUMN eventos_job.data_json IS 'Event-specific metadata (progress %, error details, etc.)';

COMMIT;
