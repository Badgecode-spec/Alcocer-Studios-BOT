import os
import sys
import pytest


# ---------------------------------------------------------------------------
# Provide stub values for required environment variables so that config.py
# does not raise RuntimeError on import (which happens before monkeypatch
# can apply).  These dummy values only affect the test process.
# ---------------------------------------------------------------------------
_REQUIRED_STUBS = {
    "OUTSCRAPER_API_KEY": "test-outscraper-key",
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "RESEND_API_KEY": "test-resend-key",
    "FROM_EMAIL": "test@example.com",
}
for _k, _v in _REQUIRED_STUBS.items():
    os.environ.setdefault(_k, _v)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def fresh_db(db_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", db_path)
    # Patch config.DB_PATH directly
    import config
    monkeypatch.setattr(config, "DB_PATH", db_path)
    import db
    # Force re-init with the temp path
    db.init_db()
    yield db
