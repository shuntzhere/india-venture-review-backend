# India Venture Review — Backend

The data pipeline powering [India Venture Review](https://github.com/shuntzhere/india-venture-review-frontend) — an automated scraper that pulls Indian startup funding news, classifies it, and stores structured records in Supabase.

---

## Project Structure

| Path | Description |
|---|---|
| `scraper/` | Core pipeline modules: fetching, parsing, database, logging, and utilities |
| `docs/` | Project documentation, guides, and design notes |
| `sql/` | Supabase schema definitions and migration scripts |
| `tests/` | Unit and integration tests |
| `logs/` | Runtime log output (generated at runtime, not committed to git) |
| `config.py` | Loads environment variables for use across the project |
| `main.py` | Entry point — runs the full scraping pipeline |
| `requirements.txt` | Python package dependencies |
| `.env` | Secret credentials — copy from `.env.example` and fill in your values |
| `.env.example` | Template showing which environment variables are required |
| `PROJECT_ARCHITECTURE.md` | Technical overview, system architecture, and planned milestones |
| `CHANGELOG.md` | Record of all notable changes to the project |
| `TODO.md` | Development backlog and upcoming milestones |

---

## Getting Started

1. Clone the repository
2. Copy `.env.example` to `.env` and add your Supabase credentials
3. Create and activate the virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run the scraper:
   ```bash
   python3 main.py
   ```

---

## Related

- **Frontend**: [india-venture-review-frontend](https://github.com/shuntzhere/india-venture-review-frontend) — React web app that surfaces the data this pipeline produces
