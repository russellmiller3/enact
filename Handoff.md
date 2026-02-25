# Handoff.md

---

## How to Use This File

**This file is for Claude, maintained by Claude.**

At the end of every session, update the Handoff section below to reflect current state.
Keep it tight — the goal is to get the next Claude session oriented in under 60 seconds.

**What to include:**
- Current git state (branch, last commit, remotes)
- What was just completed this session
- Exact next step (be specific — file name, function name, what it should do)
- Any blockers, decisions pending, or things to watch out for
- Links/paths to key files

**What to cut:**
- History that's already done and not relevant to next steps
- Anything already captured in SPEC.md
- Long explanations — just the facts

**When to update:** Before ending any session where code was written or decisions were made.

---

## Current Handoff

**Date:** 2026-02-24
**Project:** Enact — action firewall for AI agents (`pip install enact-sdk`)

### Git State
- Branch: `master`
- Remote: `origin` → https://github.com/russellmiller3/enact (pushed 2026-02-24)
- `backup` remote → D:/backup/enact — user says D: drive is back, but bash still can't see it. Try remounting or check Disk Management. When it works: `git push backup master`
- PyPI name: `enact-sdk` (plain `enact` was taken — different project, no traction)
- License: ELv2 + no-resale clause (no managed service, no selling the software itself)

### What Exists (fully built + tested)
272 tests, all passing. Published to PyPI as `enact-sdk 0.1.0` (everything since rollback not yet published — bump to 0.2.0 is next).

```
enact/
  models.py, policy.py, receipt.py, client.py
  rollback.py                   # execute_rollback_action() dispatch for GitHub + Postgres + Filesystem
  connectors/github.py          # rollback_data populated; close_pr, close_issue, create_branch_from_sha added
  connectors/postgres.py        # pre-SELECT in update_row/delete_row; rollback_data populated
  connectors/filesystem.py      # NEW — read_file, write_file, delete_file, list_dir; base_dir path confinement
  policies/git.py               # no_push_to_main, max_files_per_commit, require_branch_prefix, no_delete_branch, no_merge_to_main
  policies/db.py                # no_delete_row, no_delete_without_where, no_update_without_where, protect_tables
  policies/filesystem.py        # NEW — no_delete_file, restrict_paths, block_extensions
  policies/crm.py, access.py, time.py
  workflows/agent_pr_workflow.py, db_safe_insert.py
CLAUDE.md, README.md, SPEC.md, PLAN-TEMPLATE.md
plans/2026-02-24-rollback.md
plans/2026-02-25-filesystem-connector.md
plans/guides/RED-TEAM-MODE-GUIDE.md
LICENSE, landing_page.html, pyproject.toml
```

### Conventions Established
- **`already_done` flag**: Every mutating connector action includes `output["already_done"]` — `False` for fresh actions, descriptive string (`"created"`, `"deleted"`, `"merged"`) for noops. All future connectors must follow this. Documented in `CLAUDE.md` and `github.py` docstring.
- **`rollback_data` field**: Every mutating `ActionResult` includes `rollback_data` dict with pre-action state needed to reverse the action. See `plans/2026-02-24-rollback.md` Appendix for the checklist when adding rollback to a new connector.
- **Plan template**: `PLAN-TEMPLATE.md` — three templates (A: Full TDD, B: Small Plan, C: Refactoring). Plans go in `plans/`.

### PyPI — LIVE ✅
`enact-sdk 0.1.0` published at https://pypi.org/project/enact-sdk/0.1.0/
Credentials in `~/.pypirc` (project-scoped token, `enact-sdk` only).

### Releasing a new version
1. Bump `version` in `pyproject.toml`
2. `python -m build`
3. `python -m twine upload dist/*`
Credentials read from `~/.pypirc` automatically — no token needed in the command.

### What Was Done This Session
- **`FilesystemConnector`** ✅ (`enact/connectors/filesystem.py` — new file)
  - `read_file`, `write_file`, `delete_file`, `list_dir`
  - `base_dir` path confinement — traversal blocked at connector level
  - `already_done` + `rollback_data` on all mutating actions
  - 29 tests in `tests/test_filesystem.py`
- **Filesystem policies** ✅ (`enact/policies/filesystem.py` — new file)
  - `no_delete_file` — sentinel, unconditional
  - `restrict_paths(list)` — factory; blocks if path not within any allowed dir (traversal-safe)
  - `block_extensions(list)` — factory; case-insensitive, handles dotfiles (.env)
  - 20 tests in `tests/test_filesystem_policies.py`
- **Filesystem rollback** ✅ (`enact/rollback.py` updated)
  - `write_file` rollback: restore previous content, or delete if file was new
  - `delete_file` rollback: recreate file with stored content
  - `read_file`, `list_dir`: read-only, skipped
  - 5 tests in `tests/test_rollback.py::TestRollbackFilesystem`
- **`no_merge_to_main`** added to `enact/policies/git.py` ✅ — reads `payload["base"]`; 8 tests
- **Plan written**: `plans/2026-02-25-filesystem-connector.md` (Template A)
- Total: 272 tests (210 → 272)

### What Was Done This Session (landing page)
- **`landing_page.html` updated** ✅ — source of truth for shipped features:
  - Step 2: "HubSpot, Salesforce, Postgres" → "GitHub, Postgres, Filesystem"
  - Quickstart code block: replaced HubSpot example with real shipped API (GitHubConnector, PostgresConnector, FilesystemConnector + no_push_to_main, no_merge_to_main, no_delete_without_where, no_delete_file, restrict_paths)
  - LangChain wrapper: `new_lead_workflow` → `agent_pr_workflow`
  - Roadmap badge: `v0.2+` → `v0.3+`, heading: "What's coming next" → "Coming in v0.3"
  - Rollback capability card: marked `badge-live`, green border, icon color — no longer amber/coming-soon
- **PyPI 0.2.0 published** ✅ — `enact-sdk 0.2.0` live at https://pypi.org/project/enact-sdk/

### Next Steps (priority order)
1. **ABAC + sensitive-read policies** (Template B) — see design notes below. ~2-3 hours.
2. **`HubSpotConnector`** — `create_contact`, `update_deal`, `create_task`, `get_contact`. Use HubSpot free sandbox.
3. **Demo evidence + terminal GIF** — plan at `docs/plans/2026-02-24-demo-evidence-and-gif.md`.
4. **AWS connector** — EC2 + S3 (v0.3 — defer until landing page + GIF are done).

### NEXT TASK: ABAC + Sensitive-Read Policies (Template B)

**The problem:** Agents can READ anything — `read_file("/etc/passwd")`, `select_rows("credit_cards")` — no policy gate exists for reads. We also have no Attribute-Based Access Control: policies can't check WHO the actor is (role, clearance, department) against WHAT they're accessing.

**The fix — two parts:**

**Part 1: Add `actor_attributes` to `WorkflowContext`** (`enact/models.py`)
```python
class WorkflowContext(BaseModel):
    workflow: str
    actor_email: str
    payload: dict = {}
    actor_attributes: dict = {}  # NEW — role, clearance_level, dept, etc.
    systems: dict = {}
```
Pass it through `EnactClient.run()` as a new kwarg: `actor_attributes={"role": "engineer", "clearance_level": 2}`.

**Part 2: New policies in `enact/policies/access.py`**
- `no_read_sensitive_tables(tables: list[str])` — factory; blocks `select_rows` when `payload["table"]` is in blocked set
- `no_read_sensitive_paths(paths: list[str])` — factory; blocks `read_file` when `payload["path"]` starts with any sensitive prefix
- `require_clearance_for_path(paths: list[str], min_clearance: int)` — ABAC; blocks if `actor_attributes["clearance_level"] < min_clearance` for sensitive paths
- `require_actor_role(*allowed_roles)` — ABAC factory; blocks if `actor_attributes["role"]` not in allowed set

**Reference:** `C:\Users\user\Desktop\programming\visa\backend\config\policies.py` — Russell's existing ABAC patterns (check_role_authorization, check_clearance_level, check_pii_restriction etc.)

**Plan template:** Template B (small feature, ~2 files, ~100 lines + tests)

### Files to Reference
- `SPEC.md` — full build plan with ✅/⏭️ status markers + strategic thesis
- `README.md` — install, quickstart, connector/policy reference
- `CLAUDE.md` — conventions, design philosophy, git workflow
- `PLAN-TEMPLATE.md` — how to write implementation plans
- `examples/demo.py` — 3-act demo: BLOCK + PASS + ROLLBACK (no credentials)
- `examples/quickstart.py` — minimal PASS + BLOCK demo
- `enact/policies/access.py` — existing ABAC-adjacent policies (contractor_cannot_write_pii, require_actor_role)
</content>
</invoke>