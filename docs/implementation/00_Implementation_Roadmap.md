# Implementation Roadmap

This is the entry point for the engineering implementation history of India Venture Review.

---

## Project Overview

India Venture Review is a venture intelligence platform focused on the Indian startup ecosystem. It automatically collects, structures, and stores startup funding data from Indian financial news sources, beginning with Entrackr.

The long-term goal is to build a comprehensive platform for tracking funding activity, enriching company profiles, and surfacing insights about the Indian venture capital landscape.

This documentation captures the complete engineering implementation history of the startup — what was built, why it was built, how it was verified, and what decisions were made at each milestone. It is intended to allow any engineer, or the original author returning after time away, to understand the full build history without needing to search through prior conversations.

---

## Development Philosophy

The startup is intentionally being built in small, verifiable milestones. Each milestone is scoped to solve one well-defined problem before the next begins.

Each milestone must:

- Solve one well-defined problem
- Be reviewed before acceptance
- Be documented in `docs/implementation/`
- Be committed to Git with a descriptive message
- Be pushed to GitHub before the next milestone begins

This approach ensures the project always has a working, documented, committed state — and that no milestone carries hidden complexity from a previous one.

---

## Implementation Workflow

Every milestone follows the same workflow:

```
Planning
    ↓
Implementation (Claude Code)
    ↓
Review
    ↓
Testing / Validation
    ↓
Documentation
    ↓
Git Commit
    ↓
GitHub Push
```

No milestone is considered complete until all steps in this workflow are done.

---

## Complete Implementation Roadmap

### Step 1 — Project Setup
**Status:** ✅ Completed

**Purpose:**
Create the project folder structure, Python virtual environment, configuration files, and Git hygiene. Every file created in this step is a placeholder only — no application logic.

**Reference:**
- [01_Project_Setup.md](01_Project_Setup.md)

---

### Step 1.1 — Project Documentation
**Status:** ✅ Completed

**Purpose:**
Establish technical documentation and an expanded folder structure before any application code is written. Includes architecture overview, changelog, development backlog, and folder READMEs.

**Reference:**
- [01.1_Project_Documentation.md](01.1_Project_Documentation.md)

---

### Step 2 — Database Schema
**Status:** ✅ Completed

**Purpose:**
Design and implement the initial PostgreSQL schema in Supabase. Creates the `companies` and `funding_events` tables with appropriate constraints, indexes, and a trigger for `updated_at` maintenance.

**Reference:**
- [02_Database_Schema.md](02_Database_Schema.md)

---

### Step 3 — Entrackr Scraper
**Status:** ⏳ Planned

**Purpose:**
Build the scraper that fetches funding-related articles from Entrackr. Handles HTTP requests, pagination, and raw HTML retrieval.

---

### Step 4 — Funding Article Parser
**Status:** ⏳ Planned

**Purpose:**
Extract structured funding information from raw HTML articles. Outputs clean, typed fields ready for database insertion.

---

### Step 5 — Supabase Database Connector
**Status:** ⏳ Planned

**Purpose:**
Insert parsed funding data into Supabase with duplicate detection. Handles company lookup or creation and links funding events to the correct company record.

---

### Step 6 — Logging
**Status:** ⏳ Planned

**Purpose:**
Record scraper runs, saved records, errors, and execution history to structured log files. Provides an audit trail for every pipeline execution.

---

### Step 7 — Pipeline Integration and Scheduling
**Status:** ⏳ Planned

**Purpose:**
Connect all modules into a complete end-to-end pipeline and schedule automated daily execution. `main.py` becomes the single entry point that orchestrates the full flow.

---

## Future Milestones

The following are possible phases beyond the MVP. They are listed here for planning purposes only and should not influence the current implementation.

- **Additional news sources** — Inc42, YourStory, VCCircle, and others
- **AI-based company enrichment** — entity extraction, classification, and profile summarization
- **Investor normalization** — deduplicate and link investor names to structured profiles
- **Public API** — REST or GraphQL endpoint for structured funding data
- **Analytics** — sector trends, investor activity, funding round breakdowns
- **Website** — public-facing frontend to browse and search funding data
- **Search** — full-text and filtered search across companies and funding events
- **Content generation** — automated digest or newsletter output
- **Newsletter** — recurring distribution of curated funding summaries
- **Admin dashboard** — internal tooling for data review and manual enrichment
