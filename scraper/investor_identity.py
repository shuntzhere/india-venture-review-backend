"""Conservative formatting rules for investor names stored as text lists."""

import re
import unicodedata


_ALIASES = {
    "ajvc": "AJVC",
    "a junior vc": "AJVC",
    "ipv": "Inflection Point Ventures",
    "inflection point ventures (ipv)": "Inflection Point Ventures",
    "peak xv": "Peak XV Partners",
    "sauce": "Sauce VC",
    "steerx vc": "SteerX Ventures",
    "chiratae": "Chiratae Ventures",
    "rainmatter by zerodha": "Rainmatter",
    "l catterton": "L Catterton",
    "the national quantum mission (nqm)": "National Quantum Mission (NQM)",
}

_TEMPORAL_SUFFIX = re.compile(
    r"\s+(?:in\s+(?:january|february|march|april|may|june|july|august|"
    r"september|october|november|december)(?:\s+\d{4})?|earlier\s+this\s+year|"
    r"last\s+year)\s*$",
    re.IGNORECASE,
)
_ROUND_SUFFIX = re.compile(
    r"\s+in\s+(?:a\s+)?(?:pre[- ]?series\s+[a-z]|pre[- ]?seed|seed|series\s+[a-z])\s*$",
    re.IGNORECASE,
)
_DESCRIPTOR_PREFIX = re.compile(
    r"^(?:(?:us|india|indian)-based\s+|indian\s+)?(?:venture\s+capital\s+firm|"
    r"wealth\s+management\s+platform|investor)\s+",
    re.IGNORECASE,
)


def normalize_investor_name(value):
    """Normalize one investor name without trying to infer its identity."""
    if not value:
        return None
    value = unicodedata.normalize("NFKC", str(value))
    value = re.sub(r"\s+", " ", value).strip(" ,;")
    value = _DESCRIPTOR_PREFIX.sub("", value)
    value = _TEMPORAL_SUFFIX.sub("", value)
    value = _ROUND_SUFFIX.sub("", value)
    value = re.sub(r"\s+along\s*$", "", value, flags=re.IGNORECASE).strip()
    return _ALIASES.get(value.casefold(), value) or None


def normalize_investor_list(value):
    """Store multiple investors as a de-duplicated comma-separated list."""
    if not value:
        return None
    # The extractor uses the word "and" between separate investors. Ampersands
    # remain untouched because they are often part of a legal organization name.
    parts = re.split(r"\s*(?:,|;)\s*|\s+and\s+", str(value), flags=re.IGNORECASE)
    normalized = []
    seen = set()
    for part in parts:
        name = normalize_investor_name(part)
        key = name.casefold() if name else None
        if name and key not in seen:
            normalized.append(name)
            seen.add(key)
    return ", ".join(normalized) or None
