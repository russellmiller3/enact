"""
Enact quickstart — policy, receipt, and rollback in ~100 lines.

THE SCENARIO:
An AI agent wants to create a git branch in a GitHub repo.
Rule: never push directly to "main" or "master" — changes go through PRs.

This is the Amazon Kiro incident (Dec 2025): an agent pushed directly to main
and caused a 13-hour AWS outage. With Enact, that push is blocked before it
fires. And if something *does* slip through, rollback undoes it in one call.

THREE CONCEPTS, IN ORDER:

  1. BLOCK  — policy runs BEFORE any action. Bad branch? Blocked instantly.
  2. PASS   — safe branch passes the policy, workflow runs, receipt is signed.
  3. ROLLBACK — one call reverses every action from a PASS run using the receipt.

HOW IT WORKS:

  Agent calls enact.run(payload={"branch": "main"})
                      │
                      ▼
  ┌──────────────────────────────────┐
  │  POLICY (runs first, every time) │
  │  dont_push_to_main checks branch │
  │  "main"? → BLOCK (receipt saved) │
  │  other?  → PASS  (continue)      │
  └──────────────────────────────────┘
                      │ PASS
                      ▼
  ┌──────────────────────────────────┐
  │  WORKFLOW                        │
  │  create_branch runs              │
  │  ActionResult captured           │
  │  with rollback_data stored       │
  └──────────────────────────────────┘
                      │
                      ▼
  ┌──────────────────────────────────┐
  │  RECEIPT (signed JSON to disk)   │
  │  run_id, decision, actions,      │
  │  policy results, HMAC signature  │
  └──────────────────────────────────┘
                      │ if needed
                      ▼
  ┌──────────────────────────────────┐
  │  ROLLBACK                        │
  │  enact.rollback(receipt.run_id)  │
  │  reads receipt, reverses actions │
  │  in reverse order, new receipt   │
  └──────────────────────────────────┘

WHERE DOES THE LLM COME IN?
In production, the LLM (Claude, GPT, etc.) calls enact.run() — not you.
The LLM decides what to do. Enact decides whether it's allowed.

    LLM: "I want to push to main"
    Enact: "No. Policy blocked it."
    LLM: "Okay, feature branch instead."
    Enact: "Approved. Receipt signed."
    Later: "Oops, that branch was wrong."
    Enact: "enact.rollback(run_id) — branch deleted. New receipt signed."

This example skips the LLM to keep things simple.
See examples/demo.py for a full 3-act scenario with DB rollback.

Usage:
    python examples/quickstart.py
"""
from enact import EnactClient
from enact.models import WorkflowContext, ActionResult
from enact.policies.git import dont_push_to_main


# ── A minimal fake connector (just enough to run) ──────────────────────────────

class FakeGitHub:
    """Pretends to create branches. No real API calls."""

    def __init__(self):
        # in-memory "repo -> set(branches)" so we can show rollback actually undoing
        self.branches: dict[str, set[str]] = {}

    def _ensure_repo(self, repo: str):
        if repo not in self.branches:
            self.branches[repo] = set()
    
    def create_branch(self, repo: str, branch: str) -> ActionResult:
        self._ensure_repo(repo)

        branch_already_exists = branch in self.branches[repo]
        if branch_already_exists:
            return ActionResult(
                action="create_branch",
                system="github",
                success=True,
                output={"repo": repo, "branch": branch, "already_done": "created"},
                rollback_data={},
            )

        self.branches[repo].add(branch)
        return ActionResult(
            action="create_branch",
            system="github",
            success=True,
            output={"repo": repo, "branch": branch, "already_done": False},
            rollback_data={"repo": repo, "branch": branch},
        )

    def delete_branch(self, repo: str, branch: str) -> ActionResult:
        self._ensure_repo(repo)

        branch_exists = branch in self.branches[repo]
        if not branch_exists:
            return ActionResult(
                action="delete_branch",
                system="github",
                success=True,
                output={"repo": repo, "branch": branch, "already_done": "deleted"},
                rollback_data={},
            )

        self.branches[repo].remove(branch)
        return ActionResult(
            action="delete_branch",
            system="github",
            success=True,
            output={"repo": repo, "branch": branch, "already_done": False},
        )


# ── A minimal workflow ─────────────────────────────────────────────────────────

def create_branch_workflow(context: WorkflowContext) -> list[ActionResult]:
    """Create a branch. That's it."""
    gh = context.systems["github"]
    repo = context.payload["repo"]
    branch = context.payload["branch"]
    return [gh.create_branch(repo=repo, branch=branch)]


# ── The Demo ───────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 50)
    print("  ENACT QUICKSTART — Minimal Example")
    print("=" * 50 + "\n")

    fake_github = FakeGitHub()

    # Set up Enact with ONE policy
    enact = EnactClient(
        systems={"github": fake_github},
        policies=[dont_push_to_main],  # ← The policy: don't push a branch to main.
        workflows=[create_branch_workflow],
        rollback_enabled=True,
        receipt_dir="receipts",
        secret="demo-secret",
        allow_insecure_secret=True,
    )

    # 1) Try to push to main (should be BLOCKED)
    print("1) Attempting to create branch 'main' (should BLOCK)...\n")

    blocked_result, blocked_receipt = enact.run(
        workflow="create_branch_workflow",
        user_email="agent@company.com",
        payload={"repo": "company/api", "branch": "main"},
    )

    print(f"  Decision: {blocked_receipt.decision}")
    print(f"  Success:  {blocked_result.success}")
    for pr in blocked_receipt.policy_results:
        status = "PASS" if pr.passed else "FAIL"
        print(f"  [{status}] {pr.policy}: {pr.reason}")

    print(f"  Run ID:   {blocked_receipt.run_id}")

    # 2) Create a safe branch (should PASS)
    print("\n2) Attempting to create branch 'feature/quickstart' (should PASS)...\n")

    pass_result, pass_receipt = enact.run(
        workflow="create_branch_workflow",
        user_email="agent@company.com",
        payload={"repo": "company/api", "branch": "feature/quickstart"},
    )

    print(f"  Decision: {pass_receipt.decision}")
    print(f"  Success:  {pass_result.success}")
    print(f"  Run ID:   {pass_receipt.run_id}")
    print(f"  Branches now: {sorted(fake_github.branches['company/api'])}")

    # 3) Roll back the PASS run by receipt.run_id
    print("\n3) Rolling back the PASS run using receipt.run_id...\n")
    rollback_result, rollback_receipt = enact.rollback(pass_receipt.run_id)

    print(f"  Rollback Decision: {rollback_receipt.decision}")
    print(f"  Rollback Success:  {rollback_result.success}")
    print(f"  Rollback Run ID:   {rollback_receipt.run_id}")
    print(f"  Branches now: {sorted(fake_github.branches['company/api'])}")

    print("\n" + "=" * 50)
    print("  BLOCKED unsafe run. PASSED safe run. Then rolled it back.")
    print("  This is policy + receipt + rollback in one file.")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
