# Step 4: Evidence Extraction Engine v1

Built the Evidence Extraction Engine — the second stage of the ingestion pipeline — transforming normalized funding articles into structured funding records using only explicitly verifiable information from each article.

---

## Objective

Build Version 1 of the Evidence Extraction Engine inside `scraper/parser.py`. The engine accepts a normalized article produced by the Entrackr adapter and returns a structured funding record containing every business field defined by the current `funding_events` and `companies` schema that can be deterministically extracted from the article content.

The implementation must not write to the database, perform scheduling, or anticipate future steps.

---

## Implementation Prompt

> This is Step 4 of 7 in a structured build process. Do exactly what is requested in this step and nothing more. Do not anticipate future steps. Do not add extra logic, optimization, or features not explicitly requested. I will give you the next step separately.
>
> Follow all conventions documented in CONTRIBUTING.md.
>
> Read the full specification for this milestone from:
> specification/step-04-evidence-extraction-engine.md
>
> Read it completely before beginning implementation. The specification is the single source of truth for this milestone. Do not proceed until you have read it in full.

---

## Technical Decisions

**`beautifulsoup4` for full article HTML parsing**
Stage 2 downloads complete article pages which contain navigation bars, sidebars, footers, related-article links, and advertisement text alongside the article body. Stripping all HTML with the stdlib `_HTMLTextExtractor` (sufficient for clean RSS content) would mix this noise into the extracted text and corrupt extraction. `BeautifulSoup` allows the engine to prefer semantic HTML elements (`<article>`, `<main>`) and explicitly remove non-content tags (`<nav>`, `<header>`, `<footer>`, `<aside>`) before extracting text. The stdlib `_HTMLTextExtractor` is retained for RSS content, which arrives pre-cleaned.

**Searching title and content separately, not concatenated**
An early implementation concatenated `title + " " + content` before running investor extraction patterns. This caused the regex to continue past the investor name into the following sentence when the title ended mid-pattern (e.g., "led by Venture Catalysts" in the title, followed immediately by the article body with no sentence boundary). Searching the title first (using its natural end-of-string boundary) and falling back to content separately produced clean results: "Venture Catalysts" and "Bharat Value Fund" were correctly isolated.

**Non-greedy descriptor stripping for company name extraction**
Company names in Indian startup headlines are frequently preceded by sector and company-type descriptors: "Healthcare startup MyKare.ai raises...", "AI data infrastructure startup Clairva raises...". The original `_DESCRIPTOR_PREFIX` regex used a fixed vocabulary list that missed multi-word descriptors. The replacement uses a non-greedy `.*?\b(?:startup|company|firm|platform|app|brand|unicorn)\b\s+` pattern, which strips everything up to the first company-type word regardless of how many sector words precede it. This correctly extracts "MyKare.ai" from "Healthcare startup MyKare.ai" and "Clairva" from "AI data infrastructure startup Clairva".

**PRIMARY_FIELDS drives Stage 2 escalation**
The engine only retrieves the full article when at least one of four primary business fields is unavailable after Stage 1: `company_name`, `funding_amount`, `funding_round`, `lead_investors`. Secondary fields (headquarters, website, founded year, description, valuation, participating investors) do not trigger Stage 2 on their own. This avoids unnecessary network requests for articles where the headline alone contains all essential business information.

**Evidence merge preserves Stage 1 values**
Stage 2 evidence is merged into the Stage 1 record using a `_merge_evidence` function that only populates `None` fields. Existing non-`None` values from Stage 1 are never overwritten, even if Stage 2 contains a different value for the same field. Verified evidence from the closer, more-structured RSS headline is considered more reliable than the same information embedded in article body prose.

**Polite delay between consecutive full-article requests**
When multiple articles require Stage 2 retrieval in a single run, a 1-second delay is introduced between consecutive requests. No delay is applied before the first retrieval. This respects the source server without materially affecting the daily ingestion workflow.

**Normalized article contract isolates source-specific logic**
The extraction engine never reads Entrackr-specific field names directly. The `normalize_entrackr_article` adapter in `parser.py` is the single place that knows about Entrackr's RSS field structure. All other extraction logic operates on the normalized contract (`article_title`, `article_url`, `article_publication_date`, `source_name`, `raw_content`). Future source adapters produce the same contract independently; the extraction engine requires no modification.

**`None` for all unavailable information**
The engine never returns `Unknown`, `N/A`, empty strings, or placeholder values. If information cannot be explicitly verified from the article, the field is `None`. Missing information is preferable to incorrect information. The validation report surfaces missing fields explicitly to support the human review workflow.

**Validation report is separate from the structured record**
The structured record returned by `process_article` contains only business fields and metadata — exactly what the database insertion pipeline in Step 5 will consume. Confidence labels, evidence source, missing field lists, and manual review recommendations belong exclusively to the validation report, which is never persisted.

**Known edge cases discovered during validation**
Three extraction limitations were identified and documented in `docs/backlog/parser-improvement.md` rather than being addressed in this step:
1. Investor-first headlines ("Boundless Ventures leads pre-seed round in Lytmus AI") — company name is `None` because the company appears after a preposition, not before a funding verb. Manual review is recommended.
2. Strategic investment headlines ("Yash Raj Films makes strategic investment in Rusk Media") — same pattern.
3. IPO/listing articles ("Turtlemint lists at 11.25% discount on market debut") — the classifier accepts these because listing share price patterns match the amount detector. The extractor correctly returns `None` for funding round and company name and recommends manual review.

---

## Files Created or Modified

| File | Action |
|---|---|
| `scraper/parser.py` | Created — full Evidence Extraction Engine (892 lines) |
| `requirements.txt` | Updated — added `beautifulsoup4==4.12.3` |
| `docs/backlog/parser-improvement.md` | Created — tracks known extraction limitations discovered during Step 4 validation |

---

## Architecture Summary

```
Entrackr adapter
      │
      ▼
Normalized Article
      │
      ▼
Input Validation
      │
      ▼
Parser Orchestrator
      │
      ├── Stage 1 Extraction (RSS title + content)
      │       ├── extract_company_fields()
      │       ├── extract_funding_fields()
      │       ├── extract_investor_fields()
      │       └── extract_metadata_fields()
      │
      ├── Primary fields complete? → No → Stage 2 (full article)
      │                                       └── same four extractors
      │
      ├── Evidence Merge (_merge_evidence)
      │       └── Stage 1 values preserved; Stage 2 fills None fields only
      │
      ├── Output Validation
      │
      └── Returns: (structured_record, validation_report)
```

**Shared extraction utilities** (used by multiple domain extractors):
- `_parse_amount(text)` — extracts (float, currency string) from USD/INR amount patterns
- `_extract_funding_round(text)` — matches Pre-Seed, Seed, Series A–Z, Bridge, Angel, Growth, Debt, Grant
- `_extract_lead_investors(title, content)` — matches "led by" / "backed by" phrases; searches title first
- `_extract_participating_investors(title, content)` — matches "with participation from" / "participated by"
- `_extract_valuation(text)` — matches "valued at" / "valuation of" patterns

---

## Verification Performed

- Ran `python3 -m scraper.parser` against 8 live funding articles.
- Confirmed Stage 2 triggered for 6 of 8 articles where primary fields were missing after Stage 1.
- Confirmed Stage 2 was not triggered for 2 articles where all primary fields were available from the RSS headline alone.
- Confirmed lead investor extraction correctly returned "Venture Catalysts" and "Bharat Value Fund" after fixing the title-concatenation issue.
- Confirmed company name correctly returned "MyKare.ai", "Clairva", "Incuspaze" after improving descriptor stripping.
- Confirmed all 8 articles produced structured records with no pipeline failures.
- Confirmed Turtlemint IPO article returned `None` for company name and funding round, and was flagged for manual review.
- Confirmed the validation summary printed correct totals: 8 processed, 8 parsed, 6 full article retrievals, 3 requiring manual review, 0 failures.
- Confirmed `None` (not empty string or placeholder) used for all unavailable fields.

---

## Outcome

The project gained Version 1 of the Evidence Extraction Engine. Running `python3 -m scraper.parser` fetches recent funding articles, runs them through the two-stage extraction pipeline, and prints a structured validation report for each article. The engine extracted an average of 6.2 of 15 business fields per article from live Entrackr content, with the primary business fields (company name, amount, round, lead investor) successfully extracted for most articles. The architecture supports future source adapters, new extraction rules, and AI-assisted enrichment without structural changes.

**Commit:** `be7c309 — Step 4: Implemented Evidence Extraction Engine`

---

## Next Step

Step 5 — Database Connector: insert structured funding records into Supabase, handle deduplication via `article_url` unique constraint, and populate the `companies` and `funding_events` tables.
