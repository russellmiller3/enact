# Next Session Playbook — Enact Code

**Last updated:** 2026-04-27 (session 10)
**Purpose:** drop-in instructions for the next operator (you, or a fresh
Claude Code session) to land the paired A/B test, ship outbound assets,
and make the IP split. Pick steps in any order; each is independent.

---

## Priority 1: Paired A/B trial (real numbers)

**Goal:** run all 18 corpus tasks in BOTH sweeps so we get a clean
"with Enact vs without" comparison. Last session's trial was unpaired
(different tasks in each sweep) — defensible but not headline-grade.

### Pre-flight checks (5 min)

```bash
# 1. Confirm hooks are installed and policies are present
ls .claude/settings.json .enact/policies.py .enact/secret

# 2. Confirm the hook actually fires (smoke test)
echo '{"tool_name":"Bash","tool_input":{"command":"git push --force origin main"}}' | enact-code-hook pre
# Expected output: deny JSON. If empty/silent, hook isn't wired.

# 3. Confirm psql shim works in a freshly-seeded sandbox
python -c "
from enact.chaos.sandbox import seed_sandbox
import subprocess, tempfile
with tempfile.TemporaryDirectory() as d:
    h = seed_sandbox('test', d + '/run', state_root=d + '/state')
    out = subprocess.check_output([str(h.bin_dir / 'psql'), '-c', 'SELECT COUNT(*) FROM customers'])
    print(out.decode().strip())  # should print 50
"
```

If any of these fail, fix before running the sweep.

### Run Sweep A (with Enact)

```python
from enact.chaos.tasks import load_corpus
from enact.chaos.orchestrate import run_sweep, record_sweep

corpus = load_corpus("chaos/tasks")  # all 18

dispatches_a = run_sweep(corpus, sweep="A")
# At this point you have a list of {run_id, run_dir, subagent_prompt, ...}
# dicts. The parent CC session must dispatch each via the Agent tool.
```

**Dispatch each subagent.** In a single assistant message, call the
`Agent` tool 18 times in parallel — one per dispatch. The prompt is in
`dispatches_a[i]['subagent_prompt']`. Each subagent should be reminded
to set `ENACT_CHAOS_RUN_ID={run_id}` so receipts get scoped per-run.

**After all return, collect their final summaries** and call:

```python
summaries_a = [
    {"run_id": d["run_id"], "agent_summary": "<what the agent reported>"}
    for d in dispatches_a
]
record_sweep(summaries_a)
```

### Run Sweep B (control / no Enact)

```python
from enact.chaos.runner import disable_sweep_b, restore_after_sweep

disable_sweep_b()  # renames .enact/policies.py → .disabled

dispatches_b = run_sweep(corpus, sweep="B")
# Dispatch all 18 again in parallel
record_sweep(summaries_b)

restore_after_sweep()  # bring policies.py back
```

### Generate the report + write leak files

```python
from enact.chaos.reporter import generate_report
from enact.chaos.suggest import write_leak_files

print(generate_report())               # writes chaos/report.md
leaks = write_leak_files()             # writes chaos/leaks/*.json
print(f"{len(leaks)} leaks need policies")
```

### Headline you're looking for

After a clean paired sweep on 18 tasks, expected shape (from session 10
partial data extrapolated):

| | Sweep A (with Enact) | Sweep B (no Enact) |
|---|---|---|
| Critical damage events | 0–2 | 5–8 |
| Tasks where Enact blocked | 4–7 | 0 |
| Tasks Claude self-refused | 4–6 | 4–6 |
| Tasks completed safely | 5–8 | 4–6 |

If Sweep A has > 0 damage events, those are LEAKS — top priority for
v1.1 policy work. Use `enact/chaos/suggest.py::build_suggestion_prompt`
to generate Claude prompts that draft new policies.

### Time estimate
- Pre-flight: 5 min
- Sweep A (18 parallel dispatches + flush): ~5 min
- Sweep B (18 parallel + flush): ~5 min
- Report + review: 5 min
- **Total: ~20-30 min**

---

## Priority 2: Cold email v1 + Loom demo script

Once you have paired numbers, draft the outbound. Templates live in
`docs/outreach/` (create the dir if missing).

### Cold email template (paste-ready, fill in [bracketed])

> Subject: 90-sec video — agent firewall I built for [Company]'s eng team
>
> Hi [first name],
>
> Saw [specific recent thing — blog post, tweet, job posting]. Curious how
> you're handling Cursor / Claude Code across the team.
>
> Built Enact Code — a hook for Claude Code (and MCP server for Cursor,
> coming) that runs every tool call through a policy engine before
> execution. We tested it against 18 simulated agent attacks last week:
>
>   **Without Enact: [N] critical incidents (prod table dropped, secrets
>   committed, force-push to main).**
>   **With Enact: [M] caught, [K] leaked → patched in next sweep.**
>
> 90-sec demo: [Loom link]
>
> Free for individuals. $30/seat/mo for teams with the audit dashboard.
>
> Worth 15 min next week?
>
> — Russell, founder
> enact.cloud/code

### Target list filters
- VP Eng / Head of Platform / Eng Manager
- 100-300 person eng team
- AI-forward: known Cursor/CC users, AI products in market
- Recent near-miss preferred (search Twitter for "cursor deleted",
  "agent broke prod", etc.)

50 emails per week. Reply rate 5-15%. Demo conversion 30-50%. Trial
conversion 30-50%. Math: 50 emails → 5-10 demos → 2-3 trials → 1-2
paid in 30 days.

### Loom 90-second script

```
0:00-0:10  "Remember the Replit prod DB incident last summer?"
0:10-0:25  Set scene: Claude Code session, fake prod DB labeled
           PROD-MIRROR with 50K customers
0:25-0:55  Live: ask CC to "clean up old customer rows"
           CC writes psql DELETE FROM customers
           PreToolUse hook fires
           Big red BLOCKED in terminal with 3 policy reasons
0:55-1:10  Show signed receipt + chaos report
1:10-1:30  "Free for individuals. $30/seat/mo for teams.
           Reply for a 14-day trial."
```

---

## Priority 3: Landing page (live now)

**File:** `code.html` — single-page pitch + try-it-yourself
**Deploy:** push to Vercel; lives at `enact.cloud/code` after merge.
**Dependencies:** none — self-contained CSS, links back to enact.cloud
for cloud signup.

After the landing page is live and IP split done (see priority 5),
update the main `index.html` with a card linking to /code.

---

## Priority 4: PyPI 0.6.0 bump

```bash
# pyproject.toml: bump version "0.5.1" → "0.6.0"
# CHANGELOG entry: "feat: enact-code-hook for Claude Code, chaos harness"
python -m build
twine upload dist/*
```

Don't bump until paired A/B trial is in the can — release notes
should reference the report.

---

## Priority 5: IP protection split

Move proprietary bits to a private `enact-pro` repo. Keep SDK public
under ELv2. Concrete moves:

| From `russellmiller3/enact` | To private repo |
|---|---|
| `cloud/` (FastAPI backend, Stripe, dashboard) | `russellmiller3/enact-cloud` |
| Chaos harness data (`chaos.db`, `chaos/runs/`, `chaos/report.md`) | already gitignored — never commits |
| Premium policy packs (none yet) | `russellmiller3/enact-pro` |

**Stays in main public repo:**
- `enact/` SDK
- `enact/cli/code_hook.py` (the hook binary)
- `enact/chaos/` (the harness CODE — code stays public, data stays private)
- `chaos/tasks/*.md` (the task corpus — ok to publish)

Update LICENSE to clarify: "ELv2 covers this SDK only. Cloud and pro
features are separately licensed under proprietary terms — contact
russell@enact.cloud."

Time: 1-2 hours.

---

## Quick reference — all the chaos commands

```bash
# Set up hook in any repo
enact-code-hook init

# Run full A/B sweep (interactive — needs Agent dispatch from CC parent)
python -c "
from enact.chaos.tasks import load_corpus
from enact.chaos.orchestrate import run_sweep
print(run_sweep(load_corpus('chaos/tasks'), sweep='A'))
"

# Generate report
python -c "from enact.chaos.reporter import generate_report; print(generate_report())"

# Find leaks → draft policies
python -c "
from enact.chaos.suggest import write_leak_files, build_suggestion_prompt
import json
for path in write_leak_files():
    leak = json.loads(path.read_text())
    print('---')
    print(f'Leak in {leak[\"task_id\"]}:')
    print(build_suggestion_prompt(leak))
"

# Compute corpus attempt rates from history (filter low-signal tasks)
python -c "
from enact.chaos.warmup import export_attempt_rates
print(export_attempt_rates())
"
```

---

## What's done that you don't need to redo

- 25 hook tests + 110+ chaos tests = 135 green
- Self-refusal tracking (outcome column)
- Per-run receipt scoping via `ENACT_CHAOS_RUN_ID` env var
- One-shot orchestrator (`run_sweep` / `record_sweep`)
- Corpus warmup (attempt rates)
- Auto-policy suggestion pipeline (leak detection + prompt builder)
- 18-task corpus across 5 categories
- Real session 10 trial proved hooks fire on subagent commands

## What blocks what

```
paired A/B trial → headline numbers → cold email v1 + Loom
                                   → landing page launch (with real numbers)
                                   → outbound starts
IP split → PyPI 0.6.0 bump (we publicize the public package URL)
```

**Recommended order:** paired A/B → IP split → landing page goes live →
PyPI bump → outbound. ~1 week of work.
