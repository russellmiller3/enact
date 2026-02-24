import os
import pytest
from enact.client import EnactClient
from enact.models import WorkflowContext, PolicyResult, ActionResult


# --- Test helpers ---

def policy_pass(ctx):
    return PolicyResult(policy="pass_policy", passed=True, reason="ok")


def policy_fail(ctx):
    return PolicyResult(policy="fail_policy", passed=False, reason="blocked")


def policy_check_payload(ctx):
    has_email = "email" in ctx.payload
    return PolicyResult(
        policy="require_email",
        passed=has_email,
        reason="Email present" if has_email else "Missing email in payload",
    )


def dummy_workflow(ctx):
    return [
        ActionResult(action="do_thing", system="test", success=True, output={"id": "abc"}),
    ]


def multi_action_workflow(ctx):
    return [
        ActionResult(action="step_1", system="test", success=True, output={"a": 1}),
        ActionResult(action="step_2", system="test", success=True, output={"b": 2}),
    ]


class TestEnactClientInit:
    def test_registers_workflows_by_name(self):
        client = EnactClient(workflows=[dummy_workflow])
        assert "dummy_workflow" in client._workflows

    def test_default_secret(self):
        client = EnactClient()
        assert client._secret == "enact-default-secret"

    def test_custom_secret(self):
        client = EnactClient(secret="my-secret")
        assert client._secret == "my-secret"

    def test_rollback_disabled_by_default(self):
        client = EnactClient()
        assert client._rollback_enabled is False


class TestEnactClientRun:
    def test_pass_returns_success(self, tmp_path):
        client = EnactClient(
            policies=[policy_pass],
            workflows=[dummy_workflow],
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.run(
            workflow="dummy_workflow",
            actor_email="agent@test.com",
            payload={"key": "val"},
        )
        assert result.success is True
        assert result.workflow == "dummy_workflow"
        assert receipt.decision == "PASS"
        assert len(receipt.actions_taken) == 1
        assert receipt.signature != ""

    def test_block_returns_failure(self, tmp_path):
        client = EnactClient(
            policies=[policy_pass, policy_fail],
            workflows=[dummy_workflow],
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.run(
            workflow="dummy_workflow",
            actor_email="agent@test.com",
            payload={},
        )
        assert result.success is False
        assert receipt.decision == "BLOCK"
        assert receipt.actions_taken == []
        assert receipt.signature != ""

    def test_block_runs_all_policies(self, tmp_path):
        """Even if first policy fails, ALL policies run."""
        client = EnactClient(
            policies=[policy_fail, policy_pass, policy_fail],
            workflows=[dummy_workflow],
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.run(
            workflow="dummy_workflow",
            actor_email="agent@test.com",
            payload={},
        )
        assert len(receipt.policy_results) == 3  # All 3 ran

    def test_unknown_workflow_raises(self, tmp_path):
        client = EnactClient(receipt_dir=str(tmp_path))
        with pytest.raises(ValueError, match="Unknown workflow"):
            client.run(workflow="nonexistent", actor_email="a@b.com", payload={})

    def test_receipt_written_to_disk(self, tmp_path):
        client = EnactClient(
            policies=[policy_pass],
            workflows=[dummy_workflow],
            receipt_dir=str(tmp_path),
        )
        _, receipt = client.run(
            workflow="dummy_workflow",
            actor_email="agent@test.com",
            payload={},
        )
        receipt_file = tmp_path / f"{receipt.run_id}.json"
        assert receipt_file.exists()

    def test_multi_action_workflow(self, tmp_path):
        client = EnactClient(
            policies=[policy_pass],
            workflows=[multi_action_workflow],
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.run(
            workflow="multi_action_workflow",
            actor_email="agent@test.com",
            payload={},
        )
        assert result.success is True
        assert len(receipt.actions_taken) == 2
        assert "step_1" in result.output
        assert "step_2" in result.output

    def test_policy_receives_correct_context(self, tmp_path):
        """Verify policies get the right workflow context."""
        captured = {}

        def capture_policy(ctx):
            captured["workflow"] = ctx.workflow
            captured["email"] = ctx.actor_email
            captured["payload"] = ctx.payload
            return PolicyResult(policy="capture", passed=True, reason="ok")

        client = EnactClient(
            policies=[capture_policy],
            workflows=[dummy_workflow],
            receipt_dir=str(tmp_path),
        )
        client.run(workflow="dummy_workflow", actor_email="x@y.com", payload={"k": "v"})
        assert captured["workflow"] == "dummy_workflow"
        assert captured["email"] == "x@y.com"
        assert captured["payload"] == {"k": "v"}


class TestEnactClientEndToEnd:
    def test_full_pass_flow(self, tmp_path):
        """Full integration: policy pass → workflow runs → signed receipt."""
        client = EnactClient(
            policies=[policy_pass, policy_check_payload],
            workflows=[dummy_workflow],
            secret="e2e-secret",
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.run(
            workflow="dummy_workflow",
            actor_email="agent@test.com",
            payload={"email": "jane@acme.com"},
        )
        assert result.success is True
        assert receipt.decision == "PASS"
        assert len(receipt.policy_results) == 2
        assert all(r.passed for r in receipt.policy_results)
        assert receipt.signature != ""
        assert len(receipt.signature) == 64  # SHA256 hex

    def test_full_block_flow(self, tmp_path):
        """Full integration: policy fail → blocked → no actions → signed receipt."""
        client = EnactClient(
            policies=[policy_check_payload],
            workflows=[dummy_workflow],
            secret="e2e-secret",
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.run(
            workflow="dummy_workflow",
            actor_email="agent@test.com",
            payload={},  # Missing email → policy fails
        )
        assert result.success is False
        assert receipt.decision == "BLOCK"
        assert receipt.actions_taken == []
        assert receipt.signature != ""
