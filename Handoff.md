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

**Date:** 2026-03-19 (session 8)
**Project:** Enact — action firewall for AI agents (`pip install enact-sdk`)

### Git State

- Branch: `feature/generic-actions` (merging to `master`)
- Remote: `origin` + `backup` (D drive)
- Vercel: `www.enact.cloud` — deployed
- PyPI: `enact-sdk 0.5.1` — published
- Working tree: **clean after this commit**

### What Was Done (session 8–9)

**Generic actions feature** — `@action` decorator + `run_action()` (566 tests, 0 failures):
- `enact/action.py` (NEW) — `@action("system.name")` decorator, `Action` dataclass, `execute_action()` with return normalization, `rollback_with()` pairing, module-level registry
- `enact/client.py` — added `actions=` param to init, `_action_registry` built from decorated fns, new `run_action()` method (single action through full policy/receipt pipeline), passes `action_registry` to rollback
- `enact/rollback.py` — added `action_registry` param to `execute_rollback_action()`, checks user-registered rollback fns BEFORE connector dispatch
- `enact/__init__.py` — exports `action`
- `tests/test_action.py` (NEW) — 25 tests covering decorator, normalization, rollback pairing, client integration, pluggable rollback, and full e2e lifecycle

**Prompt injection policy** — `enact/policies/prompt_injection.py` — regex-based payload scanning for injection patterns (instruction overrides, role hijacking, jailbreaks, delimiter attacks). Two policies: `block_prompt_injection` (scans all strings) and `block_prompt_injection_fields(list)` (scans only named fields).

**Landing page** — BYOC positioning, barless A wordmark (filled-path SVG), blue E as favicon only, footer disclaimer added.

**Legal** — liability disclaimer in LICENSE ("Disclaimer of Responsibility for Agent Actions"), README, and landing page footer. User is solely responsible for agent actions.

**Outreach** — `docs/outreach-plan.md` — 10 people to contact for validation/feedback (potential customers, agent space founders, governance experts).

### Next Step

**Deploy to Fly + wire up Stripe** — code is done, needs 3 secrets set in production:
```
flyctl secrets set STRIPE_SECRET_KEY=sk_live_...
flyctl secrets set STRIPE_WEBHOOK_SECRET=whsec_...
flyctl secrets set STRIPE_PRICE_ID=price_...  # or set in fly.toml [env]
```
Then register the webhook URL in Stripe dashboard: `https://enact.fly.dev/stripe/webhook`
Events to subscribe: `checkout.session.completed`, `customer.subscription.deleted`, `invoice.payment_failed`

After deploy: manually test the full signup flow end-to-end (Stripe test mode).

### Infrastructure State

- **Fly app**: `enact` at `https://enact.fly.dev` (SJC) — LIVE
- **Supabase**: pooler URL set as `DATABASE_URL` Fly secret — connected
- **Fly CLI path** (Windows): `~/.fly/bin/flyctl` (not in PATH)
- **`ENACT_EMAIL_DRY_RUN=1`** set in fly.toml
- **Stripe secrets needed (not yet set):** `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID`

### What Exists (fully built + tested)

**SDK:** `enact/` — models, policy, receipt, client, rollback, cloud_client, ui, connectors (GitHub, Postgres, Filesystem, Slack), `@action` decorator, 30 policies, 3 workflows

**Cloud:** `cloud/` — FastAPI backend (receipt storage, HITL gates, badge SVG, auditor API, zero-knowledge encryption, dashboard UI, Stripe signup flow, usage enforcement)

**Tests:** 530 passing.
