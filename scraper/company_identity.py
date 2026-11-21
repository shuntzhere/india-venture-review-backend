"""Canonical company identity helpers shared by ingestion and backfills."""

import re
import unicodedata
from urllib.parse import urlsplit


_EDITORIAL_PREFIX = re.compile(r"^\s*exclusive\s*:\s*", re.IGNORECASE)
_DOTTED_AI_SUFFIX = re.compile(r"\.\s*ai$", re.IGNORECASE)
_PLAIN_AI_SUFFIX = re.compile(r"\s+ai$", re.IGNORECASE)
_TRAILING_EDITORIAL_PUNCTUATION = re.compile(r"[,;:]\s*$")
_WHITESPACE = re.compile(r"\s+")
_CURATED_ALIAS_KEYS = {
    "curelink": "disha",
    "disha formerly curelink": "disha",
}


def clean_company_name(value):
    """Clean shape-only noise while preserving verified brand styling."""
    if value is None:
        return None
    name = unicodedata.normalize("NFKC", str(value))
    name = _WHITESPACE.sub(" ", name).strip()
    name = _EDITORIAL_PREFIX.sub("", name)
    name = _TRAILING_EDITORIAL_PUNCTUATION.sub("", name).strip()
    name = _DOTTED_AI_SUFFIX.sub(".ai", name)
    name = _PLAIN_AI_SUFFIX.sub(".ai", name)
    return name or None


def company_name_key(value):
    """Return a comparison key; ``Foo AI`` and ``Foo.ai`` intentionally match."""
    name = clean_company_name(value) or ""
    folded = unicodedata.normalize("NFKD", name)
    ascii_name = folded.encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.casefold().replace("&", " and ")
    return _WHITESPACE.sub(
        " ", re.sub(r"[^a-z0-9]+", " ", ascii_name)
    ).strip()


def company_lookup_key(value):
    """Return the canonical lookup key, including reviewed former-name aliases."""
    key = company_name_key(value)
    return _CURATED_ALIAS_KEYS.get(key, key)


def normalize_website(value):
    """Return a canonical HTTPS homepage URL, or ``None`` for an invalid value."""
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    parsed = urlsplit(raw if "://" in raw else "//" + raw)
    hostname = (parsed.hostname or "").casefold().rstrip(".")
    if hostname.startswith("www."):
        hostname = hostname[4:]
    if not hostname or "." not in hostname or any(char.isspace() for char in hostname):
        return None
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return None
    return "https://" + hostname


def website_domain(value):
    """Return the normalized hostname for a canonical or legacy website value."""
    normalized = normalize_website(value)
    return urlsplit(normalized).hostname if normalized else None
