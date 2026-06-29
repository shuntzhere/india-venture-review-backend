# docs/

This folder contains project documentation beyond the top-level README.

Add guides, design decisions, API references, and research notes here as the project grows.

---

## Implementation History

Step 3 introduced the RSS ingestion pipeline in `scraper/entrackr.py`. The module connects to Entrackr's RSS feed, applies a 24-hour lookback window, and passes each article through a multi-signal weighted classifier before returning it.

The classifier was intentionally designed to evolve. Signal detectors are registered independently via `SIGNAL_REGISTRY`, and the scoring engine is separate from each detector's implementation. This architecture allows new signals — including AI-based classification — to be added in future milestones without restructuring the surrounding pipeline.

See `docs/implementation/` for the full engineering history of each milestone.
