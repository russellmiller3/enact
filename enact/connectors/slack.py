"""
Slack connector — wraps slack-sdk WebClient for safe, allowlist-gated messaging.

Design: allowlist-first
------------------------
Every public method calls _check_allowed() before touching the Slack API.

Error handling pattern
-----------------------
All methods catch SlackApiError (and generic Exception as fallback) and return
ActionResult(success=False, output={"error": ...}). SlackApiError.response["error"]
gives the Slack error code string.
_check_allowed() raises PermissionError — programming error, blow up loudly.

Idempotency (already_done convention)
--------------------------------------
post_message: always already_done=False. Messages are intentionally not idempotent —
posting the same text twice is two messages, not a duplicate.
delete_message: already_done="deleted" if Slack returns "message_not_found"
(message already deleted or never existed).

Rollback
---------
post_message is reversible via delete_message.
rollback_data stores response["channel"] (the resolved Slack channel ID), NOT the
input channel. This matters for DM posts: input may be a user ID (U123) but Slack
responds with the DM channel ID (D456). chat.delete requires D456.

Rollback constraint: the bot token must have chat:delete scope, and can only delete
messages it posted. Human messages cannot be deleted by the bot.

delete_message is NOT in the default allowlist. Add it explicitly to enable rollback:
    SlackConnector(token=..., allowed_actions=["post_message", "delete_message"])

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

    Instantiate once and pass into EnactClient(systems={"slack": slack}).
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
            # Must be explicitly added: allowed_actions=["post_message", "delete_message"]
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

        rollback_data uses response["channel"] (the resolved channel ID), not the
        input channel, so delete_message targets the correct channel for DM rollbacks.
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
