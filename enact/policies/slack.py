"""
Slack policies — prevent bad Slack operations before they reach the connector.

Payload keys used by this module:
  "channel" — Slack channel ID or name (both policies)

Slack channel ID conventions:
  C... = public/private channel
  D... = direct message channel
  U... = user ID (Slack API converts to a DM channel on delivery)
  G... = legacy group DM (not blocked by block_dms — known v1 gap)
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

    Slack DM channel IDs start with "D". User IDs start with "U" (Slack converts
    them to DM channels on delivery). This policy blocks both conventions.

    Known gap: legacy group DM channels start with "G" and are not blocked here.
    If you need to block G... channels, use require_channel_allowlist instead.

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
