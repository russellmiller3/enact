# Visa GDO Demo - Progress Tracker

## Context

Russell is interviewing for a **Director of AI Transformation** role at Visa's Global Data Office (GDO). The interviewers are:
- **Matt Foreman** — Data Science background, cares about measurable ROI and fraud-adjacent use cases
- **Harish Raghavendra** — Engineering background, cares about buildable/modular/scalable architecture

Russell is building a **working POC** of a multi-agent data access automation system to demonstrate what he'd build on the job. The demo needs to:
1. Show real AI orchestration (LangGraph + Claude Sonnet) that can't be faked
2. Show governance guardrails (policy enforcement, audit trails, human-in-the-loop)
3. Be presentable in a 90-second demo
4. Show a $780K/year ROI story (150 hrs/week saved at $100/hr blended)

**Demo script:** Type a request → 4 agents execute → access granted/escalated/denied with full audit trail. "2 minutes vs 2-5 days. $780k/year ROI. This pattern scales to every GDO workflow."

---

## What Exists (4 HTML prototypes + design doc, all working)

### Screen 1: `plans/demo-prototype.html` — Request Workflow ✅ INTERACTIVE
- Premium Visa-branded header (navy gradient + gold accent)
- 3 persona cards (Sarah Chen/James Rodriguez/Unknown User) populate textarea on click
- JS animation engine: clicking "Run Workflow" triggers staggered card reveals with streaming text
- Timeline rail with 4 agents (Intake → Policy → Provision → Notify)
- 8 policy checks: PII, Read Auto-Approve, Write/Admin Escalation, Time-Limited, Employment Type (FTE/Contractor), MNPI Blackout, InfoSec
- Execution badges: `Claude Sonnet` (847 tok) / `Rule Engine` (8 checks) / `API Call`
- LLM reasoning trace with `confidence: 0.94`
- Multi-channel notifications: Email + Slack + ServiceNow
- Live timestamps using actual clock
- All 3 scenarios work: Approve, Escalate, Deny

### Screen 2: `plans/dashboard-prototype.html` — Governance Dashboard ✅ STATIC
- KPIs: 127 requests / 89 approved / 31 escalated / 7 denied
- Policy trigger heatmap, anomaly detection, compliance scorecard
- Department breakdown, FTE vs Contractor, integration health

### Screen 3: `plans/review-prototype.html` — Human Review Queue ✅ STATIC
- Escalation cards with AI recommendation + confidence scores
- Approve/Deny/Return buttons + RLHF feedback (Good/Bad/Policy update + free text)
- Spot check cards for auto-approved decisions
- "47 labels this month → prompt v2.3 deployed" retraining story

### Screen 4: `plans/roi-prototype.html` — ROI Report ✅ STATIC
- $780K hero stat, $65K/month, 1,875 hours reclaimed
- **NEW: Risk & Compliance Value section** — fraud prevention ($1.8M) + regulatory fine avoidance ($2.4M)
- **NEW: Total Value Composition bar** — dark navy stacked bar showing $5.0M risk-adjusted total
- Fraud card: 7 blocked, 84/yr projected, 0% unauthorized grants, IBM $5.9M breach citation
- Regulatory card: GDPR/PCI DSS/SOX/SEC badges with fine exposure, ~12→0 compliance gaps
- Cost comparison: $320 manual vs $0.47 automated
- Monthly trend chart, projection bars ($780K → $1.2M → $3.8M)
- Model quality metrics + feedback loop

### Design Doc: `plans/ux-decisions.md` ✅
- 8 design decisions documented with reasoning (added Decision 8: Risk & Compliance metrics)

---

## Design Decisions (Summary)

- **Timeline rail** (not stacked cards) — shows sequential agent flow
- **Persona cards** (not tabs) — proves AI isn't pre-baked, enables "change one word" demo move
- **Execution badges** — Claude Sonnet/Rule Engine/API Call differentiation
- **8 policies** including MNPI Blackout (SEC compliance) and FTE/Contractor
- **Streaming text** — char-by-char build simulates real LLM output
- **Live timestamps** — actual clock, not hardcoded
- **No ROI banner** in app — that's narration, not UI
- **Slack + ServiceNow** alongside email for enterprise credibility

## Visual Spec

| Element | Value |
|---------|-------|
| Font body | DM Sans |
| Font mono | DM Mono |
| Header | Gradient #0a0e3d → #1A1F71 |
| Gold accent | #F7B600 |
| Green/Amber/Red | #059669 / #d97706 / #dc2626 |
| Max width | 880px |

---

## What's Next

1. ~~**Add fraud prevention + GDPR fine avoidance** to ROI report~~ ✅ DONE — Added Risk & Compliance section with fraud prevention ($1.8M), regulatory badges (GDPR/PCI/SOX/SEC), and $5.0M total value composition bar
2. **Build the real Gradio app** (`app.py`) matching this design with actual Claude API calls + LangGraph orchestration
3. **Tech stack:** Python + LangGraph + Claude Sonnet + Gradio Blocks + custom CSS

## Reference Docs (in workspace root)
- `PLAN.md` — Build order (outside-in: UI first → backend)
- `visa_data_approval_one_pager` — Demo script, mock requests, talking points
- `visa_data_approval_spec` — Full step-by-step build guide with code examples
