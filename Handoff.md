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

**Date:** 2026-03-04
**Project:** Enact — action firewall for AI agents (`pip install enact-sdk`)

### Git State

- Branch: `master`
- Last commit: `9b244a3` feat(docs+landing): new landing page live + Mintlify docs scaffold + short README
- Remote: `origin` → https://github.com/russellmiller3/enact
- PyPI: `enact-sdk 0.5` — published
- License: ELv2 + no-resale clause
- All clean — nothing uncommitted

### What Was Done This Session (2026-03-04)

**Landing page swapped:**
- `new-landing.html` is now `index.html` (live on Vercel)
- Old `index.html` → `landing_pages/index-v1-backup.html`
- "Install the open-source SDK →" CTA → PyPI
- "Get Audit-Ready →" nav button stays → mailto (enterprise sale)

**Docs shipped (Mintlify — live):**
- `docs/mint.json` — nav, colors, topbar CTA ("pip install enact-sdk")
- 11 MDX pages across: getting-started, migration, integrations, concepts/*, cloud/*, reference/*
- Foreman analogy in `docs/concepts/overview.mdx`
- `docs/integrations.mdx` — maps Enact workflows to Anthropic skills, MCP, LangChain, CrewAI
- Mintlify connected: russellmiller3/enact, branch=master, monorepo path=/docs
- Docs auto-deploy on every push to master

**README:**
- Cut from 609 lines → 57 lines
- Foreman analogy kept
- Everything else links to docs.enact.cloud

### Next Steps (priority order)

1. **Receipt search UI** — HTMX + Tailwind CDN in `cloud/routes/ui.py`; filterable list + detail view + HITL queue
2. **Slack alerting on BLOCK** — `SLACK_WEBHOOK_URL`, fire on `decision=BLOCK` in `push_receipt_to_cloud()`
3. **HubSpotConnector** — `create_contact`, `update_deal`, `create_task`, `get_contact`
4. **Show HN post** — after receipt UI ships
5. **Custom domain for docs** — point `docs.enact.cloud` at Mintlify (DNS in Porkbun)

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
  policies/git.py, db.py, filesystem.py, crm.py, access.py, time.py, email.py
  policies/slack.py                 # require_channel_allowlist, block_dms
  policies/cloud_storage.py         # dont_delete_without_human_ok
  workflows/agent_pr_workflow.py, db_safe_insert.py
  workflows/post_slack_message.py
```

**Cloud backend (`cloud/` package):**

```
cloud/
  db.py           # SQLite, ENACT_DB_PATH read fresh per call (test isolation)
  auth.py         # X-Enact-Api-Key header; SHA-256 hash stored, raw key never persisted
  token.py        # HMAC-signed approve/deny tokens; action bound to token
  approval_email.py  # smtplib; ENACT_EMAIL_DRY_RUN=1 for local dev
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

### Key Design Decisions

- **DateTime format:** All stored as `"%Y-%m-%dT%H:%M:%SZ"` — Python 3.9's `fromisoformat` can't parse `+00:00`
- **Signature contract:** `_write_hitl_receipt` signs canonical JSON (`sort_keys=True, separators=(",",":")`)
- **Badge ordering:** `ORDER BY rowid DESC` — handles same-second inserts correctly
- **DB path isolation:** `get_connection()` reads `ENACT_DB_PATH` fresh on every call

### Conventions Established

- **`already_done` flag**: Every mutating connector action includes `output["already_done"]`
- **`rollback_data` field**: Every mutating `ActionResult` captures pre-action state
- **Boolean naming**: Name booleans after what you _want_ to be true (see `.roorules`)

### Next Steps (priority order after demo fix)

1. **Fix demo player** — unpkg fallback (see blocker above)
2. **Make new-landing.html the live page** — replace `index.html` with `new-landing.html` content
3. **Receipt search UI** — HTMX + Tailwind CDN in `cloud/routes/ui.py`; filterable list + detail view + HITL queue
4. **Slack alerting on BLOCK** — `SLACK_WEBHOOK_URL`, fire on `decision=BLOCK` in `push_receipt_to_cloud()`
5. **HubSpotConnector** — `create_contact`, `update_deal`, `create_task`, `get_contact`
6. **Show HN post** — after receipt UI ships

### Files to Reference

- `SPEC.md` — full build plan, strategic thesis, workflow roadmap
- `README.md` — install, quickstart, connector/policy/rollback reference
- `CLAUDE.md` — conventions, design philosophy, git workflow
- `PLAN-TEMPLATE.md` — how to write implementation plans
- `plans/guides/RED-TEAM-MODE-GUIDE.md` — red-team checklist
