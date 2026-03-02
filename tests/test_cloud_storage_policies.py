import pytest
from enact.models import WorkflowContext, PolicyResult
from enact.policies.cloud_storage import dont_delete_without_human_ok

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

def test_dont_delete_gdrive_without_human_ok_block_delete_no_hint():
    policy = dont_delete_without_human_ok("gdrive")
    context = WorkflowContext(
        workflow="delete_gdrive",
        user_email="agent@example.com",
        payload={"action": "delete", "path": "test.txt"}
    )
    result = policy(context)
    assert result.passed is False
    assert "requires human approval" in result.reason

def test_dont_delete_gdrive_without_human_ok_pass_delete_with_hint():
    policy = dont_delete_without_human_ok("gdrive")
    context = WorkflowContext(
        workflow="delete_gdrive",
        user_email="agent@example.com",
        payload={"action": "delete", "path": "test.txt", "human_ok": True}
    )
    result = policy(context)
    assert result.passed is True
    assert "Human approval verified" in result.reason

def test_dont_delete_s3_without_human_ok_block_delete_no_hint():
    policy = dont_delete_without_human_ok("s3")
    context = WorkflowContext(
        workflow="delete_s3",
        user_email="agent@example.com",
        payload={"action": "delete", "path": "s3://bucket/obj"}
    )
    result = policy(context)
    assert result.passed is False
    assert "requires human approval" in result.reason
