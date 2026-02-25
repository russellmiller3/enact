# Plan 005: Filesystem Connector + Policies

**Template:** A (Full TDD — new connector, new policies, rollback wiring, ~400 lines)
**Date:** 2026-02-25
**Status:** Partial — connector + policies implemented. Rollback wiring + docs remain.

---

## A.1 What We're Building

A `FilesystemConnector` that lets AI agents safely read, write, delete, and list files — with the same allowlist-first, idempotent, rollback-capable design as GitHub and Postgres connectors.

Also:
- `no_merge_to_main` git policy (analogous to `no_push_to_main`, reads `payload["base"]`)
- `enact/policies/filesystem.py`: `no_delete_file`, `restrict_paths`, `block_extensions`
- Filesystem rollback dispatch in `rollback.py`

```
BEFORE                              AFTER
------                              -----
Agents can read/write/delete        FilesystemConnector with:
files with zero governance.         - allowlist-first (PermissionError if unlisted)
                                    - base_dir path confinement (traversal blocked)
Claude Code rm -rf → no receipt,   - rollback_data on every mutating action
no rollback, no policy gate.        - policies: no_delete_file, restrict_paths,
                                      block_extensions
                                    - full rollback: restore deleted/overwritten files
```

**Key Decisions:**
- `base_dir` is a required hard constraint at the connector level — all paths resolved relative to it, traversal blocked at the connector before any policy runs
- Extensions check is case-insensitive and handles dotfiles (`.env` has no `.suffix` in pathlib — use `.name` instead)
- `restrict_paths` uses `Path.resolve()` + `relative_to()` to catch traversal in any form
- `write_file` idempotent: `already_done="written"` if content unchanged, `False` otherwise
- `delete_file` idempotent: `already_done="deleted"` if file already gone, `False` otherwise

---

## A.2 Existing Code to Read First

| File | Why |
|------|-----|
| `enact/connectors/github.py` | Reference pattern: allowlist, already_done, rollback_data |
| `enact/rollback.py` | Where to add `_rollback_filesystem()` dispatcher |
| `enact/policies/db.py` | Pattern for sentinel + factory policies |
| `enact/policies/git.py` | Pattern for `no_push_to_main` → `no_merge_to_main` |

---

## A.3 Data Flow Diagram

```
EnactClient.run(context)
  │
  ├── Policy gate (payload["path"] checked by restrict_paths, block_extensions)
  │   └── BLOCK → receipt, no action
  │
  └── Workflow executes
        │
        └── FilesystemConnector
              ├── _check_allowed(action)   → PermissionError if not in allowlist
              ├── _resolve(path)           → None if outside base_dir
              └── read_file / write_file / delete_file / list_dir
                    └── ActionResult(
                          system="filesystem",
                          rollback_data={...}   # content stored for undo
                        )
```

---

## A.4 Files to Create

### FilesystemConnector

**Path:** `enact/connectors/filesystem.py`

**ActionResult shapes:**

```python
# write_file — fresh write
ActionResult(
    action="write_file", system="filesystem", success=True,
    output={"path": "src/main.py", "already_done": False},
    rollback_data={"path": "src/main.py", "previous_content": "old text or None"},
)

# write_file — idempotent (same content)
ActionResult(
    action="write_file", system="filesystem", success=True,
    output={"path": "src/main.py", "already_done": "written"},
    rollback_data={},
)

# write_file — failure
ActionResult(
    action="write_file", system="filesystem", success=False,
    output={"error": "Path '../escape' resolves outside base_dir — operation blocked"},
)

# read_file — success
ActionResult(
    action="read_file", system="filesystem", success=True,
    output={"path": "src/main.py", "content": "file contents here"},
    rollback_data={},
)

# read_file — missing file
ActionResult(
    action="read_file", system="filesystem", success=False,
    output={"error": "File not found: missing.txt"},
)

# delete_file — fresh delete
ActionResult(
    action="delete_file", system="filesystem", success=True,
    output={"path": "old.log", "already_done": False},
    rollback_data={"path": "old.log", "content": "file content before delete"},
)

# delete_file — idempotent (already gone)
ActionResult(
    action="delete_file", system="filesystem", success=True,
    output={"path": "old.log", "already_done": "deleted"},
    rollback_data={},
)

# list_dir — success
ActionResult(
    action="list_dir", system="filesystem", success=True,
    output={"path": "src", "entries": ["main.py", "utils.py"]},
    rollback_data={},
)

# path traversal error (all methods)
ActionResult(
    action="<action>", system="filesystem", success=False,
    output={"error": "Path '<path>' resolves outside base_dir — operation blocked"},
)
```

**Error strings (exact):**
```python
# PermissionError from _check_allowed
PermissionError(
    "Action 'write_file' is not in the allowed_actions list for this FilesystemConnector. "
    "Allowed: ['read_file']"
)

# Path traversal block
{"error": "Path '../escape.txt' resolves outside base_dir — operation blocked"}

# File not found (read_file)
{"error": "File not found: missing.txt"}

# Directory not found (list_dir)
{"error": "Directory not found: no_such_dir"}
```

**Test file:** `tests/test_filesystem.py` ✅ (written — 29 tests, all passing)

---

### Filesystem Policies

**Path:** `enact/policies/filesystem.py`

**Payload convention:** `payload["path"]` — the file or directory path the workflow will operate on.

**Policy output shapes:**

```python
# no_delete_file — always blocks
PolicyResult(policy="no_delete_file", passed=False,
    reason="File deletion is not permitted on this client")

# restrict_paths — blocked
PolicyResult(policy="restrict_paths", passed=False,
    reason="Path '/etc/passwd' is outside all allowed directories. Allowed: ['/workspace']")

# restrict_paths — allowed
PolicyResult(policy="restrict_paths", passed=True,
    reason="Path '/workspace/src/main.py' is within allowed directory '/workspace'")

# restrict_paths — no path in payload
PolicyResult(policy="restrict_paths", passed=True,
    reason="No path specified in payload")

# block_extensions — blocked
PolicyResult(policy="block_extensions", passed=False,
    reason="File extension '.env' is blocked — operations on '/workspace/.env' not permitted")

# block_extensions — allowed
PolicyResult(policy="block_extensions", passed=True,
    reason="File extension '.py' is not blocked")
```

**Dotfile edge case:** `Path(".env").suffix == ""` in Python. Fix: if suffix is empty and name starts with ".", use the full name as the extension.

```python
p = Path(path_str)
suffix = p.suffix.lower()
if not suffix and p.name.startswith("."):
    suffix = p.name.lower()   # ".env" treated as its own extension
```

**Test file:** `tests/test_filesystem_policies.py` ✅ (written — 20 tests, all passing)

---

### no_merge_to_main

**Path:** `enact/policies/git.py` (append to existing file)

Reads `payload["base"]` — the branch the PR merges INTO. Case-insensitive. Empty base passes through.

```python
PolicyResult(policy="no_merge_to_main", passed=False,
    reason="Merge into 'main' is blocked — PRs must target a non-protected branch")

PolicyResult(policy="no_merge_to_main", passed=True,
    reason="Merge target is not main/master")
```

**Test additions:** `tests/test_git_policies.py` ✅ (8 tests, all passing)

---

## A.5 Files to Modify

### rollback.py

**Path:** `enact/rollback.py`

Add to docstring inverse map:
```
filesystem.write_file  -> filesystem.write_file (restore previous_content)
                          OR filesystem.delete_file (if previous_content is None — file was new)
filesystem.delete_file -> filesystem.write_file (recreate with stored content)
filesystem.read_file   -> (read-only, skipped)
filesystem.list_dir    -> (read-only, skipped)
```

Add to `_READ_ONLY`:
```python
_READ_ONLY = {
    ("postgres", "select_rows"),
    ("filesystem", "read_file"),
    ("filesystem", "list_dir"),
}
```

Add filesystem dispatch in `execute_rollback_action`:
```python
elif action_result.system == "filesystem":
    return _rollback_filesystem(action_result.action, rd, connector)
```

Add `_rollback_filesystem()`:
```python
def _rollback_filesystem(action: str, rd: dict, connector) -> ActionResult:
    try:
        if action == "write_file":
            previous_content = rd.get("previous_content")
            if previous_content is None:
                # File was new — delete it to undo
                return connector.delete_file(rd["path"])
            else:
                # File existed — restore old content
                return connector.write_file(rd["path"], previous_content)

        elif action == "delete_file":
            return connector.write_file(rd["path"], rd["content"])

        else:
            return ActionResult(
                action=f"rollback_{action}",
                system="filesystem",
                success=False,
                output={"error": f"No rollback handler for filesystem.{action}"},
            )
    except Exception as e:
        return ActionResult(
            action=f"rollback_{action}",
            system="filesystem",
            success=False,
            output={"error": f"Rollback failed for filesystem.{action}: {str(e)}"},
        )
```

**Tests:** `tests/test_rollback.py` — append `TestRollbackFilesystem` class (5 tests):
- `test_rollback_write_file_restores_previous_content`
- `test_rollback_write_file_deletes_if_no_previous_content`
- `test_rollback_delete_file_recreates_file`
- `test_rollback_read_file_is_skipped`
- `test_rollback_list_dir_is_skipped`

---

## A.6 Edge Cases & Error Handling

| Scenario | Handling | Test? |
|----------|----------|-------|
| Path traversal (`../etc/passwd`) | `_resolve()` returns None → `success=False, error="...outside base_dir..."` | ✅ yes (all 4 methods) |
| Dotfile extension (`.env`) | `Path(".env").suffix == ""` → use `.name` | ✅ yes |
| Disallowed action | `_check_allowed()` raises `PermissionError` | ✅ yes |
| `write_file` same content | `already_done="written"`, no I/O | ✅ yes |
| `delete_file` already gone | `already_done="deleted"`, no I/O | ✅ yes |
| `read_file` missing file | `success=False, error="File not found: ..."` | ✅ yes |
| `list_dir` missing dir | `success=False, error="Directory not found: ..."` | ✅ yes |
| `write_file` to new subdir | `parent.mkdir(parents=True, exist_ok=True)` before write | ✅ yes |
| Rollback `write_file` with `previous_content=None` | `delete_file()` — new file, undo = delete | ✅ yes |
| `restrict_paths([])` | Empty allowed list → all paths blocked | ✅ yes |
| `block_extensions([])` | Empty blocked list → everything allowed | ✅ yes |
| Binary files | Not handled — UTF-8 only; agent-written files are text | Note in docstring |

---

## A.7 Implementation Order

### ✅ Cycle 1: no_merge_to_main

Tests: `tests/test_git_policies.py::TestNoMergeToMain` (8 tests)
Implementation: `enact/policies/git.py` — appended `no_merge_to_main()`
All passing.

### ✅ Cycle 2: FilesystemConnector

Tests: `tests/test_filesystem.py` (29 tests)
Implementation: `enact/connectors/filesystem.py`
All passing.

### ✅ Cycle 3: Filesystem Policies

Tests: `tests/test_filesystem_policies.py` (20 tests, including dotfile edge case)
Implementation: `enact/policies/filesystem.py`
All passing.

### 🔜 Cycle 4: Filesystem Rollback

**RED:** Tests appended in `tests/test_rollback.py::TestRollbackFilesystem` (5 tests)
**GREEN:** Add `_rollback_filesystem()` and update `_READ_ONLY` in `enact/rollback.py`
**VERIFY:** `pytest tests/test_rollback.py -v`

### 🔜 Cycle 5: Docs + Commit

- Update `README.md`: policy table, connector tree, test count
- Update `SPEC.md`: mark filesystem items done
- Update `Handoff.md`
- Commit + push

---

## A.8 Test Strategy

```bash
pytest tests/test_git_policies.py -v        # git policies incl. no_merge_to_main
pytest tests/test_filesystem.py -v          # connector
pytest tests/test_filesystem_policies.py -v # policies
pytest tests/test_rollback.py -v            # rollback incl. filesystem
pytest tests/ -v                            # full suite (target: 258 tests)
```

**Success Criteria:**
- [x] no_merge_to_main: 8 tests pass
- [x] FilesystemConnector: 29 tests pass
- [x] Filesystem policies: 20 tests pass
- [ ] Filesystem rollback: 5 tests pass
- [ ] Full suite clean

---

## A.9 Success Criteria & Cleanup

- [ ] All tests pass (`pytest -v`)
- [ ] README policy table includes `filesystem.py` policies + `no_merge_to_main`
- [ ] SPEC updated
- [ ] Handoff updated
- [ ] Committed and pushed
