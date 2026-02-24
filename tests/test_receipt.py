import json
import os
import pytest
from enact.receipt import build_receipt, sign_receipt, verify_signature, write_receipt
from enact.models import PolicyResult, ActionResult, Receipt


@pytest.fixture
def sample_policy_results():
    return [
        PolicyResult(policy="check_a", passed=True, reason="All good"),
        PolicyResult(policy="check_b", passed=True, reason="Looks fine"),
    ]


@pytest.fixture
def sample_actions():
    return [
        ActionResult(
            action="create_contact", system="hubspot", success=True, output={"id": "123"}
        ),
    ]


class TestBuildReceipt:
    def test_creates_receipt_with_uuid(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test_wf",
            actor_email="agent@co.com",
            payload={"email": "jane@acme.com"},
            policy_results=sample_policy_results,
            decision="PASS",
        )
        assert receipt.run_id  # UUID is set
        assert receipt.workflow == "test_wf"
        assert receipt.actor_email == "agent@co.com"
        assert receipt.decision == "PASS"
        assert receipt.timestamp  # ISO timestamp is set
        assert receipt.signature == ""  # Not signed yet
        assert len(receipt.policy_results) == 2
        assert receipt.actions_taken == []

    def test_block_receipt_has_no_actions(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test_wf",
            actor_email="agent@co.com",
            payload={},
            policy_results=sample_policy_results,
            decision="BLOCK",
        )
        assert receipt.decision == "BLOCK"
        assert receipt.actions_taken == []

    def test_pass_receipt_has_actions(self, sample_policy_results, sample_actions):
        receipt = build_receipt(
            workflow="test_wf",
            actor_email="agent@co.com",
            payload={},
            policy_results=sample_policy_results,
            decision="PASS",
            actions_taken=sample_actions,
        )
        assert receipt.decision == "PASS"
        assert len(receipt.actions_taken) == 1
        assert receipt.actions_taken[0].action == "create_contact"


class TestSignReceipt:
    def test_sign_produces_hex_digest(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test",
            actor_email="a@b.com",
            payload={},
            policy_results=sample_policy_results,
            decision="PASS",
        )
        signed = sign_receipt(receipt, secret="test-secret-key")
        assert signed.signature != ""
        assert len(signed.signature) == 64  # SHA256 hex = 64 chars

    def test_different_secrets_different_signatures(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test",
            actor_email="a@b.com",
            payload={},
            policy_results=sample_policy_results,
            decision="PASS",
        )
        sig1 = sign_receipt(receipt, secret="key1").signature
        sig2 = sign_receipt(receipt, secret="key2").signature
        assert sig1 != sig2

    def test_signing_is_deterministic(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test",
            actor_email="a@b.com",
            payload={},
            policy_results=sample_policy_results,
            decision="PASS",
        )
        sig1 = sign_receipt(receipt, secret="key").signature
        sig2 = sign_receipt(receipt, secret="key").signature
        assert sig1 == sig2


class TestVerifySignature:
    def test_valid_signature_passes(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test",
            actor_email="a@b.com",
            payload={},
            policy_results=sample_policy_results,
            decision="PASS",
        )
        signed = sign_receipt(receipt, secret="my-secret")
        assert verify_signature(signed, secret="my-secret") is True

    def test_wrong_secret_fails(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test",
            actor_email="a@b.com",
            payload={},
            policy_results=sample_policy_results,
            decision="PASS",
        )
        signed = sign_receipt(receipt, secret="my-secret")
        assert verify_signature(signed, secret="wrong-secret") is False

    def test_tampered_receipt_fails(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test",
            actor_email="a@b.com",
            payload={},
            policy_results=sample_policy_results,
            decision="PASS",
        )
        signed = sign_receipt(receipt, secret="my-secret")
        # Tamper with the decision
        tampered = signed.model_copy(update={"decision": "BLOCK"})
        assert verify_signature(tampered, secret="my-secret") is False


class TestWriteReceipt:
    def test_writes_json_file(self, tmp_path, sample_policy_results):
        receipt = build_receipt(
            workflow="test",
            actor_email="a@b.com",
            payload={"x": 1},
            policy_results=sample_policy_results,
            decision="PASS",
        )
        signed = sign_receipt(receipt, secret="key")
        filepath = write_receipt(signed, directory=str(tmp_path))

        assert os.path.exists(filepath)
        with open(filepath) as f:
            data = json.load(f)
        assert data["workflow"] == "test"
        assert data["signature"] != ""

    def test_creates_directory_if_missing(self, tmp_path, sample_policy_results):
        receipt = build_receipt(
            workflow="test",
            actor_email="a@b.com",
            payload={},
            policy_results=sample_policy_results,
            decision="PASS",
        )
        new_dir = str(tmp_path / "nested" / "receipts")
        filepath = write_receipt(receipt, directory=new_dir)
        assert os.path.exists(filepath)


class TestActionResultRollbackData:
    def test_action_result_has_rollback_data_field(self):
        """rollback_data defaults to empty dict — backward compatible."""
        result = ActionResult(action="create_branch", system="github", success=True, output={})
        assert result.rollback_data == {}

    def test_action_result_rollback_data_can_be_set(self):
        result = ActionResult(
            action="create_branch",
            system="github",
            success=True,
            output={"branch": "agent/x"},
            rollback_data={"repo": "owner/repo", "branch": "agent/x"},
        )
        assert result.rollback_data["branch"] == "agent/x"

    def test_receipt_decision_accepts_partial(self):
        """
        Receipt.decision Literal must include "PARTIAL" — rollback() sets this
        when some actions could not be reversed. Without it, Pydantic raises
        ValidationError and the rollback call crashes.
        """
        receipt = build_receipt(
            workflow="rollback:test_workflow",
            actor_email="agent@test.com",
            payload={"original_run_id": "abc", "rollback": True},
            policy_results=[],
            decision="PARTIAL",
        )
        assert receipt.decision == "PARTIAL"
