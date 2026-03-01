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
