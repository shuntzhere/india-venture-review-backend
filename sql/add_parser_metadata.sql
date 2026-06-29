-- =============================================================================
-- Migration: Add parser metadata columns to funding_events
-- Compatible with: Supabase (PostgreSQL 15+)
-- Run this once in the Supabase SQL Editor after add_classification_confidence.sql
-- has been applied. Do not modify any existing SQL files.
-- =============================================================================
--
-- Why these columns exist:
--   The Evidence Extraction Engine (Step 4) produces a validation report
--   alongside each structured funding record. Two fields from that report
--   need to be persisted so that the morning curation workflow can prioritise
--   records for manual review without re-running the pipeline.
--
-- manual_review_required (BOOLEAN, nullable):
--   Set to TRUE when the extraction engine could not confidently extract one
--   or more primary business fields (company name, funding amount, funding
--   round, lead investors), or when a retrieval or parsing error occurred.
--   NULL means the record has not yet been evaluated.
--
-- manual_review_reason (TEXT, nullable):
--   Human-readable description of why manual review is recommended. Contains
--   one or more reasons joined by "; " when multiple issues were detected.
--   NULL when manual review is not required.
--
-- Note: classification_confidence was already added in add_classification_confidence.sql
-- (Step 2.3). Do not attempt to add it again.
-- =============================================================================

ALTER TABLE funding_events
    ADD COLUMN manual_review_required  BOOLEAN,
    ADD COLUMN manual_review_reason    TEXT;

-- =============================================================================
-- Verification queries (run after applying this migration):
--
--   SELECT column_name, data_type, is_nullable
--   FROM information_schema.columns
--   WHERE table_name = 'funding_events'
--     AND column_name IN ('manual_review_required', 'manual_review_reason');
--
-- Expected result:
--   manual_review_required | boolean | YES
--   manual_review_reason   | text    | YES
-- =============================================================================
