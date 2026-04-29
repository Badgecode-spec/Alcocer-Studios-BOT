import anthropic

import config
from logger import get_logger

log = get_logger(__name__)

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

DEFAULT_AI_LINE = "Vi que su presencia en línea tiene áreas de mejora que les están costando clientes potenciales."

# Lead immediately with the observation — no intro paragraph, direct CTA
_OUTREACH_TEMPLATE = """\
Hola {name},

{ai_line}

En Alcocer Studios creamos páginas web que convierten visitas en clientes reales, especialmente desde celular. ¿Tienen 15 minutos esta semana para una llamada rápida?

Pueden responder este correo, llamarnos al (55) 2880-9044 o ver nuestro trabajo en alcocerstudios.com

Pablo Alcocer — Alcocer Studios\
"""

# Round 1 — soft check-in, very short
_FOLLOWUP_1_TEMPLATE = """\
Hola {name},

Les escribí hace un par de días — quería asegurarme de que les llegó. ¿Pudieron verlo?

Si no es el momento, sin problema. Si les interesa platicar sobre cómo podríamos ayudarles a conseguir más clientes, aquí estoy.

Pablo Alcocer — Alcocer Studios | (55) 2880-9044\
"""

# Round 2 — different angle, quantifies the cost of a weak web presence
_FOLLOWUP_2_TEMPLATE = """\
Hola {name},

Quería compartirles algo concreto: la mayoría de negocios en su categoría pierden entre 3 y 5 clientes nuevos por semana por no tener una página web optimizada para celular — que es donde más del 80% de la gente busca hoy en día.

¿Podríamos hablar 10 minutos esta semana? Sin ningún compromiso.

Pablo Alcocer — Alcocer Studios | (55) 2880-9044 | alcocerstudios.com\
"""

# Round 3 — brief closing, leaves door open, no pressure
_FOLLOWUP_3_TEMPLATE = """\
Hola {name},

Último mensaje de mi parte — no quiero molestarles. Si en algún momento les interesa hablar sobre cómo conseguir más clientes a través de su página web, aquí estoy.

Que les vaya muy bien.

Pablo Alcocer — Alcocer Studios | (55) 2880-9044\
"""

_FOLLOWUP_TEMPLATES = {
    1: _FOLLOWUP_1_TEMPLATE,
    2: _FOLLOWUP_2_TEMPLATE,
    3: _FOLLOWUP_3_TEMPLATE,
}


def generate_ai_line(name: str, website: str, category: str) -> str:
    """Call Claude Haiku for a single personalized sentence (~50 input tokens)."""
    prompt = (
        f"Negocio: {name}. Sitio web: {website}. Categoría: {category}. "
        "Escribe UNA sola oración en español formal (de ustedes, dirigiéndote al equipo del negocio) que identifique de forma específica "
        "el problema digital de este negocio — ya sea que su página web se ve mal en celular, "
        "no tiene página web, no aparece en Google, o no transmite confianza. "
        "Menciona el nombre del negocio. Solo la oración, sin saludos ni explicaciones. "
        "Usa únicamente palabras reales del español; nunca inventes palabras. "
        "Si mencionas una dirección web, llámala 'dirección web' o 'enlace', nunca 'URL'."
    )
    try:
        response = _client.messages.create(
            model=config.HAIKU_MODEL,
            max_tokens=config.HAIKU_MAX_TOKENS,
            system="Eres un asistente de ventas conciso. Responde solo con una oración corta en español estándar correcto, sin inventar palabras.",
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
        "subject": f"Duda para {display_name}",
        "body": body,
        "ai_line": ai_line,
    }


def build_followup_email(name: str, followup_num: int = 1) -> dict:
    """
    Returns {"subject": str, "body": str}.
    followup_num: 1 (first follow-up), 2 (second), or 3 (closing).
    No AI call — static templates differentiated by round.
    """
    display_name = name or "amigo"
    template = _FOLLOWUP_TEMPLATES.get(followup_num, _FOLLOWUP_1_TEMPLATE)
    body = template.format(name=display_name)
    return {
        "subject": f"Re: Duda para {display_name}",
        "body": body,
    }
