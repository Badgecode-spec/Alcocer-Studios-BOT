"""Tests for imap_checker.py."""
import pytest
from unittest.mock import MagicMock, patch


# ── is_optout ────────────────────────────────────────────────────────────────

def test_is_optout_detects_spanish_keywords():
    """Known opt-out phrase should return True."""
    import imap_checker
    assert imap_checker.is_optout("Por favor no me contactes más.") is True


def test_is_optout_multiple_keywords():
    """Multiple opt-out keywords in text should still return True."""
    import imap_checker
    assert imap_checker.is_optout("Quiero dar de baja mi suscripción y no molestar.") is True


def test_is_optout_unsubscribe_english():
    """English 'unsubscribe' keyword should also trigger opt-out."""
    import imap_checker
    assert imap_checker.is_optout("Please unsubscribe me from this list.") is True


def test_is_optout_false_for_normal_reply():
    """A genuine interested reply should NOT trigger opt-out."""
    import imap_checker
    assert imap_checker.is_optout("Gracias, me interesa mucho su propuesta.") is False


def test_is_optout_case_insensitive():
    """Opt-out detection should be case-insensitive."""
    import imap_checker
    assert imap_checker.is_optout("NO ME CONTACTES") is True


# ── _decode_value ────────────────────────────────────────────────────────────

def test_decode_bytes_value():
    """Bytes should be decoded to a UTF-8 string."""
    import imap_checker
    result = imap_checker._decode_value("Hola mundo".encode("utf-8"))
    assert result == "Hola mundo"


def test_decode_str_value():
    """A plain string should pass through unchanged."""
    import imap_checker
    result = imap_checker._decode_value("already a string")
    assert result == "already a string"


def test_decode_value_none():
    """None should return empty string."""
    import imap_checker
    result = imap_checker._decode_value(None)
    assert result == ""


# ── run_imap_check no-op when credentials missing ────────────────────────────

def test_run_imap_check_returns_zero_when_no_credentials(monkeypatch):
    """run_imap_check should return 0 immediately when credentials are not set."""
    import config
    monkeypatch.setattr(config, "ZOHO_IMAP_EMAIL", "")
    monkeypatch.setattr(config, "ZOHO_APP_PASSWORD", "")
    import imap_checker
    result = imap_checker.run_imap_check()
    assert result == 0


def test_run_imap_check_returns_zero_when_only_email_set(monkeypatch):
    """run_imap_check should return 0 when only the email is set (no password)."""
    import config
    monkeypatch.setattr(config, "ZOHO_IMAP_EMAIL", "hola@example.com")
    monkeypatch.setattr(config, "ZOHO_APP_PASSWORD", "")
    import imap_checker
    result = imap_checker.run_imap_check()
    assert result == 0


def test_run_imap_check_handles_connection_error(monkeypatch):
    """run_imap_check should return 0 gracefully when IMAP connection fails."""
    import imaplib
    import config
    monkeypatch.setattr(config, "ZOHO_IMAP_EMAIL", "hola@example.com")
    monkeypatch.setattr(config, "ZOHO_APP_PASSWORD", "secret")

    with patch("imaplib.IMAP4_SSL", side_effect=imaplib.IMAP4.error("connection refused")):
        import imap_checker
        result = imap_checker.run_imap_check()
    assert result == 0
