# Database Connector — persists structured funding records to Supabase.
#
# Responsibilities:
#   - Company lookup and creation (never updates existing company records)
#   - Funding event insertion with duplicate detection by article_url
#   - Metadata persistence: classification_confidence, manual_review_required,
#     manual_review_reason
#   - Operational summary
#
# This module does not parse, extract, reconcile, or modify upstream output.
# It receives structured records from the Evidence Extraction Engine and
# persists them exactly as received.

import datetime

from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY


# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

def _get_client():
    """Create and return a configured Supabase client."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set in the .env file."
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ---------------------------------------------------------------------------
# Persistence validation
# ---------------------------------------------------------------------------

# Minimum fields required before a record can be written to the database.
# Business fields (amount, round, investors, etc.) may remain NULL.
_REQUIRED_FIELDS = [
    "company_name",
    "article_url",
    "article_publication_date",
    "source_name",
]


def _validate_record(record):
    """
    Return a list of missing required field names.
    An empty list means the record satisfies the minimum persistence contract.
    """
    return [f for f in _REQUIRED_FIELDS if not record.get(f)]


# ---------------------------------------------------------------------------
# Company handling
# ---------------------------------------------------------------------------

def _find_company(client, company_name):
    """
    Look up a company by exact name match.
    Returns the first matching row (dict with 'id') or None.

    company_name is not unique in the schema — two startups can share a name.
    For the MVP, the first match is reused. Fuzzy matching belongs to a future
    milestone.
    """
    result = (
        client.table("companies")
        .select("id")
        .eq("company_name", company_name)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def _create_company(client, record):
    """
    Insert a new company record using fields from the structured funding record.
    Returns the created row (dict including the generated 'id').

    Only fields with non-None values are sent to avoid overwriting schema
    defaults. company_name and first_seen_date are always included.
    """
    data = {
        "company_name":    record["company_name"],
        "first_seen_date": datetime.date.today().isoformat(),
    }

    optional_fields = [
        "website",
        "description",
        "industry",
        "business_model",
        "headquarters_city",
        "headquarters_state",
        "headquarters_country",
        "founded_year",
    ]
    for field in optional_fields:
        if record.get(field) is not None:
            data[field] = record[field]

    result = client.table("companies").insert(data).execute()
    return result.data[0]


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def _article_exists(client, article_url):
    """
    Return True if a funding event with this article URL already exists.

    article_url is the natural deduplication key — it is UNIQUE NOT NULL in
    the funding_events schema. Checking before insertion gives a clear
    'duplicate skipped' result rather than relying on exception parsing.
    """
    result = (
        client.table("funding_events")
        .select("id")
        .eq("article_url", article_url)
        .limit(1)
        .execute()
    )
    return bool(result.data)


# ---------------------------------------------------------------------------
# Funding event insertion
# ---------------------------------------------------------------------------

def _insert_funding_event(client, record, company_id, validation_report):
    """
    Insert one funding event row.

    Assumes duplicate detection has already passed. Persists all business
    fields (which may be NULL) and all pipeline metadata exactly as received.
    """
    review_reasons = validation_report.get("review_reasons") or []

    data = {
        "company_id":                company_id,
        "article_url":               record["article_url"],
        "article_title":             record.get("article_title"),
        "article_publication_date":  record.get("article_publication_date"),
        "source_name":               record["source_name"],
        "scraped_timestamp":         datetime.datetime.now(datetime.timezone.utc).isoformat(),
        # Business fields — may remain NULL
        "funding_amount":            record.get("funding_amount"),
        "currency":                  record.get("currency"),
        "funding_round":             record.get("funding_round"),
        "lead_investors":            record.get("lead_investors"),
        "participating_investors":   record.get("participating_investors"),
        "valuation":                 record.get("valuation"),
        # Pipeline metadata — preserved exactly as received from upstream stages
        "classification_confidence": record.get("classification_confidence"),
        "manual_review_required":    validation_report.get("requires_manual_review"),
        "manual_review_reason":      "; ".join(review_reasons) if review_reasons else None,
    }

    # Remove None values — the database applies NULL for any missing column.
    data = {k: v for k, v in data.items() if v is not None}

    client.table("funding_events").insert(data).execute()


# ---------------------------------------------------------------------------
# Main connector
# ---------------------------------------------------------------------------

def persist_funding_records(results):
    """
    Persist a list of (structured_record, validation_report) tuples to Supabase.

    Processing order for each record:
      1. Validate required fields
      2. Check for duplicate article URL — skip if already exists
      3. Look up or create the company
      4. Insert the funding event

    A failure for one record never interrupts remaining records.

    Args:
        results: list of (structured_record, validation_report) tuples
                 as returned by extract_funding_records().

    Returns:
        dict: operational stats for the summary display.
    """
    client = _get_client()

    stats = {
        "companies_created":   0,
        "companies_reused":    0,
        "events_inserted":     0,
        "duplicates_skipped":  0,
        "validation_failures": 0,
        "database_errors":     0,
        "review_queue":        0,
    }

    # Per-article outcomes — consumed by the logger to build the ARTICLE LOG and
    # FAILURES sections. Each entry contains enough context to diagnose issues
    # without re-running the pipeline.
    article_log = []

    for record, report in results:
        if record is None:
            # The extraction engine returned no record (complete pipeline failure).
            stats["validation_failures"] += 1
            article_log.append({
                "outcome":      "validation_failure",
                "title":        None,
                "url":          None,
                "confidence":   None,
                "company_name": None,
                "reason":       "Extraction engine returned no record",
            })
            continue

        # --- Persistence validation ---
        missing = _validate_record(record)
        if missing:
            stats["validation_failures"] += 1
            url_label = record.get("article_url") or "unknown URL"
            reason = f"Missing required fields: {', '.join(missing)}"
            print(f"  [SKIP — Validation] {url_label}")
            print(f"    {reason}")
            article_log.append({
                "outcome":      "validation_failure",
                "title":        record.get("article_title"),
                "url":          record.get("article_url"),
                "confidence":   record.get("classification_confidence"),
                "company_name": record.get("company_name"),
                "reason":       reason,
            })
            continue

        article_url  = record["article_url"]
        company_name = record["company_name"]

        try:
            # --- Duplicate detection ---
            if _article_exists(client, article_url):
                stats["duplicates_skipped"] += 1
                print(f"  [SKIP — Duplicate] {record.get('article_title', article_url)}")
                article_log.append({
                    "outcome":      "duplicate",
                    "title":        record.get("article_title"),
                    "url":          article_url,
                    "confidence":   record.get("classification_confidence"),
                    "company_name": company_name,
                    "reason":       None,
                })
                continue

            # --- Company lookup or creation ---
            existing = _find_company(client, company_name)
            if existing:
                company_id = existing["id"]
                stats["companies_reused"] += 1
            else:
                created = _create_company(client, record)
                company_id = created["id"]
                stats["companies_created"] += 1

            # --- Funding event insertion ---
            _insert_funding_event(client, record, company_id, report)
            stats["events_inserted"] += 1

            if report.get("requires_manual_review"):
                stats["review_queue"] += 1

            title = record.get("article_title", article_url)
            confidence = record.get("classification_confidence", "")
            review_flag = " ← review" if report.get("requires_manual_review") else ""
            print(f"  [INSERTED — {confidence}] {title}{review_flag}")
            article_log.append({
                "outcome":      "inserted",
                "title":        title,
                "url":          article_url,
                "confidence":   confidence,
                "company_name": company_name,
                "reason":       None,
            })

        except Exception as e:
            error_str = str(e)
            # Catch duplicate constraint violations that slip past the pre-check
            # (e.g., a concurrent run inserting the same URL between check and insert).
            if "duplicate" in error_str.lower() or "unique" in error_str.lower():
                stats["duplicates_skipped"] += 1
                print(f"  [SKIP — Duplicate] {record.get('article_title', article_url)}")
                article_log.append({
                    "outcome":      "duplicate",
                    "title":        record.get("article_title"),
                    "url":          article_url,
                    "confidence":   record.get("classification_confidence"),
                    "company_name": company_name,
                    "reason":       None,
                })
            else:
                stats["database_errors"] += 1
                print(f"  [ERROR] {record.get('article_title', article_url)}")
                print(f"    {error_str}")
                article_log.append({
                    "outcome":      "database_error",
                    "title":        record.get("article_title"),
                    "url":          article_url,
                    "confidence":   record.get("classification_confidence"),
                    "company_name": company_name,
                    "reason":       error_str,
                })

    return {"stats": stats, "article_log": article_log}


# ---------------------------------------------------------------------------
# Manual run entry point
# ---------------------------------------------------------------------------
# Run the full ingestion pipeline end to end:
#   python3 -m scraper.database

if __name__ == "__main__":
    from scraper.entrackr import fetch_entrackr_articles
    from scraper.parser import extract_funding_records

    print("India Venture Review — Full Ingestion Pipeline")
    print("=" * 60)
    print()

    # --- Stage 1: RSS ingestion and classification ---
    print("Stage 1  Fetching articles from Entrackr RSS...")
    articles = fetch_entrackr_articles(verbose=False)
    rss_accepted = len(articles)

    if not articles:
        print("         No funding articles found in the last 24 hours.")
        raise SystemExit(0)

    print(f"         {rss_accepted} funding article(s) accepted by classifier")
    print()

    # --- Stage 2: Evidence extraction ---
    print("Stage 2  Running Evidence Extraction Engine...")
    results = extract_funding_records(articles)
    print(f"         {len(results)} structured record(s) produced")
    print()

    # --- Stage 3: Database persistence ---
    print("Stage 3  Persisting to Supabase...")
    print()
    db_result = persist_funding_records(results)
    stats = db_result["stats"]
    print()

    # --- Operational summary ---
    print("─" * 60)
    print("Operational Summary")
    print("─" * 60)
    print(f"  {'RSS Articles Processed':<35} {rss_accepted}")
    print(f"  {'Funding Articles Accepted':<35} {rss_accepted}")
    print(f"  {'Structured Records Produced':<35} {len(results)}")
    print(f"  {'Companies Created':<35} {stats['companies_created']}")
    print(f"  {'Companies Reused':<35} {stats['companies_reused']}")
    print(f"  {'Funding Events Inserted':<35} {stats['events_inserted']}")
    print(f"  {'Duplicates Skipped':<35} {stats['duplicates_skipped']}")
    print(f"  {'Persistence Validation Failures':<35} {stats['validation_failures']}")
    print(f"  {'Database Errors':<35} {stats['database_errors']}")
    review_label = "Today's Review Queue"
    print(f"  {review_label:<35} {stats['review_queue']}")
    print("─" * 60)
