-- One-time repair for the Theater Series A duplicate that motivated event-level
-- reconciliation. Apply only after add_funding_event_sources.sql.

BEGIN;

DO $$
DECLARE
    earlier_event_id UUID;
    canonical_event_id UUID;
    earlier_company_id UUID;
    canonical_company_id UUID;
BEGIN
    SELECT id, company_id
      INTO earlier_event_id, earlier_company_id
      FROM public.funding_events
     WHERE article_url = 'https://entrackr.com/exclusive/exclusive-fashion-brand-theater-raises-series-a-at-rs-400-cr-valuation-12509223';

    SELECT id, company_id
      INTO canonical_event_id, canonical_company_id
      FROM public.funding_events
     WHERE article_url = 'https://entrackr.com/snippets/niveshaay-leads-rs-75-cr-series-a-round-in-fashion-brand-theater-12515108';

    IF canonical_event_id IS NULL THEN
        RAISE EXCEPTION 'The canonical Theater event was not found; no changes made';
    END IF;

    IF earlier_event_id IS NOT NULL AND earlier_company_id <> canonical_company_id THEN
        RAISE EXCEPTION 'The Theater events point to different companies; no changes made';
    END IF;

    UPDATE public.funding_events
       SET funding_amount = 75,
           currency = 'INR Cr',
           funding_round = 'Series A',
           valuation = 410,
           manual_review_required = TRUE,
           manual_review_reason =
               'Conflicting source evidence: the 9 Sep filing report states Rs 56.25 crore at approximately Rs 402 crore; the 10 Sep company announcement states Rs 75 crore at Rs 410 crore.'
     WHERE id = canonical_event_id;

    UPDATE public.funding_event_sources
       SET funding_event_id = canonical_event_id,
           is_canonical = (article_url = 'https://entrackr.com/snippets/niveshaay-leads-rs-75-cr-series-a-round-in-fashion-brand-theater-12515108'),
           extracted_funding_amount = CASE
               WHEN article_url LIKE '%exclusive-fashion-brand-theater-%' THEN 56.25
               ELSE 75
           END,
           extracted_currency = 'INR Cr',
           extracted_funding_round = 'Series A',
           extracted_valuation = CASE
               WHEN article_url LIKE '%exclusive-fashion-brand-theater-%' THEN 400
               ELSE 410
           END
     WHERE article_url IN (
         'https://entrackr.com/exclusive/exclusive-fashion-brand-theater-raises-series-a-at-rs-400-cr-valuation-12509223',
         'https://entrackr.com/snippets/niveshaay-leads-rs-75-cr-series-a-round-in-fashion-brand-theater-12515108'
     );

    IF earlier_event_id IS NOT NULL THEN
        DELETE FROM public.funding_events WHERE id = earlier_event_id;
    END IF;
END;
$$;

COMMIT;
