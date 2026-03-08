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

**Date:** 2026-03-07 (session 6)
**Project:** Enact — action firewall for AI agents (`pip install enact-sdk`)

### Git State

- Branch: `master`
- Last commit: `c8a0b37` feat: add .intent spec system
- Remote: `origin` + `backup` (D drive)
- Vercel: `www.enact.cloud` — deployed
- PyPI: `enact-sdk 0.5.1` — published
- Working tree: **uncommitted changes** (see below)

### Uncommitted Changes

- `CLAUDE.md` — updated: references `enact-intent.md` instead of `enact.intent`; added "always red-team plans" rule
- `SPEC.md` — added cross-reference to `enact-intent.md`
- `enact.intent` — **deleted** (replaced by `enact-intent.md`)
- `enact-intent.md` — **new** (markdown rewrite of the `.intent` file)
- `plans/2026-03-07-stripe-integration.md` — **new** (Stripe plan, red-teamed)

### What Was Done (session 6)

- **Converted `enact.intent` → `enact-intent.md`** — same content, proper markdown format (headings, tables, code blocks instead of `//` comments)
- **Stripe integration plan** — wrote and red-teamed `plans/2026-03-07-stripe-integration.md`. Red team found 2 critical issues (raw key plaintext in DB, unauthenticated key exposure) and fixed them (one-time-read pattern, `retrieved_at` + NULL key after read)
- **CLAUDE.md updates** — added "always red-team plans immediately after creating" rule; updated intent file reference
- **SPEC.md** — added cross-reference to `enact-intent.md`

### Next Step

**Implement Stripe integration** — follow `plans/2026-03-07-stripe-integration.md`

TDD cycles in order:
1. DB schema (subscriptions + checkout_sessions tables) in `cloud/db.py`
2. Checkout session endpoint in `cloud/routes/stripe.py`
3. Webhook handler (`checkout.session.completed`)
4. Success page + one-time-read polling
5. Subscription lifecycle events
6. Usage enforcement (50K soft / 75K hard) in `cloud/routes/receipts.py`
7. Landing page CTA updates in `index.html`

**Before coding:** commit the uncommitted changes from this session first.

### Key Files

- `plans/2026-03-07-stripe-integration.md` — the plan (red-teamed, ready to implement)
- `cloud/db.py` — add subscriptions + checkout_sessions tables
- `cloud/routes/stripe.py` — new file: all Stripe endpoints
- `cloud/routes/receipts.py` — add usage enforcement to `push_receipt()`
- `cloud/main.py` — register stripe router
- `cloud/auth.py` — reuse `create_api_key()` for provisioning
- `index.html` — update Cloud tier CTA from mailto to Stripe Checkout

### Infrastructure State

- **Fly app**: `enact` at `https://enact.fly.dev` (SJC) — LIVE
- **Supabase**: pooler URL set as `DATABASE_URL` Fly secret — connected
- **Fly CLI path** (Windows): `~/.fly/bin/flyctl` (not in PATH)
- **`ENACT_EMAIL_DRY_RUN=1`** set in fly.toml
- **New env vars needed for Stripe:** `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (Fly secrets), `STRIPE_PRICE_ID` (fly.toml env)

### What Exists (fully built + tested)

**SDK:** `enact/` — models, policy, receipt, client, rollback, cloud_client, ui, connectors (GitHub, Postgres, Filesystem, Slack), 30 policies, 3 workflows

**Cloud:** `cloud/` — FastAPI backend (receipt storage, HITL gates, badge SVG, auditor API, zero-knowledge encryption, dashboard UI)

**Tests:** 478 passing.
