"""Tests for db.py — all using fresh_db fixture for isolation."""
import pytest


def _sample_lead(**overrides):
    lead = {
        "name": "Spa Ejemplo",
        "website": "https://spaejemplo.com",
        "email": "hola@spaejemplo.com",
        "phone": "5551234567",
        "address": "Calle Falsa 123, CDMX",
        "category": "spa",
        "query_used": "spa en Ciudad de Mexico",
    }
    lead.update(overrides)
    return lead


def test_upsert_lead_inserts_new(fresh_db):
    """A new lead should be inserted and return a positive integer id."""
    lead_id = fresh_db.upsert_lead(_sample_lead())
    assert isinstance(lead_id, int)
    assert lead_id > 0


def test_upsert_lead_ignores_duplicate_email(fresh_db):
    """Inserting the same email twice should return the same id."""
    id1 = fresh_db.upsert_lead(_sample_lead())
    id2 = fresh_db.upsert_lead(_sample_lead())
    assert id1 == id2
    # Only one row in DB
    rows = fresh_db.get_leads_by_status("new")
    assert len(rows) == 1


def test_get_leads_by_status(fresh_db):
    """get_leads_by_status should only return leads matching the given status."""
    fresh_db.upsert_lead(_sample_lead(email="a@example.com"))
    fresh_db.upsert_lead(_sample_lead(email="b@example.com"))
    rows = fresh_db.get_leads_by_status("new")
    assert len(rows) == 2
    assert all(row["status"] == "new" for row in rows)


def test_update_lead_outreach_sent_changes_status(fresh_db):
    """After update_lead_outreach_sent, lead status should be 'contacted'."""
    lead_id = fresh_db.upsert_lead(_sample_lead())
    fresh_db.update_lead_outreach_sent(lead_id, ai_line="Tu web no carga bien en celular.")
    rows = fresh_db.get_leads_by_status("contacted")
    assert len(rows) == 1
    assert rows[0]["ai_line_used"] == "Tu web no carga bien en celular."
    assert rows[0]["outreach_sent_at"] is not None


def test_update_lead_followup_sent(fresh_db):
    """After update_lead_followup_sent, lead status should be 'followup'."""
    lead_id = fresh_db.upsert_lead(_sample_lead())
    fresh_db.update_lead_outreach_sent(lead_id, ai_line="")
    fresh_db.update_lead_followup_sent(lead_id)
    rows = fresh_db.get_leads_by_status("followup")
    assert len(rows) == 1
    assert rows[0]["followup_sent_at"] is not None


def test_update_lead_replied(fresh_db):
    """After update_lead_replied, lead status should be 'replied' with notes."""
    lead_id = fresh_db.upsert_lead(_sample_lead())
    fresh_db.update_lead_replied(lead_id, notes="Sí me interesa")
    rows = fresh_db.get_leads_by_status("replied")
    assert len(rows) == 1
    assert rows[0]["notes"] == "Sí me interesa"
    assert rows[0]["replied_at"] is not None


def test_close_lead(fresh_db):
    """close_lead should set status to 'closed' with notes."""
    lead_id = fresh_db.upsert_lead(_sample_lead())
    fresh_db.close_lead(lead_id, notes="Opt-out requested")
    rows = fresh_db.get_leads_by_status("closed")
    assert len(rows) == 1
    assert rows[0]["notes"] == "Opt-out requested"


def test_get_lead_by_email(fresh_db):
    """get_lead_by_email should return the lead row matching the email."""
    lead_id = fresh_db.upsert_lead(_sample_lead())
    row = fresh_db.get_lead_by_email("hola@spaejemplo.com")
    assert row is not None
    assert row["id"] == lead_id
    assert row["name"] == "Spa Ejemplo"


def test_get_lead_by_email_case_insensitive(fresh_db):
    """get_lead_by_email should be case-insensitive."""
    fresh_db.upsert_lead(_sample_lead())
    row = fresh_db.get_lead_by_email("HOLA@SPAEJEMPLO.COM")
    assert row is not None


def test_get_lead_by_email_missing_returns_none(fresh_db):
    """get_lead_by_email should return None when email not in DB."""
    result = fresh_db.get_lead_by_email("nosuchperson@nowhere.com")
    assert result is None


def test_count_sends_today(fresh_db):
    """count_sends_today should count only successful sends for today."""
    lead_id = fresh_db.upsert_lead(_sample_lead())
    assert fresh_db.count_sends_today() == 0
    fresh_db.log_send(lead_id, "outreach", True)
    assert fresh_db.count_sends_today() == 1
    # Failed send should NOT count
    fresh_db.log_send(lead_id, "followup", False, "timeout")
    assert fresh_db.count_sends_today() == 1


def test_get_weekly_stats(fresh_db):
    """get_weekly_stats should return a dict with expected keys and correct totals."""
    stats = fresh_db.get_weekly_stats()
    assert "sent_7d" in stats
    assert "total" in stats
    for status in ("new", "contacted", "followup", "replied", "closed"):
        assert status in stats
    # Initially empty
    assert stats["total"] == 0
    assert stats["sent_7d"] == 0

    # Add a lead and a send
    lead_id = fresh_db.upsert_lead(_sample_lead())
    fresh_db.log_send(lead_id, "outreach", True)
    stats2 = fresh_db.get_weekly_stats()
    assert stats2["total"] == 1
    assert stats2["new"] == 1
    assert stats2["sent_7d"] == 1


def test_get_state_returns_empty_string_for_missing_key(fresh_db):
    """get_state on a key that doesn't exist should return empty string."""
    result = fresh_db.get_state("nonexistent_key_xyz")
    assert result == ""


def test_set_state_and_get_state(fresh_db):
    """set_state then get_state should round-trip correctly."""
    fresh_db.set_state("last_lead_fetch_date", "2026-04-16")
    result = fresh_db.get_state("last_lead_fetch_date")
    assert result == "2026-04-16"


def test_set_state_overwrites(fresh_db):
    """set_state called twice with same key should overwrite the value."""
    fresh_db.set_state("mykey", "first")
    fresh_db.set_state("mykey", "second")
    assert fresh_db.get_state("mykey") == "second"


def test_email_exists(fresh_db):
    """email_exists should return True when email is in DB, False otherwise."""
    assert not fresh_db.email_exists("nobody@example.com")
    fresh_db.upsert_lead(_sample_lead())
    assert fresh_db.email_exists("hola@spaejemplo.com")
