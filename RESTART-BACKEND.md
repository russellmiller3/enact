# RESTART: Visa GDO Backend - Debug Tests & Wire Frontend

## 🔴 STOP! READ /.roo/roorules FIRST

**REFERENCE FILES (read first, in order):**
1. `backend/README.md` - Architecture overview & run instructions
2. `plans/backend-architecture.html` - Visual diagram (open in browser)
3. `PLAN.md` - Original implementation plan
4. This file (RESTART-BACKEND.md) - Current status

**BRANCH:** main (no feature branch)
**COST SO FAR:** $11.89 (previous session)

---

## COMPLETED ✅

**Phase 1: Backend Infrastructure**
✅ FastAPI server (`backend/server.py`) with SSE streaming
✅ Workflow orchestrator (`backend/workflow.py`) - NO LangGraph (linear flow)
✅ Config loaders (`backend/utils.py`) with hot-reload + SHA256 version hash
✅ Pydantic models (`backend/models.py`) for validation
✅ Audit receipt writer (`backend/receipts.py`)

**Phase 2: 5 Agents Complete**
✅ Agent #0: Discovery (`backend/agents/discovery.py`) - Claude catalog search
✅ Agent #1: Intake (`backend/agents/intake.py`) - Claude NLU parsing  
✅ Agent #2: Policy (`backend/agents/policy.py`) - **ABAC engine (NO LLM)** ✨
✅ Agent #3: Provision (`backend/agents/provision.py`) - JWT token generation
✅ Agent #4: Notify (`backend/agents/notify.py`) - Template-based messages

**Phase 3: Editable Config Files (Demo Proof)**
✅ `backend/config/users.json` - 3 users (Sarah Chen, James Rodriguez, Unknown)
✅ `backend/config/datasets.json` - 4 datasets with columns metadata
✅ `backend/config/policies.py` - 8 ABAC policy functions (pure Python)

**Phase 4: Dependencies**
✅ `backend/requirements.txt` - Simplified (removed LangChain/LangGraph conflicts)
✅ Dependencies installed via `pip install -r requirements.txt`
✅ `.env` file created with ANTHROPIC_API_KEY

**Phase 5: Tests Written**
✅ `backend/tests/test_policy_agent.py` - 15+ test cases
✅ `backend/pytest.ini` - Test configuration
[-] **Tests hanging on import - NOT VERIFIED** ⚠️

---

## CURRENT ISSUE ❌

**Symptom:** Tests hang when running, never produce output
```bash
cd backend && python -m pytest tests/test_policy_agent.py -v --tb=short
# Output: platform info, then nothing...
```

**What WORKS:**
- Dependencies installed successfully (exit code 0)
- Files created and exist
- pytest.ini found by pytest

**What DOESN'T WORK:**
- Test collection hangs (never shows "collected X items")
- Simple import test also hangs:
  ```bash
  python -c "from agents.policy import run_policy; print('Import successful')"
  # No output, no error, just hangs
  ```

**HYPOTHESIS:**
1. Circular import in agents module
2. Config file loading blocking (users.json or datasets.json)
3. Missing `__init__.py` somewhere causing import issues
4. `policies.py` has syntax error or infinite loop on import

---

## NEXT ACTIONS (numbered, specific)

### 1. **TEST SIMPLE IMPORT FIRST**
```bash
cd backend
python -c "import json; print('OK')"  # Sanity check Python works
python -c "from pathlib import Path; print(Path.cwd())"  # Check working dir
python -c "import utils; print('utils OK')"  # Test utils
python -c "import models; print('models OK')"  # Test models
python -c "from agents import policy; print('policy OK')"  # Test policy import
```

If any of these hang, you know where the problem is.

### 2. **CHECK FOR CIRCULAR IMPORTS**
Look at these files for circular dependencies:
- `backend/agents/__init__.py` (line 4-8) imports all agents
- `backend/agents/policy.py` (line 11-12) imports from `utils` and `models`
- `backend/utils.py` (line 21-35) loads JSON files on import (calls `reload_config()` at bottom)

**FIX IF FOUND:** Move `reload_config()` call from module level to inside functions.

### 3. **CHECK CONFIG FILES SYNTAX**
```bash
cd backend
python -c "import json; json.load(open('config/users.json'))"  # Validate JSON
python -c "import json; json.load(open('config/datasets.json'))"  # Validate JSON
python -c "import sys; sys.path.insert(0, 'config'); import policies; print('policies OK')"
```

### 4. **FIX UTILS.PY IF IT'S THE CULPRIT**
If `utils.py` import hangs (Step 1), the issue is line 88:
```python
# Line 88 in utils.py
reload_config()  # ← This is called on import!
```

**FIX:** Remove line 88, call `reload_config()` lazily inside functions instead.

### 5. **ONCE IMPORTS WORK, RUN TESTS**
```bash
cd backend
python -m pytest tests/test_policy_agent.py -v --tb=short
```

Expected output:
```
collected 15 items
test_policy_agent.py::TestPolicyAgent_APPROVE::test_sarah_chen... PASSED
...
```

### 6. **THEN START SERVER**
```bash
cd backend
python server.py
```

Should see:
```
🚀 Visa GDO Data Access Automation
Frontend:  http://localhost:8000/
SSE API:   http://localhost:8000/api/stream_workflow
Config version: abc123def456
```

### 7. **TEST API MANUALLY**
```bash
curl http://localhost:8000/api/health
# Expected: {"status":"healthy", ...}

curl "http://localhost:8000/api/stream_workflow?request_text=I+need+fraud+data&requester_email=analyst@visa.com"
# Expected: SSE stream with event: discovery, intake, policy, etc.
```

---

## KEY FILES (with line numbers)

### Import Chain (Debug Path)
```
backend/
├── agents/__init__.py
│   ├── Line 4: from .discovery import run_discovery
│   ├── Line 5: from .intake import run_intake  
│   ├── Line 6: from .policy import run_policy  ← LIKELY CULPRIT
│   └── ...
├── agents/policy.py
│   ├── Line 11: from utils import get_user, get_dataset  ← Imports utils
│   └── Line 12: from models import PolicyResult, ABACCheck
├── utils.py
│   ├── Line 21-35: load_users(), load_datasets() functions
│   └── Line 88: reload_config()  ← CALLED ON IMPORT! ⚠️
└── config/
    ├── users.json (37 lines)
    ├── datasets.json (95 lines)  
    └── policies.py (146 lines)
```

### Critical Suspect: `backend/utils.py`
**Line 88 is the problem if imports hang:**
```python
# Line 88 (module-level code that executes on import)
reload_config()
```

This calls `load_users()` and `load_datasets()` which:
1. Open JSON files
2. Parse them
3. Compute SHA256 hash

If JSON files are malformed or huge, this could hang.

**FIX:** Remove line 88, add lazy loading:
```python
# At top of utils.py
_initialized = False

def ensure_initialized():
    global _initialized
    if not _initialized:
        reload_config()
        _initialized = True

# In each function, add:
def get_user(email):
    ensure_initialized()
    ...
```

---

## FILE STRUCTURE (Full Tree)

```
backend/
├── server.py              # FastAPI app (158 lines)
├── workflow.py            # Agent orchestrator (150 lines)
├── models.py              # Pydantic schemas (110 lines)
├── utils.py               # Config loaders (88 lines) ← CHECK LINE 88
├── receipts.py            # Audit writer (160 lines)
├── requirements.txt       # Dependencies (11 packages)
├── pytest.ini             # Test config
├── README.md              # Architecture docs
├── .env                   # API key (user added)
├── .env.example
├── agents/
│   ├── __init__.py        # Exports all agents (15 lines)
│   ├── discovery.py       # Agent #0 Claude (130 lines)
│   ├── intake.py          # Agent #1 Claude (95 lines)
│   ├── policy.py          # Agent #2 ABAC (NO LLM) (170 lines)
│   ├── provision.py       # Agent #3 JWT (45 lines)
│   └── notify.py          # Agent #4 Templates (275 lines)
├── config/
│   ├── users.json         # 3 users (37 lines)
│   ├── datasets.json      # 4 datasets (95 lines)
│   └── policies.py        # 8 ABAC functions (146 lines)
├── receipts/
│   └── README.md
└── tests/
    ├── __init__.py
    └── test_policy_agent.py  # 15+ tests (270 lines)
```

---

## DONE WHEN ✅

1. ✅ Simple import works: `python -c "from agents.policy import run_policy; print('OK')"`
2. ✅ Tests run: `pytest tests/test_policy_agent.py -v` shows results (pass or fail)
3. ✅ At least 10/15 tests pass (policy scenarios: APPROVE, ESCALATE, DENY)
4. ✅ Server starts: `python server.py` runs without errors
5. ✅ API responds: `curl http://localhost:8000/api/health` returns JSON
6. ⏳ Frontend wired to SSE (NEXT PHASE - not started)

---

## WHY THIS MATTERS (Demo Proof)

**The Key Insight:** Only 2 of 5 agents use Claude (Discovery + Intake). Policy engine is 100% deterministic Python + JSON.

**Live Demo:**
1. Run workflow: Sarah Chen requests `fraud_detection_models` → **APPROVE**
2. Edit `backend/config/users.json`: Change Sarah's role to "Contractor"
3. Save file → config reloads (version hash changes)
4. Rerun same request → **ESCALATE** (contractor restriction)
5. Edit `backend/config/datasets.json`: Change `min_clearance` to 4
6. Rerun → **DENY** (Sarah has clearance 3)

**This proves:** Policy decisions read from files, not an LLM.

---

## WHAT TO DO FIRST

**Start here:**
```bash
cd backend
python -c "import utils; print('utils OK')"
```

If it hangs, fix `utils.py` line 88 (remove `reload_config()` call).
If it works, test next: `python -c "from agents import policy; print('OK')"`

Work through the import chain until you find what's blocking.
