# Red Team Mode — Enact Plan-Proofing Guide

**Created:** 2026-02-24
**Purpose:** Make plans so bulletproof that implementation can't go wrong

---

## Core Philosophy

Red Team doesn't just find holes — it **fills them with explicit code and specs** that can be copy-pasted directly into the implementation.

The goal: a plan so detailed that a half-asleep dev at 3am could implement it correctly.

**If Red Team says "add a test" without writing the test → Red Team failed.**

---

## When to Use It

```
Plan Mode → Red Team Mode → Code Mode
 (draft)    (bulletproof)   (implement)
```

**Use for:**
- Any plan with connector methods (psycopg2 SQL footguns everywhere)
- Plans with transaction logic (commit/rollback edge cases)
- API integrations (data contracts between layers)
- Anything that involves ActionResult output shapes
- Any plan where you'd be embarrassed if the tests didn't catch what you missed

**Skip for:**
- One-liner fixes
- Config-only changes
- Plans you're implementing yourself (you ARE the red team)

---

## What Red Team Produces

### 1. Every Test Written Out (pytest, copy-paste ready)

Not "add a test for X" — the actual test code:

```python
# ❌ WRONG — AI will write a lazy test
"Add test for DB error handling"

# ✅ RIGHT — copy-paste ready
def test_insert_rolls_back_on_constraint_violation():
    conn = make_conn()
    conn.cursor.side_effect = Exception("unique constraint violated")
    pg = make_pg(conn=conn)

    result = pg.insert_row("users", {"email": "dup@acme.com"})

    assert result.success is False
    assert "unique constraint violated" in result.output["error"]
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
```

### 2. ActionResult Data Contracts

Every connector method needs exact output shapes documented:

```python
# insert_row — SUCCESS shape
ActionResult(
    action="insert_row",
    system="postgres",
    success=True,
    output={
        "id": 42,                    # int, DB-assigned — always present if RETURNING *
        "email": "jane@acme.com",    # string, echoed from DB
        "already_done": False,       # bool — always False for insert
    }
)

# insert_row — FAILURE shape
ActionResult(
    action="insert_row",
    system="postgres",
    success=False,
    output={
        "error": "unique constraint violated"  # str(e) from psycopg2
        # NO already_done on failure
    }
)
```

### 3. Exact Error Message Strings

Not "show error" — the exact strings:

```python
# PermissionError from _check_allowed
PermissionError("Action 'insert_row' not in allowlist: {'select_rows'}")

# ImportError when psycopg2 missing
ImportError(
    "psycopg2 is required for PostgresConnector. "
    "Install it with: pip install 'enact-sdk[postgres]'"
)

# ActionResult error output — always str(e)
{"error": "connection refused"}
{"error": "relation \"users\" does not exist"}
{"error": "unique constraint violated on column \"email\""}
```

### 4. Transaction Safety Table

For every mutating method, verify commit/rollback paths:

| Method | Success path | Error path | Rollback needed? |
|--------|-------------|------------|-----------------|
| `select_rows` | No commit (read-only) | No rollback | No |
| `insert_row` | `conn.commit()` after fetchone | `conn.rollback()` | Yes |
| `update_row` | `conn.commit()` after execute | `conn.rollback()` | Yes |
| `delete_row` | `conn.commit()` after execute | `conn.rollback()` | Yes |

**Footgun:** Calling `commit()` BEFORE `fetchone()` — the cursor closes and RETURNING data is lost.

**Correct order:**
```python
cursor.execute(query, params)
row = cursor.fetchone()   # BEFORE commit
conn.commit()             # AFTER fetching
```

### 5. SQL Injection Safety Checklist

For every SQL operation, check identifier vs value handling:

| Part of query | Method | Example | Safe? |
|--------------|--------|---------|-------|
| Table name | `pgsql.Identifier(table)` | `"users"` → `"users"` | ✅ |
| Column name in WHERE | `pgsql.Identifier(k)` | `"email"` → `"email"` | ✅ |
| Column value | `pgsql.Placeholder()` + params | `%s` + `["jane@acme.com"]` | ✅ |
| Raw f-string for table | `f"SELECT * FROM {table}"` | — | ❌ NEVER |
| Raw f-string for value | `f"WHERE email='{val}'"` | — | ❌ NEVER |

**Red Team mandate:** Any f-string in a SQL query is an auto-fail. Replace with `pgsql.Identifier` / `pgsql.Placeholder`.

---

## Attack Checklist

### 🚨 PRIORITY 1: Idempotency Contract Verification

The `already_done` convention is the most important contract in enact. Every mutating method must follow it exactly.

**Check every mutating method:**

| Method | Condition for `already_done: "..."` | Value |
|--------|-------------------------------------|-------|
| `create_branch` (GitHub) | Branch already exists | `"created"` |
| `delete_branch` (GitHub) | Branch already gone | `"deleted"` |
| `insert_row` (Postgres) | — (handled at workflow level) | always `False` |
| `delete_row` (Postgres) | `rowcount == 0` | `"deleted"` |
| `update_row` (Postgres) | — (setting same value is harmless) | always `False` |

**Auto-fail if:** Any mutating method returns `success=True` without `already_done` in the output.

---

### 🚨 PRIORITY 2: Transaction Rollback Coverage

**Every `conn.commit()` must have a paired `conn.rollback()` in the except block.**

```python
# ❌ MISSING rollback — DB left in inconsistent state
def insert_row(self, table, data):
    conn = self._get_connection()
    with conn.cursor() as cursor:
        cursor.execute(query, params)
        conn.commit()
    # Error here leaves transaction open!

# ✅ CORRECT — rollback on any failure
def insert_row(self, table, data):
    conn = None
    try:
        conn = self._get_connection()
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            conn.commit()
            return ActionResult(success=True, ...)
    except Exception as e:
        if conn:
            conn.rollback()
        return ActionResult(success=False, output={"error": str(e)})
```

**Check:** `conn = None` initializer before try block — so `if conn: conn.rollback()` works even when `_get_connection()` itself fails.

---

### 🚨 PRIORITY 3: Mock Cursor Context Manager Pattern

The psycopg2 cursor is used as a context manager: `with conn.cursor() as cursor:`.
This means `conn.cursor()` must return an object with `__enter__` / `__exit__`.

```python
# ❌ BROKEN — MagicMock() default doesn't match context manager protocol correctly
mock_cursor = MagicMock()
mock_conn.cursor.return_value = mock_cursor  # cursor() returns cursor directly
# But `with conn.cursor() as cursor:` calls __enter__ — you get a MagicMock, not cursor

# ✅ CORRECT — set up the context manager properly
cursor = make_cursor(rows=[...], description=[("id",)])
cm = MagicMock()
cm.__enter__ = MagicMock(return_value=cursor)
cm.__exit__ = MagicMock(return_value=False)
conn.cursor.return_value = cm
```

**Red Team must verify:** Every cursor mock in tests uses the CM setup. If tests have bare `conn.cursor.return_value = cursor`, they will fail when the connector uses `with conn.cursor() as cursor:`.

---

### 🚨 PRIORITY 4: Import/Export Audit

For every new module:

| Check | Example |
|-------|---------|
| Module importable without optional dep? | `try/except ImportError` at top of connector file |
| Graceful ImportError message? | "Install it with: pip install 'enact-sdk[postgres]'" |
| `__init__.py` updated if publicly exported? | Does `enact/__init__.py` need updating? |
| Test file imports correct module path? | `from enact.connectors.postgres import PostgresConnector` |

---

### 🚨 PRIORITY 5: Edge Cases — The Big Table

For every connector method, fill this out:

| Input | Edge Case | Expected Behavior | Test? |
|-------|-----------|-------------------|-------|
| `table` | SQL injection in table name | `pgsql.Identifier` handles it | No (library handles it) |
| `where` | Empty dict `{}` | Same as `None` — fetch all | Yes |
| `where` | Multi-column | AND-joined conditions | Yes |
| `data` | Empty dict `{}` | `INSERT INTO x () VALUES ()` — let DB decide | Document |
| `data` | 1 key | Single column insert | Yes |
| `data` | Many keys | Correct placeholder count | Yes |
| DB error | Connection dropped mid-transaction | rollback + ActionResult failure | Yes |
| DB error | Constraint violation | rollback + ActionResult failure | Yes |

---

## TDD Cycle Requirements

Each cycle MUST have:

1. **The exact test code** (copy-paste ready, not described)
2. **The test command**: `pytest tests/test_postgres.py::TestClass::test_name -v`
3. **What "green" looks like**: "Test passes, cursor.execute called once, conn.commit called once"
4. **The implementation code** for simple cycles

Example of a proper cycle:

```markdown
### Cycle 1: delete_row idempotency 🔴🟢🔄

**Test (add to TestDeleteRow in tests/test_postgres.py):**

```python
def test_zero_rows_deleted_returns_already_done_deleted(self):
    cursor = make_cursor(rowcount=0)
    conn = make_conn(cursor)
    pg = make_pg(conn=conn)

    result = pg.delete_row("users", where={"id": 999})

    assert result.success is True
    assert result.output["rows_deleted"] == 0
    assert result.output["already_done"] == "deleted"
```

**Run:** `pytest tests/test_postgres.py::TestDeleteRow::test_zero_rows_deleted_returns_already_done_deleted -v`

**Implementation (in delete_row, after conn.commit()):**

```python
rows_deleted = cursor.rowcount
return ActionResult(
    action="delete_row",
    system="postgres",
    success=True,
    output={
        "rows_deleted": rows_deleted,
        "already_done": "deleted" if rows_deleted == 0 else False,
    },
)
```

**Green means:** Test passes, `already_done` is `"deleted"` when rowcount is 0, `False` otherwise.
```

---

## Red Team Output Format

**CRITICAL:** Red Team produces TWO separate outputs:

### Output 1: Updated Plan File (for the implementing AI)

The plan file gets:
- **All Red Team fixes applied directly** — code blocks corrected, tests written out, edge cases added
- **ZERO Red Team commentary** — no attack summaries, no "I found this bug", no meta-discussion
- **Restructured to follow `PLAN-TEMPLATE.md` order** if it was out of order

The implementing AI doesn't care what was wrong — it just needs clean instructions.

### Output 2: Attack Report (for Russell, in chat)

Deliver to Russell in the conversation, NOT in the plan file:

#### 🎯 Attack Summary

- **Critical** (blocks implementation): What you found and what you fixed
- **Moderate** (will cause bugs): Same
- **Low** (tech debt): Note for later

#### 📋 What Was Fixed

- Bugs in code blocks
- Missing tests (with the actual test code written)
- Wrong ActionResult shapes
- Transaction footguns
- Missing rollbacks

#### ⚠️ Remaining Risks

- Anything still risky that needs attention during implementation

---

## What Goes IN the Plan vs. OUT

| Content | In Plan? | In Chat Report? |
|---------|----------|-----------------|
| Implementation code | ✅ Yes | ❌ No |
| Test code | ✅ Yes | ❌ No |
| ActionResult shapes | ✅ Yes | ❌ No |
| Error strings | ✅ Yes | ❌ No |
| "I found this bug" | ❌ No | ✅ Yes |
| Attack summary | ❌ No | ✅ Yes |
| Red Team reasoning | ❌ No | ✅ Yes |
| Fixes you applied | ❌ No | ✅ Yes |

---

## Devil's Advocate Questions (enact-specific)

For EVERY feature, ask:

1. **"What if the DB connection drops mid-transaction?"** → Rollback happens? State is consistent?
2. **"What if the agent retries this workflow?"** → `already_done` handled correctly for this method?
3. **"What if `where` dict is empty?"** → Deletes everything? That's probably a bug.
4. **"What will the AI assume about column names?"** → Explicit with `pgsql.Identifier`?
5. **"What if psycopg2 isn't installed?"** → Graceful ImportError with install hint?
6. **"What if RETURNING * returns no row?"** → `fetchone()` returns `None` — handled?
7. **"What if the allowlist is empty `[]`?"** → Every action raises PermissionError — is that intentional?

---

## The Complete Workflow

```
1. Write plan (Plan Mode)
2. Red-team the plan (find holes, write fixes)
3. Apply all fixes directly to the plan file (clean, no commentary)
4. Tell Russell in chat:
   - What bugs were found
   - What was fixed
   - Any remaining risks
5. Russell approves → Code Mode implements
```

### What Red Team DOES:
- Fixes bugs in code blocks
- Writes missing tests (actual code, not descriptions)
- Verifies ActionResult shapes match the convention
- Checks transaction commit/rollback coverage
- Saves clean plan

### What Red Team DOES NOT:
- Leave Red Team commentary in plan files
- Just list problems without fixing them
- Say "add a test" without writing the test

If Red Team finds architectural issues that need redesign, say so in chat and stop.
