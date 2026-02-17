# Implementation Plan: Visa GDO Multi-Agent Data Access Automation

## Build Order: OUTSIDE-IN (REVISED)

**Phase 1: Pixel-perfect UI prototype** ✅ DONE
- Built 4 HTML prototypes with custom CSS (no framework)
- [`plans/demo-prototype.html`](plans/demo-prototype.html) — Interactive request workflow with streaming animation
- [`plans/dashboard-prototype.html`](plans/dashboard-prototype.html) — Governance metrics
- [`plans/review-prototype.html`](plans/review-prototype.html) — Human review queue
- [`plans/roi-prototype.html`](plans/roi-prototype.html) — ROI report with fraud/compliance value
- All design decisions documented in [`plans/ux-decisions.md`](plans/ux-decisions.md)

**Phase 2: Wire live backend** (NEXT — estimated 5-6 hours)
- Build FastAPI backend with SSE streaming + editable JSON config
- Implement 5 agents: Discovery (Claude), Intake (Claude), Policy (ABAC from files), Provisioning (mock), Notify (templates)
- Wire LangGraph orchestration with real-time SSE streaming to frontend
- Connect frontend to backend via EventSource API
- **PROOF: Edit config files → outcomes change**

**Phase 3: Polish & edge cases** (estimated 1-2 hours)
- Handle unknown datasets gracefully
- Handle adversarial/nonsense input
- Test "type your own request" flow
- Deploy (Vercel frontend + Railway/Render backend)

---

## The Key Insight: Editable Config as Proof

**Why this matters for the interview:**

Most demo apps hardcode data. Russell's demo **reads from editable files**:

```bash
# During demo, Russell can:
1. Show Sarah Chen (Senior Data Analyst) getting APPROVED for fraud_detection_models
2. Open backend/config/users.json in VS Code
3. Change Sarah's role to "Contractor"
4. Save file
5. Rerun same request → now ESCALATES (contractor + PII restriction)
6. Change dataset's min_clearance from 2 to 4
7. Rerun → now DENIES (Sarah only has clearance 3)
```

**This proves:**
1. System is data-driven, not hardcoded
2. ABAC rules are deterministic (change attribute → change outcome)
3. Policy engine is NOT an LLM (plain Python reading JSON)
4. Only Discovery + Intake use Claude (for NLU, not decisions) — 2 of 5 agents

---

## Tech Stack (REVISED FOR LIVE CONFIG)

| Component | Technology | Why |
|-----------|-----------|-----|
| **Frontend** | HTML + Vanilla JS + EventSource | Pixel-perfect design, already done; SSE for real-time streaming |
| **Backend API** | FastAPI + sse-starlette | Lightweight, async, SSE streaming per agent step |
| **LLM** | Claude Sonnet 3.5 | Dataset discovery + request parsing ONLY |
| **Policy Engine** | Python ABAC + JSON config | Deterministic, auditable, editable |
| **Orchestration** | LangGraph | State machine for agent workflow |
| **Streaming** | Server-Sent Events (SSE) | Real-time agent-by-agent updates to frontend |
| **Config Storage** | JSON files | Editable, version-controllable, no database needed |
| **Language** | Python 3.11+ | Backend only |
| **Deployment** | Vercel (frontend) + Railway (backend) | Free tier, instant deploy |

---

## File Structure (UPDATED)

```
visa/
├── frontend/
│   ├── index.html              # Main demo (from demo-prototype.html)
│   ├── dashboard.html
│   ├── review.html
│   ├── roi.html
│   └── assets/screenshots/
├── backend/
│   ├── server.py               # FastAPI app + SSE streaming endpoint
│   ├── config/                 # ← EDITABLE CONFIG FILES
│   │   ├── users.json          # User attributes (role, clearance, training)
│   │   ├── datasets.json       # Dataset catalog (4 datasets, with column schemas)
│   │   └── policies.py         # ABAC rules (8 policy functions)
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── discovery.py        # Agent #0: Claude searches catalog, returns matches
│   │   ├── intake.py           # Agent #1: Claude parses request → structured JSON
│   │   ├── policy.py           # Agent #2: ABAC engine (NO LLM), reads config
│   │   ├── provision.py        # Agent #3: JWT generation (mock IAM)
│   │   └── notify.py           # Agent #4: Template-based notifications
│   ├── workflow.py             # LangGraph orchestration + SSE event emitter
│   ├── models.py               # Pydantic schemas
│   ├── receipts.py             # Audit receipt writer (backend/receipts/*.txt)
│   └── utils.py                # Config loaders, file watchers, version hash
│   ├── receipts/               # Auto-generated audit receipt files
├── .env                        # ANTHROPIC_API_KEY
├── requirements.txt
├── README.md
└── plans/
    └── [existing design docs]
```

---

## Editable Config Files

### `backend/config/users.json`
```json
{
  "analyst@visa.com": {
    "name": "Sarah Chen",
    "role": "Senior Data Analyst",
    "employee_type": "FTE",
    "org": "Risk Analytics",
    "clearance_level": 3,
    "training_completed": ["PII_Handling_2026", "InfoSec_Annual_2026"],
    "training_dates": {
      "InfoSec_Annual_2026": "2026-01-15"
    },
    "manager": "mike.foster@visa.com"
  },
  "scientist@visa.com": {
    "name": "James Rodriguez",
    "role": "Staff Data Scientist",
    "employee_type": "FTE",
    "org": "Data Science",
    "clearance_level": 4,
    "training_completed": ["PII_Handling_2026", "InfoSec_Annual_2026"],
    "training_dates": {
      "InfoSec_Annual_2026": "2026-01-10"
    },
    "manager": "director@visa.com"
  },
  "unknown@visa.com": {
    "name": "Unknown User",
    "role": null,
    "employee_type": null,
    "clearance_level": 0,
    "training_completed": [],
    "training_dates": {},
    "manager": null
  }
}
```

### `backend/config/datasets.json` (4 datasets — matches prototype modal)
```json
{
  "fraud_detection_models": {
    "id": "DS-001",
    "name": "fraud_detection_models",
    "description": "ML model definitions and performance metrics for fraud detection",
    "classification": "Internal",
    "contains_pii": false,
    "contains_mnpi": false,
    "row_count": "2.3M",
    "column_count": 47,
    "owner": "Data Science Team",
    "last_updated": "2026-02-15",
    "read_roles": ["Data Analyst", "Senior Data Analyst", "Data Scientist", "Staff Data Scientist"],
    "write_roles": ["Staff Data Scientist", "Principal Data Scientist"],
    "admin_roles": ["Principal Data Scientist", "Director of Data Science"],
    "min_clearance": 2,
    "required_training": ["InfoSec_Annual_2026"],
    "keywords": ["fraud", "models", "ml", "detection", "risk"],
    "columns": {
      "Key Metrics": ["model_id", "model_name", "accuracy_score", "precision_rate", "recall_rate", "f1_score", "false_positive_rate", "false_negative_rate"],
      "Metadata": ["training_date", "deployment_date", "version", "owner_team", "model_type"]
    }
  },
  "customer_pii_cardholder_data": {
    "id": "DS-002",
    "name": "customer_pii_cardholder_data",
    "description": "Cardholder personal information including addresses and contact details",
    "classification": "Restricted",
    "contains_pii": true,
    "contains_mnpi": false,
    "row_count": "45M",
    "column_count": 23,
    "owner": "Compliance Team",
    "last_updated": "2026-02-16",
    "read_roles": ["Senior Data Analyst", "Data Scientist", "Staff Data Scientist"],
    "write_roles": ["Staff Data Scientist", "Principal Data Scientist"],
    "admin_roles": ["Principal Data Scientist"],
    "min_clearance": 3,
    "required_training": ["PII_Handling_2026", "InfoSec_Annual_2026"],
    "pii_contractor_restriction": true,
    "keywords": ["pii", "cardholder", "customer", "personal", "address"],
    "columns": {
      "Personal Info": ["cardholder_id", "first_name", "last_name", "date_of_birth", "ssn_hash"],
      "Contact": ["email", "phone", "address_line_1", "address_line_2", "city", "state", "zip_code", "country"]
    }
  },
  "fraud_training_data": {
    "id": "DS-008",
    "name": "fraud_training_data",
    "description": "Historical transaction data used for training fraud detection models",
    "classification": "Highly Restricted",
    "contains_pii": true,
    "contains_mnpi": false,
    "row_count": "180M",
    "column_count": 89,
    "owner": "Fraud Prevention Team",
    "last_updated": "2026-02-10",
    "read_roles": ["Staff Data Scientist", "Principal Data Scientist"],
    "write_roles": ["Principal Data Scientist"],
    "admin_roles": ["Principal Data Scientist"],
    "min_clearance": 4,
    "required_training": ["PII_Handling_2026", "InfoSec_Annual_2026", "Fraud_Detection_Specialist_2026"],
    "pii_contractor_restriction": true,
    "keywords": ["fraud", "training", "transactions", "historical", "pii"],
    "columns": {
      "Transaction Data": ["transaction_id", "transaction_amt", "merchant_id", "merchant_category", "transaction_date", "card_present", "is_fraud"],
      "Features (engineered)": ["velocity_7d", "avg_transaction_amt", "merchant_risk_score", "geographic_anomaly", "time_since_last_txn"]
    }
  },
  "fraud_model_metrics": {
    "id": "DS-012",
    "name": "fraud_model_metrics",
    "description": "Daily performance logs and KPIs for production fraud detection models",
    "classification": "Internal",
    "contains_pii": false,
    "contains_mnpi": false,
    "row_count": "45M",
    "column_count": 23,
    "owner": "Analytics Team",
    "last_updated": "2026-02-16",
    "read_roles": ["Data Analyst", "Senior Data Analyst", "Data Scientist", "Staff Data Scientist"],
    "write_roles": ["Staff Data Scientist", "Principal Data Scientist"],
    "admin_roles": ["Principal Data Scientist"],
    "min_clearance": 1,
    "required_training": ["InfoSec_Annual_2026"],
    "keywords": ["fraud", "metrics", "kpi", "performance", "models", "production"],
    "columns": {
      "Performance Metrics": ["metric_date", "model_id", "true_positives", "false_positives", "true_negatives", "false_negatives", "precision", "recall", "f1_score"],
      "Volume & Latency": ["predictions_count", "avg_latency_ms", "p95_latency_ms", "error_rate"]
    }
  }
}
```

### `backend/config/policies.py`
```python
"""
ABAC Policy Rules - 8 deterministic checks
Each function returns: {requirement: str, user_value: str, match: bool}
"""

def check_role_authorization(user, dataset, access_level):
    """Check if user's role is in dataset's allowed roles for access level"""
    roles_map = {
        "read": dataset.get("read_roles", []),
        "write": dataset.get("write_roles", []),
        "admin": dataset.get("admin_roles", [])
    }
    required_roles = roles_map.get(access_level, [])
    user_role = user.get("role")
    
    return {
        "policy": "Role Authorization",
        "requirement": f"One of: [{', '.join(required_roles)}]",
        "user_value": user_role or "No role in system",
        "match": user_role in required_roles
    }

def check_clearance_level(user, dataset, access_level):
    """Check if user's clearance meets dataset minimum"""
    min_clearance = dataset.get("min_clearance", 0)
    user_clearance = user.get("clearance_level", 0)
    
    return {
        "policy": "Clearance Level",
        "requirement": f"Minimum: Level {min_clearance}",
        "user_value": f"Level {user_clearance} (verified)",
        "match": user_clearance >= min_clearance
    }

def check_access_level(user, dataset, access_level):
    """Only READ requests auto-approve; WRITE/ADMIN escalate"""
    auto_approve_eligible = (access_level == "read")
    
    return {
        "policy": "Access Level Restriction",
        "requirement": "READ requests: auto-approve eligible",
        "user_value": f"Requesting {access_level.upper()} access",
        "match": auto_approve_eligible
    }

def check_pii_restriction(user, dataset, access_level):
    """Check PII handling requirements"""
    contains_pii = dataset.get("contains_pii", False)
    
    if not contains_pii:
        return {
            "policy": "PII Restriction",
            "requirement": "No PII in dataset",
            "user_value": "N/A",
            "match": True
        }
    
    # Contractor restriction
    if dataset.get("pii_contractor_restriction") and user.get("employee_type") == "Contractor":
        return {
            "policy": "PII Restriction",
            "requirement": "FTE only for PII datasets",
            "user_value": "Contractor (requires manager approval)",
            "match": False
        }
    
    # PII training check
    has_pii_training = "PII_Handling_2026" in user.get("training_completed", [])
    return {
        "policy": "PII Restriction",
        "requirement": "PII training required",
        "user_value": "Completed PII_Handling_2026" if has_pii_training else "Missing PII training",
        "match": has_pii_training
    }

def check_training_requirements(user, dataset, access_level):
    """Check if user has completed required training"""
    required_training = dataset.get("required_training", [])
    user_training = user.get("training_completed", [])
    
    missing = [t for t in required_training if t not in user_training]
    
    if not missing:
        latest_training = required_training[0] if required_training else None
        training_date = user.get("training_dates", {}).get(latest_training, "unknown date")
        return {
            "policy": "Training Requirements",
            "requirement": ", ".join(required_training),
            "user_value": f"Completed {training_date}",
            "match": True
        }
    
    return {
        "policy": "Training Requirements",
        "requirement": ", ".join(required_training),
        "user_value": f"Missing: {', '.join(missing)}",
        "match": False
    }

def check_employment_type(user, dataset, access_level):
    """Check if employment type is valid"""
    emp_type = user.get("employee_type")
    valid = emp_type in ["FTE", "Contractor"]
    
    return {
        "policy": "Employment Type",
        "requirement": "FTE or approved contractor",
        "user_value": f"{emp_type} (verified via HR system)" if emp_type else "No employment record",
        "match": valid
    }

def check_mnpi_blackout(user, dataset, access_level):
    """Check if dataset contains MNPI (Material Non-Public Information)"""
    contains_mnpi = dataset.get("contains_mnpi", False)
    classification = dataset.get("classification", "Unknown")
    
    return {
        "policy": "MNPI Blackout",
        "requirement": "Dataset not tagged MNPI",
        "user_value": "MNPI dataset (manual review required)" if contains_mnpi else f"N/A - Dataset is {classification}",
        "match": not contains_mnpi
    }

def check_time_limited_access(user, dataset, access_level):
    """All access expires in 90 days"""
    return {
        "policy": "Time-Limited Access",
        "requirement": "All access expires in 90 days",
        "user_value": "Expiry will be set to +90 days",
        "match": True
    }

# Policy registry
ABAC_POLICIES = [
    check_role_authorization,
    check_clearance_level,
    check_access_level,
    check_pii_restriction,
    check_training_requirements,
    check_employment_type,
    check_mnpi_blackout,
    check_time_limited_access
]
```

---

## API Design (SSE STREAMING)

### Architecture Decision: Real SSE Streaming

The frontend uses `EventSource` to connect to a streaming endpoint. Each agent emits SSE events as it completes, so the UI can animate cards in real-time. This is NOT fake — the backend sends events as LangGraph nodes execute.

```
Frontend (EventSource) ←── SSE ──← FastAPI (sse-starlette) ←── LangGraph workflow
                                    │
                                    ├── event: discovery   (Agent #0 result)
                                    ├── event: intake      (Agent #1 result)
                                    ├── event: policy      (Agent #2 result)
                                    ├── event: provision   (Agent #3 result, if APPROVED)
                                    ├── event: notify      (Agent #4 result)
                                    ├── event: audit       (receipt data)
                                    └── event: done        (final summary)
```

### Endpoint 1: `GET /api/stream_workflow?request_text=...&requester_email=...&selected_dataset=...`

**Why GET not POST:** EventSource API only supports GET. Query params are URL-encoded.

**SSE Event Format** (each event is one JSON object):
```
event: discovery
data: {"agent":"DiscoveryAgent","status":"complete","duration_ms":180,"tokens":245,"matches":[...full dataset objects...],"match_count":3}

event: intake
data: {"agent":"IntakeAgent","status":"complete","duration_ms":340,"tokens":782,"extracted":{...},"reasoning":[...]}

event: policy
data: {"agent":"ABACPolicyEngine","status":"complete","duration_ms":12,"checks_run":8,"abac_checks":[...],"decision":"APPROVE","justification_note":"..."}

event: provision
data: {"agent":"ProvisioningAgent","status":"complete","duration_ms":45,"token":"eyJ...","expires_at":"2026-05-17"}

event: notify
data: {"agent":"NotificationAgent","status":"complete","duration_ms":25,"channels":["email","slack","servicenow"],"messages":[...]}

event: audit
data: {"request_id":"REQ-12345","receipt_path":"backend/receipts/REQ-12345_2026-02-16.txt","entries":[...]}

event: done
data: {"decision":"APPROVED","agents_run":5,"checks_passed":8,"checks_total":8,"total_ms":565,"total_tokens":1027}
```

### Endpoint 2: `POST /api/run_workflow` (non-streaming fallback)

**Request:**
```json
{
  "request_text": "I need fraud data for Q1 analysis",
  "requester_email": "analyst@visa.com",
  "selected_dataset": "fraud_detection_models"
}
```

Returns the same data as SSE but as a single JSON blob (for testing/curl).

### Discovery Response (FULL dataset objects — matches prototype modal)

When discovery finds multiple matches, each match includes the FULL dataset object so the frontend can render the modal with owner, classification, columns, badges:

```json
{
  "matches": [
    {
      "dataset": "fraud_detection_models",
      "id": "DS-001",
      "description": "ML model definitions and performance metrics for fraud detection",
      "classification": "Internal",
      "row_count": "2.3M",
      "column_count": 47,
      "owner": "Data Science Team",
      "last_updated": "2026-02-15",
      "contains_pii": false,
      "columns": {
        "Key Metrics": ["model_id", "model_name", "accuracy_score", "..."],
        "Metadata": ["training_date", "deployment_date", "version", "..."]
      },
      "match_score": 0.92,
      "matched_keywords": ["fraud", "models"]
    },
    {
      "dataset": "fraud_training_data",
      "id": "DS-008",
      "description": "Historical transaction data...",
      "classification": "Highly Restricted",
      "row_count": "180M",
      "column_count": 89,
      "owner": "Fraud Prevention Team",
      "last_updated": "2026-02-10",
      "contains_pii": true,
      "columns": {"Transaction Data": ["..."], "Features (engineered)": ["..."]},
      "match_score": 0.88,
      "matched_keywords": ["fraud", "training"]
    },
    {
      "dataset": "fraud_model_metrics",
      "id": "DS-012",
      "description": "Daily performance logs and KPIs for production fraud models",
      "classification": "Internal",
      "row_count": "45M",
      "column_count": 23,
      "owner": "Analytics Team",
      "last_updated": "2026-02-16",
      "contains_pii": false,
      "columns": {"Performance Metrics": ["..."], "Volume & Latency": ["..."]},
      "match_score": 0.85,
      "matched_keywords": ["fraud", "metrics"]
    }
  ]
}
```

### ABAC Check Response Format (includes `badge` for UI color-coding)

```json
{
  "policy": "Role Authorization",
  "requirement": "One of: [Data Analyst, Senior Data Analyst, Data Scientist]",
  "user_value": "Senior Data Analyst",
  "match": true,
  "badge": "g"
}
```

**Badge values:** `"g"` = green/pass, `"a"` = amber/escalate, `"r"` = red/fail, `"s"` = skip/N/A

Badge is computed server-side in `policy.py`:
- `match: true` → `"g"`
- `match: false` + policy is "Access Level" → `"a"` (escalatable)
- `match: false` + critical policy → `"r"`
- `match: false` + not assessable (unknown dataset) → `"s"`

---

## Implementation Checklist (REVISED — 5 agents, SSE streaming)

### Backend (5-6 hours)

- [ ] **Setup** (15 min)
  - [ ] Create `backend/` directory structure
  - [ ] `requirements.txt`: `fastapi`, `uvicorn`, `sse-starlette`, `anthropic`, `langgraph`, `pydantic`, `python-jose`, `python-dotenv`, `watchfiles`
  - [ ] `.env` with `ANTHROPIC_API_KEY`

- [ ] **Editable Config** (45 min)
  - [ ] Create `backend/config/users.json` with 3 users (Sarah, James, Unknown)
  - [ ] Create `backend/config/datasets.json` with **4 datasets** (fraud_detection_models, customer_pii_cardholder_data, fraud_training_data, **fraud_model_metrics DS-012**)
  - [ ] Each dataset MUST include `columns` object with grouped column names (matches prototype "View Columns" modal)
  - [ ] Create `backend/config/policies.py` with 8 ABAC functions
  - [ ] `utils.py` — Config loaders with in-memory cache + config version hash
  - [ ] Config version hash: SHA256 of `users.json + datasets.json` contents, exposed via `GET /api/config/version`

- [ ] **Agent #0: Discovery** (30 min) — `agents/discovery.py`
  - [ ] Claude-powered keyword + semantic search of dataset catalog
  - [ ] Prompt: "User requests: {text}. Match against this catalog: {datasets with descriptions + keywords}. Return ranked matches."
  - [ ] Return: **Full dataset objects** (not just name/id) — frontend needs owner, classification, columns for modal
  - [ ] Match algorithm: Claude scores relevance 0-1, also returns matched_keywords
  - [ ] Handle 3 cases:
    - Exact match (request contains literal dataset name) → skip modal, go to intake
    - Partial match (2+ results) → return matches, frontend shows modal
    - No match → return error with suggestion: "No datasets match. Try: fraud, customer, transactions"
  - [ ] Tokens/duration tracked and included in SSE event

- [ ] **Agent #1: Intake** (30 min) — `agents/intake.py`
  - [ ] Claude-powered request parsing
  - [ ] Prompt: "Extract: dataset, access_level, justification, urgency from: {text}. Dataset was selected: {selected_dataset}"
  - [ ] Return: Structured JSON + reasoning array + confidence score
  - [ ] Handle: Low confidence (<0.7) → set escalation flag
  - [ ] Tokens/duration tracked

- [ ] **Agent #2: Policy** (45 min) — `agents/policy.py`
  - [ ] ABAC engine (NO LLM)
  - [ ] Load user from `users.json` by email
  - [ ] Load dataset from `datasets.json` by name
  - [ ] Run all 8 policy functions from `policies.py`
  - [ ] Return: List of `{policy, requirement, user_value, match, badge}`
  - [ ] Badge computation: `match:true` → `"g"`, escalatable fail → `"a"`, hard fail → `"r"`, N/A → `"s"`
  - [ ] Decision logic: All pass → APPROVE, any write/admin or escalation flags → ESCALATE, any critical fail → DENY
  - [ ] Generate `justification_note` string: template-based, key off decision type
    - APPROVE: "Justification text is logged for audit but not scored. Decision based on ABAC matching above."
    - ESCALATE: "Write access to PII data requires manager approval regardless of other checks. Justification logged for manager review."
    - DENY: "Admin access to unknown dataset with insufficient justification. Multiple policy violations detected."

- [ ] **Agent #3: Provision** (20 min) — `agents/provision.py`
  - [ ] JWT token generation with dataset scope + 90-day expiry
  - [ ] Only runs if decision == APPROVE
  - [ ] Mock IAM call (log would-be API request)

- [ ] **Agent #4: Notify** (20 min) — `agents/notify.py`
  - [ ] Template-based message generation (no Jinja2 needed — simple f-strings)
  - [ ] Generate email/Slack/ServiceNow messages based on decision
  - [ ] Return array of `{channel, label, text}` objects matching prototype format

- [ ] **Receipt Writer** (15 min) — `receipts.py`
  - [ ] Generate plaintext audit receipt matching prototype "Access Decision Receipt" format
  - [ ] Write to `backend/receipts/REQ-{id}_{date}.txt`
  - [ ] Include: decision, WHO/WHAT/REASON, policy check results, technical log
  - [ ] Return receipt path + entries array in SSE `audit` event

- [ ] **LangGraph Workflow + SSE** (1 hour) — `workflow.py`
  - [ ] State machine with SSE event emission after each node
  - [ ] Node 0: Discovery (always runs; if exact match, auto-selects)
  - [ ] Node 1: Intake (parse request with selected dataset)
  - [ ] Node 2: Policy (ABAC checks)
  - [ ] Node 3: Provision (conditional: only if APPROVED)
  - [ ] Node 4: Notify (always runs)
  - [ ] After each node: yield SSE event with agent result JSON
  - [ ] Final: yield `audit` event + `done` event with summary stats
  - [ ] Error handling: if any node fails, yield `event: error` with message and stop

- [ ] **FastAPI Server** (30 min) — `server.py`
  - [ ] `GET /api/stream_workflow` → SSE streaming via `sse-starlette`
    - Query params: `request_text`, `requester_email`, `selected_dataset` (optional)
    - Returns: stream of SSE events (discovery, intake, policy, provision, notify, audit, done)
  - [ ] `POST /api/run_workflow` → Non-streaming JSON fallback (for curl/testing)
  - [ ] `GET /api/config/users` → Return users.json
  - [ ] `GET /api/config/datasets` → Return datasets.json (with columns)
  - [ ] `GET /api/config/version` → Return config version hash (for verifying reload)
  - [ ] `POST /api/config/reload` → Force reload + return new version hash
  - [ ] CORS middleware for local dev
  - [ ] Serve `frontend/` static files at root

- [ ] **Config Hot-Reload** (15 min)
  - [ ] Use `watchfiles` to watch `backend/config/*.json`
  - [ ] On file change: reload config into memory, recompute version hash
  - [ ] Log to console: `"Config reloaded (version: abc123)"`
  - [ ] Race condition mitigation: config reload is synchronous, grabs a lock before updating

### Frontend Integration (1 hour)

- [ ] **SSE consumption** — `index.html` (replaces hardcoded SCENARIOS)
  - [ ] Connect to `GET /api/stream_workflow` via `new EventSource(url)`
  - [ ] On `event: discovery` → if multiple matches, show discovery modal with full dataset cards (columns, owner, etc.)
  - [ ] On `event: intake` → animate Intake Agent card with streamed fields
  - [ ] On `event: policy` → animate ABAC checks one by one, use `badge` field for colors
  - [ ] On `event: provision` → animate Provisioning card (if present)
  - [ ] On `event: notify` → animate Notification card
  - [ ] On `event: audit` → render receipt with entries
  - [ ] On `event: done` → show result banner with stats
  - [ ] On `event: error` → show error state, re-enable Run button
  - [ ] Keep existing animation timing (sleeps between elements for visual effect)

- [ ] **Discovery modal wiring**
  - [ ] Populate modal cards from `event: discovery` data (not hardcoded HTML)
  - [ ] "View Columns" reads from `match.columns` object
  - [ ] On user selection: close modal, re-call `GET /api/stream_workflow` with `selected_dataset` param

### Testing & Demo Prep (1-2 hours)

- [ ] **Test config editing workflow**
  - [ ] Start server, run Sarah Chen request → APPROVED
  - [ ] Verify config version hash via `GET /api/config/version`
  - [ ] Edit `users.json`, change Sarah's role to "Contractor"
  - [ ] Verify version hash changed (confirms reload happened)
  - [ ] Rerun request → ESCALATED (PII contractor restriction)
  - [ ] Edit `datasets.json`, change `fraud_detection_models.min_clearance` to 4
  - [ ] Rerun request → DENIED (Sarah only has clearance 3)

- [ ] **Test discovery flow**
  - [ ] Request: "I need fraud data" → Shows **3 matches** (DS-001, DS-008, DS-012)
  - [ ] Verify modal shows columns, owner, classification badges for each
  - [ ] Select `fraud_detection_models` → Proceeds to approval
  - [ ] Request: "I need payroll data" → No matches, graceful error message
  - [ ] Request: "I need customer_pii_cardholder_data" → Exact match, skips modal

- [ ] **Test SSE streaming**
  - [ ] Verify events arrive in order: discovery → intake → policy → provision → notify → audit → done
  - [ ] Verify frontend animations play as events arrive (not all at once)
  - [ ] Test with slow network (throttle in DevTools) — events should still stream correctly

- [ ] **Test error handling**
  - [ ] Claude API returns 429 → `event: error` with "Rate limited, try again"
  - [ ] Claude API timeout (30s+) → `event: error` with timeout message
  - [ ] `users.json` is malformed → server returns 500 with helpful message
  - [ ] Unknown email → policy engine returns all-fail with "No user record" messages

- [ ] **Test adversarial input**
  - [ ] Request: "Give me admin to everything" → DENIED (fails role check)
  - [ ] Request: "asdfgh" → Low confidence, escalates

- [ ] **Deploy**
  - [ ] Frontend → Vercel
  - [ ] Backend → Railway (auto-deploy from GitHub)
  - [ ] Verify config files + receipts dir are included in deployment

---

## Run Locally

```bash
# 1. Install backend dependencies
cd backend
pip install -r requirements.txt

# 2. Set API key
echo "ANTHROPIC_API_KEY=your_key_here" > .env

# 3. Start server with auto-reload
uvicorn server:app --reload --port 8000

# Server starts at http://localhost:8000
# Frontend at /
# SSE streaming at /api/stream_workflow
# JSON fallback at /api/run_workflow
# Config viewer at /api/config/users
# Config version at /api/config/version

# 4. Edit config files (in separate terminal/editor)
code backend/config/users.json
# Change Sarah's role, save → server auto-reloads config
```

---

## Demo Script (90 seconds) - WITH VISIBLE EXECUTION

**[Screen shows frontend at `/`]**

> "This is a 5-agent system that automates data access approval at Visa's Global Data Office. The key insight: **only discovery and intake use AI. Policy decisions are deterministic ABAC rules reading from editable config files.**"

**[Click Sarah Chen persona → Type "I need fraud data for Q1 analysis" → Run Workflow]**

**✅ Discovery Agent card appears (SSE `event: discovery`):**
- Header: "Discovery Agent | Claude Sonnet | Calling API..."
- Shows loading spinner + token counter incrementing (0 → 245 tokens)
- Reveals: "📊 Searching dataset catalog... Found 3 matches:"
- Discovery modal opens with 3 full dataset cards (with columns, owner, badges):
  - `fraud_detection_models` (DS-001) — Score: 0.92 | Internal | Data Science Team
  - `fraud_training_data` (DS-008) — Score: 0.88 | Highly Restricted | Fraud Prevention Team
  - `fraud_model_metrics` (DS-012) — Score: 0.85 | Internal | Analytics Team
- User clicks "Select" on fraud_detection_models → modal closes

**✅ Intake Agent card appears:**
- Header: "Intake Agent | Claude Sonnet | Calling API..."
- Shows token counter: 0 → 782 tokens, duration: 340ms
- Streams extraction fields (typewriter effect):
  ```
  requester: analyst@visa.com ✓
  dataset: fraud_detection_models ✓
  access_level: read ✓ (inferred from "analysis")
  justification: Q1 analysis ✓
  confidence: 0.92 ✓
  ```
- Shows LLM reasoning in purple box:
  "Detected dataset from user selection. Inferred READ access from verb 'analysis'. Justification brief but has business context."

**✅ Policy Agent card appears:**
- Header: "ABAC Policy Engine | No LLM | Python Execution"
- Shows: "📂 Loading backend/config/users.json..."
- Reveals user attributes box:
  ```
  User: Sarah Chen
  Role: Senior Data Analyst
  Clearance: Level 3
  Employment: FTE
  Training: [PII_Handling_2026 ✓, InfoSec_Annual_2026 ✓]
  Manager: mike.foster@visa.com
  ```
- Shows: "📂 Loading backend/config/datasets.json..."
- Reveals dataset requirements box:
  ```
  Dataset: fraud_detection_models (DS-001)
  Classification: Internal
  Min Clearance: Level 2
  Required Training: [InfoSec_Annual_2026]
  Contains PII: No
  Read Roles: [Data Analyst, Senior Data Analyst, Data Scientist, Staff Data Scientist]
  ```
- Shows: "⚙️ Running 8 ABAC checks..."
- Displays checks one by one (with animated checkmarks):
  ```
  ✅ Role Authorization
     Requirement: One of [Data Analyst, Senior Data Analyst, Data Scientist, Staff Data Scientist]
     User Value: Senior Data Analyst ✓

  ✅ Clearance Level
     Requirement: Minimum Level 2
     User Value: Level 3 (verified) ✓

  ✅ Access Level Restriction
     Requirement: READ requests auto-approve eligible
     User Value: Requesting READ access ✓

  ✅ PII Restriction
     Requirement: No PII in dataset
     User Value: N/A ✓

  ✅ Training Requirements
     Requirement: InfoSec_Annual_2026
     User Value: Completed 2026-01-15 ✓

  ✅ Employment Type
     Requirement: FTE or approved contractor
     User Value: FTE (verified via HR system) ✓

  ✅ MNPI Blackout
     Requirement: Dataset not tagged MNPI
     User Value: N/A - Dataset is Internal ✓

  ✅ Time-Limited Access
     Requirement: All access expires in 90 days
     User Value: Expiry will be set to 2026-05-17 ✓
  ```
- Shows decision banner: **✅ DECISION: APPROVE — All 8 ABAC checks passed**
- Shows note: "ℹ️ Justification text 'Q1 analysis' logged for audit but not scored. Decision based on ABAC matching above."

**✅ Provisioning & Notification agents execute (cards appear)**

**✅ Audit Trail appears (receipt style, streamed via SSE `event: audit`):**
```
15:30:00 UTC | DiscoveryAgent | dataset_search → 3 matches found (245 tokens, 180ms)
15:30:01 UTC | IntakeAgent | parse_request → extracted 5 fields (782 tokens, 340ms)
15:30:02 UTC | ABACPolicyEngine | policy_check → APPROVED (8/8 checks passed, loaded from users.json + datasets.json)
15:30:02 UTC | ProvisioningAgent | grant_access → token visa-token-91847 (expires 2026-05-17)
15:30:03 UTC | NotificationAgent | send_notifications → 4 messages sent
```

**[Results banner: ✅ APPROVED • 5 agents • 8/8 ABAC checks • 1,027 tokens • 565ms total]**

> "Now watch what happens when I edit Sarah's config file..."

**[Split screen: Open `backend/config/users.json` in VS Code]**
**[Change Sarah's role from "Senior Data Analyst" to "Contractor"]**
**[Save file → console shows "Config reloaded"]**

**[Rerun same request]**

- Same discovery, same intake extraction
- **Policy check fails:** "Role Authorization: Contractor ∉ [Data Analyst, Senior Data Analyst, ...]"
- **Decision: ESCALATE** (contractor restriction)

**[Change back to "Senior Data Analyst", change dataset's `min_clearance` to 4]**
**[Rerun]**

- **Policy check fails:** "Clearance Level: Level 3 < required Level 4"
- **Decision: DENIED**

**[Restore config to original]**

> "That's the proof. The policy engine reads from files. The LLM only does natural language understanding—it never makes access decisions. This is the architecture for governance-sensitive workflows: **AI at the intake, rules at the core.**"

---

## Why This Architecture Works

1. **Provable data-driven logic** — Edit config → outcome changes instantly
2. **Governance-first** — Policy decisions are auditable Python + JSON, not LLM
3. **Live AI where it matters** — Claude handles discovery + intake (2 of 5 agents); 3 agents use zero LLM
4. **Real-time visibility** — SSE streaming shows each agent executing live, not a loading spinner
5. **Production-ready pattern** — Config files can be replaced with database/API in prod
6. **Interview gold** — Russell can demonstrate deep AI understanding by knowing when NOT to use it

---

## Reference Docs

- [`VISA-DEMO-PROGRESS.md`](VISA-DEMO-PROGRESS.md) — What's built, what's next
- [`plans/ux-decisions.md`](plans/ux-decisions.md) — 8 design decisions with reasoning
- [`plans/live-vs-mock-strategy.md`](plans/live-vs-mock-strategy.md) — AI vs deterministic logic
- [`plans/abac-demo-tdd-plan.md`](plans/abac-demo-tdd-plan.md) — TDD plan for ABAC implementation
- [`visa_data_approval_one_pager`](visa_data_approval_one_pager) — Demo script, talking points
