# Step 7: Main Application and Scheduler

Implemented the final step of the MVP — wiring all pipeline modules into a single entry point and configuring macOS launchd to run the pipeline automatically every morning.

---

## Objective

Replace the stub `main.py` with a complete pipeline orchestrator that calls each module in sequence and hands the result to the logger. Configure a macOS LaunchAgent to run `python main.py` automatically at 7:00 AM IST every day.

After Step 7, the entire ingestion pipeline runs with one command:

```bash
python main.py
```

---

## Implementation Prompt

> This is Step 7 of 7 in a structured build process. Do exactly what is requested in this step and nothing more. Follow all conventions documented in CONTRIBUTING.md.
>
> Read the full specification for this milestone from:
> specification/step-07-main-and-scheduler.md
>
> Read it completely before beginning implementation. The specification is the single source of truth for this milestone. Do not proceed until you have read it in full.

---

## Technical Decisions

**`main.py` contains no business logic**
All classification, extraction, persistence, and logging decisions are made by the modules `main.py` calls. `main.py` is responsible only for calling them in the correct order, passing outputs between them, and reporting the outcome. Adding any logic (filtering, retrying, reordering) to `main.py` would violate the single-responsibility principle established across all previous steps.

**`load_dotenv()` called at the top of `main.py`**
Environment variables must be loaded before any module-level imports that read from `os.environ`. Calling `load_dotenv()` before the `scraper.*` imports ensures `.env` is in scope when `config.py` reads `SUPABASE_URL` and `SUPABASE_KEY`. This is the correct load order.

**Run ID generated in `main.py` from `start_time`**
The run ID (`IVR-YYYYMMDD-HHMM`) is a single string format known at startup. Generating it inline in `main.py` avoids importing a private helper from the logger and keeps the startup banner self-contained. The same `run_id` and `start_time` are passed to `write_log()` so the log file records exactly the same values printed to the terminal.

**Catastrophic failure handled at Stage 3 only**
The spec's FAILED status covers "pipeline itself could not complete" scenarios — primarily a database connection failure that prevents any records from being processed. Stages 1 and 2 (`fetch_entrackr_articles`, `extract_funding_records`) do not raise under normal error conditions: the fetcher returns `[]` on RSS failure, and the extraction engine handles per-article errors internally. Only the database connector can raise a connection-level exception that requires a FAILED log.

**`_print_completion()` extracted to avoid duplication**
The completion banner is printed in three places: no articles found, database failure, and successful completion. A small private helper avoids repeating three print statements three times.

**launchd chosen over cron**
The spec explicitly requires launchd. Unlike cron, launchd handles sleep states gracefully — if the Mac is asleep at 7:00 AM IST, the job runs as soon as the Mac wakes rather than being silently skipped. This is essential for a morning pipeline on a laptop.

**`RunAtLoad: false` prevents an immediate run on load**
Loading the LaunchAgent with `launchctl load` should not trigger an immediate pipeline run — the day's articles have already been processed manually. `RunAtLoad: false` is set explicitly in the plist to make this intent clear.

**plist uses local time (IST) for the schedule**
launchd `StartCalendarInterval` uses local system time, not UTC. The Mac's timezone is IST (UTC+5:30), verified with `date +%Z`. 7:00 AM IST = `Hour=7, Minute=0` in the plist. No UTC conversion is needed.

**plist stored outside the repository**
`~/Library/LaunchAgents/` is the correct location for user-level LaunchAgents on macOS. It is not inside the project directory and not committed to git — the plist contains machine-specific absolute paths that would be wrong on any other machine.

**stdout and stderr redirected to `logs/`**
During automated runs, no terminal is open to capture output. `StandardOutPath` and `StandardErrorPath` redirect all pipeline output to `logs/launchd-stdout.log` and `logs/launchd-stderr.log`. These files capture both the per-article output from `persist_funding_records()` and any unexpected Python tracebacks.

---

## Files Created or Modified

| File | Action |
|---|---|
| `main.py` | Implemented — complete pipeline orchestrator |
| `~/Library/LaunchAgents/com.indiaventurereview.pipeline.plist` | Created — macOS LaunchAgent (not committed to git) |

---

## LaunchAgent Commands

```bash
# Load the LaunchAgent (run once — persists across reboots)
launchctl load ~/Library/LaunchAgents/com.indiaventurereview.pipeline.plist

# Verify it is loaded and waiting (dash = not running, 0 = healthy exit)
launchctl list | grep indiaventurereview

# Test manually without waiting for the scheduled time
launchctl start com.indiaventurereview.pipeline

# Unload if needed (stops scheduling without deleting the plist)
launchctl unload ~/Library/LaunchAgents/com.indiaventurereview.pipeline.plist
```

---

## Verifying the Schedule

The Mac's timezone is IST. launchd uses local time, so `Hour=7, Minute=0` in the plist schedules the job at 7:00 AM IST exactly.

To verify:

```bash
# Confirm Mac timezone is IST
date +%Z
# Expected output: IST

# Confirm LaunchAgent is loaded and not currently running
launchctl list | grep indiaventurereview
# Expected output: -    0    com.indiaventurereview.pipeline
# (dash = no active PID, 0 = last exit was clean)
```

If the Mac's timezone ever changes, update the `Hour` and `Minute` values in the plist to reflect the correct local time for 7:00 AM IST, then reload.

---

## Validation Command

```bash
python main.py
```

Expected terminal output:

```
India Venture Review — Ingestion Pipeline
Starting run: IVR-20260630-0525

  [SKIP — Duplicate] ...
  [SKIP — Validation] ...

Log written to: logs/2026-06-30.log

Pipeline complete.
Status: PARTIAL_SUCCESS
Log: logs/2026-06-30.log
```

---

## Verification Performed

- Ran `python main.py` and confirmed startup banner, per-article output, log file written, and completion banner with correct status.
- Confirmed `launchctl list | grep indiaventurereview` shows the agent loaded with no active PID and exit status 0.
- Confirmed the LaunchAgent did not trigger a run on load (`RunAtLoad: false`).

---

## Outcome

The India Venture Review MVP ingestion pipeline is complete. Every morning at 7:00 AM IST, macOS launchd runs `python main.py`, which fetches funding articles from Entrackr, extracts structured records, persists them to Supabase, and writes a dated log file — all without any manual intervention.

**Commit:** `70d5d91 — Step 7: Implemented main.py and launchd scheduler`

---

## MVP Complete

All 7 steps are implemented:

| Step | Module | Responsibility |
|---|---|---|
| 1–2 | Project setup + schema | Foundation |
| 3 | `scraper/entrackr.py` | RSS ingestion and classification |
| 4 | `scraper/parser.py` | Evidence extraction |
| 5 | `scraper/database.py` | Supabase persistence |
| 6 | `scraper/logger.py` | Structured log files |
| 7 | `main.py` + launchd | Orchestration and scheduling |
