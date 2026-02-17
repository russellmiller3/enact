# Visa GDO Backend - Multi-Agent Data Access Automation

## 🎯 Current Status: FULLY WIRED & WORKING

**Frontend ↔️ Backend SSE streaming is LIVE**

- ✅ 5 agents executing in real-time
- ✅ Beautiful Visa UI with live data streaming
- ✅ Comprehensive terminal logging (detailed execution flow)
- ✅ SSE event-driven updates (sequential agent rendering)
- ✅ Server online/offline demo ready
- ✅ Conference interview-ready
- ✅ Fixed SSE race condition (agents now render in correct order)

Find and kill processes
netstat -ano | findstr :8000
taskkill /PID 22588 /F
taskkill /F /PID 22588 /T

---

## What We Built

**5 agents in sequence: Discovery → Intake → Policy → Provision → Notify**

SSE streaming + deterministic ABAC policy engine

### Architecture

```
┌─────────────────────────────────────────────┐
│   Frontend (workflow.html)                  │
│   • EventSource SSE client                  │
│   • Real-time UI updates                    │
│   • Beautiful Visa branding + animations    │
│   • Server status indicator                 │
└────────┬────────────────────────────────────┘
         │ SSE Stream
         ▼
┌─────────────────────────────────────────────┐
│   FastAPI Server (server.py)                │
│   • GET /api/stream_workflow (SSE)          │
│   • POST /api/run_workflow (JSON)           │
│   • Config hot-reload                       │
│   • CORS for local dev                      │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│   Workflow Orchestrator (workflow.py)       │
│   • Coordinates 5 agents sequentially       │
│   • Emits 7 SSE events                      │
│   • Comprehensive logging                   │
│   • Tracks metrics (tokens, ms, decisions)  │
└────────┬────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────┐
│  Agent #0: Discovery (Claude Sonnet 3.5)                 │
│            → Semantic search of dataset catalog          │
│            → Returns top 3 matches with metadata         │
├──────────────────────────────────────────────────────────┤
│  Agent #1: Intake (Claude Sonnet 3.5)                    │
│            → Parse natural language request              │
│            → Extract: dataset, access_level, reason      │
├──────────────────────────────────────────────────────────┤
│  Agent #2: Policy (ABAC Engine) ★ NO LLM ★               │
│            → 8 deterministic policy checks               │
│            → Loads users.json + datasets.json            │
│            → Decision: APPROVE / ESCALATE / DENY         │
├──────────────────────────────────────────────────────────┤
│  Agent #3: Provisioning (JWT Generator)                  │
│            → Generates access token                      │
│            → Sets expiry (90 days)                       │
│            → Skipped if decision ≠ APPROVE               │
├──────────────────────────────────────────────────────────┤
│  Agent #4: Notification (Template Engine)                │
│            → Sends to: Email, Slack, ServiceNow          │
│            → Different messages per decision type        │
└──────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│   Config Files (EDITABLE - no restart!)     │
│   • config/users.json (3 personas)          │
│   • config/datasets.json (11 datasets)      │
│   • config/policies.py (8 ABAC functions)   │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│   Audit Receipts (receipts/*.txt)           │
│   • One file per request                    │
│   • Full decision trail                     │
│   • Searchable plain text                   │
└─────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Add Your API Key

Create/edit `.env` file:

```bash
ANTHROPIC_API_KEY=sk-ant-...your-key-here
```

### 3. Start Server

```bash
python server.py
```

You'll see:

```
============================================================
🚀 Visa GDO Data Access Automation
============================================================
Frontend:  http://localhost:8000/
SSE API:   http://localhost:8000/api/stream_workflow
...
============================================================
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 4. Open Frontend

Navigate to **http://localhost:8000/** in your browser

---

## Terminal Output (What You'll See)

When you run a workflow, the terminal shows **detailed execution logs**:

```
============================================================
🚀 NEW REQUEST: REQ-12345
   User: analyst@visa.com
   Text: I need read access to fraud data for my analysis...
============================================================

🔍 [1/5] Running Discovery Agent...
   ✓ Found 2 dataset(s) | 45ms | 120 tokens

📥 [2/5] Running Intake Agent...
   ✓ Extracted: READ access to fraud_detection_models | 350ms | 559 tokens

🛡️  [3/5] Running ABAC Policy Engine...
   ✓ Decision: APPROVE | 8/8 checks passed | 12ms

🔑 [4/5] Running Provisioning Agent...
   ✓ Access granted | Token: eyJhbGciOiJIUzI1NiI... | 180ms

📧 [5/5] Running Notification Agent...
   ✓ Sent 4 notifications | 90ms

📋 Generating audit receipt...
   ✓ Receipt saved: backend/receipts/REQ-12345_2026-02-17.txt

============================================================
✅ WORKFLOW COMPLETE: APPROVE
   Agents: 5 | Checks: 8/8 | Time: 677ms | Tokens: 679
   Request ID: REQ-12345
============================================================
```

**This shows:**

- **Discovery agent** searching catalog and matching datasets
- **Intake agent** parsing the request with Claude
- **Policy engine** running deterministic ABAC checks (NO LLM)
- **Provisioning agent** generating access tokens (if approved)
- **Notification agent** sending alerts
- Full timing and token metrics for each step

---

## Interview Demo Script (2 minutes)

### Part 1: Show It Working (30 sec)

1. Open http://localhost:8000/
2. Sarah Chen scenario is pre-selected
3. Click **"Run Workflow"**
4. Point to terminal: "Watch the 5 agents execute"
5. Point to browser: "UI updates in real-time from SSE stream"
6. Result: **APPROVED** ✅

### Part 2: Prove It's Real (30 sec)

1. Kill the server (Ctrl+C in terminal)
2. Click **"Run Workflow"** again
3. Point to browser: "Connection error - proves it's hitting real backend"
4. Restart server: `python server.py`
5. Click **"Run Workflow"** → works again

### Part 3: Show Deterministic Policy (60 sec)

1. **Open config/users.json**
2. Change Sarah's role from `"Senior Data Analyst"` to `"Contractor"`
3. Save file (server auto-reloads)
4. Run workflow → Result: **ESCALATE** ⚠️
5. Point to terminal: Shows which ABAC check failed
6. Point to browser: Shows amber badges on failed policies

**This proves:**

- ✅ It's a real backend (not mock data)
- ✅ Policy decisions are data-driven (edit file → different result)
- ✅ Only 2/5 agents use AI (Discovery + Intake)
- ✅ Policy engine is deterministic Python code

---

## Key Endpoints

| Endpoint                      | Method | Description                                |
| ----------------------------- | ------ | ------------------------------------------ |
| `/`                           | GET    | Serve frontend (workflow.html)             |
| `/workflow.html`              | GET    | Main workflow demo interface               |
| `/dashboard-prototype.html`   | GET    | Governance dashboard (metrics, anomalies)  |
| `/review-prototype.html`      | GET    | Human review queue (escalations)           |
| `/roi-prototype.html`         | GET    | ROI report ($5M annual value)              |
| `/api/stream_workflow`        | GET    | **SSE streaming** - real-time agent events |
| `/api/run_workflow`           | POST   | JSON response (for testing/debugging)      |
| `/api/config/users`           | GET    | View users.json                            |
| `/api/config/datasets`        | GET    | View datasets.json                         |
| `/api/config/version`         | GET    | Config version hash (changes on edit)      |
| `/api/config/reload`          | POST   | Force reload configs                       |
| `/api/health`                 | GET    | Health check                               |

---

## Testing

Run policy engine tests:

```bash
cd backend
python -m pytest tests/test_policy_agent.py -v
```

**Tests cover:**

- ✅ APPROVE scenarios (all 8 checks pass)
- ✅ ESCALATE scenarios (write/admin access requires approval)
- ✅ DENY scenarios (insufficient clearance/role)
- ✅ Badge colors (green ✓ / amber ⚠ / red ✗)
- ✅ Determinism (same input = same output, always)

---

## SSE Event Flow

```
Frontend opens EventSource → GET /api/stream_workflow

Backend streams 7 events:

  1. event: discovery
     data: {"matches": [...], "match_count": 2, "tokens": 120}

  2. event: intake
     data: {"extracted": {...}, "reasoning": [...], "tokens": 559}

  3. event: policy
     data: {"decision": "APPROVE", "abac_checks": [...]}

  4. event: provision
     data: {"token": "eyJ...", "expires_at": "2026-05-18"}

  5. event: notify
     data: {"channels": [...], "messages": [...]}

  6. event: audit
     data: {"receipt_path": "...", "entries": [...]}

  7. event: done
     data: {"total_ms": 677, "total_tokens": 679, "request_id": "REQ-12345"}
```

Frontend renders each event with beautiful animations as it arrives.

---

## File Structure

```
backend/
├── server.py              # FastAPI app + SSE endpoint
├── workflow.py            # Orchestrates 5 agents + logging
├── models.py              # Pydantic schemas
├── utils.py               # Config loaders + hot-reload
├── receipts.py            # Audit trail writer
├── requirements.txt       # Python dependencies
├── .env                   # API keys (gitignored)
├── agents/
│   ├── __init__.py
│   ├── discovery.py       # Agent #0 - Claude Sonnet 3.5
│   ├── intake.py          # Agent #1 - Claude Sonnet 3.5
│   ├── policy.py          # Agent #2 - ABAC (NO LLM)
│   ├── provision.py       # Agent #3 - JWT generator
│   └── notify.py          # Agent #4 - Templates
├── config/
│   ├── users.json         # 3 test users (editable!)
│   ├── datasets.json      # 11 datasets with metadata
│   └── policies.py        # 8 ABAC policy functions
├── receipts/              # Auto-generated audit files
│   ├── README.md
│   └── REQ-*.txt          # One per request
└── tests/
    ├── __init__.py
    └── test_policy_agent.py  # Policy engine unit tests
```

---

## Config Hot-Reload (Live Demo Trick)

**The server watches config files and reloads automatically:**

1. Edit `config/users.json` (change a role)
2. Save the file
3. Server detects change via version hash
4. Next request uses updated config
5. No restart needed!

**Verify reload:**

```bash
# Get current version
curl http://localhost:8000/api/config/version

# Edit users.json, save

# Check version again (hash will change)
curl http://localhost:8000/api/config/version
```

---

## The 8 ABAC Policy Checks

Located in `config/policies.py`:

1. **Role Authorization** - User role must be in dataset's `allowed_roles`
2. **Clearance Level** - User clearance ≥ dataset's `min_clearance`
3. **Access Level** - READ auto-approves, WRITE/ADMIN escalate
4. **PII Restriction** - Only FTEs can access PII datasets
5. **Training Requirements** - User must have completed required training
6. **Employment Type** - Contractors blocked from certain datasets
7. **MNPI Blackout** - Block access to MNPI during blackout periods
8. **Time-Limited Access** - All access expires in 90 days

**Each check returns:**

- `match`: True/False (did user pass?)
- `badge`: "g" (green ✓) / "a" (amber ⚠) / "r" (red ✗)
- `requirement`: What was required
- `user_value`: What the user has

---

## Production Considerations

**Current state:** Demo-ready, conference-ready  
**NOT production-ready because:**

- Uses in-memory JSON files (no database)
- Mock JWT tokens (no real IAM integration)
- No authentication/authorization on API
- No rate limiting
- Single-threaded server

**To productionize:**

1. Replace JSON files with PostgreSQL/MongoDB
2. Integrate with Okta/AWS IAM for real access tokens
3. Add API authentication (OAuth2/JWT)
4. Use Redis for config caching
5. Deploy with Kubernetes for scale
6. Add rate limiting + request validation
7. Implement audit log streaming to Splunk/DataDog

---

## Tech Stack

- **Backend:** Python 3.11+ with FastAPI
- **LLM:** Anthropic Claude Sonnet 3.5 (for agents #0 and #1)
- **Validation:** Pydantic v2
- **Testing:** pytest
- **Frontend:** Vanilla JS + SSE (EventSource API)
- **Config:** JSON files with SHA256 version hashing

---

## Known Issues & Fixes

### ✅ FIXED: SSE Event Rendering Race Condition

**Symptom:** Agents rendered out of order, or alert popup appeared after Discovery/Intake agents.

**Root Cause:** `EventSource.onerror` fired when the server naturally closed the SSE connection after sending all events. EventSource is designed for persistent connections and treats connection closure as an error. The `onerror` handler called `alert()` which blocked the JavaScript thread, preventing the `queueHandler` promise chain from processing remaining events (policy, provision, notify, audit, done).

**Fix (commit `a2513c4`):**
1. Added `receivedDone` flag in `runWorkflow()` to distinguish normal stream end from errors
2. Close `EventSource` immediately in `done` event listener (before queueHandler)
3. Skip `onerror` handling if `receivedDone` is true (normal stream end, not error)
4. Reset `handlerQueue = Promise.resolve()` at start of each workflow run
5. Fixed `total_duration_ms` → `total_ms` field name mismatch

**Verify Fix:** Hard refresh browser (Ctrl+Shift+R) to clear cache. All 7 SSE events should arrive in order, all 5 agent cards render sequentially, no alert popups.

---

## Next Steps

- [x] Backend 5-agent system
- [x] SSE streaming endpoint
- [x] Frontend SSE integration
- [x] Terminal logging for demos
- [x] Fixed SSE race condition
- [ ] Add server status indicator to frontend
- [ ] Deploy backend to Railway
- [ ] Deploy frontend to Vercel
- [ ] Record demo video

---

## Notes

- **Python 3.11+** required
- **Windows**: Uses Git Bash for commands
- **Config files**: JSON for data, Python for logic
- **No database**: Config files are version-controlled
- **Built with TDD**: Tests written before implementation 🧪

**Built for the Visa GDO interview - February 2026**
