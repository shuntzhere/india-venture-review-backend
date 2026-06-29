# Fetches articles from the Entrackr RSS feed and filters for funding announcements.

import re
import requests
import feedparser
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

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
# traffic easy to identify in server logs if Entrackr ever contacts us.
HTTP_HEADERS = {
    "User-Agent": "IndiaVentureReview/1.0 (+https://github.com/shuntzhere/india-venture-review)"
}

# ---------------------------------------------------------------------------
# Funding keyword list
# ---------------------------------------------------------------------------
# Matched against article titles using whole-word matching (not substring).
# See is_funding_article() for the matching strategy.
# Add or remove keywords here to tune filtering without touching any other code.
#
# Deliberately excluded:
#   "investment" — too broad; matches "investment banking", "divestment", etc.
#                  Actual funding events using this word almost always also
#                  contain "raises", "funding", or "round", which are covered.
#                  Keeping it caused false positives in validation (e.g. Zerodha
#                  seeking a merchant banking licence was accepted incorrectly).

FUNDING_KEYWORDS = [
    "raises",
    "funding",
    "secures",
    "bags",        # common in Indian startup reporting ("bags Rs 10 Cr seed round")
    "round",
    "backed",
    "Series",
    "Seed",
    "Pre-Seed",
    "venture",
]


# ---------------------------------------------------------------------------
# HTML text extractor
# ---------------------------------------------------------------------------
# RSS feed content often contains HTML markup. We clean it here, before
# returning raw_content, so the parser in Step 4 receives plain text and
# does not need to duplicate this logic.
#
# Uses Python's built-in html.parser rather than regex. Regex-based HTML
# stripping is fragile: it breaks on nested tags, self-closing elements,
# and HTML entities. A proper parser handles all of these correctly.

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
# Funding classification function
# ---------------------------------------------------------------------------
# Kept as a self-contained function so it can be replaced by an AI classifier,
# NLP model, or rule-based scorer in a future milestone without touching the
# surrounding ingestion pipeline. The rest of fetch_entrackr_articles() calls
# this function and uses only its return value — it has no knowledge of how
# the classification works internally.

def is_funding_article(title):
    """
    Determine whether an article title is a funding announcement.

    Uses whole-word matching via regex word boundaries rather than simple
    substring matching. This prevents false positives inside unrelated words:
    for example, "round" will not match "surrounding" or "background",
    and "backed" will not match "setback".

    re.escape() is used on each keyword so that special characters (e.g. the
    hyphen in "Pre-Seed") are treated as literals rather than regex operators.

    Args:
        title (str): The article title to evaluate.

    Returns:
        (True, matched_keyword)  if a funding keyword is found
        (False, None)            if no keyword matches
    """
    for keyword in FUNDING_KEYWORDS:
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, title, re.IGNORECASE):
            return True, keyword
    return False, None


# ---------------------------------------------------------------------------
# Main ingestion function
# ---------------------------------------------------------------------------

def fetch_entrackr_articles(verbose=False):
    """
    Fetch articles from the Entrackr RSS feed published in the last 24 hours
    and return those that match at least one funding keyword.

    Args:
        verbose (bool): If True, print per-article accept/reject status and a
                        validation summary at the end. Intended for development
                        use only — not part of the production pipeline.

    Returns:
        List of dicts, each containing:
            article_title
            article_url
            article_publication_date  (ISO format string: YYYY-MM-DD)
            source_name
            raw_content               (plain text, HTML stripped)
        Returns an empty list if the feed is unavailable or no articles match.
    """

    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

    # Counters used only for the verbose validation summary.
    count_total = 0
    count_accepted = 0
    count_rejected = 0
    count_too_old = 0
    count_no_date = 0

    # ------------------------------------------------------------------
    # Step 1: Fetch the raw RSS feed using requests.
    # Using requests (rather than letting feedparser fetch directly) gives
    # us reliable timeout control. feedparser's built-in HTTP client does
    # not support setting a request timeout, which would cause the scraper
    # to hang indefinitely if Entrackr is slow or unresponsive.
    # ------------------------------------------------------------------
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
        return []

    # ------------------------------------------------------------------
    # Step 2: Parse the fetched content with feedparser.
    # ------------------------------------------------------------------
    feed = feedparser.parse(response.content)

    if not feed.entries:
        if verbose:
            print("[INFO] RSS feed returned no entries.")
        return []

    # ------------------------------------------------------------------
    # Step 3: Filter, clean, and collect matching articles.
    # ------------------------------------------------------------------
    results = []
    seen_urls = set()  # tracks URLs already added; guards against duplicate RSS entries

    for entry in feed.entries:
        count_total += 1
        title = entry.get("title", "").strip()
        url = entry.get("link", "").strip()

        # Skip entries with no publication date — we cannot place them in time.
        published_parsed = entry.get("published_parsed")
        if not published_parsed:
            count_no_date += 1
            if verbose:
                print(f"[SKIP] No publication date — {title}")
            continue

        # Convert published_parsed (a UTC time.struct_time) to an aware datetime.
        pub_datetime = datetime(*published_parsed[:6], tzinfo=timezone.utc)

        # Skip articles older than the lookback window.
        if pub_datetime < cutoff:
            count_too_old += 1
            if verbose:
                print(f"[SKIP] Too old ({pub_datetime.date()}) — {title}")
            continue

        # Check the title against the funding keyword list.
        is_funding, matched_keyword = is_funding_article(title)

        if not is_funding:
            count_rejected += 1
            if verbose:
                print(f"[REJECTED] No funding keyword detected — {title}")
            continue

        # Deduplicate by URL. RSS feeds occasionally repeat entries (e.g. on
        # updates or feed regeneration). Only the first occurrence is kept.
        if url in seen_urls:
            if verbose:
                print(f"[SKIP] Duplicate URL — {title}")
            continue
        seen_urls.add(url)

        # Extract the best available content from the feed entry,
        # then strip HTML to deliver clean text to the parser.
        raw_html = ""
        if hasattr(entry, "content") and entry.content:
            raw_html = entry.content[0].get("value", "")
        elif entry.get("summary"):
            raw_html = entry.get("summary", "")

        results.append({
            "article_title": title,
            "article_url": url,
            "article_publication_date": pub_datetime.date().isoformat(),
            "source_name": SOURCE_NAME,
            "raw_content": _strip_html(raw_html),
        })

        count_accepted += 1
        if verbose:
            print(f"[ACCEPTED] Matched keyword '{matched_keyword}' — {title}")

    # ------------------------------------------------------------------
    # Validation summary
    # ------------------------------------------------------------------
    if verbose:
        print(f"\n{'─' * 60}")
        print(f"Validation summary")
        print(f"{'─' * 60}")
        print(f"  RSS entries processed     : {count_total}")
        print(f"  Funding articles accepted : {count_accepted}")
        print(f"  Articles rejected         : {count_rejected}")
        print(f"  Skipped (too old)         : {count_too_old}")
        print(f"  Skipped (no date)         : {count_no_date}")
        print(f"{'─' * 60}")

    return results


# ---------------------------------------------------------------------------
# Manual validation entry point
# ---------------------------------------------------------------------------
# Run this file directly to validate the ingestion pipeline:
#   python3 -m scraper.entrackr

if __name__ == "__main__":
    print(f"Fetching articles from: {ENTRACKR_RSS_URL}")
    print(f"Lookback window: {LOOKBACK_HOURS} hours\n")

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
