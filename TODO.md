# Development Backlog

Tasks are listed in intended build order.

---

## In Progress

- [ ] Improve project structure and documentation

---

## Up Next

- [ ] Build Supabase schema — define tables for funding rounds, companies, investors
- [ ] Build Entrackr scraper — fetch article listing and individual article pages
- [ ] Build article parser — extract structured fields from raw HTML
- [ ] Build database connector — insert and deduplicate records in Supabase

---

## Backlog

- [ ] Add logging — structured log output to `logs/` with rotation
- [ ] Add scheduling — run the scraper automatically on a recurring interval
- [ ] Add unit tests — cover parser, utils, and database modules
- [ ] Add support for additional news sources — Inc42, YourStory, VCCircle

---

## Future

- [ ] AI enrichment layer — entity extraction, classification, summarization
- [ ] Analytics module — sector trends, investor activity, funding round breakdowns
- [ ] Content generation — automated digest or newsletter output
- [ ] Public website — browsable frontend for funding data
- [ ] Public API — REST or GraphQL endpoint for structured data access
