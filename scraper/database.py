# Database Connector — persists structured funding records to Supabase.
#
# Responsibilities:
#   - Company lookup and creation (never updates existing company records)
#   - Funding event insertion with article and event-level duplicate detection
#   - Additional-source attachment for repeat coverage of an existing event
#   - Metadata persistence: classification_confidence, manual_review_required,
#     manual_review_reason
#   - Operational summary
#
# This module does not parse, extract, reconcile, or modify upstream output.
# It receives structured records from the Evidence Extraction Engine and
# persists them exactly as received.

import datetime
import re
import time
import unicodedata
from decimal import Decimal, InvalidOperation

import httpx
from supabase import ClientOptions, create_client
from config import SUPABASE_URL, SUPABASE_KEY
from scraper.company_identity import clean_company_name, company_lookup_key, normalize_website
from scraper.investor_identity import normalize_investor_list
from scraper.sector_taxonomy import sector_category


# Keep individual PostgREST operations comfortably below the hosted function
# deadline. Only read operations and idempotent funding-event upserts retry.
DATABASE_TIMEOUT_SECONDS = 8
READ_RETRY_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 0.25
PIPELINE_LOCK_NAME = "ivr-ingestion"
EVENT_MATCH_WINDOW_DAYS = 7
EVENT_AMOUNT_RELATIVE_TOLERANCE = Decimal("0.10")


# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

def _get_client():
    """Create and return a configured Supabase client."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set in the .env file."
        )
    return create_client(
        SUPABASE_URL,
        SUPABASE_KEY,
        options=ClientOptions(postgrest_client_timeout=DATABASE_TIMEOUT_SECONDS),
    )


def _execute_with_retry(operation, attempts=READ_RETRY_ATTEMPTS):
    """Retry only transient HTTP failures for operations safe to repeat."""
    for attempt in range(attempts):
        try:
            return operation()
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
            if attempt == attempts - 1:
                raise
            time.sleep(RETRY_DELAY_SECONDS)


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
    normalized_name = company_lookup_key(company_name)
    if not normalized_name:
        return None

    try:
        result = _execute_with_retry(
            lambda: (
                client.table("companies")
                .select("id,company_name")
                .eq("company_name_normalized", normalized_name)
                .limit(3)
                .execute()
            )
        )
        candidates = result.data or []
        if not candidates:
            aliases = _execute_with_retry(
                lambda: (
                    client.table("company_aliases")
                    .select("company_id")
                    .eq("normalized_alias", normalized_name)
                    .limit(3)
                    .execute()
                )
            ).data or []
            company_ids = sorted({alias["company_id"] for alias in aliases})
            candidates = [{"id": company_id} for company_id in company_ids]
    except Exception as error:
        # Keep deployments safe while the companion SQL migration is being
        # rolled out. Only a missing relation/column is eligible for fallback.
        message = str(error).lower()
        if not any(token in message for token in (
            "company_name_normalized", "company_aliases", "42703", "42p01"
        )):
            raise
        result = _execute_with_retry(
            lambda: client.table("companies").select("id,company_name").execute()
        )
        candidates = [
            row for row in (result.data or [])
            if company_lookup_key(row.get("company_name")) == normalized_name
        ]

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        exact = [
            row for row in candidates
            if clean_company_name(row.get("company_name")) == clean_company_name(company_name)
        ]
        if len(exact) == 1:
            return exact[0]
        raise RuntimeError(
            "Ambiguous normalized company identity for %r; manual review required"
            % company_name
        )
    return None


def _create_company(client, record):
    """
    Insert a new company record using fields from the structured funding record.
    Returns the created row (dict including the generated 'id').

    Only fields with non-None values are sent to avoid overwriting schema
    defaults. company_name and first_seen_date are always included.
    """
    data = {
        "company_name":    clean_company_name(record["company_name"]),
        "first_seen_date": datetime.date.today().isoformat(),
    }

    optional_fields = [
        "description",
        "business_model",
        "headquarters_city",
        "headquarters_state",
        "headquarters_country",
        "founded_year",
    ]
    for field in optional_fields:
        if record.get(field) is not None:
            data[field] = record[field]

    source_industry = record.get("industry")
    canonical_industry = sector_category(
        source_industry,
        description=record.get("description"),
    )
    if canonical_industry:
        data["industry"] = canonical_industry
        if source_industry and source_industry != canonical_industry:
            data["sub_industry"] = source_industry

    # Article text is not proof that a domain belongs to the funded company.
    # A website is persisted only when an enrichment explicitly marks it as
    # identity-verified and supplies supporting evidence.
    if record.get("website_verified") and record.get("website_evidence_url"):
        website = normalize_website(record.get("website"))
        if website:
            data.update({
                "website": website,
                "website_verified": True,
                "website_evidence_url": record["website_evidence_url"],
            })

    result = client.table("companies").insert(data).execute()
    return result.data[0]


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def _article_exists(client, article_url):
    """
    Return True if this source article URL has already been processed.

    funding_event_sources owns article identity so several distinct articles
    can support one canonical funding event without creating extra events.
    """
    result = _execute_with_retry(
        lambda: (
            client.table("funding_event_sources")
            .select("id")
            .eq("article_url", article_url)
            .limit(1)
            .execute()
        )
    )
    return bool(result.data)


def _normalized_text(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.casefold()).strip()


def _normalized_round(value):
    return (
        _normalized_text(value)
        .replace("pre series", "pre-series")
        .replace("pre seed", "pre-seed")
    )


def _normalized_currency(value):
    words = _normalized_text(value).split()
    aliases = {
        "crore": "cr", "lakhs": "lakh", "million": "mn", "m": "mn",
        "billion": "bn", "b": "bn", "thousand": "k",
    }
    return " ".join(aliases.get(word, word) for word in words)


def _investor_names(value):
    names = set()
    for part in re.split(r",|;|\s+(?:and|&)\s+", value or "", flags=re.IGNORECASE):
        name = _normalized_text(part)
        name = re.sub(r"^(?:new|existing)\s+investor\s+", "", name)
        if name:
            names.add(name)
    return names


def _amounts_close(existing, incoming):
    try:
        left = Decimal(str(existing))
        right = Decimal(str(incoming))
    except (InvalidOperation, TypeError, ValueError):
        return False
    if left == right:
        return True
    scale = max(abs(left), abs(right))
    return bool(scale) and abs(left - right) / scale <= EVENT_AMOUNT_RELATIVE_TOLERANCE


def _events_match(existing, incoming):
    """Conservatively identify two articles as coverage of the same event."""
    existing_round = _normalized_round(existing.get("funding_round"))
    incoming_round = _normalized_round(incoming.get("funding_round"))
    if not existing_round or existing_round != incoming_round:
        return False

    investor_overlap = bool(
        _investor_names(existing.get("lead_investors"))
        & _investor_names(incoming.get("lead_investors"))
    )
    existing_currency = _normalized_currency(existing.get("currency"))
    incoming_currency = _normalized_currency(incoming.get("currency"))
    amount_match = (
        existing_currency
        and incoming_currency
        and existing_currency == incoming_currency
        and _amounts_close(existing.get("funding_amount"), incoming.get("funding_amount"))
    )
    return investor_overlap or amount_match


def _find_matching_funding_event(client, company_id, record):
    """Find nearby corroborated coverage of the same company's funding round."""
    try:
        publication_date = datetime.date.fromisoformat(record["article_publication_date"])
    except (KeyError, TypeError, ValueError):
        return None
    if not _normalized_round(record.get("funding_round")):
        return None

    start = publication_date - datetime.timedelta(days=EVENT_MATCH_WINDOW_DAYS)
    end = publication_date + datetime.timedelta(days=EVENT_MATCH_WINDOW_DAYS)
    result = _execute_with_retry(
        lambda: (
            client.table("funding_events")
            .select(
                "id,funding_amount,currency,funding_round,lead_investors,valuation,"
                "article_publication_date,manual_review_reason"
            )
            .eq("company_id", company_id)
            .gte("article_publication_date", start.isoformat())
            .lte("article_publication_date", end.isoformat())
            .order("article_publication_date", desc=True)
            .execute()
        )
    )
    return next((event for event in result.data or [] if _events_match(event, record)), None)


def _source_data(record, funding_event_id, is_canonical=False):
    return {
        "funding_event_id": funding_event_id,
        "article_url": record["article_url"],
        "article_title": record.get("article_title"),
        "article_publication_date": record.get("article_publication_date"),
        "source_name": record["source_name"],
        "scraped_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "is_canonical": is_canonical,
        "extracted_funding_amount": record.get("funding_amount"),
        "extracted_currency": record.get("currency"),
        "extracted_funding_round": record.get("funding_round"),
        "extracted_lead_investors": normalize_investor_list(record.get("lead_investors")),
        "extracted_participating_investors": normalize_investor_list(record.get("participating_investors")),
        "extracted_valuation": record.get("valuation"),
    }


def _attach_event_source(client, funding_event_id, record):
    """Attach a new article and its extracted evidence to a canonical event."""
    data = {
        key: value
        for key, value in _source_data(record, funding_event_id).items()
        if value is not None
    }
    result = _execute_with_retry(
        lambda: client.table("funding_event_sources")
        .upsert(data, on_conflict="article_url", ignore_duplicates=True)
        .execute()
    )
    return bool(result.data)


def _conflicting_event_fields(existing, incoming):
    conflicts = []
    if (
        existing.get("funding_amount") is not None
        and incoming.get("funding_amount") is not None
        and not _amounts_close(existing["funding_amount"], incoming["funding_amount"])
    ):
        conflicts.append("funding_amount")
    if (
        existing.get("valuation") is not None
        and incoming.get("valuation") is not None
        and not _amounts_close(existing["valuation"], incoming["valuation"])
    ):
        conflicts.append("valuation")
    if (
        existing.get("currency")
        and incoming.get("currency")
        and _normalized_currency(existing["currency"]) != _normalized_currency(incoming["currency"])
    ):
        conflicts.append("currency")
    return conflicts


def _flag_event_conflict(client, event, record, conflicts):
    detail = "Conflicting source evidence for %s: %s" % (
        ", ".join(conflicts),
        record["article_url"],
    )
    existing_reason = event.get("manual_review_reason") or ""
    reason = (
        existing_reason
        if detail in existing_reason
        else "; ".join(filter(None, (existing_reason, detail)))
    )
    _execute_with_retry(
        lambda: client.table("funding_events")
        .update({"manual_review_required": True, "manual_review_reason": reason})
        .eq("id", event["id"])
        .execute()
    )


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
        "lead_investors":            normalize_investor_list(record.get("lead_investors")),
        "participating_investors":   normalize_investor_list(record.get("participating_investors")),
        "lead_investor_status":      (
            "identified" if record.get("lead_investors") else "unreviewed"
        ),
        "valuation":                 record.get("valuation"),
        # Pipeline metadata — preserved exactly as received from upstream stages
        "classification_confidence": record.get("classification_confidence"),
        "manual_review_required":    validation_report.get("requires_manual_review"),
        "manual_review_reason":      "; ".join(review_reasons) if review_reasons else None,
    }

    # Remove None values — the database applies NULL for any missing column.
    data = {k: v for k, v in data.items() if v is not None}

    # The database's article_url constraint makes this write safe to retry.
    result = _execute_with_retry(
        lambda: client.table("funding_events")
        .upsert(
            data,
            on_conflict="article_url",
            ignore_duplicates=True,
        )
        .execute()
    )
    return bool(result.data)


def acquire_pipeline_lock(run_id, lease_seconds=330):
    """Atomically acquire the hosted ingestion lease, returning False if busy."""
    client = _get_client()
    result = client.rpc(
        "acquire_ingestion_lock",
        {
            "p_lock_name": PIPELINE_LOCK_NAME,
            "p_locked_by": run_id,
            "p_lease_seconds": lease_seconds,
        },
    ).execute()
    return bool(result.data)


def release_pipeline_lock(run_id):
    """Release only the lease held by this invocation."""
    client = _get_client()
    result = client.rpc(
        "release_ingestion_lock",
        {
            "p_lock_name": PIPELINE_LOCK_NAME,
            "p_locked_by": run_id,
        },
    ).execute()
    return bool(result.data)


def create_ingestion_run(run):
    """Create one telemetry row; callers handle failures without affecting ingestion."""
    client = _get_client()
    result = client.table("ingestion_runs").insert(run).execute()
    return result.data[0] if result.data else None


def complete_ingestion_run(run_id, updates):
    """Idempotently complete a telemetry row using safe bounded retries."""
    client = _get_client()
    result = _execute_with_retry(
        lambda: client.table("ingestion_runs").update(updates).eq("run_id", run_id).execute()
    )
    return result.data[0] if result.data else None


def list_ingestion_runs(started_at=None, completed_at=None):
    """Read durable hosted-run history without triggering or changing ingestion."""
    client = _get_client()
    query = client.table("ingestion_runs").select("*").order("started_at")
    if started_at:
        query = query.gte("started_at", started_at)
    if completed_at:
        query = query.lte("started_at", completed_at)
    result = _execute_with_retry(lambda: query.execute())
    return result.data or []


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
      4. Attach the article to a matching event, or insert a new event

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
        "ineligible_skipped":  0,
        "database_errors":     0,
        "review_queue":        0,
        "event_sources_attached": 0,
        "event_conflicts_flagged": 0,
    }

    # Per-article outcomes — consumed by the logger to build the ARTICLE LOG and
    # FAILURES sections. Each entry contains enough context to diagnose issues
    # without re-running the pipeline.
    article_log = []
    website_enrichment_targets = []

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

        funding_status = report.get("funding_status", record.get("funding_status", "unknown"))
        if funding_status != "confirmed":
            stats["ineligible_skipped"] += 1
            reason = report.get("funding_status_reason") or (
                f"Funding status is {funding_status}"
            )
            title = record.get("article_title", record.get("article_url", "unknown"))
            print(f"  [SKIP — Ineligible: {funding_status}] {title}")
            print(f"    {reason}")
            article_log.append({
                "outcome": "ineligible",
                "title": record.get("article_title"),
                "url": record.get("article_url"),
                "confidence": record.get("classification_confidence"),
                "company_name": record.get("company_name"),
                "funding_status": funding_status,
                "reason": reason,
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
                if not created.get("website"):
                    website_enrichment_targets.append({
                        "id": company_id,
                        "company_name": created.get("company_name") or clean_company_name(company_name),
                        "source_article_url": article_url,
                    })

            # --- Event-level duplicate detection ---
            # Distinct URLs can report the same round. Keep one event, retain the
            # new source, and surface conflicting evidence for human review.
            matching_event = _find_matching_funding_event(client, company_id, record)
            if matching_event:
                attached = _attach_event_source(client, matching_event["id"], record)
                if not attached:
                    stats["duplicates_skipped"] += 1
                    article_log.append({
                        "outcome": "duplicate",
                        "title": record.get("article_title"),
                        "url": article_url,
                        "confidence": record.get("classification_confidence"),
                        "company_name": company_name,
                        "reason": None,
                    })
                    continue

                conflicts = _conflicting_event_fields(matching_event, record)
                if conflicts:
                    _flag_event_conflict(client, matching_event, record, conflicts)
                    stats["event_conflicts_flagged"] += 1
                    stats["review_queue"] += 1
                stats["event_sources_attached"] += 1
                reason = (
                    "Conflicting evidence: " + ", ".join(conflicts)
                    if conflicts else "Matched an existing funding event"
                )
                print(f"  [SOURCE ATTACHED] {record.get('article_title', article_url)}")
                article_log.append({
                    "outcome": "source_attached",
                    "title": record.get("article_title"),
                    "url": article_url,
                    "confidence": record.get("classification_confidence"),
                    "company_name": company_name,
                    "funding_event_id": matching_event["id"],
                    "reason": reason,
                })
                continue

            # --- Funding event insertion ---
            inserted = _insert_funding_event(client, record, company_id, report)
            if not inserted:
                stats["duplicates_skipped"] += 1
                article_log.append({
                    "outcome":      "duplicate",
                    "title":        record.get("article_title"),
                    "url":          article_url,
                    "confidence":   record.get("classification_confidence"),
                    "company_name": company_name,
                    "reason":       None,
                })
                continue

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

    return {
        "stats": stats,
        "article_log": article_log,
        "website_enrichment_targets": website_enrichment_targets,
    }


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
    print(f"  {'Additional Sources Attached':<35} {stats['event_sources_attached']}")
    print(f"  {'Event Conflicts Flagged':<35} {stats['event_conflicts_flagged']}")
    print(f"  {'Duplicates Skipped':<35} {stats['duplicates_skipped']}")
    print(f"  {'Persistence Validation Failures':<35} {stats['validation_failures']}")
    print(f"  {'Database Errors':<35} {stats['database_errors']}")
    review_label = "Today's Review Queue"
    print(f"  {review_label:<35} {stats['review_queue']}")
    print("─" * 60)
