# Parser Improvements Backlog

This document tracks parser quality improvements discovered during validation and real-world usage.

It is intentionally separate from the project roadmap (`TODO.md`) and release history (`CHANGELOG.md`).

The parser is considered architecturally complete. The items below focus on improving extraction accuracy and coverage without requiring architectural redesign.

---

# High Priority

## 1. Improve Company Extraction for Investor-First Headlines

**Priority:** High

### Problem

The current company extraction logic assumes the funded company appears before the funding verb.

This fails when the investor is mentioned first.

### Example

Headline:

> Boundless Ventures leads pre-seed round in Lytmus AI

Current Extraction

```text
Company: None
```

Expected Extraction

```text
Company: Lytmus AI
```

### Expected Behaviour

Support additional headline patterns where the funded company appears after phrases such as:

- leads round in
- invests in
- backs
- participates in

### Status

Not Started

### Discovered During

Step 4 Validation (2026-06-30)

---

## 2. Improve Company Extraction for Strategic Investment Headlines

**Priority:** High

### Problem

Strategic investment headlines may mention the investor first, causing the funded company to be missed.

### Example

Headline:

> Yash Raj Films makes strategic investment in Rusk Media

Current Extraction

```text
Company: None
```

Expected Extraction

```text
Company: Rusk Media
```

### Expected Behaviour

Recognize strategic investment headline structures and correctly identify the funded company.

### Status

Not Started

### Discovered During

Step 4 Validation (2026-06-30)

---

## 3. Exclude IPO, Listing and Market Debut Articles

**Priority:** High

### Problem

The parser currently accepts some IPO or listing-related articles as funding events.

### Example

Headline:

> Turtlemint lists at 11.25% discount on market debut

Current Extraction

```text
Funding Amount: 475M USD
```

Expected Behaviour

The article should be rejected before extraction or classified as a non-funding event.

Funding extraction should only occur for genuine funding announcements.

### Status

Not Started

### Discovered During

Step 4 Validation (2026-06-30)

---

## 4. Improve Lead Investor Extraction

**Priority:** High

### Problem

Some articles return no lead investors even though funding information is successfully extracted.

### Investigation

Determine whether:

- the article genuinely omits the lead investor, or
- the extraction logic failed to recognize the pattern.

Collect several examples before modifying the extraction rules.

### Expected Behaviour

Lead investors should be extracted whenever explicitly mentioned.

### Status

Needs Investigation

### Discovered During

Step 4 Validation (2026-06-30)

---

# Medium Priority

## 5. Improve Industry Classification

**Priority:** Medium

### Problem

Industry extraction currently relies primarily on keyword matching.

As more articles are processed, this approach may produce incorrect classifications.

### Expected Behaviour

Increase extraction accuracy while remaining deterministic.

Avoid inferring industries that are not explicitly stated.

### Status

Deferred

---

## 6. Improve Company Description Extraction

**Priority:** Medium

### Problem

Company descriptions may contain unnecessary marketing language or repeated phrases.

### Expected Behaviour

Return concise, structured business descriptions suitable for storage.

### Status

Deferred

---

## 7. Improve Valuation Extraction

**Priority:** Medium

### Problem

Valuation information is relatively uncommon and may appear in multiple formats.

### Expected Behaviour

Expand valuation pattern coverage while avoiding false positives.

### Status

Deferred

---

# Low Priority

## 8. Improve Extraction Metrics

**Priority:** Low

### Problem

Current validation reports only basic extraction statistics.

### Expected Behaviour

Track additional metrics such as:

- Stage 2 success rate
- Fields improved by Stage 2
- Per-field extraction accuracy
- Average extraction completeness over time

### Status

Future Enhancement

---

# Notes

These improvements are intentionally iterative.

The current parser architecture is considered stable. Future work should focus on improving extraction quality through better deterministic rules and broader pattern coverage rather than architectural changes.