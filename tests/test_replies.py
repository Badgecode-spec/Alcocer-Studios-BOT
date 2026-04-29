"""Tests for replies.py."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def _patch_anthropic(monkeypatch):
    """Prevent real Anthropic API calls in replies.py."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Respuesta simulada de Sonnet.")]
    mock_client.messages.create.return_value = mock_response
    import replies
    monkeypatch.setattr(replies, "_client", mock_client)


# ── classify_reply ────────────────────────────────────────────────────────────

def test_classify_reply_short_is_simple():
    """A reply with fewer than 15 words should be classified as simple (False)."""
    import replies
    assert replies.classify_reply("Sí, me interesa") is False


def test_classify_reply_long_is_complex():
    """A reply with more than 15 words should be classified as complex (True)."""
    import replies
    long_text = "Ya tenemos una agencia que nos lleva el sitio y realmente estamos bastante satisfechos con ella actualmente"
    assert replies.classify_reply(long_text) is True


def test_classify_reply_complex_template_is_complex():
    """A known complex template should always be classified as complex."""
    import replies
    template = replies.COMPLEX_REPLY_TEMPLATES[0]
    assert replies.classify_reply(template) is True


def test_classify_reply_exactly_15_words_is_simple():
    """A reply of exactly 15 words should NOT be complex (needs >15)."""
    import replies
    fifteen_words = " ".join(["palabra"] * 15)
    assert replies.classify_reply(fifteen_words) is False


def test_classify_reply_16_words_is_complex():
    """A reply of exactly 16 words should be classified as complex."""
    import replies
    sixteen_words = " ".join(["palabra"] * 16)
    assert replies.classify_reply(sixteen_words) is True


# ── run_reply_cycle ───────────────────────────────────────────────────────────

def test_run_reply_cycle_returns_zero_when_simulation_off(monkeypatch, fresh_db):
    """run_reply_cycle should return 0 immediately when REPLY_SIMULATION_CHANCE <= 0."""
    import config
    import replies
    monkeypatch.setattr(config, "REPLY_SIMULATION_CHANCE", 0.0)
    result = replies.run_reply_cycle()
    assert result == 0


def test_run_reply_cycle_returns_zero_when_no_candidates(monkeypatch, fresh_db):
    """run_reply_cycle should return 0 when no contacted/followup leads exist."""
    import config
    import replies
    monkeypatch.setattr(config, "REPLY_SIMULATION_CHANCE", 1.0)
    # fresh_db has no leads, so no candidates
    result = replies.run_reply_cycle()
    assert result == 0


# ── build_reply_email ────────────────────────────────────────────────────────

def test_build_reply_email_subject_format():
    """Reply email subject should start with 'Re: Duda para'."""
    import replies
    result = replies.build_reply_email("Ana García", "¿Cuánto cuesta?")
    assert result["subject"].startswith("Re: Duda para")


def test_build_reply_email_simple_does_not_use_sonnet(monkeypatch):
    """A short (simple) reply should not call Sonnet (used_sonnet=False)."""
    import replies
    result = replies.build_reply_email("Ana García", "¿Cuánto cuesta?")
    assert result["used_sonnet"] is False


def test_build_reply_email_complex_uses_sonnet(monkeypatch):
    """A long (complex) reply should use Sonnet (used_sonnet=True)."""
    import replies
    long_reply = "Ya tenemos una agencia que nos lleva el sitio y queremos saber qué diferencia tienen ustedes con ella en términos de precio y calidad"
    result = replies.build_reply_email("Carlos Biz", long_reply)
    assert result["used_sonnet"] is True
