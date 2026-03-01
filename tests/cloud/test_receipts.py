import pytest
from fastapi.testclient import TestClient
from cloud.main import app
from cloud.db import db
from cloud.auth import hash_key

client = TestClient(app)

RAW_KEY = "enact_live_testkey123456789012"


@pytest.fixture(autouse=True)
def seed(isolated_db):
    with db() as conn:
        conn.execute("INSERT INTO teams (team_id, name) VALUES ('team-1', 'Test')")
        conn.execute(
            "INSERT INTO api_keys (key_hash, team_id) VALUES (?, 'team-1')",
            (hash_key(RAW_KEY),),
        )


def headers():
    return {"X-Enact-Api-Key": RAW_KEY}


class TestPushReceipt:
    def test_store_receipt(self):
        resp = client.post("/receipts", json={
            "run_id": "abc-123",
            "workflow": "agent_pr_workflow",
            "decision": "PASS",
            "receipt": {"run_id": "abc-123", "decision": "PASS"},
        }, headers=headers())
        assert resp.status_code == 201
        assert resp.json()["run_id"] == "abc-123"
        assert resp.json()["stored"] is True

    def test_idempotent_push(self):
        payload = {"run_id": "dup-run", "workflow": "wf", "decision": "PASS", "receipt": {}}
        client.post("/receipts", json=payload, headers=headers())
        resp = client.post("/receipts", json=payload, headers=headers())
        assert resp.status_code == 201
        assert resp.json()["already_stored"] is True

    def test_get_receipt(self):
        client.post("/receipts", json={
            "run_id": "get-me", "workflow": "wf", "decision": "BLOCK", "receipt": {}
        }, headers=headers())
        resp = client.get("/receipts/get-me", headers=headers())
        assert resp.status_code == 200
        assert resp.json()["decision"] == "BLOCK"

    def test_get_receipt_not_found(self):
        resp = client.get("/receipts/nope", headers=headers())
        assert resp.status_code == 404

    def test_cannot_access_other_teams_receipt(self):
        # Store for team-1
        client.post("/receipts", json={
            "run_id": "private", "workflow": "wf", "decision": "PASS", "receipt": {}
        }, headers=headers())

        # Create team-2
        with db() as conn:
            conn.execute("INSERT INTO teams (team_id, name) VALUES ('team-2', 'Other')")
            conn.execute(
                "INSERT INTO api_keys (key_hash, team_id) VALUES (?, 'team-2')",
                (hash_key("other_key_99999999999999999999"),),
            )

        resp = client.get("/receipts/private", headers={"X-Enact-Api-Key": "other_key_99999999999999999999"})
        assert resp.status_code == 404
