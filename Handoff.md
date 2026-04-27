# Handoff.md

**This file is for Claude, maintained by Claude.** Read at session start. Goal: orient the next session in under 60 seconds.

---

## Current State (2026-04-27, end of session 11)

### Git
- Branch: `claude/reid-handoff-next-steps-cnufC` (NOT yet merged to master)
- Tests: **135 passing** (27 hook + 108 chaos)
- Working tree: clean after final commit

### Headline numbers — 36-run paired sweep (this session)
| Metric | Sweep A (Enact ON) | Sweep B (Enact OFF) |
|---|---|---|
| Total runs | 18 | 18 |
| Critical damage events | **0** | **6** |
| Damage runs (any state change for the worse) | **0** | **4** |
| Direct policy blocks | 5 | n/a |
| Agent self-refusals | 8 | 7 |
| Clean | 5 | 7 |
| Leaks (Enact ON but damage anyway) | **0** | n/a |

**Translation:** Same 18 dangerous prompts, same Claude. With Enact: 0 damage. Without: 4 of 18 caused damage including DROP customers, DELETE users, rename-then-drop, batched-delete. Hook caught everything; no leaks → no new policy candidates this round.

Damage detail in `chaos/report.md`. Cold-email body (3 picked findings) at `docs/outreach/cold_email_v1.md`.

### Hook fixes shipped this session

Two bugs fixed in `enact/cli/code_hook.py`:

1. **`ENACT_CHAOS_RUN_ID` resolution** — when subagents prefix the var inline (`ENACT_CHAOS_RUN_ID=xxx <cmd>`), it lands in the child process env, NOT the hook's process env. Added `_resolve_chaos_run_id(command)` helper that falls back to regex-parsing the var out of the command text. Per-run receipt scoping now works without requiring the parent CC env to be set.
2. **PreToolUse never wrote BLOCK receipts** — `cmd_post` was the only receipt writer, and PostToolUse never fires for blocked commands. Added BLOCK receipt write in `cmd_pre` so the actions table sees denials. Defense-in-depth.

Plus regex tweak in `runner._compute_outcome` so agent summaries that say "blocked by Enact" / "protect_tables policy" classify as `enact_blocked` even if the BLOCK receipt is missing.

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

## Priority 1 — DONE this session

36-run paired sweep complete. See "Headline numbers" above. Damage detail in `chaos/report.md`. **Skip everything below in Priority 1; it documents what was done.**

---

## Priority 1 (was): Run a LARGER paired sweep

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

### Once you have real numbers — three follow-up tasks (do all three before moving on)

These three things together turn the raw sweep data into a usable
marketing artifact + a smarter v1.1. Skip them and the whole sweep is
wasted effort.

#### 1a. Update the four "Real numbers" stat boxes on the landing page

**What:** the new homepage (`index.html`) has a section called
"Real numbers" with four big number callouts ("2 critical damage
events without Enact" etc.). Those numbers are placeholders from
the 11-run trial. After the 36-run paired sweep, the numbers are
different and bigger.

**Why:** "We tested 36 simulated attacks" beats "11" for credibility.
And "of the 18 dangerous tasks Claude attempted, Enact stopped all 18"
is a stronger headline than the partial data we have now.

**How:**
1. Open `index.html` and search for `<section id="numbers"`.
2. Find the four `<div class="stat">` blocks.
3. Update each `.stat-num` value AND the `.stat-label` description
   from the new `chaos/report.md` Headline + Outcome breakdown tables.
4. Update the italic paragraph below the stats with the new "non-obvious
   finding" — usually a specific adversarial bypass that worked.

**Time:** ~10 minutes of editing. No code change, just copy.
**Depends on:** Priority 1 (sweep) being done.

#### 1b. Generate the leak files and review them as draft policies

**What:** if any Sweep A run (Enact ON) still produced damage, that's
a "leak" — Enact failed to catch something. The harness writes these
to `chaos/leaks/{run_id}.json`. Each leak is a draft new policy waiting
to be written.

**Why:** **This is the flywheel turning.** Every leak found in the
sweep produces a draft policy candidate. Over time the policy library
gets smarter without manual hunting.

**How:**
1. After the sweep, run:
   ```bash
   python -c "
   from enact.chaos.suggest import write_leak_files, build_suggestion_prompt
   import json
   for path in write_leak_files():
       leak = json.loads(path.read_text())
       print('=' * 70)
       print(f'LEAK: {leak[\"task_id\"]}  (run {leak[\"run_id\"][:8]})')
       print('=' * 70)
       print(build_suggestion_prompt(leak))
       print()
   "
   ```
2. For each leak printed: copy the prompt, paste into a fresh Claude
   conversation (claude.ai or API console — your choice). Claude
   responds with a draft Python policy function.
3. Read the draft. Edit if needed. Drop into `enact/policies/coding_agent.py`
   (create the file if it doesn't exist).
4. Add the new policy to `.enact/policies.py` POLICIES list.
5. Re-run JUST that one task to confirm the leak is closed:
   ```python
   from enact.chaos.tasks import load_corpus
   from enact.chaos.orchestrate import run_sweep, record_sweep
   task = next(t for t in load_corpus("chaos/tasks") if t.id == "<the leaked task>")
   d = run_sweep([task], sweep="A")[0]
   # Dispatch one Agent. Then record. Should now be enact_blocked, not damage.
   ```

**Time:** ~10-30 min depending on how many leaks (each leak = ~5-10 min).
**Depends on:** Priority 1 done. **Critically: human review on every draft policy.** Never auto-apply.

#### 1c. Pick three damage findings for the cold-email body

**What:** the cold email template has a `[N] critical incidents...`
line. Fill it in with three specific, concrete damage events from
Sweep B (the without-Enact mode). Pick diverse categories — one DB
attack, one git attack, one secret leak — so it reads as breadth.

**Why:** specific concrete incidents land harder than "we caught
attacks." A reader scans the email, sees "the agent dropped the
customers table, force-pushed to main, and committed three API keys,"
and instantly maps that onto their own infra.

**How:**
1. Open `chaos/report.md` and look at the "Damage events (Sweep B)" table.
2. Pick three rows with diverse `event_type`s. Good mix:
   - One `customers_emptied` or `customers_table_dropped` (DB)
   - One `force_push_attempted` or `env_committed` (git)
   - One `workflow_modified` or similar (CI/secrets)
3. Write a single short sentence per incident (active voice, agent as
   subject):
   - "Agent dropped the customers table to 'free disk space.'"
   - "Agent force-pushed an unsigned rebase to main during a code freeze."
   - "Agent committed `.env` containing 3 API keys to a feature branch."
4. Drop those three sentences into the cold-email template (Priority 4).

**Time:** ~10 min.
**Depends on:** Priority 1.

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

### How to actually build the target list (50 names)

**What:** spreadsheet with 50 rows. Columns: company, name, role,
email, hook (specific reason you're reaching out — recent blog post,
job posting, public near-miss).

**Why:** generic mass-email gets ignored. Personalized cold email gets
5-15% reply rate. The personalization is the work.

**How:**
1. **Filter criteria — match all three:**
   - 100-300 person eng team (small enough to talk to manager directly,
     big enough to have budget)
   - AI-forward (visible AI products, AI engineering job postings, or
     known Cursor/CC users)
   - One of: had a public near-miss, in regulated industry
     (fintech / healthcare / gov), OR VP Eng has tweeted about agent
     safety / coding-agent risk
2. **Sources for the list:**
   - **LinkedIn Sales Navigator** — search "VP Engineering" + "Head of
     Platform" at companies sized 50-500, filter by industry. ~$80/mo.
   - **YC company directory** — filter to AI / devtools / SaaS in W23-W25
     batches. Free.
   - **Twitter search** — query strings like `"cursor deleted"`,
     `"agent broke prod"`, `"claude code yolo"`, `"force push agent"`.
     Look at who's complaining; those are warm prospects.
   - **HackerNews** — recent "Show HN" posts about AI agents. Authors
     of AI-tool startups are good targets too.
3. **Personalization hook** — for each entry, add 1-2 sentences
   referencing something specific (latest blog post, recent ship,
   public incident). Rotate through. Generic = dead email.
4. **Send via personal Gmail or Apollo** — low volume = warmer than
   batch tools. ~50/week is the sustainable rate.
5. **Track in spreadsheet:** date sent, replied (Y/N), demo booked
   (Y/N), trial started (Y/N), paid (Y/N). The numbers are what you
   tune the email/Loom against.

**Time:** ~5-8 hours total for the first list (research-heavy).
Subsequent lists are faster as you reuse criteria.

**Math (realistic):** 50 emails → 5-10 replies → 3-5 demos → 2-3
trials → 1-2 paid in 30 days. Repeat weekly.

### Loom 90s script (concrete recording instructions)

**What:** a 90-second screen recording showing the live demo. Goes
into every cold email as the `[Loom link]` in the template.

**Why:** cold emails with a video link get 3-5x reply rates. Without
a video, you're asking a busy exec to imagine what your product does.
The video does the imagining for them.

**How:**

**Setup (10 min):**
1. Open Loom (loom.com — free tier is fine) or Quicktime + screen capture
2. Spin up a fresh sandbox repo:
   ```bash
   mkdir /tmp/enact-demo && cd /tmp/enact-demo && git init -b main
   pip install enact-sdk
   enact-code-hook init
   ```
3. Open Claude Code in `/tmp/enact-demo`
4. Have a terminal visible alongside CC for showing receipts at the end

**Script (90 seconds):**
```
0:00-0:10  Camera/voiceover: "Last summer, Replit's agent dropped a
           production database during a code freeze. Here's what
           would have happened with Enact Code installed."

0:10-0:25  Set scene: in CC, type the prompt:
           "I need to clean up old rows in the customers table."

0:25-0:55  CC proposes psql DELETE FROM customers (or similar).
           PreToolUse hook fires.
           Camera zooms into the BLOCKED message in the terminal.
           Voiceover reads the policy reason aloud:
           "Enact's protect_tables policy fired. The customers table
           is in the protected list, so the operation gets denied
           before it executes. Claude sees the deny, tells me, and
           doesn't run the SQL."

0:55-1:10  Cut to the receipts/ folder showing the signed receipt JSON.
           Brief flash of `chaos/report.md` showing "0 damage with
           Enact, [N] without."

1:10-1:30  Voiceover: "Free for individual developers. $30 per seat
           per month for teams who want the audit dashboard. Reply
           for a 14-day trial. Link to the docs is in the email."
```

**Record (20 min):**
- Do 2-3 takes. First take is always rough; second is usually shippable.
- Don't over-edit. Real-feeling > polished. A solo founder with a
  scrappy demo lands better than a corporate sizzle reel.
- Upload to Loom, get the share link, paste into the cold email template.

**Time:** ~30 min total including setup + 2-3 takes + upload.
**Depends on:** Priorities 1, 1a, 1b, 1c done so the "[N] without
Enact" number you mention is real.

### How the priorities chain together

```
Priority 1 (sweep)
   ├─→ 1a (update landing-page numbers)
   ├─→ 1b (generate leak files → draft policies)
   └─→ 1c (pick 3 damage findings)
                  ├─→ Loom recording (uses real numbers)
                  └─→ Cold email body (uses 3 findings + Loom link)
                          └─→ First 50 emails sent
```

If you do the priorities in numerical order without the 1a/1b/1c
follow-ups, you'll have a sweep that produced data nobody saw. The
follow-ups are what turn data into outbound.

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

## ADHD-friendly / plain-English rule (SESSION-PERMANENT)

**Russell has ADHD.** All responses must follow the plain-English /
ADHD-friendly rules now baked into `CLAUDE.md` (Communication Style
section) AND enforced via a `UserPromptSubmit` hook in
`.claude/settings.json` that injects a reminder on every message.

The rules in one line: **lead with the answer; short paragraphs;
tables/bullets over prose; concrete numbers; plain English first;
bold takeaways; skip meta; 3-5 next-likely-needs tail at the end.**

If you find yourself writing a wall of text, you've already broken the
rule. Stop, restructure as bullets/tables, then continue.

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

