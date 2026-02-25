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
163 tests, all passing. Published to PyPI as `enact-sdk 0.1.0` (rollback not yet published — still on 0.1.0).

```
enact/
  models.py, policy.py, receipt.py, client.py
  rollback.py                   # NEW — execute_rollback_action() dispatch for GitHub + Postgres
  connectors/github.py          # rollback_data populated; close_pr, close_issue, create_branch_from_sha added
  connectors/postgres.py        # pre-SELECT in update_row/delete_row; rollback_data populated
  policies/git.py, crm.py, access.py, time.py
  workflows/agent_pr_workflow.py, db_safe_insert.py
CLAUDE.md, README.md, SPEC.md, PLAN-TEMPLATE.md
plans/2026-02-24-rollback.md
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
- **Rollback feature — SHIPPED** ✅
  - `enact/models.py`: `rollback_data: dict` field on `ActionResult`; `"PARTIAL"` added to `Receipt.decision` Literal
  - `enact/receipt.py`: `load_receipt(run_id, directory)` added
  - `enact/rollback.py`: NEW — `execute_rollback_action()` with `_rollback_github()` and `_rollback_postgres()` dispatch
  - `enact/client.py`: `rollback_enabled=False` param + `rollback(run_id)` premium method
  - `enact/connectors/github.py`: `rollback_data` in all 5 mutating methods; new rollback-only actions: `close_pr`, `close_issue`, `create_branch_from_sha`
  - `enact/connectors/postgres.py`: pre-SELECT in `update_row` and `delete_row`; `rollback_data` in all 3 mutating methods
  - 40 new tests (123 → 163)

### Next Steps (priority order)
1. **Bump PyPI to 0.2.0** — rollback is a significant feature. Bump `pyproject.toml`, build, upload.
2. **`HubSpotConnector`** — `create_contact`, `update_deal`, `create_task`, `get_contact`. Use HubSpot free sandbox. Use Appendix in `plans/2026-02-24-rollback.md` for rollback checklist.
3. **Demo agent** — end-to-end script: triage issue → create branch → open PR. Good for README video.
4. **Email connector** — SendGrid. High idempotency value.

### Files to Reference
- `SPEC.md` — full build plan with ✅/⏭️ status markers + strategic thesis
- `README.md` — install, quickstart, connector/policy reference
- `CLAUDE.md` — conventions, design philosophy, git workflow
- `PLAN-TEMPLATE.md` — how to write implementation plans
- `examples/quickstart.py` — runnable PASS + BLOCK demo
- `landing_page.html` — marketing page (open in browser to preview)
</content>
</invoke>