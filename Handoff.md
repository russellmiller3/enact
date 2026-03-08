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

**Date:** 2026-03-08 (session 7)
**Project:** Enact — action firewall for AI agents (`pip install enact-sdk`)

### Git State

- Branch: `master`
- Remote: `origin` + `backup` (D drive)
- Vercel: `www.enact.cloud` — deployed
- PyPI: `enact-sdk 0.5.1` — published
- Working tree: **clean after this commit**

### What Was Done (session 7)

**Stripe integration** — fully implemented and tested (505 tests, 0 failures):
- `cloud/routes/stripe.py` — 4 endpoints: `POST /stripe/create-checkout-session`, `POST /stripe/webhook` (HMAC-verified; provisions team + API key + subscription atomically, idempotent on duplicate webhooks), `GET /stripe/success` (polling success page), `GET /stripe/status/{session_id}` (one-time key read — NULLed from DB after first call)
- `cloud/db.py` — added `subscriptions` + `checkout_sessions` tables + indexes
- `cloud/routes/receipts.py` — usage enforcement: 50K → warning header, 75K → 429
- `cloud/main.py` — stripe router registered; `/stripe/webhook` exempted from rate limiting (has its own HMAC auth)
- `cloud/requirements.txt` — added `stripe>=8.0.0`
- `tests/cloud/test_stripe.py` — 23 new tests
- `tests/cloud/test_receipts.py` — 4 new usage enforcement tests
- `tests/cloud/conftest.py` — clears `_rate_buckets` per test to prevent rate limiter bleed
- `index.html` — both Cloud CTAs now call `startCheckout()` JS function → Stripe Checkout redirect

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

**SDK:** `enact/` — models, policy, receipt, client, rollback, cloud_client, ui, connectors (GitHub, Postgres, Filesystem, Slack), 30 policies, 3 workflows

**Cloud:** `cloud/` — FastAPI backend (receipt storage, HITL gates, badge SVG, auditor API, zero-knowledge encryption, dashboard UI, Stripe signup flow, usage enforcement)

**Tests:** 505 passing.
