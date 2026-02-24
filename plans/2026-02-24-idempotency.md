# Plan 1: GitHub Connector Idempotency

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make every GitHub connector method safe to retry — if the thing already exists, return success instead of failing.

**Architecture:** Each method gets a "check first" guard before the mutating API call. The guard uses PyGithub lookups. If the resource is already in the desired state, return `ActionResult(success=True)` with `already_done` set to a descriptive string. No new models, no new files — just smarter methods.

**Tech Stack:** Python 3.9+, PyGithub, pytest, unittest.mock

**Template:** B (Small Plan — <200 lines, 1 file + tests)

---

## `already_done` Convention

Every connector action includes an `already_done` key in its output dict. One field, two jobs — programmatic check AND human-readable explanation.

```python
# Fresh action — always False
{"branch": "agent/feature-x", "already_done": False}

# Idempotent hit — the value IS the explanation
{"branch": "agent/feature-x", "already_done": "created"}
{"branch": "agent/old",       "already_done": "deleted"}
{"merged": True,              "already_done": "merged"}
```

**Programmatic check:** `if result.output.get("already_done"):` — strings are truthy, `False` is falsy.

| Action | `already_done` value | Meaning |
|---|---|---|
| `create_branch` | `"created"` | Branch with this name already exists |
| `create_pr` | `"created"` | Open PR for same head->base already exists |
| `create_issue` | `"created"` | Open issue with same title already exists |
| `delete_branch` | `"deleted"` | Branch was already gone (404) |
| `merge_pr` | `"merged"` | PR was already merged |

**Why one field:** Every future connector (SendGrid, Postgres, HubSpot) will use this same key. Callers never need to know which connector they're talking to — just `if result.output.get("already_done")`. The value tells humans what happened; the truthiness tells code.

---

## B.1 THE PROBLEM

**What's broken or missing:** If an agent retries a workflow (network blip, timeout, crash recovery), the GitHub connector creates duplicate branches, PRs, and issues. `create_branch` fails with "Reference already exists", `create_pr` fails with 422, etc. The agent sees `success=False` and may retry again, making things worse.

**Root Cause:** Every method is fire-and-forget. None of them check whether the operation was already performed.

## B.2 THE FIX

**Key Insight:** Every GitHub resource has a natural lookup — branches by name, PRs by head+base, issues by title, merges by `pr.merged`. Check before acting. If already done, return success with the reason.

```
BEFORE: create_branch("feature-x") -> API call -> 422 "already exists" -> ActionResult(success=False)

AFTER:  create_branch("feature-x") -> check: branch exists?
            YES -> ActionResult(success=True, already_done="created")
            NO  -> create it -> ActionResult(success=True, already_done=False)
```

## B.3 FILES INVOLVED

| File | Changes |
|---|---|
| `enact/connectors/github.py` | Add idempotency guards to all 5 methods, import `UnknownObjectException` |
| `tests/test_github.py` | Add idempotency tests for each method |

## B.4 EDGE CASES

| Scenario | Handling |
|---|---|
| Branch exists on retry | Return success + `already_done: "created"` |
| PR already open for same head->base | Return success + existing PR info + `already_done: "created"` |
| PR closed (not merged) for same head->base | Create new PR (closed PRs shouldn't block new ones) |
| Issue with same title exists | Return success + existing issue info + `already_done: "created"` |
| Branch already deleted | Return success + `already_done: "deleted"` |
| PR already merged | Return success + `already_done: "merged"` |
| Idempotency check itself fails (API error) | Fall through to normal create — don't let the guard break the happy path |

## B.5 IMPLEMENTATION STEPS

### Step 0: Branch

```bash
git checkout -b feature/idempotency
```

---

### Cycle 1: `create_branch` idempotency

**Goal:** `create_branch` returns success when branch already exists.

**Test:**

```python
class TestCreateBranchIdempotency:
    def test_create_branch_returns_success_when_already_exists(self, connector):
        """Retry safety: if branch already exists, return success with already_done."""
        mock_repo = MagicMock()
        mock_repo.get_branch.return_value.commit.sha = "abc123"
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_branch(repo="owner/repo", branch="agent/feature-x")

        assert result.success is True
        assert result.output["branch"] == "agent/feature-x"
        assert result.output["already_done"] == "created"
        mock_repo.create_git_ref.assert_not_called()
```

**Implementation — replace `create_branch` in `enact/connectors/github.py:89-125`:**

```python
def create_branch(
    self, repo: str, branch: str, from_branch: str = "main"
) -> ActionResult:
    self._check_allowed("create_branch")
    try:
        repo_obj = self._get_repo(repo)
        # Idempotency: check if target branch already exists
        try:
            repo_obj.get_branch(branch)
            return ActionResult(
                action="create_branch",
                system="github",
                success=True,
                output={"branch": branch, "already_done": "created"},
            )
        except Exception:
            pass  # Branch doesn't exist — proceed to create

        source = repo_obj.get_branch(from_branch)
        repo_obj.create_git_ref(f"refs/heads/{branch}", source.commit.sha)
        return ActionResult(
            action="create_branch",
            system="github",
            success=True,
            output={"branch": branch, "already_done": False},
        )
    except Exception as e:
        return ActionResult(
            action="create_branch",
            system="github",
            success=False,
            output={"error": str(e)},
        )
```

**Verify:** `pytest tests/test_github.py::TestCreateBranchIdempotency tests/test_github.py::TestCreateBranch -v`
**Commit:** `"feat: make create_branch idempotent"`

---

### Cycle 2: `create_pr` idempotency

**Goal:** `create_pr` returns existing PR info when one is already open for same head->base.

**Tests:**

```python
class TestCreatePRIdempotency:
    def test_create_pr_returns_existing_when_open(self, connector):
        """Retry safety: if open PR exists for same head->base, return it."""
        mock_repo = MagicMock()
        mock_existing_pr = MagicMock()
        mock_existing_pr.number = 42
        mock_existing_pr.html_url = "https://github.com/owner/repo/pull/42"
        mock_repo.get_pulls.return_value = [mock_existing_pr]
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_pr(
            repo="owner/repo", title="Agent PR", body="Automated", head="agent/feature-x",
        )

        assert result.success is True
        assert result.output["pr_number"] == 42
        assert result.output["already_done"] == "created"
        mock_repo.create_pull.assert_not_called()

    def test_create_pr_creates_when_no_open_pr(self, connector):
        """Normal path: no existing PR, creates new one."""
        mock_repo = MagicMock()
        mock_repo.get_pulls.return_value = []
        mock_new_pr = MagicMock()
        mock_new_pr.number = 43
        mock_new_pr.html_url = "https://github.com/owner/repo/pull/43"
        mock_repo.create_pull.return_value = mock_new_pr
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_pr(
            repo="owner/repo", title="Agent PR", body="Automated", head="agent/feature-x",
        )

        assert result.success is True
        assert result.output["pr_number"] == 43
        assert result.output["already_done"] is False
```

**Implementation — replace `create_pr` in `enact/connectors/github.py:127-160`:**

```python
def create_pr(
    self, repo: str, title: str, body: str, head: str, base: str = "main"
) -> ActionResult:
    self._check_allowed("create_pr")
    try:
        repo_obj = self._get_repo(repo)
        # Idempotency: check for existing open PR with same head->base
        try:
            existing = list(repo_obj.get_pulls(state="open", head=head, base=base))
            if existing:
                pr = existing[0]
                return ActionResult(
                    action="create_pr",
                    system="github",
                    success=True,
                    output={"pr_number": pr.number, "url": pr.html_url, "already_done": "created"},
                )
        except Exception:
            pass  # Lookup failed — proceed to create

        pr = repo_obj.create_pull(title=title, body=body, head=head, base=base)
        return ActionResult(
            action="create_pr",
            system="github",
            success=True,
            output={"pr_number": pr.number, "url": pr.html_url, "already_done": False},
        )
    except Exception as e:
        return ActionResult(
            action="create_pr",
            system="github",
            success=False,
            output={"error": str(e)},
        )
```

**Verify:** `pytest tests/test_github.py::TestCreatePRIdempotency tests/test_github.py::TestCreatePR -v`
**Commit:** `"feat: make create_pr idempotent"`

---

### Cycle 3: `create_issue` idempotency

**Goal:** `create_issue` returns existing issue when open issue with same title exists.

**Tests:**

```python
class TestCreateIssueIdempotency:
    def test_create_issue_returns_existing_when_title_matches(self, connector):
        """Retry safety: if open issue with same title exists, return it."""
        mock_repo = MagicMock()
        mock_existing = MagicMock()
        mock_existing.number = 7
        mock_existing.html_url = "https://github.com/owner/repo/issues/7"
        mock_existing.title = "Bug found"
        mock_repo.get_issues.return_value = [mock_existing]
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_issue(repo="owner/repo", title="Bug found")

        assert result.success is True
        assert result.output["issue_number"] == 7
        assert result.output["already_done"] == "created"
        mock_repo.create_issue.assert_not_called()

    def test_create_issue_creates_when_no_match(self, connector):
        """Normal path: no matching open issue, creates new one."""
        mock_repo = MagicMock()
        mock_repo.get_issues.return_value = []
        mock_new_issue = MagicMock()
        mock_new_issue.number = 8
        mock_new_issue.html_url = "https://github.com/owner/repo/issues/8"
        mock_repo.create_issue.return_value = mock_new_issue
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.create_issue(repo="owner/repo", title="New bug")

        assert result.success is True
        assert result.output["issue_number"] == 8
        assert result.output["already_done"] is False
```

**Implementation — replace `create_issue` in `enact/connectors/github.py:162-191`:**

```python
def create_issue(self, repo: str, title: str, body: str = "") -> ActionResult:
    self._check_allowed("create_issue")
    try:
        repo_obj = self._get_repo(repo)
        # Idempotency: check for open issue with same title
        try:
            for issue in repo_obj.get_issues(state="open"):
                if issue.title == title:
                    return ActionResult(
                        action="create_issue",
                        system="github",
                        success=True,
                        output={"issue_number": issue.number, "url": issue.html_url, "already_done": "created"},
                    )
        except Exception:
            pass  # Lookup failed — proceed to create

        issue = repo_obj.create_issue(title=title, body=body)
        return ActionResult(
            action="create_issue",
            system="github",
            success=True,
            output={"issue_number": issue.number, "url": issue.html_url, "already_done": False},
        )
    except Exception as e:
        return ActionResult(
            action="create_issue",
            system="github",
            success=False,
            output={"error": str(e)},
        )
```

**Verify:** `pytest tests/test_github.py::TestCreateIssueIdempotency tests/test_github.py::TestCreateIssue -v`
**Commit:** `"feat: make create_issue idempotent"`

---

### Cycle 4: `delete_branch` idempotency

**Goal:** `delete_branch` returns success when branch is already gone.

**Test:**

```python
from github import UnknownObjectException

class TestDeleteBranchIdempotency:
    def test_delete_branch_success_when_already_gone(self, connector):
        """Retry safety: if branch already deleted, return success."""
        mock_repo = MagicMock()
        mock_repo.get_git_ref.side_effect = UnknownObjectException(404, {}, {})
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.delete_branch(repo="owner/repo", branch="agent/old")

        assert result.success is True
        assert result.output["branch"] == "agent/old"
        assert result.output["already_done"] == "deleted"
```

**Implementation — add import + replace `delete_branch` in `enact/connectors/github.py:193-227`:**

Add import at top:
```python
from github import Github, UnknownObjectException
```

```python
def delete_branch(self, repo: str, branch: str) -> ActionResult:
    self._check_allowed("delete_branch")
    try:
        repo_obj = self._get_repo(repo)
        try:
            ref = repo_obj.get_git_ref(f"heads/{branch}")
        except UnknownObjectException:
            return ActionResult(
                action="delete_branch",
                system="github",
                success=True,
                output={"branch": branch, "already_done": "deleted"},
            )
        ref.delete()
        return ActionResult(
            action="delete_branch",
            system="github",
            success=True,
            output={"branch": branch, "already_done": False},
        )
    except Exception as e:
        return ActionResult(
            action="delete_branch",
            system="github",
            success=False,
            output={"error": str(e)},
        )
```

**Verify:** `pytest tests/test_github.py::TestDeleteBranchIdempotency tests/test_github.py::TestDeleteBranch -v`
**Commit:** `"feat: make delete_branch idempotent"`

---

### Cycle 5: `merge_pr` idempotency

**Goal:** `merge_pr` returns success when PR is already merged.

**Test:**

```python
class TestMergePRIdempotency:
    def test_merge_pr_success_when_already_merged(self, connector):
        """Retry safety: if PR already merged, return success."""
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.merged = True
        mock_pr.merge_commit_sha = "deadbeef"
        mock_repo.get_pull.return_value = mock_pr
        connector._get_repo = MagicMock(return_value=mock_repo)

        result = connector.merge_pr(repo="owner/repo", pr_number=42)

        assert result.success is True
        assert result.output["merged"] is True
        assert result.output["sha"] == "deadbeef"
        assert result.output["already_done"] == "merged"
        mock_pr.merge.assert_not_called()
```

**Implementation — replace `merge_pr` in `enact/connectors/github.py:229-259`:**

```python
def merge_pr(self, repo: str, pr_number: int) -> ActionResult:
    self._check_allowed("merge_pr")
    try:
        repo_obj = self._get_repo(repo)
        pr = repo_obj.get_pull(pr_number)
        if pr.merged:
            return ActionResult(
                action="merge_pr",
                system="github",
                success=True,
                output={"merged": True, "sha": pr.merge_commit_sha, "already_done": "merged"},
            )
        result = pr.merge()
        return ActionResult(
            action="merge_pr",
            system="github",
            success=True,
            output={"merged": result.merged, "sha": result.sha, "already_done": False},
        )
    except Exception as e:
        return ActionResult(
            action="merge_pr",
            system="github",
            success=False,
            output={"error": str(e)},
        )
```

**Verify:** `pytest tests/test_github.py::TestMergePRIdempotency tests/test_github.py::TestMergePR -v`
**Commit:** `"feat: make merge_pr idempotent"`

---

### Cycle 6: Update existing tests + final verification

**Goal:** Update existing success tests to assert `already_done` contract. Verify full suite.

**Add to existing success tests:**

```python
# TestCreateBranch.test_create_branch_success
assert result.output["already_done"] is False

# TestCreatePR.test_create_pr_success
assert result.output["already_done"] is False

# TestCreateIssue.test_create_issue_success
assert result.output["already_done"] is False

# TestDeleteBranch.test_delete_branch_success
assert result.output["already_done"] is False

# TestMergePR.test_merge_pr_success
assert result.output["already_done"] is False
```

**Note:** `create_pr` and `create_issue` now call `get_pulls` / `get_issues` before creating. MagicMock auto-creates these as MagicMock objects which are truthy — may need to explicitly mock them to return empty lists. Fix if tests fail.

**Verify:** `pytest -v`
**Commit:** `"feat: complete GitHub connector idempotency (v0.2)"`

---

## B.6 SUCCESS CRITERIA

- [ ] All 5 methods have idempotency guards
- [ ] Every method outputs `already_done` — `False` for fresh, descriptive string for noop
- [ ] Each method has at least 1 idempotency-specific test
- [ ] All existing tests still pass
- [ ] `pytest -v` all green
- [ ] No new files, no new models — just smarter methods
