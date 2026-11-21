-- Model a funding event separately from the articles that report it.
-- Apply this migration before deploying the matching connector changes.

BEGIN;

CREATE TABLE IF NOT EXISTS public.funding_event_sources (
    id                                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    funding_event_id                    UUID NOT NULL
                                            REFERENCES public.funding_events (id)
                                            ON DELETE CASCADE,
    article_url                         TEXT UNIQUE NOT NULL,
    article_title                       TEXT,
    article_publication_date            DATE,
    source_name                         TEXT NOT NULL,
    scraped_timestamp                   TIMESTAMPTZ NOT NULL,
    is_canonical                        BOOLEAN NOT NULL DEFAULT FALSE,
    extracted_funding_amount            NUMERIC,
    extracted_currency                  TEXT,
    extracted_funding_round             TEXT,
    extracted_lead_investors            TEXT,
    extracted_participating_investors   TEXT,
    extracted_valuation                 NUMERIC,
    created_at                          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_funding_event_sources_event_id
    ON public.funding_event_sources (funding_event_id, article_publication_date DESC);

ALTER TABLE IF EXISTS public.ingestion_runs
    ADD COLUMN IF NOT EXISTS event_sources_attached INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS event_conflicts_flagged INTEGER NOT NULL DEFAULT 0;

-- Preserve every article already represented by a legacy funding_events row.
INSERT INTO public.funding_event_sources (
    funding_event_id,
    article_url,
    article_title,
    article_publication_date,
    source_name,
    scraped_timestamp,
    is_canonical,
    extracted_funding_amount,
    extracted_currency,
    extracted_funding_round,
    extracted_lead_investors,
    extracted_participating_investors,
    extracted_valuation
)
SELECT
    id,
    article_url,
    article_title,
    article_publication_date,
    source_name,
    scraped_timestamp,
    TRUE,
    funding_amount,
    currency,
    funding_round,
    lead_investors,
    participating_investors,
    valuation
FROM public.funding_events
ON CONFLICT (article_url) DO NOTHING;

-- New canonical events continue to be written through funding_events. Mirror
-- their first article automatically so event creation and source capture share
-- one database transaction.
CREATE OR REPLACE FUNCTION public.capture_canonical_funding_event_source()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.funding_event_sources (
        funding_event_id,
        article_url,
        article_title,
        article_publication_date,
        source_name,
        scraped_timestamp,
        is_canonical,
        extracted_funding_amount,
        extracted_currency,
        extracted_funding_round,
        extracted_lead_investors,
        extracted_participating_investors,
        extracted_valuation
    ) VALUES (
        NEW.id,
        NEW.article_url,
        NEW.article_title,
        NEW.article_publication_date,
        NEW.source_name,
        NEW.scraped_timestamp,
        TRUE,
        NEW.funding_amount,
        NEW.currency,
        NEW.funding_round,
        NEW.lead_investors,
        NEW.participating_investors,
        NEW.valuation
    )
    ON CONFLICT (article_url) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS funding_events_capture_canonical_source
    ON public.funding_events;
CREATE TRIGGER funding_events_capture_canonical_source
    AFTER INSERT ON public.funding_events
    FOR EACH ROW
    EXECUTE FUNCTION public.capture_canonical_funding_event_source();

ALTER TABLE public.funding_event_sources ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.funding_event_sources FROM PUBLIC;
REVOKE ALL ON TABLE public.funding_event_sources FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON TABLE public.funding_event_sources TO service_role;

REVOKE ALL ON FUNCTION public.capture_canonical_funding_event_source() FROM PUBLIC;

COMMIT;
