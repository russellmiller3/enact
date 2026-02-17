# Self-Service Discovery: Don't Shift Work to Governance

> Russell's objection to Option 3: "Seems like it pushes more work on governance team"

---

## You're Absolutely Right

**Current state (no system):**
- Sarah spends 2-8 hours asking colleagues/searching wikis for table names
- Discovery work is **distributed** (colleagues help when available)

**Option 3 (smart fuzzy matching → escalate to Lisa):**
- Sarah types vague request
- System escalates: "Lisa, I found 3 tables, please confirm which one"
- Discovery work is now **centralized** on Lisa → she becomes the bottleneck

**This is WORSE.** We've made Lisa the single point of contact for all discovery questions. She already has a queue of 73 tickets.

---

## The Real Solution: Self-Service Discovery

Instead of escalating to a human, **show the suggestions directly to Sarah and let her pick.**

### Flow Diagram

```
Sarah types: "I need fraud data for Q1 analysis"
         ↓
   [Submit Request]
         ↓
Intake Agent extracts:
  - dataset: ambiguous (confidence: 0.68)
  - Found 3 matches in catalog
         ↓
┌───────────────────────────────────────────────┐
│ 🔍 I found multiple datasets matching         │
│    "fraud data". Which do you need?          │
│                                               │
│ ○ fraud_detection_models                     │
│   ML model definitions + performance metrics  │
│   2.3M rows • 47 columns • Restricted        │
│   Common use: Model analysis, accuracy       │
│                                               │
│ ○ fraud_training_data                        │
│   Historical transactions for training        │
│   180M rows • 89 columns • Highly Restricted │
│   Common use: ML model training              │
│                                               │
│ ○ fraud_model_metrics                        │
│   Daily performance logs + KPIs               │
│   45M rows • 23 columns • Internal           │
│   Common use: Monitoring, dashboards         │
│                                               │
│        [Select and Continue] [Cancel]        │
└───────────────────────────────────────────────┘
         ↓
Sarah clicks "fraud_model_metrics"
         ↓
Request auto-updates with clarified dataset
         ↓
Workflow runs normally (Intake → Policy → etc.)
```

**No human in the loop.** Sarah does her own discovery with AI assistance.

---

## What Changed From Option 3

| Aspect | Option 3 (Bad) | Self-Service (Good) |
|--------|---------------|---------------------|
| **Ambiguity detection** | ✅ Intake Agent finds 3 matches | ✅ Same |
| **Next step** | ❌ Escalate to Lisa for routing | ✅ Show Sarah the options directly |
| **Lisa's workload** | ❌ Increases (she routes all ambiguous requests) | ✅ Decreases (Sarah self-serves) |
| **Sarah's experience** | ⚠️ Waits for Lisa to reply | ✅ Instant clarification, picks herself |
| **Time saved** | ⚠️ 2 hrs → 10 min (Lisa routing) | ✅ 2 hrs → 30 sec (Sarah picks) |

---

## Time Savings (Updated)

**Discovery phase:**
- **Current:** 2-8 hours asking around → eventually someone tells her the table name
- **With self-service:** 30 seconds reading AI suggestions → clicks one → done

**Savings per ambiguous request:** ~3 hours average

**Volume:**
- 30% of requests are ambiguous (don't specify exact table)
- 127 requests/month × 30% = 38 ambiguous requests/month
- 38 × 3 hours = **114 hrs/month = 26 hrs/week saved**

**Governance team:**
- Lisa's workload DECREASES because she's no longer routing discovery questions
- She only reviews true escalations (policy violations, high-risk access)

**New ROI:**
- Approval automation: 55 hrs/week
- Discovery self-service: 26 hrs/week
- **Total: 81 hrs/week**

Still not 150 hrs/week (that number might be inflated), but much more defensible.

---

## UX Design: Disambiguation Screen

### Wireframe (ASCII)

```
┌────────────────────────────────────────────────────────────────┐
│  Visa GDO — Data Access Request                       [×]      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Your Request:                                                 │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ I need fraud data for Q1 analysis                        │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                │
│  🔍  I found 3 datasets matching "fraud data"                 │
│      Please select which you need:                            │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  ○  fraud_detection_models                      DS-001   │ │
│  │                                                           │ │
│  │     ML model definitions and performance metrics         │ │
│  │     2.3M rows • 47 columns • Restricted                  │ │
│  │     Common for: Model analysis, accuracy tracking        │ │
│  │                                                           │ │
│  │     Owner: Data Science Team                             │ │
│  │     Last updated: 2026-02-15                             │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  ○  fraud_training_data                         DS-008   │ │
│  │                                                           │ │
│  │     Historical transaction data for model training       │ │
│  │     180M rows • 89 columns • Highly Restricted           │ │
│  │     Common for: ML model training, feature engineering   │ │
│  │                                                           │ │
│  │     Owner: Fraud Prevention Team                         │ │
│  │     ⚠️  Requires additional PII training                 │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  ○  fraud_model_metrics                         DS-012   │ │
│  │                                                           │ │
│  │     Daily performance logs and KPIs                      │ │
│  │     45M rows • 23 columns • Internal                     │ │
│  │     Common for: Monitoring dashboards, reporting         │ │
│  │                                                           │ │
│  │     Owner: Analytics Team                                │ │
│  │     Last updated: 2026-02-16 (today)                     │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌─────────────────────────────────────────┐                  │
│  │  Can't find what you need?              │                  │
│  │  Try searching by table name or owner   │  [Search]        │
│  └─────────────────────────────────────────┘                  │
│                                                                │
│                           [Cancel]  [Continue with Selection] │
└────────────────────────────────────────────────────────────────┘
```

### HTML Mockup (Interactive)

I can build a quick HTML prototype of this disambiguation screen so you can click through the flow. Want me to?

---

## Implementation Complexity

| Component | Time | Difficulty |
|-----------|------|-----------|
| **Intake Agent: catalog search** | 30 min | Easy (add dataset list to prompt, return matches) |
| **Backend: disambiguation endpoint** | 20 min | Easy (return multiple matches as JSON) |
| **Frontend: disambiguation modal** | 1 hour | Medium (radio buttons → re-submit flow) |
| **Testing: edge cases** | 30 min | Easy (0 matches, 1 match, 10+ matches) |

**Total: ~2 hours** (vs 4-5 hours for full catalog browser)

---

## Edge Cases

### What if 0 matches?
```
🔍  I couldn't find any datasets matching "payroll data"

The GDO catalog doesn't include payroll datasets. This request
will be escalated to the governance team for manual review.

Possible reasons:
• Dataset exists but isn't cataloged yet
• Dataset is managed by a different team (HR, Finance)
• Dataset name is misspelled

[Submit for Manual Review]  [Edit Request]
```

### What if 1 exact match?
Skip disambiguation entirely. Proceed directly to workflow.

**User types:** "I need read access to fraud_detection_models"
→ Intake extracts exact match (confidence: 0.98)
→ No disambiguation needed
→ Workflow runs

### What if 10+ matches?
Show top 5 most relevant (ranked by AI) + "See all 12 matches" expansion.

---

## Demo Impact

**Before (Option 3):** 
> "When the request is ambiguous, the system escalates to a human reviewer..."
→ Interviewer thinks: "So it's not that smart, still needs humans"

**After (Self-Service):**
> "Watch what happens when Sarah's vague about which table she needs..."
>
> [Types: "I need fraud data"]
>
> [System instantly shows 3 options with descriptions]
>
> "The AI searches the catalog, ranks matches, and shows Sarah the options. She picks one in 30 seconds instead of asking around for 2 hours. No governance team involvement needed."

**Much stronger story.** Shows AI being HELPFUL without pretending to be omniscient.

---

## Comparison to Jira Form Dropdowns

**Why not just add a dropdown to the Jira form?**

Jira form with 200+ datasets in a dropdown:
```
Dataset Name: [Select...]
  ▼ account_balance_daily
  ▼ account_lifecycle_events
  ▼ atm_transaction_logs
  ▼ auth_failures_analytics
  ...
  ▼ fraud_detection_models        ← Sarah scrolls for 30 sec
  ▼ fraud_feature_store
  ▼ fraud_training_data
  ...
  ▼ zzz_test_dataset_old
```

**Problems:**
- Sarah doesn't know which one she needs (same discovery problem)
- No context (what's the difference between fraud_detection_models and fraud_model_metrics?)
- Alphabetical sort is useless
- No search/filter

**Your system:**
- Sarah types natural language
- AI interprets intent
- Shows ONLY relevant options with descriptions
- Helps her make an informed choice

That's the AI value add.

---

## My Updated Recommendation

**Build self-service discovery (2 hours):**

1. Enhance Intake Agent to search catalog and return top 3 matches
2. If confidence < 0.85 → return disambiguation options to frontend
3. Show modal with radio buttons + dataset cards
4. Sarah picks → re-submit with clarified dataset → workflow runs

**This is WAY better than:**
- Option 1 (ignoring discovery) — incomplete
- Option 3 (escalating to Lisa) — shifts work to governance
- Option 2 (full catalog browser) — too much scope

**And it's only 2 hours of work.**

Want me to mock up the disambiguation screen in HTML so you can see the interaction?
