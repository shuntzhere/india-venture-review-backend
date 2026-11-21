-- Durable operational telemetry for hosted ingestion. Run manually only after
-- review; this table is intentionally separate from company and funding data.

BEGIN;

-- Existing IVR UUID-backed tables use this function. Fail atomically rather
-- than changing extension state if it is unexpectedly unavailable.
DO $$
BEGIN
    IF to_regprocedure('gen_random_uuid()') IS NULL THEN
        RAISE EXCEPTION
            'gen_random_uuid() is unavailable; verify the existing IVR UUID setup before applying this migration';
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                  TEXT UNIQUE NOT NULL,
    started_at              TIMESTAMPTZ NOT NULL,
    completed_at            TIMESTAMPTZ,
    status                  TEXT NOT NULL,
    trigger                 TEXT NOT NULL,
    source_name             TEXT,
    sources_attempted       INTEGER NOT NULL DEFAULT 0,
    articles_fetched        INTEGER NOT NULL DEFAULT 0,
    new_articles            INTEGER NOT NULL DEFAULT 0,
    relevance_passes        INTEGER NOT NULL DEFAULT 0,
    confirmed               INTEGER NOT NULL DEFAULT 0,
    prospective             INTEGER NOT NULL DEFAULT 0,
    unknown                 INTEGER NOT NULL DEFAULT 0,
    funding_events_created  INTEGER NOT NULL DEFAULT 0,
    event_sources_attached  INTEGER NOT NULL DEFAULT 0,
    event_conflicts_flagged INTEGER NOT NULL DEFAULT 0,
    companies_created       INTEGER NOT NULL DEFAULT 0,
    companies_reused        INTEGER NOT NULL DEFAULT 0,
    duplicates_skipped      INTEGER NOT NULL DEFAULT 0,
    extraction_errors       INTEGER NOT NULL DEFAULT 0,
    database_errors         INTEGER NOT NULL DEFAULT 0,
    error_details           JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ingestion_runs_started_at
    ON ingestion_runs (started_at);

ALTER TABLE ingestion_runs ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE ingestion_runs FROM PUBLIC;
REVOKE ALL ON TABLE ingestion_runs FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON TABLE ingestion_runs TO service_role;

COMMIT;
