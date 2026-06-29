# Project Architecture

## Purpose

India Venture Review is an automated data pipeline that scrapes Indian startup funding news from Entrackr, parses and structures the data, and stores it in a Supabase (PostgreSQL) database. The long-term goal is to enrich this data with AI, surface it through a public website and API, and support analytics and content generation.

---

## Folder Structure

```
india-venture-review/
├── scraper/              # Core scraping and data pipeline logic
│   ├── __init__.py       # Package initializer
│   ├── entrackr.py       # Fetches raw HTML from Entrackr.com
│   ├── parser.py         # Extracts structured data from raw HTML
│   ├── database.py       # Reads and writes records to Supabase
│   ├── logger.py         # Shared logging configuration
│   └── utils.py          # Shared helper functions
├── docs/                 # Project documentation
├── sql/                  # Database schema and migration files
├── tests/                # Unit and integration tests
├── logs/                 # Runtime log output (git-ignored)
├── config.py             # Loads environment variables
├── main.py               # Entry point — runs the full pipeline
├── requirements.txt      # Python package dependencies
├── .env                  # Secret credentials (git-ignored)
├── .env.example          # Template for .env
├── PROJECT_ARCHITECTURE.md
├── CHANGELOG.md
├── TODO.md
└── README.md
```

---

## High-Level System Architecture

```
Entrackr.com
     │
     ▼
entrackr.py       ← HTTP requests, raw HTML retrieval
     │
     ▼
parser.py         ← HTML parsing, data extraction and structuring
     │
     ▼
database.py       ← Deduplication, insert/update to Supabase
     │
     ▼
Supabase (PostgreSQL)
```

Supporting modules:
- `config.py` supplies credentials to all modules via environment variables
- `logger.py` provides a shared logger used across all modules
- `utils.py` provides reusable helpers (text cleaning, date normalization, etc.)
- `main.py` orchestrates the full pipeline end to end

---

## Planned Development Milestones

| Milestone | Description |
|---|---|
| 1 | Project skeleton and structure |
| 2 | Supabase schema and database connector |
| 3 | Entrackr scraper and article parser |
| 4 | Logging and scheduling |
| 5 | Unit tests |
| 6 | AI enrichment layer |
| 7 | Additional news sources |
| 8 | Analytics and content generation |
| 9 | Public website and API |

---

## Current Modules

| Module | Status | Description |
|---|---|---|
| `scraper/entrackr.py` | Planned | Fetches pages from Entrackr |
| `scraper/parser.py` | Planned | Parses funding data from HTML |
| `scraper/database.py` | Planned | Supabase read/write operations |
| `scraper/logger.py` | Planned | Logging setup |
| `scraper/utils.py` | Planned | Shared utility functions |
| `config.py` | Planned | Environment variable loader |
| `main.py` | Planned | Pipeline entry point |

---

## Future Modules

| Module | Description |
|---|---|
| AI enrichment | Classify funding rounds, extract entities, generate summaries using an LLM |
| Additional news sources | Inc42, YourStory, VCCircle, and others |
| Analytics | Trend detection, sector breakdowns, investor activity reports |
| Content generation | Automated newsletter or digest generation from stored data |
| Website | Public-facing frontend to browse and search funding data |
| API | REST or GraphQL API to serve structured funding data to consumers |

---

*Update this document whenever the project structure or architecture changes significantly.*
