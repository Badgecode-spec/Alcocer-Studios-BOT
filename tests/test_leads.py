"""Tests for leads.py pure functions — no Outscraper API calls."""
import pytest


@pytest.fixture(autouse=True)
def _no_api_calls(monkeypatch):
    """Prevent any real HTTP calls in tests."""
    import leads
    monkeypatch.setattr(leads, "fetch_leads_from_outscraper", lambda *a, **kw: [])
    monkeypatch.setattr(leads, "fetch_email_from_website", lambda *a, **kw: "")


# ── _has_weak_presence ──────────────────────────────────────────────────────

def test_has_weak_presence_social_media():
    """A business whose 'website' is facebook.com should be a weak target."""
    import leads
    raw = {}
    assert leads._has_weak_presence(raw, "https://facebook.com/mispa") is True


def test_has_weak_presence_wix():
    """A business on wix.com should be a weak target."""
    import leads
    raw = {}
    assert leads._has_weak_presence(raw, "https://mispa.wix.com") is True


def test_has_weak_presence_too_many_reviews():
    """A business with 600 reviews (> _MAX_REVIEWS=500) should NOT be a target."""
    import leads
    raw = {"reviews": 600}
    # They have a real website and too many reviews
    assert leads._has_weak_presence(raw, "https://realsite.com") is False


def test_has_weak_presence_small_reviews():
    """A business with 100 reviews (≤ _MAX_REVIEWS) should be a target."""
    import leads
    raw = {"reviews": 100}
    assert leads._has_weak_presence(raw, "https://somesite.com") is True


def test_has_weak_presence_no_reviews_field():
    """A business with no reviews field in raw data should be a target."""
    import leads
    raw = {}
    assert leads._has_weak_presence(raw, "https://somesite.com") is True


# ── parse_lead ──────────────────────────────────────────────────────────────

def test_parse_lead_returns_none_when_no_website():
    """parse_lead should return None when raw has no website."""
    import leads
    raw = {"name": "Sin Sitio", "email": "test@test.com"}
    assert leads.parse_lead(raw, "spa en cdmx") is None


def test_parse_lead_returns_none_when_too_established():
    """parse_lead should return None for a business with 600 reviews and real site."""
    import leads
    raw = {
        "name": "Mega Spa",
        "site": "https://megaspa.com",
        "email": "info@megaspa.com",
        "reviews": 600,
    }
    assert leads.parse_lead(raw, "spa en cdmx") is None


def test_parse_lead_valid_lead():
    """parse_lead should return a dict with expected keys for a valid target."""
    import leads
    raw = {
        "name": "Spa Bonito",
        "site": "https://spabonito.wix.com",
        "email": "spa@bonito.com",
        "phone": "5550001111",
        "full_address": "Calle 1, CDMX",
        "type": "spa",
        "reviews": 50,
    }
    result = leads.parse_lead(raw, "spa en cdmx")
    assert result is not None
    assert result["name"] == "Spa Bonito"
    assert result["website"] == "https://spabonito.wix.com"
    assert result["email"] == "spa@bonito.com"
    assert result["query_used"] == "spa en cdmx"


# ── _validate_email ─────────────────────────────────────────────────────────

def test_validate_email_valid():
    """A properly formatted email should pass validation."""
    import leads
    assert leads._validate_email("hola@ejemplo.com") == "hola@ejemplo.com"


def test_validate_email_no_at_sign():
    """An email without '@' should return empty string."""
    import leads
    assert leads._validate_email("noatsign.com") == ""


def test_validate_email_no_dot_in_domain():
    """An email whose domain has no '.' should return empty string."""
    import leads
    assert leads._validate_email("hola@nodot") == ""
