"""Independent backup; never calls the hosted Vercel endpoint."""
import argparse
import datetime as dt
import sys
import os
import signal
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scraper.database import _get_client, _execute_with_retry
from api.run import run_ingestion

UTC = dt.timezone.utc
EXECUTION_TIMEOUT_SECONDS = 240


def daily_cutoff(now):
    """Most recent primary schedule, 06:00 UTC (11:30 IST)."""
    cutoff = now.astimezone(UTC).replace(hour=6, minute=0, second=0, microsecond=0)
    return cutoff if now >= cutoff else cutoff - dt.timedelta(days=1)


def needs_run(client, now):
    # Reading metrics as well verifies the required schema before any scrape.
    # A zero-article SUCCESS counts; a last funding-row timestamp does not.
    query = (client.table('ingestion_runs')
            .select('run_id,started_at,completed_at,status,duration_ms,cpu_ms,stages,cache_refresh_status')
            .eq('status', 'SUCCESS').gte('started_at', daily_cutoff(now).isoformat())
            .lte('started_at', now.isoformat()).order('started_at', desc=True)
            .limit(1))
    rows = _execute_with_retry(query.execute).data
    return not any(row.get('completed_at') for row in rows or [])


def execute(check_only=False):
    """Run in a child process so termination cannot outlive the database lease."""
    command = [sys.executable, str(Path(__file__).resolve()), '--execute']
    if check_only:
        command.append('--check-only')
    child = subprocess.Popen(command, start_new_session=True)
    try:
        return child.wait(timeout=EXECUTION_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.wait()
        print('FAILED: backup exceeded its four-minute execution limit')
        return 124


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true', help='Read history without ingestion')
    parser.add_argument('--execute', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        client = _get_client()
        if not needs_run(client, dt.datetime.now(UTC)):
            print('SKIPPED_FRESH: daily ingestion already succeeded')
            return 0
        if args.check_only:
            print('DUE: backup ingestion is needed; no changes made')
            return 0
        status, summary = run_ingestion(
            trigger='github_fallback', lookback_hours=48, require_history=True, enrich_websites=False,
            should_run=lambda: needs_run(client, dt.datetime.now(UTC)),
        )
        if status != 200 or summary['status'] not in ('SUCCESS', 'SKIPPED_FRESH', 'SKIPPED_CONCURRENT'):
            return 1
        if summary['status'] == 'SUCCESS':
            query = (client.table('ingestion_runs').select('status,completed_at')
                     .eq('run_id', summary['run_id']))
            rows = _execute_with_retry(query.execute).data
            if not rows or rows[0]['status'] != 'SUCCESS' or not rows[0].get('completed_at'):
                print('FAILED: ingestion completion was not durably recorded')
                return 1
        return 0
    except Exception as error:
        # SDK exceptions can include request URLs/credentials; keep CI output safe.
        print(f'FAILED: backup unavailable ({type(error).__name__}); check schema, credentials and connectivity')
        return 1


if __name__ == '__main__':
    # The child uses the same parser; parent has no database operations.
    if '--execute' in sys.argv:
        raise SystemExit(main())
    if set(sys.argv[1:]) - {'--check-only'}:
        raise SystemExit(main(['--help']))
    raise SystemExit(execute(check_only='--check-only' in sys.argv))
