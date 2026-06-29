# Logger — records every pipeline execution to a structured log file in logs/.
#
# Responsibilities:
#   - Generate a unique run ID per execution
#   - Write a structured log file capturing run metadata, configuration,
#     version, statistics, per-article outcomes, and failures
#   - Determine pipeline status: SUCCESS, PARTIAL_SUCCESS, or FAILED
#   - Never cause the pipeline to fail — logging errors are reported to terminal
#
# The Logger is passive: it observes and records, it does not influence decisions.

import os
import subprocess
import datetime

# Component version labels embedded in every log file.
PARSER_VERSION = "1.0"
DATABASE_CONNECTOR_VERSION = "1.0"


def _generate_run_id(start_time):
    """Return a unique run ID formatted as IVR-YYYYMMDD-HHMM."""
    return f"IVR-{start_time.strftime('%Y%m%d-%H%M')}"


def _get_git_commit_hash():
    """Return the short git commit hash, or 'unavailable' if git is inaccessible."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unavailable"


def _get_log_path(date):
    """
    Return the path for today's log file.
    If logs/YYYY-MM-DD.log already exists, append -1, -2, etc. until a free
    name is found. Creates the logs/ directory if it does not exist.
    """
    os.makedirs("logs", exist_ok=True)
    base = os.path.join("logs", date.strftime("%Y-%m-%d") + ".log")
    if not os.path.exists(base):
        return base
    n = 1
    while True:
        path = os.path.join("logs", f"{date.strftime('%Y-%m-%d')}-{n}.log")
        if not os.path.exists(path):
            return path
        n += 1


def _format_duration(seconds):
    """Format a duration in seconds as a human-readable string."""
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    if minutes > 0:
        m_unit = "minute" if minutes == 1 else "minutes"
        s_unit = "second" if secs == 1 else "seconds"
        return f"{minutes} {m_unit} {secs} {s_unit}"
    s_unit = "second" if total == 1 else "seconds"
    return f"{total} {s_unit}"


def _determine_status(stats, pipeline_aborted):
    """
    Return the pipeline status string.

    FAILED         — a system-level error prevented the pipeline from completing.
    PARTIAL_SUCCESS — the pipeline completed but one or more articles failed.
    SUCCESS        — the pipeline completed with no failures.
    """
    if pipeline_aborted:
        return "FAILED"
    if stats.get("database_errors", 0) > 0 or stats.get("validation_failures", 0) > 0:
        return "PARTIAL_SUCCESS"
    return "SUCCESS"


def _suggested_action(outcome):
    """Return the canonical suggested action for a failure outcome code."""
    return {
        "duplicate":          "Already processed — no action required",
        "validation_failure": "Manual review required",
        "database_error":     "Retry tomorrow",
    }.get(outcome, "Investigate")


def write_log(
    run_id,
    start_time,
    end_time,
    status,
    config_snapshot,
    stats,
    article_log,
    rss_accepted,
    records_produced,
):
    """
    Write a structured log file for one pipeline execution to logs/.

    Never raises — if writing fails, the error is printed to the terminal so
    the pipeline is not affected.

    Args:
        run_id           (str): Unique run identifier (IVR-YYYYMMDD-HHMM).
        start_time       (datetime): When the pipeline began.
        end_time         (datetime): When the pipeline completed.
        status           (str): SUCCESS, PARTIAL_SUCCESS, or FAILED.
        config_snapshot  (dict): rss_source, lookback_hours, classifier_threshold.
        stats            (dict): Operational stats from persist_funding_records().
        article_log      (list): Per-article outcome dicts from persist_funding_records().
        rss_accepted     (int): Count of articles accepted by the classifier.
        records_produced (int): Count of structured records sent to the connector.

    Returns:
        str: Path to the written log file, or None if writing failed.
    """
    duration_secs = (end_time - start_time).total_seconds()
    git_hash = _get_git_commit_hash()
    log_path = _get_log_path(start_time.date())

    lines = []

    # --- Header ---
    lines += [
        "=" * 60,
        "INDIA VENTURE REVIEW — INGESTION PIPELINE LOG",
        "=" * 60,
        "",
        f"Run ID:               {run_id}",
        f"Start Time:           {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"End Time:             {end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Total Execution Time: {_format_duration(duration_secs)}",
        f"Pipeline Status:      {status}",
        "",
    ]

    # --- Configuration ---
    lines += [
        "-" * 60,
        "CONFIGURATION",
        "-" * 60,
        f"RSS Source:           {config_snapshot['rss_source']}",
        f"Lookback Window:      {config_snapshot['lookback_hours']} hours",
        f"Classifier Threshold: {config_snapshot['classifier_threshold']}",
        "",
    ]

    # --- Version ---
    lines += [
        "-" * 60,
        "VERSION",
        "-" * 60,
        f"Git Commit Hash:      {git_hash}",
        f"Parser Version:       {PARSER_VERSION}",
        f"Database Connector:   {DATABASE_CONNECTOR_VERSION}",
        "",
    ]

    # --- Pipeline statistics ---
    lines += [
        "-" * 60,
        "PIPELINE STATISTICS",
        "-" * 60,
        f"{'RSS Articles Processed:':<35} {rss_accepted}",
        f"{'Funding Articles Accepted:':<35} {rss_accepted}",
        f"{'Structured Records Produced:':<35} {records_produced}",
        f"{'Companies Created:':<35} {stats['companies_created']}",
        f"{'Companies Reused:':<35} {stats['companies_reused']}",
        f"{'Funding Events Inserted:':<35} {stats['events_inserted']}",
        f"{'Duplicates Skipped:':<35} {stats['duplicates_skipped']}",
        f"{'Persistence Validation Failures:':<35} {stats['validation_failures']}",
        f"{'Database Errors:':<35} {stats['database_errors']}",
    ]
    review_queue_label = "Today's Review Queue:"
    lines.append(f"{review_queue_label:<35} {stats['review_queue']}")
    lines.append("")

    # --- Article log ---
    lines += [
        "-" * 60,
        "ARTICLE LOG",
        "-" * 60,
    ]

    failures = []

    for entry in article_log:
        outcome    = entry["outcome"]
        title      = entry.get("title") or entry.get("url") or "unknown"
        confidence = entry.get("confidence") or ""
        reason     = entry.get("reason") or ""

        if outcome == "inserted":
            label = f"[INSERTED — {confidence}]"
            lines.append(f"{label:<24} {title}")
        elif outcome == "duplicate":
            lines.append(f"[DUPLICATE — Skipped]    {title}")
        elif outcome == "validation_failure":
            url_label = entry.get("url") or title
            lines.append(f"[SKIP — Validation]      {url_label}")
            if reason:
                lines.append(f"                         Reason: {reason}")
            failures.append(entry)
        elif outcome == "database_error":
            lines.append(f"[ERROR]                  {title}")
            if reason:
                lines.append(f"                         Reason: {reason}")
            failures.append(entry)

    lines.append("")

    # --- Failures ---
    lines += [
        "-" * 60,
        "FAILURES",
        "-" * 60,
    ]

    if failures:
        for failure in failures:
            lines += [
                "FAILED ARTICLE",
                "-" * 40,
                f"Company:          {failure.get('company_name') or 'Unknown'}",
                f"Article:          {failure.get('url') or 'unknown'}",
                f"Reason:           {failure.get('reason') or 'Unknown'}",
                f"Suggested Action: {_suggested_action(failure['outcome'])}",
                "",
            ]
    else:
        lines.append("None")
        lines.append("")

    # --- Footer ---
    lines += [
        "=" * 60,
        "END OF LOG",
        "=" * 60,
    ]

    content = "\n".join(lines) + "\n"

    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\nLog written to: {log_path}")
        return log_path
    except Exception as e:
        print(f"\n[WARNING] Failed to write log file: {e}")
        return None


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------
# Run the full ingestion pipeline end to end and produce a log file:
#   python3 -m scraper.logger

if __name__ == "__main__":
    from scraper.entrackr import (
        fetch_entrackr_articles,
        SOURCE_NAME,
        LOOKBACK_HOURS,
        ACCEPTANCE_THRESHOLD,
    )
    from scraper.parser import extract_funding_records
    from scraper.database import persist_funding_records

    _config_snapshot = {
        "rss_source":           SOURCE_NAME,
        "lookback_hours":       LOOKBACK_HOURS,
        "classifier_threshold": ACCEPTANCE_THRESHOLD,
    }

    _empty_stats = {
        "companies_created":   0,
        "companies_reused":    0,
        "events_inserted":     0,
        "duplicates_skipped":  0,
        "validation_failures": 0,
        "database_errors":     0,
        "review_queue":        0,
    }

    start_time = datetime.datetime.now()
    run_id = _generate_run_id(start_time)

    print("India Venture Review — Full Ingestion Pipeline")
    print("=" * 60)
    print()

    # --- Stage 1: RSS ingestion and classification ---
    print("Stage 1  Fetching articles from Entrackr RSS...")
    articles = fetch_entrackr_articles(verbose=False)
    rss_accepted = len(articles)

    if not articles:
        print("         No funding articles found in the last 24 hours.")
        end_time = datetime.datetime.now()
        write_log(
            run_id=run_id,
            start_time=start_time,
            end_time=end_time,
            status="SUCCESS",
            config_snapshot=_config_snapshot,
            stats=_empty_stats,
            article_log=[],
            rss_accepted=0,
            records_produced=0,
        )
        raise SystemExit(0)

    print(f"         {rss_accepted} funding article(s) accepted by classifier")
    print()

    # --- Stage 2: Evidence extraction ---
    print("Stage 2  Running Evidence Extraction Engine...")
    results = extract_funding_records(articles)
    print(f"         {len(results)} structured record(s) produced")
    print()

    # --- Stage 3: Database persistence ---
    print("Stage 3  Persisting to Supabase...")
    print()
    try:
        db_result = persist_funding_records(results)
        stats = db_result["stats"]
        article_log = db_result["article_log"]
    except Exception as e:
        print(f"  [FATAL] Database connector failed: {e}")
        end_time = datetime.datetime.now()
        write_log(
            run_id=run_id,
            start_time=start_time,
            end_time=end_time,
            status="FAILED",
            config_snapshot=_config_snapshot,
            stats=_empty_stats,
            article_log=[],
            rss_accepted=rss_accepted,
            records_produced=len(results),
        )
        raise SystemExit(1)

    end_time = datetime.datetime.now()
    print()

    # --- Operational summary ---
    print("─" * 60)
    print("Operational Summary")
    print("─" * 60)
    print(f"  {'RSS Articles Processed':<35} {rss_accepted}")
    print(f"  {'Funding Articles Accepted':<35} {rss_accepted}")
    print(f"  {'Structured Records Produced':<35} {len(results)}")
    print(f"  {'Companies Created':<35} {stats['companies_created']}")
    print(f"  {'Companies Reused':<35} {stats['companies_reused']}")
    print(f"  {'Funding Events Inserted':<35} {stats['events_inserted']}")
    print(f"  {'Duplicates Skipped':<35} {stats['duplicates_skipped']}")
    print(f"  {'Persistence Validation Failures':<35} {stats['validation_failures']}")
    print(f"  {'Database Errors':<35} {stats['database_errors']}")
    review_label = "Today's Review Queue"
    print(f"  {review_label:<35} {stats['review_queue']}")
    print("─" * 60)

    # --- Write log file ---
    status = _determine_status(stats, pipeline_aborted=False)

    write_log(
        run_id=run_id,
        start_time=start_time,
        end_time=end_time,
        status=status,
        config_snapshot=_config_snapshot,
        stats=stats,
        article_log=article_log,
        rss_accepted=rss_accepted,
        records_produced=len(results),
    )
