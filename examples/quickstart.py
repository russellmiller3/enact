"""
Enact quickstart — BLOCK, PASS, and ROLLBACK in 60 seconds.

This shows the three core scenarios that matter for AI agents:
1. BLOCK — Agent tries something dangerous, policy stops it
2. PASS — Agent does normal work, receipt proves what happened
3. ROLLBACK — Something went wrong, undo it with one call

No credentials needed. Uses in-memory demo connectors.

Usage:
    git clone https://github.com/russellmiller3/enact
    cd enact
    pip install enact-sdk
    python examples/quickstart.py
"""
import sys

# Windows CP1252 can't encode box-drawing chars — switch to UTF-8 early
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from enact import EnactClient
from enact.models import WorkflowContext, PolicyResult, ActionResult
from enact.policies.git import dont_push_to_main


# ── Demo connector (in-memory, no real API calls) ──────────────────────────────

class DemoGitHubConnector:
    """In-memory GitHub — same interface as real GitHubConnector."""

    def __init__(self):
        self._branches: dict[str, set] = {}
        self._prs: dict[str, dict] = {}
        self._pr_counter = 100

    def create_branch(self, repo: str, branch: str, base: str = "main") -> ActionResult:
        self._branches.setdefault(repo, set())
        already = branch in self._branches[repo]
        if not already:
            self._branches[repo].add(branch)
        return ActionResult(
            action="create_branch",
            system="github",
            success=True,
            output={"branch": branch, "repo": repo, "already_done": already},
            rollback_data={"repo": repo, "branch": branch},
        )

    def create_pr(self, repo: str, title: str, body: str, head: str, base: str = "main") -> ActionResult:
        self._pr_counter += 1
        pr_num = self._pr_counter
        self._prs.setdefault(repo, {})[pr_num] = {"title": title, "head": head, "state": "open"}
        return ActionResult(
            action="create_pr",
            system="github",
            success=True,
            output={"pr_number": pr_num, "url": f"https://github.com/{repo}/pull/{pr_num}"},
            rollback_data={"repo": repo, "pr_number": pr_num},
        )

    def delete_branch(self, repo: str, branch: str) -> ActionResult:
        self._branches.get(repo, set()).discard(branch)
        return ActionResult(
            action="delete_branch",
            system="github",
            success=True,
            output={"branch": branch, "repo": repo},
        )

    def close_pr(self, repo: str, pr_number: int) -> ActionResult:
        pr = self._prs.get(repo, {}).get(pr_number)
        if pr:
            pr["state"] = "closed"
        return ActionResult(
            action="close_pr",
            system="github",
            success=True,
            output={"pr_number": pr_number},
        )


class DemoPostgresConnector:
    """In-memory Postgres — same interface as real PostgresConnector."""

    def __init__(self):
        self._tables: dict[str, list[dict]] = {"customers": [
            {"id": 1, "email": "alice@example.com", "status": "active"},
            {"id": 2, "email": "bob@example.com", "status": "inactive"},
            {"id": 3, "email": "carol@example.com", "status": "inactive"},
        ]}
        self._id_counter = 3

    def select_rows(self, table: str, where: dict | None = None) -> ActionResult:
        rows = self._tables.get(table, [])
        if where:
            rows = [r for r in rows if all(r.get(k) == v for k, v in where.items())]
        return ActionResult(
            action="select_rows",
            system="postgres",
            success=True,
            output={"rows": rows, "row_count": len(rows)},
        )

    def insert_row(self, table: str, data: dict) -> ActionResult:
        self._id_counter += 1
        row = {"id": self._id_counter, **data}
        self._tables.setdefault(table, []).append(row)
        return ActionResult(
            action="insert_row",
            system="postgres",
            success=True,
            output={"inserted_id": self._id_counter},
            rollback_data={"table": table, "id": self._id_counter},
        )

    def delete_row(self, table: str, where: dict) -> ActionResult:
        rows = self._tables.get(table, [])
        before = len(rows)
        deleted = [r for r in rows if all(r.get(k) == v for k, v in where.items())]
        self._tables[table] = [r for r in rows if not all(r.get(k) == v for k, v in where.items())]
        return ActionResult(
            action="delete_row",
            system="postgres",
            success=True,
            output={"rows_deleted": before - len(self._tables[table])},
            rollback_data={"table": table, "deleted_rows": deleted},
        )

    def insert_rows(self, table: str, rows: list[dict]) -> ActionResult:
        for row in rows:
            self._id_counter += 1
            self._tables.setdefault(table, []).append({"id": self._id_counter, **row})
        return ActionResult(
            action="insert_rows",
            system="postgres",
            success=True,
            output={"rows_inserted": len(rows)},
        )


# ── Workflows ──────────────────────────────────────────────────────────────────

def direct_push_workflow(context: WorkflowContext) -> list[ActionResult]:
    """Simulates an agent pushing directly to a branch (dangerous on main!)."""
    gh = context.systems["github"]
    repo = context.payload["repo"]
    branch = context.payload["branch"]
    return [gh.create_branch(repo=repo, branch=branch)]


def agent_pr_workflow(context: WorkflowContext) -> list[ActionResult]:
    """Normal agent workflow: create branch → open PR."""
    gh = context.systems["github"]
    repo = context.payload["repo"]
    branch = context.payload["branch"]
    
    result1 = gh.create_branch(repo=repo, branch=branch)
    result2 = gh.create_pr(
        repo=repo,
        title=f"Agent: {branch}",
        body="Automated PR from Enact agent",
        head=branch,
    )
    return [result1, result2]


def db_cleanup_workflow(context: WorkflowContext) -> list[ActionResult]:
    """Delete inactive customers — the Replit pattern (goes wrong)."""
    pg = context.systems["postgres"]
    table = context.payload["table"]
    status = context.payload["status_filter"]
    
    # Find what we're about to delete
    select_result = pg.select_rows(table=table, where={"status": status})
    if not select_result.output.get("rows"):
        return [select_result]
    
    # Delete them — this is where the incident happens
    delete_result = pg.delete_row(table=table, where={"status": status})
    return [select_result, delete_result]


# ── The Demo ───────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 60)
    print("  ENACT QUICKSTART — Block, Pass, Rollback")
    print("=" * 60)

    # We don't pass allowed_actions here because Demo connectors don't enforce it,
    # but in real usage you would do:
    # gh = GitHubConnector(token="...", allowed_actions=["create_branch", "create_pr"])
    gh = DemoGitHubConnector()
    pg = DemoPostgresConnector()

    # ════════════════════════════════════════════════════════════════════════════
    # SCENARIO 1: BLOCK — Agent tries to push to main
    # ════════════════════════════════════════════════════════════════════════════
    print()
    print("─" * 60)
    print("  SCENARIO 1: BLOCK")
    print("─" * 60)
    print()
    print("  An infra agent tries to push directly to main.")
    print("  In Dec 2025, this caused a 13-hour AWS outage (Amazon Kiro).")
    print()

    enact = EnactClient(
        systems={"github": gh},
        policies=[dont_push_to_main],
        workflows=[direct_push_workflow],
        receipt_dir="receipts",
        secret="demo-secret",
        allow_insecure_secret=True,
    )

    result, receipt = enact.run(
        workflow="direct_push_workflow",
        user_email="infra-agent@company.com",
        payload={"repo": "company/api", "branch": "main"},
    )

    print(f"  Decision:  {receipt.decision}")
    print(f"  Success:   {result.success}")
    print("  Policy results:")
    for pr in receipt.policy_results:
        status = "PASS" if pr.passed else "FAIL"
        print(f"    [{status}] {pr.policy}: {pr.reason}")
    print()
    print("  >>> The push was BLOCKED. No branch created. Receipt saved.")
    print()

    # ════════════════════════════════════════════════════════════════════════════
    # SCENARIO 2: PASS — Normal agent PR workflow
    # ════════════════════════════════════════════════════════════════════════════
    print("─" * 60)
    print("  SCENARIO 2: PASS")
    print("─" * 60)
    print()
    print("  Same agent, but follows the rules: creates a feature branch + PR.")
    print()

    enact2 = EnactClient(
        systems={"github": gh},
        policies=[dont_push_to_main],
        workflows=[agent_pr_workflow],
        receipt_dir="receipts",
        secret="demo-secret",
        allow_insecure_secret=True,
    )

    result, receipt = enact2.run(
        workflow="agent_pr_workflow",
        user_email="infra-agent@company.com",
        payload={"repo": "company/api", "branch": "agent/fix-149"},
    )

    print(f"  Decision:  {receipt.decision}")
    print(f"  Success:   {result.success}")
    print("  Policy results:")
    for pr in receipt.policy_results:
        status = "PASS" if pr.passed else "FAIL"
        print(f"    [{status}] {pr.policy}: {pr.reason}")
    print("  Actions taken:")
    for action in receipt.actions_taken:
        print(f"    - {action.action}: {action.output}")
    print(f"  Signature: {receipt.signature[:16]}...")
    print()
    print("  >>> Branch created, PR opened. Signed receipt proves what happened.")
    print()

    # ════════════════════════════════════════════════════════════════════════════
    # SCENARIO 3: ROLLBACK — Undo a database operation
    # ════════════════════════════════════════════════════════════════════════════
    print("─" * 60)
    print("  SCENARIO 3: ROLLBACK")
    print("─" * 60)
    print()
    print("  An agent deletes 'inactive' customers. Oops — those were VIPs!")
    print("  In July 2025, Replit's agent deleted their production database.")
    print()

    enact3 = EnactClient(
        systems={"postgres": pg},
        policies=[],  # No policies blocking this — it's authorized but wrong
        workflows=[db_cleanup_workflow],
        receipt_dir="receipts",
        secret="demo-secret",
        allow_insecure_secret=True,
        rollback_enabled=True,
    )

    # Show before state
    before = pg.select_rows(table="customers")
    print(f"  Before: {before.output['row_count']} customers in database")
    print()

    result, receipt = enact3.run(
        workflow="db_cleanup_workflow",
        user_email="data-agent@company.com",
        payload={"table": "customers", "status_filter": "inactive"},
    )

    print(f"  Decision:  {receipt.decision}")
    print("  Actions taken:")
    for action in receipt.actions_taken:
        if "rows_deleted" in action.output:
            print(f"    - {action.action}: {action.output['rows_deleted']} rows deleted")
        elif "row_count" in action.output:
            print(f"    - {action.action}: {action.output['row_count']} rows found")

    # Show after state
    after = pg.select_rows(table="customers")
    print(f"  After: {after.output['row_count']} customers remaining")
    print()
    print("  >>> Oh no! Those 'inactive' users were actually VIPs on vacation.")
    print("  >>> Rolling back with one call...")
    print()

    # Rollback!
    rollback_result, rollback_receipt = enact3.rollback(receipt.run_id)

    print(f"  Rollback decision: {rollback_receipt.decision}")
    print("  Actions reversed:")
    for action in rollback_receipt.actions_taken:
        if "rows_restored" in action.output:
            print(f"    - {action.action}: {action.output['rows_restored']} rows restored")

    # Show final state
    final = pg.select_rows(table="customers")
    print(f"  Final: {final.output['row_count']} customers restored")
    print()
    print("  >>> Database restored. Signed rollback receipt proves what was undone.")
    print()

    # ════════════════════════════════════════════════════════════════════════════
    print("=" * 60)
    print("  That's Enact in 60 seconds.")
    print("  - Policies block dangerous actions BEFORE they happen")
    print("  - Receipts prove WHAT happened and WHY")
    print("  - Rollback undoes mistakes with one call")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
