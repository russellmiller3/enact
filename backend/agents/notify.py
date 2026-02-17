"""
Notification Agent: Template-based message generation
Generates email/Slack/ServiceNow messages based on decision
"""
import time
from models import NotificationResult, NotificationMessage

def run_notify(
    decision: str,
    requester_email: str,
    dataset_name: str,
    access_level: str,
    justification: str,
    user_name: str = "User",
    manager_email: str = None,
    token: str = None,
    expires_at: str = None
) -> NotificationResult:
    """
    Generate notification messages for all channels
    Templates based on decision type
    """
    print("\n" + "="*60)
    print("📧 NOTIFICATION AGENT - Sending notifications")
    print("="*60)
    print(f"📋 Decision: {decision}")
    print(f"👤 Recipient: {user_name} ({requester_email})")
    
    start_time = time.time()
    
    messages = []
    
    if decision == "APPROVE":
        print(f"✓ Generating APPROVED notifications...")
        messages = _generate_approved_messages(
            requester_email, user_name, dataset_name, access_level, token, expires_at
        )
    elif decision == "ESCALATE":
        print(f"⚠️  Generating ESCALATION notifications...")
        messages = _generate_escalated_messages(
            requester_email, user_name, dataset_name, access_level, justification, manager_email
        )
    else:  # DENY
        print(f"❌ Generating DENIED notifications...")
        messages = _generate_denied_messages(
            requester_email, user_name, dataset_name, access_level, justification
        )
    
    channels = list(set([m.channel for m in messages]))
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    print(f"📬 Sending {len(messages)} notifications across {len(channels)} channels:")
    for ch in channels:
        count = sum(1 for m in messages if m.channel == ch)
        print(f"   • {ch}: {count} message(s)")
    print(f"⏱️  Notifications completed in {duration_ms}ms")
    print("="*60 + "\n")
    
    return NotificationResult(
        duration_ms=duration_ms,
        channels=channels,
        messages=messages
    )

def _generate_approved_messages(requester, name, dataset, access_level, token, expires_at):
    """Templates for APPROVE decision"""
    messages = []
    
    # Email
    email_text = f"""Hi {name},

Your request for {access_level.upper()} access to {dataset} has been APPROVED.

Access Details:
• Dataset: {dataset}
• Access Level: {access_level.upper()}
• Expires: {expires_at}
• Token: {token[:20]}...

You can now query this dataset using your assigned credentials.

Questions? Contact the Data Governance team.

---
Automated message from Visa GDO Access System"""
    
    messages.append(NotificationMessage(
        channel="email",
        label=f"To: {requester}",
        text=email_text
    ))
    
    # Slack
    slack_text = f"""✅ *Access Approved*
User: {name} ({requester})
Dataset: `{dataset}`
Level: {access_level.upper()}
Expires: {expires_at}"""
    
    messages.append(NotificationMessage(
        channel="slack",
        label="#data-access-notifications",
        text=slack_text
    ))
    
    # ServiceNow ticket
    snow_text = f"""TICKET AUTO-CLOSED

Request: Data Access - {dataset}
Requester: {requester}
Status: APPROVED (auto-approved via ABAC policy checks)
Access Level: {access_level.upper()}
Expiry Date: {expires_at}

All policy checks passed. No manual review required.
Token generated and delivered to requester."""
    
    messages.append(NotificationMessage(
        channel="servicenow",
        label="Ticket #REQ-AUTO-CLOSE",
        text=snow_text
    ))
    
    # Audit log
    audit_text = f"ACCESS_GRANTED | {requester} | {dataset} | {access_level} | expires:{expires_at} | decision:APPROVE | auto-approved"
    
    messages.append(NotificationMessage(
        channel="audit_log",
        label="Compliance Log",
        text=audit_text
    ))
    
    return messages

def _generate_escalated_messages(requester, name, dataset, access_level, justification, manager):
    """Templates for ESCALATE decision"""
    messages = []
    
    # Email to requester
    requester_email = f"""Hi {name},

Your request for {access_level.upper()} access to {dataset} requires manager approval.

Request Details:
• Dataset: {dataset}
• Access Level: {access_level.upper()}
• Justification: {justification}

Your manager ({manager or 'your manager'}) has been notified and will review your request.

You'll receive an update within 2 business days.

---
Automated message from Visa GDO Access System"""
    
    messages.append(NotificationMessage(
        channel="email",
        label=f"To: {requester}",
        text=requester_email
    ))
    
    # Email to manager
    manager_email_text = f"""Hi,

One of your team members has requested data access that requires your approval.

Requester: {name} ({requester})
Dataset: {dataset}
Access Level: {access_level.upper()}
Justification: "{justification}"

Review and approve/deny: https://gdo.visa.com/reviews/pending

---
Automated message from Visa GDO Access System"""
    
    messages.append(NotificationMessage(
        channel="email",
        label=f"To: {manager or 'manager@visa.com'}",
        text=manager_email_text
    ))
    
    # Slack
    slack_text = f"""⚠️ *Escalation Required*
User: {name} ({requester})
Dataset: `{dataset}`
Level: {access_level.upper()}
Reason: Manager approval needed
Assigned to: {manager or 'Manager'}"""
    
    messages.append(NotificationMessage(
        channel="slack",
        label="#data-access-escalations",
        text=slack_text
    ))
    
    # ServiceNow ticket
    snow_text = f"""TICKET ESCALATED TO MANAGER

Request: Data Access - {dataset}
Requester: {requester}
Status: PENDING APPROVAL
Access Level: {access_level.upper()}
Justification: {justification}

Assigned to: {manager or 'Manager'}
SLA: 2 business days"""
    
    messages.append(NotificationMessage(
        channel="servicenow",
        label="Ticket #REQ-ESCALATED",
        text=snow_text
    ))
    
    return messages

def _generate_denied_messages(requester, name, dataset, access_level, justification):
    """Templates for DENY decision"""
    messages = []
    
    # Email
    email_text = f"""Hi {name},

Your request for {access_level.upper()} access to {dataset} has been DENIED.

Request Details:
• Dataset: {dataset}
• Access Level: {access_level.upper()}
• Justification: {justification}

Reason: You do not meet the required policy criteria for this dataset.

If you believe this is an error, contact the Data Governance team at gdosupport@visa.com.

---
Automated message from Visa GDO Access System"""
    
    messages.append(NotificationMessage(
        channel="email",
        label=f"To: {requester}",
        text=email_text
    ))
    
    # Slack
    slack_text = f"""🚫 *Access Denied*
User: {name} ({requester})
Dataset: `{dataset}`
Level: {access_level.upper()}
Reason: Policy criteria not met"""
    
    messages.append(NotificationMessage(
        channel="slack",
        label="#data-access-notifications",
        text=slack_text
    ))
    
    # ServiceNow
    snow_text = f"""TICKET AUTO-CLOSED (DENIED)

Request: Data Access - {dataset}
Requester: {requester}
Status: DENIED
Access Level: {access_level.upper()}

Reason: User does not meet policy requirements for this dataset.
No manual review required - automatic denial per ABAC rules."""
    
    messages.append(NotificationMessage(
        channel="servicenow",
        label="Ticket #REQ-AUTO-DENY",
        text=snow_text
    ))
    
    # Audit log
    audit_text = f"ACCESS_DENIED | {requester} | {dataset} | {access_level} | decision:DENY | policy-violation"
    
    messages.append(NotificationMessage(
        channel="audit_log",
        label="Compliance Log",
        text=audit_text
    ))
    
    return messages
