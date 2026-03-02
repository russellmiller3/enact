import pytest
from enact.models import WorkflowContext, PolicyResult
from enact.policies.email import no_mass_emails, no_repeat_emails
from cloud.db import init_db, db

@pytest.fixture(autouse=True)
def setup_db(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("ENACT_DB_PATH", str(db_path))
    init_db()
    yield

def test_no_mass_emails_single_recipient():
    context = WorkflowContext(
        workflow="send_email",
        user_email="agent@example.com",
        payload={"to": "alice@example.com"}
    )
    result = no_mass_emails(context)
    assert result.passed is True
    assert "Single recipient" in result.reason

def test_no_mass_emails_multiple_recipients():
    context = WorkflowContext(
        workflow="send_email",
        user_email="agent@example.com",
        payload={"to": ["alice@example.com", "bob@example.com"]}
    )
    result = no_mass_emails(context)
    assert result.passed is False
    assert "Mass email blocked" in result.reason

def test_no_repeat_emails_no_history():
    policy = no_repeat_emails(window_hours=24, workflow_name="send_email")
    context = WorkflowContext(
        workflow="send_email",
        user_email="agent@example.com",
        payload={"to": "alice@example.com"}
    )
    result = policy(context)
    assert result.passed is True
    assert "No recent email" in result.reason

def test_no_repeat_emails_with_history():
    # Insert a fake receipt into the DB
    with db() as conn:
        conn.execute(
            """
            INSERT INTO teams (team_id, name) VALUES ('team1', 'Test Team')
            """
        )
        conn.execute(
            """
            INSERT INTO receipts (run_id, team_id, workflow, decision, receipt_json)
            VALUES ('run1', 'team1', 'send_email', 'ALLOW', '{"payload": {"to": "alice@example.com"}}')
            """
        )

    policy = no_repeat_emails(window_hours=24, workflow_name="send_email")
    context = WorkflowContext(
        workflow="send_email",
        user_email="agent@example.com",
        payload={"to": "alice@example.com"}
    )
    result = policy(context)
    assert result.passed is False
    assert "Repeat email blocked" in result.reason
