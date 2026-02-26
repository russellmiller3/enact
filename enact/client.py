"""
EnactClient — the main entry point for Enact.

This is the single object your agent interacts with. It owns:
  - the set of allowed connectors (systems)
  - the registered policy functions
  - the registered workflow functions
  - the HMAC signing secret
  - the receipt output directory

Calling run() triggers the full Enact loop:
    build context → run all policies → PASS or BLOCK → execute workflow → sign receipt → return

Why workflows are stored as {name: fn}
---------------------------------------
Callers invoke workflows by name string: enact.run(workflow="agent_pr_workflow", ...).
This allows an agent to decide at runtime which workflow to call without needing
to import the function directly. The dict is built at init time from the function's
__name__ attribute, so the name used in run() must match the function name exactly.

ENACT_SECRET
------------
The HMAC signing key. Required — pass secret= or set the ENACT_SECRET env var.
There is no default; receipts are only trustworthy if the secret is private.
All receipts written to disk by a given deployment should use the same secret so
verify_signature() can validate them consistently. For development/testing, pass
allow_insecure_secret=True to skip the 32-character minimum length check.
"""
import os
from enact.models import WorkflowContext, RunResult, Receipt
from enact.policy import evaluate_all, all_passed
from enact.receipt import build_receipt, sign_receipt, verify_signature, write_receipt, load_receipt
from enact.rollback import execute_rollback_action


class EnactClient:
    """
    The Enact action firewall client.

    Instantiate once with your systems, policies, and workflows. Then call
    run() for each agent action. Every call produces a signed receipt.

    Example:
        enact = EnactClient(
            systems={"github": GitHubConnector(token=os.environ["GITHUB_TOKEN"])},
            policies=[dont_push_to_main, require_branch_prefix("agent/")],
            workflows=[agent_pr_workflow],
        )
        result, receipt = enact.run(
            workflow="agent_pr_workflow",
            actor_email="agent@company.com",
            payload={"repo": "owner/repo", "branch": "agent/my-feature"},
        )
    """

    def __init__(
        self,
        systems: dict | None = None,
        policies: list | None = None,
        workflows: list | None = None,
        secret: str | None = None,
        receipt_dir: str = "receipts",
        rollback_enabled: bool = False,
        allow_insecure_secret: bool = False,
    ):
        """
        Initialise the client.

        Args:
            systems              — connector instances keyed by name, e.g. {"github": GitHubConnector(...)}.
                                   Passed into WorkflowContext so policies and workflows can call them.
            policies             — list of policy callables, each (WorkflowContext) -> PolicyResult.
                                   May include factory-produced closures (e.g. max_files_per_commit(10)).
                                   All policies run on every call to run() — order matters only for receipt readability.
            workflows            — list of workflow functions, each (WorkflowContext) -> list[ActionResult].
                                   Stored as {function.__name__: function} so they can be looked up by name string.
            secret               — HMAC key for receipt signing. Falls back to ENACT_SECRET env var.
                                   Required — receipts are unforgeable only if the secret is kept private.
            receipt_dir          — directory to write signed receipt JSON files. Created on first run if absent.
            rollback_enabled     — premium feature flag. Set True to enable client.rollback(run_id).
            allow_insecure_secret — skip secret strength validation. For development/testing ONLY.
                                    Never use in production — short secrets enable receipt forgery.
        """
        self._systems = systems or {}
        self._policies = policies or []
        # Index by function name so run(workflow="foo") can find the function without
        # requiring the caller to import it directly.
        self._workflows = {wf.__name__: wf for wf in (workflows or [])}

        # --- Secret validation (Risk #2: no more insecure default) ---
        self._secret = secret or os.environ.get("ENACT_SECRET")
        if not self._secret:
            raise ValueError(
                "No signing secret provided. Pass secret= to EnactClient or set the "
                "ENACT_SECRET environment variable. Receipts cannot be trusted without a secret."
            )
        if not allow_insecure_secret and len(self._secret) < 32:
            raise ValueError(
                f"Secret must be at least 32 characters (got {len(self._secret)}). "
                "Use a strong, random secret in production. "
                "Pass allow_insecure_secret=True for development/testing only."
            )

        self._receipt_dir = receipt_dir
        self._rollback_enabled = rollback_enabled

    def run(
        self,
        workflow: str,
        actor_email: str,
        payload: dict,
    ) -> tuple[RunResult, Receipt]:
        """
        Execute the full Enact loop for one agent action.

        Steps:
            1. Resolve the workflow function by name (raises ValueError if not registered)
            2. Build a WorkflowContext from the args + registered systems
            3. Run ALL registered policies (never bails early — see policy.py for why)
            4. If any policy failed → BLOCK: build + sign + write receipt, return failure
            5. If all passed → PASS: execute the workflow function
            6. Build + sign + write the PASS receipt (includes actions_taken)
            7. Return (RunResult, Receipt) to the caller

        A signed receipt is always written to disk, for both PASS and BLOCK.
        The caller receives the RunResult for immediate use and the Receipt
        for logging/display.

        Args:
            workflow     — name of a registered workflow function (must match __name__ exactly)
            actor_email  — identity of the agent making the request; stored in every receipt
            payload      — arbitrary dict of inputs the workflow needs (repo, email, table, etc.)

        Returns:
            tuple[RunResult, Receipt] — RunResult.success is False on BLOCK or unknown workflow

        Raises:
            ValueError — if the workflow name is not registered
        """
        # 1. Resolve workflow function — fail loudly if not registered (not silently passing)
        if workflow not in self._workflows:
            raise ValueError(
                f"Unknown workflow: {workflow}. Registered: {list(self._workflows.keys())}"
            )
        workflow_fn = self._workflows[workflow]

        # 2. Build context — single shared object passed to policies AND the workflow
        context = WorkflowContext(
            workflow=workflow,
            actor_email=actor_email,
            payload=payload,
            systems=self._systems,
        )

        # 3. Run all policies — evaluate_all() never short-circuits
        policy_results = evaluate_all(context, self._policies)

        # 4. BLOCK path — at least one policy failed
        if not all_passed(policy_results):
            receipt = build_receipt(
                workflow=workflow,
                actor_email=actor_email,
                payload=payload,
                policy_results=policy_results,
                decision="BLOCK",
                # actions_taken is intentionally empty — nothing ran
            )
            receipt = sign_receipt(receipt, self._secret)
            write_receipt(receipt, self._receipt_dir)
            return RunResult(success=False, workflow=workflow), receipt

        # 5. PASS path — all policies passed, execute the workflow
        actions_taken = workflow_fn(context)

        # 6. Build + sign receipt including what the workflow actually did
        receipt = build_receipt(
            workflow=workflow,
            actor_email=actor_email,
            payload=payload,
            policy_results=policy_results,
            decision="PASS",
            actions_taken=actions_taken,
        )
        receipt = sign_receipt(receipt, self._secret)
        write_receipt(receipt, self._receipt_dir)

        # 7. Collapse successful action outputs into a flat dict for easy agent consumption.
        # Failed actions are in the receipt but excluded from RunResult.output.
        output = {a.action: a.output for a in actions_taken if a.success}
        return RunResult(success=True, workflow=workflow, output=output), receipt

    def rollback(self, run_id: str) -> tuple[RunResult, Receipt]:
        """
        Reverse all successful actions from a previous run, in reverse order.

        Loads the receipt for run_id, filters to actions that were actually
        executed (success=True AND not already_done), then calls the inverse
        operation for each via execute_rollback_action(). Produces a new
        signed receipt referencing the original run.

        PREMIUM FEATURE: requires rollback_enabled=True at init time.

        Args:
            run_id — the UUID from the original run's Receipt.run_id

        Returns:
            tuple[RunResult, Receipt] — RunResult.success=False if any rollback
            step failed (best-effort: all steps are attempted regardless)

        Raises:
            PermissionError   — if rollback_enabled=False
            FileNotFoundError — if no receipt exists for run_id
            ValueError        — if the original run was a BLOCK (nothing to undo)
        """
        if not self._rollback_enabled:
            raise PermissionError(
                "Rollback is a premium feature. Set rollback_enabled=True on EnactClient to use it."
            )

        original_receipt = load_receipt(run_id, self._receipt_dir)

        # Verify signature BEFORE executing any rollback operations.
        # Prevents TOCTOU attacks where an attacker modifies the receipt on disk
        # between load and execution — tampered receipts are rejected immediately.
        if not verify_signature(original_receipt, self._secret):
            raise ValueError(
                f"Receipt signature verification failed for run_id: {run_id}. "
                "The receipt may have been tampered with."
            )

        if original_receipt.decision == "BLOCK":
            raise ValueError("Cannot rollback a blocked run — no actions were taken")

        # Filter to actions that were actually executed: success=True AND not a noop
        reversible = [
            a for a in reversed(original_receipt.actions_taken)
            if a.success and not a.output.get("already_done")
        ]

        # Best-effort: execute all rollbacks, collect results
        rollback_results = []
        for action in reversible:
            result = execute_rollback_action(action, self._systems)
            rollback_results.append(result)

        # Determine overall outcome BEFORE building the receipt — decision depends on it
        all_success = all(r.success for r in rollback_results) if rollback_results else True

        # Build + sign + write rollback receipt
        receipt = build_receipt(
            workflow=f"rollback:{original_receipt.workflow}",
            actor_email=original_receipt.actor_email,
            payload={"original_run_id": run_id, "rollback": True},
            policy_results=[],
            decision="PASS" if all_success else "PARTIAL",
            actions_taken=rollback_results,
        )
        receipt = sign_receipt(receipt, self._secret)
        write_receipt(receipt, self._receipt_dir)
        output = {r.action: r.output for r in rollback_results if r.success}
        return (
            RunResult(
                success=all_success,
                workflow=f"rollback:{original_receipt.workflow}",
                output=output,
            ),
            receipt,
        )
