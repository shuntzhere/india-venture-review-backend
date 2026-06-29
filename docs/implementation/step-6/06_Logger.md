# Step 6: Logger

Implemented the Logger — the fifth and final stage of the ingestion pipeline — recording every pipeline execution as a structured log file in `logs/`.

---

## Objective

Build `scraper/logger.py` to write a human-readable log file after every pipeline run, capturing run metadata, configuration, software version, pipeline statistics, per-article outcomes, and failure details. The logger must never cause the pipeline to fail — if logging itself fails, the error is printed to the terminal and the pipeline continues.

---

## Implementation Prompt

> This is Step 6 of 7 in a structured build process. Do exactly what is requested in this step and nothing more. Do not anticipate future steps. Do not add extra logic, optimization, or features not explicitly requested. I will give you the next step separately.
>
> Follow all conventions documented in CONTRIBUTING.md.
>
> Read the full specification for this milestone from:
> specification/step-06-logger.md
>
> Read it completely before beginning implementation. The specification is the single source of truth for this milestone. Do not proceed until you have read it in full.

---

## Technical Decisions

**`persist_funding_records()` extended to return per-article outcomes**
The logger's ARTICLE LOG and FAILURES sections require article-level data — what happened to each article and why. The only way to get this without re-implementing connector logic in the logger was to have `persist_funding_records()` return it. The function now returns `{"stats": stats, "article_log": article_log}` instead of `stats` alone. Each `article_log` entry records: `outcome`, `title`, `url`, `confidence`, `company_name`, and `reason`. The function's core processing logic is unchanged — it still does exactly the same thing, it just also reports what it did at article granularity.

**Logger is passive — it never influences pipeline decisions**
All decisions about what to accept, skip, insert, or flag for review are made by the classifier, extraction engine, and database connector. The logger only observes their output and records it. The `write_log()` function receives all data as arguments; it computes nothing about the pipeline itself.

**`write_log()` wraps its file operations in try/except**
The spec requires that a logging failure never brings down the pipeline. All file I/O in `write_log()` is wrapped in a single `try/except Exception` block. If writing fails for any reason (permissions, disk full, etc.), the exception message is printed to the terminal and the function returns `None` rather than raising.

**Run ID embeds date and time for unique identification**
`IVR-YYYYMMDD-HHMM` format means any two runs at different minutes of the day produce different IDs. For same-minute runs, the file naming collision logic (`-1`, `-2` suffix) ensures no log file is ever overwritten. Both mechanisms working together mean every run is identifiable and every log is preserved.

**Same-day reruns produce `YYYY-MM-DD-N.log` files**
`_get_log_path()` checks whether the base filename exists before claiming it. If `2026-06-30.log` exists, it tries `2026-06-30-1.log`, then `-2`, etc. This is a simple, reliable collision strategy with no configuration needed.

**Git commit hash retrieved via subprocess**
`subprocess.run(["git", "rev-parse", "--short", "HEAD"])` is wrapped in a broad `except Exception` block that returns `"unavailable"` on any failure. This handles environments where git is not installed, the working directory is not a git repo, or the process has no read access to `.git/`. The pipeline is never blocked.

**Pipeline status uses three distinct values**
- `SUCCESS` — pipeline completed, no failures of any kind
- `PARTIAL_SUCCESS` — pipeline completed, but one or more articles had `database_errors` or `validation_failures`
- `FAILED` — a system-level error (DB connection failure, unhandled exception in Stage 3) prevented the pipeline from completing

Duplicates skipped and articles without company names (`validation_failures`) are treated as `PARTIAL_SUCCESS` rather than `SUCCESS` — they represent articles that could not be persisted, even if the reason is expected (IPO listings, etc.). This is intentional: the status reflects the run accurately, not optimistically.

**`__main__` in `scraper/logger.py` is the new pipeline entry point**
`python3 -m scraper.logger` runs the full pipeline and writes a log file. `python3 -m scraper.database` still works (its `__main__` block was updated to unpack the new return value) but does not write a log. For operational use, `scraper.logger` is the correct command.

**Python 3.9 f-string backslash workaround**
`"Today's Review Queue:"` contains an apostrophe that cannot appear in an f-string expression in Python 3.9. Both `scraper/database.py` and `scraper/logger.py` assign this string to a local variable before using it in an f-string. This is the same approach already established in Step 5.

---

## Files Created or Modified

| File | Action |
|---|---|
| `scraper/logger.py` | Created — Logger module with `write_log()`, helper functions, and `__main__` pipeline entry point |
| `scraper/database.py` | Modified — `persist_funding_records()` now returns `{"stats": stats, "article_log": article_log}`; `__main__` block updated to unpack `db_result["stats"]` |

---

## Validation Command

```bash
python3 -m scraper.logger
```

Running this command executes the full pipeline end to end and writes a log file to `logs/`:

1. Fetches and classifies articles from the Entrackr RSS feed
2. Runs the Evidence Extraction Engine
3. Persists structured records to Supabase
4. Prints the operational summary to the terminal
5. Writes `logs/YYYY-MM-DD.log` (or `logs/YYYY-MM-DD-N.log` on same-day reruns)

---

## Verification Performed

- Ran `python3 -m scraper.logger` and confirmed `logs/2026-06-30.log` was created.
- Ran the pipeline a second time and confirmed `logs/2026-06-30-1.log` was created — no overwrite.
- Confirmed log content: Run ID `IVR-20260630-0454`, git commit hash `ee8a34a`, all 8 articles logged (7 duplicates + 1 validation failure), PARTIAL_SUCCESS status, FAILURES section correctly populated for Turtlemint.
- Confirmed `python3 -m scraper.database` still works after the return-value change.

---

## Outcome

Every pipeline execution now produces a permanent record in `logs/`. Running `python3 -m scraper.logger` is the new operational command — it replaces `python3 -m scraper.database` as the top-level entry point. The pipeline is one step away from final wiring in Step 7.

**Commit:** `49ebe30 — Step 6: Implemented Logger`

---

## Next Step

Step 7 — Wire `main.py` — connect all pipeline modules into a complete, schedulable end-to-end entry point.
