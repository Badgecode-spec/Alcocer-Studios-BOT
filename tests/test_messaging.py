"""Tests for messaging.py with mocked Anthropic client."""
import pytest
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def _patch_anthropic(monkeypatch):
    """Prevent real Anthropic API calls by patching the module-level client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Línea IA simulada.")]
    mock_client.messages.create.return_value = mock_response

    import messaging
    monkeypatch.setattr(messaging, "_client", mock_client)
    return mock_client


# ── build_outreach_email ─────────────────────────────────────────────────────

def test_build_outreach_email_subject():
    """Subject of outreach email should start with 'Duda para'."""
    import messaging
    result = messaging.build_outreach_email("Barbería Cool", "https://barb.com", "barberia")
    assert result["subject"].startswith("Duda para")


def test_build_outreach_email_body_contains_name():
    """Body of outreach email should contain the business name."""
    import messaging
    result = messaging.build_outreach_email("Barbería Cool", "https://barb.com", "barberia")
    assert "Barbería Cool" in result["body"]


def test_build_outreach_email_body_uses_ustedes():
    """Body should use 'tienen' (ustedes form, not tú)."""
    import messaging
    result = messaging.build_outreach_email("Spa Lux", "https://spalux.com", "spa")
    assert "tienen" in result["body"].lower()


def test_build_outreach_email_has_ai_line():
    """Result dict should contain 'ai_line' key with a non-empty string."""
    import messaging
    result = messaging.build_outreach_email("Cafetería XYZ", "https://cafe.com", "cafeteria")
    assert "ai_line" in result
    assert isinstance(result["ai_line"], str)
    assert len(result["ai_line"]) > 0


def test_build_outreach_email_leads_with_ai_observation():
    """New shorter template: the AI line should appear near the top of the body."""
    import messaging
    result = messaging.build_outreach_email("Spa Lux", "https://spalux.com", "spa")
    body = result["body"]
    ai_pos = body.find("Línea IA simulada.")
    # AI line should be in the first 200 chars (right after the greeting)
    assert ai_pos != -1 and ai_pos < 200


# ── build_followup_email ─────────────────────────────────────────────────────

def test_build_followup_email_subject():
    """Subject of follow-up email should start with 'Re: Duda para'."""
    import messaging
    result = messaging.build_followup_email("Salón Bello")
    assert result["subject"].startswith("Re: Duda para")


def test_build_followup_email_body_contains_name():
    """Body of all follow-up rounds should contain the business name."""
    import messaging
    for num in (1, 2, 3):
        result = messaging.build_followup_email("Salón Bello", num)
        assert "Salón Bello" in result["body"], f"round {num} missing name"


def test_followup_templates_are_distinct():
    """Each follow-up round should produce a different body text."""
    import messaging
    bodies = [messaging.build_followup_email("X", n)["body"] for n in (1, 2, 3)]
    assert bodies[0] != bodies[1]
    assert bodies[1] != bodies[2]
    assert bodies[0] != bodies[2]


def test_followup_round3_is_short():
    """Round 3 closing email should be brief (under 400 chars)."""
    import messaging
    result = messaging.build_followup_email("Negocio", 3)
    assert len(result["body"]) < 400


def test_followup_default_round_is_1():
    """build_followup_email with no round arg should return round-1 template."""
    import messaging
    assert messaging.build_followup_email("X") == messaging.build_followup_email("X", 1)


# ── generate_ai_line ─────────────────────────────────────────────────────────

def test_generate_ai_line_returns_default_on_api_error(monkeypatch):
    """When Anthropic raises an exception, generate_ai_line should return DEFAULT_AI_LINE."""
    import messaging
    failing_client = MagicMock()
    failing_client.messages.create.side_effect = Exception("API unavailable")
    monkeypatch.setattr(messaging, "_client", failing_client)

    result = messaging.generate_ai_line("Spa Test", "https://spa.com", "spa")
    assert result == messaging.DEFAULT_AI_LINE
