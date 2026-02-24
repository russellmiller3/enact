# Enact — Build Spec

> Source of truth: `landing_page.html`
> Goal: Ship OSS MVP → get GitHub traction → convert to Cloud at $299/mo

---

## Strategic Thesis

**Why this matters now.** Gartner forecasts 40% of enterprise apps will feature AI agents by 2026, up from <5% in 2025. 57% of organisations already have agents in production. The problem they all share: agents can do anything, and there's no enforcement layer, audit trail, or governance primitive. Enact is that layer.

**Why this is the right abstraction.** Enact sits at the *action layer*, not the model layer. Models change constantly — GPT-5, Claude, Gemini, Llama. The actions agents take (write to database, open PR, create contact, send email) are stable. Being LLM-vendor-independent isn't a feature, it's the architecture. Same with orchestration tools like Temporal — Enact is a library that composes with whatever stack the customer uses, not a competing platform.

**The business model (McAfee for agent side effects).**
- OSS core drives adoption — free to use, self-managed
- The moat is the **vetted workflow library**: pre-built, edge-case-hardened, kept current as APIs change. Customers subscribe for updates the same way they subscribed for antivirus signature updates.
- Network effect: every production error logged across all customers is a data point. More installs → more failure telemetry → better ML anomaly detection → better product. Nobody else has this dataset because nobody else sits at the action layer.
- Eventually: an ML model trained on real agent failure modes across real production systems. Predicts which workflows will fail, which policy configs are too loose, which actors are behaving anomalously.

**Build sequencing principle.** Ship 20 hardened workflows before building the ML model. Workflows are the data collection points and the reason to subscribe. The model comes after the data exists.

**The #1 industry pain point (confirmed by research).** Idempotency on retries — duplicate emails, duplicate tickets, duplicate CRM records from agent retries. Enact's saga approach (smarter connector methods that check-before-act) directly addresses this. Ship this in v0.2 as a named feature, not an implementation detail.

---

## What Enact Is

An action firewall for AI agents. Three things:

1. **Vetted action allowlist** — agents can only call what you explicitly permit
2. **Deterministic policy engine** — Python functions, no LLMs, versioned in Git, testable
3. **Human-readable receipts** — every run returns who/what/why/pass/fail/what changed

Single call from your agent:
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

**CRM (`enact/policies/crm.py`)**
- `no_duplicate_contacts()`
- `limit_tasks_per_contact(max_tasks, window_days)`

**Access (`enact/policies/access.py`)**
- `contractor_cannot_write_pii()`
- `require_actor_role(allowed_roles)`

**Time (`enact/policies/time.py`)**
- `within_maintenance_window(start_utc, end_utc)`

**Git (`enact/policies/git.py`)**
- `no_push_to_main()` — blocks any push directly to main/master
- `no_push_during_deploy_freeze(start_utc, end_utc)` — time-based block
- `max_files_per_commit(n)` — blast radius control
- `require_branch_prefix(prefix)` — e.g. agent branches must start with `agent/`

### Receipt Writer (v1)
Port from `receipts.py` + add:
- HMAC-SHA256 signing (makes "audit-trail ready" claim true)
- Return as structured dict (not just text file)
- Write to `receipts/` directory (local, OSS)

### Models (v1)

```python
class WorkflowContext(BaseModel):
    workflow: str
    actor_email: str
    payload: dict
    systems: dict           # connector instances keyed by name

class PolicyResult(BaseModel):
    policy: str
    passed: bool
    reason: str

class ActionResult(BaseModel):
    action: str             # e.g. "create_contact"
    system: str             # e.g. "hubspot"
    success: bool
    output: dict            # raw response from the connector

class Receipt(BaseModel):
    run_id: str             # UUID
    workflow: str
    actor_email: str
    payload: dict
    policy_results: list[PolicyResult]
    decision: str           # "PASS" | "BLOCK"
    actions_taken: list[ActionResult]   # empty if BLOCK
    timestamp: str          # ISO8601
    signature: str          # HMAC-SHA256 hex digest

class RunResult(BaseModel):
    success: bool
    workflow: str
    output: dict
```

### EnactClient (v1)
```python
class EnactClient:
    def __init__(self, systems, policies, workflows): ...
    def run(self, workflow, actor_email, payload) -> tuple[RunResult, Receipt]: ...
```

`run()` execution order:
1. Build `WorkflowContext` from args + registered systems
2. Run all registered policies → `list[PolicyResult]`
3. If any policy fails → `decision = BLOCK`, write receipt (`actions_taken=[]`), return `RunResult(success=False)`
4. If all pass → `decision = PASS`, execute workflow → `list[ActionResult]`
5. Write signed receipt (includes `actions_taken`)
6. Return `RunResult(success=True, output=...)`

---

## Repo Structure (Target)

```
enact/
├── enact/                    # The pip-installable package
│   ├── __init__.py           # Exports: EnactClient, Receipt
│   ├── client.py             # EnactClient — main entry point
│   ├── policy.py             # Policy engine (ported from agents/policy.py)
│   ├── receipt.py            # Receipt writer (ported from receipts.py)
│   ├── models.py             # WorkflowContext, PolicyResult, ActionResult, Receipt, RunResult
│   ├── connectors/
│   │   ├── __init__.py
│   │   ├── hubspot.py        # HubSpot connector (hubspot-api-client)
│   │   ├── postgres.py       # Postgres connector (psycopg2)
│   │   └── github.py         # GitHub connector (PyGithub)
│   ├── workflows/
│   │   ├── __init__.py
│   │   ├── new_lead.py           # new_lead_workflow reference impl
│   │   ├── db_safe_insert.py     # db_safe_insert_workflow reference impl
│   │   └── agent_pr_workflow.py  # agent_pr_workflow reference impl
│   └── policies/             # Built-in policy functions (ships with pip install enact)
│       ├── __init__.py
│       ├── crm.py            # no_duplicate_contacts, limit_tasks_per_contact
│       ├── access.py         # contractor_cannot_write_pii, require_actor_role
│       ├── git.py            # no_push_to_main, max_files_per_commit, require_branch_prefix
│       └── time.py           # within_maintenance_window
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

> **Legend:** ✅ Done · 🔜 Planned (v0.2) · ⏭️ Skipped in v0.1

### Phase 1 — Core SDK (no external deps, fully testable with mocks)
1. ✅ `enact/models.py` — `WorkflowContext`, `PolicyResult`, `ActionResult`, `Receipt`, `RunResult`
2. ✅ `enact/policy.py` — `evaluate_all()`, `all_passed()`
3. ✅ `enact/receipt.py` — `build_receipt()`, `sign_receipt()`, `verify_signature()`, `write_receipt()`
4. ✅ `enact/client.py` — `EnactClient.__init__` + `run()` (policy gate + workflow execution)
5. ✅ Tests: `test_policy_engine.py`, `test_receipt.py`, `test_client.py`

### Phase 2 — Postgres Connector
6. ⏭️ `enact/connectors/postgres.py` — skipped in v0.1; planned for v0.2
7. ✅ `enact/workflows/db_safe_insert.py` — reference workflow (Postgres connector mocked in tests)
8. ✅ Tests: `test_workflows.py`

### Phase 3 — GitHub Connector
9.  ✅ `enact/connectors/github.py` — `create_branch`, `create_pr`, `push_commit`, `delete_branch`, `create_issue`, `merge_pr`
10. ✅ `enact/workflows/agent_pr_workflow.py` — reference workflow
11. ✅ `enact/policies/git.py` — `no_push_to_main()`, `max_files_per_commit(n)`, `require_branch_prefix(prefix)`
    - ⏭️ `no_push_during_deploy_freeze()` — not implemented in v0.1
12. ✅ Tests: `test_github.py`, `test_git_policies.py`

### Phase 4 — Policies + HubSpot
13. ✅ `enact/policies/crm.py` — `no_duplicate_contacts()`, `limit_tasks_per_contact(max, window_days)`
14. ✅ `enact/policies/access.py` — `contractor_cannot_write_pii()`, `require_actor_role(roles)`
15. ✅ `enact/policies/time.py` — `within_maintenance_window(start_utc, end_utc)`
16. ⏭️ `enact/connectors/hubspot.py` — skipped in v0.1; planned for v0.2
17. ⏭️ `enact/workflows/new_lead.py` — skipped (depends on HubSpot connector)
18. ✅ Tests: `test_policies.py`

### Phase 5 — Ship
19. ✅ `examples/quickstart.py` — runnable demo using GitHub connector + git policies
20. ✅ `README.md` — synced with v0.1 implementation
21. ✅ `pyproject.toml` — PyPI config, `pip install -e ".[dev]"` works
22. ✅ `pytest tests/ -v` — 96 tests, 0 failures
23. ✅ PyPI publish — `pip install enact-sdk` live at https://pypi.org/project/enact-sdk/0.1.0/

---

## Workflow Roadmap (v0.2+)

> Based on research into most common production agent use cases (2025-2026).
> Priority = frequency of use × severity of side effects if something goes wrong.
> Each workflow ships with: implementation + edge-case handling + idempotency + tests.

### Tier 1 — Highest priority (most common + highest blast radius)

| Workflow | System | Key policies needed | Idempotency concern |
|---|---|---|---|
| `send_email_workflow` | Gmail / SMTP | `no_bulk_email_blast`, `no_email_external_domains`, `require_actor_role` | Don't send twice on retry |
| `create_support_ticket_workflow` | Jira / Zendesk | `no_duplicate_tickets`, `limit_tickets_per_hour` | Duplicate tickets on retry |
| `update_crm_record_workflow` | HubSpot / Salesforce | `no_overwrite_owner`, `require_field_validation` | Double-write on retry |
| `new_lead_workflow` | HubSpot | `no_duplicate_contacts`, `limit_tasks_per_contact` | Already partially built |
| `db_safe_update_workflow` | Postgres | `no_update_without_where_clause`, `require_row_exists` | Partial update on retry |

### Tier 2 — High value (common in coding agents + DevOps)

| Workflow | System | Key policies needed | Idempotency concern |
|---|---|---|---|
| `issue_triage_workflow` | GitHub | `no_duplicate_labels`, `require_branch_prefix` | Double-labelling on retry |
| `code_review_workflow` | GitHub | `no_review_own_pr`, `require_actor_role` | Duplicate review comments |
| `deploy_to_environment_workflow` | GitHub Actions / AWS | `no_prod_deploy_without_passing_tests`, `within_maintenance_window` | Double deploy |
| `update_feature_flag_workflow` | LaunchDarkly / custom | `require_actor_role`, `no_prod_flag_change_without_approval` | Flag toggled twice |
| `escalate_ticket_workflow` | Jira / PagerDuty | `no_duplicate_escalation`, `within_on_call_window` | Double page |

### Tier 3 — Strong enterprise demand

| Workflow | System | Key policies needed | Idempotency concern |
|---|---|---|---|
| `post_slack_message_workflow` | Slack | `no_bulk_channel_blast`, `no_dm_external_users` | Duplicate message on retry |
| `schedule_meeting_workflow` | Google Calendar / Outlook | `no_double_book`, `within_business_hours` | Double calendar invite |
| `outreach_sequence_workflow` | HubSpot / Apollo | `no_duplicate_outreach`, `limit_emails_per_contact_per_day` | Duplicate outreach |
| `update_ticket_status_workflow` | Jira / Zendesk | `no_invalid_status_transition`, `require_actor_role` | Status ping-pong |
| `db_bulk_import_workflow` | Postgres | `no_import_without_schema_validation`, `limit_rows_per_run` | Partial import on crash |

### Tier 4 — Future / emerging

| Workflow | System | Notes |
|---|---|---|
| `create_invoice_workflow` | Stripe / QuickBooks | High stakes — financial data |
| `update_dns_record_workflow` | Cloudflare / Route53 | Infra — needs careful rollback |
| `send_sms_workflow` | Twilio | Regulatory compliance angle |
| `publish_content_workflow` | CMS / social | Brand risk policies |
| `provision_cloud_resource_workflow` | AWS / GCP | Cost policies critical |

### V0.2 Feature: Idempotency (Saga Pattern)
Before building more workflows, retrofit connectors with check-before-act:
- Each connector method returns `already_existed: bool` alongside `success: bool`
- Caller supplies optional `idempotency_key` to `enact.run()` — signed into receipt
- Workflows retry-safe by default, not by accident
- Start with `agent_pr_workflow` as the reference implementation

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
