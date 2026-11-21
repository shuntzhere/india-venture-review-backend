import datetime as dt
import unittest
import subprocess
from unittest.mock import MagicMock, patch

from scripts import fallback_ingestion as backup
from api import run


class FallbackTests(unittest.TestCase):
    def test_cutoff_before_and_after_primary(self):
        for hour, day in [(5, 20), (6, 21), (14, 21)]:
            now = dt.datetime(2026, 11, 21, hour, tzinfo=dt.timezone.utc)
            self.assertEqual(backup.daily_cutoff(now), now.replace(day=day, hour=6))

    def test_success_with_no_new_articles_still_counts(self):
        client = MagicMock()
        client.table.return_value.select.return_value.eq.return_value.gte.return_value.lte.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {'completed_at': '2026-11-21T06:01:00Z'}]
        self.assertFalse(backup.needs_run(client, dt.datetime.now(dt.timezone.utc)))

    def test_missing_history_fails_closed(self):
        with patch.object(backup, '_get_client', side_effect=RuntimeError('unavailable')), patch.object(backup, 'run_ingestion') as ingest:
            self.assertEqual(backup.main([]), 1)
            ingest.assert_not_called()

    def test_fresh_primary_skips_backup(self):
        with patch.object(backup, '_get_client'), patch.object(backup, 'needs_run', return_value=False), patch.object(backup, 'run_ingestion') as ingest:
            self.assertEqual(backup.main([]), 0)
            ingest.assert_not_called()

    def test_check_only_does_not_write(self):
        with patch.object(backup, '_get_client'), patch.object(backup, 'needs_run', return_value=True), patch.object(backup, 'run_ingestion') as ingest:
            self.assertEqual(backup.main(['--check-only']), 0)
            ingest.assert_not_called()

    def test_partial_failure_is_not_reported_as_success(self):
        with patch.object(backup, '_get_client'), patch.object(backup, 'needs_run', return_value=True), patch.object(backup, 'run_ingestion', return_value=(200, {'status': 'PARTIAL_SUCCESS'})):
            self.assertEqual(backup.main([]), 1)

    def test_missing_completion_fails(self):
        client = MagicMock()
        client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        with patch.object(backup, '_get_client', return_value=client), patch.object(backup, 'needs_run', return_value=True), patch.object(backup, 'run_ingestion', return_value=(200, {'status': 'SUCCESS', 'run_id': 'test'})):
            self.assertEqual(backup.main([]), 1)

    def test_freshness_is_rechecked_under_lock(self):
        with patch.object(run, 'acquire_pipeline_lock', return_value=True), patch.object(run, 'release_pipeline_lock') as release, patch.object(run, '_history_start'), patch.object(run, '_history_complete'), patch.object(run, 'fetch_entrackr_result') as fetch:
            status, summary = run.run_ingestion(trigger='github_fallback', should_run=lambda: False)
            self.assertEqual((status, summary['status']), (200, 'SKIPPED_FRESH'))
            self.assertEqual(summary['trigger'], 'github_fallback')
            fetch.assert_not_called()
            release.assert_called_once()

    def test_history_write_failure_prevents_scraping(self):
        with patch.object(run, '_history_start', return_value=False), patch.object(run, '_history_complete'), patch.object(run, 'fetch_entrackr_result') as fetch, patch.object(run, 'acquire_pipeline_lock') as lock:
            status, summary = run.run_ingestion(require_history=True)
            self.assertEqual((status, summary['status']), (503, 'FAILED'))
            fetch.assert_not_called()
            lock.assert_not_called()

    def test_timeout_kills_child_process_group(self):
        child = MagicMock(pid=123)
        child.wait.side_effect = [subprocess.TimeoutExpired('backup', 240), 0]
        with patch.object(backup.subprocess, 'Popen', return_value=child) as spawn, patch.object(backup.os, 'killpg') as kill:
            self.assertEqual(backup.execute(), 124)
            self.assertTrue(spawn.call_args.kwargs['start_new_session'])
            kill.assert_called_once_with(123, backup.signal.SIGKILL)

    def test_successful_backup_verifies_completion_and_defers_enrichment(self):
        client = MagicMock()
        client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{'status': 'SUCCESS', 'completed_at': '2026-11-22T08:00:00Z'}]
        with patch.object(backup, '_get_client', return_value=client), patch.object(backup, 'needs_run', return_value=True), patch.object(backup, 'run_ingestion', return_value=(200, {'status': 'SUCCESS', 'run_id': 'test'})) as ingest:
            self.assertEqual(backup.main([]), 0)
            self.assertFalse(ingest.call_args.kwargs['enrich_websites'])
            self.assertTrue(ingest.call_args.kwargs['require_history'])

    def test_database_history_failure_does_not_scrape(self):
        with patch.object(backup, '_get_client'), patch.object(backup, 'needs_run', side_effect=RuntimeError('unavailable')), patch.object(backup, 'run_ingestion') as ingest:
            self.assertEqual(backup.main([]), 1)
            ingest.assert_not_called()

    def test_empty_ingestion_does_not_call_optional_ai(self):
        from scraper.entrackr import FetchResult
        with patch.object(run, '_history_start', return_value=True), patch.object(run, '_history_complete'), patch.object(run, 'acquire_pipeline_lock', return_value=True), patch.object(run, 'release_pipeline_lock'), patch.object(run, 'fetch_entrackr_result', return_value=FetchResult('Entrackr', [], 0)) as fetch, patch.object(run, '_enrich_websites') as enrich:
            status, summary = run.run_ingestion(lookback_hours=48, enrich_websites=False)
            self.assertEqual((status, summary['status']), (200, 'SUCCESS'))
            fetch.assert_called_once_with(verbose=False, lookback_hours=48)
            enrich.assert_not_called()

    def test_backup_window_accepts_article_missed_by_daily_window(self):
        from scraper import entrackr
        published = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=36)
        entry = {'title': 'Example raises $5 Mn led by Example Capital',
                 'link': 'https://example.test/funding',
                 'published_parsed': published.utctimetuple(),
                 'summary': 'Example raises $5 Mn led by Example Capital'}
        feed = MagicMock(entries=[entry])
        with patch.object(entrackr.requests, 'get'), patch.object(entrackr.feedparser, 'parse', return_value=feed):
            self.assertEqual(len(entrackr.fetch_entrackr_result().articles), 0)
            self.assertEqual(len(entrackr.fetch_entrackr_result(lookback_hours=48).articles), 1)


if __name__ == '__main__':
    unittest.main()
