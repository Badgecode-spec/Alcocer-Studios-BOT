import time

import requests

import config
import db
from logger import get_logger

log = get_logger(__name__)

_OUTSCRAPER_URL = "https://api.outscraper.com/maps/search-v3"


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
        resp = requests.get(_OUTSCRAPER_URL, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # Outscraper returns {"data": [[...results...]]} or {"data": [...results...]}
        raw = data.get("data", [])
        # Flatten nested lists (v3 wraps results in a list per query)
        if raw and isinstance(raw[0], list):
            raw = raw[0]
        log.info("outscraper query=%r fetched=%d", query, len(raw))
        return raw
    except requests.HTTPError as exc:
        log.error("outscraper HTTP error query=%r status=%s", query, exc.response.status_code)
        return []
    except Exception as exc:
        log.error("outscraper error query=%r: %s", query, exc)
        return []


def _extract_email(raw: dict) -> str:
    """Extract best available email from a raw Outscraper result."""
    email = raw.get("email", "")
    if not email:
        emails_from_site = raw.get("emails_from_website", [])
        if emails_from_site and isinstance(emails_from_site, list):
            email = emails_from_site[0]
    email = str(email).strip().lower()
    # Basic sanity check
    if "@" not in email or "." not in email.split("@")[-1]:
        return ""
    return email


def parse_lead(raw: dict, query_used: str) -> dict | None:
    """
    Normalize a raw Outscraper place dict.
    Returns None if website or email is missing (filter rule).
    """
    website = (raw.get("site") or raw.get("website") or "").strip()
    email = _extract_email(raw)

    if not website or not email:
        return None

    return {
        "name": (raw.get("name") or "").strip(),
        "website": website,
        "email": email,
        "phone": (raw.get("phone") or raw.get("phone_number") or "").strip(),
        "address": (raw.get("full_address") or raw.get("address") or "").strip(),
        "category": (raw.get("type") or raw.get("category") or "").strip(),
        "query_used": query_used,
    }


def run_lead_fetch() -> int:
    """
    Fetch leads for all configured queries, filter, and upsert into DB.
    Returns total number of new leads inserted.
    """
    if not config.OUTSCRAPER_QUERIES:
        log.warning("OUTSCRAPER_QUERIES is empty — no leads fetched")
        return 0

    total_new = 0

    for i, query in enumerate(config.OUTSCRAPER_QUERIES):
        raw_list = fetch_leads_from_outscraper(query, config.OUTSCRAPER_LIMIT)
        new_for_query = 0

        for raw in raw_list:
            lead = parse_lead(raw, query)
            if lead is None:
                continue
            if db.email_exists(lead["email"]):
                continue
            db.upsert_lead(lead)
            new_for_query += 1

        log.info("leads_fetch query=%r new=%d", query, new_for_query)
        total_new += new_for_query

        # Courtesy sleep between queries to avoid rate limits
        if i < len(config.OUTSCRAPER_QUERIES) - 1:
            time.sleep(1)

    log.info("leads_fetch_total new=%d", total_new)
    return total_new
