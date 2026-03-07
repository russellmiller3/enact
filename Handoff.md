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

**Date:** 2026-03-07 (session 4)
**Project:** Enact — action firewall for AI agents (`pip install enact-sdk`)

### Git State

- Branch: `master`
- Last commit: `cab8963` feat(cloud): Supabase Postgres + Fly.io deploy config + rate limiting
- Remote: `origin` → https://github.com/russellmiller3/enact (in sync)
- PyPI: `enact-sdk 0.5.1` — published
- Working tree: **clean**

### What Was Done (session 4)

- **First production deploy** to `https://enact.fly.dev` — live and passing health checks.
- Fixed deploy blocker: `DATABASE_URL` was set to Supabase's direct connection (`db.xxx.supabase.co:5432`). Fly.io connects via IPv6; direct Supabase port 5432 rejects IPv6. Fixed by switching to Supabase **Supavisor pooler URL** (`aws-0-us-west-2.pooler.supabase.com:6543`).
- `curl https://enact.fly.dev/health` → `{"status":"ok"}` ✅

### Infrastructure State

- **Fly app**: `enact` at `https://enact.fly.dev` (SJC) — **LIVE** ✅
- **Supabase**: pooler URL set as `DATABASE_URL` Fly secret — connected ✅
- **Fly CLI path** (Windows): `~/.fly/bin/flyctl` (not in PATH)
- **`ENACT_EMAIL_DRY_RUN=1`** set in fly.toml — HITL emails won't send until toggled

### Next Step

**Phase 3: Stripe integration** — see `plans/2026-03-06-revenue-launch.md`
- Add Stripe checkout for `$199/mo` Cloud plan
- Webhook handler to provision team + API key on payment
- Gate receipt storage behind valid API key (already built in `cloud/auth.py`)

### Key Files

- `cloud/db.py` — dual-mode DB layer (Postgres + SQLite)
- `cloud/main.py` — FastAPI app + rate limiting
- `Dockerfile` / `fly.toml` — deployment config
- `plans/2026-03-06-revenue-launch.md` — revenue launch plan (Phase 1 done, Phase 2 done, Phase 3 next)

### What Exists (fully built + tested)

**SDK:** `enact/` — models, policy, receipt, client, rollback, cloud_client, ui, connectors (GitHub, Postgres, Filesystem, Slack), 16 policies, 3 workflows

**Cloud:** `cloud/` — FastAPI backend (receipt storage, HITL gates, badge SVG, auditor API, zero-knowledge encryption, dashboard UI)

**Tests:** 415 passing.
