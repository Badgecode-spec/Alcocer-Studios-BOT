import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


# === API Keys ===
OUTSCRAPER_API_KEY: str = _require("OUTSCRAPER_API_KEY")
ANTHROPIC_API_KEY: str = _require("ANTHROPIC_API_KEY")
RESEND_API_KEY: str = _require("RESEND_API_KEY")

# === Claude Models ===
HAIKU_MODEL: str = "claude-haiku-4-5-20251001"
SONNET_MODEL: str = "claude-sonnet-4-6"
HAIKU_MAX_TOKENS: int = 80
SONNET_MAX_TOKENS: int = 200

# === Scheduler ===
LOOP_INTERVAL_SECONDS: int = int(_optional("LOOP_INTERVAL_SECONDS", "3600"))

# === Follow-up ===
FOLLOWUP_DAYS: int = int(_optional("FOLLOWUP_DAYS", "2"))

# === Reply simulation ===
REPLY_SIMULATION_CHANCE: float = float(_optional("REPLY_SIMULATION_CHANCE", "0"))

# === Email sender ===
FROM_EMAIL: str = _require("FROM_EMAIL")
FROM_NAME: str = _optional("FROM_NAME", "Alcocer Studios")

# === Safety cap ===
DAILY_SEND_LIMIT: int = int(_optional("DAILY_SEND_LIMIT", "50"))

# === Telegram ===
TELEGRAM_BOT_TOKEN: str = _optional("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = _optional("TELEGRAM_CHAT_ID", "")

# === Paths ===
DB_PATH: str = _optional("DB_PATH", "bot.db")
LOG_FILE: str = _optional("LOG_FILE", "bot.log")

# === Outscraper ===
# 90 queries across 22 Mexican cities × 4-6 categories = ~900 fresh results/day at limit=10.
# Override OUTSCRAPER_QUERIES in Railway to customise without a redeploy.
_raw_queries = _optional(
    "OUTSCRAPER_QUERIES",
    # ── Tourist / coastal cities ──────────────────────────────────────────────
    "spa en Cancun,salon de belleza en Cancun,barberia en Cancun,cafeteria en Cancun,"
    "estudio de pilates en Cancun,gimnasio en Cancun,"
    "spa en Tulum,salon de belleza en Tulum,barberia en Tulum,cafeteria en Tulum,"
    "spa en Puerto Vallarta,salon de belleza en Puerto Vallarta,barberia en Puerto Vallarta,"
    "estudio de pilates en Puerto Vallarta,cafeteria en Puerto Vallarta,"
    "spa en Playa del Carmen,salon de belleza en Playa del Carmen,barberia en Playa del Carmen,cafeteria en Playa del Carmen,"
    "spa en Cabo San Lucas,salon de belleza en Cabo San Lucas,cafeteria en Cabo San Lucas,"
    "spa en Mazatlan,salon de belleza en Mazatlan,barberia en Mazatlan,cafeteria en Mazatlan,"
    "spa en Acapulco,salon de belleza en Acapulco,barberia en Acapulco,"
    "spa en Huatulco,salon de belleza en Huatulco,cafeteria en Huatulco,"
    "spa en Puerto Escondido,salon de belleza en Puerto Escondido,cafeteria en Puerto Escondido,"
    "spa en Manzanillo,salon de belleza en Manzanillo,cafeteria en Manzanillo,"
    # ── Colonial / cultural cities ────────────────────────────────────────────
    "spa en San Miguel de Allende,salon de belleza en San Miguel de Allende,cafeteria en San Miguel de Allende,"
    "spa en Guanajuato,salon de belleza en Guanajuato,barberia en Guanajuato,cafeteria en Guanajuato,"
    "spa en Oaxaca,salon de belleza en Oaxaca,barberia en Oaxaca,cafeteria en Oaxaca,"
    "spa en Morelia,salon de belleza en Morelia,barberia en Morelia,cafeteria en Morelia,"
    "spa en Taxco,salon de belleza en Taxco,cafeteria en Taxco,"
    "spa en San Cristobal de las Casas,salon de belleza en San Cristobal de las Casas,cafeteria en San Cristobal de las Casas,"
    # ── Major cities ─────────────────────────────────────────────────────────
    "spa en Ciudad de Mexico,salon de belleza en Ciudad de Mexico,"
    "barberia en Ciudad de Mexico,estudio de pilates en Ciudad de Mexico,"
    "gimnasio en Ciudad de Mexico,cafeteria en Ciudad de Mexico,"
    "spa en Guadalajara,salon de belleza en Guadalajara,barberia en Guadalajara,"
    "gimnasio en Guadalajara,estudio de pilates en Guadalajara,cafeteria en Guadalajara,"
    "spa en Monterrey,salon de belleza en Monterrey,barberia en Monterrey,"
    "gimnasio en Monterrey,estudio de pilates en Monterrey,cafeteria en Monterrey,"
    "spa en Puebla,salon de belleza en Puebla,barberia en Puebla,"
    "gimnasio en Puebla,cafeteria en Puebla,"
    "spa en Leon,salon de belleza en Leon,barberia en Leon,gimnasio en Leon,cafeteria en Leon,"
    "spa en Merida,salon de belleza en Merida,barberia en Merida,gimnasio en Merida,cafeteria en Merida,"
    "spa en Queretaro,salon de belleza en Queretaro,barberia en Queretaro,estudio de pilates en Queretaro,cafeteria en Queretaro,"
    "spa en San Luis Potosi,salon de belleza en San Luis Potosi,barberia en San Luis Potosi,cafeteria en San Luis Potosi,"
    "spa en Tijuana,salon de belleza en Tijuana,barberia en Tijuana,cafeteria en Tijuana,"
    "spa en Hermosillo,salon de belleza en Hermosillo,barberia en Hermosillo,cafeteria en Hermosillo,"
    "spa en Aguascalientes,salon de belleza en Aguascalientes,barberia en Aguascalientes,cafeteria en Aguascalientes,"
    "spa en Toluca,salon de belleza en Toluca,barberia en Toluca,cafeteria en Toluca,"
    "spa en Chihuahua,salon de belleza en Chihuahua,barberia en Chihuahua,cafeteria en Chihuahua,"
    "spa en Culiacan,salon de belleza en Culiacan,barberia en Culiacan,cafeteria en Culiacan,"
    "spa en Veracruz,salon de belleza en Veracruz,barberia en Veracruz,cafeteria en Veracruz,"
    "spa en Saltillo,salon de belleza en Saltillo,barberia en Saltillo,cafeteria en Saltillo,"
    "spa en Villahermosa,salon de belleza en Villahermosa,cafeteria en Villahermosa",
)
OUTSCRAPER_QUERIES: list[str] = [q.strip() for q in _raw_queries.split(",") if q.strip()]
OUTSCRAPER_LIMIT: int = int(_optional("OUTSCRAPER_LIMIT", "10"))

# === IMAP (Zoho reply detection) ===
ZOHO_IMAP_EMAIL: str = _optional("ZOHO_IMAP_EMAIL", "")
ZOHO_APP_PASSWORD: str = _optional("ZOHO_APP_PASSWORD", "")
IMAP_HOST: str = "imap.zoho.com"
IMAP_PORT: int = 993

# === Email send pacing ===
EMAIL_SEND_DELAY: float = float(_optional("EMAIL_SEND_DELAY", "2.0"))
