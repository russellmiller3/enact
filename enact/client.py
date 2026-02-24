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
The HMAC signing key. Defaults to "enact-default-secret" for local development.
Set the ENACT_SECRET environment variable in production to prevent receipt forgery.
All receipts written to disk by a given deployment should use the same secret so
verify_signature() can validate them consistently.
"""
import os
from enact.models import WorkflowContext, RunResult, Receipt
from enact.policy import evaluate_all, all_passed
from enact.receipt import build_receipt, sign_receipt, write_receipt


class EnactClient:
    """
    The Enact action firewall client.

    Instantiate once with your systems, policies, and workflows. Then call
    run() for each agent action. Every call produces a signed receipt.

    Example:
        enact = EnactClient(
            systems={"github": GitHubConnector(token=os.environ["GITHUB_TOKEN"])},
            policies=[no_push_to_main, require_branch_prefix("agent/")],
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
    ):
        """
        Initialise the client.

        Args:
            systems     — connector instances keyed by name, e.g. {"github": GitHubConnector(...)}.
                          Passed into WorkflowContext so policies and workflows can call them.
            policies    — list of policy callables, each (WorkflowContext) -> PolicyResult.
                          May include factory-produced closures (e.g. max_files_per_commit(10)).
                          All policies run on every call to run() — order matters only for receipt readability.
            workflows   — list of workflow functions, each (WorkflowContext) -> list[ActionResult].
                          Stored as {function.__name__: function} so they can be looked up by name string.
            secret      — HMAC key for receipt signing. Falls back to ENACT_SECRET env var,
                          then to "enact-default-secret". Override in production.
            receipt_dir — directory to write signed receipt JSON files. Created on first run if absent.
        """
        self._systems = systems or {}
        self._policies = policies or []
        # Index by function name so run(workflow="foo") can find the function without
        # requiring the caller to import it directly.
        self._workflows = {wf.__name__: wf for wf in (workflows or [])}
        self._secret = secret or os.environ.get("ENACT_SECRET", "enact-default-secret")
        self._receipt_dir = receipt_dir

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
