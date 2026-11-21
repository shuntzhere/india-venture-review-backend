-- Standalone fallback prerequisite; avoids enabling unrelated source workers.
BEGIN;
ALTER TABLE public.ingestion_runs
 ADD COLUMN IF NOT EXISTS duration_ms bigint,
 ADD COLUMN IF NOT EXISTS cpu_ms bigint,
 ADD COLUMN IF NOT EXISTS stages jsonb NOT NULL DEFAULT '{}'::jsonb,
 ADD COLUMN IF NOT EXISTS cache_refresh_status text;
COMMIT;
