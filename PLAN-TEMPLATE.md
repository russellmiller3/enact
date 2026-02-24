# Plan [NUMBER]: [FEATURE NAME]

---

## CHOOSE YOUR TEMPLATE

| Template | Use When | TDD? |
|---|---|---|
| **[A: Full TDD](#template-a-full-tdd-greenfield-features)** | New features from scratch (>200 lines, multiple files) | Kent Beck cycles |
| **[B: Small Plan](#template-b-small-plan-bug-fixes--small-features)** | Bug fixes, small features (<200 lines) | Simplified cycles |
| **[C: Refactoring](#template-c-refactoringmigration)** | Renaming, restructuring, migrations | Test verification only |

```
Is the logic already written and tested?
|-- YES -> Template C (Refactoring/Migration)
|-- NO -> Building new logic?
    |-- Small (<200 lines, 1-2 files) -> Template B
    |-- Large (>200 lines, multiple systems) -> Template A
```

---

## CRITICAL RULES (ALL TEMPLATES)

### Copy these into Step 0 of every plan.

### Read the last 10 commits for context

### ALWAYS make a new branch first

### UPDATE TESTS WHEN CHANGING CODE

Tests and code change in the SAME step. Never commit code changes that break existing tests.

```bash
# CORRECT
# 1. Change code
# 2. Update tests in same step
# 3. pytest -v
# 4. git commit

# WRONG
# 1. Change code
# 2. git commit   <-- tests fail, commit rejected
# 3. scramble to fix tests
```

### CRITICAL THINKING MANDATE (Karpathy's Law)

**BEFORE implementing ANYTHING:**

- **Flag confusion** - Any ambiguity? Stop. Ask Russell.
- **Surface inconsistencies** - Plan contradicts code? Stop. Point it out.
- **Present tradeoffs** - Multiple ways? Stop. Show options with pros/cons.
- **Simplest solution FIRST** - Can this be 50 lines instead of 500?
- **Push back** - Plan seems overcomplicated? Say why.
- **Preserve unrelated code** - NEVER change code outside your task scope.

### TEST PATTERNS (enact-sdk)

```python
# Fixture pattern — patch PyGithub at import
@pytest.fixture
def connector():
    with patch("enact.connectors.github.Github"):
        return GitHubConnector(token="fake-token")

# Mock pattern — replace _get_repo to control API responses
mock_repo = MagicMock()
connector._get_repo = MagicMock(return_value=mock_repo)

# Assert ActionResult
assert result.success is True
assert result.action == "create_branch"
assert result.output["branch"] == "agent/feature-x"

# Assert API was called correctly
mock_repo.create_git_ref.assert_called_once_with("refs/heads/branch", "sha")
```

---

# TEMPLATE A: Full TDD (Greenfield Features)

**Use for:** New features from scratch (>200 lines, multiple systems)

## A.1 What We're Building

[User-facing description with ASCII diagrams]

```
BEFORE -> AFTER
```

**Key Decisions:**
- [Decision 1 with rationale]

## A.2 Existing Code to Read First

| File | Why |
|---|---|
| `path` | Reason |

## A.3 Data Flow Diagram

```
Input -> Processing -> Output
```

## A.4 Files to Create

### Module Name

**Path:** `exact/path/to/file.py`

```python
# Full code — copy-paste ready
```

**Test File (COMPLETE CODE):**

```python
import pytest
from unittest.mock import patch, MagicMock

class TestFeature:
    def test_happy_path(self):
        # Setup
        # Act
        # Assert
        pass

    def test_failure_case(self):
        pass

    def test_edge_case(self):
        pass
```

## A.5 Files to Modify

### File Name

**Path:** `path`
**Line ~XX** (after `marker code`)

```python
# ADD/REPLACE:
[code]
```

## A.6 Edge Cases & Error Handling

| Scenario | Handling | Test? |
|---|---|---|
| API timeout | Return ActionResult(success=False, output={"error": ...}) | yes |
| Missing required field | Raise ValueError with clear message | yes |

## A.7 Implementation Order (Kent Beck TDD)

### PRE-IMPLEMENTATION CHECKPOINT

1. **Can this be simpler?** (YAGNI check)
2. **Do I understand the task?**
3. **Scope discipline** - What am I NOT touching?

### TDD Cycle Pattern

| Phase | Action |
|---|---|
| RED | Write failing test |
| GREEN | Make it pass (minimal) |
| REFACTOR | Clean up NOW |
| VERIFY | Run pytest, confirm pass |

### Cycle 1: [Smallest testable unit]

**Goal:** [What this achieves]

| Phase | Action |
|---|---|
| RED | Test: `test_specific_behavior` |
| GREEN | Implement minimal code |
| REFACTOR | Clean up |
| VERIFY | `pytest tests/path/test.py::TestClass::test_name -v` |

**Files changed:** [list]
**Commit:** `"feat: [desc]"`

### Cycle 2, 3, etc...

[Repeat pattern]

## A.8 Test Strategy

```bash
# Run specific test
pytest tests/test_file.py::TestClass::test_name -v

# Run all tests for a file
pytest tests/test_file.py -v

# Run full suite
pytest -v
```

**Success Criteria:**
- [ ] All new tests pass
- [ ] All existing tests still pass
- [ ] No dead code

## A.9 Success Criteria & Cleanup

- [ ] All tests pass (`pytest -v`)
- [ ] No dead code
- [ ] Committed and pushed

---

# TEMPLATE B: Small Plan (Bug Fixes & Small Features)

**Use for:** Bug fixes, small features (<200 lines, 1-2 files)

## B.1 THE PROBLEM

**What's broken or missing:** [1-2 sentences]

**Root Cause:** [Why current approach fails]

## B.2 THE FIX

**Key Insight:** [The "aha" moment]

```
BEFORE -> AFTER
```

**Why This Works:**
- [Reason 1]
- [Reason 2]

## B.3 FILES INVOLVED

### New Files

| File | Purpose |
|---|---|
| `path/file.py` | Description |
| `tests/test_file.py` | Tests |

### Files to Modify

| File | Changes |
|---|---|
| `path/existing.py` | What gets added/changed |

## B.4 EDGE CASES

| Scenario | Handling |
|---|---|
| [Case 1] | [How we handle it] |
| [Case 2] | [How we handle it] |

## B.5 IMPLEMENTATION STEPS

### Cycle 1: [Smallest unit]

| Step | Action |
|---|---|
| RED | Test: expect [behavior] |
| GREEN | Implement minimal code |
| REFACTOR | Cleanup |

**Verify:** `pytest tests/test_file.py -v`
**Commit:** `"feat/fix: [desc]"`

### Cycle 2: [Next unit]

[Same pattern]

## B.6 SUCCESS CRITERIA

- [ ] All new tests pass
- [ ] All existing tests still pass
- [ ] `pytest -v` clean

---

# TEMPLATE C: Refactoring/Migration

**Use for:** Renaming, restructuring, migrations (existing tested logic)

## C.1 Observations

**Current state:** [What exists now]
**Goal:** [What we want]

## C.2 Approach

1. **Phase 1:** [e.g., Rename all references]
2. **Phase 2:** [e.g., Move to new structure]
3. **Phase 3:** [e.g., Cleanup old code]

## C.3 Phase 1: [Name]

**Goal:** [What this phase achieves]

### 1.1 [Task]

```bash
# Exact commands or code changes
```

### 1.2 Verify Tests Pass

```bash
pytest -v
```

**Fix failures BEFORE proceeding.**

### 1.3 Commit Phase 1

```bash
git add [files]
git commit -m "refactor: [desc]"
```

## C.4 Phase 2, 3, etc...

[Same pattern per phase]

## C.5 Success Criteria

- [ ] All phases complete
- [ ] Tests passing (`pytest -v`)
- [ ] No dead code
- [ ] No stray references to old names

---

## QUICK REFERENCE

**"I'm adding a new feature"** -> >200 lines? A. Otherwise B.
**"I'm fixing a bug"** -> Template B
**"I'm renaming/restructuring"** -> Template C
**"Not sure"** -> Start B, escalate to A if it grows
