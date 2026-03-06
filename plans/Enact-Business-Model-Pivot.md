# Enact Business Model Pivot — Independent Agent Audit Infrastructure

> Date: 2026-03-05
> Status: Plan
> Author: Russell + Claude session

---

## The Insight

Enact is not a developer tool. It's **independent audit infrastructure for AI agents.**

Companies can't audit themselves. Ernst & Young audits Goldman Sachs. When AI agents start touching financial transactions, databases, and production systems, regulators (SOX, SOC 2, EU AI Act) will require an **independent third party** to verify that controls existed and ran correctly.

Enact is that third party. The cloud stores encrypted, append-only, tamper-proof proof that agents followed the rules — and Enact can't even read the data (zero-knowledge encryption).

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Company    │     │    Enact     │     │   Auditor   │
│              │     │   (cloud)    │     │             │
│ Runs agents  │────▶│ Stores proof │────▶│ Verifies    │
│ Owns keys    │     │ Can't read   │     │ Controls    │
│ Writes policy│     │ Can verify   │     │ Existed     │
│              │     │ Append-only  │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
```

---

## The Regulatory Tailwind (why now)

| Regulation                                             | Deadline                     | What it requires                                                                           |
| ------------------------------------------------------ | ---------------------------- | ------------------------------------------------------------------------------------------ |
| **EU AI Act** (full enforcement for high-risk systems) | **August 2026** (5 months)   | Conformity assessment, traceability, transparency, documented accountability               |
| **SOX** (SEC cyber disclosure requirements)            | Already in effect            | AI agents that touch financial processes = SOX control risk. Need evidence controls exist. |
| **SOC 2** (Trust Services Criteria)                    | Ongoing, auditors asking NOW | "Auditable records for production execution in addition to AI decisions"                   |
| **ISO 42001** (AI management systems)                  | 2025+                        | Governance, risk management, documentation for AI systems                                  |

Source: SafePaaS ("2026: When Every AI Agent Becomes a SOX Risk"), Blaxel ("SOC 2 for AI Agents"), Teleport ("AI Agents Impact SOC 2 Trust Services"), Security Boulevard ("Compliance Frameworks for Agentic AI"), EU AI Risk conformity assessment guide.

This is not hypothetical. Auditors are already asking companies "how do you control your AI agents?" in 2026. The EU AI Act enforcement is 5 months away.

---

## Business Model

### Architecture: Local Hot Path + Zero-Knowledge Cloud

```
SDK (source-available, BSL license, on PyPI + GitHub):
  - Policy engine runs LOCALLY (hot path — no dependency on cloud)
  - Custom policies in Python (run on customer's machine)
  - Connectors call real APIs locally
  - Receipts generated + HMAC-signed locally
  - Receipts ENCRYPTED with customer's key before cloud upload
  - If cloud is down → agents keep working, receipts queue locally

Cloud (proprietary — the business):
  - Receives encrypted receipt blob + searchable metadata
  - CAN see: run_id, timestamp, decision, workflow, policy names
  - CANNOT see: payload contents, SQL queries, PII, business data
  - Append-only, immutable storage (tamper-proof)
  - HITL gates (approve/deny via signed email)
  - Compliance exports (SOC2, SOX, EU AI Act, ISO 42001)
  - Anomaly detection across agent fleet
  - Auditor API (read-only, metadata + signature verification)
  - Retention SLAs (1yr, 3yr, 7yr contractual)
```

### Why engineers trust it

- SDK is source-available — read every line, audit the policy engine
- Custom policies run on THEIR machine — they trust their own code
- Zero-knowledge encryption — Enact literally cannot read their data
- Same model as 1Password, Proton Mail, Signal

### Why Russell doesn't burn out

- SDK is BSL (source-available, NOT open source) — no PR review, no community management, no fork risk
- Hot path is local — if cloud goes down, agents keep working. No 3am pages.
- Ship releases on your own schedule, not the community's
- Focus energy on proprietary cloud (the revenue engine)

---

## Pricing

### Positioning shift

| Before                      | After                                     |
| --------------------------- | ----------------------------------------- |
| "Cool dev tool"             | "Independent audit infrastructure"        |
| Buyer: engineer             | Buyer: CISO/CFO                           |
| Budget: $200/mo credit card | Budget: $25K-100K/yr compliance line item |
| "Nice to have"              | Moving toward legally required            |

### Tiers

| Tier           | Price                     | Buyer                             | What                                                                                                                                      |
| -------------- | ------------------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **SDK**        | Free                      | Engineers evaluating              | Source-available SDK. Full local engine: policies, connectors, rollback, local receipts. Works without cloud. No account needed.          |
| **Cloud**      | $199/mo                   | Eng leads, small teams            | Zero-knowledge encrypted receipt storage, search, HITL gates, team dashboard, anomaly alerts. 50K runs/mo.                                |
| **Compliance** | $999/mo                   | Companies doing SOC2/SOX audits   | Everything in Cloud + compliance export templates (SOC2, SOX, EU AI Act), auditor API access, retention SLAs (3yr), dedicated onboarding. |
| **Enterprise** | Talk to us ($25K-100K/yr) | CFOs/CISOs at regulated companies | VPC deployment, 7yr retention, custom compliance templates, dedicated support, custom policy packs, SLA guarantees.                       |

The $199/mo tier gets engineers in the door. The real money is Compliance ($999/mo) and Enterprise ($25K-100K/yr) — those buyers have existing budget lines for exactly this problem.

### Revenue ramp (conservative)

| Month              | Milestone                                                   | MRR      |
| ------------------ | ----------------------------------------------------------- | -------- |
| Month 1 (Mar 2026) | License change + landing page + Show HN                     | $0       |
| Month 2            | First 5-10 SDK installs, 1-2 cloud trial signups            | $0-400   |
| Month 3            | First paying Cloud customer, start Compliance conversations | $199-600 |
| Month 6            | 5-10 Cloud customers, 1 Compliance customer                 | $2K-3K   |
| Month 9            | 15-20 Cloud, 3-5 Compliance, first Enterprise conversation  | $5K-8K   |
| Month 12           | 30+ Cloud, 5-10 Compliance, 1 Enterprise                    | $10K-15K |
| Month 18           | EU AI Act fully in effect → demand spike                    | $25K-50K |

These are conservative. One Enterprise deal at $50K/yr changes the picture overnight. The EU AI Act enforcement in August 2026 is the demand catalyst — every company with high-risk AI agents will need to demonstrate compliance.

---

## GTM Plan (Go-To-Market)

### Phase 1: Foundation (Week 1-2) — Do before anything public

1. **Change license** from MIT/Apache to Elastic License 2.0
   - Update `LICENSE` file ✅
   - Update `pyproject.toml` with new license classifier ✅
   - EL2 bars SaaS competitors from using Enact as a hosted service — stronger protection than BSL
   - No community to upset — do it now before anyone cares

2. **Build zero-knowledge encryption into SDK**
   - Add `encryption_key` param to `EnactClient`
   - Split receipt into metadata (searchable) + payload (encrypted)
   - Encrypt payload with AES-256-GCM before cloud push
   - Add async local queue (if cloud unreachable, queue locally, push later)
   - Update `cloud_client.py` to handle encrypted blobs
   - Estimate: 1-2 weeks

3. **Update cloud backend**
   - Accept encrypted blobs in receipt storage
   - Index only metadata for search
   - Add auditor API endpoint (read-only, metadata + signature verification)
   - Add append-only constraint (no UPDATE/DELETE on receipt storage)

4. **Revise landing page** (`index.html`)
   - New positioning: "Independent audit infrastructure for AI agents"
   - Lead with regulatory angle: EU AI Act, SOX, SOC 2
   - Zero-knowledge encryption as headline differentiator
   - New pricing section: 4 tiers (SDK free / Cloud $199 / Compliance $999 / Enterprise talk to us)
   - Remove "Open source core" language → "Source-available — read every line"
   - Add auditor trust diagram (three-party model)

5. **Update PyPI package**
   - New version (v0.5 or v1.0) with BSL license
   - Add encryption_key parameter
   - Update README with new positioning
   - Don't yank old versions — just deprecate

### Phase 2: Launch (Week 3) — Show HN

6. **Show HN post**
   - Title: "Show HN: Enact — zero-knowledge audit infrastructure for AI agents"
   - Hook: "EU AI Act enforcement is 5 months away. Your AI agents need an independent audit trail. We built one where we can't even read your data."
   - Link to landing page + GitHub
   - Demo: show the encryption flow (receipt generated locally → encrypted → pushed to cloud → cloud can search metadata but can't read payload)
   - Prepared responses for: "why not open source?" / "why BSL?" / "why not just log to S3?"

7. **Post on relevant communities**
   - LangChain Discord: "SOC 2 compliance for AI agents — how Enact works with LangChain"
   - Anthropic developer Discord: "audit trail for Claude agents"
   - r/devops, r/netsec: "EU AI Act compliance for autonomous agents"
   - dev.to / Hashnode: "Why your AI agents need an independent auditor"

### Phase 3: Content + Outreach (Week 4-8)

8. **SEO content** (each is a Google-indexed landing page)
   - "SOC 2 compliance for AI agents — the 2026 guide"
   - "EU AI Act: what it means for AI agent deployments"
   - "How to prove your AI agent only did what it was supposed to"
   - "Why MCP needs an independent audit layer"
   - "Zero-knowledge audit trails for autonomous systems"

9. **Direct enterprise outreach**
   - Target: companies that announced AI agent deployments (press releases, eng blogs)
   - Message: "You announced your agent deployment. EU AI Act enforcement is in [N] months. Here's the audit trail and independent verification layer you'll need."
   - Target: SOC 2 / SOX consultancies — offer Enact as a tool they recommend to clients
   - One Enterprise customer at $50K/yr pays for the year

10. **YC batch outreach**
    - ~50% of current YC batch are agent companies
    - They'll need compliance before Series A due diligence
    - Offer: "Free Cloud tier for 3 months in exchange for case study"

### Phase 4: Compliance Product (Month 2-4)

11. **Build compliance export templates**
    - SOC 2 Trust Services Criteria mapping (agent receipts → TSC evidence)
    - SOX control evidence package
    - EU AI Act conformity assessment documentation
    - ISO 42001 mapping
    - These templates are the $999/mo product — high value, moderate build effort

12. **Build auditor API**
    - Read-only API for external auditors
    - Metadata access (no encrypted content)
    - Signature verification endpoint
    - Time-range queries ("show all agent activities Q1 2026")
    - This is a CISO's dream — "here's the API key for your auditor, they can verify everything independently"

---

## Execution Checklist

### Week 1

- [x] Change LICENSE to Elastic License 2.0
- [x] Update pyproject.toml license field
- [x] Add encryption_key param to EnactClient
- [x] Implement receipt metadata/payload split (cloud_client.py splits metadata + encrypted payload)
- [x] Add AES-256-GCM encryption to cloud_client.py (enact/encryption.py)

### Week 2

- [x] Add local receipt queue (enact/local_queue.py — queues on failure, drains on next success)
- [x] Update cloud backend to accept encrypted blobs (cloud/routes/receipts.py)
- [x] Add append-only constraint to receipt storage
- [x] Write new landing page (new positioning, new pricing, auditor trust diagram)
- [x] Update README

### Week 3

- [ ] Publish enact-sdk v0.5 (or v1.0) to PyPI with BSL license
- [ ] Deploy updated landing page
- [ ] Submit Show HN
- [ ] Post to LangChain, Anthropic, devops communities

### Week 4-8

- [ ] Publish first SEO article (SOC 2 + AI agents)
- [ ] Start enterprise outreach (10 companies/week)
- [ ] Start YC batch outreach
- [ ] Begin compliance export template build

### Month 3-4

- [ ] Ship compliance export templates (SOC2, SOX, EU AI Act)
- [ ] Ship auditor API
- [ ] First Compliance tier customer

---

## Key Decisions Made

| Decision                             | Rationale                                                                                                                                   |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **Elastic License 2.0, not open source** | No community management burden, no fork risk, engineers can still read every line. Bars SaaS competitors from hosting Enact as a service. No existing community to upset. |
| **Hot path local, cold path cloud**  | No 3am pages for Russell (health constraint). Agents keep working if cloud is down.                                                         |
| **Zero-knowledge encryption**        | Nuclear trust signal. Differentiator vs every competitor. Solves "I don't trust a third party with my data" objection.                      |
| **Cloud = independent auditor**      | Not "convenience storage" — independent, tamper-proof, append-only audit infrastructure. This is what regulations will require.             |
| **$199 → $999 → Enterprise pricing** | Engineers enter at $199. Compliance buyers pay $999+. Enterprise/regulated companies pay $25K-100K/yr. Different buyers, different budgets. |

## Research Sources

- SafePaaS: "2026: When Every AI Agent Becomes a SOX Risk" (Feb 2026)
- Blaxel: "SOC 2 Compliance for AI Agents in 2026" (Feb 2026)
- Teleport: "How AI Agents Impact SOC 2 Trust Services Criteria" (Feb 2026)
- Security Boulevard: "Compliance and Audit Frameworks for Agentic AI Systems" (Jan 2026)
- AAIA: "Agentic Audit Trails: The Strategic Guide" (Jan 2026)
- EU AI Risk: "Conformity Assessment Guide" (Sep 2025)
- C&F: "Accountability, Transparency, Traceability for Trustworthy AI Agents" (Feb 2026)
- OpenView Partners: SaaS Benchmarks (developer tool conversion rates 1-3%)
- ChartMogul: 2026 Free-to-Paid Conversion Report (median 5.5% freemium)
- Aditya Pandey (PEXT): "Economics of Open Source Dev Tools" — hosted models monetize 40% faster
- Sid Sijbrandij (GitLab/OCV): "You need proprietary IP to monetize — it's not negotiable"
- Mike Perham (Sidekiq): open-core solo founder, ~$10M/yr revenue on $18/mo hosting
- Proton: zero-knowledge encryption architecture documentation
