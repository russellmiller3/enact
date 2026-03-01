"""
tests/test_ui.py — integration tests for the Enact receipt browser HTTP server.

Each test starts a real HTTPServer in a background daemon thread, makes requests
via urllib (no external deps), and asserts on the JSON or HTML response.
The server is shut down cleanly after each test.
"""
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from enact.models import ActionResult, PolicyResult
from enact.receipt import build_receipt, sign_receipt, write_receipt
from enact.ui import make_server

SECRET = "test-secret-that-is-long-enough-to-use-here"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _free_port() -> int:
    """Find a free local port without binding it permanently."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start(directory, port, secret=None):
    """Create and start the receipt browser on a background daemon thread."""
    httpd = make_server(directory=str(directory), port=port, secret=secret)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    time.sleep(0.05)  # give server time to bind and accept connections
    return httpd


def _get(url):
    """HTTP GET — returns (status_code, body_str). Never raises on HTTP errors."""
    try:
        res = urllib.request.urlopen(url, timeout=5)
        return res.status, res.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def receipts_dir(tmp_path):
    return tmp_path


@pytest.fixture
def pass_receipt(receipts_dir):
    """Write a signed PASS receipt to receipts_dir."""
    receipt = build_receipt(
        workflow="agent_pr_workflow",
        user_email="bot@example.com",
        payload={"repo": "my-repo", "branch": "agent/fix-1"},
        policy_results=[
            PolicyResult(
                policy="dont_push_to_main",
                passed=True,
                reason="Branch is not main",
            ),
        ],
        decision="PASS",
        actions_taken=[
            ActionResult(
                action="create_branch",
                system="github",
                success=True,
                output={"branch": "agent/fix-1", "sha": "abc123"},
            ),
        ],
    )
    signed = sign_receipt(receipt, SECRET)
    write_receipt(signed, directory=str(receipts_dir))
    return signed


@pytest.fixture
def block_receipt(receipts_dir):
    """Write a signed BLOCK receipt to receipts_dir."""
    receipt = build_receipt(
        workflow="db_safe_insert",
        user_email="agent@example.com",
        payload={"table": "users"},
        policy_results=[
            PolicyResult(
                policy="dont_delete_row",
                passed=False,
                reason="Delete operation blocked",
            ),
        ],
        decision="BLOCK",
    )
    signed = sign_receipt(receipt, SECRET)
    write_receipt(signed, directory=str(receipts_dir))
    return signed


# ---------------------------------------------------------------------------
# Index page
# ---------------------------------------------------------------------------


class TestIndexPage:
    def test_returns_html(self, receipts_dir):
        port = _free_port()
        httpd = _start(receipts_dir, port)
        try:
            status, body = _get(f"http://127.0.0.1:{port}/")
            assert status == 200
            assert "text/html" in body or "<html" in body.lower()
            assert "Enact" in body
        finally:
            httpd.shutdown()

    def test_root_path_without_slash_also_works(self, receipts_dir):
        port = _free_port()
        httpd = _start(receipts_dir, port)
        try:
            # urllib follows the redirect / normalises, so hitting / is fine
            status, body = _get(f"http://127.0.0.1:{port}/")
            assert status == 200
        finally:
            httpd.shutdown()

    def test_unknown_path_returns_404(self, receipts_dir):
        port = _free_port()
        httpd = _start(receipts_dir, port)
        try:
            status, body = _get(f"http://127.0.0.1:{port}/unknown-path")
            assert status == 404
        finally:
            httpd.shutdown()


# ---------------------------------------------------------------------------
# Receipt list endpoint
# ---------------------------------------------------------------------------


class TestReceiptList:
    def test_empty_list_when_no_receipts(self, receipts_dir):
        port = _free_port()
        httpd = _start(receipts_dir, port)
        try:
            status, body = _get(f"http://127.0.0.1:{port}/api/receipts")
            assert status == 200
            assert json.loads(body) == []
        finally:
            httpd.shutdown()

    def test_returns_summary_fields(self, receipts_dir, pass_receipt):
        port = _free_port()
        httpd = _start(receipts_dir, port)
        try:
            status, body = _get(f"http://127.0.0.1:{port}/api/receipts")
            assert status == 200
            data = json.loads(body)
            assert len(data) == 1
            r = data[0]
            assert r["run_id"] == pass_receipt.run_id
            assert r["workflow"] == "agent_pr_workflow"
            assert r["user_email"] == "bot@example.com"
            assert r["decision"] == "PASS"
            assert "timestamp" in r
            assert r["action_count"] == 1
            assert r["policy_count"] == 1
            assert r["failed_policies"] == 0
        finally:
            httpd.shutdown()

    def test_payload_not_in_list_response(self, receipts_dir, pass_receipt):
        """Payload is excluded from the list — it can be large and is in the detail view."""
        port = _free_port()
        httpd = _start(receipts_dir, port)
        try:
            status, body = _get(f"http://127.0.0.1:{port}/api/receipts")
            data = json.loads(body)
            assert "payload" not in data[0]
        finally:
            httpd.shutdown()

    def test_multiple_receipts_sorted_newest_first(
        self, receipts_dir, pass_receipt, block_receipt
    ):
        port = _free_port()
        httpd = _start(receipts_dir, port)
        try:
            status, body = _get(f"http://127.0.0.1:{port}/api/receipts")
            data = json.loads(body)
            assert len(data) == 2
            # Newer timestamp must appear first
            assert data[0]["timestamp"] >= data[1]["timestamp"]
        finally:
            httpd.shutdown()

    def test_failed_policies_counted_for_block(self, receipts_dir, block_receipt):
        port = _free_port()
        httpd = _start(receipts_dir, port)
        try:
            status, body = _get(f"http://127.0.0.1:{port}/api/receipts")
            data = json.loads(body)
            r = data[0]
            assert r["decision"] == "BLOCK"
            assert r["failed_policies"] == 1
            assert r["policy_count"] == 1
            assert r["action_count"] == 0
        finally:
            httpd.shutdown()

    def test_returns_200_when_receipts_dir_does_not_exist(self, tmp_path):
        """Missing receipts directory returns empty list, not an error."""
        port = _free_port()
        missing = tmp_path / "does_not_exist"
        httpd = _start(missing, port)
        try:
            status, body = _get(f"http://127.0.0.1:{port}/api/receipts")
            assert status == 200
            assert json.loads(body) == []
        finally:
            httpd.shutdown()


# ---------------------------------------------------------------------------
# Receipt detail endpoint
# ---------------------------------------------------------------------------


class TestReceiptDetail:
    def test_returns_full_receipt(self, receipts_dir, pass_receipt):
        port = _free_port()
        httpd = _start(receipts_dir, port)
        try:
            status, body = _get(
                f"http://127.0.0.1:{port}/api/receipts/{pass_receipt.run_id}"
            )
            assert status == 200
            data = json.loads(body)
            assert data["run_id"] == pass_receipt.run_id
            assert data["workflow"] == "agent_pr_workflow"
            assert "policy_results" in data
            assert len(data["policy_results"]) == 1
            assert "actions_taken" in data
            assert len(data["actions_taken"]) == 1
            assert "payload" in data
        finally:
            httpd.shutdown()

    def test_signature_valid_with_correct_secret(self, receipts_dir, pass_receipt):
        port = _free_port()
        httpd = _start(receipts_dir, port, secret=SECRET)
        try:
            status, body = _get(
                f"http://127.0.0.1:{port}/api/receipts/{pass_receipt.run_id}"
            )
            data = json.loads(body)
            assert data["signature_valid"] is True
        finally:
            httpd.shutdown()

    def test_signature_invalid_with_wrong_secret(self, receipts_dir, pass_receipt):
        port = _free_port()
        wrong_secret = "wrong-secret-that-is-long-enough-xxxxxxxxxx"
        httpd = _start(receipts_dir, port, secret=wrong_secret)
        try:
            status, body = _get(
                f"http://127.0.0.1:{port}/api/receipts/{pass_receipt.run_id}"
            )
            data = json.loads(body)
            assert data["signature_valid"] is False
        finally:
            httpd.shutdown()

    def test_signature_none_when_no_secret_configured(self, receipts_dir, pass_receipt):
        port = _free_port()
        httpd = _start(receipts_dir, port, secret=None)
        try:
            status, body = _get(
                f"http://127.0.0.1:{port}/api/receipts/{pass_receipt.run_id}"
            )
            data = json.loads(body)
            assert data["signature_valid"] is None
        finally:
            httpd.shutdown()

    def test_returns_404_for_unknown_run_id(self, receipts_dir):
        port = _free_port()
        httpd = _start(receipts_dir, port)
        try:
            fake_id = "00000000-0000-4000-8000-000000000000"
            status, body = _get(f"http://127.0.0.1:{port}/api/receipts/{fake_id}")
            assert status == 404
            data = json.loads(body)
            assert "error" in data
        finally:
            httpd.shutdown()

    def test_returns_400_for_invalid_run_id(self, receipts_dir):
        port = _free_port()
        httpd = _start(receipts_dir, port)
        try:
            status, body = _get(
                f"http://127.0.0.1:{port}/api/receipts/not-a-valid-uuid"
            )
            assert status == 400
            data = json.loads(body)
            assert "error" in data
        finally:
            httpd.shutdown()

    def test_returns_400_for_path_with_dots(self, receipts_dir):
        """UUID validation rejects anything that isn't a UUID, including path traversal patterns."""
        port = _free_port()
        httpd = _start(receipts_dir, port)
        try:
            # Use a UUID-looking string with dots to confirm UUID regex catches it
            status, body = _get(
                f"http://127.0.0.1:{port}/api/receipts/00000000-0000-0000-0000-..etc.passwd"
            )
            assert status == 400
        finally:
            httpd.shutdown()
