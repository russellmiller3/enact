# Visa GDO Current State: How Data Access *Actually* Works Today

> Reconstructing the existing workflow to inform system design

---

## The Likely Current Process (2-5 Day Timeline)

### Step 1: Sarah Realizes She Needs Data (Day 0, Morning)

**Context:** Sarah is building Q1 fraud report. She needs data but doesn't know:
- Which exact table/dataset name
- What columns are available
- Who owns the data
- What access level she needs

**What she does:**
1. Checks **internal wiki** or **Confluence** for data catalog → finds outdated docs
2. Asks colleague: "Hey, where's the fraud model performance data?"
3. Colleague says: "Check with Mike in Data Engineering, he knows the tables"
4. Slacks Mike Foster (manager): "Need fraud data for Q1 report, which table should I use?"

**Time elapsed: 2 hours** (if Mike responds quickly)

---

### Step 2: Discovery Hell (Day 0, Afternoon)

**Mike replies:**
> "Could be `fraud_detection_models` or `fraud_model_metrics`. What exactly do you need? Also check the GDO data catalog in ServiceNow."

**Sarah:**
- Opens ServiceNow catalog (if it exists)
- Finds 47 tables with "fraud" in the name
- No descriptions, or descriptions like "Fraud data table v2 (updated)"
- Still doesn't know which one has the metrics she needs

**She escalates to data steward:**
- Emails data governance team: "Which table has fraud model false positive rates for Q1?"
- Waits for response

**Time elapsed: +6 hours** (end of Day 0)

---

### Step 3: The Jira Ticket (Day 1, Morning)

**Sarah FINALLY knows she needs `fraud_detection_models.read`**

Now she follows the **"official process":**

1. Opens Jira project: **GDO-Data-Access-Requests**
2. Clicks **"Create Issue"** → Template loads with 15 fields:

```
REQUIRED FIELDS:
☐ Dataset Name: ________________
☐ Access Level: [Dropdown: Read / Write / Admin]
☐ Business Justification: ________________ (min 50 chars)
☐ Duration Needed: [Dropdown: 30 days / 90 days / 1 year / Permanent]
☐ Manager Name: ________________
☐ Cost Center: ________________
☐ Project Code: ________________
☐ Data Classification: [Dropdown: Public / Internal / Confidential / Restricted]
☐ Compliance Review Needed?: [Y/N]
☐ PII Expected?: [Y/N]
☐ MNPI Exposure?: [Y/N]
☐ Intended Use: [Dropdown: Analytics / ML Model / Reporting / Other]
☐ Will Data Leave Visa Network?: [Y/N]
☐ Third-Party Sharing?: [Y/N]
☐ Additional Notes: ________________
```

**Sarah's experience:**
- Knows 4 of these fields off the top of her head
- Googles "what is MNPI" (Material Non-Public Information)
- Doesn't know her cost center → looks up in HR system
- Doesn't know data classification → guesses "Confidential"
- Doesn't know if PII is in the table → puts "Maybe?"

**Time to fill form: 25 minutes**

Submits ticket: **GDO-4521**

**Time elapsed: Day 1, 10:30am**

---

### Step 4: The Queue (Day 1-2)

**What happens to the ticket:**

Jira ticket lands in queue with **73 other open requests**.

**Who processes it?**
- **Data Governance Analyst** (probably 2-3 people for entire GDO)
- They work tickets FIFO (first in, first out)
- Average processing time: 8 tickets/day
- Sarah's ticket is #74 in queue

**Sarah's ticket sits untouched for 36 hours.**

**Time elapsed: Day 2, 10:30pm** (still no human has looked at it)

---

### Step 5: Initial Review (Day 3, Morning)

**Governance Analyst (let's call her Lisa) picks up ticket:**

**Lisa's checklist:**
1. ✅ Is requester a valid employee? → checks Active Directory
2. ✅ Is dataset name valid? → checks catalog
3. ❌ Is business justification sufficient?
   - Sarah wrote: "Need for Q1 fraud report"
   - Lisa thinks: "That's vague. What report? Why do YOU need it vs your manager?"
4. ❌ Is data classification correct?
   - Sarah guessed "Confidential"
   - Lisa checks dataset metadata: actually "Restricted - PII Present"
5. ❌ Cost center field is blank (Sarah skipped it)

**Lisa updates ticket:**
> **Status: NEEDS INFO**
> 
> "Please provide:
> 1. More specific justification (which report? for what initiative?)
> 2. Your cost center code
> 3. Confirm you've completed PII handling training (dataset contains PII)
> 
> Ticket will be closed if no response in 3 business days."

**Sarah gets email notification at 2pm while in a meeting.**

**Time elapsed: Day 3, 2:00pm**

---

### Step 6: Back and Forth (Day 3-4)

**Sarah sees email at 5pm (after meeting marathon):**
- Updates ticket with more details
- Still doesn't know cost center → emails HR
- Checks training records → took PII training 18 months ago, might be expired

**Day 4, 10am:** HR replies with cost center
**Day 4, 11am:** Sarah updates Jira ticket
**Day 4, 2pm:** Lisa checks training system → Sarah's training is expired
**Day 4, 3pm:** Lisa comments: "You need to retake PII training (expired). Link: [...]"

**Sarah groans. Training is 45 minutes.**

**Time elapsed: Day 4, end of day**

---

### Step 7: Escalation (Day 5, Morning)

**Sarah has now:**
- ✅ Retaken training
- ✅ Updated justification
- ✅ Added cost center

**Lisa reviews again:**
- Everything looks good NOW
- But dataset has PII + Sarah wants READ access
- Per policy: **any PII access requires manager approval**

**Lisa escalates:**
- Assigns ticket to Sarah's manager (Mike Foster)
- Adds comment: "Please approve or deny within 2 business days"

**Mike is traveling. Auto-responder says: "Out of office until Feb 20."**

**Ticket waits another 3 days.**

**Time elapsed: Day 8**

---

### Step 8: Approval (Day 8)

**Mike returns, sees 47 unread Jira notifications:**
- Approves Sarah's ticket: "Approved - she's working on the quarterly fraud analysis"

**Lisa gets notification Day 8, 3pm**

---

### Step 9: Provisioning (Day 8-9)

**Lisa now needs to actually grant access:**

1. Opens internal tool (maybe Okta, AWS IAM, custom system)
2. Looks up Sarah's user ID
3. Grants `fraud_detection_models.read` permission
4. Sets expiry: 90 days
5. Generates credentials/token
6. Emails Sarah: "Access granted. Token: [...]"

**If the internal tool is down or has a bug:**
- Lisa manually files another ticket with InfoSec
- +2 more days

**Assuming no issues:** Access granted Day 9, 10am

**Time elapsed: 9 days from initial need, 5 business days from ticket creation**

---

## Current State Summary

### Timeline
```
Day 0:  Sarah realizes need → discovery process (asks around)
Day 1:  Sarah files Jira ticket (25 min form)
Day 2:  Ticket sits in queue
Day 3:  Lisa reviews → NEEDS INFO (missing fields)
Day 4:  Sarah updates → training expired → retakes training
Day 5:  Lisa re-reviews → escalates to manager
Day 6-7: Manager OOO
Day 8:  Manager approves
Day 9:  Lisa provisions access

TOTAL: 9 calendar days, ~5 business days from ticket submission
```

### Pain Points

| Actor | Pain Point |
|-------|-----------|
| **Sarah (Requester)** | - Doesn't know which table to request<br>- Form has 15 fields she doesn't understand<br>- Multiple back-and-forth cycles<br>- Can't do her job for a week |
| **Lisa (Governance)** | - Manual review of every ticket<br>- Same questions over and over (cost center, training status)<br>- Firefighting urgent requests<br>- No way to auto-approve simple read requests |
| **Mike (Manager)** | - Spammed with approval requests<br>- No context when approving (has to read Jira threads)<br>- Interrupt-driven work |

### Where Your System Fits

**Your system REPLACES:**
- ❌ The 15-field Jira form → Natural language textarea
- ❌ Manual field validation → Intake Agent extraction
- ❌ Manual policy checks → Policy Agent rules
- ❌ Manual provisioning steps → Provisioning Agent automation
- ❌ 36-hour queue time → 2-minute decision

**Your system KEEPS:**
- ✅ Human review for escalations (Lisa's job shifts to reviewing only edge cases)
- ✅ Manager approval for high-risk requests (but streamlined)
- ✅ Audit trail (even better than before)

---

## Answer to Your Question

**Is this Jira backend or direct use?**

**It's BOTH, in phases:**

### Phase 1 (MVP - Your Demo):
**Jira Replacement for Known Requests**

Sarah STILL discovers tables by asking around (that's a harder problem). But once she knows she needs `fraud_detection_models`, instead of:
- 15-field Jira form → She types: "I need read access to fraud_detection_models to analyze Q1 false positive rates"
- Her request gets processed in 2 minutes, not 5 days

**This is direct use of your UI** (not Jira backend). It's a replacement for the Jira ticket system.

### Phase 2 (Post-MVP):
**Add Discovery Agent**

Sarah doesn't know table name yet. She types:
> "I need fraud model performance metrics for Q1"

System replies:
> "I found 3 relevant datasets:
> - `fraud_detection_models` (model configs + performance, 2.3M rows)
> - `fraud_model_metrics` (daily perf logs, 45M rows) ← **likely match**
> - `fraud_training_results` (historical training runs, 800K rows)
> 
> Based on 'Q1 performance metrics', I recommend `fraud_model_metrics`. Want to see columns?"

This is the chatbot flow you mentioned. But it's v2.

---

## Updated System Design

**For your demo:** Direct use UI, assumes Sarah knows table name (realistic after discovery phase).

**Demo script:**
> "Right now, data access at Visa takes 5+ business days. A data analyst fills out a 15-field Jira form, waits in a queue, goes through back-and-forth reviews, manager approvals. 
>
> This system lets them describe what they need in plain English. Watch..."

Makes sense?
