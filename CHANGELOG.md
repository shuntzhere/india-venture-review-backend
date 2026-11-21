# Changelog

All notable changes to this project are documented here.

## [1.0.1-backup.1] - 2026-11-22

- Added independent GitHub Actions funding ingestion with durable freshness checks,
  shared locking, bounded runtime and verified completion.
- Added additive run-history metrics migration and recorded production installation.
- Pinned workflow Actions and dependency hashes; prepared a main-only environment.
- Verified 74 tests and a controlled production run; recovered five missing events.
- Extended outage recovery to the partial day of 18 November, adding three late
  announcements for eight recovered events total.
- Automatic scheduling remains pending credential approval and release activation.



---

## [Unreleased]

---

## [0.7.1] - 2026-06-30

### Step 7.1 — Implementation Documentation for Step 7
- Created `docs/implementation/step-7/07_Main_And_Scheduler.md`

---

## [0.7.0] - 2026-06-30

### Step 7 — Main Application and Scheduler
- Implemented `main.py` — single entry point wiring all pipeline modules in sequence
- Pipeline executes with one command: `python main.py`
- Prints startup banner with run ID (`IVR-YYYYMMDD-HHMM`) and completion banner with status and log path
- Handles catastrophic Stage 3 failures: logs FAILED status, prints failure reason, exits cleanly
- Configured macOS launchd to run the pipeline automatically every day at 7:00 AM IST
- Created `~/Library/LaunchAgents/com.indiaventurereview.pipeline.plist` — points to `.venv` Python interpreter, sets working directory, redirects stdout/stderr to `logs/launchd-stdout.log` and `logs/launchd-stderr.log`
- `RunAtLoad: false` — first automated run is the next morning; loading the agent does not trigger an immediate run
- LaunchAgent loaded and verified: `launchctl list | grep indiaventurereview`

---

## [0.6.1] - 2026-06-30

### Step 6.1 — Implementation Documentation for Step 6
- Created `docs/implementation/step-6/06_Logger.md`

---

## [0.6.0] - 2026-06-30

### Step 6 — Logger
- Built `scraper/logger.py` — structured logging system recording every pipeline execution to `logs/`
- Implemented `write_log()` — writes a human-readable log file; never raises, pipeline is never blocked by a logging failure
- Log file naming convention: `logs/YYYY-MM-DD.log`, incrementing to `-1`, `-2`, etc. when the pipeline runs more than once on the same day
- Each log captures: run metadata (Run ID, start/end time, total execution time, pipeline status), configuration snapshot (RSS source, lookback window, classifier threshold), software version (git commit hash, parser version, database connector version), pipeline statistics, per-article outcome log, and failure details with suggested actions
- Run ID formatted as `IVR-YYYYMMDD-HHMM` — every run uniquely identifiable without additional tooling
- Pipeline status determination: `SUCCESS` (no failures), `PARTIAL_SUCCESS` (one or more article-level failures), `FAILED` (system-level error preventing pipeline completion)
- Failure reporting: each failed article recorded with company name, URL, reason, and suggested action from the error classification table
- Extended `persist_funding_records()` in `scraper/database.py` to return per-article outcome dicts alongside aggregate stats — consumed by the logger to build the ARTICLE LOG and FAILURES sections
- Validation command: `python3 -m scraper.logger`

---

## [0.5.2] - 2026-06-30

### Step 5.2 — Implementation Documentation for Steps 5 and 5.1
- Created `docs/implementation/step-5/05_Database_Connector.md`
- Created `docs/implementation/step-5/05.1_Investor_Led_Title_Extraction.md`

---

## [0.5.1] - 2026-06-30

### Step 5.1 — Improved Company Name Extraction for Investor-Led Titles
- Added `_INVESTOR_LED_PATTERNS` constant to `scraper/parser.py`
- Extended `_extract_company_name()` with a two-strategy architecture: existing company-led extraction runs first; investor-led pattern matching runs as fallback
- Patterns added: "X leads [round] in/for Y", "X makes investment in Y", "X backs Y", "X invests in Y", "X puts [amount] in Y"
- Fixed: "Boundless Ventures leads pre-seed round in Lytmus AI" → "Lytmus AI"
- Fixed: "Yash Raj Films makes strategic investment in Rusk Media" → "Rusk Media"
- All previously working company-led titles continue to extract correctly

---

## [0.5.0] - 2026-06-30

### Step 5 — Database Connector
- Built `scraper/database.py` — persists structured funding records to Supabase
- Implemented company lookup by exact name match — existing company records are never overwritten
- Implemented funding event insertion with pre-check duplicate detection via `article_url`
- Implemented per-record error handling — one failure never interrupts the remaining pipeline
- Added operational summary: companies created/reused, events inserted, duplicates skipped, validation failures, database errors, review queue
- Wired `classification_confidence` through the full pipeline: classifier → article dict → normalized article → structured record → database
- Added `sql/add_parser_metadata.sql` migration — adds `manual_review_required` (BOOLEAN) and `manual_review_reason` (TEXT) to `funding_events`
- Updated `config.py` to load `SUPABASE_URL` and `SUPABASE_KEY` from `.env` via `python-dotenv`
- Added `supabase==2.31.0` and `python-dotenv==1.2.1` to `requirements.txt`
- Pipeline command: `python3 -m scraper.database`

---

## [0.4.1] - 2026-06-30

### Step 4.1 — Implementation Documentation for Step 4
- Created `docs/implementation/step-4/04_Evidence_Extraction_Engine.md`

---

## [0.4.0] - 2026-06-30

### Step 4 — Evidence Extraction Engine v1
- Built `scraper/parser.py` — Evidence Extraction Engine transforming normalized articles into structured funding records
- Implemented two-stage progressive extraction: Stage 1 (RSS content), Stage 2 (full article, only when primary fields are missing)
- Implemented four independent domain extractors: Company, Funding, Investors, Metadata
- Implemented shared extraction utilities: amount parsing, funding round detection, investor phrase matching, valuation extraction
- Added parser orchestrator coordinating the full extraction lifecycle
- Added Entrackr source adapter (`normalize_entrackr_article`) — extraction engine never reads source-specific fields directly
- Added evidence merge: Stage 1 verified values are never overwritten by Stage 2
- Added per-article validation output with confidence level, evidence source, field counts, and manual review recommendation
- Added validation summary after all articles are processed
- Introduced polite 1-second delay between consecutive full-article requests
- Added `beautifulsoup4==4.12.3` to `requirements.txt` for full-article HTML parsing
- Validation command: `python3 -m scraper.parser`

---

## [0.3.3] - 2026-06-29

### Step 3.3 — Implementation Documentation for Steps 3, 3.1, and 3.2
- Created `docs/implementation/step-3/03_Entrackr_RSS_Ingestion.md`
- Created `docs/implementation/step-3/03.1_Engineering_Refinement.md`
- Created `docs/implementation/step-3/03.2_Funding_Article_Classifier.md`
- All files follow the established implementation documentation format

---

## [0.3.2] - 2026-06-29

### Step 3.2 — Funding Article Classifier v1
- Evolved classifier from keyword matching to a weighted multi-signal scoring engine
- Implemented three independent signal detectors: `detect_funding_keyword`, `detect_funding_amount`, `detect_investor_phrase`
- Introduced `SIGNAL_REGISTRY` pattern — adding a new signal requires only a detector function and one tuple entry
- Implemented weighted scoring with configurable `ACCEPTANCE_THRESHOLD`
- Added confidence labels (Strong, Moderate, Weak) to validation output — internal only, not returned to callers
- Known edge case: IPO listing stories with share price patterns can trigger false positives at Moderate confidence — to be addressed in Step 4

---

## [0.3.1] - 2026-06-29

### Step 3.1 — Engineering Refinement of Entrackr Ingestion Module
- Added explicit HTTP `User-Agent` header identifying the scraper to the server
- Improved keyword matching from simple substring search to word-boundary regex (`\b`)
- Expanded and refined funding keyword list: added `"bags"`, removed `"investment"` (too broad — caused false positives)
- Isolated funding classification into a dedicated, swappable function
- Added HTML cleaning of `raw_content` using Python's built-in `html.parser` (not regex)
- Added URL-based deduplication to guard against repeated RSS entries
- Improved validation output with per-article rejection reasons and a structured summary

---

## [0.3.0] - 2026-06-29

### Step 3 — Entrackr RSS Ingestion Module
- Built `scraper/entrackr.py` to fetch and filter funding articles from Entrackr's RSS feed
- Implemented keyword-based funding article detection
- Added 24-hour lookback window with date filtering
- Added diagnostic validation output with accept/reject reasons per article
- Added validation summary showing total counts at the end of each run
- Added `requests==2.32.3` and `feedparser==6.0.11` to `requirements.txt`

---

## [0.2.4] - 2026-06-29

### Step 2.4 — Restructured docs/implementation into step folders
- Reorganised `docs/implementation/` into `step-1/`, `step-2/`, and `step-3/` subfolders
- Moved all existing implementation documentation files into their respective folders
- No file contents were modified during restructuring

---

## [0.2.3] - 2026-06-29

### Step 2.3 — Database Schema Migration: Add Classification Metadata
- Added `classification_confidence` column to `funding_events` table
- Column type is `TEXT`, nullable
- CHECK constraint restricts values to `Strong`, `Moderate`, `Weak`, or `NULL`
- Migration saved to `sql/add_classification_confidence.sql`
- Created `docs/implementation/step-2/02.3_Classification_Confidence_Migration.md`
- Validated via Supabase SQL Editor — NULL accepted, Strong accepted, High correctly rejected

---

## [0.2.2] - 2026-06-29

### Step 2.2 — Added Implementation Roadmap
- Added `00_Implementation_Roadmap.md` to `docs/implementation/`
- Documented planned development milestones and architecture decisions

---

## [0.2.1] - 2026-06-29

### Step 2.1 — Added Implementation Documentation
- Added initial implementation documentation files to `docs/implementation/`
- Created `01_Project_Setup.md` documenting Step 1
- Created `01.1_Project_Documentation.md` documenting Step 1.1
- Created `02_Database_Schema.md` documenting Step 2

---

## [0.2.0] - 2026-06-29

### Step 2 — Database Schema
- Designed and created initial PostgreSQL schema for Supabase
- Created `companies` table with UUID primary key, 20 fields, `updated_at` trigger, and 2 indexes
- Created `funding_events` table with UUID primary key, 15 fields, `article_url` unique constraint, and 3 indexes
- Used `TIMESTAMPTZ` for all timestamps for timezone safety
- Used `ON DELETE RESTRICT` on `company_id` foreign key to prevent accidental data loss
- Schema saved to `sql/create_tables.sql`

---

## [0.1.1] - 2026-06-29

### Step 1.1 — Project Documentation
- Added `docs/`, `sql/`, and `tests/` folders
- Created `PROJECT_ARCHITECTURE.md` with technical overview, system architecture diagram, and milestone table
- Created `CHANGELOG.md` and `TODO.md`
- Created `docs/README.md`, `sql/README.md`, and `tests/README.md`
- Updated `README.md` with folder reference table and Getting Started section

---

## [0.1.0] - 2026-06-29

### Added
- Initial project setup
- Git repository initialized
- GitHub repository connected
- Python virtual environment created (`.venv`)
- Project skeleton completed: `scraper/`, `logs/`, `config.py`, `main.py`, `requirements.txt`, `.env`, `.env.example`
- `.gitignore` configured for Python, virtual environments, secrets, and macOS artifacts
- `docs/`, `sql/`, `tests/` folders added for long-term structure
- `PROJECT_ARCHITECTURE.md` with technical overview and planned milestones
- `CHANGELOG.md`, `TODO.md` added
- `README.md` updated with folder reference
