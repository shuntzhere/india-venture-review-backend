# Step 2: Database Schema

Designed and created the initial PostgreSQL schema for Supabase covering companies and funding events.

---

## Objective

Design a clean, normalized, and scalable relational schema to store Indian startup funding data. The schema needed to support an MVP scraper while remaining extensible enough for a long-term venture intelligence platform. No application code was written in this step — only the SQL schema file.

---

## Implementation Prompt

> This is Step 2 of 7 in a structured build process.
>
> Do exactly what is requested in this step and nothing more.
>
> Do not anticipate future steps.
>
> Do not write any Python code.
>
> Do not create scraper, parser, logging, scheduling, or application logic.
>
> If you believe a database design decision could significantly improve maintainability or scalability, explain it before implementing it. Do not silently add tables, fields, or architectural changes.
>
> **Objective**
> Design the initial PostgreSQL database schema for Supabase.
>
> The long-term goal is to build a venture intelligence platform, so the schema should be clean, normalized, and scalable while remaining simple enough for an MVP.
>
> **Create the following tables**
>
> Table 1 — companies
> Each startup should exist only once.
>
> Fields: id, company_name, website, linkedin_url, logo_url, description, industry, sub_industry, business_model, headquarters_city, headquarters_state, headquarters_country, founded_year, founders, employee_count, total_funding, latest_funding_round, latest_funding_amount, first_seen_date, created_at, updated_at
>
> Notes:
> * Do not make company_name unique.
> * total_funding is maintained by the application rather than scraped directly.
> * sub_industry is intentionally nullable. It will not be scraped during initial ingestion and is expected to be populated later through manual curation or AI-assisted enrichment.
>
> Table 2 — funding_events
> Each funding announcement should become a separate record linked to a company.
>
> Fields: id, company_id, funding_amount, currency, funding_round, lead_investors, participating_investors, valuation, article_title, article_summary, article_publication_date, article_url, source_name, scraped_timestamp, created_at
>
> Notes:
> * source_name should remain plain text for now.
> * article_summary will be manually generated later and is not scraped.
>
> **Database Requirements**
>
> Use PostgreSQL syntax compatible with Supabase.
> Generate the SQL inside sql/create_tables.sql
>
> Requirements:
> * Create tables only if they do not already exist.
> * Use UUID primary keys.
> * Add appropriate foreign keys.
> * Add sensible indexes for frequently queried fields such as: company_name, company_id, article_publication_date, source_name
> * Use appropriate SQL data types.
> * Allow NULL where information may not always be available.
> * Use appropriate constraints.
> * Explain every design decision.
>
> **Deliverables**
> * Create the SQL script.
> * Explain how to execute the SQL inside Supabase.
> * Explain how to verify both tables were created correctly.
> * Do not execute anything automatically.
> * Stop after Step 2 and wait for my confirmation before continuing.

---

## Technical Decisions

**`TIMESTAMPTZ` instead of `TIMESTAMP`**
PostgreSQL offers two timestamp types: `TIMESTAMP` (no timezone awareness) and `TIMESTAMPTZ` (stores in UTC, displays in local timezone). Supabase runs in UTC. Using `TIMESTAMPTZ` for all timestamp fields prevents subtle timezone bugs if the scraper ever runs in a different timezone. All `created_at`, `updated_at`, and `scraped_timestamp` fields use `TIMESTAMPTZ`.

**`updated_at` auto-update trigger**
A PostgreSQL trigger function (`update_updated_at_column`) was added to automatically set `updated_at = now()` whenever a row in the `companies` table is modified. Without this, the application would need to manually set `updated_at` on every update — easy to forget and a common source of stale data. This is pure database infrastructure, not application logic.

**`ON DELETE RESTRICT` on the `company_id` foreign key**
When a company row is deleted, `RESTRICT` prevents the deletion if any linked `funding_events` rows exist. The alternative (`CASCADE`) would silently delete all related funding events — too destructive for a data platform. `RESTRICT` forces intentional cleanup and prevents accidental data loss.

**`article_url` as the deduplication key**
`article_url` is defined as `UNIQUE NOT NULL` on `funding_events`. This is the natural deduplication key: if the scraper runs multiple times, it cannot insert the same article twice regardless of run frequency. The application uses `INSERT ... ON CONFLICT DO NOTHING` against this constraint.

**Denormalized text fields for investors and founders**
`lead_investors`, `participating_investors`, and `founders` are stored as plain text (e.g. `"Sequoia, Accel"`) rather than normalized into a separate `investors` table. This is a deliberate MVP simplification. Normalizing investors is a future milestone that would add complexity with no current benefit.

**`company_name` is not unique**
Two real Indian startups can share the same name. Making `company_name` unique would cause false conflicts. Deduplication is handled at the application layer using fuzzy matching rather than a database constraint.

**`sub_industry` intentionally nullable**
`sub_industry` will not be populated during initial scraping. It is reserved for a later milestone involving manual curation or AI-assisted enrichment. The field is present in the schema now so no future migration is needed to add it.

**`source_name` as plain text**
`source_name` (e.g. `"Entrackr"`) is stored as plain text rather than a foreign key to a `sources` table. A `sources` table is a future milestone. Normalizing it now would add a join to every query with no current benefit.

**`scraped_timestamp` and `created_at` are separate fields**
`scraped_timestamp` records when the scraper fetched the article. `created_at` records when the row was inserted into the database. These can differ if there is a processing delay between scraping and insertion. Both are kept to preserve a complete audit trail.

---

## Files Created or Modified

| File | Action |
|---|---|
| `sql/create_tables.sql` | Created — full schema with tables, trigger, trigger function, constraints, and indexes |

---

## Verification Performed

Verification steps were provided for execution in the Supabase SQL Editor after running the schema:

1. **Table Editor** — confirmed `companies` and `funding_events` appeared in the Supabase UI.
2. **`information_schema.tables` query** — confirmed both tables existed in the `public` schema.
3. **`information_schema.columns` query** — confirmed all columns, data types, and nullability matched the specification.
4. **`pg_indexes` query** — confirmed all 5 indexes were created: `idx_companies_company_name`, `idx_companies_industry`, `idx_funding_events_company_id`, `idx_funding_events_article_publication_date`, `idx_funding_events_source_name`.

---

## Outcome

The project had a production-ready PostgreSQL schema in Supabase with two normalized tables, correct constraints, a deduplication key, an auto-updating `updated_at` trigger, and query-optimized indexes. The schema is extensible enough to support future milestones (AI enrichment, additional sources, analytics) without requiring a redesign.

**Commit:** `d8fef71 — Step 2: Created initial database schema`

---

## Next Step

Step 3 — Build the Entrackr scraper and article parser (`scraper/entrackr.py`, `scraper/parser.py`).
