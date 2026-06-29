-- =============================================================================
-- Migration: Add classification_confidence to funding_events
-- Compatible with: Supabase (PostgreSQL 15+)
-- Run this once in the Supabase SQL Editor after create_tables.sql has been
-- applied. Do not run create_tables.sql again — this migration extends the
-- existing schema with ALTER TABLE.
-- =============================================================================
--
-- Why this column exists:
--   The funding article classifier introduced in Step 3.2 evaluates each
--   article using multiple independent signals (funding keyword, funding
--   amount, investor phrase) and assigns a weighted score. The score is
--   mapped to a human-readable label: Strong, Moderate, or Weak.
--
-- Why it is operational metadata, not business data:
--   classification_confidence does not describe the funding event itself.
--   It describes the classifier's confidence at the time the article was
--   ingested. Its primary use case is operational: each morning, articles
--   can be reviewed and prioritised by confidence level before manual
--   research and content creation begins. The value may change if the
--   article is re-classified by a future classifier version.
--
-- Why it is nullable:
--   1. Existing rows in funding_events were inserted before the classifier
--      existed and have no classification assessment. Requiring a value
--      would make this migration impossible without backfilling every row.
--   2. Future classifier versions may not populate this field immediately
--      during a migration period, so NULL must remain a valid state.
--   3. NULL has a clear semantic meaning here: "not yet assessed by the
--      classifier" — distinct from Weak, which means "assessed and low
--      confidence".
-- =============================================================================

ALTER TABLE funding_events
    ADD COLUMN  classification_confidence  TEXT,
    ADD CONSTRAINT funding_events_classification_confidence_check
        CHECK (classification_confidence IN ('Strong', 'Moderate', 'Weak'));

-- =============================================================================
-- PostgreSQL CHECK constraint behaviour with NULL:
--   An IN (...) constraint evaluates to NULL (not FALSE) when the column
--   value is NULL. PostgreSQL only rejects a row when a CHECK constraint
--   evaluates to FALSE — NULL is treated as passing. This means NULL values
--   are permitted by the constraint above without needing to write an
--   explicit OR ... IS NULL clause.
-- =============================================================================
