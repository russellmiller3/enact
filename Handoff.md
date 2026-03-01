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
- Branch: `claude/merge-branches-update-docs-dOg68` (merged all feature branches → push to master)
- Remote: `origin` → https://github.com/russellmiller3/enact
- PyPI: `enact-sdk 0.4` — bump when ready to publish
- License: ELv2 + no-resale clause

### What Exists (fully built + tested)

**SDK:**
```
enact/
  models.py, policy.py, receipt.py, client.py
  rollback.py                       # dispatch for GitHub + Postgres + Filesystem + Slack
  cloud_client.py                   # thin HTTP client for cloud API, lazy-imported
  ui.py                             # local receipt browser, dark mode, enact-ui CLI
  connectors/github.py, postgres.py, filesystem.py
  connectors/slack.py               # post_message, delete_message; rollback via ts
  policies/git.py, db.py, filesystem.py, crm.py, access.py, time.py
  policies/slack.py                 # require_channel_allowlist, block_dms
  workflows/agent_pr_workflow.py, db_safe_insert.py
  workflows/post_slack_message.py
```

**Cloud backend (`cloud/` package):**
```
cloud/
  __init__.py
  db.py           # SQLite, ENACT_DB_PATH read fresh per call (test isolation)
  auth.py         # X-Enact-Api-Key header; SHA-256 hash stored, raw key never persisted
  token.py        # HMAC-signed approve/deny tokens; action bound to token
  email.py        # smtplib; ENACT_EMAIL_DRY_RUN=1 for local dev
  main.py         # FastAPI app with lifespan startup
  routes/
    receipts.py   # POST /receipts (idempotent), GET /receipts/{run_id}
    hitl.py       # POST /hitl/request, GET /hitl/{id}, approve/deny + confirm pages
    badge.py      # GET /badge/{team_id}/{workflow}.svg — public, green/red/grey
```

**Tests:** 356+ tests total (SDK + cloud), all passing.

**Run cloud locally:**
```
CLOUD_SECRET=changeme ENACT_EMAIL_DRY_RUN=1 uvicorn cloud.main:app --reload
```

### Key Design Decisions (cloud)
- **DateTime format:** All stored as `"%Y-%m-%dT%H:%M:%SZ"` — Python 3.9's `fromisoformat` can't parse `+00:00`
- **Signature contract:** `_write_hitl_receipt` signs canonical JSON (`sort_keys=True, separators=(",",":")`) and stores the same canonical string
- **Badge ordering:** `ORDER BY rowid DESC` — handles same-second inserts correctly
- **DB path isolation:** `get_connection()` reads `ENACT_DB_PATH` fresh on every call — no module reload needed in tests

### Conventions Established
- **`already_done` flag**: Every mutating connector action includes `output["already_done"]` — `False` for fresh, descriptive string for noop
- **`rollback_data` field**: Every mutating `ActionResult` captures pre-action state
- **Plan template**: `PLAN-TEMPLATE.md` → red-team with `plans/guides/RED-TEAM-MODE-GUIDE.md` before coding

### What Was Done This Session (2026-03-01)
- **Merged all feature branches** into `claude/merge-branches-update-docs-dOg68`:
  - `receipt-ui-build` — `enact/ui.py`, local receipt browser with dark mode, `enact-ui` CLI ✅
  - `red-team-slack-exercise` — `SlackConnector`, Slack policies, `post_slack_message` workflow, rollback ✅
  - `cloud-service-architecture` — Cloud MVP: HITL, receipt storage, status badge, approval receipts ✅
  - `review-demo-index-page` — landing page receipt section fix ✅
  - `handoff-pytedt-fix`, `complete-handoff-tasks` — docs/plan updates ✅
- **README, SPEC, index.html** — updated for all merged features ✅

### Previously Completed
- ABAC policies, `block_ddl`, `code_freeze_active`, `user_email` rename ✅
- `FilesystemConnector` + filesystem policies + rollback ✅
- Rollback engine, idempotency, migration section in landing page + README ✅
- `enact-sdk 0.3.1` on PyPI ✅

### Next Steps (priority order)
1. **Receipt search UI** — HTMX + Tailwind CDN in `cloud/routes/ui.py`; filterable list + detail view + HITL queue
2. **Slack alerting on BLOCK** — `SLACK_WEBHOOK_URL`, fire on `decision=BLOCK` in `push_receipt_to_cloud()`
3. **HubSpotConnector** — `create_contact`, `update_deal`, `create_task`, `get_contact` (Template A)
4. **Show HN post** — after receipt UI ships

### Files to Reference
- `SPEC.md` — full build plan, strategic thesis, workflow roadmap
- `README.md` — install, quickstart, connector/policy/rollback reference
- `CLAUDE.md` — conventions, design philosophy, git workflow
- `PLAN-TEMPLATE.md` — how to write implementation plans
- `plans/guides/RED-TEAM-MODE-GUIDE.md` — red-team checklist
- `plans/2026-03-01-cloud-mvp.md` — cloud MVP plan (implemented)
- `plans/2026-03-01-slack-connector.md` — Slack plan (implemented)
- `examples/demo.py` — 3-act demo: BLOCK + PASS + ROLLBACK
