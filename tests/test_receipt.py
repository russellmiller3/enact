import json
import os
import pytest
from enact.receipt import build_receipt, sign_receipt, verify_signature, write_receipt, load_receipt
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
            user_email="agent@co.com",
            payload={"email": "jane@acme.com"},
            policy_results=sample_policy_results,
            decision="PASS",
        )
        assert receipt.run_id  # UUID is set
        assert receipt.workflow == "test_wf"
        assert receipt.user_email == "agent@co.com"
        assert receipt.decision == "PASS"
        assert receipt.timestamp  # ISO timestamp is set
        assert receipt.signature == ""  # Not signed yet
        assert len(receipt.policy_results) == 2
        assert receipt.actions_taken == []

    def test_block_receipt_has_no_actions(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test_wf",
            user_email="agent@co.com",
            payload={},
            policy_results=sample_policy_results,
            decision="BLOCK",
        )
        assert receipt.decision == "BLOCK"
        assert receipt.actions_taken == []

    def test_pass_receipt_has_actions(self, sample_policy_results, sample_actions):
        receipt = build_receipt(
            workflow="test_wf",
            user_email="agent@co.com",
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
            user_email="a@b.com",
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
            user_email="a@b.com",
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
            user_email="a@b.com",
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
            user_email="a@b.com",
            payload={},
            policy_results=sample_policy_results,
            decision="PASS",
        )
        signed = sign_receipt(receipt, secret="my-secret")
        assert verify_signature(signed, secret="my-secret") is True

    def test_wrong_secret_fails(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test",
            user_email="a@b.com",
            payload={},
            policy_results=sample_policy_results,
            decision="PASS",
        )
        signed = sign_receipt(receipt, secret="my-secret")
        assert verify_signature(signed, secret="wrong-secret") is False

    def test_tampered_receipt_fails(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test",
            user_email="a@b.com",
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
            user_email="a@b.com",
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
            user_email="a@b.com",
            payload={},
            policy_results=sample_policy_results,
            decision="PASS",
        )
        new_dir = str(tmp_path / "nested" / "receipts")
        filepath = write_receipt(receipt, directory=new_dir)
        assert os.path.exists(filepath)


class TestLoadReceipt:
    def test_load_receipt_roundtrip(self, tmp_path, sample_policy_results):
        """Receipt written to disk can be loaded back and matches original."""
        receipt = build_receipt(
            workflow="test_workflow",
            user_email="agent@test.com",
            payload={"key": "val"},
            policy_results=sample_policy_results,
            decision="PASS",
        )
        receipt = sign_receipt(receipt, "test-secret")
        write_receipt(receipt, str(tmp_path))

        loaded = load_receipt(receipt.run_id, str(tmp_path))

        assert loaded.run_id == receipt.run_id
        assert loaded.workflow == receipt.workflow
        assert loaded.signature == receipt.signature

    def test_load_receipt_raises_for_missing_run_id(self, tmp_path):
        # Must use a valid UUID format — non-UUID strings now raise ValueError
        with pytest.raises(FileNotFoundError, match="No receipt found for run_id"):
            load_receipt("00000000-0000-0000-0000-000000000000", str(tmp_path))


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
            user_email="agent@test.com",
            payload={"original_run_id": "abc", "rollback": True},
            policy_results=[],
            decision="PARTIAL",
        )
        assert receipt.decision == "PARTIAL"


# ── Security: Path traversal protection (Risk #1) ───────────────────────────

class TestPathTraversalProtection:
    def test_load_receipt_rejects_unix_traversal(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid run_id"):
            load_receipt("../../etc/passwd", str(tmp_path))

    def test_load_receipt_rejects_windows_traversal(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid run_id"):
            load_receipt("..\\..\\Windows\\System32", str(tmp_path))

    def test_load_receipt_rejects_embedded_slash(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid run_id"):
            load_receipt("foo/bar", str(tmp_path))

    def test_load_receipt_rejects_dot_dot(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid run_id"):
            load_receipt("..", str(tmp_path))

    def test_load_receipt_rejects_non_uuid_string(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid run_id"):
            load_receipt("not-a-uuid-at-all", str(tmp_path))

    def test_write_receipt_rejects_crafted_run_id(self, tmp_path, sample_policy_results):
        """Manually crafted Receipt with malicious run_id is rejected at write time."""
        receipt = build_receipt(
            workflow="test", user_email="a@b.com", payload={},
            policy_results=sample_policy_results, decision="PASS",
        )
        evil = receipt.model_copy(update={"run_id": "../../evil"})
        evil = sign_receipt(evil, "test-secret-key")
        with pytest.raises(ValueError, match="Invalid run_id"):
            write_receipt(evil, str(tmp_path))

    def test_valid_uuid_roundtrips(self, tmp_path, sample_policy_results):
        """Legitimate UUID run_ids still work correctly after validation."""
        receipt = build_receipt(
            workflow="test", user_email="a@b.com", payload={},
            policy_results=sample_policy_results, decision="PASS",
        )
        signed = sign_receipt(receipt, "test-secret-key")
        write_receipt(signed, str(tmp_path))
        loaded = load_receipt(receipt.run_id, str(tmp_path))
        assert loaded.run_id == receipt.run_id


# ── Security: HMAC covers all fields (Risk #3) ──────────────────────────────

class TestHMACFullCoverage:
    def test_tampered_payload_fails_verification(self, sample_policy_results):
        """Modifying payload after signing invalidates the signature."""
        receipt = build_receipt(
            workflow="test", user_email="a@b.com",
            payload={"key": "original"},
            policy_results=sample_policy_results, decision="PASS",
        )
        signed = sign_receipt(receipt, "test-secret")
        tampered = signed.model_copy(update={"payload": {"key": "modified"}})
        assert verify_signature(tampered, "test-secret") is False

    def test_tampered_policy_results_fails_verification(self, sample_policy_results):
        """Modifying policy_results after signing invalidates the signature."""
        receipt = build_receipt(
            workflow="test", user_email="a@b.com", payload={},
            policy_results=sample_policy_results, decision="PASS",
        )
        signed = sign_receipt(receipt, "test-secret")
        tampered = signed.model_copy(update={
            "policy_results": [PolicyResult(policy="evil", passed=True, reason="forged")]
        })
        assert verify_signature(tampered, "test-secret") is False

    def test_tampered_actions_taken_fails_verification(self, sample_policy_results, sample_actions):
        """Modifying actions_taken after signing invalidates the signature."""
        receipt = build_receipt(
            workflow="test", user_email="a@b.com", payload={},
            policy_results=sample_policy_results, decision="PASS",
            actions_taken=sample_actions,
        )
        signed = sign_receipt(receipt, "test-secret")
        tampered = signed.model_copy(update={"actions_taken": []})
        assert verify_signature(tampered, "test-secret") is False
