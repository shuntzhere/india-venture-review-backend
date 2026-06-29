# Changelog

All notable changes to this project are documented here.

---

## [Unreleased]

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
