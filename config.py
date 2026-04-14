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
REPLY_SIMULATION_CHANCE: float = float(_optional("REPLY_SIMULATION_CHANCE", "0.15"))

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
    "restaurantes en Ciudad de Mexico,salones de belleza en CDMX,"
    "talleres mecanicos en Guadalajara,dentistas en Monterrey,"
    "plomeros en Puebla,contadores en Guadalajara,"
    "veterinarias en Ciudad de Mexico,gimnasios en CDMX",
)
OUTSCRAPER_QUERIES: list[str] = [q.strip() for q in _raw_queries.split(",") if q.strip()]
OUTSCRAPER_LIMIT: int = int(_optional("OUTSCRAPER_LIMIT", "20"))
