import pytest
from unittest.mock import MagicMock, patch
from enact.client import EnactClient
from enact.models import Receipt, PolicyResult, ActionResult


@pytest.fixture
def cloud_client():
    return EnactClient(
        secret="a-sufficiently-long-secret-for-tests-32chars",
        cloud_api_key="enact_live_test",
        cloud_base_url="http://localhost:9999",
    )


class TestCloudClientInit:
    def test_cloud_none_when_no_key(self):
        client = EnactClient(secret="a-sufficiently-long-secret-for-tests-32chars")
        assert client._cloud is None

    def test_cloud_set_when_key_provided(self, cloud_client):
        assert cloud_client._cloud is not None

    def test_push_receipt_raises_without_cloud(self):
        client = EnactClient(secret="a-sufficiently-long-secret-for-tests-32chars")
        with pytest.raises(PermissionError, match="cloud_api_key"):
            client.push_receipt_to_cloud(MagicMock())

    def test_run_with_hitl_raises_without_cloud(self):
        client = EnactClient(
            secret="a-sufficiently-long-secret-for-tests-32chars",
            workflows=[lambda ctx: []],
        )
        with pytest.raises(PermissionError, match="cloud_api_key"):
            client.run_with_hitl(
                workflow="whatever",
                user_email="x@y.com",
                payload={},
                notify_email="ops@y.com",
            )


class TestRunWithHitl:
    def test_approved_runs_workflow(self):
        def my_workflow(ctx):
            return []
        my_workflow.__name__ = "my_workflow"

        cloud_mock = MagicMock()
        cloud_mock.request_hitl.return_value = {"hitl_id": "abc-123", "expires_at": "..."}
        cloud_mock.poll_until_decided.return_value = "APPROVED"

        client = EnactClient(
            secret="a-sufficiently-long-secret-for-tests-32chars",
            workflows=[my_workflow],
        )
        client._cloud = cloud_mock

        result, receipt = client.run_with_hitl(
            workflow="my_workflow",
            user_email="agent@co.com",
            payload={"x": 1},
            notify_email="ops@co.com",
        )
        assert result.success is True
        assert receipt.decision == "PASS"

    def test_denied_returns_block(self):
        def my_workflow(ctx):
            return []
        my_workflow.__name__ = "my_workflow"

        cloud_mock = MagicMock()
        cloud_mock.request_hitl.return_value = {"hitl_id": "abc-456", "expires_at": "..."}
        cloud_mock.poll_until_decided.return_value = "DENIED"

        client = EnactClient(
            secret="a-sufficiently-long-secret-for-tests-32chars",
            workflows=[my_workflow],
        )
        client._cloud = cloud_mock

        result, receipt = client.run_with_hitl(
            workflow="my_workflow",
            user_email="agent@co.com",
            payload={"x": 1},
            notify_email="ops@co.com",
        )
        assert result.success is False
        assert receipt.decision == "BLOCK"
        assert "DENIED" in receipt.policy_results[0].reason

    def test_expired_returns_block(self):
        def my_workflow(ctx):
            return []
        my_workflow.__name__ = "my_workflow"

        cloud_mock = MagicMock()
        cloud_mock.request_hitl.return_value = {"hitl_id": "abc-789", "expires_at": "..."}
        cloud_mock.poll_until_decided.return_value = "EXPIRED"

        client = EnactClient(
            secret="a-sufficiently-long-secret-for-tests-32chars",
            workflows=[my_workflow],
        )
        client._cloud = cloud_mock

        result, receipt = client.run_with_hitl(
            workflow="my_workflow",
            user_email="agent@co.com",
            payload={},
            notify_email="ops@co.com",
        )
        assert result.success is False
        assert receipt.decision == "BLOCK"
