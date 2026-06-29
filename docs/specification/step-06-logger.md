Step 6 — Logger Specification
Status: Draft

Version: 1.0

Milestone: Step 6 of 7

Prerequisite: Step 5 (Database Connector) completed and validated.

Table of Contents

Objective
Architectural Constraints
Log Format
Log Location and Retention
Run Metadata
Pipeline Statistics
Failure Reporting
Configuration Snapshot
Pipeline Version Information
Run Status
Deliverables
Acceptance Criteria
Out of Scope


Revision History
VersionDescription1.0Initial implementation of the Logger.

1. Objective
Implement a structured logging system that records every pipeline execution for India Venture Review.
Every morning when the ingestion pipeline runs, a log file should be created capturing the complete operational record of that run.
The Logger serves two purposes:

Operational visibility — understand what happened during each run without re-executing the pipeline
Historical diagnostics — diagnose long-term issues by comparing runs over time

The Logger is the fifth and final component of the ingestion pipeline before Step 7 wires everything together.
RSS Feed
    ↓
Funding Classifier
    ↓
Evidence Extraction Engine
    ↓
Database Connector
    ↓
Logger
    ↓
Log File (logs/YYYY-MM-DD.log)

2. Architectural Constraints

The Logger is responsible only for recording pipeline execution. It must not modify pipeline behaviour.
The Logger must never cause the pipeline to fail. If logging itself fails, the pipeline should continue and report the logging failure to the terminal.
Log files must be human-readable without requiring any tooling.
Log content must mirror terminal output so live runs and historical logs are directly comparable.
The Logger must be passive — it observes and records, it does not influence decisions.


3. Log Format
Use a structured operational log rather than free-form text.
The log should be readable as a plain text file and should mirror the terminal output produced during a live run.
Each log file represents one complete pipeline execution.
Example log structure:
============================================================
INDIA VENTURE REVIEW — INGESTION PIPELINE LOG
============================================================

Run ID:              IVR-20260630-0800
Start Time:          2026-06-30 08:00:03
End Time:            2026-06-30 08:04:17
Total Execution Time: 4 minutes 14 seconds
Pipeline Status:     SUCCESS

------------------------------------------------------------
CONFIGURATION
------------------------------------------------------------
RSS Source:          Entrackr
Lookback Window:     24 hours
Classifier Threshold: 3

------------------------------------------------------------
VERSION
------------------------------------------------------------
Git Commit Hash:     be7c309
Parser Version:      1.0
Database Connector:  1.0

------------------------------------------------------------
PIPELINE STATISTICS
------------------------------------------------------------
RSS Articles Processed:           8
Funding Articles Accepted:        7
Structured Records Produced:      7
Companies Created:                2
Companies Reused:                 5
Funding Events Inserted:          2
Duplicates Skipped:               5
Persistence Validation Failures:  0
Database Errors:                  0
Today's Review Queue:             0

------------------------------------------------------------
ARTICLE LOG
------------------------------------------------------------
[INSERTED — Strong]   Healthcare startup MyKare.ai raises $3.2 Mn
[DUPLICATE — Skipped] The Capitalist Ventures bags Rs 10 Cr seed round
[DUPLICATE — Skipped] AI data infrastructure startup Clairva raises $500K
[INSERTED — Strong]   Lytmus AI raises pre-seed round from Boundless Ventures
[DUPLICATE — Skipped] The Func. Lab raises $1.5 Mn seed round
[DUPLICATE — Skipped] Co-working startup Incuspaze raises Rs 150 Cr
[SKIP — Validation]   https://entrackr.com/snippets/turtlemint-...
                      Reason: Missing required fields: company_name

------------------------------------------------------------
FAILURES
------------------------------------------------------------
None

============================================================
END OF LOG
============================================================

4. Log Location and Retention
Store all log files inside the logs/ folder in the project root.
One log file per pipeline execution.
File naming convention:
logs/YYYY-MM-DD.log
Examples:
logs/2026-07-01.log
logs/2026-07-02.log
logs/2026-07-03.log
If the pipeline runs more than once on the same day, append a run number:
logs/2026-07-01-1.log
logs/2026-07-01-2.log
Retention policy: Keep all logs. No rotation or deletion for now. Log files are small text files and historical runs are valuable for diagnosing long-term issues. Log rotation can be introduced in a future milestone if needed.

5. Run Metadata
Each log file must begin with metadata describing the pipeline execution.
Required fields:

Run ID — unique identifier formatted as IVR-YYYYMMDD-HHMM
Start Time — timestamp when the pipeline began execution
End Time — timestamp when the pipeline completed
Total Execution Time — human-readable duration
Pipeline Status — one of SUCCESS, PARTIAL_SUCCESS, or FAILED

The Run ID embeds both the date and time of execution, making every run uniquely identifiable and easily referenceable.

6. Pipeline Statistics
Each log must record the complete operational summary matching the terminal output exactly.
Required statistics:

RSS Articles Processed
Funding Articles Accepted
Structured Records Produced
Companies Created
Companies Reused
Funding Events Inserted
Duplicates Skipped
Persistence Validation Failures
Database Errors
Today's Review Queue

These statistics must match the terminal summary produced during the same run.

7. Failure Reporting
Each failed article must be recorded with enough context to diagnose the problem without rerunning the pipeline.
Required fields per failure:

Company name (if available)
Article URL
Failure reason
Suggested action

Example:
FAILED ARTICLE
----------------------------------------
Company:          Clairva
Article:          https://entrackr.com/snippets/...
Reason:           Supabase timeout
Suggested Action: Retry tomorrow
Suggested actions should be drawn from the error classification defined in Step 5:
ErrorSuggested ActionDuplicate articleAlready processed — no action requiredPersistence validation failureManual review requiredTemporary database or network failureRetry tomorrowUnexpected application errorInvestigate

8. Configuration Snapshot
Each log must capture the runtime configuration used during execution.
Required fields:

RSS Source
Lookback Window
Classifier Threshold

Example:
RSS Source:           Entrackr
Lookback Window:      24 hours
Classifier Threshold: 3
This makes logs meaningful even if configuration changes in the future. A historical log will always reflect the exact configuration that produced it.

9. Pipeline Version Information
Each log must record the software version that produced the run.
Required fields:

Git Commit Hash (if available — gracefully handle if git is unavailable)
Parser Version
Database Connector Version

Example:
Git Commit Hash:     be7c309
Parser Version:      1.0
Database Connector:  1.0
This makes every historical log traceable to the exact code that generated it.

10. Run Status
The pipeline status field must use one of three values only.
SUCCESS
The pipeline completed with no failures.
All articles were processed successfully.
PARTIAL_SUCCESS
The pipeline completed, but one or more articles failed while others succeeded.
Example: 8 articles processed, 7 inserted, 1 failed due to a validation error.
FAILED
The pipeline itself could not complete.
Example: RSS feed unreachable, database connection could not be established.
This distinction matters operationally.
PARTIAL_SUCCESS represents a healthy pipeline with one problematic article.
FAILED represents an operational outage requiring immediate attention.
These are fundamentally different situations and must never be conflated.

11. Deliverables
Implement:

Logger module inside scraper/logger.py
Log file creation in logs/ with correct naming convention
Run metadata section
Configuration snapshot section
Version information section
Pipeline statistics section
Per-article log entries
Failure reporting with suggested actions
Run status determination — SUCCESS, PARTIAL_SUCCESS, FAILED
Integration with existing pipeline modules without modifying their core logic
Updated requirements.txt if new dependencies are required
A validation command to run the full pipeline and confirm a log file is produced


12. Acceptance Criteria
The implementation is complete when:
✓ A log file is created in logs/ after every pipeline run
✓ The log file name follows the YYYY-MM-DD.log convention
✓ Run ID is formatted as IVR-YYYYMMDD-HHMM
✓ Start time, end time, and execution time are recorded correctly
✓ Pipeline status is correctly determined as SUCCESS, PARTIAL_SUCCESS, or FAILED
✓ Configuration snapshot is recorded
✓ Version information including git commit hash is recorded
✓ Pipeline statistics match the terminal summary exactly
✓ Every article outcome is recorded in the article log
✓ Failed articles include company name, URL, reason, and suggested action
✓ Logger failure never causes the pipeline to fail
✓ Log files are human-readable plain text
✓ Running the pipeline twice produces two separate log entries on the same day

13. Out of Scope
The following capabilities are intentionally excluded from Step 6:

Log rotation or deletion
Centralised log aggregation
Email or push notifications
Dashboard or visualisation
Log parsing or analysis tools
Remote log storage
Alerting systems

These belong to future milestones.

Stop immediately after completing this milestone. Wait for confirmation before beginning Step 7. Do not anticipate future milestones.