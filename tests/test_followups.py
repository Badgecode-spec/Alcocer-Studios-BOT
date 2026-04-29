"""Tests for followups.py — 3-round follow-up cycle with auto-close."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _isolate_db(fresh_db):
    pass


def _contacted_lead(fresh_db, days_ago: int, followup_count: int = 0):
    """Insert a contacted lead with outreach sent `days_ago` days ago,
    and optionally log `followup_count` previous follow-ups."""
    lead_id = fresh_db.upsert_lead({
        "name": "Test Biz",
        "website": "https://test.com",
        "email": "test@test.com",
        "phone": "",
        "address": "",
        "category": "spa",
        "query_used": "test",
    })
    outreach_ts = (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    status = "followup" if followup_count > 0 else "contacted"
    with fresh_db.get_connection() as conn:
        conn.execute(
            "UPDATE leads SET status=?, outreach_sent_at=? WHERE id=?",
            (status, outreach_ts, lead_id),
        )
    for i in range(followup_count):
        ts = (datetime.now(timezone.utc) - timedelta(days=days_ago - 2 * (i + 1))).strftime("%Y-%m-%dT%H:%M:%SZ")
        with fresh_db.get_connection() as conn:
            conn.execute(
                "INSERT INTO send_log (lead_id, send_type, sent_at, success) VALUES (?,?,?,1)",
                (lead_id, "followup", ts),
            )
    return lead_id


def _mock_send_ok(mocker):
    return mocker.patch("followups.emailer.send_email", return_value=True)


def _in_window(mocker):
    """Patch datetime so the cycle thinks it's 10am CDMX."""
    from datetime import timezone, timedelta
    CDMX = timezone(timedelta(hours=-6))
    fake_now = datetime(2026, 5, 1, 10, 0, tzinfo=CDMX)
    m = mocker.patch("followups.datetime")
    m.now.return_value = fake_now
    return m


# ── time window ──────────────────────────────────────────────────────────────

def test_followup_skipped_outside_window(mocker, fresh_db):
    """Cycle should return 0 and skip when current hour is outside 9am-9pm CDMX."""
    from datetime import timezone, timedelta
    CDMX = timezone(timedelta(hours=-6))
    fake_now = datetime(2026, 5, 1, 2, 0, tzinfo=CDMX)
    m = mocker.patch("followups.datetime")
    m.now.return_value = fake_now

    import followups
    assert followups.run_followup_cycle() == 0


# ── round selection ──────────────────────────────────────────────────────────

def test_round1_sends_template_1(mocker, fresh_db):
    """First follow-up should call build_followup_email with followup_num=1."""
    _in_window(mocker)
    _contacted_lead(fresh_db, days_ago=3, followup_count=0)
    mock_send = _mock_send_ok(mocker)
    mock_build = mocker.patch(
        "followups.messaging.build_followup_email",
        return_value={"subject": "Re: X", "body": "body"},
    )

    import followups
    followups.run_followup_cycle()

    mock_build.assert_called_once()
    assert mock_build.call_args[0][1] == 1  # followup_num=1


def test_round2_sends_template_2(mocker, fresh_db):
    """Second follow-up should call build_followup_email with followup_num=2."""
    _in_window(mocker)
    _contacted_lead(fresh_db, days_ago=6, followup_count=1)
    _mock_send_ok(mocker)
    mock_build = mocker.patch(
        "followups.messaging.build_followup_email",
        return_value={"subject": "Re: X", "body": "body"},
    )

    import followups
    followups.run_followup_cycle()

    mock_build.assert_called_once()
    assert mock_build.call_args[0][1] == 2


def test_round3_sends_template_3(mocker, fresh_db):
    """Third follow-up should call build_followup_email with followup_num=3."""
    _in_window(mocker)
    _contacted_lead(fresh_db, days_ago=10, followup_count=2)
    _mock_send_ok(mocker)
    mock_build = mocker.patch(
        "followups.messaging.build_followup_email",
        return_value={"subject": "Re: X", "body": "body"},
    )

    import followups
    followups.run_followup_cycle()

    mock_build.assert_called_once()
    assert mock_build.call_args[0][1] == 3


# ── auto-close after round 3 ─────────────────────────────────────────────────

def test_auto_close_after_round3(mocker, fresh_db):
    """After the 3rd follow-up is sent, the lead should be marked 'closed'."""
    _in_window(mocker)
    lead_id = _contacted_lead(fresh_db, days_ago=10, followup_count=2)
    _mock_send_ok(mocker)
    mocker.patch(
        "followups.messaging.build_followup_email",
        return_value={"subject": "Re: X", "body": "body"},
    )

    import followups
    followups.run_followup_cycle()

    closed = fresh_db.get_leads_by_status("closed")
    assert len(closed) == 1
    assert closed[0]["id"] == lead_id


def test_no_close_after_round1(mocker, fresh_db):
    """After round 1, the lead should NOT be closed."""
    _in_window(mocker)
    lead_id = _contacted_lead(fresh_db, days_ago=3, followup_count=0)
    _mock_send_ok(mocker)
    mocker.patch(
        "followups.messaging.build_followup_email",
        return_value={"subject": "Re: X", "body": "body"},
    )

    import followups
    followups.run_followup_cycle()

    closed = fresh_db.get_leads_by_status("closed")
    assert len(closed) == 0


def test_failed_send_does_not_close(mocker, fresh_db):
    """If the 3rd send fails, the lead should NOT be closed (retried next cycle)."""
    _in_window(mocker)
    _contacted_lead(fresh_db, days_ago=10, followup_count=2)
    mocker.patch("followups.emailer.send_email", return_value=False)
    mocker.patch(
        "followups.messaging.build_followup_email",
        return_value={"subject": "Re: X", "body": "body"},
    )

    import followups
    result = followups.run_followup_cycle()

    assert result == 0
    closed = fresh_db.get_leads_by_status("closed")
    assert len(closed) == 0
