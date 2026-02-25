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

### Next Steps (priority order)
1. **Bump PyPI to 0.2.0** — `pyproject.toml` already at 0.2.0. `python -m build && python -m twine upload dist/*`
2. **Decide on landing_page_v2.html** — review in browser, swap it in as `landing_page.html` when satisfied.
3. **Demo evidence + terminal GIF** — plan at `docs/plans/2026-02-24-demo-evidence-and-gif.md`.
4. **`HubSpotConnector`** — `create_contact`, `update_deal`, `create_task`, `get_contact`. Use HubSpot free sandbox.
5. **AWS connector** — EC2 + S3 (v0.3 — defer until landing page + GIF are done).

### Files to Reference
- `docs/plans/2026-02-24-demo-evidence-and-gif.md` — NEXT TASK: demo evidence + GIF plan
- `SPEC.md` — full build plan with ✅/⏭️ status markers + strategic thesis
- `README.md` — install, quickstart, connector/policy reference
- `CLAUDE.md` — conventions, design philosophy, git workflow
- `PLAN-TEMPLATE.md` — how to write implementation plans
- `examples/demo.py` — 3-act demo: BLOCK + PASS + ROLLBACK (no credentials)
- `examples/quickstart.py` — minimal PASS + BLOCK demo
- `landing_page_v2.html` — updated marketing page (open in browser to preview)
</content>
</invoke>