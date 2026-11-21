-- India Venture Review -- canonical company identity and website storage.
-- Safe to re-run. Existing public slugs are intentionally left unchanged.

BEGIN;

CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE OR REPLACE FUNCTION public.ivr_clean_company_name(value TEXT)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    cleaned TEXT;
BEGIN
    cleaned := regexp_replace(trim(coalesce(value, '')), '\s+', ' ', 'g');
    cleaned := regexp_replace(cleaned, '^\s*exclusive\s*:\s*', '', 'i');
    cleaned := regexp_replace(cleaned, '[,;:]\s*$', '');
    cleaned := regexp_replace(cleaned, '\.\s*ai$', '.ai', 'i');
    cleaned := regexp_replace(cleaned, '\s+ai$', '.ai', 'i');
    RETURN nullif(trim(cleaned), '');
END;
$$;

CREATE OR REPLACE FUNCTION public.ivr_company_name_normalized(value TEXT)
RETURNS TEXT
LANGUAGE SQL
STABLE
AS $$
    SELECT nullif(
        trim(regexp_replace(
            lower(unaccent(replace(public.ivr_clean_company_name(value), '&', ' and '))),
            '[^a-z0-9]+', ' ', 'g'
        )),
        ''
    );
$$;

CREATE OR REPLACE FUNCTION public.ivr_canonical_website(value TEXT)
RETURNS TEXT
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    host TEXT;
BEGIN
    IF value IS NULL OR trim(value) = '' THEN
        RETURN NULL;
    END IF;
    host := lower(trim(value));
    host := regexp_replace(host, '^https?://', '', 'i');
    host := regexp_replace(host, '^www\.', '', 'i');
    host := regexp_replace(host, '[/#?].*$', '');
    host := regexp_replace(host, ':\d+$', '');
    IF host = '' OR host !~ '^[a-z0-9.-]+\.[a-z]{2,}$' THEN
        RETURN NULL;
    END IF;
    RETURN 'https://' || host;
END;
$$;

CREATE OR REPLACE FUNCTION public.ivr_website_domain(value TEXT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT nullif(regexp_replace(
        coalesce(public.ivr_canonical_website(value), ''), '^https://', ''
    ), '');
$$;

ALTER TABLE public.companies
    ADD COLUMN IF NOT EXISTS company_name_normalized TEXT,
    ADD COLUMN IF NOT EXISTS website_domain TEXT,
    ADD COLUMN IF NOT EXISTS website_verified BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS website_evidence_url TEXT,
    ADD COLUMN IF NOT EXISTS identity_review_required BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS identity_review_reason TEXT;

UPDATE public.companies
SET
    company_name = public.ivr_clean_company_name(company_name),
    company_name_normalized = public.ivr_company_name_normalized(company_name),
    website_domain = public.ivr_website_domain(website);

ALTER TABLE public.companies
    ALTER COLUMN company_name_normalized SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_companies_company_name_normalized
    ON public.companies (company_name_normalized);

CREATE INDEX IF NOT EXISTS idx_companies_website_domain
    ON public.companies (website_domain)
    WHERE website_domain IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.company_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    alias_type TEXT NOT NULL DEFAULT 'source_variant'
        CHECK (alias_type IN ('source_variant', 'former_name', 'legal_name', 'brand_name')),
    evidence_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, normalized_alias)
);

CREATE INDEX IF NOT EXISTS idx_company_aliases_normalized_alias
    ON public.company_aliases (normalized_alias);

CREATE TABLE IF NOT EXISTS public.company_identity_change_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    changed_fields TEXT[] NOT NULL,
    old_values JSONB NOT NULL,
    new_values JSONB NOT NULL,
    reason TEXT,
    evidence_url TEXT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION public.normalize_company_identity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.company_name := public.ivr_clean_company_name(NEW.company_name);
    IF NEW.company_name IS NULL THEN
        RAISE EXCEPTION 'company_name cannot be empty after normalization';
    END IF;
    NEW.company_name_normalized := public.ivr_company_name_normalized(NEW.company_name);
    NEW.website := public.ivr_canonical_website(NEW.website);
    NEW.website_domain := public.ivr_website_domain(NEW.website);
    IF NEW.website_verified AND (NEW.website IS NULL OR NEW.website_evidence_url IS NULL) THEN
        RAISE EXCEPTION 'website and website_evidence_url are required when website_verified is true';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS companies_00_normalize_identity ON public.companies;
CREATE TRIGGER companies_00_normalize_identity
    BEFORE INSERT OR UPDATE OF company_name, website, website_verified, website_evidence_url
    ON public.companies
    FOR EACH ROW
    EXECUTE FUNCTION public.normalize_company_identity();

CREATE OR REPLACE FUNCTION public.capture_company_identity_aliases()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.company_name IS DISTINCT FROM NEW.company_name THEN
        INSERT INTO public.company_aliases (company_id, alias, normalized_alias, alias_type)
        VALUES (
            NEW.id,
            OLD.company_name,
            public.ivr_company_name_normalized(OLD.company_name),
            'source_variant'
        )
        ON CONFLICT (company_id, normalized_alias) DO NOTHING;
    END IF;
    INSERT INTO public.company_aliases (company_id, alias, normalized_alias, alias_type)
    VALUES (
        NEW.id,
        NEW.company_name,
        public.ivr_company_name_normalized(NEW.company_name),
        'brand_name'
    )
    ON CONFLICT (company_id, normalized_alias) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS companies_capture_identity_aliases ON public.companies;
CREATE TRIGGER companies_capture_identity_aliases
    AFTER INSERT OR UPDATE OF company_name ON public.companies
    FOR EACH ROW
    EXECUTE FUNCTION public.capture_company_identity_aliases();

INSERT INTO public.company_aliases (company_id, alias, normalized_alias, alias_type)
SELECT id, company_name, company_name_normalized, 'brand_name'
FROM public.companies
ON CONFLICT (company_id, normalized_alias) DO NOTHING;

REVOKE ALL ON TABLE public.company_aliases, public.company_identity_change_log FROM PUBLIC;
REVOKE ALL ON TABLE public.company_aliases, public.company_identity_change_log FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON TABLE public.company_aliases TO service_role;
GRANT SELECT, INSERT ON TABLE public.company_identity_change_log TO service_role;

NOTIFY pgrst, 'reload schema';

COMMIT;
