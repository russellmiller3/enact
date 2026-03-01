#!/usr/bin/env python3
"""
Enact demo — three scenarios that explain why this exists.

No credentials needed. Uses in-memory demo connectors with the same
interface as the real ones, so EnactClient.rollback() works exactly
as it does against a real database or GitHub repo.

Usage:
    python examples/demo.py
"""
import os
import sys
import time

# Windows CP1252 can't encode box-drawing chars — switch to UTF-8 early
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from enact import EnactClient
from enact.models import WorkflowContext, PolicyResult, ActionResult
from enact.workflows.agent_pr_workflow import agent_pr_workflow
from enact.policies.git import dont_push_to_main, require_branch_prefix


# ── ANSI colours ─────────────────────────────────────────────────────────────
def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        return bool(os.environ.get("ANSICON") or os.environ.get("WT_SESSION"))
    return True


_c = _supports_color()
R   = "\033[31m" if _c else ""
G   = "\033[32m" if _c else ""
Y   = "\033[33m" if _c else ""
B   = "\033[1m"  if _c else ""
DIM = "\033[2m"  if _c else ""
RST = "\033[0m"  if _c else ""


# ── Demo connectors ───────────────────────────────────────────────────────────
# These implement the exact same interface as GitHubConnector and
# PostgresConnector. rollback.py dispatches by method name — it has no
# knowledge of whether the connector is real or in-memory.

class DemoGitHubConnector:
    """In-memory GitHub — same interface as GitHubConnector. No API calls."""

    def __init__(self):
        self._branches: dict[str, set] = {}
        self._prs: dict[str, dict] = {}
        self._pr_counter = 41

    def create_branch(self, repo: str, branch: str, base: str = "main") -> ActionResult:
        self._branches.setdefault(repo, set())
        already = branch in self._branches[repo]
        if not already:
            self._branches[repo].add(branch)
        return ActionResult(
            action="create_branch",
            system="github",
            success=True,
            output={"branch": branch, "repo": repo, "already_done": "created" if already else False},
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
            output={
                "pr_number": pr_num,
                "url": f"https://github.com/{repo}/pull/{pr_num}",
                "already_done": False,
            },
            rollback_data={"repo": repo, "pr_number": pr_num},
        )

    def close_pr(self, repo: str, pr_number: int) -> ActionResult:
        pr = self._prs.get(repo, {}).get(pr_number)
        if pr:
            pr["state"] = "closed"
        return ActionResult(
            action="close_pr",
            system="github",
            success=True,
            output={"pr_number": pr_number, "already_done": False},
        )

    def delete_branch(self, repo: str, branch: str) -> ActionResult:
        self._branches.get(repo, set()).discard(branch)
        return ActionResult(
            action="delete_branch",
            system="github",
            success=True,
            output={"branch": branch, "already_done": False},
        )


class DemoPostgresConnector:
    """
    In-memory Postgres — same interface as PostgresConnector. No psycopg2 needed.

    Pre-loaded with 47 customer rows: 42 active, 5 inactive.
    The db_cleanup_workflow deletes the 5 inactive ones.
    rollback.py reverses the delete by calling insert_row for each — same
    code path as a real Postgres rollback.
    """

    def __init__(self):
        self._tables: dict[str, list] = {
            "customers": [
                {
                    "id": i,
                    "name": f"Customer {i:03d}",
                    "email": f"customer{i}@example.com",
                    "arr_usd": 12000 + (i * 800),
                    "status": "inactive" if i > 42 else "active",
                }
                for i in range(1, 48)
            ]
        }

    def _match(self, row: dict, where: dict) -> bool:
        return all(row.get(k) == v for k, v in where.items())

    def select_rows(self, table: str, where: dict | None = None) -> ActionResult:
        rows = list(self._tables.get(table, []))
        if where:
            rows = [r for r in rows if self._match(r, where)]
        return ActionResult(
            action="select_rows",
            system="postgres",
            success=True,
            output={"rows": rows},
        )

    def insert_row(self, table: str, data: dict) -> ActionResult:
        self._tables.setdefault(table, []).append(dict(data))
        return ActionResult(
            action="insert_row",
            system="postgres",
            success=True,
            output={**data, "already_done": False},
            rollback_data={"table": table, "inserted_row": dict(data)},
        )

    def update_row(self, table: str, data: dict, where: dict) -> ActionResult:
        count = 0
        for row in self._tables.get(table, []):
            if self._match(row, where):
                row.update(data)
                count += 1
        return ActionResult(
            action="update_row",
            system="postgres",
            success=True,
            output={"rows_updated": count, "already_done": False},
            rollback_data={"table": table, "old_rows": [], "where": where},
        )

    def delete_row(self, table: str, where: dict) -> ActionResult:
        rows = self._tables.get(table, [])
        deleted = [r for r in rows if self._match(r, where)]
        self._tables[table] = [r for r in rows if not self._match(r, where)]
        return ActionResult(
            action="delete_row",
            system="postgres",
            success=True,
            output={
                "rows_deleted": len(deleted),
                "already_done": "deleted" if not deleted else False,
            },
            rollback_data={"table": table, "deleted_rows": deleted},
        )


# ── Demo workflows ────────────────────────────────────────────────────────────

def direct_push_workflow(context: WorkflowContext) -> list[ActionResult]:
    """
    Workflow that pushes directly to main — the Kiro pattern.
    Blocked by the dont_push_to_main policy before it ever runs.
    """
    gh = context.systems["github"]
    return [gh.create_pr(
        repo=context.payload["repo"],
        title="Agent: emergency hotfix",
        body="Pushing directly to main — no branch needed",
        head=context.payload["branch"],
    )]


def db_cleanup_workflow(context: WorkflowContext) -> list[ActionResult]:
    """
    Workflow that deletes 'inactive' customer records — the Replit pattern.
    The policy gate passes. The action is authorized. It still goes wrong.
    """
    pg = context.systems["postgres"]
    table = context.payload["table"]
    status = context.payload["status_filter"]
    results = []

    # Step 1: Find what we're about to delete
    select_result = pg.select_rows(table=table, where={"status": status})
    results.append(select_result)

    if not select_result.output.get("rows"):
        return results

    # Step 2: Delete them — this is where the incident happens
    delete_result = pg.delete_row(table=table, where={"status": status})
    results.append(delete_result)
    return results


# ── Output helpers ────────────────────────────────────────────────────────────

W = 62

def _divider():
    print(f"{DIM}{'─' * W}{RST}")

def _act_header(text: str):
    pad = W - 8 - len(text)
    print()
    print(f"{B}{'━' * 4}  {text}  {'━' * pad}{RST}")
    print()

def _print_policies(results):
    for pr in results:
        icon = f"{G}✓{RST}" if pr.passed else f"{R}✗{RST}"
        print(f"    {icon}  {B}{pr.policy}{RST}  ·  {pr.reason}")

def _print_actions(actions):
    for a in actions:
        if a.output.get("already_done") == "skipped":
            continue
        icon = f"{G}✓{RST}" if a.success else f"{R}✗{RST}"
        detail = ""
        out = a.output
        rd = a.rollback_data or {}
        if "pr_number" in out:
            detail = f"  →  PR #{out['pr_number']} · {out.get('url', '')}"
        elif "branch" in out and a.action == "create_branch":
            detail = f"  →  branch \"{out['branch']}\" created"
        elif "rows_deleted" in out:
            detail = f"  →  {out['rows_deleted']} rows deleted from \"{rd.get('table', '?')}\""
        elif "rows" in out:
            detail = f"  →  {len(out['rows'])} rows found matching filter"
        print(f"    {icon}  {B}{a.action}{RST}{detail}")

def _print_rollback_actions(actions):
    for a in actions:
        if a.output.get("already_done") == "skipped":
            continue
        icon = f"{G}✓{RST}" if a.success else f"{R}✗{RST}"
        if a.success:
            restored = a.output.get("rows_restored")
            suffix = f"  ·  {G}{restored} rows restored{RST}" if restored else ""
            print(f"    {icon}  {B}{a.action}{RST}  →  {G}REVERSED{RST}{suffix}")
        else:
            print(f"    {icon}  {B}{a.action}{RST}  →  {R}COULD NOT REVERSE{RST}  ·  {a.output.get('error', '')}")


# ── The demo ──────────────────────────────────────────────────────────────────

def run_demo():
    print()
    print(f"{B}{'═' * W}{RST}")
    print(f"{B}  ENACT DEMO  ·  action firewall for AI agents{RST}")
    print(f"{B}{'═' * W}{RST}")

    gh = DemoGitHubConnector()
    pg = DemoPostgresConnector()

    # ── ACT 1: The Kiro Scenario ─────────────────────────────────────────────
    _act_header("ACT 1: The Kiro Scenario")
    print(f"  It's 3:57am. An infra agent decides to push directly to main.")
    print(f"  {DIM}In Dec 2025 this cascaded into a 13-hour AWS outage.{RST}")
    print()
    print(f"  {DIM}enact.run(workflow=\"direct_push_workflow\",{RST}")
    print(f"  {DIM}          actor=\"infra-agent@company.com\",{RST}")
    print(f"  {DIM}          payload={{\"repo\": \"company/api\", \"branch\": \"main\"}}){RST}")
    print()

    git_enact = EnactClient(
        systems={"github": gh},
        policies=[dont_push_to_main],
        workflows=[direct_push_workflow],
        secret="demo-secret", allow_insecure_secret=True,
    )
    _, receipt1 = git_enact.run(
        workflow="direct_push_workflow",
        user_email="infra-agent@company.com",
        payload={"repo": "company/api", "branch": "main"},
    )
    print(f"  {B}Policy gate:{RST}")
    _print_policies(receipt1.policy_results)
    print()
    color = G if receipt1.decision == "PASS" else R
    print(f"  {B}Decision:{RST} {color}{receipt1.decision}{RST}  ·  No actions executed  ·  Receipt signed.")
    print(f"  {DIM}receipts/{receipt1.run_id[:8]}...json{RST}")
    _divider()

    # ── ACT 2: Normal Operation ──────────────────────────────────────────────
    _act_header("ACT 2: Normal Operation")
    print(f"  Same agent. Correct workflow. Creates a branch, opens a PR.")
    print()
    print(f"  {DIM}enact.run(workflow=\"agent_pr_workflow\",{RST}")
    print(f"  {DIM}          actor=\"agent@company.com\",{RST}")
    print(f"  {DIM}          payload={{\"repo\": \"company/api\", \"branch\": \"agent/fix-149\"}}){RST}")
    print()

    pr_enact = EnactClient(
        systems={"github": gh},
        policies=[dont_push_to_main, require_branch_prefix("agent/")],
        workflows=[agent_pr_workflow],
        secret="demo-secret", allow_insecure_secret=True,
    )
    _, receipt2 = pr_enact.run(
        workflow="agent_pr_workflow",
        user_email="agent@company.com",
        payload={
            "repo": "company/api",
            "branch": "agent/fix-149",
            "title": "fix: handle null user on checkout",
        },
    )
    print(f"  {B}Policy gate:{RST}")
    _print_policies(receipt2.policy_results)
    print()
    print(f"  {B}Workflow:{RST}")
    _print_actions(receipt2.actions_taken)
    print()
    color = G if receipt2.decision == "PASS" else R
    print(f"  {B}Decision:{RST} {color}{receipt2.decision}{RST}  ·  Receipt signed.")
    print(f"  {DIM}receipts/{receipt2.run_id[:8]}...json{RST}")
    _divider()

    # ── ACT 3: The Replit Scenario ───────────────────────────────────────────
    _act_header("ACT 3: The Replit Scenario")
    print(f"  An agent is doing routine database cleanup.")
    print(f"  It has ops approval. The policies pass. The cleanup runs.")
    print(f"  Everything works exactly as configured.")
    print()
    print(f"  {DIM}enact.run(workflow=\"db_cleanup_workflow\",{RST}")
    print(f"  {DIM}          actor=\"cleanup-agent@company.com\",{RST}")
    print(f"  {DIM}          payload={{\"table\": \"customers\", \"status_filter\": \"inactive\"}}){RST}")
    print()

    def ops_approved(context: WorkflowContext) -> PolicyResult:
        return PolicyResult(
            policy="ops_approved",
            passed=True,
            reason="Routine maintenance — approved by ops team",
        )

    db_enact = EnactClient(
        systems={"postgres": pg},
        policies=[ops_approved],
        workflows=[db_cleanup_workflow],
        rollback_enabled=True,
        secret="demo-secret", allow_insecure_secret=True,
    )
    _, receipt3 = db_enact.run(
        workflow="db_cleanup_workflow",
        user_email="cleanup-agent@company.com",
        payload={"table": "customers", "status_filter": "inactive"},
    )
    print(f"  {B}Policy gate:{RST}")
    _print_policies(receipt3.policy_results)
    print()
    print(f"  {B}Workflow:{RST}")
    _print_actions(receipt3.actions_taken)
    print()
    print(f"  {B}Decision:{RST} {G}PASS{RST}  ·  Receipt signed.")
    print(f"  {DIM}receipts/{receipt3.run_id[:8]}...json{RST}")
    print()

    time.sleep(0.5)

    rows_deleted = 0
    for a in receipt3.actions_taken:
        if a.action == "delete_row":
            rows_deleted = a.output.get("rows_deleted", 0)

    print(f"  {Y}{B}⚠  The status field was wrong. Those records were live customers.{RST}")
    print(f"  {Y}⚠  {rows_deleted} records gone. ${ rows_deleted * 14400:,} ARR just vanished.{RST}")
    print(f"  {DIM}The policy worked. The agent did what it was told. The source data was bad.{RST}")
    print()

    # Show what was deleted — pulled from the receipt's rollback_data
    delete_action = next(
        (a for a in receipt3.actions_taken if a.action == "delete_row"), None
    )
    if delete_action and delete_action.rollback_data.get("deleted_rows"):
        deleted_rows = delete_action.rollback_data["deleted_rows"]
        print(f"  {B}What was deleted{RST} {DIM}(captured in receipt at deletion time):{RST}")
        for row in deleted_rows:
            name = row.get("name", "?")
            email = row.get("email", "?")
            arr = row.get("arr_usd", 0)
            print(f"    {R}x{RST}  {name}  ·  {email}  ·  ${arr:,} ARR")
        print(f"  {DIM}Stored in receipts/{receipt3.run_id[:8]}...json · HMAC-SHA256 signed{RST}")
        print()

    time.sleep(0.5)

    print(f"  {DIM}enact.rollback(\"{receipt3.run_id[:8]}...\"){RST}")
    print()

    _, rollback_receipt = db_enact.rollback(receipt3.run_id)

    print(f"  {B}Rollback:{RST}")
    _print_rollback_actions(rollback_receipt.actions_taken)
    print()

    # Verify: query the database to prove the rows are actually back
    verify = pg.select_rows(table="customers", where={"status": "inactive"})
    restored_rows = verify.output.get("rows", [])
    if restored_rows:
        print(f"  {B}Verified{RST} {DIM}(live query after rollback):{RST}")
        for row in restored_rows:
            name = row.get("name", "?")
            email = row.get("email", "?")
            print(f"    {G}✓{RST}  {name}  ·  {email}  ·  {G}back{RST}")
        print()

    color = G if rollback_receipt.decision in ("PASS", "PARTIAL") else R
    print(f"  {B}Decision:{RST} {color}{rollback_receipt.decision}{RST}  ·  {rows_deleted} customer records restored.")
    print(f"  {DIM}receipts/{rollback_receipt.run_id[:8]}...json  (rollback receipt, signed){RST}")
    _divider()

    print()
    print(f"{B}{'═' * W}{RST}")
    print(f"{B}  3 scenarios. Receipts signed. One command to undo.{RST}")
    print(f"  {DIM}pip install enact-sdk  ·  github.com/russellmiller3/enact{RST}")
    print(f"{B}{'═' * W}{RST}")
    print()


if __name__ == "__main__":
    run_demo()
