Step 7 — Main Application and Scheduler Specification
Status: Draft

Version: 1.0

Milestone: Step 7 of 7

Prerequisite: Step 6 (Logger) completed and validated.

Table of Contents

Objective
Architectural Constraints
Main Application
Scheduling
Error Handling
Deliverables
Acceptance Criteria
Out of Scope


Revision History
VersionDescription1.0Initial implementation of main.py and launchd scheduling.

1. Objective
Wire all pipeline components into a single application entry point.
After Step 7, the entire ingestion pipeline should execute with one command:
python main.py
Additionally, configure macOS launchd to run the pipeline automatically every morning at 7:00 AM IST without any manual intervention.
This is the final step that transforms a collection of independent modules into a complete, automated application.

2. Architectural Constraints

main.py is the application entry point only. It must not contain business logic.
main.py must coordinate existing modules without duplicating their responsibilities.
The scheduler must use macOS launchd — not cron — for better sleep state handling.
The pipeline must remain manually runnable at any time via python main.py.
Scheduling must not affect the pipeline's behaviour — the same code runs whether triggered manually or by the scheduler.


3. Main Application
Responsibility
main.py is responsible for:

Loading environment variables from .env
Initialising the pipeline
Calling each module in the correct sequence
Passing outputs between modules
Handing the final result to the logger
Reporting the outcome to the terminal

Pipeline Sequence
Load environment
        ↓
Fetch RSS articles (scraper/entrackr.py)
        ↓
Run Evidence Extraction Engine (scraper/parser.py)
        ↓
Persist to Supabase (scraper/database.py)
        ↓
Write log file (scraper/logger.py)
        ↓
Print operational summary to terminal
Entry Point
Running the pipeline manually should require only:
python main.py
No additional arguments should be required for normal daily operation.
Environment
Load all credentials and configuration from .env using python-dotenv.
Never hardcode credentials or configuration values in main.py.
Terminal Output
main.py should print a clean startup message when the pipeline begins:
India Venture Review — Ingestion Pipeline
Starting run: IVR-20260630-0700
And a clean completion message when it finishes:
Pipeline complete.
Status: SUCCESS
Log: logs/2026-06-30.log

4. Scheduling
Tool
Use macOS launchd for scheduling.
Do not use cron.
launchd is the recommended macOS job scheduler. Unlike cron, launchd handles sleep states gracefully — if the Mac is asleep at the scheduled time, the job runs as soon as the Mac wakes up rather than being skipped entirely.
Schedule
Run the pipeline every day at 7:00 AM IST.
7:00 AM IST = 1:30 AM UTC.
launchd uses local system time. Provide instructions for verifying the correct local time conversion based on the Mac's timezone setting.
First Run Date
The LaunchAgent should be configured to begin automated runs from tomorrow's date onwards.
Do not trigger a run today.
Today's pipeline has already been executed manually.
The first automated run should occur tomorrow morning at 7:00 AM IST.
Provide instructions for verifying the LaunchAgent is loaded and waiting for tomorrow's scheduled time without triggering an immediate run.
LaunchAgent Configuration
Create a launchd plist file at:
~/Library/LaunchAgents/com.indiaventurereview.pipeline.plist
The plist should:

Point to the correct Python interpreter inside .venv
Point to main.py in the project root
Set the working directory to the project root
Redirect stdout and stderr to log files for debugging
Run at 7:00 AM IST every day

Loading the LaunchAgent
Provide exact Terminal commands to:

Load the LaunchAgent
Verify it is loaded correctly
Test it manually without waiting for the scheduled time
Unload it if needed

Stdout and Stderr Redirection
Redirect pipeline output to:
logs/launchd-stdout.log
logs/launchd-stderr.log
This captures any output or errors that occur during automated runs when no terminal is open.

5. Error Handling
If any pipeline stage fails catastrophically:

Log the failure with status FAILED
Print the failure reason to the terminal
Exit cleanly without crashing

main.py should never produce an unhandled exception visible to the user.

6. Deliverables

Updated main.py wiring all pipeline modules in sequence
launchd plist file at the correct location
Exact Terminal commands to load, verify, test, and unload the LaunchAgent
Instructions to verify the pipeline runs correctly via python main.py
Instructions to verify the LaunchAgent is loaded and scheduled correctly
Updated requirements.txt if new dependencies are introduced


7. Acceptance Criteria
The implementation is complete when:
✓ python main.py runs the complete pipeline end to end
✓ A log file is produced after every run
✓ The terminal shows a clean startup and completion message
✓ The LaunchAgent is loaded and scheduled for 7:00 AM IST daily
✓ The pipeline runs automatically without manual intervention
✓ If the Mac is asleep at 7:00 AM, the pipeline runs when the Mac wakes up
✓ Stdout and stderr are redirected to log files during automated runs
✓ The pipeline behaves identically whether triggered manually or by the scheduler
✓ No credentials or configuration values are hardcoded in main.py
✓ The first automated run occurs tomorrow morning — today's run has already been completed manually

8. Out of Scope
The following capabilities are intentionally excluded from Step 7:

Cloud deployment
Remote server scheduling
Email or push notifications
Dashboard or monitoring UI
Multiple pipeline configurations
Command line arguments
Pipeline parameterisation

These belong to future milestones.

Stop immediately after completing this milestone. Wait for confirmation before continuing. This is the final step of the MVP pipeline.