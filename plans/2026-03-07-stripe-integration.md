# Plan: Stripe Integration — $199/mo Cloud Tier

---

## Context

Phase 3 of the revenue launch plan (`plans/2026-03-06-revenue-launch.md`). Cloud backend is live on Fly.io, receipt dashboard and HITL are built. Now we need self-serve signup: user clicks button on landing page → Stripe Checkout → gets API key → starts pushing receipts.

## What We're Building

```
Landing page          Stripe Hosted           Enact Cloud
   [CTA] ──────────▶ Checkout Page ──webhook──▶ Provision team
                      (card + email)            + generate API key
                           │                         │
                           ▼                         ▼
                      Success page ◀──poll──── checkout_sessions
                      (shows API key)           (raw key stored
                                                 temporarily)
```

**Key Decisions:**
- **Stripe Checkout (hosted)** — no custom card forms, PCI handled by Stripe
- **Webhook-first provisioning** — team + key created in webhook handler, not on success page (Stripe guarantees delivery)
- **Bridge table (`checkout_sessions`)** — stores raw key temporarily so success page can retrieve it after webhook fires
- **Show key on success page** — since `ENACT_EMAIL_DRY_RUN=1`, we can't rely on email alone; show key + attempt email
- **No subscription enforcement on auth** — MVP only. Canceled customer keys still work. Add enforcement later.
- **Card required for trial** — filters tire-kickers per the revenue plan

## Existing Code to Read First

| File | Why |
|---|---|
| `cloud/main.py:97-100` | Where to register stripe router |
| `cloud/db.py:102-233` | Schema pattern for new tables |
| `cloud/auth.py:35-45` | `create_api_key()` — reuse for provisioning |
| `cloud/routes/receipts.py:60-129` | `push_receipt()` — where to add usage enforcement |
| `cloud/routes/hitl.py` | HTML rendering pattern for success page |

## Files to Create

### 1. `cloud/routes/stripe.py` — all Stripe endpoints

**Endpoints:**
- `POST /stripe/create-checkout-session` — unauthenticated, creates Stripe Checkout session
- `POST /stripe/webhook` — Stripe webhook handler (signature verified)
- `GET /stripe/success` — branded success page (shows API key)
- `GET /stripe/status/{session_id}` — JSON polling endpoint for success page. **One-time read:** returns raw key on first call, NULLs it from DB, subsequent calls return `{"status": "already_retrieved"}`

### 2. `tests/cloud/test_stripe.py` — full test coverage

## Files to Modify

### 1. `cloud/db.py`
Add 2 new tables to both `_init_postgres()` and `_init_sqlite()`:

**`subscriptions` table:**
```sql
CREATE TABLE IF NOT EXISTS subscriptions (
    team_id               TEXT PRIMARY KEY REFERENCES teams(team_id),
    stripe_customer_id    TEXT NOT NULL,
    stripe_subscription_id TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'trialing',
    plan_name             TEXT NOT NULL DEFAULT 'cloud',
    current_period_end    TEXT,
    created_at            TEXT DEFAULT ...,
    updated_at            TEXT DEFAULT ...
)
```

**`checkout_sessions` table** (temporary bridge — raw key is NULLed after first read):
```sql
CREATE TABLE IF NOT EXISTS checkout_sessions (
    session_id     TEXT PRIMARY KEY,
    team_id        TEXT,
    raw_api_key    TEXT,
    customer_email TEXT,
    status         TEXT NOT NULL DEFAULT 'pending',
    retrieved_at   TEXT,
    created_at     TEXT DEFAULT ...
)
```
**Security:** `raw_api_key` is stored temporarily so the success page can show it once. After the first read via `/stripe/status/{session_id}`, the handler sets `retrieved_at` and NULLs out `raw_api_key`. This ensures the raw key is never sitting in the DB longer than necessary.

Add indexes in `_create_indexes()`:
- `idx_subscriptions_stripe_customer ON subscriptions(stripe_customer_id)`
- `idx_checkout_sessions_status ON checkout_sessions(status)`

### 2. `cloud/main.py`
- Import and register `stripe_router` (line ~100)
- Add Stripe env var presence check in lifespan (warning, not fatal — Stripe features gracefully degrade)

### 3. `cloud/routes/receipts.py`
- Add usage enforcement to `push_receipt()` before the INSERT
- Count receipts for team in current month
- 75K+ → 429 rejection
- 50K+ → accept but add `X-Enact-Usage-Warning` header

### 4. `cloud/requirements.txt`
- Add `stripe>=8.0.0`

### 5. `index.html`
- Cloud tier CTA (line ~1532): change `mailto:` → JS checkout redirect
- Footer CTA (line ~1583): same change
- Add small `<script>` block for checkout function

## Edge Cases & Error Handling

| Scenario | Handling |
|---|---|
| Webhook arrives before success page load | Normal flow — key in checkout_sessions table |
| Success page loads before webhook | Poll returns `{"status": "pending"}`, JS retries |
| Duplicate webhook delivery | Single-transaction: check subscriptions for stripe_customer_id AND teams table, skip if exists. All inserts (team + key + subscription + checkout_session update) in one `with db() as conn:` block for atomicity |
| Invalid webhook signature | Return 400, log warning |
| Stripe env vars not set | Checkout endpoint returns 503, webhook returns 503 |
| Customer email already has a team | Create new team with unique ID (allow multiple teams) |
| Subscription canceled | Update status in subscriptions table; keys still work (MVP) |
| Usage > 75K receipts/month | Return 429 with clear message |
| Usage > 50K receipts/month | Accept receipt, add warning header |
| Key already retrieved from success page | `/stripe/status` returns `{"status": "already_retrieved"}` — key is gone from DB |
| Partial webhook (team created but subscription insert fails) | Single transaction — all-or-nothing via `with db() as conn:` |
| Orphan checkout sessions (abandoned checkouts) | Tech debt — no cleanup for MVP. Add `DELETE WHERE created_at < 24h AND status = 'pending'` later |

## Implementation Order (TDD Cycles)

### Cycle 1: Database schema + checkout_sessions table
- RED: Test that `init_db()` creates subscriptions and checkout_sessions tables
- GREEN: Add tables to `_init_postgres()` and `_init_sqlite()`
- VERIFY: `pytest tests/cloud/test_stripe.py -v`

### Cycle 2: Checkout session creation endpoint
- RED: Test `POST /stripe/create-checkout-session` returns Stripe URL
- GREEN: Implement with mocked `stripe.checkout.Session.create()`
- Test: missing Stripe env vars → 503
- VERIFY: `pytest tests/cloud/test_stripe.py -v`

### Cycle 3: Webhook handler — checkout.session.completed
- RED: Test webhook creates team + API key + subscription
- GREEN: Implement webhook with signature verification
- Test: duplicate webhook is idempotent
- Test: invalid signature → 400
- VERIFY: `pytest tests/cloud/test_stripe.py -v`

### Cycle 4: Success page + polling
- RED: Test `GET /stripe/success?session_id=X` returns HTML
- RED: Test `GET /stripe/status/{session_id}` returns key when ready
- GREEN: Implement success page (inline HTML like HITL pages) + status endpoint
- Test: poll before webhook → `{"status": "pending"}`
- Test: poll after webhook → `{"status": "ready", "api_key": "enact_live_..."}`
- Test: poll SECOND time after retrieval → `{"status": "already_retrieved"}` (raw key NULLed from DB)
- Test: unknown session_id → 404
- VERIFY: `pytest tests/cloud/test_stripe.py -v`

### Cycle 5: Webhook handler — subscription events
- RED: Test `customer.subscription.deleted` updates status
- RED: Test `invoice.payment_failed` updates status
- GREEN: Add event handlers
- VERIFY: `pytest tests/cloud/test_stripe.py -v`

### Cycle 6: Usage enforcement
- RED: Test receipt push at 75K+ → 429
- RED: Test receipt push at 50K+ → accepted with warning header
- RED: Test receipt push under 50K → normal
- GREEN: Add usage check to `push_receipt()` in receipts.py
- VERIFY: `pytest tests/cloud/test_receipts.py -v && pytest -v`

### Cycle 7: Landing page CTAs
- Update `index.html` Cloud tier button + footer CTA
- Add minimal JS for checkout redirect
- Manual verification via local server

## Environment Variables (new)

| Var | Where | Purpose |
|---|---|---|
| `STRIPE_SECRET_KEY` | Fly secret | Stripe API authentication |
| `STRIPE_WEBHOOK_SECRET` | Fly secret | Webhook signature verification |
| `STRIPE_PRICE_ID` | fly.toml [env] | $199/mo price ID |

## Test Strategy

```bash
# Run Stripe tests only
pytest tests/cloud/test_stripe.py -v

# Run receipts tests (usage enforcement)
pytest tests/cloud/test_receipts.py -v

# Full suite
pytest -v
```

**Mocking approach:** All Stripe API calls mocked via `unittest.mock.patch`. No real Stripe calls in tests. Test the webhook handler by patching `stripe.Webhook.construct_event()` to return a fake event dict — never add a "skip verification" env var or toggle. The mock replaces the Stripe SDK call, not our verification logic.

**Usage month boundary:** Use `created_at >= '{year}-{month:02d}-01T00:00:00Z'` (first of current UTC month) for usage count queries. ISO-8601 string comparison works correctly for this pattern.

## Success Criteria

- [ ] All new tests pass (~25-30 new tests)
- [ ] All 478 existing tests still pass
- [ ] `POST /stripe/create-checkout-session` → Stripe Checkout URL
- [ ] Webhook provisions team + key + subscription
- [ ] Success page shows API key after webhook fires
- [ ] Usage enforcement: 75K → 429, 50K → warning
- [ ] Landing page CTAs point to Stripe Checkout
- [ ] No dead code
