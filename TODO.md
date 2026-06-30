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
- [x] Build Evidence Extraction Engine — two-stage extraction, domain extractors, progressive evidence collection, validation output
- [x] Build Database Connector — company lookup/creation, funding event insertion, duplicate detection, operational summary
- [x] Wire `classification_confidence` through full pipeline — classifier → parser → database
- [x] Improve company name extraction for investor-led titles — "X leads round in Y", "X makes investment in Y", etc.
- [x] Build Logger — structured log files in `logs/`, per-article outcomes, failure reporting, pipeline status determination
- [x] Wire `main.py` — single entry point running the complete pipeline with `python main.py`
- [x] Configure launchd scheduler — automated daily run at 7:00 AM IST via macOS LaunchAgent

---

## Up Next

MVP complete. The pipeline runs automatically every morning.

---

## Backlog

- [ ] Add unit tests — cover parser, utils, and database modules
- [ ] Add support for additional news sources — Inc42, YourStory, VCCircle

---

## Future

- [ ] AI enrichment layer — entity extraction, classification, summarization
- [ ] Analytics module — sector trends, investor activity, funding round breakdowns
- [ ] Content generation — automated digest or newsletter output
- [ ] Public website — browsable frontend for funding data
- [ ] Public API — REST or GraphQL endpoint for structured data access
