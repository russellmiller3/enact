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


class TestStatusBadge:
    def test_no_data_returns_grey_svg(self):
        resp = client.get("/badge/team-1/agent_pr_workflow.svg")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/svg+xml"
        assert "no data" in resp.text
        assert "#6b7280" in resp.text  # grey

    def test_pass_badge_is_green(self):
        client.post("/receipts", json={
            "run_id": "r1", "workflow": "agent_pr_workflow",
            "decision": "PASS", "receipt": {},
        }, headers=headers())
        resp = client.get("/badge/team-1/agent_pr_workflow.svg")
        assert "#16a34a" in resp.text  # green
        assert "PASS" in resp.text

    def test_block_badge_is_red(self):
        client.post("/receipts", json={
            "run_id": "r2", "workflow": "agent_pr_workflow",
            "decision": "BLOCK", "receipt": {},
        }, headers=headers())
        resp = client.get("/badge/team-1/agent_pr_workflow.svg")
        assert "#dc2626" in resp.text  # red
        assert "BLOCK" in resp.text

    def test_shows_most_recent_run(self):
        # PASS first, then BLOCK — badge should show BLOCK
        client.post("/receipts", json={
            "run_id": "r3", "workflow": "wf", "decision": "PASS", "receipt": {}
        }, headers=headers())
        client.post("/receipts", json={
            "run_id": "r4", "workflow": "wf", "decision": "BLOCK", "receipt": {}
        }, headers=headers())
        resp = client.get("/badge/team-1/wf.svg")
        assert "#dc2626" in resp.text

    def test_no_auth_required(self):
        # badge endpoint is public — no API key needed
        resp = client.get("/badge/team-1/wf.svg")
        assert resp.status_code == 200  # not 401
