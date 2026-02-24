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
96 tests, all passing. Published to PyPI as `enact-sdk 0.1.0`.

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
1. **Saga pattern** — if step 1 of a workflow succeeds and step 2 fails, a retry should skip step 1.
   - Each step needs to be idempotent (e.g. "create branch if not exists" not "create branch")
   - **Open question: where to store per-step state?**
     - Can't be in-memory — lost on crash, defeats the point
     - Can't be in the receipt — receipt is written at the *end* of a run, not during
     - Options: (a) saga log file in `receipts/` keyed by `idempotency_key`, written step-by-step,
       deleted on clean completion; (b) caller passes in a state store; (c) each connector action
       checks its own side-effect before executing (e.g. GitHub: does branch exist? skip)
     - Option (c) is the lightest — no new infrastructure, just smarter connector methods
   - Caller supplies an optional `idempotency_key` on `enact.run()` — gets signed into receipt
   - Start in `enact/workflows/agent_pr_workflow.py` as the concrete test case

2. **`PostgresConnector`** — `db_safe_insert` mocked; real connector needs psycopg2 + `select_rows()`, `insert_row()`, `delete_row()`. Works with Supabase/Neon/RDS.
3. **`HubSpotConnector`** — `no_duplicate_contacts` already wired; just needs the connector class. Use HubSpot free sandbox.
4. **Demo agent** — end-to-end script: triage issue → create branch → open PR. Good for README video / landing page.

### Files to Reference
- `SPEC.md` — full build plan with ✅/⏭️/🔜 status markers
- `README.md` — install, quickstart, connector/policy reference
- `examples/quickstart.py` — runnable PASS + BLOCK demo
</content>
</invoke>