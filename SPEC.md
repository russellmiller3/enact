# Enact — Build Spec

> Source of truth: `landing_page.html`
> Goal: Ship OSS MVP → get GitHub traction → convert to Cloud at $299/mo

---

## What's Been Built (as of 2026-03-01)

**356+ tests, 0 failures. Published on PyPI as `enact-sdk` v0.4.**

### Core SDK (v0.1)
- **EnactClient** — `run()` orchestrates policy gate → workflow execution → signed receipt. `rollback(run_id)` reverses a prior run.
- **Policy engine** — `evaluate_all()` runs every registered policy against `WorkflowContext`. Never bails early. Returns `list[PolicyResult]`.
- **Receipt system** — HMAC-SHA256 signed JSON receipts. Signature covers all fields (payload, policy results, actions). Path traversal protection on `load_receipt()` / `write_receipt()`. Receipts written to `receipts/` directory.
- **Models** — `WorkflowContext`, `PolicyResult`, `ActionResult` (with `rollback_data`), `Receipt`, `RunResult`. Pydantic v2.

### Connectors (v0.1–v0.2)
| Connector | Actions | Rollback | Idempotent |
|-----------|---------|----------|------------|
| **GitHub** | `create_branch`, `create_pr`, `create_issue`, `delete_branch`, `merge_pr`, `close_pr`, `close_issue` | ✅ (except `merge_pr`, `push_commit`) | ✅ `already_done` convention |
| **Postgres** | `select_rows`, `insert_row`, `update_row`, `delete_row` | ✅ (pre-SELECT captures state) | ✅ |
| **Filesystem** | `read_file`, `write_file`, `delete_file`, `list_dir` | ✅ (content captured before mutation) | ✅ |
| **Slack** | `post_message`, `delete_message` | ✅ `post_message` → `delete_message` via `ts`; needs `chat:delete` scope | No — duplicate posts are intentional |

### Receipt Browser (v0.4)
- **`enact/ui.py`** — local receipt browser served via stdlib `http.server`, zero extra deps
- **`enact-ui` CLI** — `enact-ui [--port N] [--dir PATH] [--secret KEY]`; registered in `pyproject.toml` as entry point
- **Dark mode toggle** with `localStorage` persistence
- **Signature verification** — shows `signature_valid` per receipt when `--secret` is passed
- API endpoints: `GET /` (HTML), `GET /api/receipts` (list), `GET /api/receipts/{run_id}` (detail)

### Cloud Backend (v0.4)
- **`cloud/main.py`** — FastAPI app, lifespan startup (checks `CLOUD_SECRET` env var exists)
- **`cloud/routes/receipts.py`** — `POST /receipts` (idempotent upsert), `GET /receipts/{run_id}`
- **`cloud/routes/hitl.py`** — `POST /hitl/request`, `GET /hitl/{id}`, `GET/POST /hitl/{id}/approve`, `GET/POST /hitl/{id}/deny`, confirm page, callback webhook (fire-and-forget daemon thread), HMAC-signed approval receipt
- **`cloud/routes/badge.py`** — `GET /badge/{team_id}/{workflow}.svg` — public SVG badge (green/red/grey), `ORDER BY rowid DESC` for correct same-second ordering
- **`cloud/auth.py`** — `X-Enact-Api-Key` header; SHA-256 hash stored, raw key never persisted
- **`cloud/token.py`** — HMAC-signed approve/deny tokens; action is bound to the token (deny token can't approve)
- **`cloud/db.py`** — SQLite, `ENACT_DB_PATH` read fresh per call (test isolation via `monkeypatch.setenv`)
- **`cloud/email.py`** — `smtplib`; `ENACT_EMAIL_DRY_RUN=1` for local dev
- **`enact/cloud_client.py`** — thin HTTP client for cloud API (`push_receipt`, `request_hitl`, `get_hitl_status`, `poll_until_decided`)
- **`enact/client.py`** — added `cloud_api_key=` param, `push_receipt_to_cloud()`, `run_with_hitl()`
- **Tests:** `tests/cloud/` (conftest, test_auth, test_receipts, test_hitl, test_badge, test_hitl_receipt) + `tests/test_cloud_client.py`

### Built-in Policies (26 policies across 7 files)
| File | Policies |
|------|----------|
| `git.py` | `dont_push_to_main`, `max_files_per_commit`, `require_branch_prefix`, `dont_delete_branch`, `dont_merge_to_main` |
| `db.py` | `dont_delete_row`, `dont_delete_without_where`, `dont_update_without_where`, `protect_tables`, `block_ddl` |
| `filesystem.py` | `dont_delete_file`, `restrict_paths`, `block_extensions` |
| `access.py` | `contractor_cannot_write_pii`, `require_actor_role`, `dont_read_sensitive_tables`, `dont_read_sensitive_paths`, `require_clearance_for_path`, `require_user_role` |
| `crm.py` | `dont_duplicate_contacts`, `limit_tasks_per_contact` |
| `time.py` | `within_maintenance_window`, `code_freeze_active` |
| `slack.py` | `require_channel_allowlist`, `block_dms` |

### Workflows
- **`agent_pr_workflow`** — create branch → open PR (never to main)
- **`db_safe_insert`** — duplicate check → insert row
- **`post_slack_message`** — policy-gated Slack message with rollback via `delete_message`

### Rollback (v0.2)
- `EnactClient.rollback(run_id)` — loads receipt, verifies signature, reverses actions in reverse order
- Produces signed rollback receipt with `PASS` or `PARTIAL` decision
- Gated behind `rollback_enabled=True`

### Security (v0.2)
- Required secret (no default) — 32+ chars or `allow_insecure_secret=True` for dev
- HMAC covers ALL fields via JSON canonicalization
- Rollback verifies receipt signature before executing (TOCTOU fix)
- Receipt path traversal protection (UUID validation)

### Shipping
- `pip install enact-sdk` — [PyPI v0.3.2](https://pypi.org/project/enact-sdk/0.3.2/)
- `examples/demo.py` — 3-act zero-credential demo (BLOCK → PASS → ROLLBACK) with row-level evidence
- `examples/quickstart.py` — runnable GitHub + git policies demo
- `examples/demo.cast` — asciinema recording for landing page
- `landing_page.html` — v2 with rollback-first tabs, Replit/Kiro evidence, migration section (#migrate)

### Plans Completed
| Plan | What it delivered |
|------|-------------------|
| `2026-02-24-idempotency` | `already_done` convention on all GitHub connector methods |
| `2026-02-24-rollback` | `rollback()`, `rollback_data`, `rollback.py`, inverse actions |
| `2026-02-24-demo-and-landing-v2` | `demo.py`, competitive research in spec, landing page v2 |
| `2026-02-24-demo-evidence-and-gif` | Row-level evidence in demo output, `record_demo.py`, `.cast` file |
| `2026-02-25-filesystem-connector` | `FilesystemConnector`, filesystem policies, rollback wiring |
| `2026-02-26-policies-abac-ddl-freeze` | ABAC policies, `block_ddl`, `code_freeze_active`, `user_email` rename |
| `2026-03-01-slack-connector` | `SlackConnector`, Slack policies, `post_slack_message` workflow, rollback wiring |
| `2026-03-01-cloud-mvp` | Cloud backend (FastAPI), HITL gates, receipt storage, status badge, `cloud_client.py`, `enact/ui.py` receipt browser |

---

## Strategic Thesis

**Why this matters now.**
- Gartner: 40% of enterprise apps will feature AI agents by 2026, up from <5% in 2025
- 57% of organisations already have agents in production
- 89% have implemented observability — they know they need visibility, but observability tells you what happened *after*. Enact tells you what's allowed *before*, and proves it after. Different product, different buyer (CISO not DevOps).
- Microsoft published a formal taxonomy of agent failure modes in 2025. When Microsoft writes a whitepaper about your problem space, enterprise security teams start budgeting for it.
- Nearly 50% of YC's latest batch are AI agent companies — your early adopter base is being minted right now.
- **The viral pain is in coding agents, not CRM.** Every major AI agent disaster in 2025-2026 involves coding agents + databases: Replit (deleted production database, July 2025), Amazon Kiro (deleted EC2 systems, 13-hour AWS outage, Dec 2025), Claude Code (`rm -rf` home directory, Dec 2025). Zero CRM stories go viral. The ICP engineer's fear is their coding agent breaking production — lead with that.
- **Rollback is the unique differentiator.** No competitor has it. AgentBouncr (HN, Feb 2026) got 1 point / 3 comments with the same governance pitch. The difference: Enact has rollback — the Replit story ends differently with Enact. Lead with that.
- **Competitors are weak right now.** AgentBouncr and Nucleus both launched "Show HN" in Feb 2026 with near-zero traction. The governance layer space is hot but no one has a compelling demo. First credible demo wins the HN slot.

**Why this is the right abstraction.**
Enact sits at the *action layer*, not the model layer. Models change constantly (GPT-5, Claude, Gemini, Llama). The actions agents take (write to database, open PR, create contact, send email) are stable. LLM-vendor-independence isn't a feature — it's the architecture. Same with Temporal and other orchestration tools: Enact is a library that composes with whatever stack the customer uses, not a competing platform.

**The MCP gap.** Model Context Protocol (MCP) is the emerging standard for connecting tools to LLMs — every agent framework is adopting it. But MCP is just a protocol. It has zero governance, zero audit, zero policy enforcement. It's TCP/IP without a firewall. Enact is the firewall. This is the "built on top of MCP" story for enterprise customers.

**Why "we write the workflows for you" is the real moat.**
Writing correct, edge-case-hardened connector code is hard. API docs are inconsistent, rate limits change, auth flows differ, idempotency is subtle. The real value isn't the policy engine — it's that customers don't have to figure out janky MCPs or write their own workflows from scratch. This is Zapier's core value prop, applied to agent governance. Every vetted workflow Enact ships is one less thing a customer has to build, test, and maintain.

**The full positioning: Zapier + Okta + Splunk for AI agents.**
- **Zapier**: pre-built integrations, don't write connector code yourself
- **Okta**: access control and policy enforcement per actor/role
- **Splunk**: audit trail, anomaly detection, compliance reporting
Each of those is a billion-dollar company. Enact is the one product that does all three, purpose-built for the agent action layer.

**The business model (McAfee for agent side effects).**
- OSS core drives adoption — free to use, self-managed, no lock-in concern
- Moat is the **vetted workflow library**: pre-built, edge-case-hardened, kept current as APIs change. Customers subscribe for updates the same way they subscribed for antivirus signatures.
- Network effect: every production error across all customers is a data point. More installs → more failure telemetry → better anomaly detection → better product. Nobody else has this dataset because nobody else sits at the action layer.
- Eventually: ML model trained on real agent failure modes. Predicts which workflows will fail, which policy configs are too loose, which actors are behaving anomalously.

**Build sequencing principle.** Ship 20 hardened workflows before building the ML model. Workflows are the data collection points and the reason to subscribe. The model comes after the data exists.

**Demo before connectors.** The most important next artifact is `examples/demo.py` — a self-contained, zero-credential 3-act script showing the Kiro scenario (BLOCK), normal operation (PASS + receipt), and the Replit scenario (PASS + rollback). This is what lands on HN and converts GitHub stars to trials. HubSpot connector comes after the demo is sharp.

**The #1 industry pain point (confirmed by research).** Idempotency on retries — duplicate emails, duplicate tickets, duplicate CRM records. Enact's saga approach (connector methods that check-before-act) directly addresses this. Ship in v0.2 as a named feature, not an implementation detail.

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
from enact.policies.crm import dont_duplicate_contacts

enact = EnactClient(
    systems={"hubspot": HubSpotConnector(api_key="...")},
    policies=[dont_duplicate_contacts],
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
def dont_duplicate_contacts(context):
    existing = context.systems["hubspot"].get_contact(context.payload["email"])
    return PolicyResult(
        policy="dont_duplicate_contacts",
        passed=existing is None,
        reason=f"Contact {context.payload['email']} already exists" if existing else "No duplicate found"
    )
```

Built-in policies to ship:

**CRM (`enact/policies/crm.py`)**
- `dont_duplicate_contacts()`
- `limit_tasks_per_contact(max_tasks, window_days)`

**Access (`enact/policies/access.py`)**
- `contractor_cannot_write_pii()`
- `require_actor_role(allowed_roles)`

**Time (`enact/policies/time.py`)**
- `within_maintenance_window(start_utc, end_utc)`

**Git (`enact/policies/git.py`)**
- `dont_push_to_main()` — blocks any push directly to main/master
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
│       ├── crm.py            # dont_duplicate_contacts, limit_tasks_per_contact
│       ├── access.py         # contractor_cannot_write_pii, require_actor_role
│       ├── git.py            # dont_push_to_main, max_files_per_commit, require_branch_prefix, dont_delete_branch, dont_merge_to_main
│       ├── db.py             # dont_delete_row, dont_delete_without_where, dont_update_without_where, protect_tables
│       ├── filesystem.py     # dont_delete_file, restrict_paths, block_extensions
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
6. ✅ `enact/connectors/postgres.py` — `select_rows`, `insert_row`, `update_row`, `delete_row`; psycopg2 with Identifier/Placeholder SQL safety; follows `already_done` convention
7. ✅ `enact/workflows/db_safe_insert.py` — reference workflow (Postgres connector mocked in tests)
8. ✅ Tests: `test_workflows.py`, `test_postgres.py` (21 tests)

### Phase 3 — GitHub Connector
9.  ✅ `enact/connectors/github.py` — `create_branch`, `create_pr`, `push_commit`, `delete_branch`, `create_issue`, `merge_pr`
10. ✅ `enact/workflows/agent_pr_workflow.py` — reference workflow
11. ✅ `enact/policies/git.py` — `dont_push_to_main()`, `max_files_per_commit(n)`, `require_branch_prefix(prefix)`, `dont_delete_branch()`, `dont_merge_to_main()`
    - ⏭️ `no_push_during_deploy_freeze()` — not implemented in v0.1
12. ✅ Tests: `test_github.py`, `test_git_policies.py`

### Phase 4 — Policies + HubSpot
13. ✅ `enact/policies/crm.py` — `dont_duplicate_contacts()`, `limit_tasks_per_contact(max, window_days)`
14. ✅ `enact/policies/access.py` — `contractor_cannot_write_pii()`, `require_actor_role(roles)`
15. ✅ `enact/policies/time.py` — `within_maintenance_window(start_utc, end_utc)`
15b. ✅ `examples/demo.py` — 3-act self-contained demo (zero credentials). DemoGitHubConnector + DemoPostgresConnector inline. Shows BLOCK → PASS → ROLLBACK narrative.
16. ⏭️ `enact/connectors/hubspot.py` — skipped in v0.1; planned for v0.2
17. ⏭️ `enact/workflows/new_lead.py` — skipped (depends on HubSpot connector)
18. ✅ Tests: `test_policies.py`

### Phase 5 — Ship
19. ✅ `examples/quickstart.py` — runnable demo using GitHub connector + git policies
20. ✅ `README.md` — synced with v0.1 implementation
21. ✅ `pyproject.toml` — PyPI config, `pip install -e ".[dev]"` works
22. ✅ `pytest tests/ -v` — 123 tests, 0 failures
23. ✅ PyPI publish — `pip install enact-sdk` live at https://pypi.org/project/enact-sdk/0.1.0/

### Phase 6 — Security Hardening + DB + Filesystem Policies (v0.2)
24. ✅ `enact/receipt.py` — path traversal protection (`_validate_run_id()`); HMAC now covers ALL fields via `_build_signature_message()`
25. ✅ `enact/client.py` — required secret (no default); `allow_insecure_secret` escape hatch; rollback verifies signature before executing (TOCTOU fix)
26. ✅ `enact/rollback.py` — `execute_rollback_action()` dispatch for GitHub + Postgres + Filesystem
27. ✅ `enact/policies/db.py` — `dont_delete_row()`, `dont_delete_without_where()`, `dont_update_without_where()`, `protect_tables(list)`
28. ✅ `enact/policies/git.py` — added `dont_delete_branch()`, `dont_merge_to_main()`
29. ✅ `enact/connectors/filesystem.py` — `read_file`, `write_file`, `delete_file`, `list_dir`; base_dir path confinement; rollback_data on mutating actions
30. ✅ `enact/policies/filesystem.py` — `dont_delete_file()`, `restrict_paths(list)`, `block_extensions(list)`
31. ✅ Tests: 317 tests total, 0 failures
32. ✅ PyPI publish — `enact-sdk 0.2.0` live

### Phase 7 — Slack Connector + ABAC Policies (v0.3)
33. ✅ `enact/connectors/slack.py` — `post_message`, `delete_message`; rollback via `ts`; `already_done` convention
34. ✅ `enact/policies/slack.py` — `require_channel_allowlist()`, `block_dms()`
35. ✅ `enact/workflows/post_slack_message.py` — policy-gated Slack message with rollback wiring
36. ✅ `enact/policies/access.py` — added `dont_read_sensitive_tables()`, `dont_read_sensitive_paths()`, `require_clearance_for_path()`, `require_user_role()`
37. ✅ `enact/policies/time.py` — added `code_freeze_active()`
38. ✅ `enact/policies/db.py` — added `block_ddl()`
39. ✅ Tests: 348 tests total, 0 failures
40. ✅ PyPI publish — `enact-sdk 0.3.2` live

### Phase 8 — Receipt Browser + Cloud MVP (v0.4)
41. ✅ `enact/ui.py` — local receipt browser (stdlib only, no extra deps); dark mode; signature verification
42. ✅ `enact-ui` CLI entry point in `pyproject.toml`
43. ✅ `cloud/` package — FastAPI backend: receipt storage (SQLite, idempotent upsert), HITL gates (HMAC-signed tokens, email approval, callback webhook), status badge SVG
44. ✅ `cloud/auth.py` — API key auth (SHA-256 hash, raw key never stored)
45. ✅ `cloud/token.py` — HMAC-signed approve/deny tokens (action bound to token)
46. ✅ `enact/cloud_client.py` — thin HTTP client for cloud API (stdlib urllib only)
47. ✅ `enact/client.py` — `cloud_api_key=` param, `push_receipt_to_cloud()`, `run_with_hitl()`
48. ✅ Tests: 356+ tests total (SDK + cloud), 0 failures
49. ✅ PyPI publish — `enact-sdk 0.4` live

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
| `new_lead_workflow` | HubSpot | `dont_duplicate_contacts`, `limit_tasks_per_contact` | Already partially built |
| `db_safe_update_workflow` | Postgres | `dont_update_without_where_clause`, `require_row_exists` | Partial update on retry |

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

### V0.2 Feature: Idempotency ✅ SHIPPED
Every mutating connector method now checks whether the desired state already exists before acting. Convention:
- `output["already_done"]` = `False` for fresh actions
- `output["already_done"]` = descriptive string (`"created"`, `"deleted"`, `"merged"`) for idempotent noops
- Callers check `if result.output.get("already_done"):` — strings are truthy, `False` is falsy
- All 5 GitHub connector methods have idempotency guards + tests (123 tests total)
- Convention documented in `CLAUDE.md` and `enact/connectors/github.py` docstring — all future connectors MUST follow this pattern

---

## Premium Capabilities Roadmap

Ordered by price-increase potential. Each unlocks a new buyer or a higher price tier.

### Tier A — Ship with Cloud v1 (justify $299/mo)
| Capability | What it is | Why it commands price |
|---|---|---|
| **Receipt storage + search UI** | Web UI for browsing all runs, filtering by agent/workflow/decision | Replaces custom logging infrastructure |
| **Real-time alerting** | Push to Slack/PagerDuty/SMS when agent does something unexpected | On-call teams will pay for this immediately |
| **Compliance export** | One-click SOC2 evidence package, GDPR processing records, ISO27001 audit logs — auto-generated from receipt data | Compliance consultants charge $50K for this; you automate it |

### Tier B — High-value differentiators (justify $999+/mo enterprise)
| Capability | What it is | Why it commands price |
|---|---|---|
| **Human-in-the-loop gates** | Policy that pauses a workflow and sends a Slack/email "approve this?" — auto-blocks if no response within N minutes | Table stakes for regulated industries; nobody else has this for agents |
| **Rollback** ✅ | `EnactClient.rollback(run_id)` — reverses all successful actions from a run in reverse order, using `rollback_data` captured at action time. Gated behind `rollback_enabled=True`. Produces a signed `PASS`/`PARTIAL` receipt. GitHub and Postgres fully supported. | Enterprise will pay significantly for "undo" — only possible because every action is receipted |
| **Vertical policy packs** | Pre-built policy bundles by industry: Healthcare (HIPAA), Finance (SOX/blackout windows), HR (GDPR/PII), Legal (privilege) | Compliance teams don't buy tools; they buy "someone already thought about the regulations" — commands 3-5x price |
| **Multi-agent arbitration** | When two agents try to modify the same resource simultaneously, Enact arbitrates — first gets a soft lock, second blocks with "resource locked by agent-A run-xyz" in receipt | Nobody else is solving multi-agent conflicts; unique differentiator |

### Tier C — ML / data network effects (long-term moat)
| Capability | What it is | Why it commands price |
|---|---|---|
| **Anomaly detection** | Rule-based first (3-sigma on rolling window per agent): "this agent called delete_row 400 times in 60 seconds" → immediate alert. ML model later. | The dataset nobody else has — real agent failure modes across real production |
| **Failure prediction** | ML model predicts which workflow configs are likely to fail based on patterns across all customers | Only possible with network scale — becomes more valuable as install base grows |
| **Policy linter** | CLI that checks your policy config against known misconfigurations — like ESLint for agent governance | Shifts left; catches problems before they reach prod |

---

## How to Get Early Users

### Channel 1 — Hacker News (highest ROI, do first)
Post "Show HN: Enact — an action firewall for AI agents" when you have a clean demo.
- Target: engineers who have already been burned by an agent doing something wrong
- What makes it land: concrete horror story in the opening line ("our agent created 847 duplicate Jira tickets")
- The comments will tell you exactly what the market wants
- **Timing: now.** Competitors (AgentBouncr, Nucleus) just launched with near-zero traction. The window is open. `examples/demo.py` is the clean demo — ship it and post.
- **Hook:** "Our demo shows the Replit database deletion with a happy ending — `enact.rollback(run_id)` restores every deleted row. Built with zero LLMs in the decision path."

### Channel 2 — YC companies (warm, fast-moving)
Nearly 50% of the current YC batch are agent companies. They're shipping fast, hitting edge cases, and have budget. Find them via:
- `ycombinator.com/companies` filter by "AI" + recent batch
- Cold email founders directly: "You're building agents. Here's the thing that will bite you."
- Offer to write their first Enact workflow free in exchange for a case study

### Channel 3 — Agent framework communities (where builders are)
- **LangChain** Discord + GitHub discussions — post "how Enact works with LangChain agents"
- **CrewAI** and **AutoGen** communities — same angle
- **Anthropic developer Discord** — Claude agent builders are exactly your audience
- Write one integration guide for each (LangChain in one afternoon, drives long-tail search)

### Channel 4 — Content (compounds over time)
Each of these is also a Google-indexed landing page:
- "How to prevent your AI agent from sending duplicate emails" → points to `send_email_workflow`
- "AI agent audit trail: how to prove your agent only did what it was supposed to" → points to receipt system
- "Why MCP needs a firewall" → explains the governance gap, positions Enact as the answer
- Post on dev.to, Hashnode, personal blog — engineers find these via search when they hit the problem

### Channel 5 — ProductHunt (awareness spike)
Launch when you have 5+ workflows and a working demo. Not the primary channel but generates a one-day spike and backlinks. Time for a Monday launch (highest traffic day).

### Channel 6 — Direct enterprise outreach (for first paying customers)
Target: companies that have publicly announced AI agent deployments (press releases, engineering blogs).
- They already have the problem, already have budget, already have a champion internally
- Message: "You announced your agent deployment in [month]. Here's the audit trail and governance layer you'll need when compliance asks."
- One enterprise customer at $299/mo pays for a month of your time.

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

---

## Security Hardening (v0.1.1)

Security audit completed 2026-02-25. Four vulnerabilities fixed, 181 tests passing.

### Receipt Integrity
- **HMAC covers all fields.** Signature now includes payload, policy_results, and actions_taken via JSON canonicalization (sorted keys, compact separators). Tampering with any field invalidates the signature.
- **No default secret.** `EnactClient` requires an explicit `secret` parameter or `ENACT_SECRET` env var. No fallback to a hardcoded value. Secrets must be 32+ characters unless `allow_insecure_secret=True` (dev/testing only).
- **Rollback verifies signatures.** `rollback()` calls `verify_signature()` immediately after loading a receipt, before executing any actions. Prevents TOCTOU attacks via tampered receipt files.

### Path Traversal Protection
- `write_receipt()` and `load_receipt()` validate that `run_id` matches UUID v4 format (`^[0-9a-f]{8}-...`). Rejects `../`, `..\\`, embedded slashes, and any non-UUID input.
- Belt-and-suspenders: `write_receipt()` also resolves the final path and verifies it stays inside the target directory.

### What's Not Fixed (Backlog)
- **Postgres table allowlist** (Risk #5) — `allowed_tables` parameter not yet added; low priority since connector already requires explicit `allowed_actions`
- **Rate limiting** (Risk #6) — belongs in the application layer, not the SDK
- **Payload size validation** (Risk #7) — caller controls payloads; not untrusted input in typical SDK usage
- **Broad exception handling** (Risk #8) — GitHub connector `except Exception` blocks; minor cleanup

### For Production Deployments
1. Set `ENACT_SECRET` to a strong 64+ character random string
2. Never use `allow_insecure_secret=True` outside of tests
3. Store receipts on append-only storage if compliance requires tamper-proof audit trails
4. Monitor for failed signature verifications (indicates tampering attempts)

---

**Generating the terminal recording (asciinema .cast).**
`examples/record_demo.py` captures `demo.py` output and writes `examples/demo.cast` (asciicast v2 JSON lines format). The landing page plays it with asciinema-player. Key gotcha: we generate the .cast without a real Unix PTY (which would provide `onlcr` to convert `\n` → `\r\n`). Without `\r`, the terminal emulator treats `\n` as raw line feed — cursor goes down but stays at the same column, causing every line to drift right and wrap. Fix: `record_demo.py` merges `\r\n` into each text event. If you regenerate the .cast and lines look shifted right in the player, you forgot the `\r`. Run: `python examples/record_demo.py` then serve with `python -m http.server 8000`.
