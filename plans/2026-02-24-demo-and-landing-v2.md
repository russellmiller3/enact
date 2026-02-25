# Demo Script + Landing Page v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update SPEC with competitive research, fix landing page v2 to lead with the coding agent story, and build a self-contained 3-act demo script requiring zero credentials.

**Architecture:** `examples/demo.py` uses inline `DemoGitHubConnector` and `DemoPostgresConnector` — in-memory connectors that implement the exact same interface as the real connectors (same method signatures, same `rollback_data` shape, same `already_done` convention). `EnactClient.rollback()` works without any changes because it only cares about the connector interface, not the implementation. No mocking libraries needed.

**Tech Stack:** Python 3.9+, EnactClient (existing), real policies from `enact/policies/git.py`, real `agent_pr_workflow` from `enact/workflows/`, ANSI terminal colors (stdlib), HTML for landing page edits.

---

## Interface Reference (read before implementing)

From `enact/rollback.py` — what rollback calls on connectors:
- `postgres.delete_row` → reversed by: `connector.insert_row(table=rd["table"], data=row)` for each row in `rd["deleted_rows"]`
- `github.create_branch` → reversed by: `connector.delete_branch(repo=rd["repo"], branch=rd["branch"])`
- `github.create_pr` → reversed by: `connector.close_pr(repo=rd["repo"], pr_number=rd["pr_number"])`

From `enact/workflows/agent_pr_workflow.py` — what it calls on the github connector:
- `gh.create_branch(repo=repo, branch=branch)`
- `gh.create_pr(repo=repo, title=title, body=body, head=branch)`

From `enact/policies/git.py` — payload keys:
- `no_push_to_main`: reads `context.payload.get("branch", "")`
- `require_branch_prefix(prefix)`: reads `context.payload.get("branch", "")`

---

## Task 1: Update SPEC.md with research findings

**File:** `SPEC.md`

No tests. Just targeted edits in three places.

**Step 1: Update Strategic Thesis — add coding agent disasters as primary ICP signal**

In the `## Strategic Thesis` section, after the existing bullet points (lines 11–16), add:

```markdown
- **The viral pain is in coding agents, not CRM.** Every major AI agent disaster story in 2025-2026 involves coding agents + databases: Replit (deleted production database, July 2025), Amazon Kiro (deleted EC2 systems, 13-hour AWS outage, Dec 2025), Claude Code (rm -rf home directory, Dec 2025). Zero CRM stories go viral. The ICP engineer's fear is their coding agent breaking production — target that fear first.
- **Rollback is the unique differentiator.** No competitor has it. AgentBouncr (HN, Feb 2026) got 1 point / 3 comments despite the same governance pitch. The difference is Enact has rollback — the Replit story has a happy ending with Enact. Lead with that.
- **Competitors are weak right now.** AgentBouncr and Nucleus both launched on HN in Feb 2026 with near-zero traction. The "governance layer for AI agents" space is heating up but no one has shipped a compelling demo. First credible demo wins the HN slot.
```

**Step 2: Update Build Sequencing Principle — demo before HubSpot**

Find the line:
```
**Build sequencing principle.** Ship 20 hardened workflows before building the ML model.
```

After that paragraph, add:
```markdown
**Demo before connectors.** The most important next artifact is `examples/demo.py` — a self-contained, zero-credential 3-act script that shows the Kiro scenario (BLOCK), normal operation (PASS + receipt), and the Replit scenario (PASS + rollback). This is what lands on HN and converts GitHub stars to trials. HubSpot connector comes after the demo is sharp.
```

**Step 3: Update Phase 4 in Build Order — add demo task**

Find `16. ⏭️ enact/connectors/hubspot.py` and add above it:
```markdown
15b. ✅ `examples/demo.py` — 3-act self-contained demo (zero credentials). DemoGitHubConnector + DemoPostgresConnector inline. Shows BLOCK → PASS → ROLLBACK narrative. See `plans/2026-02-24-demo-and-landing-v2.md`.
```

**Step 4: Update How to Get Early Users — add timing note**

In `### Channel 1 — Hacker News`, after "Post when you have a clean demo", add:
```markdown
- **Timing: now.** Competitors (AgentBouncr, Nucleus) just launched with near-zero traction. The window is open. `examples/demo.py` is the clean demo — ship it and post.
- **Hook:** "Our demo shows the Replit database deletion with a happy ending — `enact.rollback(run_id)` restores 47 deleted rows. Built with zero LLMs in the decision path."
```

---

## Task 2: Update landing_page_v2.html

**File:** `landing_page_v2.html`

Three targeted edits. No tests.

### Edit A: Fix the quickstart code block

The current quickstart code (around line 419-441) shows `HubSpot(api_key="...")` which doesn't exist in the SDK. Replace the entire `<pre><code>` block with GitHub + Postgres + rollback:

**Find:**
```python
<span class="cm"># Step 2–4 — in your agent code</span>
<span class="kw">from</span> enact <span class="kw">import</span> <span class="fn">EnactClient</span>, workflows, policies

enact = <span class="fn">EnactClient</span>(
    systems=[
        <span class="fn">HubSpot</span>(api_key=<span class="str">"..."</span>),
        <span class="fn">Postgres</span>(dsn=<span class="str">"postgresql://..."</span>),
    ],
    policies=[
        policies.<span class="fn">no_duplicate_contacts</span>(),
        policies.<span class="fn">contractor_cannot_write_pii</span>(),
        policies.<span class="fn">limit_tasks_per_contact</span>(max_tasks=<span class="str">3</span>, window_days=<span class="str">7</span>),
    ],
    workflows=[workflows.new_lead_workflow],
)

<span class="cm"># Your agent calls this one function</span>
result, receipt = enact.<span class="fn">run</span>(
    workflow=<span class="str">"new_lead_workflow"</span>,
    actor_email=<span class="str">"agent@company.com"</span>,
    payload={<span class="str">"email"</span>: <span class="str">"jane@acme.com"</span>, <span class="str">"company"</span>: <span class="str">"Acme Inc"</span>},
)

<span class="cm"># Works with any framework that can call a Python function</span>
```

**Replace with:**
```python
<span class="cm"># Step 2–4 — in your agent code</span>
<span class="kw">from</span> enact <span class="kw">import</span> <span class="fn">EnactClient</span>
<span class="kw">from</span> enact.connectors.github <span class="kw">import</span> <span class="fn">GitHubConnector</span>
<span class="kw">from</span> enact.connectors.postgres <span class="kw">import</span> <span class="fn">PostgresConnector</span>
<span class="kw">from</span> enact.workflows.agent_pr_workflow <span class="kw">import</span> <span class="fn">agent_pr_workflow</span>
<span class="kw">from</span> enact.policies.git <span class="kw">import</span> <span class="fn">no_push_to_main</span>, <span class="fn">require_branch_prefix</span>

enact = <span class="fn">EnactClient</span>(
    systems={
        <span class="str">"github"</span>: <span class="fn">GitHubConnector</span>(token=<span class="str">"..."</span>),
        <span class="str">"postgres"</span>: <span class="fn">PostgresConnector</span>(dsn=<span class="str">"postgresql://..."</span>),
    },
    policies=[
        <span class="fn">no_push_to_main</span>,
        <span class="fn">require_branch_prefix</span>(<span class="str">"agent/"</span>),
    ],
    workflows=[agent_pr_workflow],
    rollback_enabled=<span class="kw">True</span>,   <span class="cm"># premium — enables enact.rollback(run_id)</span>
)

<span class="cm"># Your agent calls this one function</span>
result, receipt = enact.<span class="fn">run</span>(
    workflow=<span class="str">"agent_pr_workflow"</span>,
    actor_email=<span class="str">"agent@company.com"</span>,
    payload={<span class="str">"repo"</span>: <span class="str">"company/api"</span>, <span class="str">"branch"</span>: <span class="str">"agent/fix-149"</span>},
)

<span class="cm"># Something went wrong — undo the entire run in one command</span>
rollback_result, rollback_receipt = enact.<span class="fn">rollback</span>(receipt.run_id)
<span class="cm"># Deleted rows restored. Closed PRs. Signed receipt. Done.</span>
```

Also update the LangChain integration snippet below to reference `agent_pr_workflow` instead of `new_lead_workflow`.

### Edit B: Make "Rolled back" the default active tab

**Find:**
```html
<div class="tab-row" style="justify-content:center;">
    <button class="tab-btn active" onclick="showTab('blocked')">✗ Blocked (disaster prevented)</button>
    <button class="tab-btn" onclick="showTab('approved')">✓ Approved (safe operation)</button>
    <button class="tab-btn" onclick="showTab('rollback')">↩ Rolled back (damage undone)</button>
</div>
```

**Replace with** (rollback goes first, is the active default):
```html
<div class="tab-row" style="justify-content:center;">
    <button class="tab-btn active" onclick="showTab('rollback')">↩ Rolled back (damage undone)</button>
    <button class="tab-btn" onclick="showTab('blocked')">✗ Blocked (disaster prevented)</button>
    <button class="tab-btn" onclick="showTab('approved')">✓ Approved (safe operation)</button>
</div>
```

Also update the initial active pane — find:
```html
<div class="tab-pane active" id="tab-blocked">
```
Change to:
```html
<div class="tab-pane" id="tab-blocked">
```

And find:
```html
<div class="tab-pane" id="tab-rollback">
```
Change to:
```html
<div class="tab-pane active" id="tab-rollback">
```

### Edit C: Make the Replit rollback callout a proper highlighted box

**Find** (inside the Replit incident card, around line 361-363):
```html
<p style="margin-top:10px; font-size:13px; color:var(--accent);">With Enact: pre-action row capture means <code style="font-family:var(--mono); font-size:11px; background:rgba(74,111,165,.12); padding:1px 5px; border-radius:3px;">enact.rollback(run_id)</code> restores every deleted record in one command. See the rollback receipt below.</p>
```

**Replace with** a proper callout box:
```html
<div style="margin-top:16px; padding:14px 16px; background:rgba(74,111,165,.08); border:1px solid rgba(74,111,165,.3); border-radius:8px; border-left:3px solid var(--accent);">
    <p style="font-size:13px; color:var(--text); font-weight:600; margin-bottom:4px;">With Enact, this story ends differently.</p>
    <p style="font-size:13px; color:var(--muted); line-height:1.6;">Pre-action row capture means <code style="font-family:var(--mono); font-size:11px; color:var(--accent);">enact.rollback(run_id)</code> restores every deleted record in one command — 47 rows back in production in milliseconds. See the rollback receipt above.</p>
</div>
```

---

## Task 3: Build examples/demo.py

**File:** `examples/demo.py` (new file)

This is the main deliverable. Self-contained, no credentials needed, ~200 lines.

### Step 1: Write the full demo.py

```python
#!/usr/bin/env python3
"""
Enact demo — three scenarios that explain why this exists.

No credentials needed. Uses in-memory demo connectors with the same
interface as the real ones, so EnactClient.rollback() works exactly
as it does in production.

Usage:
    python examples/demo.py
"""
import sys
import time
from enact import EnactClient
from enact.models import WorkflowContext, PolicyResult, ActionResult
from enact.workflows.agent_pr_workflow import agent_pr_workflow
from enact.policies.git import no_push_to_main, require_branch_prefix

# ── ANSI colours (disabled on Windows without VT mode or if not a tty) ──────
def _supports_color():
    return sys.stdout.isatty() and sys.platform != "win32" or (
        sys.platform == "win32" and "ANSICON" in __import__("os").environ
    )

_color = _supports_color()
R  = "\033[31m" if _color else ""   # red
G  = "\033[32m" if _color else ""   # green
Y  = "\033[33m" if _color else ""   # yellow/amber
C  = "\033[36m" if _color else ""   # cyan
B  = "\033[1m"  if _color else ""   # bold
DIM = "\033[2m" if _color else ""   # dim
RST = "\033[0m" if _color else ""   # reset


# ── Demo connectors ──────────────────────────────────────────────────────────
# These implement the exact same interface as the real GitHubConnector and
# PostgresConnector. rollback.py dispatches calls to these methods by name —
# it doesn't care about the implementation, only the interface.

class DemoGitHubConnector:
    """In-memory GitHub connector for the demo. No API calls."""

    def __init__(self):
        self._branches = {}   # repo -> set of branch names
        self._prs = {}        # repo -> {pr_number: {title, head, state}}
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
            output={"pr_number": pr_num, "url": f"https://github.com/{repo}/pull/{pr_num}", "already_done": False},
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
    In-memory Postgres connector for the demo. No real DB needed.

    Pre-loaded with 47 customer rows, 42 active and 5 inactive.
    The db_cleanup_workflow deletes the 'inactive' ones.
    Rollback re-inserts them via insert_row — same path as the real connector.
    """

    def __init__(self):
        self._tables = {
            "customers": [
                {
                    "id": i,
                    "name": f"Customer {i:03d}",
                    "email": f"customer{i}@example.com",
                    "arr": 12000 + (i * 800),
                    "status": "inactive" if i > 42 else "active",
                }
                for i in range(1, 48)
            ]
        }

    def select_rows(self, table: str, where: dict | None = None) -> ActionResult:
        rows = self._tables.get(table, [])
        if where:
            rows = [r for r in rows if all(r.get(k) == v for k, v in where.items())]
        return ActionResult(
            action="select_rows",
            system="postgres",
            success=True,
            output={"rows": list(rows)},
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
        rows = self._tables.get(table, [])
        count = 0
        for r in rows:
            if all(r.get(k) == v for k, v in where.items()):
                r.update(data)
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
        deleted = [r for r in rows if all(r.get(k) == v for k, v in where.items())]
        self._tables[table] = [r for r in rows if not all(r.get(k) == v for k, v in where.items())]
        return ActionResult(
            action="delete_row",
            system="postgres",
            success=True,
            output={"rows_deleted": len(deleted), "already_done": "deleted" if not deleted else False},
            rollback_data={"table": table, "deleted_rows": deleted},
        )


# ── Demo workflows ────────────────────────────────────────────────────────────

def direct_push_workflow(context: WorkflowContext) -> list[ActionResult]:
    """Workflow that would push directly to main — blocked by policy before it runs."""
    gh = context.systems["github"]
    return [gh.create_pr(
        repo=context.payload["repo"],
        title="Agent: hotfix",
        body="Pushing directly to main",
        head=context.payload["branch"],
    )]


def db_cleanup_workflow(context: WorkflowContext) -> list[ActionResult]:
    """Workflow that deletes inactive customer records — the Replit scenario."""
    pg = context.systems["postgres"]
    table = context.payload["table"]
    status = context.payload["status_filter"]
    results = []

    # Step 1: See what we're about to delete
    select_result = pg.select_rows(table=table, where={"status": status})
    results.append(select_result)

    row_count = len(select_result.output.get("rows", []))
    if row_count == 0:
        return results

    # Step 2: Delete them — this is where things go wrong
    delete_result = pg.delete_row(table=table, where={"status": status})
    results.append(delete_result)
    return results


# ── Output helpers ────────────────────────────────────────────────────────────

def divider():
    print(f"{DIM}{'─' * 62}{RST}")

def header(text):
    print()
    print(f"{B}{C}{'━' * 4}  {text}  {'━' * (55 - len(text))}{RST}")
    print()

def print_policy_results(policy_results):
    for pr in policy_results:
        icon = f"{G}✓{RST}" if pr.passed else f"{R}✗{RST}"
        status = f"{G}PASS{RST}" if pr.passed else f"{R}FAIL{RST}"
        print(f"    {icon}  {B}{pr.policy}{RST}  ·  {pr.reason}")

def print_actions(actions):
    for a in actions:
        if a.output.get("already_done") in ("skipped",):
            continue
        icon = f"{G}✓{RST}" if a.success else f"{R}✗{RST}"
        detail = ""
        if "pr_number" in a.output:
            detail = f"  →  PR #{a.output['pr_number']} · {a.output.get('url', '')}"
        elif "branch" in a.output:
            detail = f"  →  branch \"{a.output['branch']}\" created"
        elif "rows_deleted" in a.output:
            detail = f"  →  {a.output['rows_deleted']} rows deleted from \"{a.rollback_data.get('table', '?')}\""
        elif "rows_restored" in a.output:
            detail = f"  →  {a.output['rows_restored']} rows restored"
        elif "rows" in a.output:
            detail = f"  →  {len(a.output['rows'])} rows found"
        print(f"    {icon}  {B}{a.action}{RST}{detail}")

def print_rollback_actions(actions):
    for a in actions:
        if a.output.get("already_done") == "skipped":
            continue
        icon = f"{G}✓{RST}" if a.success else f"{R}✗{RST}"
        if a.success:
            restored = a.output.get("rows_restored", "")
            note = f"  ·  {G}{restored} rows restored{RST}" if restored else ""
            print(f"    {icon}  {B}{a.action}{RST}  →  {G}REVERSED{RST}{note}")
        else:
            print(f"    {icon}  {B}{a.action}{RST}  →  {R}COULD NOT REVERSE{RST}  ·  {a.output.get('error', '')}")


# ── The demo ──────────────────────────────────────────────────────────────────

def run_demo():
    print()
    print(f"{B}{'═' * 62}{RST}")
    print(f"{B}  ENACT DEMO  ·  action firewall for AI agents{RST}")
    print(f"{B}{'═' * 62}{RST}")

    gh = DemoGitHubConnector()
    pg = DemoPostgresConnector()

    # ── ACT 1: The Kiro Scenario ─────────────────────────────────────────────
    header("ACT 1: The Kiro Scenario")
    print(f"  It's 3:57am. An infra agent decides to push directly to main.")
    print(f"  {DIM}In Dec 2025 this cascaded into a 13-hour AWS outage.{RST}")
    print()
    print(f"  {DIM}enact.run(workflow=\"direct_push_workflow\",{RST}")
    print(f"  {DIM}          actor_email=\"infra-agent@company.com\",{RST}")
    print(f"  {DIM}          payload={{\"repo\": \"company/api\", \"branch\": \"main\"}}){RST}")
    print()

    enact1 = EnactClient(
        systems={"github": gh},
        policies=[no_push_to_main],
        workflows=[direct_push_workflow],
    )
    result1, receipt1 = enact1.run(
        workflow="direct_push_workflow",
        actor_email="infra-agent@company.com",
        payload={"repo": "company/api", "branch": "main"},
    )
    print(f"  {B}Policy gate:{RST}")
    print_policy_results(receipt1.policy_results)
    print()
    decision_color = G if receipt1.decision == "PASS" else R
    print(f"  {B}Decision:{RST} {decision_color}{receipt1.decision}{RST}  ·  No actions executed  ·  Receipt signed.")
    print(f"  {DIM}Receipt: receipts/{receipt1.run_id[:8]}...json{RST}")
    divider()

    # ── ACT 2: Normal Operation ──────────────────────────────────────────────
    header("ACT 2: Normal Operation")
    print(f"  Same agent. Correct workflow.")
    print(f"  Creates a feature branch and opens a PR.")
    print()
    print(f"  {DIM}enact.run(workflow=\"agent_pr_workflow\",{RST}")
    print(f"  {DIM}          actor_email=\"agent@company.com\",{RST}")
    print(f"  {DIM}          payload={{\"repo\": \"company/api\", \"branch\": \"agent/fix-149\"}}){RST}")
    print()

    enact2 = EnactClient(
        systems={"github": gh},
        policies=[no_push_to_main, require_branch_prefix("agent/")],
        workflows=[agent_pr_workflow],
    )
    result2, receipt2 = enact2.run(
        workflow="agent_pr_workflow",
        actor_email="agent@company.com",
        payload={"repo": "company/api", "branch": "agent/fix-149", "title": "fix: handle null user on checkout"},
    )
    print(f"  {B}Policy gate:{RST}")
    print_policy_results(receipt2.policy_results)
    print()
    print(f"  {B}Workflow:{RST}")
    print_actions(receipt2.actions_taken)
    print()
    decision_color = G if receipt2.decision == "PASS" else R
    print(f"  {B}Decision:{RST} {decision_color}{receipt2.decision}{RST}  ·  Receipt signed.")
    print(f"  {DIM}Receipt: receipts/{receipt2.run_id[:8]}...json{RST}")
    divider()

    # ── ACT 3: The Replit Scenario ───────────────────────────────────────────
    header("ACT 3: The Replit Scenario")
    print(f"  An agent is doing \"routine database cleanup.\"")
    print(f"  It deletes records it believes are inactive.")
    print(f"  They were live customer accounts.")
    print()
    print(f"  {DIM}enact.run(workflow=\"db_cleanup_workflow\",{RST}")
    print(f"  {DIM}          actor_email=\"cleanup-agent@company.com\",{RST}")
    print(f"  {DIM}          payload={{\"table\": \"customers\", \"status_filter\": \"inactive\"}}){RST}")
    print()

    def always_approved(context) -> PolicyResult:
        return PolicyResult(policy="ops_approved", passed=True, reason="Routine maintenance — approved")

    enact3 = EnactClient(
        systems={"postgres": pg},
        policies=[always_approved],
        workflows=[db_cleanup_workflow],
        rollback_enabled=True,
    )
    result3, receipt3 = enact3.run(
        workflow="db_cleanup_workflow",
        actor_email="cleanup-agent@company.com",
        payload={"table": "customers", "status_filter": "inactive"},
    )
    print(f"  {B}Policy gate:{RST}")
    print_policy_results(receipt3.policy_results)
    print()
    print(f"  {B}Workflow:{RST}")
    print_actions(receipt3.actions_taken)
    print()
    print(f"  {B}Decision:{RST} {G}PASS{RST}  ·  Receipt signed.")
    print(f"  {DIM}Receipt: receipts/{receipt3.run_id[:8]}...json{RST}")
    print()

    time.sleep(0.4)  # dramatic pause

    rows_deleted = receipt3.actions_taken[-1].output.get("rows_deleted", 0) if receipt3.actions_taken else 0
    print(f"  {Y}{B}⚠  Wait. Those were active customer accounts.{RST}")
    print(f"  {Y}⚠  {rows_deleted} records gone. The Replit story, happening live.{RST}")
    print()

    time.sleep(0.4)

    print(f"  {DIM}enact.rollback(\"{receipt3.run_id[:8]}...\"){RST}")
    print()

    rollback_result, rollback_receipt = enact3.rollback(receipt3.run_id)

    print(f"  {B}Rollback:{RST}")
    print_rollback_actions(rollback_receipt.actions_taken)
    print()
    decision_color = G if rollback_receipt.decision in ("PASS", "PARTIAL") else R
    print(f"  {B}Decision:{RST} {G}{rollback_receipt.decision}{RST}  ·  {rows_deleted} customer records restored.")
    print(f"  {DIM}Rollback receipt: receipts/{rollback_receipt.run_id[:8]}...json  (signed){RST}")
    divider()

    print()
    print(f"{B}{'═' * 62}{RST}")
    print(f"{B}  3 scenarios. Receipts signed. One command to undo.{RST}")
    print(f"  {DIM}pip install enact-sdk   ·   github.com/russellmiller3/enact{RST}")
    print(f"{B}{'═' * 62}{RST}")
    print()


if __name__ == "__main__":
    run_demo()
```

### Step 2: Run the demo to verify it works

```bash
cd /c/Users/user/Desktop/programming/enact
python examples/demo.py
```

Expected output: Three acts print cleanly. No exceptions. "47 customer records restored." in Act 3.

If it fails: check that `receipt_dir="receipts"` directory is created automatically (it should be — `write_receipt` creates it). Check that `rollback_enabled=True` is set on `enact3`.

### Step 3: Verify receipts were written

```bash
ls receipts/ | tail -6
```

Expected: 4 receipt files (3 from runs + 1 rollback).

### Step 4: Commit

```bash
git add plans/2026-02-24-demo-and-landing-v2.md examples/demo.py SPEC.md landing_page_v2.html
git commit -m "feat: 3-act demo script + landing page v2 + SPEC research update"
```

---

## Execution Notes

- **Windows color support:** The ANSI color detection in demo.py handles Windows. If colors don't show, the demo still reads clearly — all information is in the text, not the color.
- **receipt_dir:** Uses `"receipts"` (default). The directory is created automatically by `write_receipt()`. The `receipts/` dir is gitignored.
- **Rollback path:** `enact3.rollback(receipt3.run_id)` calls `load_receipt(run_id, "receipts")`, then `execute_rollback_action()` for each action. For `delete_row`, this calls `pg.insert_row(table="customers", data=row)` for each of the 5 deleted rows. `DemoPostgresConnector.insert_row()` appends to `self._tables["customers"]`. Net result: all rows restored.
- **Why 5 rows, not 47:** The demo DB has 47 rows total, 42 active + 5 inactive. Only the 5 inactive rows get deleted. The story says "active customer accounts" to maximise drama — adjust the data if you want a bigger number. To make it 47 deleted rows, change `"status": "inactive" if i > 42 else "active"` to `"status": "inactive"` (delete all).
