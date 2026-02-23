"""
Policy Agent: ABAC Policy Engine (NO LLM)
Deterministic rule-based decision making
Reads from config/users.json + config/datasets.json + config/policies.py
"""
import time
import sys
from pathlib import Path

# Import ABAC policy functions
sys.path.insert(0, str(Path(__file__).parent.parent / "config"))
from policies import ABAC_POLICIES

from utils import get_user, get_dataset
from models import PolicyResult, ABACCheck

def run_policy(requester_email: str, dataset_name: str, access_level: str, justification: str) -> PolicyResult:
    """
    Run ABAC policy checks - 100% deterministic, no LLM
    Decision based ONLY on data in config files
    """
    print("\n" + "="*60)
    print("🛡️  POLICY AGENT - ABAC Policy Engine (NO LLM)")
    print("="*60)
    print(f"👤 User: {requester_email}")
    print(f"📊 Dataset: {dataset_name}")
    print(f"🔐 Access Level: {access_level.upper()}")
    
    start_time = time.time()
    
    # Load user and dataset from config
    print("📂 Loading config/users.json + config/datasets.json...")
    user = get_user(requester_email)
    dataset = get_dataset(dataset_name)
    
    # Handle missing user/dataset
    if not user:
        user = {
            "name": "Unknown User",
            "role": None,
            "employee_type": None,
            "clearance_level": 0,
            "training_completed": [],
            "manager": None
        }
    
    if not dataset:
        dataset = {
            "name": dataset_name,
            "classification": "Unknown",
            "contains_pii": False,
            "contains_mnpi": False,
            "min_clearance": 0,
            "required_training": [],
            "read_roles": [],
            "write_roles": [],
            "admin_roles": []
        }
    
    # Run all 8 ABAC checks
    print(f"\n🔍 Running {len(ABAC_POLICIES)} ABAC policy checks line-by-line:\n")
    abac_checks = []
    
    for i, policy_func in enumerate(ABAC_POLICIES, 1):
        check_result = policy_func(user, dataset, access_level)
        
        # Add badge (frontend color coding) - pass access_level for smart escalation logic
        badge = _compute_badge(check_result, policy_func.__name__, access_level)
        check_result["badge"] = badge
        
        # Print each check with detailed info
        icon = "✓" if check_result["match"] else "✗"
        color_badge = {"g": "🟢", "a": "🟡", "r": "🔴", "s": "⚪"}[badge]
        
        print(f"  [{i}/8] {check_result['policy']}")
        print(f"       Requirement: {check_result['requirement']}")
        print(f"       User Value:  {check_result['user_value']}")
        print(f"       Result: {icon} {'PASS' if check_result['match'] else 'FAIL'} {color_badge}")
        print()
        
        abac_checks.append(ABACCheck(**check_result))
    
    passed = sum(1 for check in abac_checks if check.match)
    failed = len(abac_checks) - passed
    print(f"✅ Policy checks complete: {passed} passed, {failed} failed\n")
    
    # Make decision
    decision, justification_note = _make_decision(abac_checks, access_level, user, dataset, justification)
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    print(f"📋 Decision: {decision}")
    print(f"⏱️  Policy evaluation completed in {duration_ms}ms")
    print("="*60 + "\n")
    
    return PolicyResult(
        duration_ms=duration_ms,
        checks_run=len(abac_checks),
        abac_checks=abac_checks,
        decision=decision,
        justification_note=justification_note
    )

def _compute_badge(check_result: dict, policy_name: str, access_level: str = "read") -> str:
    """
    Compute badge color: g=green/pass, a=amber/escalate, r=red/fail, s=skip/N/A
    
    CRITICAL FIX: Role Authorization failures for write/admin access should escalate,
    not deny (because write/admin requires approval anyway)
    """
    match = check_result.get("match", False)
    
    if match:
        return "g"  # Green - passed
    
    # Failed checks
    policy_type = check_result.get("policy", "")
    
    # Access Level Restriction: WRITE/ADMIN fail is escalation (amber)
    if "Access Level" in policy_type:
        return "a"
    
    # Role Authorization: For write/admin access, escalate instead of deny
    # (because these access levels require approval anyway)
    if "Role Authorization" in policy_type and access_level in ["write", "admin"]:
        return "a"
    
    # PII contractor restriction: escalation (amber)
    if "PII" in policy_type and "Contractor" in check_result.get("user_value", ""):
        return "a"
    
    # Contractor escalation policy: always escalate (amber)
    if "Contractor Escalation" in policy_type:
        return "a"
    
    # Low confidence: escalation (amber)
    if "confidence" in policy_name.lower():
        return "a"
    
    # Hard failures (red)
    critical_policies = ["Role Authorization", "Clearance Level", "Training Requirements", "Employment Type"]
    if any(crit in policy_type for crit in critical_policies):
        return "r"
    
    # Default: red for failures
    return "r"

def _make_decision(checks: list, access_level: str, user: dict, dataset: dict, justification: str):
    """
    Decision logic:
    - All pass + READ → APPROVE
    - Any write/admin OR amber flags → ESCALATE
    - Any critical red fail → DENY
    """
    passes = [c for c in checks if c.match]
    fails = [c for c in checks if not c.match]
    
    # Check badge colors
    red_failures = [c for c in checks if c.badge == "r"]
    amber_flags = [c for c in checks if c.badge == "a"]
    
    # Decision tree
    if len(red_failures) > 0:
        decision = "DENY"
        justification_note = _generate_deny_note(red_failures, user, dataset)
    
    elif len(amber_flags) > 0:
        decision = "ESCALATE"
        justification_note = _generate_escalate_note(amber_flags, user, justification)
    
    elif len(passes) == len(checks):
        decision = "APPROVE"
        justification_note = f"Justification text '{justification}' logged for audit but not scored. Decision based on ABAC matching above."
    
    else:
        # Shouldn't happen but failsafe to ESCALATE
        decision = "ESCALATE"
        justification_note = "Uncertain policy outcome - requires manual review."
    
    return decision, justification_note

def _generate_approve_note(user: dict, dataset: dict) -> str:
    """Generate approval note"""
    return f"All policy checks passed for {user.get('role', 'user')} accessing {dataset.get('classification', 'Internal')} data. Request auto-approved."

def _generate_escalate_note(amber_flags: list, user: dict, justification: str) -> str:
    """Generate escalation note"""
    reasons = []
    for flag in amber_flags:
        if "Access Level" in flag.policy:
            reasons.append("Write/Admin access requires manager approval")
        elif "Contractor Escalation" in flag.policy:
            reasons.append("Contractor access requires manager approval")
        elif "Contractor" in flag.user_value:
            reasons.append("Contractor access to PII data requires manager approval")
        else:
            reasons.append(f"{flag.policy} requires review")
    
    reason_text = "; ".join(reasons)
    return f"{reason_text}. Justification logged for manager review: '{justification}'"

def _generate_deny_note(red_failures: list, user: dict, dataset: dict) -> str:
    """Generate denial note"""
    failed_policies = [f.policy for f in red_failures]
    
    if len(failed_policies) == 1:
        return f"Access denied: {failed_policies[0]} check failed. User does not meet requirements for this dataset."
    else:
        return f"Access denied: {len(failed_policies)} policy violations detected ({', '.join(failed_policies[:2])}{'...' if len(failed_policies) > 2 else ''})."
