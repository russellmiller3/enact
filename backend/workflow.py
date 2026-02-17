"""
Workflow orchestration with SSE event emission
Coordinates all 5 agents and streams results
"""
import asyncio
import secrets
from typing import AsyncGenerator
from agents import run_discovery, run_intake, run_policy, run_provision, run_notify
from receipts import generate_receipt
from utils import get_user
from models import WorkflowComplete

async def run_workflow_stream(
    request_text: str,
    requester_email: str,
    selected_dataset: str = None
) -> AsyncGenerator[tuple[str, dict], None]:
    """
    Run complete workflow and yield SSE events
    Returns: (event_name, event_data) tuples
    """
    
    request_id = f"REQ-{secrets.randbelow(100000):05d}"
    print(f"\n{'='*60}")
    print(f"🚀 NEW REQUEST: {request_id}")
    print(f"   User: {requester_email}")
    print(f"   Text: {request_text[:80]}...")
    print(f"{'='*60}\n")
    
    # Get user info for later
    user = get_user(requester_email) or {"name": "Unknown User", "manager": None}
    user_name = user.get("name", "Unknown User")
    manager_email = user.get("manager")
    
    # Track metrics
    total_tokens = 0
    
    try:
        # ==================== AGENT 0: DISCOVERY ====================
        print(f"🔍 [1/5] Running Discovery Agent...")
        discovery_result = run_discovery(request_text, selected_dataset)
        total_tokens += discovery_result.tokens
        print(f"   ✓ Found {discovery_result.match_count} dataset(s) | {discovery_result.duration_ms}ms | {discovery_result.tokens} tokens")
        
        yield ("discovery", discovery_result.model_dump())
        
        # If no matches, error out
        if discovery_result.match_count == 0:
            error_data = {
                "error": "no_matches",
                "message": "No datasets match your request",
                "details": "Try searching for: fraud, customer, transactions, models"
            }
            yield ("error", error_data)
            return
        
        # Auto-select top match (highest score) if multiple matches
        # This provides smooth UX - user can always refine their request later
        final_dataset = selected_dataset or discovery_result.matches[0].dataset
        
        # Note: In production, you might show a modal for >1 matches
        # For demo purposes, we auto-select to keep flow smooth
        
        # ==================== AGENT 1: INTAKE ====================
        print(f"📥 [2/5] Running Intake Agent...")
        intake_result = run_intake(request_text, requester_email, final_dataset)
        total_tokens += intake_result.tokens
        print(f"   ✓ Extracted: {intake_result.extracted.access_level.upper()} access to {final_dataset} | {intake_result.duration_ms}ms | {intake_result.tokens} tokens")
        
        yield ("intake", intake_result.model_dump())
        
        # ==================== AGENT 2: POLICY ====================
        print(f"🛡️  [3/5] Running ABAC Policy Engine...")
        policy_result = run_policy(
            requester_email=requester_email,
            dataset_name=final_dataset,
            access_level=intake_result.extracted.access_level,
            justification=intake_result.extracted.justification
        )
        passed = sum(1 for c in policy_result.abac_checks if c.match)
        print(f"   ✓ Decision: {policy_result.decision} | {passed}/{policy_result.checks_run} checks passed | {policy_result.duration_ms}ms")
        
        yield ("policy", policy_result.model_dump())
        
        decision = policy_result.decision
        
        # ==================== AGENT 3: PROVISIONING (conditional) ====================
        provision_result = None
        provision_ms = 0
        token = None
        expires_at = None
        
        if decision == "APPROVE":
            print(f"🔑 [4/5] Running Provisioning Agent...")
            provision_result = run_provision(
                requester_email=requester_email,
                dataset_name=final_dataset,
                access_level=intake_result.extracted.access_level
            )
            provision_ms = provision_result.duration_ms
            token = provision_result.token
            expires_at = provision_result.expires_at
            print(f"   ✓ Access granted | Token: {token[:20]}... | {provision_ms}ms")
            
            yield ("provision", provision_result.model_dump())
        else:
            print(f"⏭️  [4/5] Provisioning skipped (decision: {decision})")
        
        # ==================== AGENT 4: NOTIFICATION ====================
        print(f"📧 [5/5] Running Notification Agent...")
        notify_result = run_notify(
            decision=decision,
            requester_email=requester_email,
            dataset_name=final_dataset,
            access_level=intake_result.extracted.access_level,
            justification=intake_result.extracted.justification,
            user_name=user_name,
            manager_email=manager_email,
            token=token,
            expires_at=expires_at
        )
        print(f"   ✓ Sent {len(notify_result.channels)} notifications | {notify_result.duration_ms}ms")
        
        yield ("notify", notify_result.model_dump())
        
        # ==================== AUDIT RECEIPT ====================
        print(f"📋 Generating audit receipt...")
        audit_result = generate_receipt(
            request_id=request_id,
            decision=decision,
            requester_email=requester_email,
            requester_name=user_name,
            dataset_name=final_dataset,
            access_level=intake_result.extracted.access_level,
            justification=intake_result.extracted.justification,
            abac_checks=policy_result.abac_checks,
            discovery_tokens=discovery_result.tokens,
            intake_tokens=intake_result.tokens,
            discovery_ms=discovery_result.duration_ms,
            intake_ms=intake_result.duration_ms,
            policy_ms=policy_result.duration_ms,
            provision_ms=provision_ms,
            notify_ms=notify_result.duration_ms
        )
        
        print(f"   ✓ Receipt saved: {audit_result.receipt_path}\n")
        
        yield ("audit", audit_result.model_dump())
        
        # ==================== WORKFLOW COMPLETE ====================
        total_ms = (
            discovery_result.duration_ms +
            intake_result.duration_ms +
            policy_result.duration_ms +
            provision_ms +
            notify_result.duration_ms
        )
        
        checks_passed = sum(1 for c in policy_result.abac_checks if c.match)
        checks_total = len(policy_result.abac_checks)
        agents_run = 5 if decision == "APPROVE" else 4
        
        complete_data = WorkflowComplete(
            decision=decision,
            agents_run=agents_run,
            checks_passed=checks_passed,
            checks_total=checks_total,
            total_ms=total_ms,
            total_tokens=total_tokens,
            request_id=request_id,
            receipt_path=audit_result.receipt_path
        )
        
        print(f"{'='*60}")
        print(f"✅ WORKFLOW COMPLETE: {decision}")
        print(f"   Agents: {agents_run} | Checks: {checks_passed}/{checks_total} | Time: {total_ms}ms | Tokens: {total_tokens}")
        print(f"   Request ID: {request_id}")
        print(f"{'='*60}\n")
        
        yield ("done", complete_data.model_dump())
        
    except Exception as e:
        error_data = {
            "error": "workflow_error",
            "message": str(e),
            "details": f"Error in workflow execution: {type(e).__name__}"
        }
        yield ("error", error_data)


async def run_workflow_json(request_text: str, requester_email: str, selected_dataset: str = None) -> dict:
    """
    Non-streaming version - returns complete workflow result as JSON
    Useful for testing/debugging
    """
    results = {
        "discovery": None,
        "intake": None,
        "policy": None,
        "provision": None,
        "notify": None,
        "audit": None,
        "complete": None,
        "error": None
    }
    
    async for event_name, event_data in run_workflow_stream(request_text, requester_email, selected_dataset):
        results[event_name] = event_data
    
    return results
