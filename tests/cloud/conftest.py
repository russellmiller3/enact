import pytest
import os
import sys

# Ensure cloud/ is importable from tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

os.environ.setdefault("CLOUD_SECRET", "test-cloud-secret-for-unit-tests-only")
os.environ.setdefault("ENACT_EMAIL_DRY_RUN", "1")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Each test gets a fresh SQLite DB in a temp dir.
    db.py reads ENACT_DB_PATH fresh on each get_connection() call,
    so monkeypatch.setenv is sufficient — no module reload needed.
    Also clears the in-memory rate limiter bucket so POST-heavy test
    suites don't exhaust the 60-req/min limit across tests.
    """
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("ENACT_DB_PATH", db_path)
    from cloud.db import init_db
    from cloud import main as cloud_main
    cloud_main._rate_buckets.clear()
    init_db()
    yield
