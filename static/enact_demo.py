"""
ENACT DEMO — Browser mock matching the real enact-sdk API surface.

API is intentionally identical to the real SDK so demo code copy-pastes
into production. The only difference: connectors are mocked (no real API
calls), receipts are in-memory (not written to disk), and HMAC signing
is skipped (signature field is a placeholder).

Real SDK usage (production):
    pip install enact-sdk
    from enact import EnactClient
    from enact.policies.db import dont_delete_without_where
"""

from dataclasses import dataclass, field
from typing import Optional, List
import uuid
from datetime import datetime


# ── MODELS ────────────────────────────────────────────────────────────────────
# Field names match enact.models exactly.

@dataclass
class PolicyResult:
    """Outcome of a single policy check."""
    policy: str       # machine-readable policy name
    passed: bool      # True = allow, False = block
    reason: str       # human-readable explanation


@dataclass
class ActionResult:
    """Outcome of a single action taken by the workflow."""
    action: str
    system: str
    success: bool
    output: dict = field(default_factory=dict)
    rollback_data: dict = field(default_factory=dict)


@dataclass
class Receipt:
    """Permanent record of everything that happened in a run."""
    run_id: str
    workflow: str
    user_email: str
    decision: str          # "PASS" or "BLOCK"
    policy_results: List[PolicyResult]
    actions: List[ActionResult]
    timestamp: str
    signature: str = "demo-hmac-skipped"

    @property
    def passed(self) -> bool:
        return self.decision == "PASS"

    def to_dict(self):
        return {
            "run_id": self.run_id,
            "workflow": self.workflow,
            "user_email": self.user_email,
            "decision": self.decision,
            "passed": self.passed,
            "policy_results": [
                {"policy": p.policy, "passed": p.passed, "reason": p.reason}
                for p in self.policy_results
            ],
            "actions": [
                {"action": a.action, "system": a.system, "success": a.success}
                for a in self.actions
            ],
            "timestamp": self.timestamp,
            "signature": self.signature,
        }


@dataclass
class RunResult:
    """Lightweight summary returned alongside the full Receipt."""
    passed: bool
    decision: str
    run_id: str


# ── INTERNAL CONTEXT ──────────────────────────────────────────────────────────
# WorkflowContext is built by EnactClient.run() — you never construct it directly.
# It's the same class as enact.models.WorkflowContext in the real SDK.

@dataclass
class WorkflowContext:
    """Built internally by EnactClient.run(). Passed to every policy and workflow."""
    workflow: str
    user_email: str
    payload: dict
    systems: dict = field(default_factory=dict)
    user_attributes: dict = field(default_factory=dict)


# ── POLICIES ──────────────────────────────────────────────────────────────────
# These match the real policy signatures: (WorkflowContext) -> PolicyResult.
# Real equivalents: enact.policies.db, enact.policies.git, enact.policies.email

def dont_delete_without_where(ctx: WorkflowContext) -> PolicyResult:
    """
    Block DELETE statements that lack a WHERE clause.

    The Replit incident (Jan 2025): an AI ran 'DELETE FROM sessions'
    (no WHERE), wiping the sessions table and taking down auth for 3 hours.
    Real equivalent: enact.policies.db.dont_delete_without_where
    """
    sql = ctx.payload.get("action", "")
    sql_upper = sql.strip().upper()

    if sql_upper.startswith("DELETE") and "WHERE" not in sql_upper:
        short = sql[:60] + ("…" if len(sql) > 60 else "")
        return PolicyResult(
            policy="dont_delete_without_where",
            passed=False,
            reason=f"DELETE has no WHERE clause — would wipe the whole table. SQL: '{short}'",
        )

    return PolicyResult(
        policy="dont_delete_without_where",
        passed=True,
        reason="DELETE has a WHERE clause — scoped deletion approved.",
    )


def dont_push_to_main(ctx: WorkflowContext) -> PolicyResult:
    """
    Block direct pushes to main/master.

    The Amazon Kiro incident (Dec 2025): an agent pushed to main,
    triggering a broken deploy that caused a 13-hour AWS outage.
    Real equivalent: enact.policies.git.dont_push_to_main
    """
    branch = ctx.payload.get("branch", "")
    if branch.lower() in ("main", "master"):
        return PolicyResult(
            policy="dont_push_to_main",
            passed=False,
            reason=f"Cannot push directly to '{branch}'. Use a feature branch and open a PR.",
        )
    return PolicyResult(
        policy="dont_push_to_main",
        passed=True,
        reason=f"Branch '{branch}' is safe for direct push.",
    )


def no_mass_emails(ctx: WorkflowContext) -> PolicyResult:
    """
    Block emails to more than 50 recipients at once.
    Real equivalent: enact.policies.email.no_mass_emails
    """
    recipients = ctx.payload.get("recipients", [])
    limit = 50
    if len(recipients) > limit:
        return PolicyResult(
            policy="no_mass_emails",
            passed=False,
            reason=f"Email has {len(recipients)} recipients — exceeds limit of {limit}.",
        )
    return PolicyResult(
        policy="no_mass_emails",
        passed=True,
        reason=f"Email to {len(recipients)} recipients is within the {limit}-recipient limit.",
    )


# ── MOCK CONNECTORS ───────────────────────────────────────────────────────────

# Fake customer records — "deleted" by the cleanup job.
_CUSTOMER_ROWS = [
    {"id": 42, "name": "Acme Corp",   "email": "ops@acme.com",      "arr_usd": 48_000},
    {"id": 43, "name": "Globex Inc",  "email": "cfo@globex.com",     "arr_usd": 24_000},
    {"id": 44, "name": "Initech LLC", "email": "it@initech.com",     "arr_usd": 36_000},
]


class _MockDB:
    def execute(self, sql: str) -> ActionResult:
        sql_upper = sql.strip().upper()
        short = sql[:70] + ("…" if len(sql) > 70 else "")

        if sql_upper.startswith("DELETE"):
            # Capture what we're about to delete — stored in rollback_data
            print(f"  [postgres] DELETE {short}")
            return ActionResult(
                action="db_delete",
                system="postgres",
                success=True,
                output={"rows_affected": len(_CUSTOMER_ROWS), "sql": short},
                rollback_data={"deleted_rows": _CUSTOMER_ROWS},
            )

        print(f"  [postgres] {short}")
        return ActionResult(action="db_execute", system="postgres", success=True,
                            output={"rows_affected": 1})

class _MockGitHub:
    def __init__(self): self._branches = {}
    def create_branch(self, repo, branch, source="main") -> ActionResult:
        self._branches[f"{repo}:{branch}"] = source
        print(f"  [GitHub] Created branch '{branch}' in {repo}")
        return ActionResult(action="create_branch", system="github", success=True,
                            output={"branch": branch, "repo": repo},
                            rollback_data={"branch": branch, "repo": repo})
    def delete_branch(self, repo, branch) -> ActionResult:
        self._branches.pop(f"{repo}:{branch}", None)
        print(f"  [GitHub] Deleted branch '{branch}' from {repo}")
        return ActionResult(action="delete_branch", system="github", success=True,
                            output={"branch": branch})


# ── ENACT CLIENT ──────────────────────────────────────────────────────────────

class EnactClient:
    """
    Action firewall client — matches the real enact.EnactClient API.

    Differences from production:
      - secret validation is skipped (no HMAC signing)
      - connectors are mocked (no real API calls)
      - receipts are in-memory (not written to disk)
    """

    def __init__(
        self,
        policies: Optional[list] = None,
        systems: Optional[dict] = None,
        workflows: Optional[list] = None,
        secret: Optional[str] = None,
        allow_insecure_secret: bool = False,
        **_kwargs,   # absorb cloud_api_key, receipt_dir, etc. for API compat
    ):
        self._policies = policies or []
        self._db = _MockDB()
        self._github = _MockGitHub()
        self._receipts = {}
        # Real SDK raises ValueError here if secret is missing. Demo lets it slide.

    def run(
        self,
        workflow: str,
        user_email: str,
        payload: dict,
    ) -> tuple:
        """
        Execute the full Enact loop.

        Returns:
            (RunResult, Receipt) — same tuple as real SDK.
        """
        ctx = WorkflowContext(workflow=workflow, user_email=user_email, payload=payload)
        run_id = str(uuid.uuid4())[:8]

        # ── Policies ──
        policy_results: List[PolicyResult] = []
        for fn in self._policies:
            r = fn(ctx)
            policy_results.append(r)

        all_passed = all(r.passed for r in policy_results)
        decision = "PASS" if all_passed else "BLOCK"

        # ── Execute if approved ──
        actions: List[ActionResult] = []
        if all_passed:
            action = self._dispatch(ctx)
            if action:
                actions.append(action)

        receipt = Receipt(
            run_id=run_id,
            workflow=workflow,
            user_email=user_email,
            decision=decision,
            policy_results=policy_results,
            actions=actions,
            timestamp=datetime.now().isoformat(),
        )
        self._receipts[run_id] = receipt

        # Compact trace — one line per policy, then blank line before user's print() output
        d_icon = "✓" if all_passed else "✗"
        print(f"▶ enact.run({workflow})  →  {d_icon} {decision}  [receipt: {run_id}]")
        for r in policy_results:
            p = "✓" if r.passed else "✗"
            print(f"  {p} [{r.policy}] {r.reason}")
        if actions:
            for a in actions:
                print(f"  → {a.action} on {a.system}")
        print()

        run_result = RunResult(passed=all_passed, decision=decision, run_id=run_id)
        return run_result, receipt

    def _dispatch(self, ctx: WorkflowContext) -> Optional[ActionResult]:
        """Route to the right mock connector based on payload shape."""
        if "branch" in ctx.payload and "repo" in ctx.payload:
            # PR / git workflow
            return self._github.create_branch(
                ctx.payload["repo"],
                ctx.payload["branch"],
            )
        if "action" in ctx.payload:
            # DB workflow — payload["action"] is a SQL string
            return self._db.execute(ctx.payload["action"])
        return None

    def rollback(self, receipt: Receipt) -> Optional["Receipt"]:
        """Reverse all actions from a previous Receipt."""
        if not receipt.passed:
            print(f"✗ Run '{receipt.run_id}' was blocked — nothing to roll back")
            return None

        print(f"\n◀ enact.rollback({receipt.run_id})")
        rollback_actions = []
        for action in reversed(receipt.actions):
            if action.action == "create_branch":
                d = action.rollback_data
                ra = self._github.delete_branch(d["repo"], d["branch"])
                rollback_actions.append(ra)
            elif action.action == "db_delete":
                deleted_rows = action.rollback_data.get("deleted_rows", [])
                print(f"  [postgres] Restoring {len(deleted_rows)} rows...")
                for row in deleted_rows:
                    print(f"    ✓ {row['name']} ({row['email']}) — ${row['arr_usd']:,} ARR")
                rollback_actions.append(ActionResult(
                    action="db_restore",
                    system="postgres",
                    success=True,
                    output={"rows_restored": len(deleted_rows)},
                ))
            else:
                print(f"  [{action.system}] No automatic rollback for '{action.action}'")

        rb = Receipt(
            run_id=str(uuid.uuid4())[:8],
            workflow=f"rollback:{receipt.run_id}",
            user_email=receipt.user_email,
            decision="PASS",
            policy_results=[PolicyResult(
                policy="manual_rollback", passed=True, reason="Rollback authorized by user",
            )],
            actions=rollback_actions,
            timestamp=datetime.now().isoformat(),
        )
        self._receipts[rb.run_id] = rb
        print(f"  Rollback receipt: {rb.run_id}")
        return rb


# ── BOOT MESSAGE ──────────────────────────────────────────────────────────────

print("Enact demo loaded. Available: EnactClient, PolicyResult, Receipt")
print("Policies: dont_delete_without_where, dont_push_to_main, no_mass_emails")
print("─" * 60)
