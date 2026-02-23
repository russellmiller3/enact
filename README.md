# Enact

**An action firewall for AI agents.**

Enact sits between your AI agent and the outside world. Every action goes through a policy gate first. If it passes, Enact executes it and returns a signed receipt. If it doesn't, nothing happens.

```python
from enact import EnactClient
from enact.connectors.hubspot import HubSpotConnector
from enact.workflows.new_lead import new_lead_workflow
from enact.policies.crm import no_duplicate_contacts

enact = EnactClient(
    systems={"hubspot": HubSpotConnector(api_key="...")},
    policies=[no_duplicate_contacts],
    workflows=[new_lead_workflow],
)

result, receipt = enact.run(
    workflow="new_lead_workflow",
    actor_email="agent@company.com",
    payload={"email": "jane@acme.com", "company": "Acme Inc"},
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

## File Structure

```
enact/
├── enact/                  # pip-installable package
│   ├── __init__.py         # exports: EnactClient, Receipt
│   ├── models.py           # data shapes for every object in a run
│   ├── client.py           # EnactClient — orchestrates the full run() loop
│   ├── policy.py           # policy engine — runs all checks, returns PolicyResult list
│   ├── receipt.py          # writes and HMAC-signs receipts
│   ├── connectors/         # system connectors (Postgres, GitHub, HubSpot)
│   ├── workflows/          # reference workflow implementations
│   └── policies/           # built-in reusable policy functions
│       ├── crm.py          # no_duplicate_contacts, limit_tasks_per_contact
│       ├── access.py       # contractor_cannot_write_pii, require_actor_role
│       ├── git.py          # no_push_to_main, max_files_per_commit
│       └── time.py         # within_maintenance_window
├── tests/
│   ├── test_policy_engine.py
│   └── test_receipt.py
├── examples/
│   └── quickstart.py       # runnable version of the quickstart above
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
| `connectors/` | Thin wrappers around vendor SDKs. Each connector exposes named actions (`create_contact`, `insert_row`, etc.) that workflows call. |
| `workflows/` | Python functions that orchestrate connector actions. Each workflow step produces an `ActionResult`. |
| `policies/` | Built-in reusable policy functions (ships with `pip install enact`). Each takes a `WorkflowContext` and returns a `PolicyResult`. |

---

## Data Flow (in code)

```
enact.run(workflow="new_lead_workflow", actor_email="agent@co.com", payload={"email": "jane@acme.com"})
  │
  ├─▶ WorkflowContext(workflow, actor_email, payload, systems)
  │
  ├─▶ policy_results = [
  │       PolicyResult(policy="no_duplicate_contacts", passed=True,  reason="..."),
  │       PolicyResult(policy="require_actor_role",    passed=True,  reason="..."),
  │   ]
  │
  ├─▶ decision = PASS → execute workflow
  │
  ├─▶ actions_taken = [
  │       ActionResult(action="create_contact", system="hubspot", success=True, output={...}),
  │       ActionResult(action="create_deal",    system="hubspot", success=True, output={...}),
  │       ActionResult(action="create_task",    system="hubspot", success=True, output={...}),
  │   ]
  │
  ├─▶ Receipt(run_id, workflow, actor_email, payload, policy_results,
  │           decision="PASS", actions_taken, timestamp, signature)
  │
  └─▶ RunResult(success=True, workflow="new_lead_workflow", output={...})
```

---

## Connectors (v1)

| System | Actions |
|--------|---------|
| Postgres | `insert_row`, `update_row`, `select_rows`, `delete_row` |
| GitHub | `create_branch`, `create_pr`, `push_commit`, `delete_branch`, `create_issue`, `merge_pr` |
| HubSpot | `create_contact`, `update_deal`, `create_task`, `get_contact` |

Postgres connector works with any Postgres-compatible host: Supabase, Neon, Railway, RDS.

---

## Built-in Policies (v1)

| File | Policy | What it blocks |
|------|--------|----------------|
| `crm.py` | `no_duplicate_contacts` | Creating a contact that already exists |
| `crm.py` | `limit_tasks_per_contact` | Too many tasks created in a time window |
| `access.py` | `contractor_cannot_write_pii` | Contractors writing PII fields |
| `access.py` | `require_actor_role` | Actors without an allowed role |
| `git.py` | `no_push_to_main` | Any direct push to main/master |
| `git.py` | `max_files_per_commit` | Commits touching too many files |
| `git.py` | `require_branch_prefix` | Agent branches not prefixed correctly |
| `time.py` | `within_maintenance_window` | Actions outside allowed time windows |

---

## Install

```bash
pip install enact
```

---

## License

MIT
