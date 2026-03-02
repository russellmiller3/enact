import pytest
from enact.models import WorkflowContext, PolicyResult
from enact.policies.email import no_mass_emails, no_repeat_emails

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

def test_no_repeat_emails_no_hint():
    context = WorkflowContext(
        workflow="send_email",
        user_email="agent@example.com",
        payload={"to": "alice@example.com"}
    )
    result = no_repeat_emails(context)
    assert result.passed is True
    assert "No recent email" in result.reason

def test_no_repeat_emails_with_hint():
    context = WorkflowContext(
        workflow="send_email",
        user_email="agent@example.com",
        payload={"to": "alice@example.com", "recently_emailed": True}
    )
    result = no_repeat_emails(context)
    assert result.passed is False
    assert "Repeat email blocked" in result.reason
