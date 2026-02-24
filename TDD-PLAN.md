# Plan 1: Enact SDK — Full Build (Template A: Full TDD)

> **Execution Mode:** Code Mode (single-domain Python SDK, clear TDD path)

---

## 0. Before Starting (CRITICAL)

### Rules:
- Read the log of past 10 commits for context
- ALWAYS make a new branch first
- Keep PROGRESS.md updated AS YOU GO
- Update tests immediately when refactoring
- Think critically — simplest solution FIRST
- Never ask user to check console — YOU debug via pytest output
- Preserve unrelated code — NEVER change code outside task scope

### 0.1 Create Feature Branch FIRST

```bash
git checkout -b feature/enact-sdk-v1
```

### 0.2 Create PROGRESS.md

```markdown
# Enact SDK v1 Progress

**Current Cost:** $X.XX

## Current Focus
[What you're working on RIGHT NOW]

## Completed
- [x] Item

## Next Steps
- [ ] Item

## Blockers
[Any issues]

## Test Status
- Tests: X/X passing
```

### 0.3 pyproject.toml (Create First — needed for pytest)

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "enact"
version = "0.1.0"
description = "An action firewall for AI agents"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.9"
dependencies = [
    "pydantic>=2.0",
    "python-dotenv",
]

[project.optional-dependencies]
postgres = ["psycopg2-binary"]
github = ["PyGithub"]
hubspot = ["hubspot-api-client"]
all = ["psycopg2-binary", "PyGithub", "hubspot-api-client"]
dev = [
    "pytest",
    "pytest-asyncio",
    "responses",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

**Commit:** `"chore: add pyproject.toml and create feature branch"`

---

## A.1 What We're Building

Enact is an action firewall for AI agents. The complete open-source Python SDK that:

```
BEFORE (today):
┌────────────────────────────────────┐
│ enact/models.py — 58 lines        │  ← Only file that exists
│ enact/__init__.py — empty          │
│ Everything else: MISSING           │
└────────────────────────────────────┘

AFTER (this plan):
┌────────────────────────────────────┐
│ enact/                             │
│ ├── models.py          ✅ EXISTS   │
│ ├── __init__.py        → exports   │
│ ├── client.py          → NEW       │  EnactClient.run() orchestrator
│ ├── policy.py          → NEW       │  Policy engine (run all, never bail)
│ ├── receipt.py         → NEW       │  HMAC-SHA256 signed receipts
│ ├── connectors/        → NEW       │  Postgres, GitHub, HubSpot
│ ├── workflows/         → NEW       │  3 reference workflows
│ └── policies/          → NEW       │  8 built-in policies (4 files)
├── tests/               → NEW       │  Full test suite
├── examples/            → NEW       │  quickstart.py
└── pyproject.toml       → NEW       │  PyPI-ready
└────────────────────────────────────┘
```

**Key Decisions:**
- No LLMs in policy path — pure Python only
- HMAC-SHA256 signed receipts (audit-trail ready)
- Connectors use vendor SDKs (psycopg2, PyGithub, hubspot-api-client)
- Policies run ALL checks — never bail early
- Workflows are thin reference implementations

---

## A.2 Existing Code to Read First

| File | Why |
|------|-----|
| `enact/models.py` | Already complete — 5 Pydantic models, DO NOT modify |
| `backend/agents/policy.py` | Policy engine pattern to generalize (badge logic, decision tree) |
| `backend/config/policies.py` | 9 ABAC check functions — pattern for built-in policies |
| `backend/receipts.py` | Receipt writer to port + add HMAC signing |
| `backend/tests/test_policy_agent.py` | Test patterns to follow (excellent structure) |
| `backend/workflow.py` | Orchestration pattern for client.py |
| `SPEC.md` | Build order and all specs |

---

## A.3 Data Flow Diagram

```
agent calls enact.run(workflow="X", actor_email="Y", payload={...})
       │
       ▼
┌─────────────────────────────────────┐
│ 1. Build WorkflowContext            │
│    (workflow, actor, payload,       │
│     systems from registered         │
│     connectors)                     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 2. Run ALL policies                 │
│    policy.evaluate_all(ctx, pols)   │
│    → list[PolicyResult]             │
│    NEVER bail early — run ALL       │
└──────────────┬──────────────────────┘
               │
        ┌──────┴──────┐
    ANY FAIL?      ALL PASS?
        │              │
        ▼              ▼
┌──────────────┐ ┌──────────────────┐
│ BLOCK        │ │ 3. Execute       │
│ receipt with │ │ workflow function │
│ actions=[]   │ │ → list[Action    │
│              │ │    Result]       │
└──────┬───────┘ └────────┬─────────┘
       │                  │
       ▼                  ▼
┌─────────────────────────────────────┐
│ 4. Build + sign Receipt             │
│    HMAC-SHA256 signature            │
│    Write to receipts/ directory     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 5. Return (RunResult, Receipt)      │
│    to calling agent                 │
└─────────────────────────────────────┘
```

---

## A.4 Files to Create

### Phase 1: Core SDK

#### `enact/policy.py`

```python
"""
Policy engine — runs all registered policies against a WorkflowContext.
Never bails early. Always runs every check.
"""
from enact.models import WorkflowContext, PolicyResult


def evaluate_all(
    context: WorkflowContext,
    policies: list,
) -> list[PolicyResult]:
    """
    Run every policy function against the context.
    Each policy is a callable: (WorkflowContext) -> PolicyResult
    Returns list of ALL results — never short-circuits.
    """
    results = []
    for policy_fn in policies:
        result = policy_fn(context)
        results.append(result)
    return results


def all_passed(results: list[PolicyResult]) -> bool:
    """Check if every policy passed."""
    return all(r.passed for r in results)
```

**Test File: `tests/test_policy_engine.py`**

```python
import pytest
from enact.policy import evaluate_all, all_passed
from enact.models import WorkflowContext, PolicyResult


def make_context(**overrides):
    """Helper to build a WorkflowContext with defaults."""
    defaults = {
        "workflow": "test_workflow",
        "actor_email": "agent@test.com",
        "payload": {"key": "value"},
        "systems": {},
    }
    defaults.update(overrides)
    return WorkflowContext(**defaults)


def policy_always_pass(ctx: WorkflowContext) -> PolicyResult:
    return PolicyResult(policy="always_pass", passed=True, reason="Always passes")


def policy_always_fail(ctx: WorkflowContext) -> PolicyResult:
    return PolicyResult(policy="always_fail", passed=False, reason="Always fails")


def policy_check_email(ctx: WorkflowContext) -> PolicyResult:
    valid = "@" in ctx.actor_email
    return PolicyResult(
        policy="check_email",
        passed=valid,
        reason="Valid email" if valid else "Invalid email format",
    )


class TestEvaluateAll:
    def test_all_pass(self):
        ctx = make_context()
        results = evaluate_all(ctx, [policy_always_pass, policy_check_email])
        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_one_fails(self):
        ctx = make_context()
        results = evaluate_all(ctx, [policy_always_pass, policy_always_fail])
        assert len(results) == 2
        assert results[0].passed is True
        assert results[1].passed is False

    def test_never_bails_early(self):
        """Even when first policy fails, ALL policies still run."""
        ctx = make_context()
        results = evaluate_all(
            ctx, [policy_always_fail, policy_always_pass, policy_always_fail]
        )
        assert len(results) == 3  # All 3 ran, not just the first failure

    def test_empty_policies(self):
        ctx = make_context()
        results = evaluate_all(ctx, [])
        assert results == []

    def test_policy_receives_context(self):
        """Verify the context is passed through to each policy."""
        received = {}
        def capture_policy(ctx):
            received["email"] = ctx.actor_email
            return PolicyResult(policy="capture", passed=True, reason="ok")

        ctx = make_context(actor_email="special@test.com")
        evaluate_all(ctx, [capture_policy])
        assert received["email"] == "special@test.com"


class TestAllPassed:
    def test_all_true(self):
        results = [
            PolicyResult(policy="a", passed=True, reason="ok"),
            PolicyResult(policy="b", passed=True, reason="ok"),
        ]
        assert all_passed(results) is True

    def test_one_false(self):
        results = [
            PolicyResult(policy="a", passed=True, reason="ok"),
            PolicyResult(policy="b", passed=False, reason="nope"),
        ]
        assert all_passed(results) is False

    def test_empty_list(self):
        assert all_passed([]) is True


class TestDeterminism:
    """Same input + same policies = same results. Always."""
    def test_idempotent(self):
        ctx = make_context()
        policies = [policy_always_pass, policy_always_fail, policy_check_email]
        run1 = evaluate_all(ctx, policies)
        run2 = evaluate_all(ctx, policies)
        assert len(run1) == len(run2)
        for r1, r2 in zip(run1, run2):
            assert r1.policy == r2.policy
            assert r1.passed == r2.passed
            assert r1.reason == r2.reason
```

---

#### `enact/receipt.py`

```python
"""
Receipt writer — builds and HMAC-SHA256 signs audit receipts.
"""
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

from enact.models import Receipt, PolicyResult, ActionResult


def build_receipt(
    workflow: str,
    actor_email: str,
    payload: dict,
    policy_results: list[PolicyResult],
    decision: str,
    actions_taken: list[ActionResult] | None = None,
) -> Receipt:
    """Build a Receipt with timestamp. Signature is empty until sign() is called."""
    return Receipt(
        workflow=workflow,
        actor_email=actor_email,
        payload=payload,
        policy_results=policy_results,
        decision=decision,
        actions_taken=actions_taken or [],
        timestamp=datetime.now(timezone.utc).isoformat(),
        signature="",
    )


def sign_receipt(receipt: Receipt, secret: str) -> Receipt:
    """
    HMAC-SHA256 sign the receipt.
    The signature covers: run_id + workflow + actor + decision + timestamp.
    Returns a new Receipt with the signature field set.
    """
    message = f"{receipt.run_id}:{receipt.workflow}:{receipt.actor_email}:{receipt.decision}:{receipt.timestamp}"
    sig = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return receipt.model_copy(update={"signature": sig})


def verify_signature(receipt: Receipt, secret: str) -> bool:
    """Verify that a receipt's signature is valid."""
    message = f"{receipt.run_id}:{receipt.workflow}:{receipt.actor_email}:{receipt.decision}:{receipt.timestamp}"
    expected = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(receipt.signature, expected)


def write_receipt(receipt: Receipt, directory: str = "receipts") -> str:
    """Write receipt to JSON file. Returns the file path."""
    os.makedirs(directory, exist_ok=True)
    filename = f"{receipt.run_id}.json"
    filepath = os.path.join(directory, filename)
    with open(filepath, "w") as f:
        json.dump(receipt.model_dump(), f, indent=2)
    return filepath
```

**Test File: `tests/test_receipt.py`**

```python
import json
import os
import pytest
from enact.receipt import build_receipt, sign_receipt, verify_signature, write_receipt
from enact.models import PolicyResult, ActionResult


@pytest.fixture
def sample_policy_results():
    return [
        PolicyResult(policy="check_a", passed=True, reason="All good"),
        PolicyResult(policy="check_b", passed=True, reason="Looks fine"),
    ]


@pytest.fixture
def sample_actions():
    return [
        ActionResult(action="create_contact", system="hubspot", success=True, output={"id": "123"}),
    ]


class TestBuildReceipt:
    def test_creates_receipt_with_uuid(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test_wf",
            actor_email="agent@co.com",
            payload={"email": "jane@acme.com"},
            policy_results=sample_policy_results,
            decision="PASS",
        )
        assert receipt.run_id  # UUID is set
        assert receipt.workflow == "test_wf"
        assert receipt.actor_email == "agent@co.com"
        assert receipt.decision == "PASS"
        assert receipt.timestamp  # ISO timestamp is set
        assert receipt.signature == ""  # Not signed yet
        assert len(receipt.policy_results) == 2
        assert receipt.actions_taken == []

    def test_block_receipt_has_no_actions(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test_wf",
            actor_email="agent@co.com",
            payload={},
            policy_results=sample_policy_results,
            decision="BLOCK",
        )
        assert receipt.decision == "BLOCK"
        assert receipt.actions_taken == []

    def test_pass_receipt_has_actions(self, sample_policy_results, sample_actions):
        receipt = build_receipt(
            workflow="test_wf",
            actor_email="agent@co.com",
            payload={},
            policy_results=sample_policy_results,
            decision="PASS",
            actions_taken=sample_actions,
        )
        assert receipt.decision == "PASS"
        assert len(receipt.actions_taken) == 1
        assert receipt.actions_taken[0].action == "create_contact"


class TestSignReceipt:
    def test_sign_produces_hex_digest(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test", actor_email="a@b.com", payload={},
            policy_results=sample_policy_results, decision="PASS",
        )
        signed = sign_receipt(receipt, secret="test-secret-key")
        assert signed.signature != ""
        assert len(signed.signature) == 64  # SHA256 hex = 64 chars

    def test_different_secrets_different_signatures(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test", actor_email="a@b.com", payload={},
            policy_results=sample_policy_results, decision="PASS",
        )
        sig1 = sign_receipt(receipt, secret="key1").signature
        sig2 = sign_receipt(receipt, secret="key2").signature
        assert sig1 != sig2

    def test_signing_is_deterministic(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test", actor_email="a@b.com", payload={},
            policy_results=sample_policy_results, decision="PASS",
        )
        sig1 = sign_receipt(receipt, secret="key").signature
        sig2 = sign_receipt(receipt, secret="key").signature
        assert sig1 == sig2


class TestVerifySignature:
    def test_valid_signature_passes(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test", actor_email="a@b.com", payload={},
            policy_results=sample_policy_results, decision="PASS",
        )
        signed = sign_receipt(receipt, secret="my-secret")
        assert verify_signature(signed, secret="my-secret") is True

    def test_wrong_secret_fails(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test", actor_email="a@b.com", payload={},
            policy_results=sample_policy_results, decision="PASS",
        )
        signed = sign_receipt(receipt, secret="my-secret")
        assert verify_signature(signed, secret="wrong-secret") is False

    def test_tampered_receipt_fails(self, sample_policy_results):
        receipt = build_receipt(
            workflow="test", actor_email="a@b.com", payload={},
            policy_results=sample_policy_results, decision="PASS",
        )
        signed = sign_receipt(receipt, secret="my-secret")
        # Tamper with the decision
        tampered = signed.model_copy(update={"decision": "BLOCK"})
        assert verify_signature(tampered, secret="my-secret") is False


class TestWriteReceipt:
    def test_writes_json_file(self, tmp_path, sample_policy_results):
        receipt = build_receipt(
            workflow="test", actor_email="a@b.com", payload={"x": 1},
            policy_results=sample_policy_results, decision="PASS",
        )
        signed = sign_receipt(receipt, secret="key")
        filepath = write_receipt(signed, directory=str(tmp_path))

        assert os.path.exists(filepath)
        with open(filepath) as f:
            data = json.load(f)
        assert data["workflow"] == "test"
        assert data["signature"] != ""

    def test_creates_directory_if_missing(self, tmp_path, sample_policy_results):
        receipt = build_receipt(
            workflow="test", actor_email="a@b.com", payload={},
            policy_results=sample_policy_results, decision="PASS",
        )
        new_dir = str(tmp_path / "nested" / "receipts")
        filepath = write_receipt(receipt, directory=new_dir)
        assert os.path.exists(filepath)
```

---

#### `enact/client.py`

```python
"""
EnactClient — the main entry point. Orchestrates the full run() loop:
build context → run policies → execute workflow → sign receipt → return result.
"""
import os
from enact.models import WorkflowContext, RunResult, Receipt
from enact.policy import evaluate_all, all_passed
from enact.receipt import build_receipt, sign_receipt, write_receipt


class EnactClient:
    def __init__(
        self,
        systems: dict | None = None,
        policies: list | None = None,
        workflows: list | None = None,
        secret: str | None = None,
        receipt_dir: str = "receipts",
    ):
        self._systems = systems or {}
        self._policies = policies or []
        self._workflows = {wf.__name__: wf for wf in (workflows or [])}
        self._secret = secret or os.environ.get("ENACT_SECRET", "enact-default-secret")
        self._receipt_dir = receipt_dir

    def run(
        self,
        workflow: str,
        actor_email: str,
        payload: dict,
    ) -> tuple[RunResult, Receipt]:
        # 1. Resolve workflow function
        if workflow not in self._workflows:
            raise ValueError(f"Unknown workflow: {workflow}. Registered: {list(self._workflows.keys())}")
        workflow_fn = self._workflows[workflow]

        # 2. Build context
        context = WorkflowContext(
            workflow=workflow,
            actor_email=actor_email,
            payload=payload,
            systems=self._systems,
        )

        # 3. Run all policies
        policy_results = evaluate_all(context, self._policies)

        # 4. Check decision
        if not all_passed(policy_results):
            # BLOCK — no actions taken
            receipt = build_receipt(
                workflow=workflow,
                actor_email=actor_email,
                payload=payload,
                policy_results=policy_results,
                decision="BLOCK",
            )
            receipt = sign_receipt(receipt, self._secret)
            write_receipt(receipt, self._receipt_dir)
            return RunResult(success=False, workflow=workflow), receipt

        # 5. PASS — execute workflow
        actions_taken = workflow_fn(context)

        # 6. Build + sign receipt
        receipt = build_receipt(
            workflow=workflow,
            actor_email=actor_email,
            payload=payload,
            policy_results=policy_results,
            decision="PASS",
            actions_taken=actions_taken,
        )
        receipt = sign_receipt(receipt, self._secret)
        write_receipt(receipt, self._receipt_dir)

        # 7. Build output from action results
        output = {a.action: a.output for a in actions_taken if a.success}
        return RunResult(success=True, workflow=workflow, output=output), receipt
```

**Test File: `tests/test_client.py`**

```python
import os
import pytest
from enact.client import EnactClient
from enact.models import WorkflowContext, PolicyResult, ActionResult


# --- Test helpers ---

def policy_pass(ctx):
    return PolicyResult(policy="pass_policy", passed=True, reason="ok")

def policy_fail(ctx):
    return PolicyResult(policy="fail_policy", passed=False, reason="blocked")

def policy_check_payload(ctx):
    has_email = "email" in ctx.payload
    return PolicyResult(
        policy="require_email", passed=has_email,
        reason="Email present" if has_email else "Missing email in payload",
    )

def dummy_workflow(ctx):
    return [
        ActionResult(action="do_thing", system="test", success=True, output={"id": "abc"}),
    ]

def multi_action_workflow(ctx):
    return [
        ActionResult(action="step_1", system="test", success=True, output={"a": 1}),
        ActionResult(action="step_2", system="test", success=True, output={"b": 2}),
    ]


class TestEnactClientInit:
    def test_registers_workflows_by_name(self):
        client = EnactClient(workflows=[dummy_workflow])
        assert "dummy_workflow" in client._workflows

    def test_default_secret(self):
        client = EnactClient()
        assert client._secret == "enact-default-secret"

    def test_custom_secret(self):
        client = EnactClient(secret="my-secret")
        assert client._secret == "my-secret"


class TestEnactClientRun:
    def test_pass_returns_success(self, tmp_path):
        client = EnactClient(
            policies=[policy_pass],
            workflows=[dummy_workflow],
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.run(
            workflow="dummy_workflow",
            actor_email="agent@test.com",
            payload={"key": "val"},
        )
        assert result.success is True
        assert result.workflow == "dummy_workflow"
        assert receipt.decision == "PASS"
        assert len(receipt.actions_taken) == 1
        assert receipt.signature != ""

    def test_block_returns_failure(self, tmp_path):
        client = EnactClient(
            policies=[policy_pass, policy_fail],
            workflows=[dummy_workflow],
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.run(
            workflow="dummy_workflow",
            actor_email="agent@test.com",
            payload={},
        )
        assert result.success is False
        assert receipt.decision == "BLOCK"
        assert receipt.actions_taken == []
        assert receipt.signature != ""

    def test_block_runs_all_policies(self, tmp_path):
        """Even if first policy fails, ALL policies run."""
        client = EnactClient(
            policies=[policy_fail, policy_pass, policy_fail],
            workflows=[dummy_workflow],
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.run(
            workflow="dummy_workflow",
            actor_email="agent@test.com",
            payload={},
        )
        assert len(receipt.policy_results) == 3  # All 3 ran

    def test_unknown_workflow_raises(self, tmp_path):
        client = EnactClient(receipt_dir=str(tmp_path))
        with pytest.raises(ValueError, match="Unknown workflow"):
            client.run(workflow="nonexistent", actor_email="a@b.com", payload={})

    def test_receipt_written_to_disk(self, tmp_path):
        client = EnactClient(
            policies=[policy_pass],
            workflows=[dummy_workflow],
            receipt_dir=str(tmp_path),
        )
        _, receipt = client.run(
            workflow="dummy_workflow",
            actor_email="agent@test.com",
            payload={},
        )
        receipt_file = tmp_path / f"{receipt.run_id}.json"
        assert receipt_file.exists()

    def test_multi_action_workflow(self, tmp_path):
        client = EnactClient(
            policies=[policy_pass],
            workflows=[multi_action_workflow],
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.run(
            workflow="multi_action_workflow",
            actor_email="agent@test.com",
            payload={},
        )
        assert result.success is True
        assert len(receipt.actions_taken) == 2
        assert "step_1" in result.output
        assert "step_2" in result.output

    def test_policy_receives_correct_context(self, tmp_path):
        """Verify policies get the right workflow context."""
        captured = {}
        def capture_policy(ctx):
            captured["workflow"] = ctx.workflow
            captured["email"] = ctx.actor_email
            captured["payload"] = ctx.payload
            return PolicyResult(policy="capture", passed=True, reason="ok")

        client = EnactClient(
            policies=[capture_policy],
            workflows=[dummy_workflow],
            receipt_dir=str(tmp_path),
        )
        client.run(workflow="dummy_workflow", actor_email="x@y.com", payload={"k": "v"})
        assert captured["workflow"] == "dummy_workflow"
        assert captured["email"] == "x@y.com"
        assert captured["payload"] == {"k": "v"}


class TestEnactClientEndToEnd:
    def test_full_pass_flow(self, tmp_path):
        """Full integration: policy pass → workflow runs → signed receipt."""
        client = EnactClient(
            policies=[policy_pass, policy_check_payload],
            workflows=[dummy_workflow],
            secret="e2e-secret",
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.run(
            workflow="dummy_workflow",
            actor_email="agent@test.com",
            payload={"email": "jane@acme.com"},
        )
        assert result.success is True
        assert receipt.decision == "PASS"
        assert len(receipt.policy_results) == 2
        assert all(r.passed for r in receipt.policy_results)
        assert receipt.signature != ""
        assert len(receipt.signature) == 64  # SHA256 hex

    def test_full_block_flow(self, tmp_path):
        """Full integration: policy fail → blocked → no actions → signed receipt."""
        client = EnactClient(
            policies=[policy_check_payload],
            workflows=[dummy_workflow],
            secret="e2e-secret",
            receipt_dir=str(tmp_path),
        )
        result, receipt = client.run(
            workflow="dummy_workflow",
            actor_email="agent@test.com",
            payload={},  # Missing email → policy fails
        )
        assert result.success is False
        assert receipt.decision == "BLOCK"
        assert receipt.actions_taken == []
        assert receipt.signature != ""
```

---

#### `enact/__init__.py`

```python
"""Enact — an action firewall for AI agents."""

from enact.client import EnactClient
from enact.models import (
    WorkflowContext,
    PolicyResult,
    ActionResult,
    Receipt,
    RunResult,
)

__all__ = [
    "EnactClient",
    "WorkflowContext",
    "PolicyResult",
    "ActionResult",
    "Receipt",
    "RunResult",
]
```

---

### Phase 2: Postgres Connector

#### `enact/connectors/__init__.py`

```python
"""Enact connectors — thin wrappers around vendor SDKs."""
```

#### `enact/connectors/postgres.py`

```python
"""
Postgres connector — works with any Postgres-compatible host:
Supabase, Neon, Railway, RDS, local.
"""
import psycopg2
import psycopg2.extras
from enact.models import ActionResult


class PostgresConnector:
    def __init__(self, dsn: str, allowed_actions: list[str] | None = None):
        self._dsn = dsn
        self._allowed_actions = set(allowed_actions or [
            "insert_row", "update_row", "select_rows", "delete_row"
        ])

    def _check_allowed(self, action: str):
        if action not in self._allowed_actions:
            raise PermissionError(f"Action '{action}' not in allowlist: {self._allowed_actions}")

    def _connect(self):
        return psycopg2.connect(self._dsn)

    def insert_row(self, table: str, data: dict) -> ActionResult:
        self._check_allowed("insert_row")
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        query = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) RETURNING *"
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(query, list(data.values()))
                    row = cur.fetchone()
                    conn.commit()
            return ActionResult(action="insert_row", system="postgres", success=True, output=dict(row))
        except Exception as e:
            return ActionResult(action="insert_row", system="postgres", success=False, output={"error": str(e)})

    def update_row(self, table: str, data: dict, where: dict) -> ActionResult:
        self._check_allowed("update_row")
        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        where_clause = " AND ".join([f"{k} = %s" for k in where.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause} RETURNING *"
        values = list(data.values()) + list(where.values())
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(query, values)
                    row = cur.fetchone()
                    conn.commit()
            return ActionResult(action="update_row", system="postgres", success=True, output=dict(row) if row else {})
        except Exception as e:
            return ActionResult(action="update_row", system="postgres", success=False, output={"error": str(e)})

    def select_rows(self, table: str, where: dict | None = None, limit: int = 100) -> ActionResult:
        self._check_allowed("select_rows")
        query = f"SELECT * FROM {table}"
        values = []
        if where:
            where_clause = " AND ".join([f"{k} = %s" for k in where.keys()])
            query += f" WHERE {where_clause}"
            values = list(where.values())
        query += f" LIMIT {limit}"
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(query, values)
                    rows = cur.fetchall()
            return ActionResult(action="select_rows", system="postgres", success=True, output={"rows": [dict(r) for r in rows]})
        except Exception as e:
            return ActionResult(action="select_rows", system="postgres", success=False, output={"error": str(e)})

    def delete_row(self, table: str, where: dict) -> ActionResult:
        self._check_allowed("delete_row")
        where_clause = " AND ".join([f"{k} = %s" for k in where.keys()])
        query = f"DELETE FROM {table} WHERE {where_clause} RETURNING *"
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(query, list(where.values()))
                    row = cur.fetchone()
                    conn.commit()
            return ActionResult(action="delete_row", system="postgres", success=True, output=dict(row) if row else {})
        except Exception as e:
            return ActionResult(action="delete_row", system="postgres", success=False, output={"error": str(e)})
```

**Test File: `tests/test_postgres.py`**

```python
import pytest
from unittest.mock import patch, MagicMock
from enact.connectors.postgres import PostgresConnector


@pytest.fixture
def connector():
    return PostgresConnector(dsn="postgresql://test:test@localhost/test")


class TestAllowlist:
    def test_default_allowlist(self):
        conn = PostgresConnector(dsn="fake")
        assert "insert_row" in conn._allowed_actions
        assert "delete_row" in conn._allowed_actions

    def test_custom_allowlist(self):
        conn = PostgresConnector(dsn="fake", allowed_actions=["select_rows"])
        assert "select_rows" in conn._allowed_actions
        assert "delete_row" not in conn._allowed_actions

    def test_blocked_action_raises(self):
        conn = PostgresConnector(dsn="fake", allowed_actions=["select_rows"])
        with pytest.raises(PermissionError, match="not in allowlist"):
            conn.insert_row(table="users", data={"name": "test"})


class TestInsertRow:
    @patch("enact.connectors.postgres.psycopg2.connect")
    def test_insert_success(self, mock_connect, connector):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1, "name": "Jane"}
        mock_connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor

        result = connector.insert_row("users", {"name": "Jane"})
        assert result.success is True
        assert result.action == "insert_row"
        assert result.system == "postgres"
        assert result.output["name"] == "Jane"

    @patch("enact.connectors.postgres.psycopg2.connect")
    def test_insert_failure(self, mock_connect, connector):
        mock_connect.side_effect = Exception("Connection failed")
        result = connector.insert_row("users", {"name": "Jane"})
        assert result.success is False
        assert "Connection failed" in result.output["error"]


class TestSelectRows:
    @patch("enact.connectors.postgres.psycopg2.connect")
    def test_select_success(self, mock_connect, connector):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{"id": 1, "name": "Jane"}]
        mock_connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor

        result = connector.select_rows("users")
        assert result.success is True
        assert len(result.output["rows"]) == 1
```

---

#### `enact/workflows/db_safe_insert.py`

```python
"""
Reference workflow: Safe database insert with constraint checking.
"""
from enact.models import WorkflowContext, ActionResult


def db_safe_insert(context: WorkflowContext) -> list[ActionResult]:
    """Insert a row into a Postgres table after checking constraints."""
    pg = context.systems["postgres"]
    table = context.payload["table"]
    data = context.payload["data"]

    # Step 1: Check if row already exists (if unique_key provided)
    results = []
    unique_key = context.payload.get("unique_key")
    if unique_key and unique_key in data:
        check = pg.select_rows(table, where={unique_key: data[unique_key]})
        results.append(check)
        if check.success and check.output.get("rows"):
            # Row exists — return early with info
            return results + [
                ActionResult(
                    action="insert_row", system="postgres", success=False,
                    output={"error": f"Row with {unique_key}={data[unique_key]} already exists"},
                )
            ]

    # Step 2: Insert the row
    insert_result = pg.insert_row(table, data)
    results.append(insert_result)
    return results
```

---

### Phase 3: GitHub Connector

#### `enact/connectors/github.py`

```python
"""
GitHub connector — wraps PyGithub for safe repository operations.
"""
from github import Github
from enact.models import ActionResult


class GitHubConnector:
    def __init__(self, token: str, allowed_actions: list[str] | None = None):
        self._github = Github(token)
        self._allowed_actions = set(allowed_actions or [
            "create_branch", "create_pr", "push_commit",
            "delete_branch", "create_issue", "merge_pr",
        ])

    def _check_allowed(self, action: str):
        if action not in self._allowed_actions:
            raise PermissionError(f"Action '{action}' not in allowlist: {self._allowed_actions}")

    def _get_repo(self, repo_name: str):
        return self._github.get_repo(repo_name)

    def create_branch(self, repo: str, branch: str, from_branch: str = "main") -> ActionResult:
        self._check_allowed("create_branch")
        try:
            repo_obj = self._get_repo(repo)
            source = repo_obj.get_branch(from_branch)
            repo_obj.create_git_ref(f"refs/heads/{branch}", source.commit.sha)
            return ActionResult(action="create_branch", system="github", success=True, output={"branch": branch})
        except Exception as e:
            return ActionResult(action="create_branch", system="github", success=False, output={"error": str(e)})

    def create_pr(self, repo: str, title: str, body: str, head: str, base: str = "main") -> ActionResult:
        self._check_allowed("create_pr")
        try:
            repo_obj = self._get_repo(repo)
            pr = repo_obj.create_pull(title=title, body=body, head=head, base=base)
            return ActionResult(action="create_pr", system="github", success=True, output={"pr_number": pr.number, "url": pr.html_url})
        except Exception as e:
            return ActionResult(action="create_pr", system="github", success=False, output={"error": str(e)})

    def create_issue(self, repo: str, title: str, body: str = "") -> ActionResult:
        self._check_allowed("create_issue")
        try:
            repo_obj = self._get_repo(repo)
            issue = repo_obj.create_issue(title=title, body=body)
            return ActionResult(action="create_issue", system="github", success=True, output={"issue_number": issue.number, "url": issue.html_url})
        except Exception as e:
            return ActionResult(action="create_issue", system="github", success=False, output={"error": str(e)})

    def delete_branch(self, repo: str, branch: str) -> ActionResult:
        self._check_allowed("delete_branch")
        try:
            repo_obj = self._get_repo(repo)
            ref = repo_obj.get_git_ref(f"heads/{branch}")
            ref.delete()
            return ActionResult(action="delete_branch", system="github", success=True, output={"branch": branch})
        except Exception as e:
            return ActionResult(action="delete_branch", system="github", success=False, output={"error": str(e)})

    def merge_pr(self, repo: str, pr_number: int) -> ActionResult:
        self._check_allowed("merge_pr")
        try:
            repo_obj = self._get_repo(repo)
            pr = repo_obj.get_pull(pr_number)
            result = pr.merge()
            return ActionResult(action="merge_pr", system="github", success=True, output={"merged": result.merged, "sha": result.sha})
        except Exception as e:
            return ActionResult(action="merge_pr", system="github", success=False, output={"error": str(e)})
```

#### `enact/workflows/agent_pr_workflow.py`

```python
"""
Reference workflow: Agent creates a branch and opens a PR (never pushes to main directly).
"""
from enact.models import WorkflowContext, ActionResult


def agent_pr_workflow(context: WorkflowContext) -> list[ActionResult]:
    """Create branch → open PR. Never push to main directly."""
    gh = context.systems["github"]
    repo = context.payload["repo"]
    branch = context.payload["branch"]
    title = context.payload.get("title", f"Agent PR: {branch}")
    body = context.payload.get("body", "Automated PR created by AI agent via Enact")

    results = []

    # Step 1: Create branch
    branch_result = gh.create_branch(repo=repo, branch=branch)
    results.append(branch_result)
    if not branch_result.success:
        return results

    # Step 2: Open PR
    pr_result = gh.create_pr(repo=repo, title=title, body=body, head=branch)
    results.append(pr_result)
    return results
```

#### `enact/policies/git.py`

```python
"""
Git policies — prevent dangerous git operations.
"""
from enact.models import WorkflowContext, PolicyResult
from datetime import datetime, timezone


def no_push_to_main(context: WorkflowContext) -> PolicyResult:
    """Block any direct push to main or master."""
    branch = context.payload.get("branch", "")
    blocked = branch.lower() in ("main", "master")
    return PolicyResult(
        policy="no_push_to_main",
        passed=not blocked,
        reason=f"Direct push to '{branch}' is blocked" if blocked else "Branch is not main/master",
    )


def max_files_per_commit(max_files: int = 50):
    """Factory: returns a policy that blocks commits touching too many files."""
    def _policy(context: WorkflowContext) -> PolicyResult:
        file_count = context.payload.get("file_count", 0)
        passed = file_count <= max_files
        return PolicyResult(
            policy="max_files_per_commit",
            passed=passed,
            reason=f"Commit touches {file_count} files (max {max_files})" if not passed
                   else f"File count {file_count} within limit of {max_files}",
        )
    return _policy


def require_branch_prefix(prefix: str = "agent/"):
    """Factory: returns a policy that requires branches to start with a prefix."""
    def _policy(context: WorkflowContext) -> PolicyResult:
        branch = context.payload.get("branch", "")
        passed = branch.startswith(prefix)
        return PolicyResult(
            policy="require_branch_prefix",
            passed=passed,
            reason=f"Branch '{branch}' must start with '{prefix}'" if not passed
                   else f"Branch '{branch}' has required prefix '{prefix}'",
        )
    return _policy
```

---

### Phase 4: Policies + HubSpot

#### `enact/connectors/hubspot.py`

```python
"""
HubSpot connector — wraps hubspot-api-client for CRM operations.
"""
from hubspot import HubSpot
from hubspot.crm.contacts import SimplePublicObjectInputForCreate
from enact.models import ActionResult


class HubSpotConnector:
    def __init__(self, api_key: str, allowed_actions: list[str] | None = None):
        self._client = HubSpot(access_token=api_key)
        self._allowed_actions = set(allowed_actions or [
            "create_contact", "update_deal", "create_task", "get_contact",
        ])

    def _check_allowed(self, action: str):
        if action not in self._allowed_actions:
            raise PermissionError(f"Action '{action}' not in allowlist: {self._allowed_actions}")

    def create_contact(self, email: str, **properties) -> ActionResult:
        self._check_allowed("create_contact")
        try:
            props = {"email": email, **properties}
            contact_input = SimplePublicObjectInputForCreate(properties=props)
            result = self._client.crm.contacts.basic_api.create(contact_input)
            return ActionResult(action="create_contact", system="hubspot", success=True, output={"id": result.id, "email": email})
        except Exception as e:
            return ActionResult(action="create_contact", system="hubspot", success=False, output={"error": str(e)})

    def get_contact(self, email: str) -> ActionResult:
        self._check_allowed("get_contact")
        try:
            # Search by email
            filter = {"propertyName": "email", "operator": "EQ", "value": email}
            search = self._client.crm.contacts.search_api.do_search(
                public_object_search_request={"filterGroups": [{"filters": [filter]}]}
            )
            if search.total > 0:
                contact = search.results[0]
                return ActionResult(action="get_contact", system="hubspot", success=True, output={"id": contact.id, "email": email, "found": True})
            return ActionResult(action="get_contact", system="hubspot", success=True, output={"found": False, "email": email})
        except Exception as e:
            return ActionResult(action="get_contact", system="hubspot", success=False, output={"error": str(e)})

    def create_task(self, contact_id: str, **properties) -> ActionResult:
        self._check_allowed("create_task")
        try:
            # HubSpot tasks are engagements
            task_data = {"associations": [{"to": {"id": contact_id}, "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 1}]}], "properties": properties}
            result = self._client.crm.objects.basic_api.create(object_type="tasks", simple_public_object_input_for_create=task_data)
            return ActionResult(action="create_task", system="hubspot", success=True, output={"id": result.id})
        except Exception as e:
            return ActionResult(action="create_task", system="hubspot", success=False, output={"error": str(e)})

    def update_deal(self, deal_id: str, **properties) -> ActionResult:
        self._check_allowed("update_deal")
        try:
            result = self._client.crm.deals.basic_api.update(deal_id=deal_id, simple_public_object_input={"properties": properties})
            return ActionResult(action="update_deal", system="hubspot", success=True, output={"id": result.id})
        except Exception as e:
            return ActionResult(action="update_deal", system="hubspot", success=False, output={"error": str(e)})
```

#### `enact/policies/crm.py`

```python
"""
CRM policies — prevent bad CRM operations.
"""
from enact.models import WorkflowContext, PolicyResult


def no_duplicate_contacts(context: WorkflowContext) -> PolicyResult:
    """Block creating a contact that already exists."""
    email = context.payload.get("email")
    if not email:
        return PolicyResult(policy="no_duplicate_contacts", passed=True, reason="No email in payload to check")

    hubspot = context.systems.get("hubspot")
    if not hubspot:
        return PolicyResult(policy="no_duplicate_contacts", passed=True, reason="No HubSpot system registered")

    result = hubspot.get_contact(email)
    if result.success and result.output.get("found"):
        return PolicyResult(
            policy="no_duplicate_contacts", passed=False,
            reason=f"Contact {email} already exists (id={result.output.get('id')})",
        )
    return PolicyResult(policy="no_duplicate_contacts", passed=True, reason=f"No existing contact for {email}")


def limit_tasks_per_contact(max_tasks: int = 3, window_days: int = 7):
    """Factory: returns a policy limiting task creation per contact."""
    def _policy(context: WorkflowContext) -> PolicyResult:
        # In v1, this checks the payload for a task_count hint
        # Full implementation would query HubSpot for recent tasks
        task_count = context.payload.get("recent_task_count", 0)
        passed = task_count < max_tasks
        return PolicyResult(
            policy="limit_tasks_per_contact",
            passed=passed,
            reason=f"Contact has {task_count} tasks in last {window_days} days (max {max_tasks})"
                   if not passed else f"Task count {task_count} within limit",
        )
    return _policy
```

#### `enact/policies/access.py`

```python
"""
Access policies — role and identity restrictions.
"""
from enact.models import WorkflowContext, PolicyResult


def contractor_cannot_write_pii(context: WorkflowContext) -> PolicyResult:
    """Block contractors from writing to PII fields."""
    actor_role = context.payload.get("actor_role", "")
    pii_fields = context.payload.get("pii_fields", [])
    writing_pii = any(f in context.payload.get("data", {}) for f in pii_fields)

    if actor_role == "contractor" and writing_pii:
        return PolicyResult(
            policy="contractor_cannot_write_pii", passed=False,
            reason="Contractors cannot write to PII fields",
        )
    return PolicyResult(
        policy="contractor_cannot_write_pii", passed=True,
        reason="No PII violation",
    )


def require_actor_role(allowed_roles: list[str]):
    """Factory: returns a policy requiring the actor to have one of the allowed roles."""
    def _policy(context: WorkflowContext) -> PolicyResult:
        actor_role = context.payload.get("actor_role", "unknown")
        passed = actor_role in allowed_roles
        return PolicyResult(
            policy="require_actor_role",
            passed=passed,
            reason=f"Role '{actor_role}' not in allowed roles: {allowed_roles}" if not passed
                   else f"Role '{actor_role}' is authorized",
        )
    return _policy
```

#### `enact/policies/time.py`

```python
"""
Time policies — enforce maintenance windows.
"""
from datetime import datetime, timezone
from enact.models import WorkflowContext, PolicyResult


def within_maintenance_window(start_hour_utc: int, end_hour_utc: int):
    """Factory: returns a policy that only allows actions during a UTC time window."""
    def _policy(context: WorkflowContext) -> PolicyResult:
        now = datetime.now(timezone.utc)
        current_hour = now.hour
        if start_hour_utc <= end_hour_utc:
            in_window = start_hour_utc <= current_hour < end_hour_utc
        else:
            # Window crosses midnight (e.g., 22-06)
            in_window = current_hour >= start_hour_utc or current_hour < end_hour_utc
        return PolicyResult(
            policy="within_maintenance_window",
            passed=in_window,
            reason=f"Current hour {current_hour} UTC is {'inside' if in_window else 'outside'} window {start_hour_utc:02d}:00-{end_hour_utc:02d}:00 UTC",
        )
    return _policy
```

#### `enact/policies/__init__.py`

```python
"""Built-in reusable policy functions."""
```

#### `enact/workflows/__init__.py`

```python
"""Reference workflow implementations."""
```

#### `enact/workflows/new_lead.py`

```python
"""
Reference workflow: New lead in HubSpot (create contact → create deal → create task).
"""
from enact.models import WorkflowContext, ActionResult


def new_lead_workflow(context: WorkflowContext) -> list[ActionResult]:
    """Create a new lead: contact + deal + follow-up task."""
    hubspot = context.systems["hubspot"]
    email = context.payload["email"]
    company = context.payload.get("company", "")

    results = []

    # Step 1: Create contact
    contact = hubspot.create_contact(email=email, company=company)
    results.append(contact)
    if not contact.success:
        return results

    contact_id = contact.output["id"]

    # Step 2: Create deal (simplified — full impl would use deals API)
    # For v1, we represent this as a task with deal info
    deal = ActionResult(
        action="create_deal", system="hubspot", success=True,
        output={"contact_id": contact_id, "value": context.payload.get("deal_value", 25000)},
    )
    results.append(deal)

    # Step 3: Create follow-up task
    task = hubspot.create_task(
        contact_id=contact_id,
        hs_task_subject=f"Follow up with {email}",
        hs_task_type="TODO",
    )
    results.append(task)
    return results
```

---

### Phase 5: Ship

#### `examples/quickstart.py`

```python
"""
Enact quickstart — matches the README example.

Usage:
    pip install enact
    python examples/quickstart.py
"""
from enact import EnactClient
from enact.models import WorkflowContext, PolicyResult, ActionResult

# --- Define a simple policy ---

def require_email_in_payload(context: WorkflowContext) -> PolicyResult:
    has_email = "email" in context.payload
    return PolicyResult(
        policy="require_email",
        passed=has_email,
        reason="Email present" if has_email else "Missing email in payload",
    )

# --- Define a simple workflow ---

def hello_workflow(context: WorkflowContext) -> list[ActionResult]:
    """A demo workflow that just returns a greeting."""
    email = context.payload["email"]
    return [
        ActionResult(
            action="greet",
            system="demo",
            success=True,
            output={"message": f"Hello, {email}!"},
        )
    ]

# --- Wire it up ---

enact = EnactClient(
    policies=[require_email_in_payload],
    workflows=[hello_workflow],
)

# Run with valid payload → PASS
print("=== Run 1: Valid payload ===")
result, receipt = enact.run(
    workflow="hello_workflow",
    actor_email="agent@company.com",
    payload={"email": "jane@acme.com"},
)
print(f"Success: {result.success}")
print(f"Output: {result.output}")
print(f"Decision: {receipt.decision}")
print(f"Signature: {receipt.signature[:16]}...")
print()

# Run without email → BLOCK
print("=== Run 2: Missing email ===")
result, receipt = enact.run(
    workflow="hello_workflow",
    actor_email="agent@company.com",
    payload={"name": "Jane"},
)
print(f"Success: {result.success}")
print(f"Decision: {receipt.decision}")
print(f"Policy results:")
for pr in receipt.policy_results:
    print(f"  {'PASS' if pr.passed else 'FAIL'} {pr.policy}: {pr.reason}")
```

---

## A.5 Files to Modify

### `enact/models.py` — NO CHANGES NEEDED

Already complete and production-ready. Do not touch.

### `.gitignore` — ADD receipts directory

**After `backend/receipts/*.txt`:**
```
▶ ADD:
receipts/
```

---

## A.6 Edge Cases & Error Handling

| Scenario | Handling Code | Test? |
|----------|---------------|-------|
| Unknown workflow name | `raise ValueError(f"Unknown workflow: {name}")` | yes |
| No policies registered | Empty list → all_passed([]) = True → PASS | yes |
| Policy function throws exception | Let it propagate (don't swallow) | yes |
| Connector action not in allowlist | `raise PermissionError(...)` | yes |
| Connector API call fails | Return `ActionResult(success=False, output={"error": str(e)})` | yes |
| Missing ENACT_SECRET env var | Fall back to "enact-default-secret" | yes |
| Receipt directory doesn't exist | `os.makedirs(directory, exist_ok=True)` | yes |
| Empty payload | Valid — policies decide what to check | yes |
| Workflow returns empty actions list | Valid — receipt has `actions_taken=[]` but decision=PASS | yes |

---

## A.7 Implementation Order (Kent Beck TDD)

### Pre-Implementation Checkpoint

1. **Can this be simpler?** — We follow the SPEC exactly. No extras.
2. **Scope discipline** — Only building what SPEC.md defines. No Cloud features.

### TDD Cycle Pattern

| Phase | Action |
|-------|--------|
| RED | Write failing test |
| GREEN | Make it pass (minimal) |
| REFACTOR | Clean up NOW |
| VERIFY | Run `pytest tests/` — ALL tests pass |
| COMMIT | `git add && git commit` |

---

### Cycle 1: Policy Engine

**Goal:** `evaluate_all()` runs all policies and returns results

| Phase | Action |
|-------|--------|
| RED | Write `tests/test_policy_engine.py` (all tests above) |
| GREEN | Create `enact/policy.py` with `evaluate_all()` and `all_passed()` |
| REFACTOR | Clean up |
| VERIFY | `pytest tests/test_policy_engine.py` — all pass |

**Files changed:** `enact/policy.py`, `tests/test_policy_engine.py`
**Test command:** `pytest tests/test_policy_engine.py -v`
**Commit:** `"feat: policy engine — evaluate_all() runs all policies, never bails early"`

---

### Cycle 2: Receipt Writer

**Goal:** Build, sign (HMAC-SHA256), verify, and write receipts to disk

| Phase | Action |
|-------|--------|
| RED | Write `tests/test_receipt.py` (all tests above) |
| GREEN | Create `enact/receipt.py` with `build_receipt()`, `sign_receipt()`, `verify_signature()`, `write_receipt()` |
| REFACTOR | Clean up |
| VERIFY | `pytest tests/test_receipt.py` — all pass |

**Files changed:** `enact/receipt.py`, `tests/test_receipt.py`
**Test command:** `pytest tests/test_receipt.py -v`
**Commit:** `"feat: receipt writer — HMAC-SHA256 signed audit receipts"`

---

### Cycle 3: EnactClient

**Goal:** `EnactClient.run()` orchestrates the full loop: policies → workflow → receipt

| Phase | Action |
|-------|--------|
| RED | Write `tests/test_client.py` (all tests above) |
| GREEN | Create `enact/client.py` with `EnactClient.__init__()` and `run()` |
| GREEN | Update `enact/__init__.py` with exports |
| REFACTOR | Clean up |
| VERIFY | `pytest tests/` — ALL tests pass |

**Files changed:** `enact/client.py`, `enact/__init__.py`, `tests/test_client.py`
**Test command:** `pytest tests/ -v`
**Commit:** `"feat: EnactClient — full run() loop with policy gate + signed receipts"`

---

### Cycle 4: Postgres Connector

**Goal:** `PostgresConnector` with allowlist enforcement and 4 CRUD actions

| Phase | Action |
|-------|--------|
| RED | Write `tests/test_postgres.py` (mocked psycopg2) |
| GREEN | Create `enact/connectors/postgres.py` |
| GREEN | Create `enact/connectors/__init__.py` |
| REFACTOR | Clean up |
| VERIFY | `pytest tests/test_postgres.py` — all pass |

**Files changed:** `enact/connectors/postgres.py`, `enact/connectors/__init__.py`, `tests/test_postgres.py`
**Test command:** `pytest tests/test_postgres.py -v`
**Commit:** `"feat: Postgres connector — insert, update, select, delete with allowlist"`

---

### Cycle 5: db_safe_insert Workflow

**Goal:** Reference workflow that checks constraints before inserting

| Phase | Action |
|-------|--------|
| RED | Write `tests/test_workflows.py` with db_safe_insert tests |
| GREEN | Create `enact/workflows/db_safe_insert.py` |
| GREEN | Create `enact/workflows/__init__.py` |
| REFACTOR | Clean up |
| VERIFY | `pytest tests/test_workflows.py` — all pass |

**Files changed:** `enact/workflows/db_safe_insert.py`, `enact/workflows/__init__.py`, `tests/test_workflows.py`
**Test command:** `pytest tests/test_workflows.py -v`
**Commit:** `"feat: db_safe_insert workflow — safe Postgres insert with constraint check"`

---

### Cycle 6: GitHub Connector

**Goal:** `GitHubConnector` with allowlist and branch/PR/issue operations

| Phase | Action |
|-------|--------|
| RED | Write `tests/test_github.py` (mocked PyGithub) |
| GREEN | Create `enact/connectors/github.py` |
| REFACTOR | Clean up |
| VERIFY | `pytest tests/test_github.py` — all pass |

**Files changed:** `enact/connectors/github.py`, `tests/test_github.py`
**Test command:** `pytest tests/test_github.py -v`
**Commit:** `"feat: GitHub connector — branch, PR, issue operations with allowlist"`

---

### Cycle 7: Git Policies + agent_pr_workflow

**Goal:** Git safety policies and the PR workflow

| Phase | Action |
|-------|--------|
| RED | Write `tests/test_git_policies.py` |
| GREEN | Create `enact/policies/git.py` (no_push_to_main, max_files_per_commit, require_branch_prefix) |
| GREEN | Create `enact/policies/__init__.py` |
| GREEN | Create `enact/workflows/agent_pr_workflow.py` |
| REFACTOR | Clean up |
| VERIFY | `pytest tests/test_git_policies.py` — all pass |

**Files changed:** `enact/policies/git.py`, `enact/policies/__init__.py`, `enact/workflows/agent_pr_workflow.py`, `tests/test_git_policies.py`
**Test command:** `pytest tests/test_git_policies.py -v`
**Commit:** `"feat: git policies + agent PR workflow — no_push_to_main, branch prefix, file limit"`

---

### Cycle 8: CRM + Access + Time Policies

**Goal:** All remaining built-in policies

| Phase | Action |
|-------|--------|
| RED | Write `tests/test_policies.py` (crm, access, time) |
| GREEN | Create `enact/policies/crm.py`, `enact/policies/access.py`, `enact/policies/time.py` |
| REFACTOR | Clean up |
| VERIFY | `pytest tests/test_policies.py` — all pass |

**Files changed:** `enact/policies/crm.py`, `enact/policies/access.py`, `enact/policies/time.py`, `tests/test_policies.py`
**Test command:** `pytest tests/test_policies.py -v`
**Commit:** `"feat: built-in policies — CRM, access control, maintenance windows"`

---

### Cycle 9: HubSpot Connector + new_lead_workflow

**Goal:** HubSpot connector and the lead workflow

| Phase | Action |
|-------|--------|
| RED | Write `tests/test_hubspot.py` (mocked HubSpot API) |
| GREEN | Create `enact/connectors/hubspot.py` |
| GREEN | Create `enact/workflows/new_lead.py` |
| REFACTOR | Clean up |
| VERIFY | `pytest tests/test_hubspot.py` — all pass |

**Files changed:** `enact/connectors/hubspot.py`, `enact/workflows/new_lead.py`, `tests/test_hubspot.py`
**Test command:** `pytest tests/test_hubspot.py -v`
**Commit:** `"feat: HubSpot connector + new_lead_workflow"`

---

### Cycle 10: Ship — pyproject.toml, examples, full test suite

**Goal:** `pip install enact` works, examples run, all tests pass

| Phase | Action |
|-------|--------|
| GREEN | Create `pyproject.toml` |
| GREEN | Create `examples/quickstart.py` |
| VERIFY | `pip install -e ".[dev]"` works |
| VERIFY | `python examples/quickstart.py` runs without errors |
| VERIFY | `pytest tests/ -v` — ALL tests pass |
| REFACTOR | Final cleanup, dead code hunt |

**Files changed:** `pyproject.toml`, `examples/quickstart.py`
**Test command:** `pytest tests/ -v && python examples/quickstart.py`
**Commit:** `"feat: ship v0.1.0 — pyproject.toml, quickstart example, full test suite"`

---

## A.8 Test Strategy

**Run Order:**
1. `pytest tests/test_policy_engine.py` — Core policy logic
2. `pytest tests/test_receipt.py` — Receipt signing/verification
3. `pytest tests/test_client.py` — Full orchestration
4. `pytest tests/test_postgres.py` — Postgres connector (mocked)
5. `pytest tests/test_github.py` — GitHub connector (mocked)
6. `pytest tests/test_hubspot.py` — HubSpot connector (mocked)
7. `pytest tests/test_git_policies.py` — Git policies
8. `pytest tests/test_policies.py` — CRM, access, time policies
9. `pytest tests/test_workflows.py` — Reference workflows
10. `pytest tests/ -v` — Full suite

**What to test (per updated philosophy):**
- Complex business logic (policy evaluation, HMAC signing, decision trees)
- Multi-step workflows (E2E: policy → workflow → receipt)
- Determinism (same input = same output)
- Allowlist enforcement (blocked actions raise PermissionError)
- Edge cases (empty policies, unknown workflows, missing fields)

**What NOT to test:**
- Pydantic model field access (getters/setters)
- JSON serialization (Pydantic handles this)
- Vendor SDK internals (mock at the boundary)

---

## A.9 Pre-Flight Checklist

- [x] Every edge case has test or graceful handling
- [x] Test patterns match codebase (pytest, Pydantic v2)
- [x] TDD cycles are minimal (10 cycles)
- [x] All code in plan is copy-paste ready
- [x] Data contracts defined (Pydantic models in models.py)
- [x] Error handling uses ActionResult(success=False) not exceptions (for connectors)

---

## A.10 ENV VARS

**Required:** None (for self-hosted OSS)

**Optional:**
- `ENACT_SECRET` — HMAC signing key (default: "enact-default-secret")
- `DATABASE_URL` — Postgres DSN (for Postgres connector)
- `GITHUB_TOKEN` — GitHub PAT (for GitHub connector)
- `HUBSPOT_API_KEY` — HubSpot access token (for HubSpot connector)

---

## A.11 Success Criteria & Cleanup

**Complete when:**
- [ ] All 10 TDD cycles pass
- [ ] `pytest tests/ -v` — 0 failures
- [ ] `pip install -e ".[dev]"` works
- [ ] `python examples/quickstart.py` runs clean
- [ ] Receipt files written to `receipts/` directory
- [ ] HMAC signatures verify correctly
- [ ] Allowlist enforcement blocks unauthorized actions
- [ ] All 8 built-in policies work
- [ ] All 3 reference workflows work
- [ ] All 3 connectors work (mocked in tests)

**Post-Build Cleanup:**
1. Get commit hash: `git log -1 --oneline`
2. Update SPEC.md — mark phases as DONE
3. Delete PROGRESS.md
4. Merge to main when ready

---

## Verification

To test the changes end-to-end:

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run full test suite
pytest tests/ -v

# Run quickstart example
python examples/quickstart.py

# Verify receipt was written
ls receipts/

# Verify HMAC signature (from Python)
python -c "
from enact.receipt import verify_signature
from enact.models import Receipt
import json, glob
f = glob.glob('receipts/*.json')[0]
r = Receipt(**json.load(open(f)))
print('Signature valid:', verify_signature(r, 'enact-default-secret'))
"
```
