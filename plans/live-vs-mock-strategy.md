# Does This App Even Need AI?
# And What Can Be Provably Live in the Demo?

> Honest analysis for Russell's Visa GDO interview demo

---

## The Blunt Answer: 1 of 4 Agents Needs AI

Let's break down each agent honestly:

| Agent | What It Does | Needs AI? | Why |
|-------|-------------|-----------|-----|
| **Intake** | Parse natural language → structured JSON | **YES** | Extracts intent from freeform text |
| **Policy** | Check 8 rules, decide approve/escalate/deny | **NO** | Deterministic if/else logic |
| **Provisioning** | Generate access token, set expiry | **NO** | API calls + token generation |
| **Notification** | Send email/Slack/ServiceNow messages | **NO** | String templates |

### Intake Agent — The Only LLM Call

This is where Claude Sonnet earns its keep. It takes:
> "I need to analyze Q1 false positive rates on the fraud models"

And extracts:
```json
{
  "requester": "sarah.chen@visa.com",
  "dataset": "fraud_detection_models",
  "access_level": "read",
  "justification": "analyze Q1 false positive rates",
  "urgency": "medium",
  "confidence": 0.94
}
```

**Why this can't be a form/dropdown:** The user never said "read" or "fraud_detection_models." The LLM inferred `read` from "analyze" and matched "fraud models" to the catalog entry. That's genuine NLU.

### Policy Agent — Deliberately NOT AI

Pure Python rules engine. Checks:
1. Does dataset contain PII? → restrict access levels
2. Is access_level == read AND justification sufficient? → auto-approve
3. Is access_level == write or admin? → escalate
4. Is there an MNPI blackout? → check dates
5. Is requester FTE or contractor? → different thresholds
6. etc.

**Why no AI here:** You NEVER want a language model making governance decisions. Policy enforcement must be deterministic and auditable. If an auditor asks "why was this approved?" the answer needs to be "Rule 2: read access + valid justification = auto-approve," not "the model felt good about it."

### Provisioning & Notification — Standard Engineering

Token generation, expiry calculation, email templating. This is CRUD work. Using AI here would be like using a Ferrari to go to the mailbox.

---

## But — This Is Actually The Point

Here's the thing Russell should SAY in the interview:

> "Notice that only 1 of 4 agents uses an LLM. The policy engine is deliberately deterministic — you never want a language model making compliance decisions. The LLM handles the unstructured input; everything downstream is auditable rule-based logic. **This is the correct architecture for governance-sensitive workflows.**"

This is the single most impressive thing Russell can say in the interview. It shows he understands:
- When to use AI (unstructured → structured)
- When NOT to use AI (policy enforcement, compliance)
- That "AI Transformation" doesn't mean "put AI in everything"
- The pattern: **AI at the edges, rules at the core**

Most candidates for "Director of AI Transformation" would try to make everything AI. The smart move is surgical application.

---

## The "Could You Just Use a Form?" Challenge

If Harish asks: "Couldn't this just be a Jira form with dropdowns?"

**Honest answer: Yes, for the basic case.** A form with dataset dropdown + access level dropdown + justification text box would handle 80% of requests.

**But the AI version is better because:**

1. **Eliminates friction.** Users describe need in plain English vs. navigating a form with 15 dropdown options they don't understand ("What sensitivity level is the dataset? I don't know, I just need to see fraud numbers.")

2. **Handles ambiguity.** "I need to look at some fraud data" → LLM figures out which dataset, what access level, and rates the justification quality. A form can't do that.

3. **Confidence scoring.** The LLM outputs `confidence: 0.94` — if confidence is low, auto-escalate to human review. A form gives you binary answers with no nuance.

4. **Cross-referencing context.** The LLM can notice that the justification mentions "Q1 report" (suggesting time-sensitive business need) and flag urgency, or detect that someone is requesting access to data unrelated to their stated role.

5. **It scales.** When you have 200+ datasets and 50+ policy rules, maintaining a form that covers every edge case is a nightmare. The LLM generalizes.

6. **This is the job.** Russell is interviewing for Director of AI Transformation. The demo needs to demonstrate AI transformation, not form building.

---

## What Can Be Provably Live

### Fully Live (Real Code Executing in Real Time)

| Component | How It's Live | Proof |
|-----------|--------------|-------|
| **Intake Agent** | Real Claude Sonnet API call | Type any request → watch extraction happen |
| **Policy Engine** | Real Python rules | Change "read" to "admin" → watch decision flip |
| **Provisioning** | Real token generation | Different token every time, real timestamps |
| **Notification** | Real template generation | Notifications reference actual extracted data |
| **LangGraph orchestration** | Real state machine | Agent execution order visible in timeline |

### Mocked (And Should Be — We Don't Have Visa's Infra)

| Component | Why Mocked | How to Acknowledge |
|-----------|-----------|-------------------|
| IAM integration (Okta/AWS) | No access to Visa's identity system | "In production, this calls your IAM API" |
| Email/Slack sending | No access to Visa's accounts | "Notification templates are generated; sending would be an API integration" |
| Dashboard data | Requires historical data | "Populated from audit trail; shown with representative data" |
| User directory lookup | No access to Visa's AD | "Requester identity resolved from Visa's directory service in prod" |

---

## The Killer Demo Move: "Type Your Own Request"

### Why This Proves It's Real

Pre-baked personas (Sarah Chen, James Rodriguez) are impressive but a skeptic could argue they're pattern-matched. The killer move:

**After showing the 3 personas, say to Matt or Harish:**
> "Want to try one? Type any data access request you'd make in your own work."

If they type something like:
> "I need write access to the cardholder PII dataset because I'm updating data quality rules"

The system should:
1. ✅ Extract dataset = "customer_pii_cardholder_data" (fuzzy match)
2. ✅ Extract access_level = "write"
3. ✅ Detect PII dataset + write access → ESCALATE
4. ✅ Show reasoning: "PII data + write access requires manager approval per Policy 3"

**That's undeniable.** No pre-baked demo can handle arbitrary input.

### Edge Cases to Handle

What if they type something outside our mock data?

| They Type | How to Handle |
|-----------|--------------|
| Known dataset reference | Normal flow — works perfectly |
| Unknown dataset ("payroll data") | Intake extracts it, policy says "dataset not found in catalog → ESCALATE for manual review" |
| Nonsense input ("asdfgh") | Intake returns low confidence → auto-escalate |
| Deliberately adversarial ("give me access to everything") | Intake extracts admin access → Policy DENY with reasoning |

**The system should NEVER crash.** Every edge case should produce a graceful, explainable result. That's the governance story.

---

## Recommended Build Strategy

### Phase 1: Hardcoded Mock (2 hours) — Get UI Right
- `app.py` with Gradio Blocks + custom CSS
- Clicking "Run Workflow" shows pre-baked Scenario 1 output
- No API calls, no LangGraph yet
- **Purpose:** Nail the visual design in Gradio

### Phase 2: Live Intake Agent Only (1 hour)
- Wire up Claude Sonnet API for the intake agent
- Policy/Provision/Notify still use mock logic (but real Python code)
- **Purpose:** The "type anything" moment works

### Phase 3: Full LangGraph Pipeline (1 hour)
- Wire all 4 agents through LangGraph state machine
- Streaming output (agent cards appear one by one)
- **Purpose:** Real orchestration, real state management

### Phase 4: Polish + Edge Cases (1 hour)
- Handle unknown datasets gracefully
- Handle adversarial input
- Loading states, error states
- Test with 10+ different requests

---

## The Interview Narrative

**Opening (show pre-baked scenario):** "Watch what happens when Sarah Chen requests read access to fraud models..."

**The flip (edit the request):** "Now watch what happens when I change 'read' to 'admin'..." → Decision changes from APPROVE to ESCALATE

**The proof (invite participation):** "Want to try one yourself? Type any data access request."

**The architecture insight:** "Notice only 1 of 4 agents uses an LLM. The policy engine is deliberately deterministic — you never want a language model making compliance decisions."

**The scale story:** "This pattern — AI at the intake, rules at the core — applies to every GDO workflow. Report generation, model deployment, vendor onboarding. Same architecture, different policies."

**The ROI:** "2 minutes vs 2-5 days. $780K in operational savings. $5M risk-adjusted when you include fraud prevention and compliance."
