"""Identity-safe website enrichment for companies created during ingestion."""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from scraper.company_identity import normalize_website, website_domain
from scraper.database import _get_client


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
MODEL = "gpt-5-mini"
REQUEST_TIMEOUT_SECONDS = 120
MAX_COMPANIES_PER_RUN = 10
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "identity_confident": {"type": "boolean"},
        "website": {"type": ["string", "null"]},
        "evidence_urls": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["identity_confident", "website", "evidence_urls"],
}


def _response_text(response):
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text", "")
    return ""


def research_official_website(company, api_key, session=None):
    """Return a verified canonical homepage and same-domain evidence URL."""
    session = session or requests.Session()
    prompt = f"""Research the exact organisation named {company['company_name']!r}.
Its funding record came from {company['source_article_url']}.
Find its official homepage using web search. The organisation may be a startup,
company, investment firm, or named fund. Do not return a news article, directory,
social profile, marketplace listing, or similarly named organisation. If the
identity or official domain is ambiguous, set identity_confident to false and
website to null. Include the official homepage itself in evidence_urls."""
    response = session.post(
        OPENAI_RESPONSES_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "store": False,
            "reasoning": {"effort": "low"},
            "tools": [{"type": "web_search"}],
            "tool_choice": "required",
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "company_website",
                    "strict": True,
                    "schema": SCHEMA,
                }
            },
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    text = _response_text(response.json())
    if not text:
        raise RuntimeError("Website research returned no structured output")

    result = json.loads(text)
    if not result["identity_confident"]:
        return None
    website = normalize_website(result.get("website"))
    domain = website_domain(website)
    evidence_url = next(
        (
            url for url in result.get("evidence_urls", [])
            if website_domain(url) == domain
        ),
        None,
    )
    if not website or not evidence_url:
        return None
    return {"website": website, "evidence_url": evidence_url}


def list_missing_website_targets(client=None, limit=MAX_COMPANIES_PER_RUN):
    """Return missing-website companies with their most recent source article."""
    client = client or _get_client()
    companies = (
        client.table("companies")
        .select("id,company_name")
        .is_("website", "null")
        .limit(limit)
        .execute()
        .data
        or []
    )
    if not companies:
        return []

    company_ids = [company["id"] for company in companies]
    events = (
        client.table("funding_events")
        .select("company_id,article_url,article_publication_date")
        .in_("company_id", company_ids)
        .order("article_publication_date", desc=True)
        .execute()
        .data
        or []
    )
    latest_source = {}
    for event in events:
        if event.get("article_url") and event["company_id"] not in latest_source:
            latest_source[event["company_id"]] = event["article_url"]
    return [
        {
            **company,
            "source_article_url": latest_source[company["id"]],
        }
        for company in companies
        if company["id"] in latest_source
    ]


def enrich_pending_company_websites(new_companies=None, client=None, api_key=None, workers=4):
    """Enrich new rows plus retry the existing missing-website backlog."""
    client = client or _get_client()
    combined = {}
    for company in list(new_companies or []) + list_missing_website_targets(client=client):
        combined[company["id"]] = company
    return enrich_new_company_websites(
        list(combined.values()),
        client=client,
        api_key=api_key,
        workers=workers,
    )


def enrich_new_company_websites(companies, client=None, api_key=None, workers=4):
    """Research and persist official websites for newly created companies."""
    targets = list(companies or [])[:MAX_COMPANIES_PER_RUN]
    result = {
        "targets": len(targets),
        "enriched": 0,
        "unresolved": 0,
        "errors": [],
    }
    if not targets:
        return result

    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        result["errors"].append("OPENAI_API_KEY is not configured")
        return result
    client = client or _get_client()

    with ThreadPoolExecutor(max_workers=min(max(workers, 1), len(targets))) as executor:
        futures = {
            executor.submit(research_official_website, company, api_key): company
            for company in targets
        }
        for future in as_completed(futures):
            company = futures[future]
            try:
                verified = future.result()
                if not verified:
                    result["unresolved"] += 1
                    continue
                updates = {
                    "website": verified["website"],
                    "website_verified": True,
                    "website_evidence_url": verified["evidence_url"],
                }
                client.table("company_identity_change_log").insert({
                    "company_id": company["id"],
                    "changed_fields": list(updates),
                    "old_values": {
                        "website": None,
                        "website_verified": False,
                        "website_evidence_url": None,
                    },
                    "new_values": updates,
                    "reason": "Official website verified after company ingestion",
                    "evidence_url": verified["evidence_url"],
                }).execute()
                client.table("companies").update(updates).eq("id", company["id"]).execute()
                result["enriched"] += 1
            except (requests.RequestException, ValueError, RuntimeError, KeyError) as error:
                result["errors"].append({
                    "company": company.get("company_name"),
                    "error": str(error)[:300],
                })
    return result
