# Visa GDO Demo: UX/UI Design Decisions

> **Goal:** A 90-second demo showing multi-agent data access automation that looks like it belongs in a Visa boardroom, not a hackathon.

## Design Principle: "Tufte meets Stripe"

**Core tension:** Data density vs. visual clarity  
**Resolution:** Show every field, every policy, every decision — but with strict hierarchy and generous spacing so it reads at a glance.

---

## Decision 1: Timeline Layout (not stacked cards)

### The Problem
Agent cards stacked vertically don't communicate sequential flow. Horizontal columns are too narrow for data-dense content.

### Recommendation: Vertical timeline rail

A green gradient line runs down the left side with checkmark dots at each agent. Cards attach to the right.

**Why:**
- Instantly communicates "these ran in sequence"
- Full card width for data-dense content (policy table, provisioning details)
- Dot colors change per outcome (green=done, amber=escalated, red=denied, gray=skipped)
- Same pattern used by GitHub, Linear, Stripe for activity feeds

---

## Decision 2: Persona Cards (not tabs)

### The Problem
Tabs labeled APPROVE/ESCALATE/DENY look like you're selecting the outcome, not demonstrating AI.

### Recommendation: Persona cards inside the request form

Three small cards below the "Run Workflow" button. Clicking fills the textarea with that persona's request. The AI parses whatever text is in the box.

**Personas:**
1. **Sarah Chen** — Senior Data Analyst — Read access to fraud models → Auto-Approve
2. **James Rodriguez** — Staff Data Scientist — Write access to PII data → Escalate
3. **Unknown User** — No role — Admin access to everything → Deny

**Demo move:** After showing scenario 1 (approve), manually edit "read" to "admin" in the textarea and re-run. This proves the AI responds to input, not pre-baked.

---

## Decision 3: Execution Type Badges

### The Problem
How to visually signal "this is real agent orchestration, not just if/else."

### Recommendation: Colored badges in card headers

Each agent card header shows:
- **Intake Agent** → `Claude Sonnet` (purple) + `847 tok · 320ms`
- **Policy Agent** → `Rule Engine` (blue) + `5 checks · 45ms`
- **Provisioning Agent** → `API Call` (green) + `180ms`
- **Notification Agent** → `API Call` (green) + `90ms`

**Why this matters:**
- Token counts prove real LLM calls
- "Rule Engine" shows deliberate architecture (not everything needs AI)
- Differentiated badge colors telegraph different execution types at a glance

---

## Decision 4: LLM Reasoning Trace

### The Problem
Extracted JSON output looks like it could be regex'd. Need to show the model *thought about it*.

### Recommendation: Purple reasoning block under Intake Agent

```
AGENT REASONING
Detected dataset: fraud_detection_models (exact catalog match, DS-001)
Inferred access_level: read from verb "analyze" confidence: 0.94
Justification quality: sufficient (62 chars, business context present)
Urgency: medium — no time-sensitive language detected
```

**Why:**
- Confidence scores are the money shot — no if/else produces those
- Shows the model reads context ("verb analyze → read access")
- Purple/lavender background differentiates from data output

---

## Decision 5: No ROI Banner in the App

### The Problem
Earlier version had a "2 min / 2-5 days / $780K / 5 Agents" banner.

### Recommendation: Remove it

ROI is narration, not UI. Russell says it during the demo. The app shows the *what*, the narrator provides the *so what*.

---

## Decision 6: No Architecture Ribbon

### The Problem
Considered a `LangGraph → Claude → Policy Engine → IAM → Email` ribbon between input and results.

### Recommendation: Skip it

The execution badges on each card already communicate the same info in context. The ribbon would be redundant and add visual clutter between the "Run" button and the results.

Use it in verbal narration instead.

---

## Decision 7: Audit Trail Design

### The Problem
JSON audit trail needs to look both professional and legible.

### Recommendation: Dark terminal aesthetic with syntax highlighting

- Dark slate background (#0c111d) with inner shadow
- Cyan keys, green agent names, gold values
- Sits outside the timeline (below, with its own label)
- Should start collapsed in the real app, expanded on click

---

## Visual Spec Summary

| Element | Value |
|---------|-------|
| Font (body) | DM Sans |
| Font (mono) | DM Mono |
| Header bg | Linear gradient #0a0e3d → #1A1F71 |
| Gold accent | #F7B600 |
| Background | #f4f5f9 + subtle radial gradients |
| Card shadow | 0 1px 3px rgba(0,0,0,.04), 0 4px 12px rgba(0,0,0,.03) |
| Green (pass) | #059669, bg #d1fae5 |
| Amber (escalate) | #d97706, bg #fef3c7 |
| Red (deny) | #dc2626, bg #fee2e2 |
| Timeline dot | 24px, gradient fill + outer glow shadow |
| Max width | 880px centered |
| Border radius | 10px (cards), 6px (buttons), 3px (badges) |

---

## Decision 8: Fraud Prevention + GDPR Metrics in ROI Report

### The Problem
The ROI report told a one-dimensional story: $780K/year from time savings. Matt Foreman (data science, fraud background) would want to see risk avoidance value. The system blocks unauthorized access and enforces regulatory compliance — that's potentially worth more than the time savings.

### Options Considered

**Option A: Insert between KPIs and Cost Comparison** — $780K hero stays, new "Risk & Compliance" section appears right below the 3 KPI cards.

**Option B: Inflate hero to $5.0M total** — Combine operational + risk + compliance into one hero number with a waterfall breakdown.

**Option C: Bury after Projected Annual section** — Put risk metrics further down, after charts.

### Recommendation: Option A

**Why:**
- **$780K is defensible math** (50 req/wk × 3 hrs × $100/hr × 52 wks). Inflating the hero with probabilistic risk numbers (Option B) would trigger a data scientist's bullshit detector.
- **Risk section needs visibility** — in a 90-second demo, Option C means Russell might not scroll there. But it shouldn't replace the concrete savings story.
- **"One more thing" narrative:** Russell says "$780K in pure operational savings..." then scrolls to: "...but the real value is risk avoidance: $5M total."

### What We Added

1. **Fraud & Breach Prevention card** (left)
   - 7 blocked this month / 84 projected annual / 0% unauthorized grants
   - Manual error rate 8.3% vs automated 0%
   - IBM citation: avg financial services breach $5.9M
   - Est. risk reduction: $1.8M/year (probability-adjusted)

2. **Regulatory Fine Avoidance card** (right)
   - ~12 manual compliance gaps/month → 0 automated
   - Four regulatory badges: GDPR (4% revenue), PCI DSS ($5K–$100K/mo), SOX (criminal), SEC 10b-5 ($millions+)
   - Est. fine avoidance: $2.4M/year (industry benchmark)

3. **Total Value Composition bar** (dark navy background)
   - Stacked bar: $780K operational (gold) + $1.8M fraud (blue) + $2.4M compliance (green)
   - $5.0M total in gold DM Mono, labeled "risk-adjusted annual"

**Credibility moves:**
- IBM citation grounds the breach cost in real research
- "probability-adjusted" and "industry benchmark" qualifiers show intellectual honesty
- $780K hero stat stays untouched — the conservative number leads
- Regulatory badges (GDPR/PCI/SOX/SEC) show knowledge of Visa's actual regulatory landscape

---

## File Reference

- **Visual prototype:** `plans/demo-prototype.html` (open in browser)
- **This doc:** `plans/ux-decisions.md`
- **Build spec:** `visa_data_approval_spec` (full code reference)
- **One-pager:** `visa_data_approval_one_pager` (demo script + scenarios)
