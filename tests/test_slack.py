"""
Tests for SlackConnector, Slack policies, and post_slack_message workflow.
slack-sdk calls are fully mocked — no real API calls made.
"""
import pytest
from unittest.mock import patch, MagicMock
from slack_sdk.errors import SlackApiError

from enact.connectors.slack import SlackConnector
from enact.policies.slack import require_channel_allowlist, block_dms
from enact.workflows.post_slack_message import post_slack_message
from enact.rollback import execute_rollback_action
from enact.models import WorkflowContext, ActionResult


# ---------------------------------------------------------------------------
# Helpers & fixtures
# ---------------------------------------------------------------------------

def make_slack_api_error(error_code: str) -> SlackApiError:
    """Build a SlackApiError with the given Slack error code string.
    slack-sdk accepts a plain dict for response — simpler and more reliable than MagicMock.
    """
    return SlackApiError(message=error_code, response={"ok": False, "error": error_code})


def make_context(payload: dict, slack_connector=None) -> WorkflowContext:
    systems = {}
    if slack_connector is not None:
        systems["slack"] = slack_connector
    return WorkflowContext(
        workflow="post_slack_message",
        user_email="agent@company.com",
        payload=payload,
        systems=systems,
    )


@pytest.fixture
def connector():
    with patch("enact.connectors.slack.WebClient"):
        return SlackConnector(token="xoxb-fake-token")


@pytest.fixture
def connector_with_delete():
    with patch("enact.connectors.slack.WebClient"):
        return SlackConnector(
            token="xoxb-fake-token",
            allowed_actions=["post_message", "delete_message"],
        )


# ---------------------------------------------------------------------------
# TestAllowlist
# ---------------------------------------------------------------------------

class TestAllowlist:
    def test_default_allowlist_includes_post_message(self):
        with patch("enact.connectors.slack.WebClient"):
            conn = SlackConnector(token="xoxb-fake")
        assert "post_message" in conn._allowed_actions

    def test_default_allowlist_excludes_delete_message(self):
        with patch("enact.connectors.slack.WebClient"):
            conn = SlackConnector(token="xoxb-fake")
        assert "delete_message" not in conn._allowed_actions

    def test_custom_allowlist_restricts_actions(self):
        with patch("enact.connectors.slack.WebClient"):
            conn = SlackConnector(token="xoxb-fake", allowed_actions=["delete_message"])
        assert "delete_message" in conn._allowed_actions
        assert "post_message" not in conn._allowed_actions

    def test_blocked_action_raises_permission_error(self):
        with patch("enact.connectors.slack.WebClient"):
            conn = SlackConnector(token="xoxb-fake", allowed_actions=["post_message"])
        with pytest.raises(PermissionError, match="not in allowlist"):
            conn.delete_message(channel="C123", ts="1234.5678")


# ---------------------------------------------------------------------------
# TestPostMessage
# ---------------------------------------------------------------------------

class TestPostMessage:
    def test_post_message_success(self, connector):
        connector._client.chat_postMessage.return_value = {
            "ok": True,
            "channel": "C1234567890",
            "ts": "1609459200.000100",
        }

        result = connector.post_message(channel="C1234567890", text="hello")

        assert result.success is True
        assert result.action == "post_message"
        assert result.system == "slack"
        assert result.output["channel"] == "C1234567890"
        assert result.output["ts"] == "1609459200.000100"
        assert result.output["already_done"] is False
        connector._client.chat_postMessage.assert_called_once_with(
            channel="C1234567890", text="hello"
        )

    def test_post_message_rollback_data_uses_response_channel(self, connector):
        """rollback_data must use response["channel"] (resolved ID), not the input."""
        connector._client.chat_postMessage.return_value = {
            "ok": True,
            "channel": "D9876543210",  # DM channel ID resolved by Slack
            "ts": "1609459200.000200",
        }

        result = connector.post_message(channel="U1111111111", text="hi")  # input: user ID

        # rollback_data must have the resolved DM channel ID, not the user ID
        assert result.rollback_data["channel"] == "D9876543210"
        assert result.rollback_data["ts"] == "1609459200.000200"

    def test_post_message_already_done_is_always_false(self, connector):
        connector._client.chat_postMessage.return_value = {
            "ok": True, "channel": "C123", "ts": "1234.5678"
        }
        result = connector.post_message(channel="C123", text="same text")
        assert result.output["already_done"] is False

    def test_post_message_slack_api_error(self, connector):
        connector._client.chat_postMessage.side_effect = make_slack_api_error("channel_not_found")

        result = connector.post_message(channel="C_INVALID", text="hello")

        assert result.success is False
        assert result.output["error"] == "channel_not_found"

    def test_post_message_generic_exception(self, connector):
        connector._client.chat_postMessage.side_effect = Exception("network timeout")

        result = connector.post_message(channel="C123", text="hello")

        assert result.success is False
        assert "network timeout" in result.output["error"]


# ---------------------------------------------------------------------------
# TestDeleteMessage
# ---------------------------------------------------------------------------

class TestDeleteMessage:
    def test_delete_message_success(self, connector_with_delete):
        connector_with_delete._client.chat_delete.return_value = {"ok": True}

        result = connector_with_delete.delete_message(channel="C123", ts="1234.5678")

        assert result.success is True
        assert result.action == "delete_message"
        assert result.output["ts"] == "1234.5678"
        assert result.output["already_done"] is False
        connector_with_delete._client.chat_delete.assert_called_once_with(
            channel="C123", ts="1234.5678"
        )

    def test_delete_message_already_deleted_returns_idempotent_success(self, connector_with_delete):
        connector_with_delete._client.chat_delete.side_effect = make_slack_api_error("message_not_found")

        result = connector_with_delete.delete_message(channel="C123", ts="1234.5678")

        assert result.success is True
        assert result.output["already_done"] == "deleted"
        assert result.output["ts"] == "1234.5678"

    def test_delete_message_other_slack_error_returns_failure(self, connector_with_delete):
        connector_with_delete._client.chat_delete.side_effect = make_slack_api_error("cant_delete_message")

        result = connector_with_delete.delete_message(channel="C123", ts="1234.5678")

        assert result.success is False
        assert result.output["error"] == "cant_delete_message"

    def test_delete_message_generic_exception(self, connector_with_delete):
        connector_with_delete._client.chat_delete.side_effect = Exception("connection error")

        result = connector_with_delete.delete_message(channel="C123", ts="1234.5678")

        assert result.success is False
        assert "connection error" in result.output["error"]


# ---------------------------------------------------------------------------
# TestRequireChannelAllowlist
# ---------------------------------------------------------------------------

class TestRequireChannelAllowlist:
    def test_permitted_channel_passes(self):
        policy = require_channel_allowlist(["C111", "C222"])
        ctx = make_context({"channel": "C111", "text": "hi"})
        result = policy(ctx)
        assert result.passed is True
        assert result.policy == "require_channel_allowlist"

    def test_unpermitted_channel_blocks(self):
        policy = require_channel_allowlist(["C111"])
        ctx = make_context({"channel": "C999", "text": "hi"})
        result = policy(ctx)
        assert result.passed is False
        assert "C999" in result.reason
        assert "C111" in result.reason

    def test_no_channel_in_payload_passes_through(self):
        policy = require_channel_allowlist(["C111"])
        ctx = make_context({"text": "hi"})
        result = policy(ctx)
        assert result.passed is True
        assert "No channel" in result.reason

    def test_empty_allowlist_blocks_all_channels(self):
        policy = require_channel_allowlist([])
        ctx = make_context({"channel": "C111", "text": "hi"})
        result = policy(ctx)
        assert result.passed is False


# ---------------------------------------------------------------------------
# TestBlockDms
# ---------------------------------------------------------------------------

class TestBlockDms:
    def test_regular_channel_passes(self):
        ctx = make_context({"channel": "C1234567890", "text": "hi"})
        result = block_dms(ctx)
        assert result.passed is True
        assert result.policy == "block_dms"

    def test_dm_channel_id_blocked(self):
        ctx = make_context({"channel": "D1234567890", "text": "hi"})
        result = block_dms(ctx)
        assert result.passed is False
        assert "D1234567890" in result.reason

    def test_user_id_input_blocked(self):
        """U... user IDs become DM channels — must be blocked."""
        ctx = make_context({"channel": "U1234567890", "text": "hi"})
        result = block_dms(ctx)
        assert result.passed is False

    def test_no_channel_in_payload_passes_through(self):
        ctx = make_context({"text": "hi"})
        result = block_dms(ctx)
        assert result.passed is True

    def test_group_dm_channel_not_blocked(self):
        """G... are legacy group DM channel IDs. block_dms only checks D and U prefixes.
        G... channels are an undocumented gap — acceptable for v1; noted in policy docstring."""
        ctx = make_context({"channel": "G1234567890", "text": "hi"})
        result = block_dms(ctx)
        assert result.passed is True


# ---------------------------------------------------------------------------
# TestPostSlackMessageWorkflow
# ---------------------------------------------------------------------------

class TestPostSlackMessageWorkflow:
    def test_workflow_calls_post_message_with_payload_values(self, connector):
        connector._client.chat_postMessage.return_value = {
            "ok": True, "channel": "C123", "ts": "1234.5678"
        }
        ctx = make_context({"channel": "C123", "text": "deploy complete"}, slack_connector=connector)

        results = post_slack_message(ctx)

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].output["channel"] == "C123"
        assert results[0].output["ts"] == "1234.5678"
        connector._client.chat_postMessage.assert_called_once_with(
            channel="C123", text="deploy complete"
        )

    def test_workflow_returns_failure_on_api_error(self, connector):
        connector._client.chat_postMessage.side_effect = make_slack_api_error("not_in_channel")
        ctx = make_context({"channel": "C123", "text": "hello"}, slack_connector=connector)

        results = post_slack_message(ctx)

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].output["error"] == "not_in_channel"


# ---------------------------------------------------------------------------
# TestRollback
# ---------------------------------------------------------------------------

class TestRollback:
    def test_rollback_post_message_calls_delete_message(self, connector_with_delete):
        connector_with_delete._client.chat_delete.return_value = {"ok": True}
        original = ActionResult(
            action="post_message",
            system="slack",
            success=True,
            output={"channel": "C123", "ts": "1234.5678", "already_done": False},
            rollback_data={"channel": "C123", "ts": "1234.5678"},
        )

        result = execute_rollback_action(original, systems={"slack": connector_with_delete})

        assert result.success is True
        connector_with_delete._client.chat_delete.assert_called_once_with(
            channel="C123", ts="1234.5678"
        )

    def test_rollback_unknown_slack_action_returns_error(self, connector_with_delete):
        original = ActionResult(
            action="unknown_action",
            system="slack",
            success=True,
            output={},
            rollback_data={},
        )

        result = execute_rollback_action(original, systems={"slack": connector_with_delete})

        assert result.success is False
        assert "No rollback handler" in result.output["error"]

    def test_rollback_missing_slack_system_returns_error(self):
        original = ActionResult(
            action="post_message",
            system="slack",
            success=True,
            output={"channel": "C123", "ts": "1234.5678", "already_done": False},
            rollback_data={"channel": "C123", "ts": "1234.5678"},
        )

        result = execute_rollback_action(original, systems={})  # no slack connector

        assert result.success is False
        assert "not available" in result.output["error"]
