import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from cloud.main import app
from cloud.db import db
from cloud.auth import hash_key
from cloud.token import make_token

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


class TestHitlRequest:
    def test_creates_pending_request(self):
        with patch("cloud.routes.hitl.send_approval_email"):
            resp = client.post("/hitl/request", json={
                "workflow": "agent_pr_workflow",
                "payload": {"repo": "owner/repo", "branch": "agent/fix"},
                "notify_email": "ops@company.com",
            }, headers=headers())
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "PENDING"
        assert "hitl_id" in data
        assert "expires_at" in data

    def test_sends_email(self):
        with patch("cloud.routes.hitl.send_approval_email") as mock_email:
            resp = client.post("/hitl/request", json={
                "workflow": "wf", "payload": {}, "notify_email": "ops@co.com",
            }, headers=headers())
        mock_email.assert_called_once()
        call_kwargs = mock_email.call_args.kwargs
        assert call_kwargs["notify_email"] == "ops@co.com"
        assert call_kwargs["workflow"] == "wf"


class TestHitlStatus:
    def _create_hitl(self):
        with patch("cloud.routes.hitl.send_approval_email"):
            resp = client.post("/hitl/request", json={
                "workflow": "wf", "payload": {}, "notify_email": "ops@co.com",
            }, headers=headers())
        return resp.json()["hitl_id"]

    def test_status_pending(self):
        hitl_id = self._create_hitl()
        resp = client.get(f"/hitl/{hitl_id}", headers=headers())
        assert resp.status_code == 200
        assert resp.json()["status"] == "PENDING"

    def test_not_found(self):
        resp = client.get("/hitl/nonexistent-id", headers=headers())
        assert resp.status_code == 404

    def test_status_approved_after_approval(self):
        hitl_id = self._create_hitl()
        token = make_token(hitl_id, "approve")
        # confirm page
        client.get(f"/hitl/{hitl_id}/approve?t={token}")
        # approve action
        client.post(f"/hitl/{hitl_id}/approve?t={token}")
        # check status
        resp = client.get(f"/hitl/{hitl_id}", headers=headers())
        assert resp.json()["status"] == "APPROVED"

    def test_status_denied_after_denial(self):
        hitl_id = self._create_hitl()
        token = make_token(hitl_id, "deny")
        client.post(f"/hitl/{hitl_id}/deny?t={token}")
        resp = client.get(f"/hitl/{hitl_id}", headers=headers())
        assert resp.json()["status"] == "DENIED"


class TestApprovalToken:
    def test_invalid_token_rejected(self):
        with patch("cloud.routes.hitl.send_approval_email"):
            resp = client.post("/hitl/request", json={
                "workflow": "wf", "payload": {}, "notify_email": "x@co.com",
            }, headers=headers())
        hitl_id = resp.json()["hitl_id"]
        resp = client.post(f"/hitl/{hitl_id}/approve?t=badtoken")
        assert resp.status_code == 403

    def test_deny_token_cannot_approve(self):
        with patch("cloud.routes.hitl.send_approval_email"):
            resp = client.post("/hitl/request", json={
                "workflow": "wf", "payload": {}, "notify_email": "x@co.com",
            }, headers=headers())
        hitl_id = resp.json()["hitl_id"]
        deny_token = make_token(hitl_id, "deny")
        resp = client.post(f"/hitl/{hitl_id}/approve?t={deny_token}")
        assert resp.status_code == 403
