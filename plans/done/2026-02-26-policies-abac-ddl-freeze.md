# Plan: ABAC, DDL Blocking, Code Freeze — HN Launch Polish

**Template:** B (small feature additions) + C (rename phase)
**Target files:** `enact/models.py`, `enact/policies/access.py`, `enact/policies/db.py`, `enact/policies/time.py`, all test files, examples, README, landing_page.html

---

## B.1 THE PROBLEM

Three gaps between "works" and "demo-ready for HN":

1. **Agents can READ anything.** No policy blocks `read_file("/etc/passwd")` or `select_rows("credit_cards")`. The access control story is write-only.
2. **DDL is unguarded.** Nothing stops an agent from running `DROP TABLE` or `TRUNCATE`. The Replit story is our opening pitch — we should be able to say "an agent that tries `DROP TABLE` gets blocked before it fires."
3. **No code freeze.** The Replit incident started with an explicit code freeze the agent ignored. `ENACT_FREEZE=1` + a policy that enforces it is a 30-minute fix that directly addresses a documented failure mode.

---

## B.2 THE FIX

Four phases, each committed separately:

```
Phase 1 (C): Rename actor_email → user_email everywhere (mechanical)
Phase 2 (B): Add user_attributes to WorkflowContext + new ABAC policies in access.py
Phase 3 (B): block_ddl sentinel in db.py
Phase 4 (B): code_freeze_active sentinel in time.py
```

---

## B.3 FILES INVOLVED

### New Tests Added To

| File | What gets added |
|---|---|
| `tests/test_policies.py` | TestDontReadSensitiveTables, TestDontReadSensitivePaths, TestRequireClearanceForPath, TestRequireUserRole, TestCodeFreezeActive |
| `tests/test_db_policies.py` | TestBlockDDL |

### Files Modified

| File | Changes |
|---|---|
| `enact/models.py` | Add `user_attributes: dict` field; rename `actor_email` → `user_email` |
| `enact/policies/access.py` | Add `dont_read_sensitive_tables`, `dont_read_sensitive_paths`, `require_clearance_for_path`, `require_user_role` |
| `enact/policies/db.py` | Add `block_ddl` sentinel |
| `enact/policies/time.py` | Add `code_freeze_active` sentinel |
| `enact/client.py` | Rename `actor_email` kwarg → `user_email` |
| `enact/receipt.py` | Rename field references |
| `examples/demo.py`, `examples/quickstart.py` | Rename kwarg |
| `README.md`, `landing_page.html` | Rename in code samples |
| All `tests/` files | Update `actor_email` → `user_email` in WorkflowContext constructors and `enact.run()` calls |

---

## B.4 EDGE CASES

| Scenario | Handling |
|---|---|
| `dont_read_sensitive_tables`: no `table` in payload | Pass through — can't determine target (same as `protect_tables`) |
| `dont_read_sensitive_paths`: no `path` in payload | Pass through |
| `dont_read_sensitive_paths`: `/etchosts` vs `/etc` | Use `PurePosixPath.relative_to()` — raises ValueError if not under prefix, so `/etchosts` does NOT match `/etc` |
| `require_clearance_for_path`: `clearance_level` missing from `user_attributes` | Default to 0 — missing = no clearance |
| `require_clearance_for_path`: path not in any sensitive prefix | Pass through — only applies to paths under protected prefixes |
| `require_user_role`: `role` missing from `user_attributes` | Default to `"unknown"` — missing identity fails the check |
| `block_ddl`: SQL is mixed case (`drop TABLE users`) | Case-insensitive match — `payload["sql"].upper()` |
| `block_ddl`: `sql` and `action` both absent | Pass through — no DDL to detect |
| `code_freeze_active`: `ENACT_FREEZE=0` | Pass — treat `"0"` as "not frozen"; only `"1"`, `"true"`, `"yes"` block |
| `code_freeze_active`: env var not set at all | Pass |

---

## B.5 IMPLEMENTATION STEPS

---

### Phase 1: Rename `actor_email` → `user_email` (Template C)

**Goal:** Consistent naming before adding `user_attributes`. Do this as one atomic commit.

**Step 1.1 — `enact/models.py`**

Find line: `actor_email: str`
Replace with: `user_email: str`

Also update the docstring: `actor_email  — identity` → `user_email  — identity`
And the Receipt field docstring: `actor_email  — who triggered this run` → `user_email  — who triggered this run`
And the Receipt field: `actor_email: str` → `user_email: str`
And `RunResult` (if referenced there — check first).

**Step 1.2 — `enact/client.py`**

Find `actor_email` in `run()` signature and all internal references. Replace all with `user_email`.

**Step 1.3 — `enact/receipt.py`**

Find `actor_email` references. Replace all with `user_email`.

**Step 1.4 — All test files**

In every test file, replace `actor_email=` with `user_email=` in WorkflowContext constructors and `enact.run()` calls.

Files: `tests/test_client.py`, `tests/test_db_policies.py`, `tests/test_filesystem_policies.py`, `tests/test_git_policies.py`, `tests/test_policies.py`, `tests/test_policy_engine.py`, `tests/test_receipt.py`, `tests/test_rollback.py`, `tests/test_workflows.py`

**Step 1.5 — Examples + docs**

`examples/demo.py`, `examples/quickstart.py`, `README.md`, `landing_page.html` — replace `actor_email=` with `user_email=`.

**Verify:** `pytest -v` — all 272 tests must still pass. Nothing new should break since this is a pure rename.

**Commit:** `"refactor: rename actor_email to user_email throughout"`

---

### Phase 2: `user_attributes` + ABAC policies

**Cycle 2.1 — Add `user_attributes` to `WorkflowContext`**

**RED:** The new ABAC policy tests below will fail because `WorkflowContext` doesn't accept `user_attributes` yet.

**GREEN — `enact/models.py`**, after the `systems` field (around line 43):

```python
# Attribute-based access control context — role, clearance_level, dept, etc.
# Set by the caller before run(); Enact does not verify these claims.
user_attributes: dict = Field(default_factory=dict)
```

**REFACTOR:** Update the class docstring to mention `user_attributes`.

**Verify:** `pytest -v` — all existing tests still pass (new field is optional with default `{}`).

**Cycle 2.2 — New ABAC policies in `enact/policies/access.py`**

Add `from pathlib import PurePosixPath` at the top.

Update the module-level docstring. Replace the sentence "All role information is read from context.payload rather than from a database." with:

> Role and clearance information is read from either `context.payload` (legacy `require_actor_role`, `contractor_cannot_write_pii`) or `context.user_attributes` (new `require_user_role`, `require_clearance_for_path`). Prefer `user_attributes` for new policies.

Also update the "Payload keys used by this module" block to add:
```
  "user_attributes" — structured identity dict on WorkflowContext:
      "role"            — actor role string (require_user_role)
      "clearance_level" — int clearance level, defaults to 0 if absent (require_clearance_for_path)
```

Append four functions after `require_actor_role` (add the `_is_under` helper first, then the four policy functions):

```python
def dont_read_sensitive_tables(tables: list[str]):
    """
    Factory: block select_rows when the target table is in the sensitive list.

    Reads context.payload.get("table", ""). Pass-through if no table in payload.
    Exact, case-sensitive match — same convention as protect_tables in db.py.

    Args:
        tables — list of table name strings to protect from reads

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """
    blocked = set(tables)

    def _policy(context: WorkflowContext) -> PolicyResult:
        table = context.payload.get("table", "")
        if not table:
            return PolicyResult(
                policy="dont_read_sensitive_tables",
                passed=True,
                reason="No table specified in payload",
            )
        if table in blocked:
            return PolicyResult(
                policy="dont_read_sensitive_tables",
                passed=False,
                reason=f"Table '{table}' is sensitive — read access not permitted",
            )
        return PolicyResult(
            policy="dont_read_sensitive_tables",
            passed=True,
            reason=f"Table '{table}' is not sensitive",
        )

    return _policy


def dont_read_sensitive_paths(paths: list[str]):
    """
    Factory: block read_file when the target path is under a sensitive directory.

    Uses PurePosixPath.relative_to() for prefix matching — '/etchosts' does NOT
    match the '/etc' prefix, only paths genuinely under '/etc/' do.

    Reads context.payload.get("path", ""). Pass-through if no path in payload.

    Args:
        paths — list of directory prefixes to protect (e.g. ["/etc", "/root"])

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """

    def _policy(context: WorkflowContext) -> PolicyResult:
        path = context.payload.get("path", "")
        if not path:
            return PolicyResult(
                policy="dont_read_sensitive_paths",
                passed=True,
                reason="No path specified in payload",
            )
        target = PurePosixPath(path)
        for sensitive in paths:
            if _is_under(target, PurePosixPath(sensitive)):
                return PolicyResult(
                    policy="dont_read_sensitive_paths",
                    passed=False,
                    reason=f"Path '{path}' is under sensitive prefix '{sensitive}' — read access not permitted",
                )
        return PolicyResult(
            policy="dont_read_sensitive_paths",
            passed=True,
            reason=f"Path '{path}' is not under any sensitive prefix",
        )

    return _policy


def require_clearance_for_path(paths: list[str], min_clearance: int):
    """
    ABAC factory: block access to paths under sensitive prefixes unless the actor
    has the required clearance level.

    Reads context.user_attributes.get("clearance_level", 0). Missing clearance
    defaults to 0 — an unidentified actor has no clearance. Paths not under any
    sensitive prefix pass through regardless of clearance level.

    Args:
        paths         — list of directory prefixes requiring elevated clearance
        min_clearance — minimum clearance_level required (integer)

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """

    def _policy(context: WorkflowContext) -> PolicyResult:
        path = context.payload.get("path", "")
        if not path:
            return PolicyResult(
                policy="require_clearance_for_path",
                passed=True,
                reason="No path specified in payload",
            )
        target = PurePosixPath(path)
        under_sensitive = any(
            _is_under(target, PurePosixPath(p)) for p in paths
        )
        if not under_sensitive:
            return PolicyResult(
                policy="require_clearance_for_path",
                passed=True,
                reason=f"Path '{path}' does not require elevated clearance",
            )
        clearance = context.user_attributes.get("clearance_level", 0)
        if clearance < min_clearance:
            return PolicyResult(
                policy="require_clearance_for_path",
                passed=False,
                reason=(
                    f"Clearance level {clearance} insufficient for path '{path}' "
                    f"(requires {min_clearance})"
                ),
            )
        return PolicyResult(
            policy="require_clearance_for_path",
            passed=True,
            reason=f"Clearance level {clearance} meets requirement of {min_clearance}",
        )

    return _policy


def require_user_role(*allowed_roles: str):
    """
    ABAC factory: block if the actor's role is not in the allowed set.

    Reads context.user_attributes.get("role", "unknown"). Missing role defaults
    to "unknown" — an unidentified actor fails any non-empty role check.

    Prefer this over require_actor_role for new code — it reads from
    user_attributes (structured identity context) rather than payload.

    Args:
        *allowed_roles — role strings that are permitted (e.g. "admin", "engineer")

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """
    allowed = set(allowed_roles)

    def _policy(context: WorkflowContext) -> PolicyResult:
        role = context.user_attributes.get("role", "unknown")
        passed = role in allowed
        return PolicyResult(
            policy="require_user_role",
            passed=passed,
            reason=(
                f"Role '{role}' not in allowed roles: {sorted(allowed)}"
                if not passed
                else f"Role '{role}' is authorized"
            ),
        )

    return _policy
```

Also add this private helper before the four functions (used by `require_clearance_for_path`):

```python
def _is_under(target: PurePosixPath, prefix: PurePosixPath) -> bool:
    """Return True if target is under prefix (or equals it)."""
    try:
        target.relative_to(prefix)
        return True
    except ValueError:
        return False
```

**VERIFY:** `pytest tests/test_policies.py -v`

**Commit:** `"feat: add ABAC policies and user_attributes to WorkflowContext"`

---

### Phase 3: DDL blocking (Template B)

**Cycle 3.1 — `block_ddl` in `enact/policies/db.py`**

**RED:** Write tests first in `tests/test_db_policies.py`.

**GREEN** — append to `enact/policies/db.py` after `protect_tables`.

First add `import re` at the top of `db.py` (after the existing `from enact.models import ...` line).

```python
import re

# DDL keywords that should never appear in agent-executed SQL.
# Use bare verbs (DROP, ALTER, CREATE) rather than qualified forms (ALTER TABLE,
# CREATE TABLE) so that all variants are caught: DROP VIEW, ALTER SEQUENCE,
# CREATE FUNCTION, CREATE TRIGGER, etc. TRUNCATE and DROP are already bare.
# \b word boundaries prevent matching column names like "created_at" or "creator".
_DDL_KEYWORDS = ("DROP", "TRUNCATE", "ALTER", "CREATE")
_DDL_PATTERN = re.compile(
    r'\b(?:' + '|'.join(re.escape(k) for k in _DDL_KEYWORDS) + r')\b'
)


def block_ddl(context: WorkflowContext) -> PolicyResult:
    """
    Block any operation that contains DDL keywords in payload["sql"] or payload["action"].

    Sentinel policy — register on any client where schema changes must never happen.
    The Replit database deletion incident (July 2025) was triggered by a schema push
    (`npm run db:push`). This policy is the Enact equivalent: if an agent tries to
    run DROP, TRUNCATE, ALTER TABLE, or CREATE TABLE, it gets blocked before firing.

    Detection uses word-boundary regex (\b) so "SELECT 1;DROP TABLE" is caught even
    without a leading space before DROP. Case-insensitive (input is uppercased first).
    The policy passes through if neither "sql" nor "action" is present in the payload.

    Payload keys:
        "sql"    — raw SQL string (checked for DDL keywords)
        "action" — action string (checked for DDL keywords as fallback)

    Args:
        context — WorkflowContext; reads payload["sql"] and payload["action"]

    Returns:
        PolicyResult — passed=False if any DDL keyword is found
    """
    candidates = [
        context.payload.get("sql", ""),
        context.payload.get("action", ""),
    ]
    for text in candidates:
        if not text:
            continue
        upper = text.strip().upper()
        match = _DDL_PATTERN.search(upper)
        if match:
            return PolicyResult(
                policy="block_ddl",
                passed=False,
                reason=f"DDL statement blocked: '{match.group(0)}' is not permitted",
            )
    return PolicyResult(
        policy="block_ddl",
        passed=True,
        reason="No DDL keywords detected",
    )
```

**Verify:** `pytest tests/test_db_policies.py -v`

**Commit:** `"feat: add block_ddl policy to prevent schema changes by agents"`

---

### Phase 4: Code freeze (Template B)

**Cycle 4.1 — `code_freeze_active` in `enact/policies/time.py`**

Add `import os` at the top of `time.py`.

Append after `within_maintenance_window`:

```python
# Values of ENACT_FREEZE that mean "yes, freeze is on"
_FREEZE_ON_VALUES = frozenset(("1", "true", "yes"))


def code_freeze_active(context: WorkflowContext) -> PolicyResult:
    """
    Block all operations when a code freeze is declared via environment variable.

    Set ENACT_FREEZE=1 (or "true" / "yes") in your environment to freeze all
    agent actions through this client. Unset or set to "0" / "" to lift the freeze.

    This directly addresses the Replit incident pattern: an agent that ignores an
    explicit "do not make changes" instruction. With this policy registered, the
    freeze is enforced at the action layer — the agent cannot override it.

    The check is case-insensitive. Only "1", "true", and "yes" trigger a block;
    "0" and empty string pass through. This avoids the Python string truthy trap
    where "0" would block if evaluated as bool("0").

    Args:
        context — WorkflowContext (not inspected)

    Returns:
        PolicyResult — passed=False if ENACT_FREEZE is set to a truthy value
    """
    freeze_value = os.environ.get("ENACT_FREEZE", "").strip().lower()
    if freeze_value in _FREEZE_ON_VALUES:
        return PolicyResult(
            policy="code_freeze_active",
            passed=False,
            reason=f"Code freeze is active (ENACT_FREEZE={os.environ.get('ENACT_FREEZE')}). No agent actions permitted.",
        )
    return PolicyResult(
        policy="code_freeze_active",
        passed=True,
        reason="No code freeze active",
    )
```

**Verify:** `pytest tests/test_policies.py -v`

**Commit:** `"feat: add code_freeze_active policy (ENACT_FREEZE env var)"`

---

## B.6 COMPLETE TEST CODE

### New tests for `tests/test_policies.py`

Add the following imports at the top:
```python
from enact.policies.access import (
    contractor_cannot_write_pii,
    require_actor_role,
    dont_read_sensitive_tables,
    dont_read_sensitive_paths,
    require_clearance_for_path,
    require_user_role,
)
from enact.policies.time import within_maintenance_window, code_freeze_active
```

Update `make_context` helper to accept optional `user_attributes`:
```python
def make_context(payload=None, systems=None, user_attributes=None):
    return WorkflowContext(
        workflow="test",
        user_email="agent@test.com",
        payload=payload or {},
        systems=systems or {},
        user_attributes=user_attributes or {},
    )
```

Add these test classes:

```python
# ─── ABAC: Sensitive Read Policies ───────────────────────────────────────────

class TestDontReadSensitiveTables:
    def test_passes_for_non_sensitive_table(self):
        ctx = make_context(payload={"table": "orders"})
        result = dont_read_sensitive_tables(["users", "credit_cards"])(ctx)
        assert result.passed is True
        assert result.policy == "dont_read_sensitive_tables"

    def test_blocks_for_sensitive_table(self):
        ctx = make_context(payload={"table": "credit_cards"})
        result = dont_read_sensitive_tables(["users", "credit_cards"])(ctx)
        assert result.passed is False
        assert "credit_cards" in result.reason

    def test_passes_when_no_table_in_payload(self):
        ctx = make_context(payload={})
        result = dont_read_sensitive_tables(["users"])(ctx)
        assert result.passed is True

    def test_blocks_only_exact_match(self):
        # "user_data" should not match "users"
        ctx = make_context(payload={"table": "user_data"})
        result = dont_read_sensitive_tables(["users"])(ctx)
        assert result.passed is True


class TestDontReadSensitivePaths:
    def test_passes_for_non_sensitive_path(self):
        ctx = make_context(payload={"path": "/home/user/docs/report.txt"})
        result = dont_read_sensitive_paths(["/etc", "/root"])(ctx)
        assert result.passed is True

    def test_blocks_for_path_under_sensitive_prefix(self):
        ctx = make_context(payload={"path": "/etc/passwd"})
        result = dont_read_sensitive_paths(["/etc", "/root"])(ctx)
        assert result.passed is False
        assert "/etc/passwd" in result.reason

    def test_blocks_for_nested_path_under_prefix(self):
        ctx = make_context(payload={"path": "/etc/ssh/sshd_config"})
        result = dont_read_sensitive_paths(["/etc"])(ctx)
        assert result.passed is False

    def test_does_not_match_path_with_similar_prefix(self):
        # /etchosts must NOT match /etc prefix
        ctx = make_context(payload={"path": "/etchosts"})
        result = dont_read_sensitive_paths(["/etc"])(ctx)
        assert result.passed is True

    def test_passes_when_no_path_in_payload(self):
        ctx = make_context(payload={})
        result = dont_read_sensitive_paths(["/etc"])(ctx)
        assert result.passed is True

    def test_blocks_exact_prefix_match(self):
        # /etc itself (not just things under it) should also be blocked
        ctx = make_context(payload={"path": "/etc"})
        result = dont_read_sensitive_paths(["/etc"])(ctx)
        assert result.passed is False


class TestRequireClearanceForPath:
    def test_passes_when_sufficient_clearance(self):
        ctx = make_context(
            payload={"path": "/sensitive/data.csv"},
            user_attributes={"clearance_level": 3},
        )
        result = require_clearance_for_path(["/sensitive"], 2)(ctx)
        assert result.passed is True

    def test_blocks_when_insufficient_clearance(self):
        ctx = make_context(
            payload={"path": "/sensitive/data.csv"},
            user_attributes={"clearance_level": 1},
        )
        result = require_clearance_for_path(["/sensitive"], 2)(ctx)
        assert result.passed is False
        assert "clearance" in result.reason.lower()
        assert "1" in result.reason
        assert "2" in result.reason

    def test_passes_for_non_sensitive_path_regardless_of_clearance(self):
        ctx = make_context(
            payload={"path": "/public/readme.txt"},
            user_attributes={"clearance_level": 0},
        )
        result = require_clearance_for_path(["/sensitive"], 2)(ctx)
        assert result.passed is True

    def test_blocks_when_clearance_missing_from_attributes(self):
        ctx = make_context(
            payload={"path": "/sensitive/data.csv"},
            user_attributes={},
        )
        result = require_clearance_for_path(["/sensitive"], 1)(ctx)
        assert result.passed is False
        assert "0" in result.reason  # defaults to 0

    def test_passes_when_no_path_in_payload(self):
        ctx = make_context(payload={}, user_attributes={})
        result = require_clearance_for_path(["/sensitive"], 5)(ctx)
        assert result.passed is True

    def test_passes_at_exact_clearance_level(self):
        ctx = make_context(
            payload={"path": "/sensitive/data.csv"},
            user_attributes={"clearance_level": 2},
        )
        result = require_clearance_for_path(["/sensitive"], 2)(ctx)
        assert result.passed is True


class TestRequireUserRole:
    def test_passes_for_allowed_role(self):
        ctx = make_context(user_attributes={"role": "admin"})
        result = require_user_role("admin", "engineer")(ctx)
        assert result.passed is True
        assert result.policy == "require_user_role"

    def test_passes_for_second_allowed_role(self):
        ctx = make_context(user_attributes={"role": "engineer"})
        result = require_user_role("admin", "engineer")(ctx)
        assert result.passed is True

    def test_blocks_for_disallowed_role(self):
        ctx = make_context(user_attributes={"role": "contractor"})
        result = require_user_role("admin", "engineer")(ctx)
        assert result.passed is False
        assert "contractor" in result.reason

    def test_blocks_when_role_missing(self):
        ctx = make_context(user_attributes={})
        result = require_user_role("admin")(ctx)
        assert result.passed is False
        assert "unknown" in result.reason

    def test_blocks_when_user_attributes_empty(self):
        ctx = make_context()
        result = require_user_role("admin")(ctx)
        assert result.passed is False


# ─── Time: Code Freeze ────────────────────────────────────────────────────────

class TestCodeFreezeActive:
    def test_passes_when_freeze_not_set(self, monkeypatch):
        monkeypatch.delenv("ENACT_FREEZE", raising=False)
        ctx = make_context()
        result = code_freeze_active(ctx)
        assert result.passed is True
        assert result.policy == "code_freeze_active"

    def test_blocks_when_freeze_is_1(self, monkeypatch):
        monkeypatch.setenv("ENACT_FREEZE", "1")
        ctx = make_context()
        result = code_freeze_active(ctx)
        assert result.passed is False
        assert "freeze" in result.reason.lower()

    def test_blocks_when_freeze_is_true(self, monkeypatch):
        monkeypatch.setenv("ENACT_FREEZE", "true")
        ctx = make_context()
        result = code_freeze_active(ctx)
        assert result.passed is False

    def test_blocks_when_freeze_is_yes(self, monkeypatch):
        monkeypatch.setenv("ENACT_FREEZE", "yes")
        ctx = make_context()
        result = code_freeze_active(ctx)
        assert result.passed is False

    def test_blocks_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("ENACT_FREEZE", "TRUE")
        ctx = make_context()
        result = code_freeze_active(ctx)
        assert result.passed is False

    def test_passes_when_freeze_is_0(self, monkeypatch):
        monkeypatch.setenv("ENACT_FREEZE", "0")
        ctx = make_context()
        result = code_freeze_active(ctx)
        assert result.passed is True

    def test_passes_when_freeze_is_empty_string(self, monkeypatch):
        monkeypatch.setenv("ENACT_FREEZE", "")
        ctx = make_context()
        result = code_freeze_active(ctx)
        assert result.passed is True
```

### New tests for `tests/test_db_policies.py`

Add import:
```python
from enact.policies.db import dont_delete_row, dont_delete_without_where, dont_update_without_where, protect_tables, block_ddl
```

Add test class:
```python
class TestBlockDDL:
    def test_passes_when_no_sql_in_payload(self):
        ctx = make_context(payload={})
        result = block_ddl(ctx)
        assert result.passed is True
        assert result.policy == "block_ddl"

    def test_blocks_drop_table(self):
        ctx = make_context(payload={"sql": "DROP TABLE users"})
        result = block_ddl(ctx)
        assert result.passed is False
        assert "DROP" in result.reason

    def test_blocks_truncate(self):
        ctx = make_context(payload={"sql": "TRUNCATE TABLE users"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_blocks_alter_table(self):
        ctx = make_context(payload={"sql": "ALTER TABLE users ADD COLUMN foo TEXT"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_blocks_alter_sequence(self):
        # ALTER bare verb catches ALTER SEQUENCE, ALTER VIEW, etc.
        ctx = make_context(payload={"sql": "ALTER SEQUENCE payments_id_seq RESTART WITH 1"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_blocks_create_table(self):
        ctx = make_context(payload={"sql": "CREATE TABLE new_table (id INT)"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_blocks_create_function(self):
        # CREATE bare verb catches CREATE FUNCTION, CREATE VIEW, CREATE TRIGGER, etc.
        ctx = make_context(payload={"sql": "CREATE FUNCTION inject() RETURNS void AS $$ $$ LANGUAGE sql"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_blocks_drop_view(self):
        # DROP bare verb catches DROP VIEW, DROP FUNCTION, DROP SEQUENCE, etc.
        ctx = make_context(payload={"sql": "DROP VIEW active_users"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_blocks_case_insensitive(self):
        ctx = make_context(payload={"sql": "drop table users"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_passes_for_select(self):
        ctx = make_context(payload={"sql": "SELECT * FROM users WHERE id = 1"})
        result = block_ddl(ctx)
        assert result.passed is True

    def test_passes_for_insert(self):
        ctx = make_context(payload={"sql": "INSERT INTO users (email) VALUES ('a@b.com')"})
        result = block_ddl(ctx)
        assert result.passed is True

    def test_passes_for_update(self):
        ctx = make_context(payload={"sql": "UPDATE users SET name = 'foo' WHERE id = 1"})
        result = block_ddl(ctx)
        assert result.passed is True

    def test_passes_column_named_created_at(self):
        # "created_at" must NOT trigger — \b after CREATE fails because next char is '_'
        ctx = make_context(payload={"sql": "SELECT created_at FROM users WHERE id = 1"})
        result = block_ddl(ctx)
        assert result.passed is True

    def test_blocks_via_action_key(self):
        ctx = make_context(payload={"action": "DROP TABLE payments"})
        result = block_ddl(ctx)
        assert result.passed is False

    def test_passes_when_action_is_non_ddl(self):
        ctx = make_context(payload={"action": "insert_row"})
        result = block_ddl(ctx)
        assert result.passed is True

    def test_passes_when_sql_is_empty_string(self):
        # Empty string sql key — nothing to inspect, should pass
        ctx = make_context(payload={"sql": ""})
        result = block_ddl(ctx)
        assert result.passed is True

    def test_blocks_semicolon_joined_ddl(self):
        # No space before DROP — word boundary regex still catches it
        ctx = make_context(payload={"sql": "SELECT 1;DROP TABLE users"})
        result = block_ddl(ctx)
        assert result.passed is False
```

---

## B.7 DATA CONTRACTS

### `WorkflowContext` (updated)

```python
class WorkflowContext(BaseModel):
    workflow: str
    user_email: str                      # renamed from actor_email
    payload: dict
    systems: dict = Field(default_factory=dict)
    user_attributes: dict = Field(default_factory=dict)  # NEW
```

### New policy payload conventions

| Policy | Payload key | Type | Notes |
|---|---|---|---|
| `dont_read_sensitive_tables` | `payload["table"]` | str | Same key as `protect_tables` — consistent |
| `dont_read_sensitive_paths` | `payload["path"]` | str | Same key as `restrict_paths` |
| `require_clearance_for_path` | `payload["path"]`, `user_attributes["clearance_level"]` | str, int | clearance_level defaults to 0 if absent |
| `require_user_role` | `user_attributes["role"]` | str | defaults to "unknown" if absent |
| `block_ddl` | `payload["sql"]`, `payload["action"]` | str, str | either key triggers check |
| `code_freeze_active` | env `ENACT_FREEZE` | str | "1", "true", "yes" = blocked |

---

## B.8 SUCCESS CRITERIA

- [ ] Phase 1: `pytest -v` — 272 tests pass (rename only, no logic change)
- [ ] Phase 2: `pytest tests/test_policies.py -v` — new ABAC tests pass
- [ ] Phase 3: `pytest tests/test_db_policies.py -v` — DDL tests pass
- [ ] Phase 4: `pytest tests/test_policies.py -v` — code freeze tests pass
- [ ] Final: `pytest -v` — all tests pass (count > 272)
- [ ] No dead code
- [ ] Committed and pushed

---

## Scope Discipline

**NOT touching:**
- `enact/connectors/` — no connector changes
- `enact/workflows/` — no workflow changes
- `enact/rollback.py` — no rollback changes
- `enact/receipt.py` — only the `actor_email` rename, no logic changes
- `plans/` files — historical, not renamed
