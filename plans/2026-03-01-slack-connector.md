# Plan 7: Slack Connector

**Template:** A (Full TDD — new connector, policies, workflow, rollback wiring)

---

## A.1 What We're Building

`SlackConnector` — lets AI agents post Slack messages, governed by Enact policies and backed by a receipt. Agents can send to channels or DM a user by email. Rollback deletes the message.

```
BEFORE: agent.post_slack("#general", "Deploy complete")  # ungoverned, no receipt
AFTER:  enact.run("post_slack_message_workflow", payload={"channel": "#alerts", "text": "..."})
        # → policy gate → send_message → signed receipt with ts for rollback
```

**Key Decisions:**

- **Auth**: Slack bot token (`xoxb-...`) via `slack_sdk.WebClient`. No OAuth flow — bot tokens are standard.
- **Idempotency**: Scan channel history for exact text match within 60s. If found → `already_done="sent"`. Same check-before-act pattern as every other connector.
- **Rollback**: `chat.delete` using the `ts` stored in `rollback_data`. Bots can delete their own messages.
- **Policies**: `no_bulk_channel_blast(protected_channels)` — block posting to #general/#everyone. `no_dm_external_users(allowed_domains)` — block DMing outside your org.
- **Optional dep**: `slack-sdk` under `[slack]` extras; added to `[dev]` so tests run without extra steps.

**Slack app scopes required (README will document):**
```
chat:write        — post + delete bot messages
channels:history  — read public channel history (dedup check)
groups:history    — read private channel history
im:history        — read DM history
im:write          — open DM conversations
users:read.email  — look up users by email for send_dm
```

---

## A.2 Existing Code to Read First

| File | Why |
|---|---|
| `enact/connectors/filesystem.py` | Pattern to follow exactly |
| `enact/rollback.py` | Where to add `_rollback_slack()` |
| `enact/workflows/agent_pr_workflow.py` | Thin workflow pattern |
| `pyproject.toml` | Add `slack-sdk` to optional deps |

---

## A.3 Data Flow

```
enact.run("post_slack_message_workflow", payload={"channel": "#alerts", "text": "..."})
  ├─ policy gate
  │   ├─ no_bulk_channel_blast(["#general"]) → PASS
  │   └─ no_dm_external_users([...])         → PASS
  ├─ post_slack_message_workflow(context)
  │   └─ slack.send_message(channel, text)
  │       ├─ _find_recent_message() → None
  │       └─ chat.postMessage() → {ts: "1234567890.123456"}
  │           rollback_data = {"channel": "C123", "ts": "1234567890.123456"}
  └─ signed receipt → RunResult

enact.rollback(run_id)
  └─ _rollback_slack("send_message", rd, connector)
      └─ connector.delete_message(channel, ts) → chat.delete()
```

---

## A.4 Files to Create

### `enact/connectors/slack.py`

```python
"""
Slack connector — policy-gated message sending for AI agents.

Idempotency: send_message and send_dm scan channel history (last 60s) for an
exact text match from this bot. If found → already_done="sent".

Rollback data:
  send_message: {"channel": channel_id, "ts": message_ts}
  send_dm:      {"channel": dm_channel_id, "ts": message_ts}
  delete_message: rollback_data={} (not reversible)

Required Slack app scopes:
  chat:write, channels:history, groups:history, im:history, im:write, users:read.email
"""
import time
from enact.models import ActionResult

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError as e:
    raise ImportError(
        "slack-sdk is required for SlackConnector. "
        "Install it with: pip install 'enact-sdk[slack]'"
    ) from e


class SlackConnector:
    ALLOWED_ACTIONS = ["send_message", "send_dm", "delete_message"]
    DEDUP_WINDOW_SECONDS = 60

    def __init__(self, token: str, allowed_actions: list[str] | None = None):
        self._client = WebClient(token=token)
        self._allowed = set(
            allowed_actions if allowed_actions is not None else self.ALLOWED_ACTIONS
        )

    def _check_allowed(self, action: str) -> None:
        if action not in self._allowed:
            raise PermissionError(
                f"Action '{action}' is not in the allowed_actions list for this SlackConnector. "
                f"Allowed: {sorted(self._allowed)}"
            )

    def _find_recent_message(self, channel: str, text: str) -> str | None:
        """Scan channel history for exact bot message match within DEDUP_WINDOW_SECONDS."""
        oldest = str(time.time() - self.DEDUP_WINDOW_SECONDS)
        try:
            resp = self._client.conversations_history(
                channel=channel, oldest=oldest, limit=100
            )
            for msg in resp.get("messages", []):
                if msg.get("text") == text and msg.get("bot_id"):
                    return msg["ts"]
        except SlackApiError:
            pass  # Missing history scope — proceed with the send
        return None

    def send_message(self, channel: str, text: str) -> ActionResult:
        self._check_allowed("send_message")
        try:
            existing_ts = self._find_recent_message(channel, text)
            if existing_ts:
                return ActionResult(
                    action="send_message", system="slack", success=True,
                    output={"channel": channel, "ts": existing_ts, "already_done": "sent"},
                    rollback_data={},
                )
            resp = self._client.chat_postMessage(channel=channel, text=text)
            return ActionResult(
                action="send_message", system="slack", success=True,
                output={"channel": channel, "ts": resp["ts"], "already_done": False},
                rollback_data={"channel": resp["channel"], "ts": resp["ts"]},
            )
        except SlackApiError as e:
            return ActionResult(
                action="send_message", system="slack", success=False,
                output={"error": str(e)},
            )

    def send_dm(self, user_email: str, text: str) -> ActionResult:
        self._check_allowed("send_dm")
        try:
            user_resp = self._client.users_lookupByEmail(email=user_email)
            user_id = user_resp["user"]["id"]
            dm_resp = self._client.conversations_open(users=[user_id])
            channel = dm_resp["channel"]["id"]
            existing_ts = self._find_recent_message(channel, text)
            if existing_ts:
                return ActionResult(
                    action="send_dm", system="slack", success=True,
                    output={"channel": channel, "ts": existing_ts, "already_done": "sent"},
                    rollback_data={},
                )
            resp = self._client.chat_postMessage(channel=channel, text=text)
            return ActionResult(
                action="send_dm", system="slack", success=True,
                output={"channel": channel, "ts": resp["ts"], "already_done": False},
                rollback_data={"channel": channel, "ts": resp["ts"]},
            )
        except SlackApiError as e:
            return ActionResult(
                action="send_dm", system="slack", success=False,
                output={"error": str(e)},
            )

    def delete_message(self, channel: str, ts: str) -> ActionResult:
        self._check_allowed("delete_message")
        try:
            self._client.chat_delete(channel=channel, ts=ts)
            return ActionResult(
                action="delete_message", system="slack", success=True,
                output={"channel": channel, "ts": ts, "already_done": False},
                rollback_data={},
            )
        except SlackApiError as e:
            if "message_not_found" in str(e):
                return ActionResult(
                    action="delete_message", system="slack", success=True,
                    output={"channel": channel, "ts": ts, "already_done": "deleted"},
                    rollback_data={},
                )
            return ActionResult(
                action="delete_message", system="slack", success=False,
                output={"error": str(e)},
            )
```

---

### `enact/policies/slack.py`

```python
"""Built-in Slack policies."""
from enact.models import WorkflowContext, PolicyResult


def no_bulk_channel_blast(protected_channels: list[str]):
    """Block posting to protected channels like #general or #everyone."""
    def _policy(context: WorkflowContext) -> PolicyResult:
        channel = context.payload.get("channel", "")
        channel_is_not_protected = channel not in protected_channels
        return PolicyResult(
            policy="no_bulk_channel_blast",
            passed=channel_is_not_protected,
            reason=(
                f"Channel '{channel}' is not in the protected list"
                if channel_is_not_protected
                else f"Posting to '{channel}' is blocked — it is a protected channel"
            ),
        )
    return _policy


def no_dm_external_users(allowed_domains: list[str]):
    """Block DMing users outside approved email domains."""
    def _policy(context: WorkflowContext) -> PolicyResult:
        user_email = context.payload.get("user_email", "")
        domain = user_email.split("@")[-1] if "@" in user_email else ""
        domain_is_allowed = domain in allowed_domains
        return PolicyResult(
            policy="no_dm_external_users",
            passed=domain_is_allowed,
            reason=(
                f"User '{user_email}' is in an approved domain"
                if domain_is_allowed
                else f"DM to '{user_email}' blocked — domain '{domain}' is not in the allowed list"
            ),
        )
    return _policy
```

---

### `enact/workflows/post_slack_message.py`

```python
"""
Reference workflow: post a message to a Slack channel.

Expected payload: {"channel": str, "text": str}
Expected systems: context.systems["slack"] — SlackConnector
"""
from enact.models import WorkflowContext, ActionResult


def post_slack_message_workflow(context: WorkflowContext) -> list[ActionResult]:
    slack = context.systems["slack"]
    return [
        slack.send_message(
            channel=context.payload["channel"],
            text=context.payload["text"],
        )
    ]
```

---

### `tests/test_slack.py`

```python
"""Tests for SlackConnector."""
import sys
from unittest.mock import MagicMock, patch
import pytest

# Mock slack_sdk before importing the connector (it's an optional dep)
_slack_sdk_mock = MagicMock()
_slack_errors_mock = MagicMock()

class _FakeSlackApiError(Exception):
    def __init__(self, message="", response=None):
        super().__init__(message)
        self.response = response or {}

_slack_errors_mock.SlackApiError = _FakeSlackApiError
sys.modules.setdefault("slack_sdk", _slack_sdk_mock)
sys.modules.setdefault("slack_sdk.errors", _slack_errors_mock)
_slack_sdk_mock.WebClient = MagicMock

from enact.connectors.slack import SlackConnector  # noqa: E402


@pytest.fixture
def connector():
    with patch("enact.connectors.slack.WebClient"):
        conn = SlackConnector(token="xoxb-fake")
    conn._client = MagicMock()
    conn._client.conversations_history.return_value = {"ok": True, "messages": []}
    return conn


class TestSendMessage:
    def test_happy_path(self, connector):
        connector._client.chat_postMessage.return_value = {
            "ok": True, "ts": "111.222", "channel": "C123"
        }
        result = connector.send_message(channel="C123", text="hello")
        assert result.success is True
        assert result.action == "send_message"
        assert result.output["ts"] == "111.222"
        assert result.output["already_done"] is False
        assert result.rollback_data == {"channel": "C123", "ts": "111.222"}

    def test_already_done_when_duplicate_found(self, connector):
        connector._client.conversations_history.return_value = {
            "ok": True,
            "messages": [{"text": "hello", "bot_id": "B123", "ts": "999.000"}],
        }
        result = connector.send_message(channel="C123", text="hello")
        assert result.output["already_done"] == "sent"
        assert result.output["ts"] == "999.000"
        connector._client.chat_postMessage.assert_not_called()

    def test_not_deduplicated_when_text_differs(self, connector):
        connector._client.conversations_history.return_value = {
            "ok": True,
            "messages": [{"text": "other", "bot_id": "B123", "ts": "999.000"}],
        }
        connector._client.chat_postMessage.return_value = {"ok": True, "ts": "111.222", "channel": "C123"}
        result = connector.send_message(channel="C123", text="hello")
        assert result.output["already_done"] is False

    def test_not_deduplicated_when_not_from_bot(self, connector):
        connector._client.conversations_history.return_value = {
            "ok": True, "messages": [{"text": "hello", "ts": "999.000"}],  # no bot_id
        }
        connector._client.chat_postMessage.return_value = {"ok": True, "ts": "111.222", "channel": "C123"}
        result = connector.send_message(channel="C123", text="hello")
        assert result.output["already_done"] is False

    def test_slack_api_error(self, connector):
        connector._client.chat_postMessage.side_effect = _FakeSlackApiError("channel_not_found")
        result = connector.send_message(channel="CBAD", text="hello")
        assert result.success is False
        assert "channel_not_found" in result.output["error"]

    def test_history_failure_does_not_block_send(self, connector):
        connector._client.conversations_history.side_effect = _FakeSlackApiError("missing_scope")
        connector._client.chat_postMessage.return_value = {"ok": True, "ts": "111.222", "channel": "C123"}
        result = connector.send_message(channel="C123", text="hello")
        assert result.success is True

    def test_action_not_allowed(self, connector):
        connector._allowed = {"send_dm"}
        with pytest.raises(PermissionError, match="send_message"):
            connector.send_message(channel="C123", text="hello")


class TestSendDm:
    def _setup(self, connector, user_id="U456", dm_channel="D789"):
        connector._client.users_lookupByEmail.return_value = {"ok": True, "user": {"id": user_id}}
        connector._client.conversations_open.return_value = {"ok": True, "channel": {"id": dm_channel}}

    def test_happy_path(self, connector):
        self._setup(connector)
        connector._client.chat_postMessage.return_value = {"ok": True, "ts": "111.222", "channel": "D789"}
        result = connector.send_dm(user_email="alice@acme.com", text="hi")
        assert result.success is True
        assert result.output["already_done"] is False
        assert result.rollback_data == {"channel": "D789", "ts": "111.222"}

    def test_already_done_when_duplicate(self, connector):
        self._setup(connector, dm_channel="D789")
        connector._client.conversations_history.return_value = {
            "ok": True, "messages": [{"text": "hi", "bot_id": "B123", "ts": "888.000"}],
        }
        result = connector.send_dm(user_email="alice@acme.com", text="hi")
        assert result.output["already_done"] == "sent"
        connector._client.chat_postMessage.assert_not_called()

    def test_user_not_found(self, connector):
        connector._client.users_lookupByEmail.side_effect = _FakeSlackApiError("users_not_found")
        result = connector.send_dm(user_email="ghost@acme.com", text="hi")
        assert result.success is False
        assert "users_not_found" in result.output["error"]


class TestDeleteMessage:
    def test_happy_path(self, connector):
        connector._client.chat_delete.return_value = {"ok": True}
        result = connector.delete_message(channel="C123", ts="111.222")
        assert result.success is True
        assert result.output["already_done"] is False

    def test_already_deleted(self, connector):
        connector._client.chat_delete.side_effect = _FakeSlackApiError("message_not_found")
        result = connector.delete_message(channel="C123", ts="111.222")
        assert result.success is True
        assert result.output["already_done"] == "deleted"

    def test_api_error(self, connector):
        connector._client.chat_delete.side_effect = _FakeSlackApiError("cant_delete_message")
        result = connector.delete_message(channel="C123", ts="111.222")
        assert result.success is False
```

---

### `tests/test_slack_policies.py`

```python
"""Tests for Slack policies."""
import pytest
from enact.models import WorkflowContext
from enact.policies.slack import no_bulk_channel_blast, no_dm_external_users


def ctx(payload):
    return WorkflowContext(workflow="test", actor_email="a@b.com", payload=payload, systems={})


class TestNoBulkChannelBlast:
    def test_allowed_channel_passes(self):
        result = no_bulk_channel_blast(["#general"])(ctx({"channel": "#alerts"}))
        assert result.passed is True
        assert result.policy == "no_bulk_channel_blast"

    def test_protected_channel_blocked(self):
        result = no_bulk_channel_blast(["#general"])(ctx({"channel": "#general"}))
        assert result.passed is False
        assert "protected" in result.reason

    def test_missing_channel_passes(self):
        # Empty string doesn't match any protected channel
        result = no_bulk_channel_blast(["#general"])(ctx({}))
        assert result.passed is True


class TestNoDmExternalUsers:
    def test_internal_user_passes(self):
        result = no_dm_external_users(["acme.com"])(ctx({"user_email": "alice@acme.com"}))
        assert result.passed is True
        assert result.policy == "no_dm_external_users"

    def test_external_user_blocked(self):
        result = no_dm_external_users(["acme.com"])(ctx({"user_email": "vendor@external.com"}))
        assert result.passed is False
        assert "external.com" in result.reason

    def test_multiple_allowed_domains(self):
        result = no_dm_external_users(["acme.com", "acme-contractors.com"])(
            ctx({"user_email": "bob@acme-contractors.com"})
        )
        assert result.passed is True

    def test_no_at_sign_blocked(self):
        result = no_dm_external_users(["acme.com"])(ctx({"user_email": "notanemail"}))
        assert result.passed is False

    def test_missing_user_email_blocked(self):
        result = no_dm_external_users(["acme.com"])(ctx({}))
        assert result.passed is False
```

---

## A.5 Files to Modify

### `enact/rollback.py`

**1. Update module docstring** — add to the inverse map block:
```
slack.send_message   -> slack.delete_message  (chat.delete by ts)
slack.send_dm        -> slack.delete_message  (chat.delete by ts)
```

**2. In `execute_rollback_action()`, after the `filesystem` elif, add:**
```python
    elif action_result.system == "slack":
        return _rollback_slack(action_result.action, rd, connector)
```

**3. After `_rollback_filesystem()`, add:**
```python
def _rollback_slack(action: str, rd: dict, connector) -> ActionResult:
    try:
        if action in ("send_message", "send_dm"):
            if not rd.get("channel") or not rd.get("ts"):
                return ActionResult(
                    action=f"rollback_{action}", system="slack", success=True,
                    output={"already_done": "skipped", "reason": "message was already a noop"},
                )
            return connector.delete_message(channel=rd["channel"], ts=rd["ts"])
        else:
            return ActionResult(
                action=f"rollback_{action}", system="slack", success=False,
                output={"error": f"No rollback handler for slack.{action}"},
            )
    except Exception as e:
        return ActionResult(
            action=f"rollback_{action}", system="slack", success=False,
            output={"error": f"Rollback failed for slack.{action}: {str(e)}"},
        )
```

### `pyproject.toml`

Add to `[project.optional-dependencies]`:
```toml
slack = ["slack-sdk>=3.0"]
```

Add `"slack-sdk>=3.0"` to the `dev` list so `pip install -e ".[dev]"` installs it.

### `index.html`

Remove `<span class="badge-soon">coming soon</span>` from `post_slack_message_workflow` line.

---

## A.6 Edge Cases & Error Handling

| Scenario | Handling | Test? |
|---|---|---|
| History API missing scope | `_find_recent_message` catches `SlackApiError`, returns None | yes |
| Channel not found | `ActionResult(success=False, output={"error": ...})` | yes |
| User email not in workspace | `SlackApiError("users_not_found")` → `success=False` | yes |
| Message already deleted on rollback | `message_not_found` → `already_done="deleted"`, `success=True` | yes |
| Human message same text (no dedup) | Only dedup if `msg.get("bot_id")` truthy | yes |
| Action not in allowlist | `PermissionError` | yes |
| `rollback_data={}` (already_done path) | Rollback returns `already_done="skipped"` | yes (rollback tests) |
| `no_dm_external_users` with no payload key | `domain=""` → not in allowed → BLOCK | yes |

---

## A.7 Implementation Cycles

### Cycle 1 — `send_message` happy path + allowlist
RED: `test_happy_path`, `test_action_not_allowed`
GREEN: Create `enact/connectors/slack.py` — `__init__`, `_check_allowed`, `send_message` (no dedup)
VERIFY: `pytest tests/test_slack.py::TestSendMessage::test_happy_path tests/test_slack.py::TestSendMessage::test_action_not_allowed -v`
COMMIT: `"feat: add SlackConnector with send_message"`

### Cycle 2 — `send_message` idempotency
RED: `test_already_done_when_duplicate_found`, `test_not_deduplicated_*`, `test_history_failure_*`
GREEN: Add `_find_recent_message()`, plug into `send_message`
VERIFY: `pytest tests/test_slack.py::TestSendMessage -v`
COMMIT: `"feat: add send_message idempotency via history scan"`

### Cycle 3 — `send_dm`
RED: `TestSendDm` tests
GREEN: Add `send_dm()` to connector
VERIFY: `pytest tests/test_slack.py::TestSendDm -v`
COMMIT: `"feat: add send_dm to SlackConnector"`

### Cycle 4 — `delete_message` + rollback wiring
RED: `TestDeleteMessage` tests + rollback tests in `tests/test_rollback.py`
GREEN: Add `delete_message()` to connector; add `_rollback_slack()` to `rollback.py`
VERIFY: `pytest tests/test_slack.py::TestDeleteMessage tests/test_rollback.py -v`
COMMIT: `"feat: add Slack rollback via delete_message"`

### Cycle 5 — Slack policies
RED: All `tests/test_slack_policies.py` tests
GREEN: Create `enact/policies/slack.py`
VERIFY: `pytest tests/test_slack_policies.py -v`
COMMIT: `"feat: add no_bulk_channel_blast and no_dm_external_users policies"`

### Cycle 6 — `post_slack_message_workflow`
RED: Workflow tests in `tests/test_workflows.py`
GREEN: Create `enact/workflows/post_slack_message.py`
VERIFY: `pytest tests/test_workflows.py -v`
COMMIT: `"feat: add post_slack_message_workflow"`

### Cycle 7 — Wiring + cleanup
- Add `slack-sdk>=3.0` to `[slack]` and `[dev]` in `pyproject.toml`
- Remove `coming soon` badge from `index.html`
- `pytest -v` — full suite
- Update `Handoff.md`
COMMIT: `"docs: remove coming-soon badge; add slack-sdk dep"`

---

## A.8 Success Criteria

- [ ] `pytest -v` — all tests pass (target: ~351 total)
- [ ] `already_done` convention on all mutating methods
- [ ] `rollback_data` populated on `send_message` and `send_dm`
- [ ] Rollback dispatches to `delete_message`
- [ ] Both policies use verbose boolean names
- [ ] `post_slack_message_workflow` badge removed from `index.html`
- [ ] `slack-sdk` in `[slack]` and `[dev]` optional deps
- [ ] `Handoff.md` updated
- [ ] Committed and pushed
