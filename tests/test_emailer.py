"""Tests for emailer.py with mocked requests and DB."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Skip the send-pacing sleep so tests are fast."""
    import emailer
    monkeypatch.setattr(emailer.time, "sleep", lambda s: None)


@pytest.fixture(autouse=True)
def _isolate_db(fresh_db):
    """Use fresh_db so log_send / count_sends_today are test-isolated."""
    pass


def _lead(email="test@biz.com", **kw):
    return {"name": "Biz", "website": "https://biz.com", "email": email,
            "phone": "", "address": "", "category": "", "query_used": "", **kw}


# ── send_email ───────────────────────────────────────────────────────────────

def test_send_email_success(fresh_db, requests_mock):
    """A 200 response should return True and log a successful send."""
    requests_mock.post("https://api.resend.com/emails", status_code=200, json={"id": "abc"})
    import emailer
    lead_id = fresh_db.upsert_lead(_lead())
    result = emailer.send_email("test@biz.com", "Asunto", "Cuerpo", lead_id)
    assert result is True
    assert fresh_db.count_sends_today() == 1


def test_send_email_failure_returns_false(fresh_db, requests_mock):
    """A 422 response should return False and not count as a successful send."""
    requests_mock.post("https://api.resend.com/emails", status_code=422, json={"error": "invalid"})
    import emailer
    lead_id = fresh_db.upsert_lead(_lead("fail@biz.com"))
    result = emailer.send_email("fail@biz.com", "Asunto", "Cuerpo", lead_id)
    assert result is False
    assert fresh_db.count_sends_today() == 0


def test_send_email_exception_returns_false(fresh_db, monkeypatch):
    """A requests exception should return False without raising."""
    import requests
    import emailer
    monkeypatch.setattr(
        "emailer.requests.post",
        MagicMock(side_effect=requests.exceptions.ConnectionError("timeout"))
    )
    lead_id = fresh_db.upsert_lead(_lead("exc@biz.com"))
    result = emailer.send_email("exc@biz.com", "Asunto", "Cuerpo", lead_id)
    assert result is False


def test_send_email_uses_first_address_for_multiple_emails(fresh_db):
    """When to_email has multiple comma-separated addresses, only the first is used."""
    posted = []

    def capture(url, **kwargs):
        posted.append(kwargs.get("json", {}).get("to", []))
        resp = MagicMock()
        resp.status_code = 200
        return resp

    import emailer
    with patch("emailer.requests.post", side_effect=capture):
        lead_id = fresh_db.upsert_lead(_lead("first@biz.com"))
        emailer.send_email("first@biz.com, second@biz.com", "Asunto", "Cuerpo", lead_id)

    assert posted, "No POST was made"
    assert posted[0] == ["first@biz.com"]


# ── can_send_outreach_today ──────────────────────────────────────────────────

def test_can_send_outreach_today_under_limit(fresh_db, monkeypatch):
    """can_send_outreach_today returns True when outreach sends < DAILY_SEND_LIMIT."""
    import config, emailer
    monkeypatch.setattr(config, "DAILY_SEND_LIMIT", 50)
    assert emailer.can_send_outreach_today() is True


def test_can_send_outreach_today_at_limit(fresh_db, monkeypatch):
    """can_send_outreach_today returns False when outreach sends >= DAILY_SEND_LIMIT."""
    import config, emailer
    monkeypatch.setattr(config, "DAILY_SEND_LIMIT", 2)
    lead_id = fresh_db.upsert_lead(_lead("cap@biz.com"))
    fresh_db.log_send(lead_id, "outreach", True)
    fresh_db.log_send(lead_id, "outreach", True)
    assert emailer.can_send_outreach_today() is False


def test_followup_sends_do_not_count_against_outreach_cap(fresh_db, monkeypatch):
    """Follow-up and reply sends must NOT reduce the available outreach slots."""
    import config, emailer
    monkeypatch.setattr(config, "DAILY_SEND_LIMIT", 2)
    lead_id = fresh_db.upsert_lead(_lead("fu@biz.com"))
    # Log 2 follow-up and 1 reply — these should not consume the outreach cap
    fresh_db.log_send(lead_id, "followup", True)
    fresh_db.log_send(lead_id, "followup", True)
    fresh_db.log_send(lead_id, "reply", True)
    # Outreach cap is still open
    assert emailer.can_send_outreach_today() is True
    # Now add outreach sends up to the cap
    fresh_db.log_send(lead_id, "outreach", True)
    fresh_db.log_send(lead_id, "outreach", True)
    assert emailer.can_send_outreach_today() is False
