# Independent daily ingestion backup

GitHub Actions executes Python directly against Supabase. It does not call
Vercel, and no running laptop is required for scheduled execution. Checks run
at 13:47, 15:47 and 19:47 IST, after the primary's 11:30 IST schedule.
GitHub schedules are best effort. Public repository schedules can be disabled
following 60 days without repository activity.

## Safeguards

- Only a completed SUCCESS started since the most recent 06:00 UTC primary
  schedule suppresses the backup. Zero new articles is a valid success.
- History is read before ingestion and rechecked under the shared database lock.
  Failed/partial runs remain eligible. Unavailable history fails closed.
- A backup must create its own history row before scraping, and verifies durable
  completion before reporting success. Run IDs are unique and marked
  github_fallback. Reads use bounded transient-error retries.
- The CLI kills its child process group after 240 seconds. The database lock
  lease lasts 330 seconds. GitHub also limits the step to five minutes and
  serializes backup jobs. A timeout can leave partial writes; existing duplicate
  checks support retries. This is not a cross-table transaction.
- Website enrichment is explicitly deferred. No OpenAI or frontend revalidation
  key is provided. Normal cache expiry applies after hosting resumes.
- The backup scans 48 hours of the current RSS feed. Older articles or articles
  absent from RSS need a separate sitemap backfill.

## Credential boundary

Actions use full commit IDs. Python dependencies and hashes are locked in
requirements-fallback.lock.txt. Tests run without production secrets. Pull
requests cannot enter the production job. That job only runs from the default
branch and references environment ivr-ingestion-backup.

Configure the environment to allow only main, with no tag rules. Store
SUPABASE_URL and SUPABASE_KEY as environment secrets, not repository-wide
secrets. Requiring a human reviewer for every run would prevent automatic
failover. The environment cannot prevent malicious code already merged into
main from using its secrets. Limit repository write access.

The existing service-role credential bypasses RLS across the project. A new
Supabase secret API key also uses service_role; it is not a restricted substitute.
A least-privilege identity requires additional auth/role/policy design and tests.
This release does not claim table-scoped access or mint a new key. Transfer of
the credential to GitHub requires the owner's explicit approval.

## Activation

1. Install sql/add_ingestion_lock.sql, sql/add_ingestion_runs.sql and
   sql/add_ingestion_run_metrics.sql. Existing funding-source and company-identity
   schema must match the connector. Do not apply unrelated repair scripts.
2. Review the isolated release and its pipeline dependencies. GitHub main was
   older than the locally deployed source when this release was prepared.
3. Configure the environment and provision its two secrets after approval.
4. Merge the reviewed release to main. Dispatch check_only=true, then false.
   Verify SUCCESS in ingestion_runs, then confirm a repeat dispatch skips.
5. Enable failed-workflow notifications in the user's GitHub settings. A failing
   Actions check alone does not guarantee an email notification.
6. Review the November outage backfill preview before applying confirmed events.

Disable the workflow in Actions to roll back scheduling. Existing data remains.
The backup covers funding ingestion only, not the AI source worker or website.

Local read-only preflight: python scripts/fallback_ingestion.py --check-only

Sources:
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
- https://supabase.com/docs/guides/getting-started/api-keys
