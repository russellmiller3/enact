# Handoff.md

---

## How to Use This File

**This file is for Claude, maintained by Claude.**

At the end of every session, update the Handoff section below to reflect current state.
Keep it tight — the goal is to get the next Claude session oriented in under 60 seconds.

**What to include:**
- Current git state (branch, last commit, remotes)
- What was just completed this session
- Exact next step (be specific — file name, function name, what it should do)
- Any blockers, decisions pending, or things to watch out for
- Links/paths to key files

**What to cut:**
- History that's already done and not relevant to next steps
- Anything already captured in SPEC.md
- Long explanations — just the facts

**When to update:** Before ending any session where code was written or decisions were made.

---

## Current Handoff

**Date:** 2026-02-23
**Project:** Enact — action firewall for AI agents (`pip install enact`)

### Git State
- Branch: `master`
- Remotes: `origin` → https://github.com/russellmiller3/enact (primary), `backup` → D:/backup/enact
- Last commit: `f683077` — Update landing page GitHub links to russellmiller3/enact
- Backup remote is stale (history was rewritten to scrub `backend/.env`). Run `git push backup master --force` to sync it.

### What Exists
- `Enact Landing Page Best.html` — canonical landing page, source of truth for product copy
- `SPEC.md` — full build plan, 5 phases, repo structure, policy examples, dependencies
- `backend/` — old Visa GDO app code, kept for porting (see SPEC.md "What We Have" table)
- `.gitignore` — covers pyc, .env, receipts, .pytest_cache

### What Does NOT Exist Yet
The `enact/` Python package has not been started. Zero SDK code written.

### Next Step: Start Phase 1

Per `SPEC.md` build order, Phase 1 is the core SDK (no external deps, all testable with mocks):

1. **`enact/models.py`** — Define `WorkflowContext`, `PolicyResult`, `Receipt`, `RunResult` using Pydantic v2
2. **`enact/policy.py`** — Port from `backend/agents/policy.py`, generalize for Enact (remove ABAC/Visa specifics)
3. **`enact/receipt.py`** — Port from `backend/receipts.py`, add HMAC-SHA256 signing
4. **`enact/client.py`** — `EnactClient.__init__(systems, policies, workflows)` + `run(workflow, actor_email, payload) -> tuple[dict, Receipt]`
5. **`enact/__init__.py`** — Export `EnactClient`, `Receipt`
6. **`tests/test_policy_engine.py`** and **`tests/test_receipt.py`**

Start with `enact/models.py`. Key models needed:
```python
class WorkflowContext(BaseModel):
    workflow: str
    actor_email: str
    payload: dict
    systems: dict  # connector instances keyed by name

class PolicyResult(BaseModel):
    policy: str
    passed: bool
    reason: str

class Receipt(BaseModel):
    run_id: str          # UUID
    workflow: str
    actor_email: str
    payload: dict
    policy_results: list[PolicyResult]
    decision: str        # "PASS" | "BLOCK"
    timestamp: str       # ISO8601
    signature: str       # HMAC-SHA256 hex digest

class RunResult(BaseModel):
    success: bool
    workflow: str
    output: dict
```

### Key Decisions (don't re-litigate)
- No LLMs in policy engine — pure Python functions only
- Connectors: Postgres (psycopg2), GitHub (PyGithub), HubSpot (hubspot-api-client) — use vendor SDKs
- Receipts are HMAC-signed — makes "audit-trail ready" literally true
- Postgres connector note: works with Supabase, Neon, Railway, RDS — call this out in README
- GitHub connector in MVP — coding agents are primary audience
- HubSpot in Phase 4 (needs sandbox to test)
- Salesforce → v2
- Domain: enact.cloud (not yet purchased)
- PyPI name `enact` — check availability before Phase 5

### Files to Reference When Building
- `backend/agents/policy.py` — policy engine to port
- `backend/receipts.py` — receipt writer to port
- `backend/config/policies.py` — example policy functions
- `backend/models.py` — old models to refactor from
