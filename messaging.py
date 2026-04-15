import anthropic

import config
from logger import get_logger

log = get_logger(__name__)

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

DEFAULT_AI_LINE = "Vi que su presencia en línea tiene áreas de mejora que les están costando clientes potenciales."

_OUTREACH_TEMPLATE = """\
Hola {name},

Mi nombre es Pablo, de Alcocer Studios. Espero que todo esté yendo muy bien por allá.

{ai_line}

En Alcocer Studios nos especializamos en crear páginas web profesionales, rápidas y diseñadas para convertir visitas en clientes reales — especialmente desde celular, que es donde la mayoría de la gente busca hoy en día.

Si le interesa saber más, puede visitar nuestra página donde encontrará ejemplos de nuestro trabajo y toda la información:
https://alcocerstudios.com

O si prefiere, con gusto lo platicamos directamente — puede responder este correo, escribirnos a alcocerstudios@yahoo.com o llamarnos al (55) 2880-9044.

Quedo a sus órdenes.

Atentamente,

Pablo Alcocer
Fundador — Alcocer Studios
─────────────────────────
Tel:     (55) 2880-9044
Correo:  alcocerstudios@yahoo.com
Web:     alcocerstudios.com\
"""

_FOLLOWUP_TEMPLATE = """\
Hola {name},

Le escribo nuevamente de Alcocer Studios — soy Pablo.

Quería asegurarme de que recibió mi mensaje anterior. Entiendo que el tiempo es valioso, por eso seré breve: encontramos algunas oportunidades concretas en su presencia digital que podrían traerle más clientes.

Si gusta, con mucho gusto le platicamos sin ningún compromiso. Puede responder este correo, escribirnos a alcocerstudios@yahoo.com o llamarnos directamente al (55) 2880-9044.

También puede ver nuestro trabajo en:
https://alcocerstudios.com

Atentamente,

Pablo Alcocer
Fundador — Alcocer Studios
─────────────────────────
Tel:     (55) 2880-9044
Correo:  alcocerstudios@yahoo.com
Web:     alcocerstudios.com\
"""


def generate_ai_line(name: str, website: str, category: str) -> str:
    """Call Claude Haiku for a single personalized sentence (~50 input tokens)."""
    prompt = (
        f"Negocio: {name}. Sitio web: {website}. Categoría: {category}. "
        "Escribe UNA sola oración en español formal (de usted) que identifique de forma específica "
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


def build_followup_email(name: str) -> dict:
    """Returns {"subject": str, "body": str}. No AI call."""
    display_name = name or "amigo"
    body = _FOLLOWUP_TEMPLATE.format(name=display_name)
    return {
        "subject": f"Re: Tu página web, {display_name}",
        "body": body,
    }
