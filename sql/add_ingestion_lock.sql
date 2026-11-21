-- Prevent overlapping hosted ingestion runs without changing business data.
-- Run once in the Supabase SQL Editor before deploying the hardened endpoint.

CREATE TABLE IF NOT EXISTS ingestion_locks (
    lock_name         TEXT PRIMARY KEY,
    locked_by         TEXT NOT NULL,
    lease_expires_at  TIMESTAMPTZ NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION acquire_ingestion_lock(
    p_lock_name TEXT,
    p_locked_by TEXT,
    p_lease_seconds INTEGER
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    acquired BOOLEAN;
BEGIN
    IF p_lease_seconds < 1 OR p_lease_seconds > 3600 THEN
        RAISE EXCEPTION 'lease duration must be between 1 and 3600 seconds';
    END IF;

    INSERT INTO ingestion_locks (lock_name, locked_by, lease_expires_at, updated_at)
    VALUES (p_lock_name, p_locked_by, now() + make_interval(secs => p_lease_seconds), now())
    ON CONFLICT (lock_name) DO UPDATE
        SET locked_by = EXCLUDED.locked_by,
            lease_expires_at = EXCLUDED.lease_expires_at,
            updated_at = now()
        WHERE ingestion_locks.lease_expires_at <= now()
    RETURNING TRUE INTO acquired;

    RETURN COALESCE(acquired, FALSE);
END;
$$;

CREATE OR REPLACE FUNCTION release_ingestion_lock(
    p_lock_name TEXT,
    p_locked_by TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    released BOOLEAN;
BEGIN
    UPDATE ingestion_locks
       SET lease_expires_at = now(), updated_at = now()
     WHERE lock_name = p_lock_name
       AND locked_by = p_locked_by
    RETURNING TRUE INTO released;

    RETURN COALESCE(released, FALSE);
END;
$$;

REVOKE ALL ON FUNCTION acquire_ingestion_lock(TEXT, TEXT, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION release_ingestion_lock(TEXT, TEXT) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION acquire_ingestion_lock(TEXT, TEXT, INTEGER)
    TO service_role;
GRANT EXECUTE ON FUNCTION release_ingestion_lock(TEXT, TEXT)
    TO service_role;
