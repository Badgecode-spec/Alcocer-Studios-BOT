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
HAIKU_MAX_TOKENS: int = 60
SONNET_MAX_TOKENS: int = 200

# === Scheduler ===
LOOP_INTERVAL_SECONDS: int = int(_optional("LOOP_INTERVAL_SECONDS", "3600"))

# === Follow-up ===
FOLLOWUP_DAYS: int = int(_optional("FOLLOWUP_DAYS", "3"))

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
_raw_queries = _optional(
    "OUTSCRAPER_QUERIES",
    # Tourist cities — high web-search intent
    "spa en Cancun,salon de belleza en Cancun,barberia en Cancun,cafeteria en Cancun,"
    "spa en Tulum,salon de belleza en Tulum,barberia en Tulum,cafeteria en Tulum,"
    "spa en Puerto Vallarta,salon de belleza en Puerto Vallarta,barberia en Puerto Vallarta,"
    "estudio de pilates en Puerto Vallarta,cafeteria en Puerto Vallarta,"
    "spa en Acapulco,salon de belleza en Acapulco,"
    # Major cities — volume
    "spa en Ciudad de Mexico,salon de belleza en Ciudad de Mexico,"
    "barberia en Ciudad de Mexico,estudio de pilates en Ciudad de Mexico,"
    "gimnasio en Ciudad de Mexico,cafeteria en Ciudad de Mexico,"
    "spa en Guadalajara,salon de belleza en Guadalajara,barberia en Guadalajara,"
    "gimnasio en Guadalajara,estudio de pilates en Guadalajara,"
    "spa en Monterrey,salon de belleza en Monterrey,barberia en Monterrey,"
    "gimnasio en Monterrey",
)
OUTSCRAPER_QUERIES: list[str] = [q.strip() for q in _raw_queries.split(",") if q.strip()]
OUTSCRAPER_LIMIT: int = int(_optional("OUTSCRAPER_LIMIT", "5"))

# === IMAP (Zoho reply detection) ===
ZOHO_IMAP_EMAIL: str = _optional("ZOHO_IMAP_EMAIL", "")
ZOHO_APP_PASSWORD: str = _optional("ZOHO_APP_PASSWORD", "")
IMAP_HOST: str = "imap.zoho.com"
IMAP_PORT: int = 993

# === Email send pacing ===
EMAIL_SEND_DELAY: float = float(_optional("EMAIL_SEND_DELAY", "2.0"))
