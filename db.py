import sqlite3
from datetime import datetime, timezone

import config
from logger import get_logger

log = get_logger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS leads (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    website             TEXT NOT NULL,
    email               TEXT NOT NULL UNIQUE,
    phone               TEXT,
    address             TEXT,
    category            TEXT,
    query_used          TEXT,
    status              TEXT NOT NULL DEFAULT 'new'
                            CHECK(status IN ('new','contacted','followup','replied','closed')),
    outreach_sent_at    TEXT,
    followup_sent_at    TEXT,
    replied_at          TEXT,
    ai_line_used        TEXT,
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_outreach_sent_at ON leads(outreach_sent_at);

CREATE TABLE IF NOT EXISTS bot_state (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS send_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id     INTEGER NOT NULL REFERENCES leads(id),
    send_type   TEXT NOT NULL CHECK(send_type IN ('outreach','followup','reply')),
    sent_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    success     INTEGER NOT NULL DEFAULT 1,
    error_msg   TEXT
);

CREATE INDEX IF NOT EXISTS idx_send_log_sent_at ON send_log(sent_at);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(_DDL)
    log.info("Database initialized: %s", config.DB_PATH)


def upsert_lead(lead_data: dict) -> int:
    """Insert lead if email not already in DB. Returns the lead id."""
    sql = """
        INSERT OR IGNORE INTO leads
            (name, website, email, phone, address, category, query_used)
        VALUES
            (:name, :website, :email, :phone, :address, :category, :query_used)
    """
    with get_connection() as conn:
        conn.execute(sql, lead_data)
        row = conn.execute("SELECT id FROM leads WHERE email = ?", (lead_data["email"],)).fetchone()
        return row["id"]


def get_leads_by_status(status: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM leads WHERE status = ?", (status,)).fetchall()


def get_leads_due_for_followup(days: int) -> list[sqlite3.Row]:
    sql = """
        SELECT * FROM leads
        WHERE status = 'contacted'
          AND outreach_sent_at < datetime('now', ? || ' days')
          AND followup_sent_at IS NULL
    """
    with get_connection() as conn:
        return conn.execute(sql, (f"-{days}",)).fetchall()


def update_lead_status(lead_id: int, status: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE leads SET status = ? WHERE id = ?", (status, lead_id))


def update_lead_outreach_sent(lead_id: int, ai_line: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with get_connection() as conn:
        conn.execute(
            "UPDATE leads SET status='contacted', outreach_sent_at=?, ai_line_used=? WHERE id=?",
            (now, ai_line, lead_id),
        )


def update_lead_followup_sent(lead_id: int) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with get_connection() as conn:
        conn.execute(
            "UPDATE leads SET status='followup', followup_sent_at=? WHERE id=?",
            (now, lead_id),
        )


def update_lead_replied(lead_id: int, notes: str = "") -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with get_connection() as conn:
        conn.execute(
            "UPDATE leads SET status='replied', replied_at=?, notes=? WHERE id=?",
            (now, notes, lead_id),
        )


def log_send(lead_id: int, send_type: str, success: bool, error_msg: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO send_log (lead_id, send_type, success, error_msg) VALUES (?,?,?,?)",
            (lead_id, send_type, 1 if success else 0, error_msg),
        )


def count_sends_today() -> int:
    # Use CDMX calendar date (UTC-6) so "today" matches Mexico City, not UTC
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM send_log "
            "WHERE date(datetime(sent_at, '-6 hours')) = date(datetime('now', '-6 hours')) "
            "AND success=1"
        ).fetchone()
        return row[0]


def email_exists(email: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM leads WHERE email=?", (email,)).fetchone()
        return row is not None


def get_state(key: str) -> str:
    """Get a persistent bot state value (survives restarts)."""
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM bot_state WHERE key=?", (key,)).fetchone()
        return row["value"] if row else ""


def set_state(key: str, value: str) -> None:
    """Persist a bot state value to the database."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO bot_state (key, value) VALUES (?,?)",
            (key, value),
        )


def get_lead_by_email(email: str) -> sqlite3.Row | None:
    """Look up a lead by their email address (case-insensitive)."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM leads WHERE lower(email)=lower(?)", (email.strip(),)
        ).fetchone()


def claim_lead_for_outreach(lead_id: int) -> bool:
    """
    Atomically flip a lead from 'new' → 'contacted' to claim it for sending.
    Returns True only if this call won — another thread already claimed it returns False.
    This prevents duplicate outreach when /sendnow and the main loop overlap.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE leads SET status='contacted' WHERE id=? AND status='new'",
            (lead_id,),
        )
        return cursor.rowcount == 1


def close_lead(lead_id: int, notes: str = "") -> None:
    """Mark a lead as closed (opted out, unresponsive, etc.)."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE leads SET status='closed', notes=? WHERE id=?",
            (notes, lead_id),
        )


def get_weekly_stats() -> dict:
    """Stats for the last 7 CDMX calendar days."""
    with get_connection() as conn:
        sent_7d = conn.execute(
            "SELECT COUNT(*) FROM send_log "
            "WHERE date(datetime(sent_at,'-6 hours')) >= date(datetime('now','-6 hours','-6 days')) "
            "AND success=1"
        ).fetchone()[0]
        counts = {}
        for status in ("new", "contacted", "followup", "replied", "closed"):
            counts[status] = conn.execute(
                "SELECT COUNT(*) FROM leads WHERE status=?", (status,)
            ).fetchone()[0]
        counts["total"] = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        counts["sent_7d"] = sent_7d
        return counts
