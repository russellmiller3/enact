# RESTART: Visa GDO - Wire Frontend to Backend

## 🔴 STOP! READ /.roo/roorules FIRST

**BRANCH:** main (no feature branch)
**COST SO FAR:** $3.56 (current session: fixed backend import bugs)

---

## ✅ COMPLETED (Backend is DONE)

### Phase 1-4: Backend Infrastructure ✅
- FastAPI server with SSE streaming
- 5 agents working (Discovery, Intake, Policy, Provision, Notify)
- Config files (users.json, datasets.json, policies.py)
- All dependencies installed

### Phase 5: Tests ✅
- 12/12 policy tests passing
- Test file: `backend/tests/test_policy_agent.py`

### Phase 6: Debug Session ✅ (Today)
**Fixed 5 bugs:**
1. `backend/utils.py` - Deadlock (Lock → RLock, removed import-time call)
2. `backend/agents/discovery.py` - Import-time blocking (lazy client)
3. `backend/agents/intake.py` - Import-time blocking (lazy client)
4. `backend/agents/policy.py` - Admin access logic (DENY → ESCALATE)
5. `backend/requirements.txt` - SDK upgrade (anthropic 0.18.0 → 0.79.0)

**Status:** Backend fully operational, server running

---

## 🎯 CURRENT STATE

### What Works Now
```bash
# 1. Start server
cd backend
python server.py
# Output: Server running at http://localhost:8000

# 2. Test health
curl http://localhost:8000/api/health
# Output: {"status":"healthy","config_version":"..."}

# 3. Test workflow
curl "http://localhost:8000/api/stream_workflow?request_text=I+need+fraud+data&requester_email=analyst@visa.com"
# Output: SSE stream with 5 events (discovery, intake, policy, provision, notify)

# 4. Run tests
cd backend
python -m pytest tests/test_policy_agent.py -v
# Output: 12/12 PASSED
```

### What Doesn't Work Yet
- ❌ No frontend
- ❌ No UI to visualize SSE stream
- ❌ No way to demo editable config files

---

## 🚀 NEXT ACTIONS (Start Here)

### Step 1: Decide Frontend Approach

**Option A: Simple HTML/JavaScript** (fastest for demo)
- Create `frontend/index.html` with SSE client
- No build step, runs directly in browser
- Pro: Quick to demo
- Con: Limited polish

**Option B: React/Vite** (better UX)
- Use one of the existing prototypes from `plans/` folder
- Needs npm install + build step
- Pro: Professional UI
- Con: More setup time

**Option C: Use existing prototype HTML files**
- Files: `plans/demo-v2-prototype.html`, `plans/dashboard-prototype.html`
- Adapt to connect to real SSE endpoint
- Pro: Already designed
- Con: Static mockups, need SSE integration

**RECOMMENDATION:** Start with Option A, get SSE working, then upgrade to Option B/C.

---

### Step 2: Create Simple SSE Test Frontend

**File:** `frontend/index.html`

**Requirements:**
1. Input fields: request_text, requester_email
2. "Submit Request" button
3. EventSource to connect to `http://localhost:8000/api/stream_workflow`
4. Display each SSE event as it arrives
5. Show agent results (discovery matches, policy checks, final decision)

**Key code snippet:**
```javascript
const eventSource = new EventSource(
  `http://localhost:8000/api/stream_workflow?request_text=${text}&requester_email=${email}`
);

eventSource.addEventListener('discovery', (e) => {
  const data = JSON.parse(e.data);
  // Display discovery results
});

eventSource.addEventListener('policy', (e) => {
  const data = JSON.parse(e.data);
  // Display ABAC checks with green/amber/red badges
});
```

---

### Step 3: Test End-to-End Workflow

**Test scenarios:**

1. **APPROVE scenario**
   - User: `analyst@visa.com` (Sarah Chen)
   - Request: "I need access to fraud detection models for analysis"
   - Expected: Discovery finds dataset → Intake extracts intent → Policy APPROVES (all green badges) → JWT token generated → Notification sent

2. **ESCALATE scenario**
   - User: `analyst@visa.com`
   - Request: "I need WRITE access to fraud models"
   - Expected: Policy ESCALATES (amber badge on Access Level check)

3. **DENY scenario**
   - User: `unknown@visa.com`
   - Request: "I need fraud data"
   - Expected: Policy DENIES (red badges on multiple checks)

---

### Step 4: Demo Config File Editing

**Goal:** Prove policy decisions read from files, not LLM

**Live demo flow:**

1. Run request: Sarah Chen → fraud_detection_models → **APPROVE**

2. Edit `backend/config/users.json`:
   ```json
   "analyst@visa.com": {
     "clearance_level": 1  // Changed from 3
   }
   ```

3. Server auto-reloads config (watchfiles monitors changes)

4. Rerun same request → **DENY** (insufficient clearance)

5. Edit `backend/config/policies.py`:
   ```python
   def check_clearance_level(user, dataset, access_level):
       # Comment out the check
       return {"policy": "...", "match": True}
   ```

6. Rerun → **APPROVE** (clearance check disabled)

**This proves:** Policy engine reads config files in real-time, not cached LLM responses.

---

## 📁 KEY FILES

### Backend (Running)
```
backend/
├── server.py              # FastAPI app (port 8000)
├── workflow.py            # Orchestrates 5 agents
├── agents/
│   ├── discovery.py       # Claude - dataset search
│   ├── intake.py          # Claude - NLU parsing
│   ├── policy.py          # ABAC engine (NO LLM)
│   ├── provision.py       # JWT token generation
│   └── notify.py          # Email templates
├── config/
│   ├── users.json         # 3 users (editable)
│   ├── datasets.json      # 4 datasets (editable)
│   └── policies.py        # 8 ABAC functions (editable Python)
└── tests/
    └── test_policy_agent.py  # 12 tests, all passing
```

### Frontend (Not Started)
```
frontend/
├── index.html             # TO CREATE: SSE client
├── style.css              # TO CREATE: Basic styling
└── app.js                 # TO CREATE: EventSource logic
```

### Existing Prototypes (Reference)
```
plans/
├── demo-v2-prototype.html      # Best UI design
├── dashboard-prototype.html    # Dashboard layout
├── discovery-demo.html         # Discovery agent mockup
└── backend-architecture.html   # Architecture diagram
```

---

## 🔍 DEBUGGING TOOLS CREATED

### `backend/debug_imports.py`
Breadcrumb trail to diagnose import hangs. Run:
```bash
cd backend
python debug_imports.py
```
Shows which import step fails.

### `backend/deadlock_explanation.md`
Deep dive on deadlock bug with ASCII diagrams. Read for understanding `Lock()` vs `RLock()`.

---

## 🎓 LESSONS LEARNED (This Session)

### Bug Pattern #1: Deadlock
**Symptom:** Import hangs forever, no error
**Cause:** Non-reentrant `Lock()` + nested function calls
**Fix:** Use `RLock()` for nested locking

### Bug Pattern #2: Import-Time Execution
**Symptom:** Import hangs, code runs before you want it to
**Cause:** Module-level code executes when file is imported
**Fix:** Lazy initialization (only run when function called)

### Bug Pattern #3: Context-Aware Logic
**Symptom:** Test expects ESCALATE, gets DENY
**Cause:** Policy treats all role failures as hard failures
**Fix:** Check access_level context (write/admin → escalate, read → deny)

### Bug Pattern #4: Version Conflicts
**Symptom:** `unexpected keyword argument 'proxies'`
**Cause:** Anthropic SDK 0.18.0 (old) incompatible with current API
**Fix:** Upgrade to 0.79.0

---

## 🎯 SUCCESS CRITERIA (Next Phase)

**Done when:**

1. ✅ Frontend HTML file exists
2. ✅ SSE connection works (see events in browser console)
3. ✅ All 5 agent results display in UI
4. ✅ Policy checks show green/amber/red badges
5. ✅ Can run test scenarios (APPROVE, ESCALATE, DENY)
6. ✅ Can edit config file → see policy change live
7. ✅ Ready to demo to stakeholders

---

## 🚦 DECISION POINT

**Before you start coding frontend, answer:**

1. **What's the demo deadline?** (Quick HTML vs polished React)
2. **Who's the audience?** (Technical vs executive)
3. **What's the key message?** (ABAC is editable vs full UX flow)

**If unsure:** Start with simple HTML SSE client, validate end-to-end, then upgrade UI.

---

## 🔗 REFERENCE LINKS

- Backend API docs: `http://localhost:8000/docs` (FastAPI auto-generated)
- SSE endpoint: `http://localhost:8000/api/stream_workflow`
- Health check: `http://localhost:8000/api/health`
- Test command: `cd backend && python -m pytest tests/test_policy_agent.py -v`

---

## 📝 NOTES

- Server must be running for frontend to work
- Config files hot-reload (watchfiles monitors changes)
- CORS already enabled in `server.py` (cross-origin requests allowed)
- SSE events: `discovery`, `intake`, `policy`, `provision`, `notify`, `complete`, `error`

---

## 🏁 START HERE

```bash
# Terminal 1: Start backend (keep running)
cd backend
python server.py

# Terminal 2: Create frontend
# (Next session starts here)
```

**First task:** Create `frontend/index.html` with basic SSE client.

**Template structure:**
```html
<!DOCTYPE html>
<html>
<head>
  <title>Visa GDO - Data Access Request</title>
</head>
<body>
  <h1>Request Data Access</h1>
  
  <input id="request_text" placeholder="What data do you need?">
  <input id="requester_email" placeholder="Your email">
  <button onclick="submitRequest()">Submit</button>
  
  <div id="results"></div>
  
  <script>
    function submitRequest() {
      const text = document.getElementById('request_text').value;
      const email = document.getElementById('requester_email').value;
      const url = `http://localhost:8000/api/stream_workflow?request_text=${encodeURIComponent(text)}&requester_email=${encodeURIComponent(email)}`;
      
      const eventSource = new EventSource(url);
      
      eventSource.addEventListener('discovery', (e) => {
        console.log('Discovery:', JSON.parse(e.data));
        // TODO: Display in UI
      });
      
      // Add handlers for other events...
    }
  </script>
</body>
</html>
```
