"""
Email notifications for HITL approval requests.

Uses smtplib (standard library) so there are no additional deps.
Configure via env vars:

    SMTP_HOST=smtp.sendgrid.net
    SMTP_PORT=587
    SMTP_USER=apikey
    SMTP_PASS=SG.xxx
    EMAIL_FROM=enact@enact.cloud
    CLOUD_BASE_URL=https://enact.cloud

For local dev: set ENACT_EMAIL_DRY_RUN=1 to print instead of send.
"""
import os
import smtplib
from email.mime.text import MIMEText
from cloud.token import make_token

CLOUD_BASE_URL = os.environ.get("CLOUD_BASE_URL", "http://localhost:8000")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "enact@enact.cloud")


def send_approval_email(
    hitl_id: str,
    workflow: str,
    payload: dict,
    notify_email: str,
    expires_at: str,
):
    approve_token = make_token(hitl_id, "approve")
    deny_token = make_token(hitl_id, "deny")

    approve_url = f"{CLOUD_BASE_URL}/hitl/{hitl_id}/approve?t={approve_token}"
    deny_url = f"{CLOUD_BASE_URL}/hitl/{hitl_id}/deny?t={deny_token}"

    body = f"""Your AI agent wants to run a workflow and needs your approval.

Workflow:  {workflow}
Payload:   {payload}
Expires:   {expires_at}

APPROVE: {approve_url}

DENY:    {deny_url}

If you did not expect this request, click Deny and check your agent configuration.
"""

    msg = MIMEText(body)
    msg["Subject"] = f"[Enact] Approve: {workflow}"
    msg["From"] = EMAIL_FROM
    msg["To"] = notify_email

    dry_run = os.environ.get("ENACT_EMAIL_DRY_RUN", "0") == "1"
    if dry_run:
        print(f"[DRY RUN] Email to {notify_email}:\n{body}")
        return

    smtp_host = os.environ.get("SMTP_HOST", "localhost")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        if smtp_user:
            server.login(smtp_user, smtp_pass)
        server.send_message(msg)
