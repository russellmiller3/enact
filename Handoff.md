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

**Date:** 2026-02-23
**Project:** Enact — action firewall for AI agents (`pip install enact-sdk`)

### Git State
- Branch: `master`
- Remote: `origin` → https://github.com/russellmiller3/enact (up to date)
- `backup` remote → D:/backup/enact — drive does not exist on this machine, ignore
- PyPI name: `enact-sdk` (plain `enact` was taken — different project, no traction)
- License: ELv2 + no-resale clause (no managed service, no selling the software itself)

### What Exists (fully built + tested)
96 tests, all passing. `dist/` contains built wheel + sdist ready to upload.

```
enact/
  models.py, policy.py, receipt.py, client.py
  connectors/github.py
  policies/git.py, crm.py, access.py, time.py
  workflows/agent_pr_workflow.py, db_safe_insert.py
LICENSE, README.md, SPEC.md, landing_page.html, pyproject.toml
```

### PyPI — LIVE ✅
`enact-sdk 0.1.0` published at https://pypi.org/project/enact-sdk/0.1.0/
Credentials in `~/.pypirc` (project-scoped token, `enact-sdk` only).

### Releasing a new version
1. Bump `version` in `pyproject.toml`
2. `python -m build`
3. `python -m twine upload dist/*`
Credentials read from `~/.pypirc` automatically — no token needed in the command.

### Next Steps (priority order)
1. **`PostgresConnector`** — `db_safe_insert` mocked; real connector needs psycopg2 + `select_rows()`, `insert_row()`, `delete_row()`. Works with Supabase/Neon/RDS.
2. **`HubSpotConnector`** — `no_duplicate_contacts` already wired; just needs the connector class. Use HubSpot free sandbox.
3. **Demo agent** — end-to-end script: triage issue → create branch → open PR. Good for README video / landing page.

### Files to Reference
- `SPEC.md` — full build plan with ✅/⏭️/🔜 status markers
- `README.md` — install, quickstart, connector/policy reference
- `examples/quickstart.py` — runnable PASS + BLOCK demo
</content>
</invoke>