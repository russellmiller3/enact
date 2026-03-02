import pytest
from enact.models import WorkflowContext, PolicyResult
from enact.policies.cloud_storage import dont_delete_without_human_ok
from cloud.db import init_db, db

@pytest.fixture(autouse=True)
def setup_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("ENACT_DB_PATH", str(db_path))
    init_db()
    yield

def test_dont_delete_gdrive_without_human_ok_pass_non_delete():
    policy = dont_delete_without_human_ok("gdrive")
    context = WorkflowContext(
        workflow="write_gdrive",
        user_email="agent@example.com",
        payload={"action": "write", "path": "test.txt"}
    )
    result = policy(context)
    assert result.passed is True
    assert "is not a deletion" in result.reason

def test_dont_delete_gdrive_without_human_ok_block_delete_no_hitl_id():
    policy = dont_delete_without_human_ok("gdrive")
    context = WorkflowContext(
        workflow="delete_gdrive",
        user_email="agent@example.com",
        payload={"action": "delete", "path": "test.txt"}
    )
    result = policy(context)
    assert result.passed is False
    assert "No hitl_id provided" in result.reason

def test_dont_delete_gdrive_without_human_ok_block_delete_invalid_hitl_id():
    policy = dont_delete_without_human_ok("gdrive")
    context = WorkflowContext(
        workflow="delete_gdrive",
        user_email="agent@example.com",
        payload={"action": "delete", "path": "test.txt", "hitl_id": "fake_id"}
    )
    result = policy(context)
    assert result.passed is False
    assert "No HITL receipt found" in result.reason

def test_dont_delete_gdrive_without_human_ok_pass_delete_with_valid_hitl_id():
    # Insert a fake HITL receipt into the DB
    with db() as conn:
        conn.execute(
            """
            INSERT INTO teams (team_id, name) VALUES ('team1', 'Test Team')
            """
        )
        conn.execute(
            """
            INSERT INTO hitl_receipts (hitl_id, team_id, workflow, decision, decided_by, decided_at, receipt_json, signature)
            VALUES ('valid_id', 'team1', 'delete_gdrive', 'APPROVE', 'human@example.com', '2026-03-02T12:00:00Z', '{}', 'sig')
            """
        )

    policy = dont_delete_without_human_ok("gdrive")
    context = WorkflowContext(
        workflow="delete_gdrive",
        user_email="agent@example.com",
        payload={"action": "delete", "path": "test.txt", "hitl_id": "valid_id"}
    )
    result = policy(context)
    assert result.passed is True
    assert "Human approval verified" in result.reason

def test_dont_delete_s3_without_human_ok_block_delete_denied_hitl_id():
    # Insert a fake HITL receipt into the DB
    with db() as conn:
        conn.execute(
            """
            INSERT INTO teams (team_id, name) VALUES ('team1', 'Test Team')
            """
        )
        conn.execute(
            """
            INSERT INTO hitl_receipts (hitl_id, team_id, workflow, decision, decided_by, decided_at, receipt_json, signature)
            VALUES ('denied_id', 'team1', 'delete_s3', 'DENY', 'human@example.com', '2026-03-02T12:00:00Z', '{}', 'sig')
            """
        )

    policy = dont_delete_without_human_ok("s3")
    context = WorkflowContext(
        workflow="delete_s3",
        user_email="agent@example.com",
        payload={"action": "delete", "path": "s3://bucket/obj", "hitl_id": "denied_id"}
    )
    result = policy(context)
    assert result.passed is False
    assert "was not approved" in result.reason
