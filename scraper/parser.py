# Evidence Extraction Engine — Version 1
#
# Transforms a normalized funding article into a structured funding record.
# Operates in two stages: RSS content first, full article only if primary
# business fields are missing after Stage 1.
#
# Architecture:
#   Entrackr adapter  →  normalized article
#   Parser orchestrator coordinates:
#     Stage 1 extraction  (RSS title + content)
#     Stage 2 extraction  (full article, if needed)
#     Evidence merge
#     Output validation
#   Returns: (structured_record, validation_report)

import re
import time
import requests
from html.parser import HTMLParser

try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Seconds to wait between consecutive full-article HTTP requests.
# Introduced only when more than one full article is retrieved in a single run.
FULL_ARTICLE_REQUEST_DELAY_SECONDS = 1

# Timeout for full article HTTP requests.
ARTICLE_TIMEOUT_SECONDS = 10

# HTTP headers for full article retrieval.
HTTP_HEADERS = {
    "User-Agent": "IndiaVentureReview/1.0 (+https://github.com/shuntzhere/india-venture-review)"
}

# Fields from the normalized article that are required before extraction begins.
REQUIRED_ARTICLE_FIELDS = {
    "article_title",
    "article_url",
    "article_publication_date",
    "source_name",
    "raw_content",
}

# Primary business fields — if any of these are missing after Stage 1,
# the orchestrator retrieves the full article (Stage 2).
PRIMARY_FIELDS = {"company_name", "funding_amount", "funding_round", "lead_investors"}

# All business fields the engine attempts to populate.
# Metadata fields (article_title, article_url, etc.) are not counted here
# because they are always available from the normalized article.
BUSINESS_FIELDS = [
    # Company
    "company_name",
    "website",
    "description",
    "industry",
    "business_model",
    "headquarters_city",
    "headquarters_state",
    "headquarters_country",
    "founded_year",
    # Funding
    "funding_amount",
    "currency",
    "funding_round",
    "valuation",
    # Investors
    "lead_investors",
    "participating_investors",
]


# ---------------------------------------------------------------------------
# HTML utilities
# ---------------------------------------------------------------------------

class _HTMLTextExtractor(HTMLParser):
    """Strips HTML tags and returns concatenated text content."""

    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self._parts.append(text)

    def get_text(self):
        return " ".join(self._parts)


def _strip_html_stdlib(raw_html):
    """Return plain text from an HTML string using stdlib. Safe on empty input."""
    if not raw_html:
        return ""
    extractor = _HTMLTextExtractor()
    extractor.feed(raw_html)
    return extractor.get_text()


def _extract_article_text(html):
    """
    Extract the main article body from a full HTML page.

    Uses BeautifulSoup when available to prefer semantic elements (<article>,
    <main>) and remove navigation, scripts, and other noise. Falls back to
    stdlib text stripping when BeautifulSoup is not installed.
    """
    if not html:
        return ""

    if not _BS4_AVAILABLE:
        return _strip_html_stdlib(html)

    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content elements that pollute extracted text.
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()

    # Prefer semantic article/main elements; fall back to body.
    content_el = soup.find("article") or soup.find("main") or soup.find("body")
    if content_el:
        return content_el.get_text(separator=" ", strip=True)
    return soup.get_text(separator=" ", strip=True)


# ---------------------------------------------------------------------------
# Shared extraction utilities
# ---------------------------------------------------------------------------
# Each utility is a pure function. All return None (or a None-containing tuple)
# when no match is found. Utilities are shared across all domain extractors.

# Ordered by specificity — more specific patterns are listed first.
_AMOUNT_PATTERNS = [
    # Dollar amounts: $3.2 Mn, $500K, $5 million
    (r'\$\s*([\d,]+(?:\.\d+)?)\s*(Mn|Bn|M|B|K|million|billion|thousand)?', "USD"),
    # INR with currency code: INR 150 crore
    (r'\bINR\s*([\d,]+(?:\.\d+)?)\s*(Cr|crore|Lakh|lakh|Mn|million)?', "INR"),
    # USD with currency code: USD 5 million
    (r'\bUSD\s*([\d,]+(?:\.\d+)?)\s*(Mn|M|Bn|B|K|million|billion)?', "USD"),
    # Unicode rupee symbol: ₹50 crore
    (r'₹\s*([\d,]+(?:\.\d+)?)\s*(Cr|crore|Lakh|lakh|Mn|million)?', "INR"),
    # Rs prefix: Rs 150 Cr, Rs. 10 crore
    (r'\bRs\.?\s*([\d,]+(?:\.\d+)?)\s*(Cr|crore|Lakh|lakh|Mn|million)?', "INR"),
]

_ROUND_PATTERNS = [
    r'\bPre-?Seed\b',
    r'\bPre-?Series\s+[A-Z]\b',
    r'\bSeries\s+[A-Z]\d*\+?\b',
    r'\bSeed\b',
    r'\bPre-?IPO\b',
    r'\bBridge\b',
    r'\bAngel\b',
    r'\bGrowth\b',
    r'\bDebt\b',
    r'\bGrant\b',
]


def _parse_amount(text):
    """
    Extract the first funding amount from text.
    Returns (amount_float, currency_with_unit) or (None, None).

    The amount is returned as stated in the article (e.g., 3.2 for "$3.2 Mn").
    The currency string includes the denomination unit (e.g., "USD Mn", "INR Cr").
    No unit conversion is performed — that would require assumptions not in the article.
    """
    for pattern, base_currency in _AMOUNT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_num = match.group(1).replace(",", "")
            try:
                amount = float(raw_num)
            except ValueError:
                continue
            unit = (match.group(2) or "").strip()
            currency = f"{base_currency} {unit}".strip() if unit else base_currency
            return amount, currency
    return None, None


def _extract_funding_round(text):
    """Return the first funding round label found in text, or None."""
    for pattern in _ROUND_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def _extract_lead_investors(title, content):
    """
    Return a string of lead investor names following 'led by' or 'backed by'.

    Searches the title first, then the content separately. Searching separately
    rather than concatenating ensures the end-of-string boundary in the title
    prevents the pattern from consuming content that follows the investor name.
    Returns None if no match is found in either.
    """
    # Lookahead stops capture at transition words or sentence boundaries.
    stop = r'(?=\s+(?:through|via|has\b|in\s+a\b|with\s+|and\s+others|to\s+)|\s*[,\.;]|$)'
    patterns = [
        r'\bled\s+by\s+([A-Z][^\.,;\n]+?)' + stop,
        r'\bbacked\s+by\s+([A-Z][^\.,;\n]+?)' + stop,
    ]
    for text in [title, content]:
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
    return None


def _extract_participating_investors(title, content):
    """
    Return a string of participating investor names, or None.
    Looks for 'with participation from' or 'participated by/in' phrases.
    Searches title first, then content.
    """
    patterns = [
        r'\bwith\s+participation\s+(?:from|by)\s+([A-Z][^\.]+)',
        r'\bparticipation\s+(?:from|by)\s+([A-Z][^\.]+)',
        r'\bparticipated\s+(?:in\s+)?(?:by|from)\s+([A-Z][^\.]+)',
    ]
    for text in [title, content]:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    return None


def _extract_valuation(text):
    """
    Extract a post-money valuation from text.
    Looks for 'valued at' or 'valuation of' followed by an amount. Returns float or None.
    """
    # Match 'valued at $X Mn' or 'valuation of Rs X Cr' etc.
    val_match = re.search(
        r'(?:valued?\s+at|valuation\s+of)\s+'
        r'(?:\$|Rs\.?|₹|USD\s*|INR\s*)\s*([\d,]+(?:\.\d+)?)',
        text,
        re.IGNORECASE,
    )
    if val_match:
        raw_val = val_match.group(1).replace(",", "")
        try:
            return float(raw_val)
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# Domain extractor: Company
# ---------------------------------------------------------------------------

# Sector keywords used to identify the company's industry from article text.
_SECTOR_MAP = {
    "Fintech":     ["fintech", "payment", "lending", "insurtech", "wealth management", "neobank"],
    "Edtech":      ["edtech", "education", "e-learning", "upskill", "tutoring"],
    "Healthtech":  ["healthtech", "health", "medtech", "healthcare", "telemedicine", "pharma"],
    "Ecommerce":   ["ecommerce", "e-commerce", "d2c", "direct-to-consumer", "retail marketplace"],
    "Logistics":   ["logistics", "supply chain", "last-mile", "warehousing", "shipping"],
    "SaaS":        ["saas", "b2b software", "enterprise software", "cloud platform"],
    "Agritech":    ["agritech", "agriculture", "farming", "crop", "agri"],
    "Proptech":    ["proptech", "real estate", "property", "housing"],
    "Deeptech":    ["deeptech", "artificial intelligence", "machine learning", "robotics"],
    "Cleantech":   ["cleantech", "ev", "electric vehicle", "solar", "clean energy", "climate"],
    "Gaming":      ["gaming", "esports", "game studio"],
    "Travel":      ["travel", "hospitality", "hotel", "tourism", "homestay"],
    "Foodtech":    ["foodtech", "quick commerce", "food delivery", "restaurant tech"],
}

# Verbs that appear directly after the company name in funding headlines.
# These are the split points used to isolate the company name.
_FUNDING_VERBS = [
    "raises", "raised", "secures", "secured", "bags", "bagged",
    "closes", "closed", "gets", "received", "receives", "lands", "landed",
]

# Patterns for investor-led titles where the funded company appears after the
# investor's action rather than before a funding verb.
# Examples:
#   "Boundless Ventures leads pre-seed round in Lytmus AI"
#   "Yash Raj Films makes strategic investment in Rusk Media"
# Each pattern captures the company name in group 1.
# [A-Z] anchors the capture to an uppercase-starting word — no re.IGNORECASE
# is used so that the company name is not confused with lowercase prepositions.
_INVESTOR_LED_PATTERNS = [
    # "X leads [round description] in/for Y"
    r'\bleads\s+.+?\s+(?:in|for)\s+([A-Z][\w\s\.]+?)(?:\s*$|[,\.])',
    # "X makes [type] investment in Y"
    r'\bmakes\s+.+?\binvestment\s+in\s+([A-Z][\w\s\.]+?)(?:\s*$|[,\.])',
    # "X backs Y"
    r'\bbacks\s+([A-Z][\w\s\.]+?)(?:\s*$|[,\.])',
    # "X invests in Y"
    r'\binvests\s+in\s+([A-Z][\w\s\.]+?)(?:\s*$|[,\.])',
    # "X puts [amount] in Y"
    r'\bputs\s+.+?\s+in\s+([A-Z][\w\s\.]+?)(?:\s*$|[,\.])',
]

# Descriptor prefixes that precede the company name and should be stripped.
_DESCRIPTOR_PREFIX = re.compile(
    r'^(?:'
    r'(?:an?\s+)?(?:indian\s+)?'
    r'(?:fintech|edtech|healthtech|agritech|proptech|saas|deeptech|cleantech|'
    r'logistics|ecommerce|e-commerce|foodtech|gaming|travel|'
    r'ai|b2b|d2c|ev|electric\s+vehicle)\s+)?'
    r'(?:startup|company|firm|platform|app|brand|unicorn|venture|'
    r'mumbai-based|bangalore-based|bengaluru-based|delhi-based|'
    r'hyderabad-based|pune-based|chennai-based|india-based|'
    r'gurugram-based|noida-based|kolkata-based)\s+',
    re.IGNORECASE,
)


def _extract_company_name(title):
    """
    Extract the company name from an article title.

    Tries two strategies in order:
    1. Company-led titles — "CompanyX raises/secures/bags..."
       Split before the funding verb; the subject is the company.
    2. Investor-led titles — "InvestorX leads round in CompanyY"
       Extract the company name from after the investor action phrase.

    Returns None if neither strategy produces a reliable result.
    Only explicit title structure is used — no inference or prior knowledge.
    """
    # --- Strategy 1: company-led titles ---
    for verb in _FUNDING_VERBS:
        pattern = r'^(.+?)\s+\b' + re.escape(verb) + r'\b'
        match = re.match(pattern, title, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            # Strip leading location-based prefixes: "Mumbai-based", "Bengaluru-based"
            candidate = re.sub(r'^[A-Za-z]+-based\s+', '', candidate).strip()
            # Strip any prefix ending with a company-type descriptor word
            # (e.g. "Healthcare startup", "AI data infrastructure startup",
            #  "Fintech firm", "Edtech platform"). Non-greedy so only the first
            # occurrence is consumed, leaving the company name intact.
            candidate = re.sub(
                r'^.*?\b(?:startup|company|firm|platform|app|brand|unicorn)\b\s+',
                '',
                candidate,
                flags=re.IGNORECASE,
            ).strip()
            if 2 <= len(candidate) <= 60:
                return candidate

    # --- Strategy 2: investor-led titles ---
    # The funded company appears after the investor's action phrase.
    for pattern in _INVESTOR_LED_PATTERNS:
        match = re.search(pattern, title)
        if match:
            candidate = match.group(1).strip()
            if 2 <= len(candidate) <= 60:
                return candidate

    return None


def _extract_description(title, content):
    """
    Extract a brief company description using the appositive pattern:
    'CompanyName, a/an [description phrase], ...'
    Returns None if no clear description phrase is found.
    """
    # Look for a comma-delimited phrase beginning with 'a' or 'an'
    match = re.search(
        r',\s+(a|an)\s+([^,]{10,120}),',
        content,
        re.IGNORECASE,
    )
    if match:
        phrase = match.group(2).strip()
        # Reject phrases that look like dates or numbers rather than descriptions
        if not re.match(r'^[\d\s]+$', phrase):
            return f"A {phrase}"
    return None


def _extract_industry(title, content):
    """Return the best-matching industry label based on keyword presence, or None."""
    text = (title + " " + content[:1000]).lower()
    for industry, keywords in _SECTOR_MAP.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', text):
                return industry
    return None


def _extract_headquarters(content):
    """
    Extract headquarters city from patterns like 'based in Mumbai' or
    'headquartered in Bengaluru'. Returns (city, state, country).
    Country defaults to 'India' when a city is found without further context.
    All three may be None.
    """
    city = None
    state = None
    country = None

    match = re.search(
        r'\b(?:based|headquartered|founded)\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        content,
    )
    if match:
        city = match.group(1).strip()
        country = "India"

    return city, state, country


def _extract_founded_year(content):
    """
    Extract founding year from explicit 'founded in YYYY' patterns.
    Returns int or None.
    """
    match = re.search(r'\bfounded\s+in\s+(20\d{2}|19\d{2})\b', content, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _extract_website(content):
    """
    Extract a website URL explicitly stated in the article body.
    Returns a normalised lowercase domain string, or None.
    """
    match = re.search(
        r'\b((?:www\.)?[a-z0-9-]+\.(?:com|in|io|co\.in|org|net|ai))\b',
        content,
        re.IGNORECASE,
    )
    if match:
        return match.group(0).lower()
    return None


def extract_company_fields(title, content):
    """
    Extract all company-related business fields from the article.
    Returns a dict. Every field is present; unavailable fields are None.
    """
    city, state, country = _extract_headquarters(content)
    return {
        "company_name":         _extract_company_name(title),
        "website":              _extract_website(content),
        "description":          _extract_description(title, content),
        "industry":             _extract_industry(title, content),
        "business_model":       None,   # not reliably deterministic from headlines
        "headquarters_city":    city,
        "headquarters_state":   state,
        "headquarters_country": country,
        "founded_year":         _extract_founded_year(content),
    }


# ---------------------------------------------------------------------------
# Domain extractor: Funding
# ---------------------------------------------------------------------------

def extract_funding_fields(title, content):
    """
    Extract all funding-related business fields from the article.
    Returns a dict. Every field is present; unavailable fields are None.
    """
    # Try title first (usually the most structured source), then content.
    amount, currency = _parse_amount(title)
    if amount is None:
        amount, currency = _parse_amount(content)

    return {
        "funding_amount": amount,
        "currency":       currency,
        "funding_round":  _extract_funding_round(title + " " + content),
        "valuation":      _extract_valuation(content),
    }


# ---------------------------------------------------------------------------
# Domain extractor: Investors
# ---------------------------------------------------------------------------

def extract_investor_fields(title, content):
    """
    Extract lead and participating investor information from the article.
    Returns a dict. Every field is present; unavailable fields are None.
    """
    return {
        "lead_investors":          _extract_lead_investors(title, content),
        "participating_investors": _extract_participating_investors(title, content),
    }


# ---------------------------------------------------------------------------
# Domain extractor: Metadata
# ---------------------------------------------------------------------------

def extract_metadata_fields(normalized_article):
    """
    Pass through article metadata directly from the normalized article.
    Metadata is always available; no extraction logic is applied.
    """
    return {
        "article_title":             normalized_article.get("article_title", ""),
        "article_url":               normalized_article.get("article_url", ""),
        "article_publication_date":  normalized_article.get("article_publication_date", ""),
        "source_name":               normalized_article.get("source_name", ""),
        "classification_confidence": normalized_article.get("classification_confidence"),
    }


# ---------------------------------------------------------------------------
# Evidence merge
# ---------------------------------------------------------------------------

def _merge_evidence(base, update):
    """
    Merge Stage 2 evidence into the Stage 1 record.
    Existing non-None values in base are always preserved.
    Only None fields in base are populated from update.
    Verified evidence is never discarded.
    """
    merged = dict(base)
    for key, value in update.items():
        if merged.get(key) is None and value is not None:
            merged[key] = value
    return merged


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def _validate_input(normalized_article):
    """
    Verify the normalized article satisfies the minimum contract before extraction.
    Returns a list of issue strings. Empty list means the article is valid.
    """
    issues = []
    for field in REQUIRED_ARTICLE_FIELDS:
        if not normalized_article.get(field):
            issues.append(f"Missing required field: {field}")
    return issues


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------

def _validate_output(record):
    """
    Verify the structured record is well-formed before it is returned.
    Returns a list of issue strings. Empty list means the record is valid.

    This validates structure and type consistency — not business correctness.
    """
    issues = []
    if not record.get("article_url"):
        issues.append("article_url is missing — record cannot be identified downstream")
    if not record.get("source_name"):
        issues.append("source_name is missing")
    if not record.get("article_publication_date"):
        issues.append("article_publication_date is missing")
    if record.get("funding_amount") is not None:
        if not isinstance(record["funding_amount"], (int, float)):
            issues.append("funding_amount is not numeric")
    if record.get("founded_year") is not None:
        if not isinstance(record["founded_year"], int):
            issues.append("founded_year is not an integer")
    return issues


# ---------------------------------------------------------------------------
# Validation report
# ---------------------------------------------------------------------------

def _build_validation_report(
    normalized_article,
    record,
    full_article_retrieved,
    input_issues,
    output_issues,
    retrieval_error,
):
    """
    Build a structured validation report for the human curator.

    The report answers three business questions:
      - Was the article successfully processed?
      - What information was extracted?
      - Does this article require manual review?

    The report is separate from the structured record and is never persisted.
    """
    missing = [f for f in BUSINESS_FIELDS if record.get(f) is None]
    extracted_count = len(BUSINESS_FIELDS) - len(missing)

    # Confidence reflects how many primary business fields were extracted.
    primary_found = sum(
        record.get(f) is not None for f in PRIMARY_FIELDS
    )
    if primary_found == 4:
        confidence = "Strong"
    elif primary_found >= 2:
        confidence = "Moderate"
    else:
        confidence = "Weak"

    evidence_source = "RSS + Full Article" if full_article_retrieved else "RSS"

    # Manual review is recommended when important information is unavailable
    # or when the pipeline encountered unexpected behaviour.
    review_reasons = []
    if record.get("company_name") is None:
        review_reasons.append("Company name could not be extracted")
    if record.get("funding_amount") is None:
        review_reasons.append("Funding amount could not be extracted")
    if record.get("funding_round") is None:
        review_reasons.append("Funding round could not be determined")
    if retrieval_error:
        review_reasons.append(f"Full article retrieval failed: {retrieval_error}")
    for issue in output_issues:
        review_reasons.append(issue)

    if not record.get("article_url"):
        extraction_status = "failed"
    elif missing:
        extraction_status = "partial"
    else:
        extraction_status = "success"

    return {
        "article_title":          normalized_article.get("article_title", ""),
        "extraction_status":      extraction_status,
        "confidence":             confidence,
        "evidence_source":        evidence_source,
        "full_article_retrieved": full_article_retrieved,
        "fields_extracted":       extracted_count,
        "total_fields":           len(BUSINESS_FIELDS),
        "missing_fields":         missing,
        "requires_manual_review": len(review_reasons) > 0,
        "review_reasons":         review_reasons,
        "errors":                 input_issues + output_issues,
    }


# ---------------------------------------------------------------------------
# Full article retrieval
# ---------------------------------------------------------------------------

def _fetch_full_article(url):
    """
    Download a full article page and return its main text content.
    Returns None on any network or HTTP error.
    """
    try:
        response = requests.get(
            url,
            headers=HTTP_HEADERS,
            timeout=ARTICLE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return _extract_article_text(response.text)
    except requests.RequestException:
        return None


# ---------------------------------------------------------------------------
# Parser orchestrator
# ---------------------------------------------------------------------------

def _needs_stage2(record):
    """Return True if any primary business field is missing after Stage 1."""
    return any(record.get(f) is None for f in PRIMARY_FIELDS)


def process_article(normalized_article, request_delay=None):
    """
    Transform one normalized article into one structured funding record.

    Processing lifecycle:
      1. Validate input
      2. Stage 1: extract from RSS title + content
      3. If primary fields missing → Stage 2: retrieve full article + re-extract
      4. Merge Stage 2 evidence into Stage 1 record
      5. Validate output
      6. Return (structured_record, validation_report)

    Args:
        normalized_article (dict): Normalized article satisfying the contract.
        request_delay (float|None): If set, sleep this many seconds before
                                    retrieving the full article. Used by the
                                    batch processor to pace requests.

    Returns:
        tuple: (structured_record dict, validation_report dict)
               structured_record contains only business fields and metadata.
               validation_report is for human review and is never persisted.
    """
    input_issues = _validate_input(normalized_article)

    title   = normalized_article.get("article_title", "")
    content = normalized_article.get("raw_content", "")
    url     = normalized_article.get("article_url", "")

    # --- Stage 1: extract from RSS title and content ---
    record = {}
    record.update(extract_company_fields(title, content))
    record.update(extract_funding_fields(title, content))
    record.update(extract_investor_fields(title, content))
    record.update(extract_metadata_fields(normalized_article))

    # --- Stage 2: retrieve full article if primary fields are missing ---
    full_article_retrieved = False
    retrieval_error = None

    if _needs_stage2(record) and url:
        if request_delay:
            time.sleep(request_delay)

        full_text = _fetch_full_article(url)

        if full_text:
            full_article_retrieved = True
            stage2 = {}
            stage2.update(extract_company_fields(title, full_text))
            stage2.update(extract_funding_fields(title, full_text))
            stage2.update(extract_investor_fields(title, full_text))
            record = _merge_evidence(record, stage2)
        else:
            retrieval_error = f"Could not retrieve {url}"

    # --- Output validation ---
    output_issues = _validate_output(record)

    # --- Build validation report ---
    validation_report = _build_validation_report(
        normalized_article,
        record,
        full_article_retrieved,
        input_issues,
        output_issues,
        retrieval_error,
    )

    return record, validation_report


# ---------------------------------------------------------------------------
# Entrackr adapter
# ---------------------------------------------------------------------------

def normalize_entrackr_article(entrackr_article):
    """
    Convert an article dict from fetch_entrackr_articles() into the normalized
    article format expected by the Evidence Extraction Engine.

    The extraction engine never reads Entrackr-specific field names directly.
    This adapter is the only place that knows about Entrackr's RSS structure.
    Future source adapters produce the same normalized format independently.
    """
    return {
        "article_title":             entrackr_article.get("article_title", ""),
        "article_url":               entrackr_article.get("article_url", ""),
        "article_publication_date":  entrackr_article.get("article_publication_date", ""),
        "source_name":               entrackr_article.get("source_name", ""),
        "raw_content":               entrackr_article.get("raw_content", ""),
        "classification_confidence": entrackr_article.get("classification_confidence"),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_funding_records(entrackr_articles):
    """
    Process a list of articles from fetch_entrackr_articles() through the
    Evidence Extraction Engine.

    A delay is introduced between consecutive full-article requests to avoid
    placing unnecessary load on the source website.

    Failure to process any single article never terminates the pipeline.

    Args:
        entrackr_articles (list): Articles from fetch_entrackr_articles().

    Returns:
        list of (structured_record, validation_report) tuples.
        structured_record is None if a completely unexpected failure occurred.
    """
    results = []
    previous_article_retrieved_full = False

    for article in entrackr_articles:
        try:
            normalized = normalize_entrackr_article(article)

            # Introduce a delay only when a previous article already triggered
            # a full-article retrieval — paces consecutive network requests.
            delay = FULL_ARTICLE_REQUEST_DELAY_SECONDS if previous_article_retrieved_full else None

            record, report = process_article(normalized, request_delay=delay)

            if report["full_article_retrieved"]:
                previous_article_retrieved_full = True

            results.append((record, report))

        except Exception as e:
            # An unexpected failure must never terminate the pipeline.
            error_report = {
                "article_title":          article.get("article_title", ""),
                "extraction_status":      "failed",
                "confidence":             "Weak",
                "evidence_source":        "RSS",
                "full_article_retrieved": False,
                "fields_extracted":       0,
                "total_fields":           len(BUSINESS_FIELDS),
                "missing_fields":         list(BUSINESS_FIELDS),
                "requires_manual_review": True,
                "review_reasons":         [f"Unexpected extraction failure: {e}"],
                "errors":                 [str(e)],
            }
            results.append((None, error_report))

    return results


# ---------------------------------------------------------------------------
# Manual validation entry point
# ---------------------------------------------------------------------------
# Run with: python3 -m scraper.parser

if __name__ == "__main__":
    from scraper.entrackr import fetch_entrackr_articles

    print("India Venture Review — Evidence Extraction Engine")
    print("=" * 60)
    print("Fetching recent articles from Entrackr RSS...")
    print()

    articles = fetch_entrackr_articles(verbose=False)

    if not articles:
        print("[INFO] No funding articles found in the last 24 hours.")
        raise SystemExit(0)

    print(f"Found {len(articles)} funding article(s). Running extraction...\n")
    print("─" * 60)

    results = extract_funding_records(articles)

    count_manual_review = 0
    count_full_article  = 0
    count_failed        = 0

    for record, report in results:
        symbol = "✓" if report["extraction_status"] != "failed" else "✗"
        print(f"\n{symbol} {report['article_title']}\n")
        print(f"  {'Confidence':<22} {report['confidence']}")
        print(f"  {'Evidence':<22} {report['evidence_source']}")
        print(f"  {'Fields Extracted':<22} {report['fields_extracted']} / {report['total_fields']}")

        if report["missing_fields"]:
            print(f"  {'Missing Fields':<22} {', '.join(report['missing_fields'])}")

        if report["requires_manual_review"]:
            reasons = "; ".join(report["review_reasons"])
            print(f"  {'Manual Review':<22} Yes — {reasons}")
        else:
            print(f"  {'Manual Review':<22} No")

        if report["errors"]:
            for err in report["errors"]:
                print(f"  [ERROR] {err}")

        if record:
            print()
            print(f"  {'Company':<22} {record.get('company_name') or '—'}")
            print(f"  {'Amount':<22} {record.get('funding_amount') or '—'} {record.get('currency') or ''}")
            print(f"  {'Round':<22} {record.get('funding_round') or '—'}")
            print(f"  {'Lead Investors':<22} {record.get('lead_investors') or '—'}")
            if record.get("industry"):
                print(f"  {'Industry':<22} {record.get('industry')}")
            if record.get("headquarters_city"):
                print(f"  {'HQ':<22} {record.get('headquarters_city')}, {record.get('headquarters_country') or ''}")

        if report["requires_manual_review"]:
            count_manual_review += 1
        if report["full_article_retrieved"]:
            count_full_article += 1
        if report["extraction_status"] == "failed":
            count_failed += 1

    # --- Validation summary ---
    print()
    print("─" * 60)
    print("Validation Summary")
    print("─" * 60)
    print(f"  {'RSS articles processed':<35} {len(articles)}")
    print(f"  {'Funding articles accepted':<35} {len(articles)}")
    print(f"  {'Successfully parsed':<35} {len(results) - count_failed}")
    print(f"  {'Full article retrievals':<35} {count_full_article}")
    print(f"  {'Requiring manual review':<35} {count_manual_review}")
    print(f"  {'Extraction failures':<35} {count_failed}")

    if results:
        total_extracted = sum(r[1]["fields_extracted"] for r in results)
        avg = total_extracted / len(results)
        print(f"  {'Avg fields extracted':<35} {avg:.1f} / {len(BUSINESS_FIELDS)}")

    print("─" * 60)
