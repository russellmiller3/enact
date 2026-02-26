# Enact

**An action firewall for AI agents.**

Your agent decides what to do. Enact makes sure it's allowed, executes it deterministically, and writes a signed receipt proving exactly what happened.

Three things:
1. **Actions run deterministically** — no LLMs in the execution path. Define workflows as plain Python functions.
2. **Policies gate every action** — pure Python checks that run before anything fires. Git-versioned, fully testable.
3. **Receipts prove everything** — HMAC-SHA256 signed JSON. Who ran what, which policies passed, what changed.

```
pip install enact-sdk
```

---

## Quickstart (30 seconds)

```bash
git clone https://github.com/russellmiller3/enact
cd enact
pip install -e ".[dev]"
python examples/quickstart.py
```

That's it. Two runs — one PASS, one BLOCK — with signed receipts.

Want the full show? `python examples/demo.py` runs a 3-act scenario: an agent blocked from pushing to main, a normal PR workflow, and a database wipe rolled back in one command. No credentials needed.

---

## Core Concepts

Think of Enact like a **bouncer at a club** 🎪 — before anyone gets in, they need to pass the rules. If they pass, they get a stamped receipt proving they got in. If they fail, they're blocked at the door.

### The Three Pieces

| Piece | What it is | Analogy |
|-------|------------|---------|
| **Policy** | A Python function that returns pass/fail | The bouncer's checklist |
| **Workflow** | A Python function that does the actual work | What happens inside the club |
| **Receipt** | A signed JSON record of what happened | Your stamped ticket out |

### How They Fit Together

```
Agent wants to do something
         |
         v
    +----------+
    | POLICIES |  <-- "Is this allowed?"
    +----------+
         |
    PASS |  BLOCK --> Receipt (denied, here's why)
         v
    +-----------+
    | WORKFLOW  |  <-- "Do the thing"
    +-----------+
         |
         v
    +----------+
    | RECEIPT  |  <-- "Here's proof of what happened"
    +----------+
```

### Why This Matters for AI Agents

AI agents are powerful but unpredictable. Real disasters have happened:

| Incident | What Happened | When |
|----------|---------------|------|
| **Replit** | Agent deleted a production database | July 2025 |
| **Amazon Kiro** | Agent deleted EC2 systems → 13-hour AWS outage | Dec 2025 |
| **Claude Code** | Agent ran `rm -rf` on home directory | Dec 2025 |

Enact prevents these by:
1. **Blocking dangerous actions before they happen** — `dont_push_to_main`, `block_ddl`, `dont_delete_without_where`
2. **Recording everything** — Every run gets a signed receipt with who/what/why/pass-or-fail
3. **Enabling rollback** — If something does go wrong, undo it with one call

### The Receipt is the Magic

Every run — whether allowed or blocked — generates a cryptographically-signed receipt. This gives you:

- **Audit trail** — Prove what happened, when, and why
- **Non-repudiation** — The HMAC signature proves the receipt wasn't tampered with
- **Compliance** — Regulators love this

It's like a store receipt, but for software decisions. "Your agent tried to do X, here's proof of what we decided and why."

---

## How It Works

### Step 1: Define what your agent should do

A workflow is a plain Python function. It takes a context (who's calling, with what data), uses **Connectors** to take actions, and returns a list of the results.

Enact ships with GitHub, Postgres, and Filesystem connectors that handle the actual API calls for you. Every time you call a connector method, it returns an `ActionResult`.

Here is how you execute multiple actions sequentially. Notice how we collect the results and stop early if something fails:

```python
from enact.models import WorkflowContext, ActionResult

def agent_pr_workflow(context: WorkflowContext) -> list[ActionResult]:
    # 1. Get the connector from the context
    gh = context.systems["github"]
    repo = context.payload["repo"]
    branch = context.payload["branch"]

    results = []

    # 2. Take the first action
    result1 = gh.create_branch(repo=repo, branch=branch)
    results.append(result1)
    
    # 3. Stop early if it failed
    if not result1.success:
        return results

    # 4. Take the next action
    result2 = gh.create_pr(repo=repo, title=f"Agent: {branch}", body="Automated PR", head=branch)
    results.append(result2)

    # 5. Return the full history of what happened
    return results
```

### Step 2: Define the policies it should follow

A policy is a Python function that returns pass/fail with a reason. No LLMs. No magic.

```python
from enact.models import WorkflowContext, PolicyResult

def dont_push_to_main(context: WorkflowContext) -> PolicyResult:
    branch = context.payload.get("branch", "")
    is_main = branch in ("main", "master")
    return PolicyResult(
        policy="dont_push_to_main",
        passed=not is_main,
        reason="Branch is main/master" if is_main else "Branch is not main/master",
    )
```

Enact ships 24 built-in policies across 6 categories:

| Category | Policies | What they block |
|----------|----------|-----------------|
| **Git** | `dont_push_to_main`, `require_branch_prefix`, `max_files_per_commit`, `dont_delete_branch`, `dont_merge_to_main` | Direct pushes to main, wrong branch names, blast radius |
| **Database** | `dont_delete_row`, `dont_delete_without_where`, `dont_update_without_where`, `protect_tables`, `block_ddl` | Dangerous deletes, unscoped updates, DDL like `DROP TABLE` |
| **Filesystem** | `dont_delete_file`, `restrict_paths`, `block_extensions` | File deletions, path traversal, sensitive files (.env, .key) |
| **Access** | `contractor_cannot_write_pii`, `require_actor_role`, `require_user_role`, `dont_read_sensitive_tables`, `dont_read_sensitive_paths`, `require_clearance_for_path` | Unauthorized access, PII exposure |
| **CRM** | `dont_duplicate_contacts`, `limit_tasks_per_contact` | Duplicate records, rate limiting |
| **Time** | `within_maintenance_window`, `code_freeze_active` | Actions outside allowed hours, during code freezes |

```python
from enact.policies.git import dont_push_to_main, require_branch_prefix
from enact.policies.db import protect_tables, block_ddl
from enact.policies.time import code_freeze_active
```

### Step 3: Wire it all up and run

```python
from enact import EnactClient
from enact.connectors.github import GitHubConnector
from enact.workflows.agent_pr_workflow import agent_pr_workflow
from enact.policies.git import dont_push_to_main, require_branch_prefix

enact = EnactClient(
    systems={"github": GitHubConnector(token="ghp_...", allowed_actions=["create_branch", "create_pr"])},
    policies=[dont_push_to_main, require_branch_prefix("agent/")],
    workflows=[agent_pr_workflow],
    secret="your-64-char-secret-here...",  # or set ENACT_SECRET env var
)

result, receipt = enact.run(
    workflow="agent_pr_workflow",
    user_email="agent@company.com",
    payload={"repo": "owner/repo", "branch": "agent/fix-149"},
)
```

### Step 4: Read the receipts

Every run — PASS or BLOCK — writes a signed JSON receipt to `receipts/`:

```json
{
  "run_id": "a1b2c3d4-...",
  "workflow": "agent_pr_workflow",
  "user_email": "agent@company.com",
  "decision": "PASS",
  "policy_results": [
    {"policy": "dont_push_to_main", "passed": true, "reason": "Branch is not main/master"},
    {"policy": "require_branch_prefix", "passed": true, "reason": "Branch 'agent/fix-149' has required prefix"}
  ],
  "actions_taken": [
    {"action": "create_branch", "system": "github", "success": true},
    {"action": "create_pr", "system": "github", "success": true}
  ],
  "timestamp": "2026-02-26T03:30:00Z",
  "signature": "hmac-sha256-hex..."
}
```

Verify a receipt hasn't been tampered with:

```python
from enact.receipt import verify_signature
is_valid = verify_signature(receipt, secret="your-secret")
```

---

## How It Flows

```
agent calls enact.run()
        |
        v
+-------------------+
|  Policy Gate      |  All policies run. Any failure = BLOCK.
|  (pure Python,    |  No LLMs. Versioned in Git. Testable.
|   no LLMs)        |
+--------+----------+
    PASS |  BLOCK
         |        +-->  Receipt (decision=BLOCK, actions_taken=[])
         v
+-------------------+
|  Workflow runs    |  Enact executes the workflow against real systems.
|  against real     |  Each action produces an ActionResult.
|  systems          |
+--------+----------+
         |
         v
+-------------------+
|  Signed Receipt   |  HMAC-SHA256 signed. Captures who/what/why/
|                   |  pass-fail/what changed.
+--------+----------+
         |
         v
  (RunResult, Receipt) returned to caller
```

---

## Connectors & Allowed Actions

Think of a **workflow** as a contractor you hired to renovate your kitchen. The workflow is the actual script the AI runs—it's the step-by-step plan saying, "I'm going to tear out these cabinets, then install the new sink."

The `allowed_actions` list is the **physical toolbox** you handed that contractor before you left for work.

If you only put a screwdriver and a wrench in that toolbox (`allowed_actions=["create_branch", "create_pr"]`), and the contractor suddenly hallucinates and decides they need to demolish a load-bearing wall (`delete_repository`), they literally don't have the sledgehammer to do it. The system just throws a `PermissionError` and tells them to fuck off.

### Defense-in-Depth

You might be thinking: *"Wait, don't we have Policies (the bouncer) to stop bad shit from happening?"*

Yes, but this is **defense-in-depth**.
* **Policies** are smart, dynamic rules ("You can push code, but *not* to the `master` branch").
* **`allowed_actions`** is a dumb, brute-force lock ("You can only read data, you can never write data").

You want both. AI agents are unpredictable. If an agent goes completely rogue and tries to call a destructive method that you didn't even think to write a policy for, the `allowed_actions` whitelist acts as your absolute bottom-line safety net.

### How it works in code

Actions are just literal Python methods defined on the Connector classes (e.g., `GitHubConnector.create_branch()`).

Every connector uses an **allowlist** — you declare which actions it can perform at construction time. The very first thing every action method does is check this list. Anything not on the list raises `PermissionError` immediately, before any API call is ever made.

```python
# This connector can ONLY create branches and PRs — nothing else
gh = GitHubConnector(token="...", allowed_actions=["create_branch", "create_pr"])

# If the agent's workflow tries to do this:
gh.delete_branch(repo="owner/repo", branch="main")
# -> Raises PermissionError: Action 'delete_branch' not in allowlist
```

| System | Actions | Rollback | Idempotent |
|--------|---------|----------|------------|
| **GitHub** | `create_branch`, `create_pr`, `create_issue`, `delete_branch`, `merge_pr` | Yes (except `merge_pr`, `push_commit`) | Yes — `already_done` convention |
| **Postgres** | `select_rows`, `insert_row`, `update_row`, `delete_row` | Yes — pre-SELECT captures state | Yes |
| **Filesystem** | `read_file`, `write_file`, `delete_file`, `list_dir` | Yes — content captured before mutation | Yes |

---

## Rollback

Undo an entire run with one call:

```python
enact = EnactClient(
    systems={...},
    policies=[...],
    workflows=[...],
    rollback_enabled=True,
    secret="...",
)

result, receipt = enact.run(workflow="my_workflow", ...)

# Later — something went wrong, undo everything
rollback_result, rollback_receipt = enact.rollback(receipt.run_id)
```

`rollback()` walks the original receipt in reverse, undoes each action (deletes the branch, closes the PR, restores the DB row), skips irreversible actions (merged PRs), and writes a signed rollback receipt with decision `PASS` or `PARTIAL`.

Every connector captures pre-action state in `rollback_data` at execution time — nothing needs to be fetched retroactively.

---

## Security

Receipts are HMAC-SHA256 signed. The signature covers **every field** — tampering with any field invalidates it.

```bash
export ENACT_SECRET="$(openssl rand -hex 32)"
```

Or pass `secret=` to `EnactClient`. Minimum 32 characters. No default.

For dev/testing only: `EnactClient(..., secret="short", allow_insecure_secret=True)`

Rollback verifies the receipt signature before executing any reversal — tampered receipts can't trigger unintended operations.

---

## Run Tests

```bash
pytest tests/ -v
# 317 tests, 0 failures
```

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `ENACT_SECRET` | Yes (or pass `secret=`) | HMAC signing key. 32+ characters. |
| `GITHUB_TOKEN` | For GitHubConnector | GitHub PAT or App token |
| `ENACT_FREEZE` | Optional | Set to `1` to activate `code_freeze_active` policy |
