# Plan: Slack Connector + Policies + Workflow

**Template:** A (Full TDD — new connector, multiple files)
**Date:** 2026-03-01

---

## A.1 What We're Building

A `SlackConnector` that lets AI agents safely post and delete Slack messages under policy control, with full rollback support.

```
Agent calls enact.run()
  → policies check: is this channel allowed? is it a DM?
  → post_message fires via SlackConnector
  → receipt records channel + ts (for rollback)
  → enact.rollback(run_id) calls delete_message(channel, ts)
```

**Actions:**
- `post_message(channel, text)` — post to a channel or DM. `already_done` is always `False` (messages are not idempotent by design; same text twice is intentional duplication).
- `delete_message(channel, ts)` — delete a posted message. Used as rollback inverse. `already_done = "deleted"` if message not found.

**Policies:**
- `require_channel_allowlist(channels)` — factory; block if `context.payload["channel"]` not in the list
- `block_dms` — block any post to a DM channel (Slack DM channel IDs start with `"D"`)

**Workflow:**
- `post_slack_message` — single step: post one message, return receipt

**Rollback:** `post_message` → `delete_message(channel=rd["channel"], ts=rd["ts"])`
- Rollback uses `response["channel"]` (the resolved Slack channel ID), NOT the input `channel`. This matters for DM posts: you pass `U123` (user ID) but Slack returns `D456` (DM channel ID). `chat.delete` requires the DM channel ID.
- Rollback only works if the bot token has `chat:delete` scope AND the bot is deleting its own message (Slack API constraint). Document this.

**Key Decisions:**
- Follow the exact `github.py` design: allowlist-first, `_check_allowed()` on every method, broad Exception catch returning `ActionResult(success=False)`, `already_done` convention
- `delete_message` is NOT in the default allowlist (same pattern as `close_pr` in GitHub) — must be explicitly added to enable rollback
- Use `slack_sdk` (`pip install slack-sdk`); import at module top-level (same as `github.py` uses PyGithub)
- `SlackApiError` caught specifically for `message_not_found` idempotency; other Slack errors fall through to generic except

---

## A.2 Existing Code to Read First

| File | Why |
|---|---|
| `enact/connectors/github.py` | Reference for allowlist pattern, `already_done`, `rollback_data`, error handling |
| `enact/rollback.py` | Where to add `_rollback_slack()` and the `"slack"` dispatch branch |
| `enact/policies/crm.py` | Factory pattern for parameterized policies |
| `tests/test_github.py` | Mock pattern: `patch("enact.connectors.github.Github")` at fixture level |
| `pyproject.toml` | Where to add `slack = ["slack-sdk"]` optional dep |

---

## A.3 Data Flow

```
enact.run(workflow="post_slack_message", payload={"channel": "C123", "text": "hello"})
  ↓
[require_channel_allowlist(["C123"])]  → passed
[block_dms]                            → passed (not a D... channel)
  ↓
post_slack_message workflow
  → SlackConnector.post_message("C123", "hello")
     → client.chat_postMessage(channel="C123", text="hello")
     → response: {"ok": True, "channel": "C123", "ts": "1234.5678"}
     → ActionResult(success=True, output={"channel": "C123", "ts": "1234.5678", "already_done": False},
                    rollback_data={"channel": "C123", "ts": "1234.5678"})
  ↓
Receipt signed. run_id stored.

enact.rollback(run_id)
  → loads receipt, verifies signature
  → execute_rollback_action(post_message result, systems)
  → _rollback_slack("post_message", {"channel": "C123", "ts": "1234.5678"}, connector)
  → connector.delete_message("C123", "1234.5678")
     → client.chat_delete(channel="C123", ts="1234.5678")
     → ActionResult(success=True, output={"ts": "1234.5678", "already_done": False})
```

---

## A.4 Files to Create

### `enact/connectors/slack.py`

**Path:** `enact/connectors/slack.py`

```python
"""
Slack connector — wraps slack-sdk WebClient for safe, allowlist-gated messaging.

Design: allowlist-first
------------------------
Every public method calls _check_allowed() before touching the Slack API.

Error handling pattern
-----------------------
All methods catch SlackApiError (and generic Exception as a fallback) and
return ActionResult(success=False, output={"error": ...}).
SlackApiError.response["error"] gives the Slack error code string.
_check_allowed() raises PermissionError — programming error, blow up loudly.

Idempotency (already_done convention)
--------------------------------------
post_message: always already_done=False. Messages are intentionally not
idempotent — posting the same text twice is two messages, not a duplicate.
delete_message: already_done="deleted" if Slack returns "message_not_found"
(message was already deleted or never existed).

Rollback
---------
post_message is reversible via delete_message.
rollback_data uses response["channel"] (the resolved Slack channel ID) not
the input channel. This matters for DM posts: input may be a user ID (U123)
but Slack responds with the DM channel ID (D456). chat.delete requires D456.

Rollback constraint: the bot token must have chat:delete scope, and can only
delete messages it posted. Human messages cannot be deleted by the bot.

delete_message is NOT in the default allowlist. Add it explicitly to enable
rollback: SlackConnector(token=..., allowed_actions=["post_message", "delete_message"])

Usage:
    slack = SlackConnector(
        token=os.environ["SLACK_BOT_TOKEN"],
        allowed_actions=["post_message"],
    )
    result = slack.post_message(channel="C1234567890", text="Hello from the agent")
"""
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from enact.models import ActionResult


class SlackConnector:
    """
    Thin wrapper around slack-sdk WebClient with per-instance action allowlisting.
    """

    def __init__(self, token: str, allowed_actions: list[str] | None = None):
        """
        Initialise the connector.

        Args:
            token           — Slack bot token (xoxb-...). Needs chat:write scope
                              for post_message, chat:delete for delete_message.
            allowed_actions — explicit list of action names this connector instance
                              is permitted to execute. Defaults to ["post_message"].
                              Add "delete_message" to enable rollback support.
        """
        self._client = WebClient(token=token)
        self._allowed_actions = set(
            allowed_actions if allowed_actions is not None else ["post_message"]
            # delete_message is a rollback operation — not included by default.
            # Must be explicitly added if rollback is needed.
        )

    def _check_allowed(self, action: str):
        """Raise PermissionError if action not in this connector's allowlist."""
        if action not in self._allowed_actions:
            raise PermissionError(
                f"Action '{action}' not in allowlist: {self._allowed_actions}"
            )

    def post_message(self, channel: str, text: str) -> ActionResult:
        """
        Post a text message to a Slack channel or DM.

        Args:
            channel — Slack channel ID (C...) or user ID (U...) for DMs.
                      Channel names like "#general" also work but IDs are preferred.
            text    — message content (plain text; Slack markdown supported)

        Returns:
            ActionResult — success=True with {"channel": str, "ts": str, "already_done": False}
                           success=False with {"error": str} on API failure

        Note: already_done is always False. Slack messages are not idempotent —
        posting the same text twice creates two messages. This is intentional.

        rollback_data stores response["channel"] (the resolved channel ID),
        not the input channel, so delete_message can target the correct channel.
        """
        self._check_allowed("post_message")
        try:
            response = self._client.chat_postMessage(channel=channel, text=text)
            resolved_channel = response["channel"]
            ts = response["ts"]
            return ActionResult(
                action="post_message",
                system="slack",
                success=True,
                output={"channel": resolved_channel, "ts": ts, "already_done": False},
                rollback_data={"channel": resolved_channel, "ts": ts},
            )
        except SlackApiError as e:
            return ActionResult(
                action="post_message",
                system="slack",
                success=False,
                output={"error": e.response["error"]},
            )
        except Exception as e:
            return ActionResult(
                action="post_message",
                system="slack",
                success=False,
                output={"error": str(e)},
            )

    def delete_message(self, channel: str, ts: str) -> ActionResult:
        """
        Delete a previously posted message. Used as rollback inverse of post_message.

        Args:
            channel — Slack channel ID where the message lives (use response["channel"]
                      from post_message, not the original input channel)
            ts      — message timestamp from post_message output["ts"]

        Returns:
            ActionResult — success=True with {"ts": str, "already_done": False}
                           success=True with {"ts": str, "already_done": "deleted"} if already gone
                           success=False with {"error": str} on other API failures

        Constraint: bot token must have chat:delete scope and can only delete
        messages the bot posted (not human messages).
        """
        self._check_allowed("delete_message")
        try:
            self._client.chat_delete(channel=channel, ts=ts)
            return ActionResult(
                action="delete_message",
                system="slack",
                success=True,
                output={"ts": ts, "already_done": False},
            )
        except SlackApiError as e:
            if e.response["error"] == "message_not_found":
                # Already deleted or never existed — idempotent success
                return ActionResult(
                    action="delete_message",
                    system="slack",
                    success=True,
                    output={"ts": ts, "already_done": "deleted"},
                )
            return ActionResult(
                action="delete_message",
                system="slack",
                success=False,
                output={"error": e.response["error"]},
            )
        except Exception as e:
            return ActionResult(
                action="delete_message",
                system="slack",
                success=False,
                output={"error": str(e)},
            )
```

### `enact/policies/slack.py`

**Path:** `enact/policies/slack.py`

```python
"""
Slack policies — prevent bad Slack operations before they reach the connector.

Payload keys used by this module:
  "channel" — Slack channel ID or name (both policies)

Slack channel ID conventions:
  C... = public/private channel
  D... = direct message channel
  U... = user ID (converted to DM channel by Slack API)
  G... = legacy group DM
"""
from enact.models import WorkflowContext, PolicyResult


def require_channel_allowlist(channels: list[str]):
    """
    Factory: return a policy that blocks posting to unlisted channels.

    Use this to restrict agents to a specific set of Slack channels.
    Channel values in the allowlist should match whatever the agent puts
    in context.payload["channel"] — IDs (C123) or names (#general) are both
    supported, as long as they match consistently.

    Passes through if no "channel" key is in the payload (nothing to check).

    Args:
        channels — list of permitted channel IDs or names

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """
    def _policy(context: WorkflowContext) -> PolicyResult:
        channel = context.payload.get("channel")
        if not channel:
            return PolicyResult(
                policy="require_channel_allowlist",
                passed=True,
                reason="No channel in payload to check",
            )
        channel_is_permitted = channel in channels
        return PolicyResult(
            policy="require_channel_allowlist",
            passed=channel_is_permitted,
            reason=(
                f"Channel '{channel}' is permitted"
                if channel_is_permitted
                else f"Channel '{channel}' not in allowlist: {channels}"
            ),
        )

    return _policy


def block_dms(context: WorkflowContext) -> PolicyResult:
    """
    Block posting to Slack direct message channels.

    Slack DM channel IDs start with "D". User IDs start with "U" (Slack
    converts them to DM channels). This policy blocks both conventions.

    Passes through if no "channel" key is in the payload.

    Args:
        context — WorkflowContext; reads context.payload.get("channel")

    Returns:
        PolicyResult — passed=False if channel is a DM (starts with D or U)
    """
    channel = context.payload.get("channel", "")
    channel_is_dm = channel.startswith("D") or channel.startswith("U")
    return PolicyResult(
        policy="block_dms",
        passed=not channel_is_dm,
        reason=(
            f"DM channels are blocked (channel='{channel}')"
            if channel_is_dm
            else f"Channel '{channel}' is not a DM"
        ),
    )
```

### `enact/workflows/post_slack_message.py`

**Path:** `enact/workflows/post_slack_message.py`

```python
"""
Reference workflow: Post a single Slack message.

Expected payload shape:
    {
        "channel": str,  # required — Slack channel ID or name
        "text":    str,  # required — message text
    }

Expected systems:
    context.systems["slack"] — a SlackConnector instance (or any object
    with .post_message(channel, text) returning an ActionResult).
    In tests this is a MagicMock.
"""
from enact.models import WorkflowContext, ActionResult


def post_slack_message(context: WorkflowContext) -> list[ActionResult]:
    """
    Post a single message to a Slack channel.

    Returns a single-element list containing the ActionResult from post_message.
    The receipt captures channel and ts, enabling rollback via delete_message.

    Args:
        context — WorkflowContext with systems["slack"] and payload keys above

    Returns:
        list[ActionResult] — [post_message result]
    """
    slack = context.systems["slack"]
    channel = context.payload["channel"]
    text = context.payload["text"]
    result = slack.post_message(channel=channel, text=text)
    return [result]
```

### `tests/test_slack.py`

**Path:** `tests/test_slack.py`

```python
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
from enact.models import WorkflowContext


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
        actor_email="agent@company.com",
        payload=payload,
        systems=systems,
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
        G... channels are an undocumented gap — acceptable for v1; note in policy docstring."""
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
```

---

## A.5 Files to Modify

### `enact/rollback.py`

**Path:** `enact/rollback.py`

**Line ~33** (in `_IRREVERSIBLE` comment — remove "Slack messages" from the note):

```python
# NOTE: Add future irreversible actions here (email sends, etc.)
```

**Line ~92** (in `execute_rollback_action`, after the `elif action_result.system == "filesystem":` block):

```python
    elif action_result.system == "slack":
        return _rollback_slack(action_result.action, rd, connector)
```

**After `_rollback_filesystem` function, add:**

```python
def _rollback_slack(action: str, rd: dict, connector) -> ActionResult:
    try:
        if action == "post_message":
            return connector.delete_message(channel=rd["channel"], ts=rd["ts"])
        else:
            return ActionResult(
                action=f"rollback_{action}",
                system="slack",
                success=False,
                output={"error": f"No rollback handler for slack.{action}"},
            )
    except Exception as e:
        return ActionResult(
            action=f"rollback_{action}",
            system="slack",
            success=False,
            output={"error": f"Rollback failed for slack.{action}: {str(e)}"},
        )
```

### `pyproject.toml`

Add `slack` optional dep and update `all`:

```toml
slack = ["slack-sdk"]
all = ["psycopg2-binary", "PyGithub", "hubspot-api-client", "slack-sdk"]
```

---

## A.6 Edge Cases & Error Handling

| Scenario | Handling | Test? |
|---|---|---|
| `post_message` to valid channel | `ActionResult(success=True, already_done=False)` | yes |
| `post_message` to nonexistent channel | `SlackApiError("channel_not_found")` → `success=False` | yes |
| `post_message` network failure | generic `Exception` → `success=False, error=str(e)` | yes |
| `delete_message` success | `ActionResult(success=True, already_done=False)` | yes |
| `delete_message` already gone | `SlackApiError("message_not_found")` → `success=True, already_done="deleted"` | yes |
| `delete_message` permission denied | `SlackApiError("cant_delete_message")` → `success=False` | yes |
| `delete_message` without allowlist | `PermissionError` raised immediately | yes |
| DM channel (`D...`) with `block_dms` | `passed=False` | yes |
| User ID (`U...`) with `block_dms` | `passed=False` | yes |
| No `channel` in payload (both policies) | pass through, `passed=True` | yes |
| Unlisted channel with `require_channel_allowlist` | `passed=False` with reason | yes |
| rollback_data uses wrong channel (input not response) | use `response["channel"]` | yes |

### ActionResult Data Contracts

**`post_message` — SUCCESS:**
```python
ActionResult(
    action="post_message",
    system="slack",
    success=True,
    output={"channel": "C1234567890", "ts": "1609459200.000100", "already_done": False},
    rollback_data={"channel": "C1234567890", "ts": "1609459200.000100"},
)
```

**`post_message` — FAILURE:**
```python
ActionResult(
    action="post_message",
    system="slack",
    success=False,
    output={"error": "channel_not_found"},  # Slack error code string
)
```

**`delete_message` — SUCCESS (fresh delete):**
```python
ActionResult(
    action="delete_message",
    system="slack",
    success=True,
    output={"ts": "1609459200.000100", "already_done": False},
)
```

**`delete_message` — IDEMPOTENT (already deleted):**
```python
ActionResult(
    action="delete_message",
    system="slack",
    success=True,
    output={"ts": "1609459200.000100", "already_done": "deleted"},
)
```

**`delete_message` — FAILURE (other error):**
```python
ActionResult(
    action="delete_message",
    system="slack",
    success=False,
    output={"error": "cant_delete_message"},
)
```

### Exact Error Strings

```python
# _check_allowed — PermissionError
PermissionError("Action 'delete_message' not in allowlist: {'post_message'}")

# post_message — SlackApiError
{"error": "channel_not_found"}   # channel ID not valid
{"error": "not_in_channel"}      # bot not in channel
{"error": "invalid_auth"}        # bad token

# delete_message — idempotent
{"ts": "...", "already_done": "deleted"}   # message_not_found from Slack

# delete_message — non-recoverable
{"error": "cant_delete_message"}   # message posted by another user
{"error": "token_revoked"}
```

---

## A.7 Implementation Order (TDD)

### PRE-IMPLEMENTATION CHECKPOINT
1. Can this be simpler? No — connector pattern is already minimal
2. Do I understand the task? Yes
3. Scope: NOT touching any existing connector, NOT modifying policy engine

### Setup
```bash
pip install slack-sdk
pip install -e ".[dev]"
pytest tests/ -v  # baseline: all existing tests pass
```

### Cycle 1: SlackConnector skeleton + allowlist 🔴🟢🔄

**Goal:** Connector initialises, allowlist works, `_check_allowed` raises correctly

**Files:** `enact/connectors/slack.py`, `tests/test_slack.py` (TestAllowlist)

**Run:** `pytest tests/test_slack.py::TestAllowlist -v`

**Commit:** `"feat: add SlackConnector skeleton with allowlist"`

---

### Cycle 2: `post_message` 🔴🟢🔄

**Goal:** `post_message` calls `chat_postMessage`, returns correct ActionResult, uses `response["channel"]` for rollback_data

**Files:** `enact/connectors/slack.py`, `tests/test_slack.py` (TestPostMessage)

**Run:** `pytest tests/test_slack.py::TestPostMessage -v`

**Commit:** `"feat: implement SlackConnector.post_message with rollback_data"`

---

### Cycle 3: `delete_message` 🔴🟢🔄

**Goal:** `delete_message` calls `chat_delete`, idempotency on `message_not_found`, other errors → failure

**Files:** `enact/connectors/slack.py`, `tests/test_slack.py` (TestDeleteMessage)

**Run:** `pytest tests/test_slack.py::TestDeleteMessage -v`

**Commit:** `"feat: implement SlackConnector.delete_message with idempotency"`

---

### Cycle 4: Policies 🔴🟢🔄

**Goal:** `require_channel_allowlist` and `block_dms` pass/fail correctly

**Files:** `enact/policies/slack.py`, `tests/test_slack.py` (TestRequireChannelAllowlist, TestBlockDms)

**Run:** `pytest tests/test_slack.py::TestRequireChannelAllowlist tests/test_slack.py::TestBlockDms -v`

**Commit:** `"feat: add Slack policies (require_channel_allowlist, block_dms)"`

---

### Cycle 5: Workflow 🔴🟢🔄

**Goal:** `post_slack_message` workflow calls connector, returns ActionResult list

**Files:** `enact/workflows/post_slack_message.py`, `tests/test_slack.py` (TestPostSlackMessageWorkflow)

**Run:** `pytest tests/test_slack.py::TestPostSlackMessageWorkflow -v`

**Commit:** `"feat: add post_slack_message workflow"`

---

### Cycle 6: Rollback wiring 🔴🟢🔄

**Goal:** `_rollback_slack` in rollback.py dispatches `post_message` → `delete_message`

**Files:** `enact/rollback.py`, `tests/test_slack.py` (TestRollback — add after Cycle 5)

Add to `tests/test_slack.py`:
```python
# TestRollback — add after the workflow tests

from enact.rollback import execute_rollback_action
from enact.models import ActionResult as AR

class TestRollback:
    def test_rollback_post_message_calls_delete_message(self, connector_with_delete):
        connector_with_delete._client.chat_delete.return_value = {"ok": True}
        original = AR(
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
        original = AR(
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
        original = AR(
            action="post_message",
            system="slack",
            success=True,
            output={"channel": "C123", "ts": "1234.5678", "already_done": False},
            rollback_data={"channel": "C123", "ts": "1234.5678"},
        )

        result = execute_rollback_action(original, systems={})  # no slack connector

        assert result.success is False
        assert "not available" in result.output["error"]
```

**Run:** `pytest tests/test_slack.py::TestRollback -v`

**Commit:** `"feat: wire Slack rollback in rollback.py"`

---

### Cycle 7: pyproject.toml + full suite 🔴🟢🔄

**Goal:** `slack` optional dep added, all existing tests still pass

**Files:** `pyproject.toml`

**Run:** `pytest -v`

**Commit:** `"chore: add slack-sdk optional dep, update pyproject.toml"`

---

## A.8 Test Strategy

```bash
# Run all Slack tests
pytest tests/test_slack.py -v

# Run full suite
pytest -v
```

**Success Criteria:**
- [ ] All new Slack tests pass
- [ ] All 321 existing tests still pass
- [ ] `pytest -v` clean

---

## A.9 Success Criteria & Cleanup

- [ ] `enact/connectors/slack.py` — `SlackConnector` with `post_message` + `delete_message`
- [ ] `enact/policies/slack.py` — `require_channel_allowlist`, `block_dms`
- [ ] `enact/workflows/post_slack_message.py` — `post_slack_message`
- [ ] `tests/test_slack.py` — full test suite (connector + policies + workflow + rollback)
- [ ] `enact/rollback.py` — `_rollback_slack()` added, `execute_rollback_action` dispatches Slack
- [ ] `pyproject.toml` — `slack = ["slack-sdk"]`, `all` updated
- [ ] `pytest -v` — all tests pass
- [ ] Committed and pushed
