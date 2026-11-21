# Fetches articles from the Entrackr RSS feed and filters for funding announcements
# using a multi-signal weighted classifier.

import re
import requests
import feedparser
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import List, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Entrackr's RSS feed URL (discovered from the site's <link rel="alternate"> tag).
ENTRACKR_RSS_URL = "https://entrackr.com/rss"

# Source label attached to every article returned by this module.
SOURCE_NAME = "Entrackr"

# How far back to look for articles (in hours).
LOOKBACK_HOURS = 24

# Seconds to wait for the RSS feed before giving up.
FEED_TIMEOUT_SECONDS = 10

# Identifies this scraper to the server.
# Including a User-Agent is good HTTP client practice: some servers treat
# unidentified requests less reliably, and a descriptive label makes our
# traffic identifiable in server logs.
HTTP_HEADERS = {
    "User-Agent": "IndiaVentureReview/1.0 (+https://github.com/shuntzhere/india-venture-review-backend)"
}


@dataclass
class FetchResult:
    """Outcome of one RSS source attempt, including an explicit failure state."""

    source_name: str
    articles: List[dict]
    entries_fetched: int
    error: Optional[str] = None

# ---------------------------------------------------------------------------
# Signal 1 — Funding keywords
# ---------------------------------------------------------------------------
# Matched against article titles using whole-word regex matching.
# Deliberately excluded: "investment" — too broad; matched "investment banking"
# and corporate deals in Step 3.1 validation (see Step 3.1 notes).

FUNDING_KEYWORDS = [
    "raises",
    "funding",
    "secures",
    "bags",        # common in Indian startup reporting ("bags Rs 10 Cr seed round")
    "round",
    "Series",
    "Seed",
    "Pre-Seed",
    "venture",
]

# A completed strategic investment can be reported without the usual funding
# verbs. Keep this title structure strict so generic investment commentary is
# not admitted as startup funding.
COMPLETED_STRATEGIC_INVESTMENT_PATTERN = (
    r"^[A-Z][A-Za-z0-9& .'-]{1,60}?\s+\bcloses\b\s+"
    r"[A-Z][A-Za-z0-9& .'-]{1,80}['’]s\s+"
    r"(?:\$|Rs\.?|₹|USD|INR)\s*[\d,]+(?:\.\d+)?\s*"
    r"(?:Mn|Bn|M|B|Cr|crore|million|billion)?\s+strategic\s+investment\b"
)

# ---------------------------------------------------------------------------
# Signal 2 — Funding amount patterns
# ---------------------------------------------------------------------------
# Covers the major currency formats used in Indian startup reporting.
# Applied to both title and the first 500 characters of article content.
# "undisclosed" is intentionally not treated as a funding amount — an
# undisclosed amount provides no evidence of a specific transaction.

FUNDING_AMOUNT_PATTERNS = [
    # Dollar amounts: $3.2 Mn, $500K, $5M, $5 million
    r'\$\s*[\d,]+(?:\.\d+)?\s*(?:Mn|Bn|M|B|K|million|billion|thousand)?',
    # Rupee with prefix: Rs 150 Cr, Rs. 10 crore, Rs 5 Lakh
    r'\bRs\.?\s*[\d,]+(?:\.\d+)?\s*(?:Cr|crore|Mn|Lakh|lakh|million)?\b',
    # Unicode rupee symbol: ₹50 crore
    r'₹\s*[\d,]+(?:\.\d+)?\s*(?:Cr|crore|Mn|Lakh|lakh|million)?',
    # Currency code prefix: USD 5 million, INR 10 crore
    r'\b(?:USD|INR)\s*[\d,]+(?:\.\d+)?\s*(?:Mn|M|Bn|B|K|million|billion|crore|Cr|Lakh|lakh)?\b',
]

# ---------------------------------------------------------------------------
# Signal 3 — Investor phrase patterns
# ---------------------------------------------------------------------------
# Phrases that indicate active investor participation in a funding event.
# Applied to both title and the first 500 characters of article content.

INVESTOR_PHRASE_PATTERNS = [
    r'\bled\s+by\b',
    r'\bbacked\s+by\b',
    r'\bfrom\s+investors\b',
    r'\bparticipated\s+by\b',
]

# These are financial events, but not startup/company funding rounds. Keep the
# exclusions structural so they do not depend on individual company names.
#
# They intentionally apply to the headline only. Article bodies routinely
# mention prior IPOs, acquisitions, and fund closes as context, which must not
# change the event represented by the article itself.
NON_COMPANY_FUNDING_PATTERNS = [
    (r'\b(?:weekly funding report|funding and acquisitions.*this week)\b',
     "funding roundup"),
    (r'\b(?:raises?|raised)\b[^.]{0,100}\b(?:price\s+)?target\s+to\b',
     "analyst price-target change"),
    (r'\b(?:ventures|capital|partners|asset(?:\s+management)?)\b[^.]{0,100}'
     r'\bannounces?\s+(?:its\s+)?(?:first|final)\s+close\b',
     "VC or fund-manager fundraise"),
    (r'\b(?:launches?|launched)\b[^.]{0,100}\b(?:venture\s+)?fund\b',
     "VC or fund-manager fundraise"),
    (r'\b(?:raises?|raised|closes?|closed)\b[^.]{0,100}\bcorpus\b',
     "VC or fund-manager fundraise"),
    (r'\b(?:closes?|closed)\b[^.]{0,100}\bfund\b',
     "VC or fund-manager fundraise"),
    (r'\b(?:raises?|raised)\s+(?:\$|Rs\.?|₹|USD|INR)\s*[\d,]+(?:\.\d+)?\s*'
     r'(?:Mn|Bn|M|B|Cr|crore|million|billion)?\s+(?!from\b|led\b|backed\b)'
     r'(?:[A-Za-z-]+\s+){0,4}fund\b', "VC or fund-manager fundraise"),
    (r'\b(?:closes?|closed)\s+[^.]{0,100}\b(?:I|II|III|IV|V)\b',
     "venture-fund close"),
    (r'\bfund\s+(?:I|II|III|IV|V)\b[^.]{0,120}'
     r'\b(?:secures?|raises?|closes?|closed)\b[^.]{0,120}'
     r'\b(?:first|final)\s+close\b',
     "venture-fund close"),
    # A bare "IPO" is often only context for a private round ("raises ahead
    # of IPO"). Restrict this exclusion to an actual public-market mechanism.
    (r'\b(?:files?|filed)\s+(?:a\s+)?(?:drhp|udrhp|draft\s+red\s+herring\s+prospectus)\b'
     r'|\b(?:fresh issue|offer for sale|\bofs\b|anchor investors?)\b'
     r'|\b(?:ipo|initial\s+public\s+offering)\b[^.]{0,100}\b(?:subscription|subscribed|listing|lists?|listed|debut|price\s+band|allotment|opens?|closes?|fresh issue|offer for sale|to\s+raise|raises?)\b'
     r'|\b(?:shares?|stock)\b[^.]{0,50}\b(?:debut|listing|lists?|listed)\b'
     r'|\b(?:debut|listing|lists?|listed)\b[^.]{0,50}\b(?:premium|shares?|stock)\b',
     "IPO or public-markets fundraising"),
    (r'\b(?:acquisition|acquires?|acquired|block deals?|secondary stake|stake sale|offload(?:s|ed)?)\b',
     "acquisition or secondary-market transaction"),
    (r'\b(?:sells?|to\s+sell)\b.{0,100}\bstake\b',
     "acquisition or secondary-market transaction"),
    (r'\b(?:gst\s+council|tax|prosecution|penalty|arrest)\b[^.]{0,120}'
     r'\b(?:threshold|powers?|provisions?|compliance)\b'
     r'|\braises?\b[^.]{0,80}\bthreshold\s+to\s+'
     r'(?:\$|Rs\.?|₹|USD|INR)\s*[\d,]+',
     "regulatory or legal threshold"),
]

# ---------------------------------------------------------------------------
# Signal registry and classifier threshold
# ---------------------------------------------------------------------------
# Each entry is (signal_name, detector_function, weight).
#
# To add a new signal: implement a detector function and append it here.
# Nothing else in the module needs to change.
#
# Weight and threshold rationale:
#   funding_keyword  +3  Sole sufficient signal. A title containing "raises",
#                        "bags", "round" etc. is almost always a funding event.
#   funding_amount   +2  Strong corroborating evidence, but not sufficient alone.
#                        A revenue article ("posts $781 Mn revenue") has an amount
#                        but no keyword — score 2 falls below threshold 3, so it is
#                        correctly rejected. This avoids the main false-positive class.
#   investor_phrase  +1  Weak corroborating signal. "led by" alone is not enough.
#   threshold        3   Keyword alone is sufficient (3 ≥ 3). Amount alone is not
#                        (2 < 3). Investor phrase alone is not (1 < 3). Two weaker
#                        signals together (amount + investor = 3) are sufficient,
#                        which is intentional: a non-keyword article that names both
#                        an amount and an investor is very likely a funding event.

ACCEPTANCE_THRESHOLD = 3

# ---------------------------------------------------------------------------
# HTML text extractor
# ---------------------------------------------------------------------------
# RSS feed content often contains HTML markup. We clean it here so the parser
# in Step 4 receives plain text and does not need to duplicate this logic.
# Uses Python's built-in html.parser rather than regex — regex-based HTML
# stripping breaks on nested tags, self-closing elements, and HTML entities.

class _HTMLTextExtractor(HTMLParser):
    """Collects all text nodes from an HTML string, discarding tags."""

    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self._parts.append(text)

    def get_text(self):
        return " ".join(self._parts)


def _strip_html(raw_html):
    """Return the plain text content of an HTML string. Safe on empty input."""
    if not raw_html:
        return ""
    extractor = _HTMLTextExtractor()
    extractor.feed(raw_html)
    return extractor.get_text()


# ---------------------------------------------------------------------------
# Signal detectors
# ---------------------------------------------------------------------------
# Each detector is a pure function: (title, content) → bool.
# Detectors are completely independent — changing one does not affect others
# or the classification engine.

def detect_funding_keyword(title, content):
    """Signal 1: Return True if the article title contains a funding keyword."""
    if re.search(COMPLETED_STRATEGIC_INVESTMENT_PATTERN, title):
        return True
    for keyword in FUNDING_KEYWORDS:
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, title, re.IGNORECASE):
            return True
    return False


def detect_funding_amount(title, content):
    """Signal 2: Return True if a funding amount pattern appears in title or content."""
    text = title + " " + content[:500]
    for pattern in FUNDING_AMOUNT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def detect_investor_phrase(title, content):
    """Signal 3: Return True if an investor phrase appears in title or content."""
    text = title + " " + content[:500]
    for pattern in INVESTOR_PHRASE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


# ---------------------------------------------------------------------------
# Signal registry
# ---------------------------------------------------------------------------
# The classifier iterates this list. Order does not affect the outcome —
# scores are summed across all signals regardless of order.

SIGNAL_REGISTRY = [
    ("funding_keyword",  detect_funding_keyword,  3),
    ("funding_amount",   detect_funding_amount,   2),
    ("investor_phrase",  detect_investor_phrase,  1),
]


# ---------------------------------------------------------------------------
# Classification engine
# ---------------------------------------------------------------------------

def _confidence_label(score):
    """
    Map a classifier score to a human-readable label.
    Used only in verbose validation output — not in classification logic.
    """
    if score >= 5:
        return "Strong"
    elif score >= ACCEPTANCE_THRESHOLD:
        return "Moderate"
    else:
        return "Weak"


def classify_article(title, content):
    """
    Evaluate an article against all registered signals and return a
    structured classification result.

    Each signal is checked independently. The total score is the sum of the
    weights of all signals that fired. An article is accepted when the score
    meets or exceeds ACCEPTANCE_THRESHOLD.

    This function is the single point of entry for all classification logic.
    Replacing it with an AI or NLP classifier requires no changes to the
    surrounding ingestion pipeline.

    Args:
        title   (str): Article title.
        content (str): Plain-text article content (HTML already stripped).

    Returns:
        dict:
            accepted (bool) — whether the article meets the threshold
            score    (int)  — total weighted score across all signals
            signals  (list) — names of the signals that fired
    """
    for pattern, reason in NON_COMPANY_FUNDING_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return {
                "accepted": False,
                "score": 0,
                "signals": [],
                "rejection_reason": reason,
            }

    score = 0
    matched_signals = []

    for signal_name, detector_fn, weight in SIGNAL_REGISTRY:
        if detector_fn(title, content):
            score += weight
            matched_signals.append(signal_name)

    return {
        "accepted": score >= ACCEPTANCE_THRESHOLD,
        "score": score,
        "signals": matched_signals,
        "rejection_reason": None,
    }


# ---------------------------------------------------------------------------
# Main ingestion function
# ---------------------------------------------------------------------------

def fetch_entrackr_result(verbose=False, *, lookback_hours=LOOKBACK_HOURS):
    """
    Fetch articles from the Entrackr RSS feed published in the last 24 hours
    and return those that pass the funding classifier.

    Args:
        verbose (bool): If True, print per-article classification detail and a
                        validation summary at the end. Intended for development
                        use only — not part of the production pipeline.

    Returns:
        List of dicts, each containing:
            article_title
            article_url
            article_publication_date  (ISO format string: YYYY-MM-DD)
            source_name
            raw_content               (plain text, HTML stripped)
        FetchResult whose error is populated when the source could not be read.
    """

    if not 1 <= lookback_hours <= 168:
        raise ValueError("lookback_hours must be between 1 and 168")
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    count_total    = 0
    count_accepted = 0
    count_rejected = 0
    count_too_old  = 0
    count_no_date  = 0

    # Fetch raw RSS feed using requests for reliable timeout control.
    # feedparser's own HTTP client does not support timeouts.
    try:
        response = requests.get(
            ENTRACKR_RSS_URL,
            headers=HTTP_HEADERS,
            timeout=FEED_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        if verbose:
            print(f"[ERROR] Could not fetch RSS feed: {e}")
        return FetchResult(
            source_name=SOURCE_NAME,
            articles=[],
            entries_fetched=0,
            error=f"Could not fetch RSS feed: {e}",
        )

    feed = feedparser.parse(response.content)

    if not feed.entries:
        if verbose:
            print("[INFO] RSS feed returned no entries.")
        return FetchResult(SOURCE_NAME, [], 0)

    results = []
    seen_urls = set()  # guards against duplicate RSS entries

    for entry in feed.entries:
        count_total += 1
        title = entry.get("title", "").strip()
        url   = entry.get("link",  "").strip()

        # Skip entries with no publication date.
        published_parsed = entry.get("published_parsed")
        if not published_parsed:
            count_no_date += 1
            if verbose:
                print(f"[SKIP] No publication date — {title}")
            continue

        pub_datetime = datetime(*published_parsed[:6], tzinfo=timezone.utc)

        # Skip articles older than the lookback window.
        if pub_datetime < cutoff:
            count_too_old += 1
            if verbose:
                print(f"[SKIP] Too old ({pub_datetime.date()}) — {title}")
            continue

        # Extract and clean content BEFORE classification so that content-based
        # signals (funding_amount, investor_phrase) have plain text to search.
        raw_html = ""
        if hasattr(entry, "content") and entry.content:
            raw_html = entry.content[0].get("value", "")
        elif entry.get("summary"):
            raw_html = entry.get("summary", "")

        content = _strip_html(raw_html)

        # Run the classification engine.
        result     = classify_article(title, content)
        label      = _confidence_label(result["score"])
        signals_str = ", ".join(result["signals"]) if result["signals"] else "none"

        if not result["accepted"]:
            count_rejected += 1
            if verbose:
                print(f"[REJECTED]")
                print(f"  Score   : {result['score']}")
                print(f"  Signals : {signals_str}")
                print(f"  Title   : {title}\n")
            continue

        # Deduplicate by URL. Only the first occurrence of each URL is kept.
        if url in seen_urls:
            if verbose:
                print(f"[SKIP] Duplicate URL — {title}")
            continue
        seen_urls.add(url)

        results.append({
            "article_title":            title,
            "article_url":              url,
            "article_publication_date": pub_datetime.date().isoformat(),
            "source_name":              SOURCE_NAME,
            "raw_content":              content,
            "classification_confidence": label,
        })

        count_accepted += 1
        if verbose:
            print(f"[ACCEPTED — {label}]")
            print(f"  Score   : {result['score']}")
            print(f"  Signals : {signals_str}")
            print(f"  Title   : {title}\n")

    if verbose:
        print(f"{'─' * 60}")
        print(f"Validation summary")
        print(f"{'─' * 60}")
        print(f"  RSS entries processed     : {count_total}")
        print(f"  Funding articles accepted : {count_accepted}")
        print(f"  Articles rejected         : {count_rejected}")
        print(f"  Skipped (too old)         : {count_too_old}")
        print(f"  Skipped (no date)         : {count_no_date}")
        print(f"{'─' * 60}")

    return FetchResult(SOURCE_NAME, results, count_total)


def fetch_entrackr_articles(verbose=False):
    """Return accepted Entrackr articles for legacy local entry points.

    Hosted orchestration must use ``fetch_entrackr_result`` so a source outage
    cannot be mistaken for a legitimate empty feed.
    """
    return fetch_entrackr_result(verbose=verbose).articles


# ---------------------------------------------------------------------------
# Manual validation entry point
# ---------------------------------------------------------------------------
# python3 -m scraper.entrackr

if __name__ == "__main__":
    print(f"Fetching articles from : {ENTRACKR_RSS_URL}")
    print(f"Lookback window        : {LOOKBACK_HOURS} hours")
    print(f"Acceptance threshold   : {ACCEPTANCE_THRESHOLD}\n")

    articles = fetch_entrackr_articles(verbose=True)

    print(f"\n{'─' * 60}")
    print(f"Funding articles returned: {len(articles)}")
    print(f"{'─' * 60}")

    for i, article in enumerate(articles, 1):
        print(f"\n[{i}] {article['article_title']}")
        print(f"    URL    : {article['article_url']}")
        print(f"    Date   : {article['article_publication_date']}")
        print(f"    Source : {article['source_name']}")
        content_preview = article["raw_content"][:120].replace("\n", " ")
        print(f"    Preview: {content_preview}...")
