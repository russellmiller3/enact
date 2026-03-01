import hmac
import hashlib
import json
import os
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


def _create_hitl(callback_url=None):
    body = {"workflow": "wf", "payload": {}, "notify_email": "ops@co.com"}
    if callback_url:
        body["callback_url"] = callback_url
    with patch("cloud.routes.hitl.send_approval_email"):
        resp = client.post("/hitl/request", json=body, headers=headers())
    return resp.json()["hitl_id"]


class TestHitlReceipt:
    def test_approval_writes_hitl_receipt(self):
        hitl_id = _create_hitl()
        token = make_token(hitl_id, "approve")
        client.post(f"/hitl/{hitl_id}/approve?t={token}")

        with db() as conn:
            row = conn.execute(
                "SELECT * FROM hitl_receipts WHERE hitl_id = ?", (hitl_id,)
            ).fetchone()
        assert row is not None
        assert row["decision"] == "APPROVED"
        assert row["decided_by"] == "ops@co.com"
        assert row["signature"]  # non-empty

    def test_denial_writes_hitl_receipt(self):
        hitl_id = _create_hitl()
        token = make_token(hitl_id, "deny")
        client.post(f"/hitl/{hitl_id}/deny?t={token}")

        with db() as conn:
            row = conn.execute(
                "SELECT * FROM hitl_receipts WHERE hitl_id = ?", (hitl_id,)
            ).fetchone()
        assert row["decision"] == "DENIED"

    def test_receipt_is_signed(self):
        """Signature must match HMAC of the stored receipt_json bytes.
        _write_hitl_receipt stores canonical JSON and signs the same bytes,
        so: hmac(receipt_json.encode()) == signature, no re-serialization needed.
        """
        hitl_id = _create_hitl()
        token = make_token(hitl_id, "approve")
        client.post(f"/hitl/{hitl_id}/approve?t={token}")

        with db() as conn:
            row = conn.execute(
                "SELECT receipt_json, signature FROM hitl_receipts WHERE hitl_id = ?",
                (hitl_id,)
            ).fetchone()

        secret = os.environ.get("CLOUD_SECRET", "")
        expected = hmac.new(secret.encode(), row["receipt_json"].encode(), hashlib.sha256).hexdigest()
        assert hmac.compare_digest(row["signature"], expected)

    def test_double_approval_does_not_duplicate_receipt(self):
        hitl_id = _create_hitl()
        token = make_token(hitl_id, "approve")
        client.post(f"/hitl/{hitl_id}/approve?t={token}")
        client.post(f"/hitl/{hitl_id}/approve?t={token}")  # second click

        with db() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM hitl_receipts WHERE hitl_id = ?", (hitl_id,)
            ).fetchone()[0]
        assert count == 1  # INSERT OR IGNORE


class TestHitlCallback:
    def test_callback_fired_on_approval(self):
        hitl_id = _create_hitl(callback_url="http://agent.internal/hitl-webhook")
        token = make_token(hitl_id, "approve")

        with patch("cloud.routes.hitl._fire_callback") as mock_cb:
            client.post(f"/hitl/{hitl_id}/approve?t={token}")

        mock_cb.assert_called_once_with(
            "http://agent.internal/hitl-webhook", hitl_id, "APPROVED"
        )

    def test_callback_fired_on_denial(self):
        hitl_id = _create_hitl(callback_url="http://agent.internal/hitl-webhook")
        token = make_token(hitl_id, "deny")

        with patch("cloud.routes.hitl._fire_callback") as mock_cb:
            client.post(f"/hitl/{hitl_id}/deny?t={token}")

        mock_cb.assert_called_once_with(
            "http://agent.internal/hitl-webhook", hitl_id, "DENIED"
        )

    def test_no_callback_when_url_not_set(self):
        hitl_id = _create_hitl()  # no callback_url
        token = make_token(hitl_id, "approve")

        with patch("cloud.routes.hitl._fire_callback") as mock_cb:
            client.post(f"/hitl/{hitl_id}/approve?t={token}")

        mock_cb.assert_not_called()
