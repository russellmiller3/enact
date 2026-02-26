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

**Date:** 2026-02-26
**Project:** Enact — action firewall for AI agents (`pip install enact-sdk`)

### Git State
- Branch: `master`
- Last commit: `e74bf20` — "docs: add migration section to landing page and README; bump to v0.3.1"
- Remote: `origin` → https://github.com/russellmiller3/enact (up to date)
- PyPI: `enact-sdk 0.3.1` live at https://pypi.org/project/enact-sdk/0.3.1/
- License: ELv2 + no-resale clause

### What Exists (fully built + tested)
321 tests, all passing. Published to PyPI as `enact-sdk 0.3.1`.

```
enact/
  models.py, policy.py, receipt.py, client.py
  rollback.py                   # execute_rollback_action() dispatch for GitHub + Postgres + Filesystem
  connectors/github.py          # rollback_data populated; close_pr, close_issue, create_branch_from_sha added
  connectors/postgres.py        # pre-SELECT in update_row/delete_row; rollback_data populated
  connectors/filesystem.py      # NEW — read_file, write_file, delete_file, list_dir; base_dir path confinement
  policies/git.py               # dont_push_to_main, max_files_per_commit, require_branch_prefix, dont_delete_branch, dont_merge_to_main
  policies/db.py                # dont_delete_row, dont_delete_without_where, dont_update_without_where, protect_tables
  policies/filesystem.py        # NEW — dont_delete_file, restrict_paths, block_extensions
  policies/crm.py, access.py, time.py
  workflows/agent_pr_workflow.py, db_safe_insert.py
CLAUDE.md, README.md, SPEC.md, PLAN-TEMPLATE.md
plans/2026-02-24-rollback.md
plans/2026-02-25-filesystem-connector.md
plans/guides/RED-TEAM-MODE-GUIDE.md
LICENSE, landing_page.html, pyproject.toml
```

### Conventions Established
- **`already_done` flag**: Every mutating connector action includes `output["already_done"]` — `False` for fresh actions, descriptive string for noops. All future connectors must follow this.
- **`rollback_data` field**: Every mutating `ActionResult` includes `rollback_data` dict with pre-action state. See `plans/done/2026-02-24-rollback.md` Appendix for the checklist.
- **Plan template**: `PLAN-TEMPLATE.md` — Template A (Full TDD), B (Small), C (Refactoring). Plans go in `plans/`.

### PyPI — LIVE ✅
`enact-sdk 0.3.1` published at https://pypi.org/project/enact-sdk/0.3.1/
Credentials in `~/.pypirc` (project-scoped token). To release: bump `version` in `pyproject.toml` → `python -m build` → `python -m twine upload dist/enact_sdk-X.Y.Z*`

### What Was Done This Session (2026-02-26)
- **Migration section added to `landing_page.html`** ✅
  - New `#migrate` section between Disasters and Quickstart
  - 3-step migration flow (Register systems → Move guard logic → Replace direct calls)
  - Side-by-side before/after code (raw SDK calls → `enact.run()`)
  - Reassurance row: any framework, agent logic unchanged, no infra changes
  - `Migrate` nav link added to header
- **Migration section added to `README.md`** ✅ — same before/after for GitHub/PyPI readers
- **`pyproject.toml`** bumped `0.3.0` → `0.3.1` (PyPI is immutable; docs-only changes still need a bump)
- **`enact-sdk 0.3.1` pushed to PyPI** ✅
- **321 tests, 0 failures** — all green before commit

### Previously Completed (all plans in `plans/done/`)
- ABAC policies (`require_user_role`, `require_clearance_for_path`, `contractor_cannot_write_pii`, etc.) ✅
- `block_ddl`, `code_freeze_active`, `user_email` rename ✅
- `FilesystemConnector` + filesystem policies + rollback ✅
- Rollback engine (`enact.rollback(run_id)`) ✅
- Idempotency (`already_done` convention) ✅

### Next Steps (priority order)
1. **`HubSpotConnector`** — `create_contact`, `update_deal`, `create_task`, `get_contact`. Use HubSpot free sandbox. (Template A)
2. **Demo evidence + terminal GIF** — plan at `docs/plans/done/2026-02-24-demo-evidence-and-gif.md`.
3. **AWS connector** — EC2 + S3 (defer until HubSpot + GIF done).
4. **Show HN post** — when demo GIF is ready. Lead with rollback story (Replit incident).

### Files to Reference
- `SPEC.md` — full build plan, strategic thesis, competitive analysis
- `README.md` — install, quickstart, connector/policy/rollback reference
- `CLAUDE.md` — conventions, design philosophy, git workflow
- `PLAN-TEMPLATE.md` — how to write implementation plans
- `examples/demo.py` — 3-act demo: BLOCK + PASS + ROLLBACK (no credentials)
- `examples/quickstart.py` — minimal PASS + BLOCK demo
</content>
</invoke>