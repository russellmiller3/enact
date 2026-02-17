"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal
from datetime import datetime

class WorkflowRequest(BaseModel):
    """User request input"""
    request_text: str
    requester_email: str
    selected_dataset: Optional[str] = None

class DatasetMatch(BaseModel):
    """Dataset discovery match"""
    dataset: str
    id: str
    description: str
    classification: str
    row_count: str
    column_count: int
    owner: str
    last_updated: str
    contains_pii: bool
    contains_mnpi: bool
    pii_contractor_restriction: bool = False  # Add contractor restriction flag
    keywords: List[str]
    match_score: float
    matched_keywords: List[str]
    columns: Optional[Dict[str, List[str]]] = None

class DiscoveryResult(BaseModel):
    """Discovery agent output"""
    agent: Literal["DiscoveryAgent"] = "DiscoveryAgent"
    status: str = "complete"
    duration_ms: int
    tokens: int
    matches: List[DatasetMatch]
    match_count: int

class IntakeExtraction(BaseModel):
    """Extracted request fields"""
    requester: str
    dataset: str
    access_level: Literal["read", "write", "admin"]
    justification: str
    urgency: Optional[str] = None
    confidence: float

class IntakeResult(BaseModel):
    """Intake agent output"""
    agent: Literal["IntakeAgent"] = "IntakeAgent"
    status: str = "complete"
    duration_ms: int
    tokens: int
    extracted: IntakeExtraction
    reasoning: List[str]

class ABACCheck(BaseModel):
    """Single ABAC policy check"""
    policy: str
    requirement: str
    user_value: str
    match: bool
    badge: Literal["g", "a", "r", "s"]  # green/amber/red/skip

class PolicyResult(BaseModel):
    """Policy agent output"""
    agent: Literal["ABACPolicyEngine"] = "ABACPolicyEngine"
    status: str = "complete"
    duration_ms: int
    checks_run: int
    abac_checks: List[ABACCheck]
    decision: Literal["APPROVE", "ESCALATE", "DENY"]
    justification_note: str

class ProvisionResult(BaseModel):
    """Provisioning agent output"""
    agent: Literal["ProvisioningAgent"] = "ProvisioningAgent"
    status: str = "complete"
    duration_ms: int
    token: str
    expires_at: str

class NotificationMessage(BaseModel):
    """Single notification message"""
    channel: str
    label: str
    text: str

class NotificationResult(BaseModel):
    """Notification agent output"""
    agent: Literal["NotificationAgent"] = "NotificationAgent"
    status: str = "complete"
    duration_ms: int
    channels: List[str]
    messages: List[NotificationMessage]

class AuditEntry(BaseModel):
    """Audit log entry"""
    timestamp: str
    agent: str
    action: str
    detail: str

class AuditResult(BaseModel):
    """Audit receipt output"""
    request_id: str
    receipt_path: str
    entries: List[AuditEntry]

class WorkflowComplete(BaseModel):
    """Final workflow summary"""
    decision: Literal["APPROVE", "ESCALATE", "DENY"]
    agents_run: int
    checks_passed: int
    checks_total: int
    total_ms: int
    total_tokens: int
    request_id: str
    receipt_path: str

class ErrorResult(BaseModel):
    """Error event"""
    error: str
    message: str
    details: Optional[str] = None
