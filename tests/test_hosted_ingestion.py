import os
import unittest
from unittest.mock import MagicMock, patch

from scraper.entrackr import FetchResult

from api import run


def _db_result(
    events=1,
    companies=1,
    duplicates=0,
    validation_failures=0,
    companies_reused=0,
    database_errors=0,
    event_sources_attached=0,
    event_conflicts_flagged=0,
    article_log=None,
    website_enrichment_targets=None,
):
    return {
        "stats": {
            "events_inserted": events,
            "companies_created": companies,
            "duplicates_skipped": duplicates,
            "validation_failures": validation_failures,
            "companies_reused": companies_reused,
            "database_errors": database_errors,
            "event_sources_attached": event_sources_attached,
            "event_conflicts_flagged": event_conflicts_flagged,
        },
        "article_log": article_log or [],
        "website_enrichment_targets": website_enrichment_targets or [],
    }


class HostedIngestionTests(unittest.TestCase):
    def setUp(self):
        self.lock = patch("api.run.acquire_pipeline_lock", return_value=True)
        self.release = patch("api.run.release_pipeline_lock", return_value=True)
        self.history_start = patch("api.run.create_ingestion_run", return_value={})
        self.history_complete = patch("api.run.complete_ingestion_run", return_value={})
        self.website_enrichment = patch(
            "api.run.enrich_pending_company_websites",
            return_value={"targets": 0, "enriched": 0, "unresolved": 0, "errors": []},
        )
        self.lock.start()
        self.release.start()
        self.create_history = self.history_start.start()
        self.complete_history = self.history_complete.start()
        self.enrich_websites = self.website_enrichment.start()
        self.addCleanup(self.lock.stop)
        self.addCleanup(self.release.stop)
        self.addCleanup(self.history_start.stop)
        self.addCleanup(self.history_complete.stop)
        self.addCleanup(self.website_enrichment.stop)

    def test_successful_run_records_structured_counts(self):
        source = FetchResult("Entrackr", [{"article_url": "https://example.test/a"}], 3)
        with patch("api.run.fetch_entrackr_result", return_value=source), \
             patch("api.run.extract_funding_records", return_value=[("record", "report")]), \
             patch("api.run.persist_funding_records", return_value=_db_result()):
            status, body = run.run_ingestion()

        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual(body["articles_fetched"], 3)
        self.assertEqual(body["new_articles"], 1)
        self.assertEqual(body["funding_events"], 1)
        self.assertEqual(body["companies_created"], 1)
        self.assertEqual(body["websites_enriched"], 0)
        start_row = self.create_history.call_args.args[0]
        self.assertEqual(start_row["run_id"], body["run_id"])
        self.assertEqual(start_row["status"], "RUNNING")
        self.assertEqual(start_row["trigger"], "hosted")
        completion = self.complete_history.call_args.args
        self.assertEqual(completion[0], body["run_id"])
        self.assertEqual(completion[1]["status"], "SUCCESS")
        self.assertEqual(completion[1]["funding_events_created"], 1)

    def test_new_companies_are_enriched_before_run_finishes(self):
        source = FetchResult("Entrackr", [{"article_url": "https://example.test/a"}], 1)
        target = {
            "id": "company-1",
            "company_name": "Nova",
            "source_article_url": "https://example.test/a",
        }
        website_result = {"targets": 1, "enriched": 1, "unresolved": 0, "errors": []}
        with patch("api.run.fetch_entrackr_result", return_value=source), \
             patch("api.run.extract_funding_records", return_value=[("record", "report")]), \
             patch("api.run.persist_funding_records", return_value=_db_result(website_enrichment_targets=[target])), \
             patch("api.run.enrich_pending_company_websites", return_value=website_result) as enrich:
            status, body = run.run_ingestion()

        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual(body["website_enrichment_targets"], 1)
        self.assertEqual(body["websites_enriched"], 1)
        enrich.assert_called_once_with([target])

    def test_missing_websites_are_retried_when_no_new_articles_exist(self):
        source = FetchResult("Entrackr", [], 0)
        self.enrich_websites.return_value = {
            "targets": 1,
            "enriched": 1,
            "unresolved": 0,
            "errors": [],
        }
        with patch("api.run.fetch_entrackr_result", return_value=source):
            status, body = run.run_ingestion()

        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual(body["websites_enriched"], 1)
        self.enrich_websites.assert_called_once_with(None)

    def test_zero_result_is_a_success_not_a_failure(self):
        source = FetchResult("Entrackr", [], 0)
        with patch("api.run.fetch_entrackr_result", return_value=source), \
             patch("api.run.extract_funding_records") as extract:
            status, body = run.run_ingestion()

        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual(body["errors"], [])
        extract.assert_not_called()

    def test_conflicting_repeat_coverage_is_visible_and_requires_review(self):
        source = FetchResult("Entrackr", [{"article_url": "https://example.test/follow-up"}], 1)
        db_result = _db_result(
            events=0,
            companies=0,
            companies_reused=1,
            event_sources_attached=1,
            event_conflicts_flagged=1,
        )
        with patch("api.run.fetch_entrackr_result", return_value=source), \
             patch("api.run.extract_funding_records", return_value=[("record", "report")]), \
             patch("api.run.persist_funding_records", return_value=db_result):
            status, body = run.run_ingestion()

        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "PARTIAL_SUCCESS")
        self.assertEqual(body["funding_events"], 0)
        self.assertEqual(body["event_sources_attached"], 1)
        self.assertEqual(body["event_conflicts_flagged"], 1)
        self.assertIn("conflicting source evidence", body["errors"][0])

    def test_rss_failure_is_reported_as_failed_run(self):
        source = FetchResult("Entrackr", [], 0, error="Could not fetch RSS feed: timeout")
        with patch("api.run.fetch_entrackr_result", return_value=source):
            status, body = run.run_ingestion()

        self.assertEqual(status, 502)
        self.assertEqual(body["status"], "FAILED")
        self.assertIn("timeout", body["errors"][0])
        completion = self.complete_history.call_args.args[1]
        self.assertEqual(completion["status"], "FAILED")
        self.assertIn("timeout", completion["error_details"][0])

    def test_cron_secret_rejects_missing_or_invalid_credentials(self):
        with patch.dict(os.environ, {"CRON_SECRET": "expected"}, clear=False):
            self.assertFalse(run._is_authorized({}))
            self.assertFalse(run._is_authorized({"Authorization": "Bearer wrong"}))
            self.assertTrue(run._is_authorized({"Authorization": "Bearer expected"}))

    def test_concurrent_invocation_is_skipped_before_source_fetch(self):
        with patch("api.run.acquire_pipeline_lock", return_value=False), \
             patch("api.run.fetch_entrackr_result") as fetch:
            status, body = run.run_ingestion()

        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "SKIPPED_CONCURRENT")
        fetch.assert_not_called()

    def test_completion_persists_outcomes_and_safe_error_details(self):
        source = FetchResult("Entrackr", [{"article_url": "https://example.test/a"}] * 3, 3)
        records = [
            ({"article_url": "https://example.test/a"}, {"funding_status": "confirmed"}),
            ({"article_url": "https://example.test/b"}, {"funding_status": "prospective"}),
            (None, {"errors": ["parser failure"]}),
        ]
        db_result = _db_result(
            events=1,
            companies=1,
            duplicates=1,
            companies_reused=1,
            database_errors=1,
            article_log=[{"outcome": "database_error", "reason": "database timeout"}],
        )
        with patch("api.run.fetch_entrackr_result", return_value=source), \
             patch("api.run.extract_funding_records", return_value=records), \
             patch("api.run.persist_funding_records", return_value=db_result):
            status, body = run.run_ingestion()

        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "PARTIAL_SUCCESS")
        updates = self.complete_history.call_args.args[1]
        self.assertEqual(updates["articles_fetched"], 3)
        self.assertEqual(updates["relevance_passes"], 3)
        self.assertEqual(updates["confirmed"], 1)
        self.assertEqual(updates["prospective"], 1)
        self.assertEqual(updates["unknown"], 0)
        self.assertEqual(updates["extraction_errors"], 1)
        self.assertEqual(updates["duplicates_skipped"], 1)
        self.assertEqual(updates["companies_reused"], 1)
        self.assertEqual(updates["database_errors"], 1)
        self.assertEqual(updates["error_details"], ["database timeout"])

    def test_history_write_failure_does_not_change_ingestion_semantics(self):
        source = FetchResult("Entrackr", [{"article_url": "https://example.test/a"}], 1)
        with patch("api.run.create_ingestion_run", side_effect=RuntimeError("telemetry unavailable")), \
             patch("api.run.complete_ingestion_run", side_effect=RuntimeError("telemetry unavailable")), \
             patch("api.run.fetch_entrackr_result", return_value=source), \
             patch("api.run.extract_funding_records", return_value=[({"article_url": "a"}, {"funding_status": "confirmed"})]), \
             patch("api.run.persist_funding_records", return_value=_db_result()) as persist:
            status, body = run.run_ingestion()

        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "SUCCESS")
        persist.assert_called_once()

    def test_persisted_error_details_redact_configured_secrets(self):
        secret = "do-not-persist-this"
        source = FetchResult("Entrackr", [], 0, error="source failed: " + secret)
        with patch.dict(os.environ, {"CRON_SECRET": secret}, clear=False), \
             patch("api.run.fetch_entrackr_result", return_value=source):
            run.run_ingestion()

        updates = self.complete_history.call_args.args[1]
        self.assertEqual(updates["error_details"], ["source failed: [redacted]"])
