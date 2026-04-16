"""Tests for emailer.py with mocked requests and DB."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Skip the send-pacing sleep so tests are fast."""
    import emailer
    monkeypatch.setattr("emailer.time.sleep", lambda s: None)


@pytest.fixture(autouse=True)
def _isolate_db(fresh_db):
    """Use fresh_db so log_send / count_sends_today are test-isolated."""
    pass


# ── send_email ───────────────────────────────────────────────────────────────

def test_send_email_success(fresh_db, requests_mock):
    """A 200 response should return True and log a successful send."""
    requests_mock.post("https://api.resend.com/emails", status_code=200, json={"id": "abc"})
    import emailer
    lead_id = fresh_db.upsert_lead({
        "name": "Test Biz",
        "website": "https://test.com",
        "email": "test@test.com",
        "phone": "",
        "address": "",
        "category": "",
        "query_used": "",
    })
    result = emailer.send_email("test@test.com", "Asunto", "Cuerpo", lead_id)
    assert result is True
    # Logged as successful
    assert fresh_db.count_sends_today() == 1


def test_send_email_failure_returns_false(fresh_db, requests_mock):
    """A 422 response should return False."""
    requests_mock.post("https://api.resend.com/emails", status_code=422, json={"error": "invalid"})
    import emailer
    lead_id = fresh_db.upsert_lead({
        "name": "Test Biz 2",
        "website": "https://test2.com",
        "email": "fail@test.com",
        "phone": "",
        "address": "",
        "category": "",
        "query_used": "",
    })
    result = emailer.send_email("fail@test.com", "Asunto", "Cuerpo", lead_id)
    assert result is False
    # Should NOT count as a successful send
    assert fresh_db.count_sends_today() == 0


def test_send_email_exception_returns_false(fresh_db, monkeypatch):
    """A requests exception should return False without raising."""
    import requests
    import emailer
    monkeypatch.setattr(
        "emailer.requests.post",
        MagicMock(side_effect=requests.exceptions.ConnectionError("timeout"))
    )
    lead_id = fresh_db.upsert_lead({
        "name": "Test Biz 3",
        "website": "https://test3.com",
        "email": "exc@test.com",
        "phone": "",
        "address": "",
        "category": "",
        "query_used": "",
    })
    result = emailer.send_email("exc@test.com", "Asunto", "Cuerpo", lead_id)
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
        lead_id = fresh_db.upsert_lead({
            "name": "Multi Email",
            "website": "https://multi.com",
            "email": "first@multi.com",
            "phone": "",
            "address": "",
            "category": "",
            "query_used": "",
        })
        emailer.send_email(
            "first@multi.com, second@multi.com",
            "Asunto",
            "Cuerpo",
            lead_id,
        )

    assert posted, "No POST was made"
    assert posted[0] == ["first@multi.com"]


# ── can_send_today ───────────────────────────────────────────────────────────

def test_can_send_today_under_limit(fresh_db, monkeypatch):
    """can_send_today returns True when sends today < DAILY_SEND_LIMIT."""
    import config
    import emailer
    monkeypatch.setattr(config, "DAILY_SEND_LIMIT", 50)
    assert emailer.can_send_today() is True


def test_can_send_today_at_limit(fresh_db, monkeypatch):
    """can_send_today returns False when sends today >= DAILY_SEND_LIMIT."""
    import config
    import emailer
    monkeypatch.setattr(config, "DAILY_SEND_LIMIT", 2)
    # Log 2 successful sends
    lead_id = fresh_db.upsert_lead({
        "name": "Cap Test",
        "website": "https://cap.com",
        "email": "cap@cap.com",
        "phone": "",
        "address": "",
        "category": "",
        "query_used": "",
    })
    fresh_db.log_send(lead_id, "outreach", True)
    fresh_db.log_send(lead_id, "outreach", True)
    assert emailer.can_send_today() is False
