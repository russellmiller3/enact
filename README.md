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
│   ├── client.py           # EnactClient — orchestrates the full run() loop
│   ├── policy.py           # policy engine — runs all checks, returns PolicyResult list
│   ├── receipt.py          # builds, HMAC-signs, verifies, and writes receipts
│   ├── connectors/
│   │   ├── github.py       # GitHub: create_branch, create_pr, create_issue, delete_branch, merge_pr
│   │   └── postgres.py     # Postgres: insert_row, update_row, select_rows, delete_row (planned v0.2)
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
│   ├── test_git_policies.py
│   ├── test_policies.py
│   └── test_workflows.py
├── examples/
│   └── quickstart.py       # runnable demo — runs PASS then BLOCK, prints receipt
├── receipts/               # auto-created at runtime, gitignored
└── pyproject.toml          # PyPI config
```

### What each file does

| File | Job |
|------|-----|
| `models.py` | Defines data shapes. `WorkflowContext` (inputs), `PolicyResult` (one policy check), `ActionResult` (one workflow action), `Receipt` (full signed run record), `RunResult` (what the agent gets back). |
| `client.py` | The main entry point. `EnactClient.run()` builds context, runs policies, executes the workflow if PASS, writes the receipt, returns `RunResult`. |
| `policy.py` | Runs every registered policy against `WorkflowContext`. Returns `list[PolicyResult]`. Never bails early — always runs all checks. |
| `receipt.py` | Takes policy results + action results, builds a `Receipt`, signs it with HMAC-SHA256, writes it to `receipts/`. |
| `connectors/` | Thin wrappers around vendor SDKs. Each connector exposes named actions (`create_branch`, `insert_row`, etc.) that workflows call. |
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
  │       ActionResult(action="create_branch", system="github", success=True, output={"branch": "agent/fix"}),
  │       ActionResult(action="create_pr",     system="github", success=True, output={"pr_number": 42, "url": "..."}),
  │   ]
  │
  ├─▶ Receipt(run_id, workflow, actor_email, payload, policy_results,
  │           decision="PASS", actions_taken, timestamp, signature)
  │
  └─▶ RunResult(success=True, workflow="agent_pr_workflow", output={...})
```

---

## Connectors (v0.1)

| System | Actions | Status |
|--------|---------|--------|
| GitHub | `create_branch`, `create_pr`, `push_commit`, `delete_branch`, `create_issue`, `merge_pr` | ✅ v0.1 |
| Postgres | `insert_row`, `update_row`, `select_rows`, `delete_row` | 🔜 v0.2 |
| HubSpot | `create_contact`, `update_deal`, `create_task`, `get_contact` | 🔜 v0.2 |

GitHub connector works with any repo accessible via a personal access token or GitHub App.

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

---

## Run Tests

```bash
pytest tests/ -v
# 96 tests, 0 failures
```

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENACT_SECRET` | `enact-default-secret` | HMAC signing key for receipts. Override in production. |
| `GITHUB_TOKEN` | — | GitHub PAT for GitHubConnector |

---

## License

MIT
