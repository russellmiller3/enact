"""
Enact core data models.

These Pydantic models define the shape of every object that flows through a run.
All models are immutable by default (Pydantic v2 behaviour) — this is intentional.
Receipt and PolicyResult are never mutated after creation; sign_receipt() returns
a new Receipt rather than modifying the existing one.

Data flow through a single enact.run() call:

    WorkflowContext  — built from the caller's args; passed to every policy and the workflow
    PolicyResult     — one per policy; collected into a list before the decision is made
    ActionResult     — one per step the workflow takes; empty list if BLOCK
    Receipt          — permanent record; written to disk as signed JSON
    RunResult        — what the calling agent actually gets back (lightweight, no full policy detail)
"""

from pydantic import BaseModel, Field
from typing import Literal
import uuid


class WorkflowContext(BaseModel):
    """
    Everything a policy function or workflow function needs to do its job.

    Passed unchanged to every policy and to the workflow itself, so all
    participants see the same picture of the run. Systems (connectors) are
    included here so policies can do live lookups — e.g. dont_duplicate_contacts
    calls context.systems["hubspot"].get_contact() before the workflow runs.

    Fields:
        workflow     — name of the registered workflow being called
        user_email  — identity of the agent/user making the request; appears in every receipt
        payload      — arbitrary key-value data the workflow needs (repo name, contact email, etc.)
        systems      — dict of connector instances, keyed by name (e.g. {"github": GitHubConnector(...)})
    """
    workflow: str
    user_email: str
    payload: dict
    # Connector instances injected at EnactClient init time.
    # Keyed by the name callers use to retrieve them (e.g. context.systems["github"]).
    systems: dict = Field(default_factory=dict)


class PolicyResult(BaseModel):
    """
    Outcome of a single policy check.

    Every policy function returns exactly one of these. They are collected
    into a list by evaluate_all() and inspected by all_passed() to determine
    the run decision. All results — including failures — are stored in the
    Receipt so the audit trail shows the full picture, not just the first failure.

    Fields:
        policy  — machine-readable policy name (matches the function name by convention)
        passed  — True = allow, False = block (if any result is False, the whole run blocks)
        reason  — human-readable explanation; shown in receipts and logs
    """
    policy: str
    passed: bool
    reason: str


class ActionResult(BaseModel):
    """
    Outcome of a single action taken by the workflow.

    Workflows return a list of these — one per logical step (e.g. create_branch,
    then create_pr). Failed actions are included in the list so the receipt
    shows exactly how far the workflow got before it stopped.

    The 'output' dict contains the raw response from the connector (e.g. the
    GitHub PR number and URL, or an error string if success=False). Connectors
    are responsible for populating this — never raise exceptions from connectors,
    always return ActionResult(success=False, output={"error": str(e)}).

    Fields:
        action   — name of the operation (e.g. "create_branch", "insert_row")
        system   — name of the connector that handled it (e.g. "github", "postgres")
        success  — whether the action completed without error
        output   — raw connector response; may include IDs, URLs, error messages
    """
    action: str
    system: str
    success: bool
    # Raw connector response. Always a dict so receipts are cleanly serialisable to JSON.
    output: dict = Field(default_factory=dict)
    # Pre-action state needed to reverse this action at rollback time.
    # Connectors populate this before mutating. Empty dict = not reversible or read-only.
    rollback_data: dict = Field(default_factory=dict)


class Receipt(BaseModel):
    """
    Permanent, signed record of everything that happened in a run.

    Written to disk as a JSON file (receipts/<run_id>.json) after every run,
    whether PASS or BLOCK. The signature field covers the immutable identity
    fields (run_id, workflow, actor, decision, timestamp) so any tampering
    is detectable. The payload and policy_results are stored for human
    inspection but are NOT part of the signature (they can be large, and the
    decision is the tamper-sensitive field).

    Fields:
        run_id          — UUID, auto-generated; used as the receipt filename
        workflow        — name of the workflow that was called
        user_email     — who triggered this run
        payload         — copy of the input payload for audit purposes
        policy_results  — full list of every policy result (pass and fail)
        decision        — "PASS" if all policies passed, "BLOCK" if any failed
        actions_taken   — list of actions the workflow executed; empty if BLOCK
        timestamp       — ISO8601 UTC timestamp, set at receipt creation time
        signature       — HMAC-SHA256 hex digest, set by sign_receipt()
    """
    # Auto-generated UUID so each receipt has a unique, stable filename.
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow: str
    user_email: str
    payload: dict
    policy_results: list[PolicyResult]
    # "PASS" = all policies passed and workflow ran
    # "BLOCK" = at least one policy failed
    # "PARTIAL" = rollback ran but some actions could not be reversed (irreversible)
    decision: Literal["PASS", "BLOCK", "PARTIAL"]
    # Empty list (not None) when BLOCK — makes serialisation consistent.
    actions_taken: list[ActionResult] = Field(default_factory=list)
    # Set by receipt.build_receipt() at construction time — always UTC.
    timestamp: str
    # Set by receipt.sign_receipt() — empty string until signing.
    signature: str


class RunResult(BaseModel):
    """
    What the calling agent gets back from EnactClient.run().

    Intentionally lightweight — the full audit detail is in the Receipt.
    The agent only needs to know: did it work, what workflow ran, and what
    did the successful actions produce?

    Fields:
        success   — True only if all policies passed AND the workflow ran
        workflow  — echoes back the workflow name for easy logging
        output    — dict of {action_name: action_output} for all successful actions
    """
    success: bool
    workflow: str
    # Only populated on PASS. Keys are action names; values are connector outputs.
    output: dict = Field(default_factory=dict)
