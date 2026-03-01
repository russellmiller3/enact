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

**Date:** 2026-03-01
**Project:** Enact — action firewall for AI agents (`pip install enact-sdk`)

### Git State
- Branch: `claude/cloud-service-architecture-dGomr` (feature branch — not yet merged to master)
- Last commit: `65c233e` — "feat: cloud MVP — HITL, receipt storage, status badge, approval receipts"
- Remote: `origin` → https://github.com/russellmiller3/enact
- PyPI: `enact-sdk 0.3.1` live at https://pypi.org/project/enact-sdk/0.3.1/

### What Exists (fully built + tested)
356 tests total (321 SDK + 35 new cloud), all passing.

**SDK (unchanged from 0.3.1):**
```
enact/
  models.py, policy.py, receipt.py, client.py, rollback.py
  cloud_client.py               # NEW — thin HTTP client for cloud API, lazy-imported
  client.py                     # MODIFIED — cloud_api_key= param, push_receipt_to_cloud(), run_with_hitl()
  connectors/github.py, postgres.py, filesystem.py
  policies/git.py, db.py, filesystem.py, crm.py, access.py, time.py
  workflows/agent_pr_workflow.py, db_safe_insert.py
```

**Cloud backend (new `cloud/` package):**
```
cloud/
  __init__.py
  db.py           # SQLite, ENACT_DB_PATH read fresh per call (test isolation w/o module reload)
  auth.py         # X-Enact-Api-Key header; SHA-256 hash stored, raw key never persisted
  token.py        # HMAC-signed approve/deny tokens; action bound to token (deny token can't approve)
  email.py        # smtplib; ENACT_EMAIL_DRY_RUN=1 for local dev
  main.py         # FastAPI app with lifespan startup (checks CLOUD_SECRET exists)
  routes/
    receipts.py   # POST /receipts (idempotent), GET /receipts/{run_id}
    hitl.py       # POST /hitl/request, GET /hitl/{id}, GET/POST approve/deny + confirm pages
                  # _write_hitl_receipt() — signed HMAC receipt, canonical JSON stored+signed
                  # _fire_callback() — fire-and-forget POST on approve/deny (daemon thread)
    badge.py      # GET /badge/{team_id}/{workflow}.svg — public, no auth, green/red/grey
```

**Tests:** `tests/cloud/` (conftest, test_auth, test_receipts, test_hitl, test_badge, test_hitl_receipt) + `tests/test_cloud_client.py`

**Run locally:**
```
CLOUD_SECRET=changeme ENACT_EMAIL_DRY_RUN=1 uvicorn cloud.main:app --reload
```

**Run tests:**
```
pytest tests/cloud/ tests/test_cloud_client.py -v
# NOTE: pytest must have fastapi+httpx installed. If "no module fastapi": uv tool install pytest --with fastapi --with httpx --with pydantic
```

### Key Design Decisions (cloud)
- **DateTime format:** All stored as `"%Y-%m-%dT%H:%M:%SZ"` (not `.isoformat()`) — Python 3.9's `fromisoformat` can't parse `+00:00` suffix
- **Signature contract:** `_write_hitl_receipt` signs canonical JSON (`sort_keys=True, separators=(",",":")`) AND stores the same canonical string — test verifies `hmac(receipt_json.encode()) == signature` directly
- **Badge ordering:** `ORDER BY rowid DESC` not `created_at DESC` — handles same-second inserts correctly
- **DB path isolation:** `get_connection()` reads `ENACT_DB_PATH` fresh on every call — no module reload needed in tests, `monkeypatch.setenv` is sufficient

### Conventions (carry forward to all new cloud routes)
- **`already_done` flag**: Every mutating connector action includes `output["already_done"]`
- **`rollback_data` field**: Every mutating `ActionResult` captures pre-action state
- **Plan template**: `PLAN-TEMPLATE.md` → red-team with `plans/guides/RED-TEAM-MODE-GUIDE.md` before coding

### Next Steps (priority order)

**1. Receipt search UI** — highest ROI, makes cloud sticky, converts trial → paid
- HTMX + Tailwind CDN, no React, no build step, lives in `cloud/routes/ui.py`
- `GET /ui/receipts` — filterable list (workflow, decision, date range, agent email)
- `GET /ui/receipts/{run_id}` — detail view with full JSON + verify signature button
- `GET /ui/hitl` — pending HITL queue (morning triage for ops teams)
- This is what a CISO shows in a board meeting. Without it, receipts are a push-and-forget API.

**2. Slack alerting on BLOCK** — 2 hours, pure growth loop
- Env var: `SLACK_WEBHOOK_URL`
- When `decision=BLOCK` pushed via `push_receipt_to_cloud()`, fire a Slack POST
- Message format: workflow name, agent email, policy that failed, link to receipt detail in UI
- Every blocked-agent ping in Slack is a referral

**3. HubSpotConnector** — closes the CRM story on the landing page
- `create_contact`, `update_deal`, `create_task`, `get_contact`
- Use HubSpot free sandbox
- `new_lead_workflow` is already designed in SPEC.md
- Template A (Full TDD), red-team before coding

**4. Show HN post** — after UI ships (gives you something to link to beyond the badge)

### Files to Reference
- `SPEC.md` — full build plan, strategic thesis, workflow roadmap
- `README.md` — install, quickstart, connector/policy/rollback reference
- `CLAUDE.md` — conventions, design philosophy, git workflow
- `PLAN-TEMPLATE.md` — how to write implementation plans
- `plans/guides/RED-TEAM-MODE-GUIDE.md` — red-team checklist (run before every plan)
- `plans/2026-03-01-cloud-mvp.md` — cloud MVP plan (already red-teamed and implemented)
- `examples/demo.py` — 3-act demo: BLOCK + PASS + ROLLBACK (no credentials)
</content>
</invoke>