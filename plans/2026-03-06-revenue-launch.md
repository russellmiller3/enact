# Plan: Revenue Launch — Cloud Deploy + UI + Stripe + Content

**Date:** 2026-03-06
**Goal:** Get from "working SDK on PyPI" to "accepting $199/mo payments" as fast as possible.

---

## What We're Building

Four things, in order:

1. **Cloud deployment** — the FastAPI backend live on the internet, accepting encrypted receipts
2. **Cloud UI** — sharp receipt search dashboard + HITL approval screen (not email-only)
3. **Stripe integration** — $199/mo Cloud tier, self-serve signup
4. **Content engine** — 4 blog posts (Mitchell Hashimoto playbook) + Show HN prep

Everything else waits. No new connectors, no new policies, no compliance templates until there's a paying customer.

---

## 1. Cloud Deployment

**What exists:** `cloud/` package — FastAPI app with receipt storage, HITL gates, badge SVG, auth (API key, SHA-256 hashed). SQLite DB. Tested (356+ tests).

**What's needed to go live:**

| Task | Detail |
|------|--------|
| Pick hosting | Railway or Fly.io. Both deploy FastAPI trivially. Railway has simpler DX. Fly has persistent volumes for SQLite. **Rec: Fly.io** — persistent volume for SQLite, free tier covers MVP traffic. |
| Persistent storage | Fly volume for SQLite DB. Receipts are append-only, so no complex DB needed yet. Migrate to Postgres later if needed. |
| Environment vars | `CLOUD_SECRET`, `ENACT_DB_PATH`, `ENACT_EMAIL_*` (SMTP creds for HITL emails) |
| Domain | `api.enact.cloud` — point to Fly deployment |
| HTTPS | Fly handles TLS automatically |
| CORS | Add CORS middleware for cloud UI (separate static deploy or same origin) |
| Health check | `GET /health` endpoint returning `{"status": "ok"}` |
| Rate limiting | Basic IP-based rate limiting on receipt ingestion (prevent abuse on free trial) |

**Deploy checklist:**
- [ ] Add `Dockerfile` for cloud/ (or `fly.toml`)
- [ ] Add `/health` endpoint
- [ ] Add CORS middleware
- [ ] Add basic rate limiting (stdlib, no extra deps)
- [ ] Deploy to Fly.io
- [ ] Point `api.enact.cloud` DNS
- [ ] Smoke test: push a receipt from local SDK, verify it arrives

---

## 2. Cloud UI — Receipt Dashboard + HITL Screen

**Philosophy:** This is the thing that makes $199/mo feel worth it. It should look as polished as the landing page. Dark mode default, IBM Plex Mono for data, Inter for UI text. Same design language as `index.html`.

### 2a. Receipt Dashboard

A single-page app (static HTML/CSS/JS, no framework) served from the cloud or a separate static host.

**Layout:**
```
+------------------------------------------------------------------+
| ENACT CLOUD                    [team name]  [dark/light]  [logout]|
+------------------------------------------------------------------+
| FILTERS: [workflow v] [decision v] [date range] [search agent...] |
+------------------------------------------------------------------+
| RUN ID        WORKFLOW         AGENT           DECISION   TIME    |
| a1b2c3d4      agent_pr_wf      deploy-bot     PASS       2m ago  |
| e5f6g7h8      db_safe_insert   data-agent     BLOCK      15m ago |
| i9j0k1l2      post_slack_msg   notify-bot     PASS       1h ago  |
+------------------------------------------------------------------+
|                    [receipt detail panel]                          |
| Click a row to see: full receipt, policy results, actions taken,  |
| signature verification status, rollback button                    |
+------------------------------------------------------------------+
```

**Key features:**
- Filterable by workflow, decision (PASS/BLOCK/ROLLBACK), date range, agent
- Click row to expand receipt detail (same format as landing page receipt examples)
- Signature verification badge (valid/invalid/no-key)
- Metadata-only view (payload is encrypted, show "[encrypted]" placeholder)
- Real-time-ish: poll every 30s or manual refresh
- Responsive (works on tablet for on-call engineers)
- Export: CSV of visible rows (metadata only)

**Tech:** Static HTML + vanilla JS. Calls `GET /api/receipts` (list) and `GET /api/receipts/{run_id}` (detail). Auth via API key in localStorage (entered on first visit, stored locally).

### 2b. HITL Approval Screen

Right now HITL works via email with signed approve/deny links. Keep that — but ALSO build a sharp approval page that the link lands on.

**Current:** `GET /hitl/{id}/approve` fires immediately. No confirmation UI.

**Target:** Link goes to a branded confirmation page showing:
```
+------------------------------------------------------------------+
| ENACT — Human Approval Required                                   |
+------------------------------------------------------------------+
|                                                                    |
|  WORKFLOW:    db_safe_insert                                       |
|  AGENT:       data-migration-bot                                   |
|  REQUESTED:   2026-03-06 14:32 UTC                                 |
|  EXPIRES:     2026-03-06 15:02 UTC (18 min remaining)              |
|                                                                    |
|  ACTION REQUESTED:                                                 |
|  Insert 847 rows into `transactions` table                         |
|                                                                    |
|  POLICIES PASSED:                                                  |
|  [checkmark] dont_delete_row                                       |
|  [checkmark] protect_tables("users", "accounts")                   |
|                                                                    |
|  +------------------+     +------------------+                     |
|  |    APPROVE       |     |      DENY        |                     |
|  +------------------+     +------------------+                     |
|                                                                    |
|  This action is cryptographically signed.                          |
|  Approval token is single-use and time-bound.                      |
+------------------------------------------------------------------+
```

**Key features:**
- Branded page (Enact logo, same design language)
- Shows workflow context — what the agent wants to do
- Countdown timer for expiry
- One-click approve/deny (signed token in URL, no login needed)
- After action: confirmation page ("Approved. Agent will proceed." / "Denied. Agent will halt.")
- Mobile-friendly (approvers are often on phone)

**Tech:** Server-rendered HTML from FastAPI (Jinja2 template or inline HTML). No JS framework needed — it's a single confirmation page.

### 2c. Cloud UI Build Checklist

- [ ] Receipt dashboard: HTML/CSS/JS scaffold (dark mode, same design language as landing page)
- [ ] Receipt list view with filters (workflow, decision, date, agent)
- [ ] Receipt detail panel (expand on click)
- [ ] API key entry + localStorage persistence
- [ ] HITL approval page (server-rendered, branded)
- [ ] HITL confirmation/result page
- [ ] HITL countdown timer
- [ ] Deploy dashboard as static site (Vercel or same Fly app)

---

## 3. Stripe Integration

**Goal:** Self-serve signup for $199/mo Cloud tier. No sales call needed.

| Task | Detail |
|------|--------|
| Stripe account | Create Stripe account, set up Product + Price ($199/mo recurring) |
| Checkout flow | Stripe Checkout (hosted page). Button on landing page and cloud dashboard → Stripe → redirect back. |
| API key provisioning | On successful payment webhook, generate API key, hash it (SHA-256), store hash in DB, email raw key to customer ONCE. |
| Webhook handler | `POST /stripe/webhook` — handle `checkout.session.completed`, `invoice.paid`, `customer.subscription.deleted` |
| Trial | 14-day free trial (no card required to start? or card required?) **Rec: card required** — filters tire-kickers, higher conversion to paid. |
| Landing page update | Change "Start free trial" mailto links to actual Stripe Checkout links |
| Usage tracking | Count receipts per customer per month. Soft limit at 50K (email warning), hard limit at 75K (reject with 429). |

**Stripe integration checklist:**
- [ ] Create Stripe account + product + price
- [ ] Add `POST /stripe/webhook` endpoint to cloud
- [ ] API key provisioning on payment
- [ ] Usage tracking (receipt count per customer/month)
- [ ] Update landing page CTAs to point to Stripe Checkout
- [ ] Test full flow: landing page → Stripe → API key → push receipt

---

## 4. Content Engine — Blog Posts + Show HN

### The Mitchell Hashimoto Playbook

Mitchell's approach: write deeply technical posts about specific problems. Each post establishes authority on that problem. The product emerges as the natural solution. Posts compound via SEO.

For Enact, two categories of posts:

**Category A: The regulatory fire** (CISO audience, compliance keywords)
**Category B: The architecture advantage** (engineer audience, technical keywords)

### Post 1: "Your AI Agents Are a SOX Risk. Here's What Auditors Are Already Asking."
**Audience:** Engineering leads and CISOs at companies with agents in production
**Keywords:** SOX AI agents, AI agent audit trail, AI agent compliance 2026
**Outline:**
- Open with: "In Q1 2026, three SOC 2 auditors independently told companies the same thing: 'Show me how you control your AI agents.'"
- The regulatory landscape: SOX (already in effect for AI), SOC 2 (auditors asking now), EU AI Act (Aug 2026)
- What auditors actually want: evidence that controls existed BEFORE the action, not just logs after
- The three-party trust problem: companies can't audit themselves
- How Enact solves it (brief, not salesy — show the receipt format, the zero-knowledge model)
- CTA: "Install the SDK free, push receipts to Cloud when you're ready"

### Post 2: "No LLMs in the Decision Path: Why Deterministic Policy Engines Beat AI Guardrails"
**Audience:** Engineers building agent systems
**Keywords:** AI agent guardrails, deterministic policy engine, AI agent safety
**Outline:**
- Open with: the Kiro/Replit stories — agents that did exactly what they were told
- The problem with LLM-based guardrails: non-deterministic, slow, expensive, untestable
- Deterministic alternative: Python functions, testable with pytest, versioned in Git
- Code examples: a policy that blocks `DELETE` without `WHERE`, a policy that enforces branch naming
- The testing story: "You can't write a unit test for an LLM guardrail. You CAN write one for a Python function."
- Why this matters for compliance: auditors need to verify the control logic. Python functions are auditable. LLM prompts are not.

### Post 3: "Rollback for AI Agents: The Feature Nobody's Built (Until Now)"
**Audience:** Engineers who've been burned by agent mistakes
**Keywords:** AI agent rollback, undo AI agent action, AI agent disaster recovery
**Outline:**
- Open with: "The Replit story ends differently with one command: `enact.rollback(run_id)`"
- Why rollback is hard: you need a receipt of exactly what happened (what was created, what was modified, what the previous state was)
- The saga pattern: every action captures rollback_data at execution time
- Code walkthrough: agent creates PR → something goes wrong → rollback closes PR, deletes branch
- What CAN and CAN'T be rolled back (honest — sent emails can't be unsent)
- The competitive landscape: nobody else has this. Not AgentBouncr, not Nucleus, not any observability tool.

### Post 4: "EU AI Act Enforcement Is 5 Months Away. Here's What You Need to Build."
**Audience:** CTOs and engineering leads at companies deploying AI in the EU
**Keywords:** EU AI Act compliance, EU AI Act August 2026, AI agent traceability
**Outline:**
- The timeline: what's enforced when (graduated enforcement schedule)
- What "high-risk AI system" means (hint: if your agent touches financial data, healthcare, or employment decisions, you're probably in scope)
- The four requirements that matter: traceability, transparency, accountability, conformity assessment
- What "traceability" actually requires: per-action audit trail, policy documentation, evidence of human oversight
- How most companies are handling it today (badly: manual spreadsheets, hope)
- The Enact approach: automatic receipts = automatic traceability

### Show HN Prep

**Title:** "Show HN: Enact -- zero-knowledge audit trail for AI agents (rollback included)"
**Hook:** "EU AI Act enforcement is 5 months away. Your AI agents need an independent audit trail that you can't tamper with and we can't read. We built one with one-command rollback."

**Prepared responses for common HN objections:**
- "Why not just log to S3?" → S3 is self-hosted. You can delete your own S3 objects. An auditor needs an independent copy you can't touch. Same reason companies use external auditors, not internal ones.
- "Why ELv2, not open source?" → Solo founder, no VC, need to prevent AWS from hosting it as a service. ELv2 lets you read every line, self-host, modify. Just can't resell it.
- "Why not use an LLM to evaluate policies?" → Non-deterministic. Untestable. Unauditable. The whole point is that a Python function is verifiable by an auditor. An LLM prompt is not.
- "This is just middleware" → Yes. TCP/IP is just a protocol. Firewalls are just middleware. The value is in the policy library and the independent audit trail.

---

## Execution Sequence

### Week 1: Cloud goes live
- [ ] Fly.io deploy (Dockerfile, fly.toml, volume for SQLite)
- [ ] DNS: api.enact.cloud
- [ ] Health check endpoint
- [ ] CORS + rate limiting
- [ ] Smoke test from local SDK

### Week 2: Cloud UI
- [ ] Receipt dashboard (HTML/CSS/JS, dark mode, filters, detail panel)
- [ ] HITL approval page (server-rendered, branded, countdown timer)
- [ ] Deploy dashboard (Vercel or Fly static)

### Week 3: Stripe + Go Live
- [ ] Stripe account + product + webhook
- [ ] API key provisioning flow
- [ ] Update landing page CTAs (real Stripe links)
- [ ] Usage tracking
- [ ] End-to-end test: signup → pay → get key → push receipt → see in dashboard

### Week 3-4: Content + Launch
- [ ] Write Post 1 (SOX risk) — publish on blog.enact.cloud or dev.to
- [ ] Write Post 2 (deterministic policies) — publish
- [ ] Submit Show HN
- [ ] Post in LangChain Discord, Anthropic Discord, r/devops
- [ ] Write Posts 3 and 4 over following 2 weeks

---

## What We're NOT Doing (yet)

- No new connectors (4 is enough for launch)
- No compliance export templates (that's the $999/mo tier — build when first customer asks)
- No anomaly detection
- No multi-agent arbitration
- No Postgres migration (SQLite is fine for first 100 customers)
- No mobile app
- No CLI dashboard

These are all real features. They wait until revenue proves the market.
