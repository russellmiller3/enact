import hashlib
import pytest
from fastapi.testclient import TestClient
from cloud.main import app
from cloud.db import db
from cloud.auth import hash_key

client = TestClient(app)


def _seed_team_and_key(raw_key="enact_live_testkey123456789012"):
    with db() as conn:
        conn.execute("INSERT INTO teams (team_id, name) VALUES ('team-1', 'Test Team')")
        conn.execute(
            "INSERT INTO api_keys (key_hash, team_id, label) VALUES (?, 'team-1', 'test')",
            (hash_key(raw_key),),
        )
    return raw_key


class TestApiKeyAuth:
    def test_missing_key_returns_422(self):
        resp = client.post("/receipts", json={})
        assert resp.status_code == 422  # FastAPI validation — missing required header

    def test_invalid_key_returns_401(self):
        resp = client.post(
            "/receipts",
            json={"run_id": "x", "workflow": "y", "decision": "PASS", "receipt": {}},
            headers={"X-Enact-Api-Key": "bad-key"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid API key"

    def test_valid_key_resolves(self):
        raw_key = _seed_team_and_key()
        resp = client.post(
            "/receipts",
            json={"run_id": "run-1", "workflow": "wf", "decision": "PASS", "receipt": {}},
            headers={"X-Enact-Api-Key": raw_key},
        )
        assert resp.status_code == 201
