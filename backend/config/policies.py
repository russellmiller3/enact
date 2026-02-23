"""
ABAC Policy Rules - 8 deterministic checks
Each function returns: {policy: str, requirement: str, user_value: str, match: bool}

Edit these functions to change policy behavior!
"""

def check_role_authorization(user, dataset, access_level):
    """Check if user's role is in dataset's allowed roles for access level"""
    roles_map = {
        "read": dataset.get("read_roles", []),
        "write": dataset.get("write_roles", []),
        "admin": dataset.get("admin_roles", [])
    }
    required_roles = roles_map.get(access_level, [])
    user_role = user.get("role")
    
    return {
        "policy": "Role Authorization",
        "requirement": f"One of: [{', '.join(required_roles)}]",
        "user_value": user_role or "No role in system",
        "match": user_role in required_roles
    }

def check_clearance_level(user, dataset, access_level):
    """Check if user's clearance meets dataset minimum"""
    min_clearance = dataset.get("min_clearance", 0)
    user_clearance = user.get("clearance_level", 0)
    
    return {
        "policy": "Clearance Level",
        "requirement": f"Minimum: Level {min_clearance}",
        "user_value": f"Level {user_clearance} (verified)",
        "match": user_clearance >= min_clearance
    }

def check_access_level(user, dataset, access_level):
    """Only READ requests auto-approve; WRITE/ADMIN escalate"""
    auto_approve_eligible = (access_level == "read")
    
    return {
        "policy": "Access Level Restriction",
        "requirement": "READ requests: auto-approve eligible",
        "user_value": f"Requesting {access_level.upper()} access",
        "match": auto_approve_eligible
    }

def check_pii_restriction(user, dataset, access_level):
    """Check PII handling requirements"""
    contains_pii = dataset.get("contains_pii", False)
    
    if not contains_pii:
        return {
            "policy": "PII Restriction",
            "requirement": "No PII in dataset",
            "user_value": "N/A",
            "match": True
        }
    
    # Contractor restriction
    if dataset.get("pii_contractor_restriction") and user.get("employee_type") == "Contractor":
        return {
            "policy": "PII Restriction",
            "requirement": "FTE only for PII datasets",
            "user_value": "Contractor (requires manager approval)",
            "match": False
        }
    
    # PII training check
    has_pii_training = "PII_Handling_2026" in user.get("training_completed", [])
    return {
        "policy": "PII Restriction",
        "requirement": "PII training required",
        "user_value": "Completed PII_Handling_2026" if has_pii_training else "Missing PII training",
        "match": has_pii_training
    }

def check_training_requirements(user, dataset, access_level):
    """Check if user has completed required training"""
    required_training = dataset.get("required_training", [])
    user_training = user.get("training_completed", [])
    
    missing = [t for t in required_training if t not in user_training]
    
    if not missing:
        latest_training = required_training[0] if required_training else None
        training_date = user.get("training_dates", {}).get(latest_training, "unknown date")
        return {
            "policy": "Training Requirements",
            "requirement": ", ".join(required_training),
            "user_value": f"Completed {training_date}",
            "match": True
        }
    
    return {
        "policy": "Training Requirements",
        "requirement": ", ".join(required_training),
        "user_value": f"Missing: {', '.join(missing)}",
        "match": False
    }

def check_employment_type(user, dataset, access_level):
    """Check if employment type is valid"""
    emp_type = user.get("employee_type")
    valid = emp_type in ["FTE", "Contractor"]
    
    return {
        "policy": "Employment Type",
        "requirement": "FTE or approved contractor",
        "user_value": f"{emp_type} (verified via HR system)" if emp_type else "No employment record",
        "match": valid
    }

def check_mnpi_blackout(user, dataset, access_level):
    """Check if dataset contains MNPI (Material Non-Public Information)"""
    contains_mnpi = dataset.get("contains_mnpi", False)
    classification = dataset.get("classification", "Unknown")
    
    return {
        "policy": "MNPI Blackout",
        "requirement": "Dataset not tagged MNPI",
        "user_value": "MNPI dataset (manual review required)" if contains_mnpi else f"N/A - Dataset is {classification}",
        "match": not contains_mnpi
    }

def check_time_limited_access(user, dataset, access_level):
    """All access expires in 90 days"""
    return {
        "policy": "Time-Limited Access",
        "requirement": "All access expires in 90 days",
        "user_value": "Expiry will be set to +90 days",
        "match": True
    }

def check_contractor_escalation(user, dataset, access_level):
    """ALL contractors require manager approval escalation - FTE only for auto-approve"""
    emp_type = user.get("employee_type")
    
    if emp_type == "Contractor":
        return {
            "policy": "Contractor Escalation",
            "requirement": "FTE only for auto-approval",
            "user_value": "Contractor (requires manager approval)",
            "match": False  # Forces escalation via amber badge
        }
    
    return {
        "policy": "Contractor Escalation",
        "requirement": "FTE only for auto-approval",
        "user_value": f"{emp_type} (verified)" if emp_type else "No employment type",
        "match": True
    }

# Policy registry
ABAC_POLICIES = [
    check_role_authorization,
    check_clearance_level,
    check_access_level,
    check_pii_restriction,
    check_training_requirements,
    check_employment_type,
    check_mnpi_blackout,
    check_time_limited_access,
    check_contractor_escalation
]
