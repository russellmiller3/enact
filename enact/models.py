"""
Enact core data models.

These define the shape of every object that flows through a run:
  WorkflowContext  — inputs to a run
  PolicyResult     — outcome of a single policy check
  ActionResult     — outcome of a single workflow action
  Receipt          — permanent signed record of the run
  RunResult        — what the caller gets back
"""

from pydantic import BaseModel, Field
from typing import Literal
import uuid


class WorkflowContext(BaseModel):
    """Everything the policy engine and workflow need to do their jobs."""
    workflow: str
    actor_email: str
    payload: dict
    systems: dict = Field(default_factory=dict)  # connector instances keyed by name


class PolicyResult(BaseModel):
    """Outcome of a single policy check."""
    policy: str
    passed: bool
    reason: str


class ActionResult(BaseModel):
    """Outcome of a single action taken by the workflow."""
    action: str    # e.g. "create_contact"
    system: str    # e.g. "hubspot"
    success: bool
    output: dict = Field(default_factory=dict)  # raw response from the connector


class Receipt(BaseModel):
    """Permanent signed record of everything that happened in a run."""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow: str
    actor_email: str
    payload: dict
    policy_results: list[PolicyResult]
    decision: Literal["PASS", "BLOCK"]
    actions_taken: list[ActionResult] = Field(default_factory=list)  # empty if BLOCK
    timestamp: str   # ISO8601 — set by receipt.py at write time
    signature: str   # HMAC-SHA256 hex digest — set by receipt.py at write time


class RunResult(BaseModel):
    """What the caller gets back from EnactClient.run()."""
    success: bool
    workflow: str
    output: dict = Field(default_factory=dict)
