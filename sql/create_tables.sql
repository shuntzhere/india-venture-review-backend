-- =============================================================================
-- India Venture Review — Initial Schema
-- Compatible with: Supabase (PostgreSQL 15+)
-- Run this once in the Supabase SQL Editor to create all tables and indexes.
-- =============================================================================


-- =============================================================================
-- TRIGGER FUNCTION: auto-update updated_at on any row change
-- Created once here and reused by any table that needs it.
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- TABLE: companies
-- One row per startup. The scraper creates a company record the first time it
-- encounters a startup and links all future funding events back to it.
--
-- Design notes:
--   - company_name is NOT unique: two startups can share a name (rare but real).
--     Deduplication is handled at the application layer using fuzzy matching.
--   - total_funding is maintained by the application by summing funding_events.
--     It is not scraped directly.
--   - sub_industry is intentionally left nullable. It will not be populated
--     during initial ingestion and is reserved for manual curation or AI
--     enrichment in a later milestone.
--   - TIMESTAMPTZ is used for all timestamps so values are stored as UTC and
--     display correctly regardless of the local timezone of the scraper host.
-- =============================================================================

CREATE TABLE IF NOT EXISTS companies (
    id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name            TEXT            NOT NULL,
    website                 TEXT,
    linkedin_url            TEXT,
    logo_url                TEXT,
    description             TEXT,
    industry                TEXT,
    sub_industry            TEXT,                       -- populated later via enrichment, not during scraping
    business_model          TEXT,
    headquarters_city       TEXT,
    headquarters_state      TEXT,
    headquarters_country    TEXT,
    founded_year            INTEGER,
    founders                TEXT,                       -- stored as plain text for MVP (e.g. "Rahul Mehta, Priya Singh")
    employee_count          INTEGER,
    total_funding           NUMERIC,                    -- maintained by application, not scraped directly
    latest_funding_round    TEXT,
    latest_funding_amount   NUMERIC,
    first_seen_date         DATE            NOT NULL,
    created_at              TIMESTAMPTZ     NOT NULL    DEFAULT now(),
    updated_at              TIMESTAMPTZ     NOT NULL    DEFAULT now()
);

-- Trigger: keep updated_at current whenever a companies row is modified
CREATE OR REPLACE TRIGGER companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Index: the most common lookup — finding a company by name
CREATE INDEX IF NOT EXISTS idx_companies_company_name
    ON companies (company_name);

-- Index: filtering by industry for analytics queries
CREATE INDEX IF NOT EXISTS idx_companies_industry
    ON companies (industry);


-- =============================================================================
-- TABLE: funding_events
-- One row per funding announcement. Each event is linked to a company.
--
-- Design notes:
--   - article_url is UNIQUE NOT NULL. This is the natural deduplication key:
--     if the scraper runs multiple times, it cannot insert the same article
--     twice. The application should use INSERT ... ON CONFLICT DO NOTHING.
--   - company_id uses ON DELETE RESTRICT. Deleting a company is blocked if
--     funding events exist, preventing accidental data loss.
--   - lead_investors and participating_investors are stored as plain text for
--     MVP simplicity. A separate investors table is a future milestone.
--   - article_summary will not be scraped. It is reserved for manual entry or
--     AI-generated summaries in a later milestone.
--   - source_name is plain text (e.g. "Entrackr"). A sources table is a future
--     milestone; normalising it now would add complexity with no current benefit.
--   - scraped_timestamp records when the scraper fetched the article.
--     created_at records when the row was inserted into the database.
--     These can differ if there is a processing delay, so both are kept.
-- =============================================================================

CREATE TABLE IF NOT EXISTS funding_events (
    id                          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id                  UUID        NOT NULL
                                            REFERENCES companies (id)
                                            ON DELETE RESTRICT,
    funding_amount              NUMERIC,
    currency                    TEXT,
    funding_round               TEXT,
    lead_investors              TEXT,                   -- plain text for MVP (e.g. "Sequoia Capital")
    participating_investors     TEXT,                   -- plain text for MVP (e.g. "Accel, Elevation Capital")
    valuation                   NUMERIC,
    article_title               TEXT,
    article_summary             TEXT,                   -- not scraped; reserved for AI enrichment
    article_publication_date    DATE,
    article_url                 TEXT        UNIQUE NOT NULL,
    source_name                 TEXT        NOT NULL,   -- plain text for MVP (e.g. "Entrackr")
    scraped_timestamp           TIMESTAMPTZ NOT NULL,
    created_at                  TIMESTAMPTZ NOT NULL    DEFAULT now()
);

-- Index: the primary join — looking up all events for a company
CREATE INDEX IF NOT EXISTS idx_funding_events_company_id
    ON funding_events (company_id);

-- Index: date-range queries (e.g. "all deals this month")
CREATE INDEX IF NOT EXISTS idx_funding_events_article_publication_date
    ON funding_events (article_publication_date);

-- Index: filtering or grouping by source (useful once multiple sources are added)
CREATE INDEX IF NOT EXISTS idx_funding_events_source_name
    ON funding_events (source_name);
