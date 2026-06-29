Step 4 — Evidence Extraction Engine (Version 1)
Status: Draft

Version: 1.0

Milestone: Step 4 of 7

Prerequisite: Step 3 (RSS Ingestion Pipeline) completed and validated.

Table of Contents

Objective
Scope
Architectural Overview
Architectural Constraints
Functional Requirements
Implementation Requirements
Validation Requirements
Deliverables
Acceptance Criteria
Out of Scope


Revision History
VersionDescription1.0Initial implementation of the Evidence Extraction Engine.

1. Objective
The RSS ingestion pipeline implemented in Step 3 is responsible for discovering funding announcements from Entrackr and returning normalized article data.
The objective of this milestone is to build Version 1 of the Evidence Extraction Engine.
The Evidence Extraction Engine transforms a single normalized funding article into the richest possible structured funding record using only explicitly verifiable information contained within that article.
The resulting structured record will be consumed by the database insertion pipeline implemented in the next milestone.
This milestone does not include:

database insertion
scheduling
historical imports
cross-source reconciliation
content generation
AI-assisted extraction
manual review persistence

The implementation should focus exclusively on deterministic evidence extraction.

2. Scope
In Scope
This milestone includes:

Evidence extraction from a normalized funding article
Progressive extraction using RSS content followed by the full article when necessary
Structured extraction of all applicable business fields defined by the current funding_events schema
Validation output for manual review
Graceful handling of incomplete or malformed articles
A reusable architecture capable of supporting additional news sources in future milestones

Out of Scope
This milestone intentionally excludes:

Database writes
Supabase integration
Historical backfill
Cross-source validation
Evidence reconciliation
Duplicate detection
Scheduling
Automation
AI-assisted extraction
Content generation
Notification systems

Future milestones will implement these capabilities.

3. Architectural Overview
The Evidence Extraction Engine forms the second stage of the ingestion pipeline.
             RSS Feed
                  │
                  ▼
          Source Adapter
                  │
                  ▼
        Normalized Article
                  │
                  ▼
   Evidence Extraction Engine
                  │
  ┌───────────────┼───────────────┐
  ▼               ▼               ▼
Company         Funding        Investor
Extractor       Extractor      Extractor
  └───────────────┼───────────────┘
                  ▼
   Structured Funding Record
                  │
                  ▼
  (Step 5 — Database Insertion)
Version 1 implements only the Entrackr adapter.
The architecture should allow additional adapters to be introduced in future milestones without modifying the shared Evidence Extraction Engine.

4. Architectural Constraints
The following constraints are mandatory.
Every implementation decision should respect these principles.
1. Evidence Over Assumptions
Only extract information explicitly stated within the article.
Never:

infer
estimate
fabricate
enrich using prior knowledge

If information cannot be verified, return None.
Missing information is preferable to incorrect information.
2. Database Schema Is the Business Contract
The funding_events schema defines the business fields that the Evidence Extraction Engine is responsible for producing.
The extraction engine should populate every applicable field defined by the current schema using only explicit evidence contained within the article.
The extraction engine should not maintain a separate authoritative definition of business fields.
Future schema additions should extend the extraction logic rather than introducing duplicate field definitions elsewhere.
3. One Article Represents One Evidence Source
Each article should be processed independently.
Version 1 does not perform:

reconciliation
comparison
conflict resolution
evidence ranking

Those capabilities belong to future milestones.
4. Progressive Evidence Collection
Evidence should be collected in stages.
Stage 1
Attempt extraction from:

RSS title
RSS summary/content

Stage 2
Only if important business fields remain unavailable:

retrieve the full article
continue extraction

If information still cannot be verified, return None.
The engine should avoid downloading the full article unless necessary.
5. Deterministic Extraction
Given identical article content, the Evidence Extraction Engine must always produce identical structured output.
The implementation must not depend on:

randomness
probabilistic techniques
AI reasoning
non-deterministic behaviour

Duplicate prevention and database idempotency are intentionally outside the scope of this milestone.
6. Human-in-the-Loop Architecture
The system is intentionally designed to support manual review.
The engine is responsible for automating repetitive extraction work.
The human reviewer remains responsible for validating uncertain or incomplete records before publication.
Validation output should surface uncertainty rather than hide it.
7. Fault Tolerance
Failure to extract one article must never terminate the processing pipeline.
If:

article retrieval fails
HTML parsing fails
extraction fails for one field

the engine should:

preserve successfully extracted fields
return None for unavailable values
continue processing remaining fields
continue processing remaining articles

8. Design for Future Evolution
The implementation should naturally support future capabilities including:

additional news sources
source adapters
evidence reconciliation
AI-assisted extraction
historical imports

These capabilities must not be implemented in Version 1.
The objective is to create stable extension points without introducing unnecessary complexity.

5. Functional Requirements
Primary Responsibility
The Evidence Extraction Engine is responsible for transforming one normalized funding article into one structured funding record.
Its objective is to extract every explicitly verifiable business fact contained within the article while making no assumptions beyond the available evidence.
The engine should operate independently of:

database insertion
scheduling
reconciliation
historical imports
content generation

Normalized Article Contract
The Evidence Extraction Engine should operate on a normalized article object rather than source-specific data structures.
Version 1 includes only the Entrackr adapter.
The adapter is responsible for converting source-specific RSS data into the normalized article format expected by the extraction engine.
The extraction engine should never depend on Entrackr-specific RSS fields or HTML structure.
The normalized article should provide the following information:
textarticle_title
article_url
article_publication_date
source_name
raw_content
Future adapters should produce the same contract regardless of publication.
Processing Lifecycle
Every article should follow the same deterministic processing pipeline.
Normalized Article
        │
        ▼
Initial Validation
        │
        ▼
Stage 1 Extraction
(RSS Title + RSS Content)
        │
        ▼
Required Fields Complete?
        │
   ┌────┴────┐
   │         │
  Yes        No
   │         │
   │         ▼
   │   Retrieve Full Article
   │         │
   │         ▼
   │   Stage 2 Extraction
   │         │
   └─────────┘
        │
        ▼
Merge Extracted Evidence
        │
        ▼
Validation Report
        │
        ▼
Structured Funding Record
Every article should follow this lifecycle.
The implementation should not bypass stages or alter the order of execution.
Progressive Evidence Collection
Stage 1
Attempt extraction using:

RSS title
RSS summary/content

If all important business fields are successfully extracted, processing should stop.
The full article should not be downloaded unnecessarily.
Stage 2
If important business fields remain unavailable after Stage 1:

download the article
continue extraction using the article body

Any values successfully extracted during Stage 1 should be preserved.
Only missing fields should be populated during Stage 2.
Stage 2 should never overwrite an existing value unless the article body explicitly provides a more complete version of the same information.
Stage 2 Escalation Criteria
The Evidence Extraction Engine should retrieve the full article only if one or more of the following primary business fields cannot be extracted during Stage 1:

Company Name
Funding Amount
Funding Round
Lead Investor(s)

These fields represent the minimum business information required for a useful funding event record.
Missing secondary fields (for example headquarters, website, founding year, valuation, business description, or participating investors) should not trigger Stage 2 retrieval on their own.
If Stage 2 is already required for a primary field, the engine should opportunistically extract all remaining available business fields from the full article before completing processing.
Business Field Extraction
The Evidence Extraction Engine should extract every applicable business field defined by the current funding_events schema.
The database schema is the authoritative business contract.
If a field exists in the schema and explicit evidence is available within the article, the extraction engine should populate that field.
If no explicit evidence exists, return None.
Do not duplicate the field definitions inside the extraction engine.
Domain-Oriented Architecture
The extraction engine should organize business logic into cohesive extraction domains.
Company Extraction
Responsible for company-related information:

company identity
company description
headquarters
industry
business model
founding information
website

Funding Extraction
Responsible for funding-related information:

funding amount
currency
funding round
valuation
funding type

Investor Extraction
Responsible for investor-related information:

lead investors
participating investors

Metadata Extraction
Responsible for metadata originating from the source article:

article URL
publication date
source name

Parser Orchestrator
The parser orchestrator is responsible for coordinating the extraction process.
Its responsibilities include:

receiving normalized articles
initiating Stage 1 extraction
determining whether Stage 2 is required
requesting the full article when necessary
coordinating all extraction domains
merging extracted evidence
producing validation information
returning one structured funding record

The orchestrator should not contain business extraction logic.
Missing Information
If information cannot be verified after both extraction stages, return:
pythonNone
Do not return:

Unknown
N/A
Empty strings
Placeholder values
Estimated values

Missing information should remain explicitly missing.
Extraction Rules
Every extracted value must satisfy all of the following conditions.
Explicit — The information must be directly stated.
Verifiable — The value should be traceable to the article.
Deterministic — Repeated extraction of the same article should always produce identical output.
Independent — Each field should be extracted independently. Failure to extract one field should never prevent extraction of the remaining fields.
Structured Record
Each processed article should produce one structured funding record.
The structured record should contain:

every successfully extracted business field
metadata required by downstream stages

The returned record should not contain:

validation output
extraction diagnostics
confidence explanations
internal implementation details

Those belong exclusively to the validation layer.
Completion Condition
The Evidence Extraction Engine has successfully processed an article when:

every extraction stage has completed
every explicitly verifiable business field has been extracted
unavailable information has been returned as None
one structured funding record has been produced
processing continues regardless of partial extraction failures


6. Implementation Requirements
Implementation Philosophy
The objective of this milestone is not only to build a working parser but to establish a maintainable architecture for future extraction capabilities.
The implementation should prioritize:

readability
maintainability
deterministic behaviour
clear separation of responsibilities

Avoid unnecessary abstraction while creating natural extension points for future milestones.
Input Validation
Before beginning extraction, the Evidence Extraction Engine should validate that the normalized article satisfies the minimum contract.
Examples include:

article title exists
article URL exists
publication date is present
source name exists
article content is available

If required information is missing:

report the validation issue
continue whenever possible
avoid terminating the processing pipeline

Input validation exists to protect the extraction engine from malformed upstream data. It is not responsible for correcting malformed input.
Internal Architecture
The implementation should separate responsibilities into distinct layers.
Normalized Article
        │
        ▼
Input Validation
        │
        ▼
Parser Orchestrator
        │
        ├─────────────┐
        ▼             ▼
 Stage 1         Stage 2
 Extraction      Extraction
        │             │
        └──────┬──────┘
               ▼
      Evidence Merge
               ▼
     Output Validation
               ▼
 Structured Funding Record
Each layer should have a clearly defined responsibility.
Separation of Responsibilities
The implementation should isolate:

source normalization
input validation
extraction
evidence merging
output validation
validation reporting

Avoid combining multiple responsibilities into a single implementation unit.
Domain Extractors
Business extraction logic should be organized into domain-oriented extractors.
Each extractor should own one cohesive responsibility.
Recommended domains:

Company
Funding
Investors
Metadata

Each extractor should operate independently.
Extractors should not depend on one another.
The parser orchestrator is responsible for combining their outputs.
Reusable Extraction Utilities
Shared extraction patterns should be implemented once and reused.
Examples include:

currency detection
funding amount detection
valuation detection
investor phrase detection
date normalization

Avoid duplicating extraction logic across multiple domains.
Full Article Retrieval
The full article should only be downloaded when required.
The orchestrator should determine whether Stage 2 extraction is necessary based on missing primary business fields after Stage 1.
Avoid unnecessary network requests.
Respectful Article Retrieval
The Evidence Extraction Engine should retrieve full articles responsibly.
Only retrieve articles when Stage 2 extraction is required.
Avoid unnecessary requests.
When multiple full article requests are made during a single execution, introduce a small delay between requests to avoid placing unnecessary load on the source website.
The exact delay may be implementation-dependent but should remain short enough that it does not materially affect the daily ingestion workflow.
A full article should be retrieved at most once per article during a processing run.
Once downloaded, the article content should be reused by all extraction domains.
HTML Parsing
The implementation should use stable HTML parsing techniques.
Avoid selectors tightly coupled to page styling.
Prefer semantic HTML whenever available.
If expected content cannot be located:

preserve existing evidence
report the issue
continue processing

HTML parsing failures should not terminate the pipeline.
Evidence Merge
Information collected during Stage 2 should be merged into the structured record.
Merge rules:

preserve existing verified values
populate only missing fields
replace values only when the article body provides a demonstrably more complete version of the same information

The merge process should never discard verified evidence.
Output Validation
Before returning the structured funding record, verify:

required metadata exists
extracted fields follow expected data types
None is used consistently for unavailable information

Output validation exists to ensure downstream stages receive a predictable structure. It is not responsible for determining business correctness.
Coding Standards
Use:

descriptive function names
descriptive variable names
clear comments where necessary

Avoid:

deeply nested conditionals
duplicated logic
excessively clever implementations
premature optimization

Readable code is preferred over compact code.
Dependencies
Use only:

Python standard library
widely adopted Python packages

If additional dependencies are required:

explain why
update requirements.txt

Avoid introducing dependencies for functionality already provided by existing packages.
Future Compatibility
Version 1 should establish natural extension points for:

additional source adapters
new extraction rules
new business fields
reconciliation engines

Do not implement these capabilities. The implementation should simply avoid making future evolution difficult.

7. Validation Requirements
Validation exists to provide visibility into the quality of the extraction process.
Its purpose is not debugging.
Its purpose is to answer three business questions:

Was the article successfully processed?
What information was extracted?
Does this article require manual review?

Validation output should optimize for the human curator reviewing funding events each morning.
Implementation details should remain hidden.
Manual Validation Command
Provide a single Terminal command that executes the complete extraction pipeline.
Running the command should:

retrieve recent RSS articles
normalize articles
execute the Evidence Extraction Engine
display validation output
return structured funding records

The command must not:

write to the database
modify application state
perform scheduling

Per-Article Validation Output
Each processed article should produce a concise validation summary.
The summary should communicate business information rather than implementation details.
Recommended information includes:

article title
extraction status
confidence level
evidence source
whether the full article was retrieved
number of extracted fields
missing fields
manual review recommendation

Example:
✓ Healthcare startup MyKare.ai raises $3.2 Mn

Confidence          Strong
Evidence            RSS + Full Article
Fields Extracted    13 / 15
Missing Fields      Headquarters
Manual Review       No
Validation Summary
After processing all articles, provide an overall summary.
Include metrics such as:

RSS articles processed
funding articles accepted
successfully parsed articles
articles requiring full article retrieval
articles requiring manual review
extraction failures

Optional metrics:

average extraction completeness
average fields extracted

Failure Reporting
Validation should distinguish between:

RSS failures
article retrieval failures
extraction failures
missing information

Missing business information is not considered an error.
Only genuine processing failures should be reported as failures.
Manual Review Recommendation
The validation output should recommend manual review whenever:

conflicting information exists
important fields remain unavailable
unexpected parsing behaviour occurs

This recommendation exists solely for the validation report. It should not be persisted.
Non-Functional Requirements
Reliability — Failure to process one article must never terminate the pipeline.
Maintainability — Business extraction logic should remain modular and easy to extend.
Readability — Code should prioritize clarity over compactness.
Determinism — Repeated processing of identical input should always produce identical output.
Extensibility — Future milestones should be able to introduce additional source adapters, reconciliation, and AI-assisted extraction without requiring significant architectural restructuring.

8. Deliverables
Implementation
A complete implementation of Version 1 of the Evidence Extraction Engine.
Project Files
Modify only the files required for this milestone. If additional modules are introduced, explain their responsibilities. Avoid unrelated modifications.
Dependencies
Update requirements.txt only when additional dependencies are required. Explain the purpose of each newly introduced dependency.
Validation Command
Provide the command required to execute the extraction pipeline manually.
Implementation Summary
Briefly explain:

parser architecture
orchestrator responsibilities
extraction domains
progressive evidence collection
evidence merge strategy
adapter integration


9. Acceptance Criteria
This milestone is considered complete only if all of the following conditions are satisfied.
✓ The Entrackr adapter produces normalized articles.
✓ The Evidence Extraction Engine accepts normalized articles.
✓ Stage 1 extraction operates on RSS data.
✓ Stage 2 retrieval occurs only when required.
✓ Business fields are extracted according to the current funding_events schema.
✓ Missing values are returned as None.
✓ No assumptions or inferred values are introduced.
✓ Validation output clearly communicates extraction quality.
✓ Processing failures do not terminate the pipeline.
✓ Structured funding records are returned.
✓ The implementation does not write to the database.
✓ The architecture naturally supports future source adapters.

10. Out of Scope
Version 1 intentionally excludes:

database insertion
scheduling
historical imports
cross-source reconciliation
duplicate detection
canonical funding events
AI-assisted extraction
content generation
notification systems
review persistence
adapter registries
factories
plugin systems

These capabilities belong to future milestones.

Stop immediately after completing this milestone. Wait for confirmation before beginning Step 5. Do not anticipate future milestones.
