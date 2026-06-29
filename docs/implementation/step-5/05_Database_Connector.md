# Step 5: Database Connector

Implemented the Database Connector — the final stage of the ingestion pipeline — persisting structured funding records produced by the Evidence Extraction Engine into Supabase.

---

## Objective

Build `scraper/database.py` to accept structured funding records and persist them to Supabase. The connector must handle company lookup and creation, funding event insertion with duplicate detection, metadata preservation, and an operational summary. It must not parse, extract, reconcile, or modify upstream output.

This step also included two prerequisite architectural changes:
- Wiring `classification_confidence` through the full pipeline from the classifier to the database
- Adding `manual_review_required` and `manual_review_reason` columns to `funding_events`

---

## Implementation Prompt

> This is Step 5 of 7 in a structured build process. Do exactly what is requested in this step and nothing more. Do not anticipate future steps. Do not add extra logic, optimization, or features not explicitly requested. I will give you the next step separately.
>
> Follow all conventions documented in CONTRIBUTING.md.
>
> Read the full specification for this milestone from:
> specification/step-05-database-connector.md
>
> Read it completely before beginning implementation. The specification is the single source of truth for this milestone. Do not proceed until you have read it in full.

---

## Technical Decisions

**`classification_confidence` wired through the pipeline as metadata**
The classifier in `scraper/entrackr.py` already computed `classification_confidence` but discarded it before returning articles. Three targeted changes were made: (1) the field is now included in each article dict returned by `fetch_entrackr_articles()`, (2) `normalize_entrackr_article()` in the parser passes it through, (3) `extract_metadata_fields()` includes it in the structured record. The parser never interprets or recomputes this value — it is owned by the classifier and preserved by every intermediate stage until the connector persists it.

**Pre-check duplicate detection rather than exception parsing**
The `_article_exists()` function queries `funding_events` for the `article_url` before attempting insertion. This produces a clean "duplicate skipped" result rather than relying on catching and parsing constraint violation error messages, which are brittle across database drivers and versions. The `article_url UNIQUE NOT NULL` constraint remains the final safeguard against concurrent race conditions.

**Company lookup by exact name match — never update existing records**
The connector queries `companies` by `company_name` using exact string matching. If a match exists, the existing `id` is reused and no fields are updated — human-curated company records are considered authoritative and must never be overwritten by ingestion. If no match exists, a new company is created with all available fields from the structured record. Fuzzy matching belongs to a future milestone.

**`first_seen_date` set at insertion time**
`first_seen_date DATE NOT NULL` is required by the `companies` schema. It is set to today's date at insertion time by the connector. The article's `article_publication_date` is not used for this field because the article may describe a deal announced before today's run.

**Only non-None fields sent to Supabase**
The Supabase REST API can behave inconsistently when `null` values are sent explicitly for certain column types. The connector strips `None` values from both company and funding event payloads before sending, allowing the database to apply its own defaults and NULL handling cleanly.

**`manual_review_reason` stored as a semicolon-joined string**
The validation report's `review_reasons` is a list of strings. Since `manual_review_reason TEXT` is a single column, the list is joined with `"; "` before storage. This keeps the schema simple for the MVP while still preserving all reasons for the morning curation workflow.

**Per-record exception handling — pipeline never terminates on one failure**
Each record is wrapped in a `try/except` block. Unexpected errors are caught, classified, and reported with a clear message. A database error for one article never prevents subsequent articles from being processed. The operational summary accurately reflects the number of errors without crashing the run.

**`config.py` loads credentials via `python-dotenv`**
`python-dotenv` loads `SUPABASE_URL` and `SUPABASE_KEY` from the `.env` file into `os.environ`. All modules that need database access import from `config.py` rather than reading environment variables directly. The `.env` file is not committed and is listed in `.gitignore`.

---

## Files Created or Modified

| File | Action |
|---|---|
| `scraper/database.py` | Created — Database Connector with company handling, event insertion, duplicate detection, operational summary |
| `scraper/entrackr.py` | Modified — added `classification_confidence` to each returned article dict |
| `scraper/parser.py` | Modified — `normalize_entrackr_article()` and `extract_metadata_fields()` now pass `classification_confidence` through |
| `config.py` | Updated — loads `SUPABASE_URL` and `SUPABASE_KEY` from `.env` via `python-dotenv` |
| `sql/add_parser_metadata.sql` | Created — migration adding `manual_review_required` (BOOLEAN) and `manual_review_reason` (TEXT) to `funding_events` |
| `requirements.txt` | Updated — added `supabase==2.31.0` and `python-dotenv==1.2.1` |

---

## Schema Migration

Run `sql/add_parser_metadata.sql` once in the Supabase SQL Editor before executing the pipeline:

```sql
ALTER TABLE funding_events
    ADD COLUMN manual_review_required  BOOLEAN,
    ADD COLUMN manual_review_reason    TEXT;
```

Verification query:
```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'funding_events'
  AND column_name IN ('manual_review_required', 'manual_review_reason');
```

---

## Validation Command

```bash
python3 -m scraper.database
```

Running this command executes the full pipeline end to end:
1. Fetches and classifies articles from the Entrackr RSS feed
2. Runs the Evidence Extraction Engine
3. Persists structured records to Supabase
4. Prints the operational summary

---

## Verification Performed

- Ran `python3 -m scraper.database` against 8 live funding articles.
- Confirmed 6 new companies were created and 6 funding events were inserted on the first run.
- Confirmed re-running the pipeline immediately after produced 6 duplicates skipped, 0 new insertions, 0 database errors.
- Confirmed `classification_confidence` populated correctly in `funding_events` (Strong/Moderate values visible in Supabase).
- Confirmed `manual_review_required` and `manual_review_reason` populated for articles with extraction gaps.
- Confirmed Turtlemint (IPO listing, no company name) was skipped with a clear persistence validation failure message.
- Confirmed the operational summary printed correct counts after every run.

---

## Outcome

The project gained a fully working end-to-end ingestion pipeline. Running `python3 -m scraper.database` fetches funding articles from Entrackr, extracts structured records, and persists them to Supabase — creating company records and funding events, skipping duplicates, and flagging articles for manual review. The pipeline is idempotent: running it multiple times against the same articles produces no duplicate records.

**Commit:** `1498496 — Step 5: Implemented Database Connector`

---

## Next Step

Step 5.1 — Improve company name extraction for investor-led article titles where the funded company appears after the investor action phrase rather than before a funding verb.
