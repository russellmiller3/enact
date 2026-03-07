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

**Date:** 2026-03-07 (session 5)
**Project:** Enact — action firewall for AI agents (`pip install enact-sdk`)

### Git State

- Branch: `master`
- Last commit: `28116b7` docs(evals): add evals/README.md with index and protocol for future mock agents
- Remote: `origin` + `backup` (D drive) — both in sync
- Vercel: `www.enact.cloud` — deployed ✅
- PyPI: `enact-sdk 0.5.1` — published
- Working tree: **clean**

### What Was Done (session 5)

- **8 new built-in policies** — `dont_edit_gitignore`, `dont_read_env`, `dont_touch_ci_cd`, `dont_access_home_dir`, `dont_copy_api_keys` (filesystem); `dont_force_push`, `require_meaningful_commit_message`, `dont_commit_api_keys` (git)
- **`enact/policies/_secrets.py`** — shared module with 9 vendor API key regexes (OpenAI, GitHub, Slack, AWS, Google); avoids duplication across filesystem + git policies
- **63 new tests** — 478 total passing
- **`/enact-setup` Claude Code skill** — `skills/enact-setup/SKILL.md`; 7-step flow: scan → map → propose → write with approval; eval tested against `evals/enact-setup-eval/mock_agent/agent.py`
- **Landing page skill section** — single-line copy-button install command on `index.html`
- **`evals/README.md`** — eval index + cold subagent protocol + pattern table for future mock agents
- **CLAUDE.md** — added teaching style bullet about WHY explanations

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
- `skills/enact-setup/SKILL.md` — Claude Code skill for adding Enact to any repo
- `enact/policies/_secrets.py` — shared API key regex patterns

### What Exists (fully built + tested)

**SDK:** `enact/` — models, policy, receipt, client, rollback, cloud_client, ui, connectors (GitHub, Postgres, Filesystem, Slack), 24 policies, 3 workflows

**Cloud:** `cloud/` — FastAPI backend (receipt storage, HITL gates, badge SVG, auditor API, zero-knowledge encryption, dashboard UI)

**Tests:** 478 passing.
