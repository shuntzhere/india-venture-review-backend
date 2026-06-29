# Development Backlog

Tasks are listed in intended build order.

---

## Completed

- [x] Initial project setup and structure
- [x] Project documentation — architecture, changelog, roadmap
- [x] Supabase schema — `companies` and `funding_events` tables
- [x] Build Entrackr RSS ingestion module (`scraper/entrackr.py`)
- [x] Engineering refinement of ingestion module — word-boundary matching, HTML cleaning, deduplication, User-Agent
- [x] Implement multi-signal funding classifier — `SIGNAL_REGISTRY`, weighted scoring, confidence labels

---

## Up Next

- [ ] Step 4 — Build article parser — extract structured funding fields from `raw_content`
- [ ] Step 4 — Address IPO listing false positive edge case detected in Step 3.2 classifier output
- [ ] Step 5 — Build database connector — insert and deduplicate records in Supabase
- [ ] Step 5 — Add `confidence_level` column to `funding_events` table in Supabase

---

## Backlog

- [ ] Step 6 — Add logging — structured log output to `logs/` with rotation
- [ ] Step 7 — Wire `main.py` — connect all modules into a complete end-to-end pipeline
- [ ] Step 7 — Add scheduling — run the scraper automatically on a daily interval
- [ ] Add unit tests — cover parser, utils, and database modules
- [ ] Add support for additional news sources — Inc42, YourStory, VCCircle

---

## Future

- [ ] AI enrichment layer — entity extraction, classification, summarization
- [ ] Analytics module — sector trends, investor activity, funding round breakdowns
- [ ] Content generation — automated digest or newsletter output
- [ ] Public website — browsable frontend for funding data
- [ ] Public API — REST or GraphQL endpoint for structured data access
