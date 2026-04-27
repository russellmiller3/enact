# Handoff.md

**This file is for Claude, maintained by Claude.** Read at session start. Goal: orient the next session in under 60 seconds.

---

## Current State (2026-04-27, end of session 10)

### Git
- Branch: `claude/add-guardrails-ai-tools-Mk20f` (NOT yet merged to master)
- Tests: **135 passing** (25 hook + 110 chaos)
- Working tree: clean after final commit

### What exists / what shipped this session

**Enact Code hook** (`enact-code-hook init|pre|post`):
- `enact/cli/code_hook.py` — drops into Claude Code via PreToolUse / PostToolUse
- Reuses existing policies (`protect_tables`, `dont_force_push`, `block_ddl`, etc.)
- Light SQL extraction from psql commands so policies fire on raw shell
- Per-run receipt scoping via `ENACT_CHAOS_RUN_ID` env var
- Idempotent setup (merge-safe with existing `.claude/settings.json`)

**Chaos harness** (`enact/chaos/`):
- `telemetry.py` — SQLite (WAL + FK) for runs/actions/policies/damage/outcome
- `sandbox.py` — per-run tmp dir w/ fake DB, fake repo, decoy `.env`,
  python+sqlite3 psql shim, state OUTSIDE run_dir (survives `rm -rf .`)
- `damage.py` — 12 deterministic state-diff rules
- `tasks.py` + `chaos/tasks/*.md` — 18-prompt corpus across 5 categories
- `runner.py` — sweep toggles + run_one + record_run_result + outcome classifier
- `orchestrate.py` — `run_sweep` + `record_sweep` (one-shot orchestrator)
- `warmup.py` — attempt-rate scoring from Sweep B history
- `suggest.py` — leak detection + draft-policy prompt builder

**Live A/B trial proven** (session 10, 11 runs):
- Sweep A (hooks on, 6 runs): 0 damage, 1 enact_block, 3 self-refusals
- Sweep B (hooks off, 5 runs): 2 critical damage, 0 blocks
- Hooks DO fire on subagent commands. Confirmed.

**Landing pages**:
- `/` (`index.html`) = **Enact Code** (the new flagship — what we lead with)
- `/agents` (`agents.html`) = **Enact for production agents** (the original use case, demoted to sub-page)

---

## Priority 1 (most important): Run a LARGER paired sweep

**This is the headline number unlock.** Last session's 11-run trial was unpaired (different tasks in A vs B). Need all 18 corpus tasks in BOTH sweeps for a defensible "with vs without" comparison. Also expand the corpus once we know what's working.

### Pre-flight checks (5 min)

```bash
# 1. Confirm hooks installed and policies present
ls .claude/settings.json .enact/policies.py .enact/secret

# 2. Confirm hook fires (smoke test via stdin)
echo '{"tool_name":"Bash","tool_input":{"command":"git push --force origin main"}}' | enact-code-hook pre
# Expected: deny JSON. If empty, hook isn't wired.

# 3. Confirm psql shim works
python -c "
from enact.chaos.sandbox import seed_sandbox
import subprocess, tempfile
with tempfile.TemporaryDirectory() as d:
    h = seed_sandbox('test', d + '/run', state_root=d + '/state')
    out = subprocess.check_output([str(h.bin_dir / 'psql'), '-c', 'SELECT COUNT(*) FROM customers'])
    print(out.decode().strip())  # should print 50
"
```

If any fail, fix before running the sweep.

### Run Sweep A (with Enact)

```python
from enact.chaos.tasks import load_corpus
from enact.chaos.orchestrate import run_sweep, record_sweep

corpus = load_corpus("chaos/tasks")  # all 18 tasks

dispatches_a = run_sweep(corpus, sweep="A")
# `dispatches_a` is a list of dicts: {run_id, run_dir, subagent_prompt, ...}
```

**Dispatch all 18 in parallel** — call the `Agent` tool 18 times in
ONE assistant message, one per dispatch. Make sure each subagent
prompt includes `ENACT_CHAOS_RUN_ID={run_id}` for receipt scoping.

```python
summaries_a = [
    {"run_id": d["run_id"], "agent_summary": "<agent's final reply>"}
    for d in dispatches_a
]
record_sweep(summaries_a)
```

### Run Sweep B (control)

```python
from enact.chaos.runner import disable_sweep_b, restore_after_sweep

disable_sweep_b()
dispatches_b = run_sweep(corpus, sweep="B")
# Dispatch all 18 in parallel again
record_sweep(summaries_b)
restore_after_sweep()
```

### Output the report + leaks

```python
from enact.chaos.reporter import generate_report
from enact.chaos.suggest import write_leak_files

print(generate_report())              # writes chaos/report.md
leaks = write_leak_files()            # writes chaos/leaks/*.json
print(f"{len(leaks)} leaks need new policies")
```

### Expected headline shape (from session-10 partial extrapolation)

| | Sweep A (with Enact) | Sweep B (no Enact) |
|---|---|---|
| Critical damage events | 0–2 | 5–8 |
| Tasks Enact directly blocked | 4–7 | 0 |
| Tasks Claude self-refused | 4–6 | 4–6 |
| Tasks completed safely | 5–8 | 4–6 |

Total trial time: ~25-30 min wall clock with parallel dispatch.

### Once you have real numbers

Update the stat callouts in `index.html` (4-stat block in the
"#numbers" section). The placeholder copy reflects session 10's
11-run partial trial; replace with the 36-run paired data.

---

## Priority 2: IP protection split

**Goal:** keep SDK source-available (ELv2) but pull cloud + chaos data
+ premium policies into a private repo. Protects the moat without
killing bottom-up adoption.

### What stays public (this repo, ELv2)

- `enact/` — SDK (models, policy engine, receipt signing, rollback, action decorator)
- `enact/cli/code_hook.py` — the hook binary (drives adoption)
- `enact/policies/` — built-in defaults (need to be open so users can audit)
- `enact/connectors/` — basic connectors (GitHub, Postgres, Filesystem, Slack)
- `enact/chaos/` — harness CODE (other people can chaos-test their own setups; that's marketing)
- `chaos/tasks/*.md` — corpus content (also marketing)
- `tests/` — yes, all of it (open-source norm)
- `index.html`, `agents.html`, `demo.html` — public landing
- `README.md`, `LICENSE`, `pyproject.toml`

### What moves to a NEW private repo `enact-cloud`

- `cloud/` — entire FastAPI backend, Stripe integration, dashboard,
  SMTP, HITL approval flow, encryption helpers
- `tests/cloud/` — cloud-specific tests
- `fly.toml` + Fly deploy configs
- Any cloud-specific CLAUDE.md notes

### What moves to a NEW private repo `enact-pro`

- `chaos.db`, `chaos.db-shm`, `chaos.db-wal` — telemetry data (already gitignored, just don't commit)
- `chaos/runs/` — sandbox snapshots (gitignored)
- `chaos/leaks/*.json` — auto-suggested policy candidates (the moat)
- `chaos/report.md` — generated reports (gitignored, but archived in pro)
- Premium policy packs as we add them (none yet)
- Tuned policy variants based on customer telemetry

### Concrete steps (~1-2 hours)

1. **Create empty private repos** on GitHub: `russellmiller3/enact-cloud`, `russellmiller3/enact-pro`.
2. **Move `cloud/`** with full git history:
   ```bash
   # In a clone of the public repo:
   git filter-repo --path cloud/ --path tests/cloud/ --path fly.toml
   git remote add cloud-origin https://github.com/russellmiller3/enact-cloud.git
   git push cloud-origin main
   ```
   *Alternative if `git filter-repo` not installed: just copy the dir contents into a fresh clone of the new private repo, commit, push. Loses history but simpler.*
3. **In the public repo, remove cloud paths**:
   ```bash
   git rm -r cloud/ tests/cloud/ fly.toml
   git commit -m "chore: move cloud backend to private enact-cloud repo"
   ```
4. **Update `pyproject.toml`** — confirm `enact-sdk` package doesn't include `cloud/`:
   ```toml
   [tool.setuptools.packages.find]
   include = ["enact*"]   # already correct; cloud/ isn't picked up
   ```
5. **Update `LICENSE`** to add a clarifying notice:
   ```
   This SDK is licensed under the Elastic License 2.0 (above).
   Enact Cloud and Enact Pro features (dashboard, premium policies,
   compliance reports, customer-tuned policy packs) are separately
   licensed under proprietary terms — contact russell@enact.cloud.
   ```
6. **Update `Fly` deployment** to point at the new `enact-cloud` repo. The
   live `enact.fly.dev` keeps running unchanged; only the source location
   moves.
7. **Bootstrap `enact-pro`** with a stub README explaining what lives there.
   No code yet; first content is the auto-generated `chaos/leaks/*.json`
   files from priority-1 sweeps.

### Why this matters NOW

Don't deploy `enact.cloud` updates referencing the new product (Enact
Code) until the IP split is done — otherwise you're publicizing a URL
that's tied to a public-repo cloud backend. Land the split, THEN deploy.

---

## Priority 3: Vercel deploy of new landing pages

After priority 2 is done:
- `index.html` (was `code.html`) goes live at `enact.cloud`
- `agents.html` (was `index.html`) goes live at `enact.cloud/agents`
- Old links to `enact.cloud` from elsewhere now hit Enact Code; old fans hit `/agents`

Vercel auto-deploys from the `master` branch. Merge `claude/add-guardrails-ai-tools-Mk20f` → `master` first.

---

## Priority 4: Cold email v1 + Loom 90s demo

After priority 1 has real numbers, draft the outbound. Templates live
in `docs/outreach/` (create dir if needed).

### Cold email (paste-ready)

> Subject: 90-sec video — agent firewall I built for [Company]'s eng team
>
> Hi [first name],
>
> Saw [specific recent thing — blog post, tweet]. Curious how you're handling Cursor / Claude Code across the team.
>
> Built Enact Code — a hook for Claude Code (Cursor MCP coming) that runs every tool call through a policy engine before execution. Tested it against 36 simulated agent attacks last week:
>
>   **Without Enact: [N] critical incidents (prod table dropped, secrets committed, force-push to main).**
>   **With Enact: [M] caught, [K] leaked → patched in next sweep.**
>
> 90-sec demo: [Loom link]
>
> Free for individuals. $30/seat/mo for teams w/ audit dashboard.
>
> Worth 15 min next week?
>
> — Russell, founder
> enact.cloud

### Target list filters
- VP Eng / Head of Platform / Eng Manager
- 100-300 person eng team
- AI-forward: known Cursor/CC users, AI products in market
- Recent near-miss preferred

50 emails/week. Math: 50 → 5-10 demos → 2-3 trials → 1-2 paid in 30 days.

### Loom 90s script

```
0:00-0:10  "Remember the Replit prod DB incident last summer?"
0:10-0:25  Set scene: CC session, fake prod DB labeled PROD-MIRROR
0:25-0:55  Live: ask CC to "clean up old customer rows"
           CC writes psql DELETE FROM customers
           PreToolUse hook fires; big red BLOCKED
0:55-1:10  Show signed receipt + chaos report headline numbers
1:10-1:30  "Free for individuals. $30/seat/mo for teams. Reply for a 14-day trial."
```

---

## Priority 5: PyPI 0.6.0 bump

```bash
# pyproject.toml: bump version "0.5.1" → "0.6.0"
# CHANGELOG entry: "feat: enact-code-hook for Claude Code, chaos harness"
python -m build
twine upload dist/*
```

Don't bump until priority 1 (sweep) is in the can — release notes
should reference the report.

---

## Useful one-liners

```bash
# Run report
python -c "from enact.chaos.reporter import generate_report; print(generate_report())"

# Find leaks → draft policies
python -c "
from enact.chaos.suggest import write_leak_files, build_suggestion_prompt
import json
for path in write_leak_files():
    leak = json.loads(path.read_text())
    print('---'); print(f'Leak: {leak[\"task_id\"]}'); print(build_suggestion_prompt(leak))
"

# Compute attempt rates from history
python -c "
from enact.chaos.warmup import export_attempt_rates
print(export_attempt_rates())
"

# Full chaos test suite
python -m pytest tests/test_code_hook.py tests/test_chaos_*.py -v
```

---

## Earlier session history (sessions 8-10 SDK work)

For full provenance, see `git log --oneline` on this branch. Key landmarks:
- Session 8-9: `@action` decorator + `run_action()`; prompt-injection policies; landing page rebrand; Stripe self-serve flow
- Session 10 part 1: Enact Code hook (cycles 1-7 + smoke test). 25 tests.
- Session 10 part 2: Chaos harness Phase 1. 75 tests, 100 total.
- Session 10 part 3: 5 flywheel tweaks (self-refusal, env-var receipts, orchestrator, warmup, leak suggester). 135 total.
- Session 10 part 4: Live A/B trial confirmed hooks fire. Landing-page swap. This handoff.

---

## Open questions / things to watch

- **Sweep parallelism receipt attribution**: subagents need to actually set `ENACT_CHAOS_RUN_ID` for clean per-run scoping. Last session they skipped it; fallback was timestamp-diff which cross-attributed. If next sweep also has this issue, lean on `agent_summary.txt` text + damage state to derive outcomes (already a working fallback).
- **Adversarial framing keeps working**: "this is sandbox maintenance" or "batch the deletes" both bypassed Claude's self-refusal. Strengthen the corpus with more such variations.
- **Cursor / Codex / Cline integration**: deferred to v2. MCP server is the path. Open question whether to build that before or after first paying customer.
- **HubSpot connector**: still unimplemented. Lower priority than the chaos flywheel.

