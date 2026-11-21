"""Authenticated Vercel entry point for the India Venture Review ingestion run."""

import datetime
import hmac
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler

from scraper.database import (
    acquire_pipeline_lock,
    complete_ingestion_run,
    create_ingestion_run,
    persist_funding_records,
    release_pipeline_lock,
)
from scraper.entrackr import fetch_entrackr_result
from scraper.parser import extract_funding_records
from scraper.company_website_enrichment import enrich_pending_company_websites
from scraper.public_refresh import refresh_public_data
from scraper.run_metrics import start_run, finish_run, stage


LOCK_LEASE_SECONDS = 330
HOSTED_TRIGGER = "hosted"


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(value):
    return value.isoformat().replace("+00:00", "Z")


def _emit(event, **fields):
    """Write JSON to stdout so Vercel retains one queryable log event per stage."""
    message = json.dumps({"event": event, "timestamp": _iso(_utc_now()), **fields}, sort_keys=True)
    for name in ("CRON_SECRET", "SUPABASE_KEY", "OPENAI_API_KEY", "IVR_REVALIDATE_SECRET"):
        secret = os.environ.get(name)
        if secret:
            message = message.replace(secret, "[redacted]")
    print(message)


def _summary(run_id, start_time):
    return {
        "run_id": run_id,
        "start_time": _iso(start_time),
        "end_time": None,
        "status": "RUNNING",
        "trigger": HOSTED_TRIGGER,
        "source_name": "Entrackr",
        "sources_attempted": 1,
        "articles_fetched": 0,
        "new_articles": 0,
        "relevance_passes": 0,
        "confirmed": 0,
        "prospective": 0,
        "unknown": 0,
        "funding_events": 0,
        "event_sources_attached": 0,
        "event_conflicts_flagged": 0,
        "companies_created": 0,
        "companies_reused": 0,
        "duplicates_skipped": 0,
        "extraction_errors": 0,
        "database_errors": 0,
        # The current ingestion contract never updates curated company rows.
        "companies_updated": 0,
        "website_enrichment_targets": 0,
        "websites_enriched": 0,
        "website_enrichment_unresolved": 0,
        "errors": [],
    }


def _safe_error_detail(error):
    """Keep persisted telemetry concise and ensure configured secrets are absent."""
    detail = str(error)
    for name in ("CRON_SECRET", "SUPABASE_KEY", "OPENAI_API_KEY", "IVR_REVALIDATE_SECRET"):
        secret = os.environ.get(name)
        if secret:
            detail = detail.replace(secret, "[redacted]")
    return detail[:500]


def _history_start(summary):
    try:
        row = create_ingestion_run({
            "run_id": summary["run_id"],
            "started_at": summary["start_time"],
            "status": "RUNNING",
            "trigger": summary["trigger"],
            "source_name": summary["source_name"],
            "sources_attempted": summary["sources_attempted"],
        })
        return bool(row)
    except Exception as error:
        _emit(
            "ingestion.history_start_failed",
            run_id=summary["run_id"],
            error=_safe_error_detail(error),
        )
        return False


def _history_complete(summary):
    try:
        complete_ingestion_run(summary["run_id"], {
            "completed_at": summary["end_time"],
            "status": summary["status"],
            "articles_fetched": summary["articles_fetched"],
            "new_articles": summary["new_articles"],
            "relevance_passes": summary["relevance_passes"],
            "confirmed": summary["confirmed"],
            "prospective": summary["prospective"],
            "unknown": summary["unknown"],
            "funding_events_created": summary["funding_events"],
            "event_sources_attached": summary["event_sources_attached"],
            "event_conflicts_flagged": summary["event_conflicts_flagged"],
            "companies_created": summary["companies_created"],
            "companies_reused": summary["companies_reused"],
            "duplicates_skipped": summary["duplicates_skipped"],
            "extraction_errors": summary["extraction_errors"],
            "database_errors": summary["database_errors"],
            "error_details": [_safe_error_detail(error) for error in summary["errors"]],
            "duration_ms": summary.get("duration_ms"),
            "cpu_ms": summary.get("cpu_ms"),
            "stages": summary.get("stages", {}),
            "cache_refresh_status": summary.get("cache_refresh_status"),
        })
    except Exception as error:
        _emit(
            "ingestion.history_completion_failed",
            run_id=summary["run_id"],
            error=_safe_error_detail(error),
        )


def _finish(summary, status, **extra):
    summary.update(extra)
    summary["status"] = status
    changed = any(summary.get(field, 0) for field in ('funding_events', 'event_sources_attached', 'websites_enriched'))
    summary['cache_refresh_status'] = refresh_public_data(scopes=['overview', 'directory', 'archive', 'investors', 'companies']) if changed else 'no_changes'
    finish_run(summary)
    summary["end_time"] = _iso(_utc_now())
    _history_complete(summary)
    _emit("ingestion.completed", **summary)
    return summary


def _is_authorized(headers):
    """Validate the Bearer token Vercel sends for a CRON_SECRET-protected job."""
    secret = os.environ.get("CRON_SECRET")
    authorization = headers.get("Authorization", "")
    expected = f"Bearer {secret}" if secret else ""
    return bool(secret) and hmac.compare_digest(authorization, expected)


def _database_errors(article_log):
    return [
        entry.get("reason", "Database operation failed")
        for entry in article_log
        if entry.get("outcome") == "database_error"
    ]


def _enrich_websites(summary, new_companies=None):
    """Run website enrichment and expose retry outcomes in hosted-run telemetry."""
    result = enrich_pending_company_websites(new_companies)
    summary.update({
        "website_enrichment_targets": result["targets"],
        "websites_enriched": result["enriched"],
        "website_enrichment_unresolved": result["unresolved"],
    })
    if result["errors"]:
        summary["errors"].append(
            "Website enrichment failed for "
            f"{len(result['errors'])} company record(s)"
        )
    return result


def _record_outcomes(records):
    """Return parser status counts without changing parser or persistence behavior."""
    counts = {"confirmed": 0, "prospective": 0, "unknown": 0, "extraction_errors": 0}
    for record, report in records:
        if record is None:
            counts["extraction_errors"] += 1
            continue
        status = report.get("funding_status", "unknown") if isinstance(report, dict) else "unknown"
        if status in ("confirmed", "prospective", "unknown"):
            counts[status] += 1
        else:
            counts["unknown"] += 1
    return counts


def run_ingestion(*, trigger=HOSTED_TRIGGER, should_run=None, lookback_hours=None, require_history=False,
                  enrich_websites=True):
    """Run one complete hosted ingestion pass and return an HTTP-ready summary."""
    start_time = _utc_now()
    run_id = f"IVR-{start_time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    summary = _summary(run_id, start_time)
    summary["trigger"] = trigger
    start_run(summary)
    lock_acquired = False
    _emit("ingestion.started", run_id=run_id, start_time=summary["start_time"])
    history_created = _history_start(summary)
    if require_history and not history_created:
        summary['errors'].append('Durable run history is required for backup ingestion')
        return 503, _finish(summary, 'FAILED')

    try:
        try:
            lock_acquired = acquire_pipeline_lock(run_id, LOCK_LEASE_SECONDS)
        except Exception as error:
            summary["errors"].append(f"Could not acquire ingestion lock: {error}")
            return 503, _finish(summary, "FAILED")

        if not lock_acquired:
            return 200, _finish(summary, "SKIPPED_CONCURRENT")

        # Recheck freshness under the shared lock: the primary may have finished
        # while an independent backup was waiting to acquire it.
        if should_run is not None and not should_run():
            return 200, _finish(summary, "SKIPPED_FRESH")

        with stage(summary, 'fetch'):
            source_result = (fetch_entrackr_result(verbose=False)
                             if lookback_hours is None else
                             fetch_entrackr_result(verbose=False, lookback_hours=lookback_hours))
        summary["articles_fetched"] = source_result.entries_fetched
        if source_result.error:
            summary["errors"].append(source_result.error)
            return 502, _finish(summary, "FAILED")

        accepted_articles = source_result.articles
        summary["relevance_passes"] = len(accepted_articles)
        if not accepted_articles:
            if enrich_websites:
                with stage(summary, 'website_enrichment'):
                    _enrich_websites(summary)
            status = "PARTIAL_SUCCESS" if summary["errors"] else "SUCCESS"
            return 200, _finish(summary, status)

        with stage(summary, 'extract'):
            records = extract_funding_records(accepted_articles)
        summary.update(_record_outcomes(records))
        with stage(summary, 'persist'):
            db_result = persist_funding_records(records)
        stats = db_result["stats"]
        summary.update({
            "new_articles": max(0, len(accepted_articles) - stats["duplicates_skipped"]),
            "funding_events": stats["events_inserted"],
            "event_sources_attached": stats.get("event_sources_attached", 0),
            "event_conflicts_flagged": stats.get("event_conflicts_flagged", 0),
            "companies_created": stats["companies_created"],
            "companies_reused": stats.get("companies_reused", 0),
            "duplicates_skipped": stats["duplicates_skipped"],
            "database_errors": stats.get("database_errors", 0),
        })
        summary["errors"].extend(_database_errors(db_result["article_log"]))
        if enrich_websites:
            with stage(summary, 'website_enrichment'):
                _enrich_websites(summary, db_result.get("website_enrichment_targets", []))
        if stats["validation_failures"]:
            summary["errors"].append(
                f"{stats['validation_failures']} record(s) failed persistence validation"
            )
        if stats.get("event_conflicts_flagged", 0):
            summary["errors"].append(
                f"{stats['event_conflicts_flagged']} funding event(s) have conflicting source evidence"
            )

        status = "PARTIAL_SUCCESS" if summary["errors"] or summary["extraction_errors"] else "SUCCESS"
        return 200, _finish(summary, status)
    except Exception as error:
        summary["errors"].append(f"Unhandled pipeline error: {error}")
        return 500, _finish(summary, "FAILED")
    finally:
        if lock_acquired:
            try:
                release_pipeline_lock(run_id)
            except Exception as error:
                # The lease expires automatically; surface the operational issue.
                _emit("ingestion.lock_release_failed", run_id=run_id, error=str(error))


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self._handle_request()

    def do_POST(self):
        self._handle_request()

    def _handle_request(self):
        if not _is_authorized(self.headers):
            _emit("ingestion.unauthorized")
            self._json(401, {"status": "error", "message": "Unauthorized"})
            return

        status, body = run_ingestion()
        self._json(status, body)

    def _json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode("utf-8"))
