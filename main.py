# Entry point for the scraper — orchestrates fetching, parsing, and storing funding data.

import datetime
from dotenv import load_dotenv

load_dotenv()

from scraper.entrackr import (
    fetch_entrackr_articles,
    SOURCE_NAME,
    LOOKBACK_HOURS,
    ACCEPTANCE_THRESHOLD,
)
from scraper.parser import extract_funding_records
from scraper.database import persist_funding_records
from scraper.logger import write_log


def _run_pipeline():
    start_time = datetime.datetime.now()
    run_id = f"IVR-{start_time.strftime('%Y%m%d-%H%M')}"

    print("India Venture Review — Ingestion Pipeline")
    print(f"Starting run: {run_id}")
    print()

    config_snapshot = {
        "rss_source":           SOURCE_NAME,
        "lookback_hours":       LOOKBACK_HOURS,
        "classifier_threshold": ACCEPTANCE_THRESHOLD,
    }
    empty_stats = {
        "companies_created":   0,
        "companies_reused":    0,
        "events_inserted":     0,
        "duplicates_skipped":  0,
        "validation_failures": 0,
        "database_errors":     0,
        "review_queue":        0,
    }

    # Stage 1: RSS ingestion and classification
    articles = fetch_entrackr_articles(verbose=False)
    rss_accepted = len(articles)

    if not articles:
        end_time = datetime.datetime.now()
        log_path = write_log(
            run_id=run_id,
            start_time=start_time,
            end_time=end_time,
            status="SUCCESS",
            config_snapshot=config_snapshot,
            stats=empty_stats,
            article_log=[],
            rss_accepted=0,
            records_produced=0,
        )
        _print_completion("SUCCESS", log_path)
        return

    # Stage 2: Evidence extraction
    results = extract_funding_records(articles)

    # Stage 3: Database persistence
    try:
        db_result = persist_funding_records(results)
        stats = db_result["stats"]
        article_log = db_result["article_log"]
    except Exception as e:
        print(f"\nPipeline failed: {e}")
        end_time = datetime.datetime.now()
        log_path = write_log(
            run_id=run_id,
            start_time=start_time,
            end_time=end_time,
            status="FAILED",
            config_snapshot=config_snapshot,
            stats=empty_stats,
            article_log=[],
            rss_accepted=rss_accepted,
            records_produced=len(results),
        )
        _print_completion("FAILED", log_path)
        return

    end_time = datetime.datetime.now()

    if stats.get("database_errors", 0) > 0 or stats.get("validation_failures", 0) > 0:
        status = "PARTIAL_SUCCESS"
    else:
        status = "SUCCESS"

    # Stage 4: Write log file
    log_path = write_log(
        run_id=run_id,
        start_time=start_time,
        end_time=end_time,
        status=status,
        config_snapshot=config_snapshot,
        stats=stats,
        article_log=article_log,
        rss_accepted=rss_accepted,
        records_produced=len(results),
    )

    _print_completion(status, log_path)


def _print_completion(status, log_path):
    print()
    print("Pipeline complete.")
    print(f"Status: {status}")
    if log_path:
        print(f"Log: {log_path}")


if __name__ == "__main__":
    _run_pipeline()
