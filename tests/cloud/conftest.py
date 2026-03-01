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
    """
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("ENACT_DB_PATH", db_path)
    from cloud.db import init_db
    init_db()
    yield
