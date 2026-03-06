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

**Date:** 2026-03-06 (late evening, session 2)
**Project:** Enact — action firewall for AI agents (`pip install enact-sdk`)

### Git State

- Branch: `master`
- Last commit: `9b244a3` feat(docs+landing): new landing page live + Mintlify docs scaffold + short README
- Remote: `origin` → https://github.com/russellmiller3/enact
- PyPI: `enact-sdk 0.5.1` — published
- **Uncommitted:** `demo.html`, `static/enact_demo.py`, `vercel.json`, `index.html`

### What Was Done This Session

Demo polish + landing page embed — all work complete:

1. **Removed redundant `print("reason: ...")` from scenarios 0, 1, 2** in `demo.html`. Run() trace already shows it inline.

2. **Rewrote Tab 4 (Rollback)** — full narrative: cleanup job at 2am, no policy protecting high-value accounts, "inactive" flag was bad data, $108k ARR deleted. Kicker: "If they'd had `dont_delete_high_value_customers`, this never would have run."

3. **Replaced asciinema player with live iframe demo** in `index.html`:
   - Removed `asciinema-player.css` + `asciinema-player.min.js` from head
   - Removed `#demo-player` CSS block
   - Added `?embed=1` support to `demo.html` — hides header+hero when embedded
   - Iframe: `src="/demo.html?embed=1"`, 680px tall, matches landing page border style
   - `/demo.html?embed=1` works locally (python http.server) AND on Vercel

### Next Steps

**Commit + deploy:**
```
git add demo.html static/enact_demo.py index.html vercel.json
git commit -m "feat(demo): live playground on landing page, polish scenarios, rollback narrative"
git push
```
Then verify at https://enact.cloud (iframe should show, Pyodide loads, all 4 tabs run).

**After deploy:**
- Smoke-test all 4 tabs embedded in landing page
- Consider a 5th scenario in `static/enact_demo.py`: add `dont_delete_high_value_customers` policy — shows proactive protection vs reactive rollback

### Technical Notes

**Payload mismatch (important):** Real `dont_delete_without_where` checks `payload["where"]` (a dict). Demo uses `payload["action"]` (SQL string) for readability. Don't swap in the real policy without fixing the payload format.

**Browser limits:** Pyodide loads 5-8s on first visit (downloads WASM runtime). Normal. The loading bar communicates this.

**COOP/COEP headers:** `vercel.json` has these set. Pyodide requires `SharedArrayBuffer` which requires these headers. Without them, Pyodide will fall back to a slower mode or fail.

### Key Files

- `demo.html` — the playground
- `static/enact_demo.py` — mock SDK (browser-safe, no cloud deps)
- `vercel.json` — static deploy config
- `index.html` — landing page (add "Try it live →" CTA here)

### What Exists (fully built + tested)

**SDK:**

```
enact/
  models.py, policy.py, receipt.py, client.py
  rollback.py, cloud_client.py, ui.py
  connectors/github.py, postgres.py, filesystem.py, slack.py
  policies/git.py, db.py, filesystem.py, crm.py, access.py, time.py, email.py, slack.py
  workflows/agent_pr_workflow.py, db_safe_insert.py, post_slack_message.py
```

**Cloud:** FastAPI backend — receipt storage, HITL gates, status badge, zero-knowledge encryption.

**Tests:** 356+ passing.

### Files to Reference

- `SPEC.md` — full build plan, strategic thesis, workflow roadmap
- `CLAUDE.md` — conventions, design philosophy, git workflow
- `examples/demo.py` — the 3-act terminal demo this browser demo mirrors
