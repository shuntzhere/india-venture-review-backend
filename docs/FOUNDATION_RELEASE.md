Status:           Foundation Release
Date:             2026-06-30
Repository Phase: Single-Source Pipeline

---

# India Venture Review — Foundation Release

## Overview

This milestone marks the completion of the first end-to-end funding ingestion pipeline for India Venture Review. Every component required to discover, classify, extract, persist, and log Indian startup funding announcements has been implemented, tested against live data, and wired into a single cohesive system.

What began as a collection of independent scripts has become a working software product. The pipeline runs on a schedule, produces structured records in a database, and leaves a permanent operational record of every run. India Venture Review is no longer a project in progress — it is a system in production.

---

## Vision

India Venture Review is being built to become a structured venture intelligence platform for the Indian startup ecosystem. The goal is not simply to aggregate funding news, but to create a clean, auditable, human-curated dataset of Indian venture activity — one that becomes more valuable over time as the historical record grows.

The approach is deliberate: begin with deterministic data collection and manual curation, establish a reliable foundation, and then expand. Multi-source ingestion, analytics, AI-assisted enrichment, and eventually a content generation pipeline all follow naturally once the foundation is sound. None of that is worth building on top of unreliable data.

This release is the foundation.

---

## What Was Built

The pipeline moves a funding article from an RSS feed into a structured database record through six discrete stages.

**Entrackr RSS Ingestion** fetches the Entrackr RSS feed over HTTP, applies a 24-hour lookback window, strips HTML from article content, and deduplicates entries by URL before passing articles downstream.

**Multi-Signal Funding Classifier** evaluates each article against three independent signals — funding keywords, funding amount patterns, and investor phrase patterns — using a weighted scoring engine with a configurable acceptance threshold. Articles that meet the threshold are accepted with a confidence label (Strong, Moderate, Weak) attached. Articles that do not are discarded with a reason.

**Evidence Extraction Engine** takes a classified article and attempts to extract structured fields across two stages. Stage 1 works from the RSS content already in hand. If primary fields — company name, funding amount, funding round, lead investors — remain incomplete after Stage 1, the engine fetches the full article and runs Stage 2. Evidence flows in one direction: verified fields from Stage 1 are never overwritten by Stage 2. The engine produces a structured record and a validation report.

**Database Connector** receives structured records from the extraction engine and persists them to Supabase. Each record goes through a three-step process: persistence validation (required fields present), duplicate detection (article URL already in database), and company lookup or creation. A failure at any step for any single record is isolated — the remaining records continue processing. The connector returns both aggregate statistics and per-article outcomes.

**Supabase Persistence** stores two entities: a `companies` table that grows as new companies are encountered, and a `funding_events` table that records each article alongside the structured data extracted from it. Classification confidence, manual review flags, and review reasons are all persisted alongside the business fields.

**Operational Logger** records every pipeline execution as a structured plain-text log file in `logs/`. Each log captures the run ID, timestamps, total duration, pipeline status, configuration snapshot, software version (including git commit hash), pipeline statistics, per-article outcomes, and failure details with suggested remediation actions. The logger is passive and non-blocking — a logging failure never stops the pipeline.

Data flows linearly through this sequence: RSS feed → classifier → extraction engine → database connector → logger → log file. No component reaches backward into a previous stage's domain, and no component anticipates the next.

---

## Engineering Principles

Several principles guided every architectural decision made during development. They were not imposed upfront — they emerged naturally from the problems encountered and resolved along the way.

**Deterministic over probabilistic.** Every classification and extraction decision in the pipeline can be traced to a specific pattern, rule, or threshold. There is no inference, no ambiguity, and no behavior that cannot be explained by reading the code. This makes the system auditable and its outputs trustworthy.

**Single responsibility for every module.** Each module owns exactly one concern. The classifier classifies. The extraction engine extracts. The connector persists. The logger records. No module reaches into another's domain, and no behavior is duplicated across modules. Adding a new news source requires only a new adapter — nothing downstream changes.

**Human curation is authoritative.** The pipeline is a data collection tool, not a data authority. Company records may be enriched by a human after ingestion. The connector never updates an existing company record — it only creates new ones. Whatever a human has edited is permanent.

**Never overwrite curated data.** A direct consequence of the above: the system writes once and defers to humans for corrections. The duplicate detection mechanism exists specifically to prevent the pipeline from trampling its own prior output or a human's edits.

**One article, one transaction.** A failure processing one article has no effect on any other article in the same run. The pipeline processes each record independently, records the outcome, and continues. An error is a data point, not a crash.

**Progressive evidence extraction.** The extraction engine avoids unnecessary full-article fetches by attempting extraction from the RSS content first. The full article is only retrieved when the RSS content is insufficient. This respects the source server's bandwidth and keeps the pipeline fast on days when articles are well-structured.

**Clear operational visibility.** Every run produces a log file. Every article produces an outcome record. Every failure includes a reason and a suggested action. The system is designed to be understood by reading its output, not by re-running it.

**Separation of business logic from infrastructure.** The extraction engine does not know about Supabase. The database connector does not know about RSS feeds. The logger does not know about confidence labels. Each component is testable, replaceable, and understandable in isolation.

---

## Current Capabilities

As of this release, the India Venture Review pipeline can:

- Discover funding announcements published in the last 24 hours from Entrackr's RSS feed
- Filter funding-related articles from general news using a weighted multi-signal classifier
- Extract structured company and funding information from article titles and content using deterministic pattern matching
- Persist company records and funding events to a Supabase PostgreSQL database
- Prevent duplicate ingestion — running the pipeline multiple times against the same articles produces no duplicate records
- Attach classification confidence, manual review flags, and review reasons to every persisted record
- Generate a dated operational log file after every run, capturing the complete record of what happened

The result is a growing, structured dataset of Indian startup funding events that can be reviewed, corrected, and built upon.

---

## Current Limitations

The following are intentional constraints at this stage of the project, not oversights.

**Single news source.** The pipeline ingests from Entrackr only. Entrackr was chosen for the MVP because it provides a reliable, structured RSS feed with high signal-to-noise ratio for Indian startup funding news. Multi-source ingestion adds reconciliation complexity that belongs to a later milestone.

**Manual enrichment required.** Secondary fields — website, description, industry, business model, headquarters, founding year — are not reliably extractable from article titles or RSS content. The pipeline leaves these fields blank for human enrichment. Automated extraction of these fields requires AI-assisted processing, which belongs to a later milestone.

**No retry queue.** Articles that fail processing are logged with a suggested action but are not automatically retried. A failed article requires manual intervention or a re-run the following day. A persistent retry queue adds operational complexity beyond the MVP scope.

**No multi-source reconciliation.** When multiple sources report the same funding event, the pipeline has no mechanism to identify and merge duplicate events from different URLs. This becomes relevant only when a second source is added.

**No analytics layer.** The database is populated but not yet queried. Sector trends, investor activity, round size distributions, and comparable analyses are future capabilities.

These constraints reflect where the project is, not where it is going.

---

## Looking Ahead

The immediate next step is pipeline orchestration — wiring all modules into a single `main.py` entry point and configuring macOS launchd to run the pipeline automatically at 7:00 AM IST every morning. Once in place, the pipeline will require no daily manual intervention.

Beyond that, the project's natural expansion points are clear. Additional news sources — Inc42, YourStory, VCCircle — each with their own adapters and potential source-level reconciliation. Reliability improvements including a retry queue for transient failures and alerting for persistent ones. An analytics layer that begins to surface patterns in the accumulated data. AI-assisted enrichment to fill secondary fields without manual intervention. Eventually, a content generation pipeline that produces structured summaries and a public platform that makes the data accessible.

Each of these builds on the foundation established here. The value of the foundation is that it holds.

---

## Reflection

Software projects often feel most alive in the middle — when modules are being built, decisions are being made, and the shape of the system is still emerging. The beginning is uncertainty. The end of a milestone is something quieter: the moment when the pieces stop being separate and become a system.

India Venture Review reached that moment with this release. The pipeline fetches, classifies, extracts, persists, and logs. It runs against real data. It handles failures gracefully and records everything. It is, in the most literal sense, working software.

What makes this milestone significant is not any individual component — it is the discipline with which they were kept separate and the care with which they were connected. A system built this way can be understood, extended, and trusted. That is worth more than any single feature.

The dataset is small. The sources are few. The capabilities are modest. But the architecture is sound, the data is clean, and the foundation is real. Everything else follows from here.
