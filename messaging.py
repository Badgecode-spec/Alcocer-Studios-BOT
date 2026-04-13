import anthropic

import config
from logger import get_logger

log = get_logger(__name__)

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

DEFAULT_AI_LINE = "Con lo que vi, hay una oportunidad clara de mejorar la experiencia en móvil."

_OUTREACH_TEMPLATE = """\
Hola {name},
Vi tu página y hay un par de cosas que están haciendo que pierdas clientes (sobre todo en celular).

{ai_line}

Te dejo esto:
https://alcocerstudios.com

Si te hace sentido, lo vemos.\
"""

_FOLLOWUP_TEMPLATE = """\
Hola {name},
Solo quería asegurarme de que recibiste mi mensaje anterior.

Si todavía no has tenido chance de ver tu página, con gusto te muestro lo que encontré.

https://alcocerstudios.com

Saludos.\
"""


def generate_ai_line(name: str, website: str, category: str) -> str:
    """Call Claude Haiku for a single personalized sentence (~50 input tokens)."""
    prompt = (
        f"Negocio: {name}. Sitio: {website}. Categoría: {category}. "
        "Escribe UNA oración corta en español que mencione algo específico sobre su negocio "
        "que sugiera por qué pueden estar perdiendo clientes en móvil. "
        "Solo la oración, sin explicaciones."
    )
    try:
        response = _client.messages.create(
            model=config.HAIKU_MODEL,
            max_tokens=config.HAIKU_MAX_TOKENS,
            system="Eres un asistente de ventas conciso. Responde solo con una oración corta en español.",
            messages=[{"role": "user", "content": prompt}],
        )
        line = response.content[0].text.strip()
        # Take only the first sentence in case model returns more
        if "." in line:
            line = line.split(".")[0].strip() + "."
        log.info("haiku_call name=%r tokens_in≈50 tokens_out=%d", name, len(line.split()))
        return line
    except Exception as exc:
        log.warning("Haiku API error for %r: %s — using default line", name, exc)
        return DEFAULT_AI_LINE


def build_outreach_email(name: str, website: str, category: str) -> dict:
    """Returns {"subject": str, "body": str, "ai_line": str}."""
    display_name = name or "amigo"
    ai_line = generate_ai_line(display_name, website, category)
    body = _OUTREACH_TEMPLATE.format(name=display_name, ai_line=ai_line)
    return {
        "subject": f"Tu página web, {display_name}",
        "body": body,
        "ai_line": ai_line,
    }


def build_followup_email(name: str) -> dict:
    """Returns {"subject": str, "body": str}. No AI call."""
    display_name = name or "amigo"
    body = _FOLLOWUP_TEMPLATE.format(name=display_name)
    return {
        "subject": f"Re: Tu página web, {display_name}",
        "body": body,
    }
