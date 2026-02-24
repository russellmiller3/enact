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
- Remote: `origin` → https://github.com/russellmiller3/enact (up to date — last commit: landing page update)
- `backup` remote → D:/backup/enact — user says D: drive is back, but bash still can't see it. Try remounting or check Disk Management. When it works: `git push backup master`
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

### Landing Page — UPDATED ✅ (this session)
`landing_page.html` now includes:
- **MCP Gap section** — "tools vs rules" positioning, wraps any MCP server
- **Framework compat strip** — Claude, OpenAI, LangChain, CrewAI, AutoGen, MCP
- **Workflow library section** — Zapier-for-agents angle, live vs coming-soon workflows
- **Coming Soon capabilities grid** — human-in-loop, rollback, vertical packs, compliance export, anomaly detection, multi-agent arbitration (amber badges)
- **Updated OSS vs Cloud table** — new rows for coming-soon features
- **Updated pricing cards** — amber coming-soon line items in Pro + Enterprise
- **hello@enact.cloud** CTAs for early access (placeholder — set up that email when ready)

### Next Steps (priority order)
1. **Saga pattern** — if step 1 of a workflow succeeds and step 2 fails, a retry should skip step 1.
   - **Decision made: Option (c)** — connector methods check their own side-effect before executing
     (e.g. GitHub: does branch exist? return `already_existed=True`, don't fail)
   - No new infrastructure. Each connector method becomes idempotent.
   - Start in `enact/connectors/github.py` — add `create_branch_if_not_exists` pattern
   - Test case: `enact/workflows/agent_pr_workflow.py`

2. **`PostgresConnector`** — `db_safe_insert` mocked; real connector needs psycopg2 + `select_rows()`, `insert_row()`, `delete_row()`. Works with Supabase/Neon/RDS.
3. **`HubSpotConnector`** — `no_duplicate_contacts` already wired; just needs the connector class. Use HubSpot free sandbox.
4. **Demo agent** — end-to-end script: triage issue → create branch → open PR. Good for README video / landing page.
5. **Set up hello@enact.cloud** — landing page CTAs point there for early access signups.

### Files to Reference
- `SPEC.md` — full build plan with ✅/⏭️/🔜 status markers + strategic thesis
- `README.md` — install, quickstart, connector/policy reference
- `examples/quickstart.py` — runnable PASS + BLOCK demo
- `landing_page.html` — marketing page (open in browser to preview)
</content>
</invoke>