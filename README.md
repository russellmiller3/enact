# Enact

**An action firewall for AI agents.**

Enact sits between your AI agent and the outside world. Every action goes through a policy gate first. If it passes, Enact executes it and returns a signed receipt. If it doesn't, nothing happens.

```python
from enact import EnactClient
from enact.connectors.github import GitHubConnector
from enact.workflows.agent_pr_workflow import agent_pr_workflow
from enact.policies.git import no_push_to_main, require_branch_prefix

enact = EnactClient(
    systems={"github": GitHubConnector(token="...")},
    policies=[no_push_to_main, require_branch_prefix(prefix="agent/")],
    workflows=[agent_pr_workflow],
    secret="...",  # or set ENACT_SECRET env var
)

result, receipt = enact.run(
    workflow="agent_pr_workflow",
    actor_email="agent@company.com",
    payload={"repo": "owner/repo", "branch": "agent/my-feature"},
)
```

---

## How It Works

```
agent calls enact.run()
        │
        ▼
┌───────────────────┐
│  Policy Gate      │  All policies run. Any failure = BLOCK.
│  (pure Python,    │  No LLMs. Versioned in Git. Testable.
│   no LLMs)        │
└────────┬──────────┘
    PASS │  BLOCK
         │        └──▶ Receipt (decision=BLOCK, actions_taken=[])
         ▼
┌───────────────────┐
│  Workflow runs    │  Enact executes the workflow against real systems.
│  against real     │  Each action produces an ActionResult.
│  systems          │
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Signed Receipt   │  HMAC-SHA256 signed. Captures who/what/why/
│                   │  pass-fail/what changed.
└────────┬──────────┘
         │
         ▼
  RunResult returned to agent
```

---

## Three Things Enact Gives You

1. **Vetted action allowlist** — agents can only call workflows you explicitly register
2. **Deterministic policy engine** — plain Python functions, no LLMs, Git-versioned, fully testable
3. **Human-readable receipts** — every run records who, what, why, pass/fail, and what changed

---

## What Enact Can Do Right Now

### Rollback

```python
enact = EnactClient(
    systems={"github": GitHubConnector(token="...", allowed_actions=["create_branch", "create_pr", "close_pr"])},
    policies=[...],
    workflows=[my_workflow],
    rollback_enabled=True,   # premium gate — off by default
)

result, receipt = enact.run(workflow="my_workflow", ...)

# Later — undo everything that run did
rollback_result, rollback_receipt = enact.rollback(receipt.run_id)
```

`rollback(run_id)` walks the original receipt in reverse, undoes each action (delete the branch, close the PR, restore the DB row), skips irreversible actions (merged PRs, pushed commits), and produces a signed `PASS` or `PARTIAL` rollback receipt. Every connector method captures pre-action state in `rollback_data` at execution time, so nothing needs to be fetched retroactively.

**Supported:** GitHub (`create_branch`, `create_pr`, `create_issue`, `delete_branch`), Postgres (`insert_row`, `update_row`, `delete_row`)

**Irreversible (recorded but not reversed):** `merge_pr`, `push_commit`

---

### Policy enforcement
- Block agents from pushing directly to `main` or `master`
- Require branch names to match a prefix (e.g. `agent/`)
- Cap how many files an agent can touch per commit
- Restrict actions to a UTC time window (e.g. 2am–6am maintenance window), including midnight-crossing windows like 22:00–06:00
- Block contractors from writing to PII fields
- Require the actor to hold a specific role (`admin`, `engineer`, etc.)
- Prevent duplicate contacts from being created in HubSpot (live lookup before the workflow runs)
- Rate-limit how many tasks an agent creates per contact within a rolling time window

### GitHub operations (via `GitHubConnector`)
- Create a branch
- Open a pull request
- Create an issue
- Delete a branch
- Merge a pull request

Every method is allowlisted at construction time — `GitHubConnector(token=..., allowlist=["create_branch", "create_pr"])` means the connector will refuse to call any method not on the list, even if the workflow tries.

**Idempotent by default.** Every method checks whether the desired state already exists before acting. If an agent retries a workflow (network blip, crash recovery), it won't create duplicate branches, PRs, or issues. The output includes `already_done` — `False` for fresh actions, a descriptive string (`"created"`, `"deleted"`, `"merged"`) when the action was already performed.

### Built-in workflows
- **`agent_pr_workflow`** — creates a feature branch then opens a PR; aborts cleanly if branch creation fails so you never get a PR pointing at a non-existent branch
- **`db_safe_insert`** — checks for a duplicate row before inserting; returns an explanatory failure instead of letting the database raise a constraint violation

### Receipts
Every run — pass or block — produces an HMAC-SHA256 signed JSON receipt written to `receipts/`. It captures: who ran what, the full payload, every policy result with its reason, the final decision, and a timestamp. `verify_signature()` lets you prove a receipt hasn't been tampered with after the fact.

---

## File Structure

```
enact/
├── enact/                  # pip-installable package
│   ├── __init__.py         # exports: EnactClient, all models
│   ├── models.py           # data shapes for every object in a run
│   ├── client.py           # EnactClient — orchestrates run() + rollback()
│   ├── policy.py           # policy engine — runs all checks, returns PolicyResult list
│   ├── receipt.py          # builds, HMAC-signs, verifies, writes, and loads receipts
│   ├── rollback.py         # execute_rollback_action() — dispatch logic for reversal
│   ├── connectors/
│   │   ├── github.py       # GitHub: create_branch, create_pr, create_issue, delete_branch, merge_pr + rollback actions
│   │   └── postgres.py     # Postgres: select_rows, insert_row, update_row, delete_row
│   ├── workflows/
│   │   ├── agent_pr_workflow.py   # create branch → open PR (never to main)
│   │   └── db_safe_insert.py      # check constraints → insert row
│   └── policies/
│       ├── git.py          # no_push_to_main, max_files_per_commit, require_branch_prefix
│       ├── crm.py          # no_duplicate_contacts, limit_tasks_per_contact
│       ├── access.py       # contractor_cannot_write_pii, require_actor_role
│       └── time.py         # within_maintenance_window
├── tests/
│   ├── test_policy_engine.py
│   ├── test_receipt.py
│   ├── test_client.py
│   ├── test_github.py
│   ├── test_postgres.py
│   ├── test_rollback.py
│   ├── test_git_policies.py
│   ├── test_policies.py
│   └── test_workflows.py
├── examples/
│   ├── quickstart.py       # runnable demo — runs PASS then BLOCK, prints receipt
│   ├── demo.py             # 3-act demo: BLOCK, PASS, and ROLLBACK (no credentials needed)
│   ├── demo.cast           # terminal recording (asciinema format) for landing page embed
│   └── record_demo.py      # regenerates demo.cast from demo.py output
├── receipts/               # auto-created at runtime, gitignored
└── pyproject.toml          # PyPI config
```

### What each file does

| File | Job |
|------|-----|
| `models.py` | Defines data shapes. `WorkflowContext` (inputs), `PolicyResult` (one policy check), `ActionResult` (one workflow action, includes `rollback_data`), `Receipt` (full signed run record), `RunResult` (what the agent gets back). |
| `client.py` | The main entry point. `EnactClient.run()` builds context, runs policies, executes the workflow if PASS, writes the receipt, returns `RunResult`. `EnactClient.rollback(run_id)` reverses a prior run. |
| `policy.py` | Runs every registered policy against `WorkflowContext`. Returns `list[PolicyResult]`. Never bails early — always runs all checks. |
| `receipt.py` | Takes policy results + action results, builds a `Receipt`, signs it with HMAC-SHA256, writes it to `receipts/`. `load_receipt(run_id)` reads one back for rollback. |
| `rollback.py` | `execute_rollback_action()` — dispatches a single rollback step to the right connector. Classifies actions as reversible, irreversible, or read-only. |
| `connectors/` | Thin wrappers around vendor SDKs. Each connector exposes named actions (`create_branch`, `insert_row`, etc.) that workflows call. Every mutating action captures pre-action state in `rollback_data`. |
| `workflows/` | Python functions that orchestrate connector actions. Each workflow step produces an `ActionResult`. |
| `policies/` | Built-in reusable policy functions (ships with `pip install enact`). Each takes a `WorkflowContext` and returns a `PolicyResult`. |

---

## Data Flow (in code)

```
enact.run(workflow="agent_pr_workflow", actor_email="agent@co.com", payload={"repo": "owner/repo", "branch": "agent/fix"})
  │
  ├─▶ WorkflowContext(workflow, actor_email, payload, systems)
  │
  ├─▶ policy_results = [
  │       PolicyResult(policy="no_push_to_main",      passed=True, reason="Branch is not main/master"),
  │       PolicyResult(policy="require_branch_prefix", passed=True, reason="Branch 'agent/fix' has required prefix"),
  │   ]
  │
  ├─▶ decision = PASS → execute workflow
  │
  ├─▶ actions_taken = [
  │       ActionResult(action="create_branch", system="github", success=True, output={"branch": "agent/fix", "already_done": False}),
  │       ActionResult(action="create_pr",     system="github", success=True, output={"pr_number": 42, "url": "...", "already_done": False}),
  │   ]
  │
  ├─▶ Receipt(run_id, workflow, actor_email, payload, policy_results,
  │           decision="PASS", actions_taken, timestamp, signature)
  │
  └─▶ RunResult(success=True, workflow="agent_pr_workflow", output={...})
```

---

## Connectors

| System | Actions | Status |
|--------|---------|--------|
| GitHub | `create_branch`, `create_pr`, `push_commit`, `delete_branch`, `create_issue`, `merge_pr` | ✅ v0.1 |
| Postgres | `select_rows`, `insert_row`, `update_row`, `delete_row` | ✅ v0.2 |

GitHub connector works with any repo accessible via a personal access token or GitHub App.

Postgres connector works with any Postgres-compatible host: Supabase, Neon, Railway, AWS RDS. Pass a standard libpq DSN: `"postgresql://user:pass@host:5432/dbname"`.

---

## Built-in Policies (v0.1)

| File | Policy | What it blocks |
|------|--------|----------------|
| `git.py` | `no_push_to_main` | Any direct push to main/master |
| `git.py` | `max_files_per_commit` | Commits touching too many files (blast radius) |
| `git.py` | `require_branch_prefix` | Agent branches not prefixed correctly |
| `crm.py` | `no_duplicate_contacts` | Creating a contact that already exists |
| `crm.py` | `limit_tasks_per_contact` | Too many tasks created in a time window |
| `access.py` | `contractor_cannot_write_pii` | Contractors writing PII fields |
| `access.py` | `require_actor_role` | Actors without an allowed role |
| `time.py` | `within_maintenance_window` | Actions outside allowed UTC time windows |

---

## Quickstart

```bash
git clone https://github.com/russellmiller3/enact
cd enact
pip install -e ".[dev]"
python examples/quickstart.py
```

### See the full demo (no credentials needed)

```bash
python examples/demo.py
```

Three scenarios in ~10 seconds: an agent blocked from pushing to main (the Kiro pattern), a normal PR workflow, and a database wipe rolled back in one command (the Replit pattern). Uses in-memory connectors — same rollback code path as production.

---

## Run Tests

```bash
pytest tests/ -v
# 181 tests, 0 failures
```

---

## Security

Receipts are HMAC-SHA256 signed. The signature covers **every field** — workflow, actor, decision, payload, policy results, and actions taken. Any tampered field invalidates the signature.

**Setting your secret** (required):
```bash
export ENACT_SECRET="$(openssl rand -hex 32)"
```
Or pass `secret=` directly to `EnactClient`. Minimum 32 characters. There is no default.

For rollback, `rollback()` verifies the receipt signature before executing any reversal actions, preventing tampered receipts from triggering unintended operations.

For development and testing only:
```python
EnactClient(..., secret="short", allow_insecure_secret=True)
```

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `ENACT_SECRET` | Yes — or pass `secret=` directly | HMAC signing key for receipts. Minimum 32 characters. |
| `GITHUB_TOKEN` | For GitHubConnector | GitHub PAT or App token |

---

## License

[Elastic License 2.0 (ELv2)](./LICENSE)

Free to use, modify, and redistribute. You may **not** offer Enact as a hosted
or managed service, nor sell or resell the software itself as a product.
See [LICENSE](./LICENSE) for full terms.
