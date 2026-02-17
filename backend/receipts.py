"""
Audit receipt writer
Generates plaintext audit receipts for compliance
"""
import os
from pathlib import Path
from datetime import datetime
from models import AuditResult, AuditEntry

RECEIPTS_DIR = Path(__file__).parent / "receipts"

def generate_receipt(
    request_id: str,
    decision: str,
    requester_email: str,
    requester_name: str,
    dataset_name: str,
    access_level: str,
    justification: str,
    abac_checks: list,
    discovery_tokens: int = 0,
    intake_tokens: int = 0,
    discovery_ms: int = 0,
    intake_ms: int = 0,
    policy_ms: int = 0,
    provision_ms: int = 0,
    notify_ms: int = 0
) -> AuditResult:
    """
    Generate and save audit receipt
    Returns receipt path and audit entries
    """
    # Ensure receipts directory exists
    RECEIPTS_DIR.mkdir(exist_ok=True)
    
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{request_id}_{timestamp}.txt"
    filepath = RECEIPTS_DIR / filename
    
    # Generate receipt content
    receipt_lines = []
    receipt_lines.append("=" * 80)
    receipt_lines.append("ACCESS DECISION RECEIPT")
    receipt_lines.append("=" * 80)
    receipt_lines.append("")
    receipt_lines.append(f"Request ID: {request_id}")
    receipt_lines.append(f"Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    receipt_lines.append(f"Decision: {decision}")
    receipt_lines.append("")
    receipt_lines.append("-" * 80)
    receipt_lines.append("REQUEST DETAILS")
    receipt_lines.append("-" * 80)
    receipt_lines.append("")
    receipt_lines.append(f"WHO:    {requester_name} ({requester_email})")
    receipt_lines.append(f"WHAT:   {access_level.upper()} access to {dataset_name}")
    receipt_lines.append(f"REASON: {justification}")
    receipt_lines.append("")
    receipt_lines.append("-" * 80)
    receipt_lines.append("POLICY EVALUATION RESULTS")
    receipt_lines.append("-" * 80)
    receipt_lines.append("")
    
    for i, check in enumerate(abac_checks, 1):
        status = "✓ PASS" if check.match else "✗ FAIL"
        receipt_lines.append(f"{i}. {check.policy}: {status}")
        receipt_lines.append(f"   Requirement: {check.requirement}")
        receipt_lines.append(f"   User Value:  {check.user_value}")
        receipt_lines.append("")
    
    receipt_lines.append("-" * 80)
    receipt_lines.append("TECHNICAL LOG")
    receipt_lines.append("-" * 80)
    receipt_lines.append("")
    receipt_lines.append(f"Discovery Agent:    {discovery_ms}ms, {discovery_tokens} tokens (Claude)")
    receipt_lines.append(f"Intake Agent:       {intake_ms}ms, {intake_tokens} tokens (Claude)")
    receipt_lines.append(f"Policy Engine:      {policy_ms}ms, 0 tokens (Python ABAC)")
    if provision_ms > 0:
        receipt_lines.append(f"Provisioning Agent: {provision_ms}ms")
    receipt_lines.append(f"Notification Agent: {notify_ms}ms")
    receipt_lines.append("")
    total_ms = discovery_ms + intake_ms + policy_ms + provision_ms + notify_ms
    total_tokens = discovery_tokens + intake_tokens
    receipt_lines.append(f"Total Execution Time: {total_ms}ms")
    receipt_lines.append(f"Total LLM Tokens: {total_tokens}")
    receipt_lines.append("")
    receipt_lines.append("-" * 80)
    receipt_lines.append("COMPLIANCE NOTES")
    receipt_lines.append("-" * 80)
    receipt_lines.append("")
    receipt_lines.append("• All access decisions are logged and auditable")
    receipt_lines.append("• This receipt is stored for compliance review")
    receipt_lines.append("• Policy engine uses deterministic ABAC rules (no LLM)")
    receipt_lines.append("• LLM used only for natural language understanding (discovery + intake)")
    receipt_lines.append("")
    receipt_lines.append("=" * 80)
    receipt_lines.append("END OF RECEIPT")
    receipt_lines.append("=" * 80)
    
    # Write to file (UTF-8 encoding for Windows compatibility with Unicode chars)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(receipt_lines))
    
    # Generate audit entries (for SSE event)
    entries = []
    
    entries.append(AuditEntry(
        timestamp=datetime.utcnow().strftime("%H:%M:%S UTC"),
        agent="DiscoveryAgent",
        action="dataset_search",
        detail=f"{discovery_tokens} tokens, {discovery_ms}ms"
    ))
    
    entries.append(AuditEntry(
        timestamp=datetime.utcnow().strftime("%H:%M:%S UTC"),
        agent="IntakeAgent",
        action="parse_request",
        detail=f"{intake_tokens} tokens, {intake_ms}ms"
    ))
    
    passed = sum(1 for c in abac_checks if c.match)
    entries.append(AuditEntry(
        timestamp=datetime.utcnow().strftime("%H:%M:%S UTC"),
        agent="ABACPolicyEngine",
        action="policy_check",
        detail=f"{decision} ({passed}/{len(abac_checks)} checks passed, loaded from config files)"
    ))
    
    if provision_ms > 0:
        entries.append(AuditEntry(
            timestamp=datetime.utcnow().strftime("%H:%M:%S UTC"),
            agent="ProvisioningAgent",
            action="grant_access",
            detail=f"token generated, {provision_ms}ms"
        ))
    
    entries.append(AuditEntry(
        timestamp=datetime.utcnow().strftime("%H:%M:%S UTC"),
        agent="NotificationAgent",
        action="send_notifications",
        detail=f"messages sent, {notify_ms}ms"
    ))
    
    return AuditResult(
        request_id=request_id,
        receipt_path=str(filepath.relative_to(Path(__file__).parent)),
        entries=entries
    )
