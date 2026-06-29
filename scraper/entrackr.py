# Fetches articles from the Entrackr RSS feed and filters for funding announcements.

import requests
import feedparser
from datetime import datetime, timedelta, timezone

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

# ---------------------------------------------------------------------------
# Funding keyword list
# ---------------------------------------------------------------------------
# These keywords are matched against article titles (case-insensitive).
# If none match, the article is skipped.
# Add or remove keywords here to refine filtering without changing any
# other part of the module.

FUNDING_KEYWORDS = [
    "raises",
    "funding",
    "secures",
    "investment",
    "round",
    "backed",
    "Series",
    "Seed",
    "Pre-Seed",
    "venture",
]


# ---------------------------------------------------------------------------
# Filtering function
# ---------------------------------------------------------------------------
# Isolated here so it can be swapped for an AI or NLP classifier in a
# future milestone without touching the rest of the ingestion pipeline.

def is_funding_article(title):
    """
    Check whether an article title contains at least one funding keyword.

    Returns:
        (True, matched_keyword)  if a keyword is found
        (False, None)            if no keyword matches
    """
    title_lower = title.lower()
    for keyword in FUNDING_KEYWORDS:
        if keyword.lower() in title_lower:
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
        verbose (bool): If True, print accept/reject status for each article.
                        Intended for development validation only.

    Returns:
        List of dicts, each containing:
            article_title
            article_url
            article_publication_date  (ISO format string: YYYY-MM-DD)
            source_name
            raw_content
        Returns an empty list if the feed is unavailable or no articles match.
    """

    # Calculate the cutoff datetime — articles older than this are skipped.
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

    # ------------------------------------------------------------------
    # Step 1: Fetch the raw RSS feed content via requests.
    # Using requests here (rather than letting feedparser fetch directly)
    # gives us reliable timeout control. feedparser's own HTTP client
    # does not support setting a timeout.
    # ------------------------------------------------------------------
    try:
        response = requests.get(ENTRACKR_RSS_URL, timeout=FEED_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as e:
        if verbose:
            print(f"[ERROR] Could not fetch RSS feed: {e}")
        return []

    # ------------------------------------------------------------------
    # Step 2: Parse the raw feed content with feedparser.
    # ------------------------------------------------------------------
    feed = feedparser.parse(response.content)

    if not feed.entries:
        if verbose:
            print("[INFO] RSS feed returned no entries.")
        return []

    # ------------------------------------------------------------------
    # Step 3: Filter and collect matching articles.
    # ------------------------------------------------------------------
    results = []

    for entry in feed.entries:
        title = entry.get("title", "").strip()
        url = entry.get("link", "").strip()

        # Skip entries with no publication date — we cannot place them in time.
        published_parsed = entry.get("published_parsed")
        if not published_parsed:
            if verbose:
                print(f"[SKIP] No publication date — {title}")
            continue

        # Convert published_parsed (a UTC time.struct_time) to an aware datetime.
        pub_datetime = datetime(*published_parsed[:6], tzinfo=timezone.utc)

        # Skip articles older than the lookback window.
        if pub_datetime < cutoff:
            if verbose:
                print(f"[SKIP] Too old ({pub_datetime.date()}) — {title}")
            continue

        # Check the title against the funding keyword list.
        is_funding, matched_keyword = is_funding_article(title)

        if not is_funding:
            if verbose:
                print(f"[REJECTED] No funding keyword detected — {title}")
            continue

        # Extract the best available content from the feed entry.
        # RSS feeds vary: some provide full content, others only a summary.
        raw_content = ""
        if hasattr(entry, "content") and entry.content:
            raw_content = entry.content[0].get("value", "")
        elif entry.get("summary"):
            raw_content = entry.get("summary", "")

        results.append({
            "article_title": title,
            "article_url": url,
            "article_publication_date": pub_datetime.date().isoformat(),
            "source_name": SOURCE_NAME,
            "raw_content": raw_content,
        })

        if verbose:
            print(f"[ACCEPTED] Matched keyword '{matched_keyword}' — {title}")

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
    print(f"Total funding articles found: {len(articles)}")
    print(f"{'─' * 60}")

    for i, article in enumerate(articles, 1):
        print(f"\n[{i}] {article['article_title']}")
        print(f"    URL    : {article['article_url']}")
        print(f"    Date   : {article['article_publication_date']}")
        print(f"    Source : {article['source_name']}")
        content_preview = article['raw_content'][:120].replace("\n", " ")
        print(f"    Preview: {content_preview}...")
