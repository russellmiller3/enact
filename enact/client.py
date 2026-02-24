"""
EnactClient — the main entry point. Orchestrates the full run() loop:
build context → run policies → execute workflow → sign receipt → return result.
"""
import os
from enact.models import WorkflowContext, RunResult, Receipt
from enact.policy import evaluate_all, all_passed
from enact.receipt import build_receipt, sign_receipt, write_receipt


class EnactClient:
    def __init__(
        self,
        systems: dict | None = None,
        policies: list | None = None,
        workflows: list | None = None,
        secret: str | None = None,
        receipt_dir: str = "receipts",
    ):
        self._systems = systems or {}
        self._policies = policies or []
        self._workflows = {wf.__name__: wf for wf in (workflows or [])}
        self._secret = secret or os.environ.get("ENACT_SECRET", "enact-default-secret")
        self._receipt_dir = receipt_dir

    def run(
        self,
        workflow: str,
        actor_email: str,
        payload: dict,
    ) -> tuple[RunResult, Receipt]:
        # 1. Resolve workflow function
        if workflow not in self._workflows:
            raise ValueError(
                f"Unknown workflow: {workflow}. Registered: {list(self._workflows.keys())}"
            )
        workflow_fn = self._workflows[workflow]

        # 2. Build context
        context = WorkflowContext(
            workflow=workflow,
            actor_email=actor_email,
            payload=payload,
            systems=self._systems,
        )

        # 3. Run all policies
        policy_results = evaluate_all(context, self._policies)

        # 4. Check decision
        if not all_passed(policy_results):
            # BLOCK — no actions taken
            receipt = build_receipt(
                workflow=workflow,
                actor_email=actor_email,
                payload=payload,
                policy_results=policy_results,
                decision="BLOCK",
            )
            receipt = sign_receipt(receipt, self._secret)
            write_receipt(receipt, self._receipt_dir)
            return RunResult(success=False, workflow=workflow), receipt

        # 5. PASS — execute workflow
        actions_taken = workflow_fn(context)

        # 6. Build + sign receipt
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

        # 7. Build output from action results
        output = {a.action: a.output for a in actions_taken if a.success}
        return RunResult(success=True, workflow=workflow, output=output), receipt
