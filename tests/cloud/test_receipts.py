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


# ── Cycle 6: Usage enforcement ────────────────────────────────────────────────

class TestUsageEnforcement:
    """Insert fake rows directly into DB to simulate usage thresholds."""

    def _bulk_insert(self, n: int, month_prefix: str = "2026-03"):
        """Insert n receipt rows for team-1 with created_at in the given month."""
        with db() as conn:
            for i in range(n):
                conn.execute(
                    """INSERT INTO receipts
                       (run_id, team_id, workflow, decision, created_at)
                       VALUES (?, 'team-1', 'wf', 'PASS', ?)""",
                    (f"bulk-{i}", f"{month_prefix}-01T00:00:0{i % 10}Z"),
                )

    def test_under_soft_limit_no_warning(self):
        resp = client.post("/receipts", json={
            "run_id": "fresh-1", "workflow": "wf", "decision": "PASS", "receipt": {}
        }, headers=headers())
        assert resp.status_code == 201
        assert "X-Enact-Usage-Warning" not in resp.headers

    def test_at_soft_limit_adds_warning_header(self, monkeypatch):
        # Patch _SOFT_LIMIT to 2 so we don't insert 50K rows
        import cloud.routes.receipts as receipts_mod
        monkeypatch.setattr(receipts_mod, "_SOFT_LIMIT", 2)
        monkeypatch.setattr(receipts_mod, "_HARD_LIMIT", 5)
        self._bulk_insert(2)
        resp = client.post("/receipts", json={
            "run_id": "warn-me", "workflow": "wf", "decision": "PASS", "receipt": {}
        }, headers=headers())
        assert resp.status_code == 201
        assert "X-Enact-Usage-Warning" in resp.headers

    def test_at_hard_limit_returns_429(self, monkeypatch):
        import cloud.routes.receipts as receipts_mod
        monkeypatch.setattr(receipts_mod, "_SOFT_LIMIT", 2)
        monkeypatch.setattr(receipts_mod, "_HARD_LIMIT", 3)
        self._bulk_insert(3)
        resp = client.post("/receipts", json={
            "run_id": "blocked", "workflow": "wf", "decision": "PASS", "receipt": {}
        }, headers=headers())
        assert resp.status_code == 429
        assert "limit" in resp.json()["detail"].lower()

    def test_prior_month_receipts_not_counted(self, monkeypatch):
        """Receipts from a previous month don't count toward the current month limit."""
        import cloud.routes.receipts as receipts_mod
        monkeypatch.setattr(receipts_mod, "_SOFT_LIMIT", 2)
        monkeypatch.setattr(receipts_mod, "_HARD_LIMIT", 3)
        self._bulk_insert(3, month_prefix="2026-02")  # previous month
        resp = client.post("/receipts", json={
            "run_id": "fresh-month", "workflow": "wf", "decision": "PASS", "receipt": {}
        }, headers=headers())
        assert resp.status_code == 201
