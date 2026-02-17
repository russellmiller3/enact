# The Discovery Problem: Does It Belong in MVP?

> Russell's question: "How much time does this actually save if Sarah still wrestles with discovery?"

---

## Breaking Down the 9-Day Timeline

| Phase | Current Time | With Your System | Time Saved |
|-------|-------------|------------------|------------|
| **Discovery** (asking colleagues, searching for table names) | 2-8 hours | 2-8 hours | **0 hours** ❌ |
| **Form filling** (15-field Jira form) | 25 minutes | 2 minutes | 23 minutes ✅ |
| **Queue wait** (ticket sits unprocessed) | 36 hours | 0 | 36 hours ✅ |
| **Review cycles** (back-and-forth on missing info) | 2-3 days | 0 (auto-approve) | 2-3 days ✅ |
| **Manager approval wait** (for escalations) | 0-3 days | 0-3 days | **0** ❌ |
| **Provisioning** (manual IAM steps) | 30 minutes | instant | 30 minutes ✅ |

**Honest answer:** Your current system saves **~3.5 days** for auto-approved requests, but does **nothing** for discovery.

---

## Where the ROI Actually Comes From

### Sarah's Time Saved (Per Request)
- **Current active time:** 2 hrs discovery + 25 min form + 15 min training check + 5 min responding to Lisa = **~3 hours**
- **With your system:** 2 hrs discovery + 2 min request = **~2 hours**
- **Saved:** 1 hour per request

### Lisa's Time Saved (Governance Analyst)
- **Current:** 15 min review + 10 min re-review + 10 min escalation routing + 20 min provisioning = **55 min per request**
- **With your system (auto-approved):** 0 min
- **With your system (escalated):** 10 min review only
- **Saved:** 55 min for auto-approved, 45 min for escalated

### The Real Savings
If 70% of requests are auto-approved (127/month from dashboard):
- Sarah's team: 1 hr × 127 requests/month = 127 hrs/month saved
- Lisa's team: 55 min × 89 auto-approved + 45 min × 38 escalated = **110 hrs/month saved**

**Total: 237 hrs/month or ~55 hrs/week**

That's **lower** than your claimed 150 hrs/week. The $780K ROI assumes you're processing **more volume** OR counting wait time as "opportunity cost."

---

## The Discovery Problem: Three Options

### Option 1: Ignore It (Current Plan)
**What you'd say in the demo:**
> "Discovery—finding the right table—is a separate problem. Most experienced analysts already know which tables they need from prior work. This system solves the **approval bottleneck**, which is where 90% of the wait time happens."

**Pros:**
- Accurate (discovery IS separate from approval)
- Keeps scope tight
- 2-3 hours to finish backend

**Cons:**
- Feels incomplete ("but what about discovery?")
- Weaker ROI story (only saves ~55 hrs/week for approval automation)

---

### Option 2: Full Discovery Flow (Catalog Browser + Multi-Turn Chat)
**Add to the system:**
```
┌─────────────────────────────────────────┐
│ Search: "fraud model performance data"  │ 
└─────────────────────────────────────────┘
          ↓
┌─────────────────────────────────────────┐
│ Found 3 datasets:                       │
│                                         │
│ ✓ fraud_detection_models               │
│   Model definitions + accuracy metrics  │
│   2.3M rows, 47 columns, Restricted     │
│   [View Columns] [Request Access]      │
│                                         │
│ ○ fraud_training_data                  │
│   Historical transactions for training  │
│   180M rows, 89 columns, Highly Res.   │
│                                         │
│ ○ fraud_model_metrics                  │
│   Daily performance logs                │
│   45M rows, 23 columns, Internal        │
└─────────────────────────────────────────┘
```

Then multi-turn conversation:
- Sarah: "Show me columns for fraud_model_metrics"
- System: [Lists 23 columns with descriptions]
- Sarah: "I need read access to that"
- System: [Runs workflow]

**Pros:**
- Solves the FULL problem (discovery + approval)
- Much stronger ROI (saves discovery time too)
- More impressive demo

**Cons:**
- 4-5 more hours of work (catalog data structure, search endpoint, UI for results)
- Out of scope for 90-second demo timeline

---

### Option 3: Smart Fuzzy Matching (Middle Ground) ⭐ RECOMMENDED

**Add to Intake Agent:**

Sarah types vague request:
> "I need fraud data for Q1 analysis"

Intake Agent (Claude) responds in reasoning trace:
```
Detected ambiguous dataset reference: "fraud data"
Catalog search found 3 matches:
  • fraud_detection_models (exact match: "fraud", likely for analysis)
  • fraud_training_data (exact match: "fraud", large volume, unlikely for simple analysis)
  • fraud_model_metrics (exact match: "fraud", time-series data)

Recommendation: fraud_detection_models (confidence: 0.72, LOW)
Action: ESCALATE with suggestions for human confirmation
```

System shows in results:
```
⚠️ ESCALATED FOR REVIEW

Reasoning:
- Dataset reference "fraud data" is ambiguous
- Found 3 possible matches: fraud_detection_models, 
  fraud_training_data, fraud_model_metrics
- Recommend human confirmation of which table is needed

Suggested next step: Requester should clarify which specific 
dataset or governance analyst can route via Slack
```

**How it works:**
- Intake Agent does fuzzy catalog search (simple string matching against dataset names + descriptions)
- If confidence is low (<0.85), auto-escalate with suggestions
- Human reviewer (Lisa) or requester (Sarah) clarifies
- One round of back-and-forth, still beats 5-day process

**Pros:**
- Acknowledges discovery problem
- Provides HELPFUL escalation (not just "request denied")
- Only ~1 hour of extra work (add catalog to Intake Agent prompt, add low-confidence escalation logic)
- Demo-able: "Watch what happens when someone's vague about the table..."

**Cons:**
- Still requires human in the loop for ambiguous requests
- Doesn't fully solve discovery (no catalog browser)

---

## My Recommendation: Option 3

Here's why:

1. **It's honest about the problem.** Discovery IS hard. Your system acknowledges it and helps.

2. **It makes the AI more impressive.** Showing the system say "I found 3 possible matches, but I'm not confident—escalating with suggestions" is BETTER than showing it blindly extract the wrong table.

3. **It's buildable in 1 hour.** Just enhance the Intake Agent prompt with catalog context and add confidence thresholds.

4. **It improves the demo narrative:**
   > "Watch what happens when Sarah's vague about which table she needs..."
   > 
   > [Types: "I need fraud data for analysis"]
   > 
   > [System extracts, sees low confidence, escalates with suggestions]
   > 
   > "The system doesn't guess—it flags ambiguity and suggests options. The governance analyst sees this in the review queue and routes Sarah to the right table via Slack. One 5-minute interaction instead of 3 days of back-and-forth."

5. **It strengthens the ROI story** because now you're also saving DISCOVERY time for ambiguous requests (Lisa helps route in 5 min vs Sarah spending 2 hours asking around).

---

## Updated ROI With Smart Fuzzy Matching

**Assumptions:**
- 30% of requests are ambiguous (don't specify exact table name)
- Discovery currently takes 2-4 hours of asking around
- With smart escalation + Lisa routing via Slack: 5 minutes

**Additional savings:**
- 30% of 127 requests = 38 ambiguous requests/month
- 38 × 3 hours saved = 114 hours/month = **26 hrs/week**

**New total savings:**
- 55 hrs/week (approval automation) + 26 hrs/week (smarter discovery) = **81 hrs/week**
- Still not 150 hrs/week, but closer

**To hit 150 hrs/week:** You'd need to process more volume OR count manager time saved OR include other workflow improvements.

---

## Implementation: What to Add

### 1. Enhance `agents/intake.py` (30 min)

Add catalog context to prompt:
```python
DATASET_CATALOG = [
    {"id": "DS-001", "name": "fraud_detection_models", "description": "ML model definitions and performance metrics", "tags": ["fraud", "ml", "models"]},
    {"id": "DS-002", "name": "fraud_training_data", "description": "Historical transaction data for model training", "tags": ["fraud", "training", "transactions"]},
    {"id": "DS-003", "name": "customer_pii_cardholder_data", "description": "Cardholder personally identifiable information", "tags": ["pii", "customer", "restricted"]},
    # ... 10-15 more datasets
]

prompt = f"""
You are extracting structured data from a data access request.

Available datasets:
{json.dumps(DATASET_CATALOG, indent=2)}

User request: "{request_text}"

Extract:
- dataset: exact dataset name from catalog (or null if ambiguous)
- dataset_matches: list of possible matches if ambiguous
- access_level: read/write/admin
- justification: the stated reason
- confidence: 0.0-1.0 score
- ambiguity_reason: why dataset is unclear (if confidence < 0.85)

If the user's request doesn't match a dataset exactly, find the closest matches and set confidence < 0.85.
"""
```

### 2. Add Escalation Logic in `agents/policy.py` (15 min)

```python
if extracted["confidence"] < 0.85:
    return {
        "decision": "ESCALATE",
        "reason": "Low confidence in dataset extraction",
        "suggested_datasets": extracted["dataset_matches"],
        "next_step": "Human reviewer should confirm dataset with requester"
    }
```

### 3. Update UI to Show Suggestions (15 min)

In the escalation card, show:
```
⚠️ ESCALATED

❌ Dataset reference "fraud data" is ambiguous (confidence: 0.72)

Possible matches:
  • fraud_detection_models — ML model definitions + metrics
  • fraud_training_data — Historical transactions (180M rows)
  • fraud_model_metrics — Daily performance logs

→ Governance analyst should confirm with requester which table is needed
```

**Total time: 1 hour**

---

## What Do You Think?

Should we add Option 3 (smart fuzzy matching) to the MVP, or keep it dead simple and just acknowledge discovery as a separate problem?
