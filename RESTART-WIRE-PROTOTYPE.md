# RESTART: Wire Demo Prototype to Live Backend

## 🔴 STOP! READ /.roo/roorules FIRST

**REFERENCE FILES (read first, in order):**
1. RESTART-FRONTEND.md - Previous frontend work (basic SSE works!)
2. This file - Current handoff

**BRANCH:** main (no feature branch)
**COST SO FAR:** $4.41 (current session: got basic SSE working)

---

## ✅ COMPLETED

### Backend Infrastructure ✅
- FastAPI server running at http://localhost:8000
- 5 agents working (Discovery, Intake, Policy, Provision, Notify)
- SSE streaming endpoint: `/api/stream_workflow`
- JSON serialization fixed (was sending Python dicts, now sends valid JSON)
- Backend sends events: `discovery`, `intake`, `policy`, `provision`, `notify`, `audit`, `done`

### Basic Frontend ✅  
- Created `frontend/index.html` with basic SSE connection
- **VERIFIED WORKING:** All 5 agents stream correctly
- EventSource connects successfully
- Auto-selects top dataset when multiple matches found
- Console shows all events with valid JSON
- **Test passed:** Sarah Chen → fraud_detection_models → APPROVE workflow

**Test log from browser console:**
```
Discovery event: {"agent": "DiscoveryAgent", "match_count": 2, ...}
Multiple matches found (2). Auto-selecting top match: fraud_detection_models
Intake event: {"agent": "IntakeAgent", "access_level": "read", ...}
Policy event: {"agent": "ABACPolicyEngine", "decision": "APPROVE", ...}
Provision event: {"agent": "ProvisioningAgent", "token": "eyJh...", ...}
Notify event: {"agent": "NotificationAgent", "channels": [...], ...}
```

### Prototype Copied ✅
- **File:** `frontend/workflow.html` (copied from `plans/demo-prototype.html`)
- Beautiful Visa UI with timeline animations
- Mock data currently (needs to be replaced with real SSE)

---

## 🎯 CURRENT STATE

### What Works
1. **Backend streaming:** Events flow correctly via SSE
2. **Data format:** Valid JSON with all fields needed
3. **Basic UI:** Simple HTML displays raw JSON successfully
4. **Prototype HTML/CSS:** Gorgeous UI exists but uses mock data

### What Doesn't Work Yet
- ❌ `frontend/workflow.html` still uses mock SCENARIOS data
- ❌ No connection between prototype UI and real backend
- ❌ Timeline animations triggered by setTimeout, not real events

---

## 🚀 NEXT ACTIONS

### Goal
Wire `frontend/workflow.html` to real backend SSE stream while **keeping all the beautiful UI/animations**.

### Strategy: Surgical Replacement

**Keep (don't touch):**
- All HTML structure (timeline, cards, badges)
- All CSS styling
- Animation functions: `streamText()`, card rendering, timeline transitions
- UI helper functions

**Replace:**
- Mock `SCENARIOS` data → real EventSource data
- `setTimeout` delays → event-driven rendering
- Hard-coded values → data from SSE events

### Step-by-Step Plan

1. **Find the mock data section** (lines ~550-750)
   - Search for `const SCENARIOS = {`
   - This is the mock data we'll replace

2. **Find the runWorkflow function** (line 799+)
   - Currently: loops through mock data with setTimeout
   - New: opens EventSource, listens for events

3. **Create mapping:** Backend JSON → UI rendering functions
   ```
   Backend Event          → UI Function to Call
   ==========================================
   'intake' event         → renderIntakeCard(data)
   'policy' event         → renderPolicyCard(data)  
   'provision' event      → renderProvisionCard(data)
   'notify' event         → renderNotifyCard(data)
   'done' event           → showComplete(data)
   ```

4. **Test each agent separately**
   - Wire intake first, verify card renders
   - Add policy, verify badges show (green/amber/red)
   - Add provision, verify token displays
   - Add notify, verify channels list
   - Add done event, verify timeline completes

---

## 📋 KEY FILES

### Backend (Already Working)
```
backend/server.py
├── Line 72-73: SSE event formatting (JSON.dumps added)
└── Endpoint: GET /api/stream_workflow?request_text=...&requester_email=...

backend/workflow.py
├── Line 38: yields ('discovery', discovery_result.model_dump())
├── Line 64: yields ('intake', intake_result.model_dump())
├── Line 74: yields ('policy', policy_result.model_dump())
├── Line 94: yields ('provision', provision_result.model_dump())
├── Line 109: yields ('notify', notify_result.model_dump())
├── Line 130: yields ('audit', audit_result.model_dump())
└── Line 154: yields ('done', complete_data.model_dump())
```

### Frontend (Needs Modification)
```
frontend/workflow.html (copied from plans/demo-prototype.html)
├── Lines 1-550: HTML/CSS (KEEP AS IS)
├── Lines 550-750: Mock SCENARIOS data (DELETE)
├── Lines 750-770: Helper functions (KEEP)
├── Lines 777-1100: runWorkflow() mock loop (REPLACE)
└── Lines 1100-1188: Initialization code (KEEP)
```

### Reference (Original Prototype)
```
plans/demo-prototype.html
└── Use as reference for UI function names/structure
```

---

## 🔍 BACKEND EVENT STRUCTURE

### Example: Intake Event
```json
{
  "agent": "IntakeAgent",
  "status": "complete",
  "duration_ms": 4569,
  "tokens": 559,
  "extracted": {
    "requester": "analyst@visa.com",
    "dataset": "fraud_detection_models",
    "access_level": "read",
    "justification": "Fraud detection models needed for analysis",
    "urgency": null,
    "confidence": 0.85
  },
  "reasoning": [
    "Step 1: Identified verb 'analysis'...",
    "Step 2: Extracted justification...",
    ...
  ]
}
```

### Example: Policy Event  
```json
{
  "agent": "ABACPolicyEngine",
  "status": "complete",
  "duration_ms": 0,
  "checks_run": 8,
  "abac_checks": [
    {
      "policy": "Role Authorization",
      "requirement": "One of: [Data Analyst...]",
      "user_value": "Senior Data Analyst",
      "match": true,
      "badge": "g"  // ← "g"=green, "a"=amber, "r"=red
    },
    ...
  ],
  "decision": "APPROVE"  // or "ESCALATE" or "DENY"
}
```

---

## 🎨 UI RENDERING TARGETS

### Cards to Render
1. **Intake Card** - Shows extracted fields (requester, dataset, access_level, justification)
2. **Policy Card** - Shows 8 ABAC check badges (green ✓/amber !/red ✗)
3. **Provision Card** - Shows JWT token + expiry date
4. **Notify Card** - Shows 4 notification channels
5. **Complete Card** - Shows final decision + stats

### Badge Colors (from backend)
- `badge: "g"` → green checkmark ✓
- `badge: "a"` → amber warning !
- `badge: "r"` → red X ✗

---

## ✅ SUCCESS CRITERIA

**Done when:**

1. ✅ Open `frontend/workflow.html` in browser
2. ✅ Click "Run Workflow" button
3. ✅ See timeline animate with real data from backend
4. ✅ See 5 agent cards appear one by one
5. ✅ See Policy card shows 8 badges (all green for Sarah Chen)
6. ✅ See JWT token in Provision card
7. ✅ See notification channels in Notify card
8. ✅ No console errors
9. ✅ Timeline completes with "APPROVED" result

**Test scenario:**
- User: analyst@visa.com (Sarah Chen)
- Request: "I need fraud detection models for analysis"
- Expected: Auto-approve with all green badges

---

## 🔧 IMPLEMENTATION APPROACH

### Option 1: Minimal Changes (Recommended)
Keep existing helper functions, just replace data source:

```javascript
// OLD (line ~799)
async function runWorkflow() {
  const s = SCENARIOS[currentScenario];  // ← mock data
  renderIntakeCard(s.intake);
  await sleep(500);
  renderPolicyCard(s.policy);
  // ...
}

// NEW
async function runWorkflow() {
  const text = document.getElementById('req').value;
  const email = document.getElementById('userEmail').textContent;
  const url = `http://localhost:8000/api/stream_workflow?request_text=${encodeURIComponent(text)}&requester_email=${encodeURIComponent(email)}`;
  
  const eventSource = new EventSource(url);
  
  eventSource.addEventListener('intake', (e) => {
    const data = JSON.parse(e.data);
    renderIntakeCard(data);  // ← same function, real data
  });
  
  eventSource.addEventListener('policy', (e) => {
    const data = JSON.parse(e.data);
    renderPolicyCard(data);
  });
  
  // ... continue for other events
}
```

### Option 2: Full Rewrite
Completely replace runWorkflow() with new SSE logic.