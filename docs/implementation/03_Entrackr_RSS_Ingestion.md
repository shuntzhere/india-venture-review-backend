# Step 3: Entrackr RSS Ingestion Module

Built the first working module of the scraping pipeline — connecting to Entrackr's RSS feed, filtering for funding announcements, and returning structured article data.

---

## Objective

Build `scraper/entrackr.py` to fetch articles from Entrackr's RSS feed published within the last 24 hours, filter for funding announcements using keyword matching, and return structured raw article data as a list of dictionaries. No database writes, parsing logic, or scheduling was included in this step.

---

## Implementation Prompt

> This is Step 3 of 7 in a structured build process.
> Do exactly what is requested in this step and nothing more.
> Do not anticipate future steps.
> Do not write any database, logging, parser, or scheduling code.
> If you believe a technical decision could significantly improve reliability or maintainability, explain it before implementing it. Do not silently add features, logic, or architectural changes that are outside the scope of this milestone.
>
> **Objective**
> Build the Entrackr RSS ingestion module inside scraper/entrackr.py
> This module should connect to Entrackr's RSS feed, retrieve newly published articles, filter for funding announcements only, and return structured raw article data.
> It should not write anything to the database.
>
> **What this module should do**
> - Fetch Entrackr's RSS feed.
> - Parse all articles published within the last 24 hours.
> - Filter for funding announcements only.
>
> Filter out articles related to: Opinion, Layoffs, Acquisitions, Policy news, Product launches, Interviews, General startup news
>
> **Funding Article Detection**
> Use keyword matching on article titles to identify funding announcements.
> Initial keywords include: raises, funding, secures, investment, round, backed, Series, Seed, Pre-Seed, venture
> The keyword list should be stored as a configurable constant within scraper/entrackr.py rather than being scattered throughout the implementation.
> Implement the filtering logic in a dedicated function so it can be replaced later by a more advanced classifier without affecting the rest of the ingestion pipeline.
>
> **Returned Data**
> For each funding article that passes the filter, return: article_title, article_url, article_publication_date, source_name (always "Entrackr"), raw_content (the full text or summary available from the RSS feed)
>
> Return the results as a list of dictionaries so the parser can process them during Step 4.
>
> **Requirements**
> - Write all implementation inside scraper/entrackr.py only
> - The module should be importable and callable as a function.
> - If the RSS feed is unavailable or times out, gracefully return an empty list rather than crashing.
> - Add clear comments explaining what each section of the code does.
> - Use only standard libraries or commonly available Python packages.
> - If additional dependencies are required, update requirements.txt.
>
> **Validation Output**
> For each processed article, indicate whether it was accepted or rejected.
> For rejected articles, include a brief reason.
> This diagnostic output is intended only to assist validation during development.
>
> **Deliverables**
> - Complete scraper/entrackr.py
> - Updated requirements.txt (if needed)
> - A simple Terminal command to verify the RSS feed is accessible, articles are being retrieved, funding articles are correctly filtered, and the returned data structure is correct.
>
> **Architectural Note (Documentation Only)**
> This milestone is intentionally focused on validating the daily RSS ingestion pipeline.
> Historical data collection is intentionally out of scope for this milestone.
> Once the daily ingestion pipeline has been validated through several consecutive successful runs, a separate milestone will be implemented to build a historical import pipeline capable of backfilling older funding announcements.
> That future historical pipeline should reuse the same parser, validation, and database insertion components developed in later milestones.
> Do not implement historical imports, archive pagination, generalized date-range ingestion, or backfill logic in this step.

---

## Technical Decisions

**RSS over website scraping**
Entrackr's RSS feed (`https://entrackr.com/rss`, discovered from the site's `<link rel="alternate">` tag) provides pre-structured article data without requiring HTML scraping of article listing pages. RSS is more stable than scraping DOM structure, lighter on the server, and unlikely to break due to layout changes. For a daily ingestion pipeline this is the correct starting point.

**`requests` + `feedparser` instead of `feedparser` alone**
`feedparser` can fetch an RSS URL directly, but it does not support setting a request timeout. If Entrackr's server is slow or unresponsive, a direct `feedparser` fetch would hang indefinitely. By using `requests` to fetch the raw feed content first (with a configurable `FEED_TIMEOUT_SECONDS`) and passing the content to `feedparser` for parsing, we get reliable timeout control. This is the single most important reliability decision in this module.

**24-hour lookback window**
The pipeline is designed to run once daily. A 24-hour window ensures every article published since the last run is captured, with a natural overlap buffer if the run is delayed slightly. Articles older than the window are skipped rather than rejected to preserve a clean distinction between time filtering and classification filtering in the validation output.

**Keyword list as a configurable constant (`FUNDING_KEYWORDS`)**
All keywords are defined in one place at the top of the module. This means the filtering behaviour can be changed by editing a single list without touching any function logic. If keywords were scattered across the implementation they would be hard to audit and easy to miss when updating.

**Dedicated classification function (`is_funding_article`)**
The keyword check is isolated in its own function rather than inlined into the main loop. This means the entire classification strategy can be replaced — with a regex engine, NLP model, or AI classifier — by rewriting one function. The surrounding ingestion pipeline requires no modification. This separation was an explicit requirement and became the foundation for the classifier architecture in Steps 3.1 and 3.2.

**Returned data structure — list of dictionaries**
Each accepted article is returned as a Python dictionary with consistent keys. A list of dicts is the natural interface between the ingestion module and the parser: it is iterable, inspectable, serialisable to JSON, and requires no custom classes. The parser in Step 4 can loop over the list and access fields by name.

**Graceful error handling — empty list on failure**
If the RSS feed is unreachable or returns an HTTP error, the function catches the exception and returns an empty list. This means a network failure or a temporary Entrackr outage will not crash the pipeline — it will simply produce no results for that run, which can be detected and logged in a future milestone.

**Dependencies: `requests` and `feedparser`**
`requests` is the standard Python HTTP library — well-maintained, widely used, and supports timeouts, headers, and retries cleanly. `feedparser` is the standard RSS/Atom parsing library for Python — it handles the many variations in RSS feed structure that a hand-rolled XML parser would miss. Both were pinned to specific versions in `requirements.txt` for reproducibility.

---

## Files Created or Modified

| File | Action |
|---|---|
| `scraper/entrackr.py` | Created — full RSS ingestion module with keyword filtering and validation output |
| `requirements.txt` | Updated — added `requests==2.32.3` and `feedparser==6.0.11` |

---

## Verification Performed

- Ran `python3 -m scraper.entrackr` and confirmed the RSS feed returned a 200 response.
- Confirmed articles within the 24-hour window were identified and processed.
- Confirmed funding articles were accepted with the matching keyword printed (e.g. `[ACCEPTED] Matched keyword 'round' — The Capitalist Ventures bags Rs 10 Cr seed round`).
- Confirmed non-funding articles were rejected with reason (e.g. `[REJECTED] No funding keyword detected — Prosus India posts $781 Mn revenue`).
- Confirmed the validation summary printed correct totals at the end of each run.
- Confirmed the returned value was a list of dicts, each containing all five required fields: `article_title`, `article_url`, `article_publication_date`, `source_name`, `raw_content`.

**Note:** The initial implementation attempted `https://entrackr.com/feed/` (standard WordPress path) which returned a 404. The correct URL `https://entrackr.com/rss` was discovered by inspecting the `<link rel="alternate">` tag in the Entrackr homepage HTML.

---

## Outcome

The project gained its first working scraper module. Running `python3 -m scraper.entrackr` connected to Entrackr's live RSS feed, retrieved 50 articles, applied the 24-hour filter, and returned 7 accepted funding articles with clean structured data. The module was importable, callable, and error-tolerant.

**Commit:** `2a55090 — Step 3: Implemented Entrackr RSS ingestion module`

---

## Next Step

Step 3.1 — Engineering Refinement of the Entrackr RSS Ingestion Module: improve keyword matching accuracy, clean HTML from `raw_content`, add URL deduplication, add HTTP User-Agent, and improve validation output.
