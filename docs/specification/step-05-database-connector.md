Step 5 — Database Connector Specification
Status: Draft

Version: 1.0

Milestone: Step 5 of 7

Prerequisite: Step 4 (Evidence Extraction Engine) completed and validated.

Table of Contents

Objective
Architectural Constraints
Prerequisites
Functional Requirements
Transaction Behaviour
Error Handling
Operational Summary
Deliverables
Acceptance Criteria
Out of Scope


1. Objective
Implement the Database Connector responsible for persisting structured funding records produced by the Evidence Extraction Engine into Supabase.
The Database Connector is the final stage of the ingestion pipeline.
RSS Feed
    ↓
Funding Classifier
    ↓
Evidence Extraction Engine
    ↓
Database Connector
    ↓
Supabase
Its responsibility is limited to database persistence.
It must not perform parsing, extraction, reconciliation, or business inference.

2. Architectural Constraints

The Database Connector is responsible only for persistence.
It must not modify parser output.
It must not perform data reconciliation.
It must never overwrite manually curated company information.
The connector must behave deterministically.
Running the connector multiple times against the same parser output must not create duplicate funding events.


3. Prerequisites
Before implementing the Database Connector, complete the following architectural changes. These are considered part of Step 5.
3.1 Preserve classification_confidence Through the Pipeline
The Funding Classifier currently computes classification_confidence, but the value is discarded before reaching the parser.
This metadata is required by the Database Connector and must be preserved throughout the pipeline.
Implement the following changes:

Include classification_confidence in the article dictionary returned by fetch_entrackr_articles()
Extend the normalized article contract in normalize_entrackr_article() to include classification_confidence
Preserve classification_confidence in the structured funding record returned by the parser
The parser must not interpret, modify, or recompute this value — it should simply preserve it as pipeline metadata
The Database Connector will persist this value directly into the funding_events table

3.2 Extend the Database Schema for Parser Metadata
The current funding_events schema does not contain parser review metadata.
As part of Step 5, create a database migration to add the following columns:

manual_review_required (boolean, nullable)
manual_review_reason (text, nullable)

Note: classification_confidence was already added to the funding_events table in Step 2.3. Do not attempt to add this column again. This migration should add only manual_review_required and manual_review_reason.
Save the migration as sql/add_parser_metadata.sql.
Do not modify sql/create_tables.sql or any existing SQL files.
3.3 Design Principle
Parser metadata should flow through the pipeline unchanged until it reaches the component responsible for persistence.
Ownership is defined as follows:
Funding Classifier       → Creates classification_confidence
Evidence Extraction Engine → Preserves pipeline metadata without interpretation
Database Connector       → Persists pipeline metadata
Supabase                 → Stores metadata for operational use and manual curation
Future pipeline metadata should follow the same preservation pattern without requiring architectural changes.

4. Functional Requirements
Company Handling
For every structured funding record:

Check whether the company already exists
If the company does not exist, create it
If the company already exists, reuse the existing company record
Never update company fields during ingestion

Human-curated company information is considered authoritative.
Funding Event Handling
Each funding event is uniquely identified by its article URL.
Before inserting:

Check whether the article URL already exists
If it exists, skip insertion
Do not update the existing funding event

Duplicate funding events must never be created.
Metadata Preservation
Persist all metadata received from upstream stages, including:

source_name
article_url
article_publication_date
classification_confidence
manual_review_required
manual_review_reason

The Database Connector must preserve metadata without modification.
Persistence Validation
Before attempting insertion, verify the minimum persistence contract.
Required fields:

Company Name
Article URL
Publication Date
Source Name

If any required field is missing:

Skip insertion
Report the reason
Continue processing remaining records

Business fields such as funding amount, funding round, valuation, investors, headquarters, website, and description may remain NULL.

5. Transaction Behaviour
Each funding article represents one independent transaction.
Processing flow:

Begin transaction
Create company if required
Insert funding event
Commit transaction

If any operation fails:

Roll back only that article
Continue processing remaining articles

A failure for one funding event must never prevent other valid funding events from being stored.

6. Error Handling
Errors should be classified into actionable categories:
ErrorActionDuplicate articleAlready processed — skipPersistence validation failureManual review requiredTemporary database or network failureRetry tomorrowUnexpected application errorInvestigate
The connector should provide clear, actionable messages instead of raw exceptions whenever possible.

7. Operational Summary
At the end of every execution, display an operational summary.
Include:

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

Today's Review Queue represents the number of records marked as requiring manual review.
The operational summary should provide a complete overview of the ingestion run before the user opens the database.

8. Deliverables
Implement:

Database Connector module inside scraper/database.py
Company lookup and creation
Funding event insertion
Duplicate detection
Transaction management
Persistence validation
Metadata persistence including classification_confidence, manual_review_required, and manual_review_reason
Operational summary
Error reporting
SQL migration file sql/add_parser_metadata.sql
Updated requirements.txt if new dependencies are required
A single Terminal command to run the full pipeline end to end including database writes


9. Acceptance Criteria
The implementation is complete when:
✓ classification_confidence flows correctly from the classifier through the parser to the database
✓ manual_review_required and manual_review_required columns exist in funding_events
✓ Valid funding records are successfully persisted
✓ Duplicate funding events are skipped
✓ Existing companies are reused
✓ Company records are never overwritten
✓ All metadata is preserved exactly as received from upstream stages
✓ One failed article does not interrupt the remaining ingestion process
✓ The operational summary accurately reflects the ingestion run
✓ Running the connector multiple times produces no duplicate funding events

10. Out of Scope
The following capabilities are intentionally excluded from Step 5:

Cross-source reconciliation
Company profile enrichment
Updating existing company information
Automatic retry queues
Historical record reconciliation
Multi-source conflict resolution

These belong to future milestones.

Stop immediately after completing this milestone. Wait for confirmation before beginning Step 6. Do not anticipate future milestones.
