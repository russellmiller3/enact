# Enact — Build Spec

> Source of truth: `Enact Landing Page Best.html`
> Goal: Ship OSS MVP → get GitHub traction → convert to Cloud at $299/mo

---

## What Enact Is

An action firewall for AI agents. Three things:

1. **Vetted action allowlist** — agents can only call what you explicitly permit
2. **Deterministic policy engine** — Python functions, no LLMs, versioned in Git, testable
3. **Human-readable receipts** — every run returns who/what/why/pass/fail/what changed

Single call from your agent:
```python
result, receipt = enact.run(
    workflow="new_lead_workflow",
    actor_email="agent@company.com",
    payload={"email": "jane@acme.com", "company": "Acme Inc"},
)
```

---

## What We Have (Reuse)

| File | Status | Reuse plan |
|------|--------|-----------|
| `backend/config/policies.py` | ✅ Working | Generalize → Enact policy engine |
| `backend/agents/policy.py` | ✅ Working | Port core logic → `EnactClient.run()` |
| `backend/receipts.py` | ✅ Working | Port + add HMAC signing |
| `backend/models.py` | ✅ Working | Refactor for Enact data model |
| `backend/server.py` | ✅ Working | Reuse for Cloud API layer |
| `backend/tests/test_policy_agent.py` | ✅ Working | Expand for Enact |
| `backend/agents/notify.py` | ⚠️ Partial | Pattern reusable for Cloud alerting |
| `backend/workflow.py` | ⚠️ Partial | Orchestrator pattern reusable |

**Deleted (Visa-specific):**
- `agents/discovery.py`, `agents/intake.py`, `agents/provision.py`
- `config/datasets.json`, `config/users.json`
- All frontend prototypes, plans/, screenshots

---

## MVP Scope

**Target:** `pip install enact` works, README example runs in 5 minutes, GitHub-starable.

### Connectors (v1)
- **Postgres** — via `psycopg2`. Works with Supabase, Neon, Railway, RDS — any Postgres-compatible host
- **GitHub** — via `PyGithub`. Coding agents are the most common AI agents; this resonates immediately with engineers
- **HubSpot** — via `hubspot-api-client`. Primary RevOps use case on landing page; needs sandbox to test
- Salesforce → v2

### Canonical Actions (v1)
| System | Actions |
|--------|---------|
| Postgres | `insert_row`, `update_row`, `select_rows`, `delete_row` |
| GitHub | `create_branch`, `create_pr`, `push_commit`, `delete_branch`, `create_issue`, `merge_pr` |
| HubSpot | `create_contact`, `update_deal`, `create_task`, `get_contact` |

### Reference Workflows (v1)
- `db_safe_insert` — Postgres: check constraints → insert row → receipt
- `agent_pr_workflow` — GitHub: create branch → push → open PR (never to main directly)
- `new_lead_workflow` — HubSpot: create contact → create deal → create task

### Policy Engine (v1)
Port and generalize from `config/policies.py`. Policies are plain Python functions:
```python
def no_duplicate_contacts(context):
    existing = context.systems["hubspot"].get_contact(context.payload["email"])
    return PolicyResult(
        policy="no_duplicate_contacts",
        passed=existing is None,
        reason=f"Contact {context.payload['email']} already exists" if existing else "No duplicate found"
    )
```

Built-in policies to ship:
- `no_duplicate_contacts()`
- `contractor_cannot_write_pii()`
- `limit_tasks_per_contact(max_tasks, window_days)`
- `within_maintenance_window(start_utc, end_utc)`
- `require_actor_role(allowed_roles)`

### Receipt Writer (v1)
Port from `receipts.py` + add:
- HMAC-SHA256 signing (makes "audit-trail ready" claim true)
- Return as structured dict (not just text file)
- Write to `receipts/` directory (local, OSS)

### EnactClient (v1)
```python
class EnactClient:
    def __init__(self, systems, policies, workflows): ...
    def run(self, workflow, actor_email, payload) -> tuple[dict, Receipt]: ...
```

---

## Repo Structure (Target)

```
enact/
├── enact/                    # The pip-installable package
│   ├── __init__.py           # Exports: EnactClient, Receipt
│   ├── client.py             # EnactClient — main entry point
│   ├── policy.py             # Policy engine (ported from agents/policy.py)
│   ├── receipt.py            # Receipt writer (ported from receipts.py)
│   ├── models.py             # PolicyResult, Receipt, RunResult
│   ├── connectors/
│   │   ├── __init__.py
│   │   ├── hubspot.py        # HubSpot connector (hubspot-api-client)
│   │   └── postgres.py       # Postgres connector (psycopg2)
│   └── workflows/
│       ├── __init__.py
│       ├── new_lead.py       # new_lead_workflow reference impl
│       └── db_insert.py      # db_insert_workflow reference impl
├── policies/                 # Built-in policy functions
│   ├── __init__.py
│   ├── crm.py                # no_duplicate_contacts, limit_tasks_per_contact
│   ├── access.py             # contractor_cannot_write_pii, require_actor_role
│   └── time.py               # within_maintenance_window
├── tests/
│   ├── test_policy_engine.py # Port + expand from test_policy_agent.py
│   ├── test_receipt.py
│   ├── test_hubspot.py       # Mock HubSpot API
│   └── test_postgres.py      # Test with local PG
├── receipts/                 # Auto-generated per run (gitignored)
├── examples/
│   └── quickstart.py         # Matches landing page exactly
├── README.md                 # Matches landing page quickstart section
├── pyproject.toml            # For PyPI publish
└── SPEC.md                   # This file
```

---

## Build Order

### Phase 1 — Core SDK (no external deps, fully testable with mocks)
1. `enact/models.py` — `PolicyResult`, `Receipt`, `RunResult`, `WorkflowContext`
2. `enact/policy.py` — generalize from `backend/agents/policy.py`
3. `enact/receipt.py` — port from `backend/receipts.py` + HMAC signing
4. `enact/client.py` — `EnactClient.__init__` + `run()`
5. Tests for policy engine + receipt writer

### Phase 2 — Postgres Connector
6. `enact/connectors/postgres.py` — `insert_row`, `update_row`, `select_rows`, `delete_row`
7. `enact/workflows/db_safe_insert.py` — reference workflow
8. Tests (local Postgres or Docker)
9. Note in README: works with Supabase, Neon, Railway, RDS

### Phase 3 — GitHub Connector
10. `enact/connectors/github.py` — `create_branch`, `create_pr`, `push_commit`, `delete_branch`, `create_issue`, `merge_pr`
11. `enact/workflows/agent_pr_workflow.py` — reference workflow
12. `policies/git.py` — `no_push_to_main()`, `no_push_during_deploy_freeze()`, `max_files_per_commit(n)`
13. Tests with mocked `PyGithub`

### Phase 4 — Policies + HubSpot
14. `policies/crm.py` — `no_duplicate_contacts()`, `limit_tasks_per_contact(max, window_days)`
15. `policies/access.py` — `contractor_cannot_write_pii()`, `require_actor_role(roles)`
16. `policies/time.py` — `within_maintenance_window(start_utc, end_utc)`
17. `enact/connectors/hubspot.py` — `create_contact`, `update_deal`, `create_task`, `get_contact`
18. `enact/workflows/new_lead.py` — reference workflow
19. `examples/quickstart.py` — must match landing page code exactly

### Phase 5 — Ship
20. `README.md` — mirrors landing page quickstart verbatim
21. `pyproject.toml` — PyPI config
22. `pip install enact` works end-to-end
23. GitHub repo public

---

## Cloud (Post-MVP)

Only after OSS has traction. Built on top of OSS core.

| Feature | Notes |
|---------|-------|
| Receipt storage + search UI | SQLite → Postgres, simple web UI |
| Real-time alerting | Twilio (SMS/call), PagerDuty API, Slack webhook |
| Retention + export | Configurable retention, JSON export |
| Hosted API | FastAPI — already have `server.py` as starting point |
| `enact.cloud` domain | Use as Cloud endpoint: `EnactClient(cloud_api_key="...")` |

---

## Dependencies

```toml
# OSS core
psycopg2-binary     # Postgres connector (Supabase, Neon, RDS, Railway)
PyGithub            # GitHub connector
hubspot-api-client  # HubSpot connector
pydantic>=2.0       # Models + validation
python-dotenv       # .env support

# Dev/test
pytest
pytest-asyncio
responses           # Mock HTTP for HubSpot/GitHub tests
```

Drop from Visa app: `anthropic`, `sse-starlette`, `watchfiles`, `python-jose`
Keep for Cloud layer: `fastapi`, `uvicorn`

---

## Key Decisions

**No LLMs in the decision path.** The policy engine is pure Python. This is the whole point.

**Connectors call real APIs.** Use vendor SDKs (`hubspot-api-client`, `psycopg2`). Don't reinvent HTTP clients.

**Receipts are signed.** HMAC-SHA256 with a secret key. Makes "audit-trail ready" literally true without SOC2.

**Workflows are thin.** Reference implementations show the pattern. Cloud sells the validated, red-teamed versions.

**PyPI first.** `pip install enact` must work before anything else.
