import time

import requests

import config
import db
from logger import get_logger

log = get_logger(__name__)

_MAPS_URL = "https://api.outscraper.com/maps/search-v3"
_EMAIL_URL = "https://api.outscraper.com/emails-and-contacts"


def fetch_leads_from_outscraper(query: str, limit: int) -> list[dict]:
    """
    Call Outscraper Google Maps API and return raw place dicts.
    Returns empty list on any error.
    """
    params = {
        "query": query,
        "limit": limit,
        "language": "es",
        "async": False,
    }
    headers = {"X-API-KEY": config.OUTSCRAPER_API_KEY}
    try:
        resp = requests.get(_MAPS_URL, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("data", [])
        if raw and isinstance(raw[0], list):
            raw = raw[0]
        log.info("outscraper maps query=%r fetched=%d", query, len(raw))
        return raw
    except requests.HTTPError as exc:
        log.error("outscraper maps HTTP error query=%r status=%s", query, exc.response.status_code)
        return []
    except Exception as exc:
        log.error("outscraper maps error query=%r: %s", query, exc)
        return []


def fetch_email_from_website(website: str) -> str:
    """
    Call Outscraper Domain Emails & Contacts API to scrape email from a website.
    Only called when Google Maps didn't provide an email.
    Returns email string or empty string on failure.
    """
    params = {
        "query": website,
        "async": False,
    }
    headers = {"X-API-KEY": config.OUTSCRAPER_API_KEY}
    try:
        resp = requests.get(_EMAIL_URL, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("data", [])
        if raw and isinstance(raw[0], list):
            raw = raw[0]
        if not raw:
            return ""
        result = raw[0] if isinstance(raw[0], dict) else {}
        # Try emails array first, then direct email field
        emails = result.get("emails", [])
        if emails and isinstance(emails, list):
            email = emails[0].get("value", "") if isinstance(emails[0], dict) else emails[0]
        else:
            email = result.get("email", "")
        return _validate_email(str(email).strip().lower())
    except Exception as exc:
        log.warning("outscraper email scrape failed website=%r: %s", website, exc)
        return ""


def _validate_email(email: str) -> str:
    """Return email if valid, empty string otherwise."""
    if "@" not in email or "." not in email.split("@")[-1]:
        return ""
    return email


def _extract_email(raw: dict) -> str:
    """Extract best available email from a raw Google Maps result."""
    email = raw.get("email", "")
    if not email:
        emails_from_site = raw.get("emails_from_website", [])
        if emails_from_site and isinstance(emails_from_site, list):
            email = emails_from_site[0]
    return _validate_email(str(email).strip().lower())


def parse_lead(raw: dict, query_used: str) -> dict | None:
    """
    Normalize a raw Outscraper place dict.
    Returns None if website is missing.
    Email may be empty — caller handles enrichment.
    """
    website = (raw.get("site") or raw.get("website") or "").strip()
    if not website:
        return None

    return {
        "name": (raw.get("name") or "").strip(),
        "website": website,
        "email": _extract_email(raw),
        "phone": (raw.get("phone") or raw.get("phone_number") or "").strip(),
        "address": (raw.get("full_address") or raw.get("address") or "").strip(),
        "category": (raw.get("type") or raw.get("category") or "").strip(),
        "query_used": query_used,
    }


def run_lead_fetch() -> int:
    """
    Fetch leads for all configured queries, enrich missing emails via
    Domain Emails API, filter, and upsert into DB.
    Returns total number of new leads inserted.
    """
    if not config.OUTSCRAPER_QUERIES:
        log.warning("OUTSCRAPER_QUERIES is empty — no leads fetched")
        return 0

    total_new = 0

    for i, query in enumerate(config.OUTSCRAPER_QUERIES):
        raw_list = fetch_leads_from_outscraper(query, config.OUTSCRAPER_LIMIT)
        new_for_query = 0
        enriched = 0

        for raw in raw_list:
            lead = parse_lead(raw, query)
            if lead is None:
                continue  # no website — skip

            # If Google Maps didn't have an email, try Domain Emails API
            if not lead["email"]:
                email = fetch_email_from_website(lead["website"])
                if email:
                    lead["email"] = email
                    enriched += 1
                    time.sleep(0.5)  # be gentle between enrichment calls

            # Still no email after enrichment — skip
            if not lead["email"]:
                continue

            if db.email_exists(lead["email"]):
                continue

            db.upsert_lead(lead)
            new_for_query += 1

        log.info("leads_fetch query=%r new=%d enriched=%d", query, new_for_query, enriched)
        total_new += new_for_query

        # Courtesy sleep between queries
        if i < len(config.OUTSCRAPER_QUERIES) - 1:
            time.sleep(1)

    log.info("leads_fetch_total new=%d", total_new)
    return total_new
