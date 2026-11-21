"""Audit or apply high-confidence company identity corrections."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scraper.company_identity import clean_company_name, normalize_website
from scraper.database import _get_client


NAME_CORRECTIONS = {
    "AJVC to back pre-seed startups": "AJVC",
    "BCT Ventures launches AI native consumer brands platform,": "BCT Ventures",
    "Coffee equipment and services provider Kaapi Machines": "Kaapi Machines",
    "D2C grocery startup Anmasa": "Anmasa",
    "Disha (formerly Curelink)": "Disha",
    "Exclusive: BiofuelCircle": "BiofuelCircle",
    "Exclusive: Dosa chain Benne": "Benne",
    "Exclusive: WizCommerce": "WizCommerce",
    "PhonePe enters UAE,": "PhonePe",
    "The Pizza Bakery operator Popo Global": "Popo Global",
    "Transition VC-backed Matel": "Matel",
    "YoLearn ai": "YoLearn.ai",
    "E3 Electric": "E3 Electric.ai",
}

WEBSITE_CORRECTIONS = {
    "Beyond Appliances": (
        "https://beyondappliances.in",
        "https://beyondappliances.in/",
    ),
    "Data Science Wizards": (
        "https://datasciencewizards.ai",
        "https://www.datasciencewizards.ai/privacy-policy",
    ),
    "Discovered Materials": (
        "https://discoveredmaterials.com",
        "https://discoveredmaterials.com/",
    ),
    "Runable": ("https://runable.com", "https://runable.com/"),
    "Tross": (
        "https://ontross.com",
        "https://www.linkedin.com/company/ontross",
    ),
    "Zaperon": ("https://zaperon.com", "https://zaperon.com/"),
}

WEBSITE_REMOVALS = {
    "E3 Electric.ai": "electric.ai was parsed from the brand phrase E3 Electric.Ai",
}

MONTH_CITIES = {
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
}

REVIEW_REASONS = {
    "Drivn’s Indian entity": "Article wording is not a verified company identity",
    "PhonePe": "Stored source appears to report regulatory approval rather than funding",
    "E3 Electric.ai": "Official homepage still needs verification",
}

IDENTITY_SCHEMA_FIELDS = {
    "website_verified",
    "website_evidence_url",
    "identity_review_required",
    "identity_review_reason",
}


def proposed_updates(company):
    """Return deterministic updates and human-readable reasons for one row."""
    old_name = company["company_name"]
    name = NAME_CORRECTIONS.get(old_name, clean_company_name(old_name))
    updates = {}
    reasons = []
    evidence_url = None

    if name != old_name:
        updates["company_name"] = name
        reasons.append("canonical company display name")

    effective_name = name or old_name
    if effective_name in WEBSITE_CORRECTIONS:
        website, evidence_url = WEBSITE_CORRECTIONS[effective_name]
        updates.update({
            "website": website,
            "website_verified": True,
            "website_evidence_url": evidence_url,
        })
        reasons.append("verified official website")
    elif effective_name in WEBSITE_REMOVALS:
        updates.update({
            "website": None,
            "website_verified": False,
            "website_evidence_url": None,
        })
        reasons.append(WEBSITE_REMOVALS[effective_name])
    elif company.get("website"):
        website = normalize_website(company["website"])
        if website != company["website"]:
            updates["website"] = website
            reasons.append("canonical website URL shape")

    if company.get("headquarters_city") in MONTH_CITIES:
        updates.update({
            "headquarters_city": None,
            "headquarters_country": None,
        })
        reasons.append("invalid month parsed as headquarters")

    review_reason = REVIEW_REASONS.get(effective_name)
    if review_reason:
        updates.update({
            "identity_review_required": True,
            "identity_review_reason": review_reason,
        })
        reasons.append("manual identity review")

    updates = {
        field: value for field, value in updates.items()
        if company.get(field) != value
    }
    return updates, reasons, evidence_url


def _change_log_entry(company, updates, reasons, evidence_url):
    fields = sorted(updates)
    return {
        "company_id": company["id"],
        "changed_fields": fields,
        "old_values": {field: company.get(field) for field in fields},
        "new_values": {field: updates[field] for field in fields},
        "reason": "; ".join(reasons),
        "evidence_url": evidence_url,
    }


def run(apply=False):
    client = _get_client()
    companies = client.table("companies").select("*").order("company_name").execute().data or []
    identity_schema_available = "company_name_normalized" in (companies[0] if companies else {})
    changes = []
    for company in companies:
        updates, reasons, evidence_url = proposed_updates(company)
        if not identity_schema_available:
            updates = {
                field: value for field, value in updates.items()
                if field not in IDENTITY_SCHEMA_FIELDS
            }
        if not updates:
            continue
        entry = _change_log_entry(company, updates, reasons, evidence_url)
        changes.append({
            "company_name": company["company_name"],
            "updates": updates,
            "reason": entry["reason"],
        })
        if not apply:
            continue
        if identity_schema_available:
            client.table("company_identity_change_log").insert(entry).execute()
        client.table("companies").update(updates).eq("id", company["id"]).execute()
        if identity_schema_available and company["company_name"] == "Disha (formerly Curelink)":
            client.table("company_aliases").upsert({
                "company_id": company["id"],
                "alias": "Curelink",
                "normalized_alias": "curelink",
                "alias_type": "former_name",
                "evidence_url": company.get("website_evidence_url"),
            }, on_conflict="company_id,normalized_alias").execute()

    return {
        "mode": "apply" if apply else "dry_run",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "companies_scanned": len(companies),
        "companies_changed": len(changes),
        "identity_schema_available": identity_schema_available,
        "changes": changes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply corrections; default is read-only.")
    args = parser.parse_args()
    print(json.dumps(run(apply=args.apply), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
