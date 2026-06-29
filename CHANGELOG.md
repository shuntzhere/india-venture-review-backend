# Changelog

All notable changes to this project are documented here.

---

## [Unreleased]

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
