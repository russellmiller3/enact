# Plan 5: Enact Setup Skill

**Template:** A (Greenfield — new files, >200 lines across two artifacts)
**Date:** 2026-03-07
**Branch:** `feature/enact-setup-skill`

---

## A.1 What We're Building

A downloadable Claude Code skill that analyzes a user's agent codebase and wraps it
in Enact interactively — approval-gated at every step.

```
WITHOUT SKILL                      WITH SKILL
─────────────────────────────────  ───────────────────────────────────
User reads migration docs          /enact-setup
Figures out which policies apply   Skill scans repo, proposes policies
Copy-pastes EnactClient setup      Skill writes the code with approval
30–60 min work                     10 min guided walkthrough
```

**Two artifacts:**
1. `skills/enact-setup/SKILL.md` — the Claude Code skill (user installs globally)
2. `index.html` — new "Install the skill" section on landing page

**Install story (one command):**
```bash
mkdir -p ~/.claude/skills/enact-setup && \
  curl https://raw.githubusercontent.com/russellmiller3/enact/master/skills/enact-setup/SKILL.md \
  -o ~/.claude/skills/enact-setup/SKILL.md
```
Then in Claude Code: `/enact-setup`

**Key Decisions:**

| Decision | Rationale |
|----------|-----------|
| `context: fork` + `agent: general-purpose` | Runs as isolated subagent — full tool access (Glob, Grep, Read, Write, Edit, Bash), doesn't pollute user's session |
| `disable-model-invocation: true` | Explicit `/enact-setup` only — never auto-triggers. This skill rewrites code. |
| Raw GitHub URL for distribution | No server needed. Always current with master. Zero infra complexity. |
| Approval-gated code writing | Brand alignment — the Enact setup skill is itself "AI that asks before it acts." |
| `pip install enact-sdk` in skill | Lowers friction. Skill installs the dependency if missing. |

---

## A.2 Existing Code to Read Before Implementing

| File | Why |
|------|-----|
| `enact/client.py` | EnactClient constructor signature — skill must propose valid code |
| `enact/connectors/github.py` | GitHubConnector API surface |
| `enact/connectors/filesystem.py` | FilesystemConnector API surface |
| `enact/connectors/postgres.py` | PostgresConnector API surface |
| `enact/connectors/slack.py` | SlackConnector API surface |
| `enact/policies/__init__.py` | All exported policy names |
| `index.html` | Find insertion point for skill section (search for existing CTA sections) |

---

## A.3 Data Flow

```
User: /enact-setup [optional: path/to/agent.py]
         │
         ▼
Skill forks → general-purpose agent with full tool access
         │
    ┌────┴─────────────────────────────────────────┐
    │ Phase 1: ORIENT                               │
    │ Read README, entry points (main/agent/app.py) │
    │ Confirm understanding with user               │
    └────┬─────────────────────────────────────────┘
         │
    ┌────┴─────────────────────────────────────────┐
    │ Phase 2: SCAN                                 │
    │ Glob all .py (skip tests/, venv/)             │
    │ Grep for: requests.post/delete, os.remove,    │
    │   subprocess, cursor.execute, github, slack   │
    │ Note file + line for each hit                 │
    └────┬─────────────────────────────────────────┘
         │
    ┌────┴─────────────────────────────────────────┐
    │ Phase 3: MAP + EXPLAIN                        │
    │ Each pattern → Enact connector + policies     │
    │ Walk user through findings, one category      │
    │ Check understanding with a question each time │
    └────┬─────────────────────────────────────────┘
         │
    ┌────┴─────────────────────────────────────────┐
    │ Phase 4: PROPOSE                              │
    │ Show proposed enact_setup.py                  │
    │ Ask: "Should I write this + modify your files?│
    └────┬─────────────────────────────────────────┘
         │
      user: "yes"
         │
    ┌────┴─────────────────────────────────────────┐
    │ Phase 5: WRITE                                │
    │ git checkout -b enact/setup                   │
    │ pip install enact-sdk                         │
    │ Write enact_setup.py                          │
    │ Modify agent files (add import, wrap calls)   │
    │ Summary: files changed, next steps            │
    └──────────────────────────────────────────────┘
```

---

## A.4 Files to Create

### `skills/enact-setup/SKILL.md`

**Path:** `skills/enact-setup/SKILL.md`

```markdown
---
name: enact-setup
description: Analyze this repository's AI agent code and wrap it in Enact for policy enforcement, signed audit receipts, and one-command rollback. Scans the codebase, maps dangerous actions to Enact policies and connectors, and writes setup code with your approval at every step.
disable-model-invocation: true
argument-hint: [path to your main agent file, optional]
context: fork
agent: general-purpose
allowed-tools: Read, Glob, Grep, Write, Edit, Bash(git *), Bash(pip install enact-sdk)
---

# Enact Setup

You're helping the user add Enact to their AI agent codebase. Enact is an action firewall:
it intercepts dangerous actions before they execute, generates cryptographically-signed audit
receipts, and enables one-command rollback.

Your job: act like a knowledgeable colleague who's done this before. Explain what you're
seeing, why it matters, and check understanding before writing code. Never write code
without explicit user approval.

## Tone
- Blunt and direct. No "Great!" No corporate cheerleading.
- Explain WHY, not just HOW.
- When you see something risky, name it specifically.
- Check for understanding with a question before moving on.

---

## Step 1: Orient

If $ARGUMENTS is provided, start by reading that file. Otherwise:

1. Read `README.md` if it exists
2. Glob for entry points: `main.py`, `agent.py`, `app.py`, `run.py`, `bot.py`
3. Read each (first 100 lines) to understand what the agent does

Summarize: "Here's what I understand your agent does: [summary]. That right?"

Wait for confirmation before scanning.

---

## Step 2: Scan for Dangerous Patterns

Search all `.py` files. Skip: `tests/`, `venv/`, `.venv/`, `node_modules/`, `__pycache__/`.

If the repo has >500 `.py` files, limit scan to: top-level directory + any dir named
`agent/`, `agents/`, `src/`, `app/`.

**HTTP/API mutations** (may need custom connector or policy):
- `requests\.(post|put|delete|patch)`
- `httpx\.(post|put|delete|patch)`

**File system mutations** → FilesystemConnector:
- `os\.remove|os\.unlink|os\.rmdir|shutil\.rmtree|shutil\.move`
- `open\(.*['"](w|a|wb|ab)['"]`
- `Path.*\.(write_text|write_bytes|unlink|rmdir)`

**Shell/subprocess** → custom policy (allowlist specific commands):
- `subprocess\.(run|call|Popen|check_output)`
- `os\.system\(`

**Database mutations** → PostgresConnector:
- `cursor\.execute.*(INSERT|UPDATE|DELETE)`
- `\.commit\(\)`
- `psycopg2|asyncpg|sqlalchemy`

**GitHub** → GitHubConnector:
- `from github import|PyGitHub|github\.Github`
- `repo\.create_|\.create_git_ref|\.merge|\.delete`

**Slack** → SlackConnector:
- `from slack_sdk|import slack`
- `chat_postMessage|files_upload|conversations_kick`

For each match: record file, line number, and the call.

---

## Step 3: Map to Enact

For each dangerous pattern found, map it:

| Pattern | Enact suggestion |
|---------|-----------------|
| `requests.delete/post/put` | Custom policy: URL allowlist before firing |
| `os.remove` / `shutil.rmtree` | `FilesystemConnector` + `NoDeletePolicy` |
| `subprocess.run` | Custom policy: command allowlist |
| DB `INSERT`/`UPDATE`/`DELETE` | `PostgresConnector` + `ProtectTablesPolicy` |
| GitHub repo mutations | `GitHubConnector` + `DontPushToMainPolicy` |
| Slack messages | `SlackConnector` + `RequireHumanApprovalPolicy` |

**Built-in policies (real names — import from submodule):**
```
# Git  (from enact.policies.git)
dont_push_to_main                         # plain function
dont_merge_to_main                        # plain function
dont_delete_branch                        # sentinel — always blocks delete
max_files_per_commit(max_files=50)        # factory
require_branch_prefix(prefix="agent/")   # factory

# DB  (from enact.policies.db)
dont_delete_row                           # sentinel — always blocks
dont_delete_without_where                 # plain function
dont_update_without_where                 # plain function
block_ddl                                 # blocks DROP/TRUNCATE/ALTER/CREATE
protect_tables(["users", "payments"])     # factory

# Filesystem  (from enact.policies.filesystem)
dont_delete_file                          # sentinel — always blocks
restrict_paths(["/workspace"])            # factory — path confinement
block_extensions([".env", ".key"])        # factory

# Access  (from enact.policies.access)
contractor_cannot_write_pii               # plain function
require_actor_role(["admin"])             # factory
require_user_role("admin", "engineer")   # factory (reads user_attributes)

# Slack  (from enact.policies.slack)
require_channel_allowlist(["#ops"])       # factory

# Time  (from enact.policies.time)
within_maintenance_window(22, 6)          # factory — UTC hours

# Email  (from enact.policies.email)
no_mass_emails
no_repeat_emails
```

**Note on human approval:** There's no standalone "require human approval" policy.
Human-in-the-loop is handled via Enact Cloud's HITL feature — see https://docs.enact.cloud/concepts/hitl

---

## Step 4: Present Findings

Walk through findings one category at a time. Be specific about file + line.

Example:
> "In `agent.py` line 47, you're calling `requests.delete()` against your own API.
> That's the most dangerous call I found — if the agent hallucinates the endpoint,
> it could delete real data with no audit trail.
>
> I'd wrap this with a policy that: (1) checks the URL against an allowlist before
> firing, (2) generates a signed receipt of every delete, (3) enables rollback if you
> capture the resource state beforehand.
>
> Does that match how risky you think this call is?"

Check understanding after each category. Let the user push back.

---

## Step 5: Propose the Setup

Once all patterns are discussed, show the proposed `enact_setup.py`.
Tailor it to what was actually found — don't include connectors for patterns
that weren't in the repo.

Example:
```python
# enact_setup.py — generated by /enact-setup
import os
from enact import EnactClient
from enact.connectors.github import GitHubConnector
from enact.connectors.filesystem import FilesystemConnector
from enact.policies.git import dont_push_to_main, require_branch_prefix
from enact.policies.filesystem import dont_delete_file, restrict_paths

github = GitHubConnector(
    token=os.environ["GITHUB_TOKEN"],
    allowed_actions=["create_branch", "create_pr", "merge_pr"],
)
fs = FilesystemConnector(
    base_dir="./output",                        # all file ops confined here
    allowed_actions=["write_file", "read_file"],
)

enact = EnactClient(
    systems={"github": github, "filesystem": fs},
    policies=[
        dont_push_to_main,
        dont_delete_file,
        require_branch_prefix("agent/"),
    ],
    # secret= required — set ENACT_SECRET env var or pass it directly
)
```

Then ask:
> "This is what I'd write to `enact_setup.py`. I'd also modify your agent files
> to import and use this `enact` client instead of calling the APIs directly.
> All changes go on a new branch `enact/setup` so you can review before merging.
>
> Want to proceed, or adjust anything first?"

---

## Step 6: Write the Code

Only after explicit "yes" / "go ahead" / "do it":

1. Check if git is initialized: `git status`. If not, skip branch creation and note it.
2. If git exists: `git checkout -b enact/setup`
3. `pip install enact-sdk` (show output — if it fails, tell user to run manually)
4. Write `enact_setup.py`
5. For each agent file with dangerous calls:
   - Add `from enact_setup import enact` at top
   - Wrap direct API calls through `enact.run()` or the appropriate connector method
   - Show before/after for each change
6. List every file modified and every line changed

---

## Step 7: Wrap Up

After writing:

> "Done. Here's what changed:
> [list every file and the nature of each change]
>
> Next steps:
> 1. Set your env vars: `GITHUB_TOKEN`, `ENACT_CLOUD_API_KEY` (optional), etc.
> 2. Run your agent — every action now goes through Enact
> 3. See receipts: `enact.get_receipts()` or push to Enact Cloud for a dashboard
>
> Full docs: https://docs.enact.cloud"

---

## If No Dangerous Patterns Found

> "I scanned [N] Python files and didn't find the patterns Enact typically wraps
> (HTTP mutations, file deletes, DB writes, GitHub/Slack API calls).
> Either your agent is read-only, or the dangerous parts are in a library
> I can't see from the source.
>
> Describe what your agent is actually doing and I'll help figure out
> what needs protecting."

---

## If User Wants a Custom Policy

If built-in policies don't cover their use case, offer to write one:

> "That's not in the built-in list, but Enact policies are just Python functions —
> I can write one for you. Give me one sentence: 'Block the action when ___.'
> I'll write the function and add it to your setup."

A custom policy looks like:
```python
from enact.models import ActionContext, PolicyResult

def only_staging_urls(ctx: ActionContext) -> PolicyResult:
    url = ctx.payload.get("url", "")
    allowed = url.startswith("https://staging.")
    return PolicyResult(passed=allowed, reason=f"URL must be staging: {url}")
```
```

---

## A.5 Files to Modify

### `index.html`

**Find:** The existing "Get started" or CTA section (search for `pip install enact-sdk`)

**Add after the pip install section** — a new section for the Claude Code skill:

```html
<!-- Enact Setup Skill -->
<section class="skill-section">
  <h2>Add Enact to your agent in minutes</h2>
  <p>The Enact Setup Skill analyzes your codebase, maps your agent's actions to
     the right policies and connectors, and writes the integration code — with
     your approval at every step.</p>

  <h3>Install the skill</h3>
  <pre><code>mkdir -p ~/.claude/skills/enact-setup && \
  curl https://raw.githubusercontent.com/russellmiller3/enact/master/skills/enact-setup/SKILL.md \
  -o ~/.claude/skills/enact-setup/SKILL.md</code></pre>

  <p>Then, inside your agent repo in Claude Code:</p>
  <pre><code>/enact-setup</code></pre>

  <p class="note">Requires <a href="https://claude.ai/claude-code">Claude Code</a>.
  The skill runs as an isolated agent — it reads your code, proposes changes,
  and only writes files after you say yes.</p>
</section>
```

(Exact markup will be adapted to match the landing page design language and existing CSS classes.)

---

## A.6 Edge Cases

| Scenario | Handling |
|----------|----------|
| Repo > 500 .py files | Limit scan to top-level + `agent/`, `agents/`, `src/`, `app/` dirs |
| No dangerous patterns found | Graceful message, ask user to describe agent behavior |
| `git` not initialized | Skip branch creation, note it, proceed with file writes |
| `pip install enact-sdk` fails | Show error, tell user to run manually, continue with skill proposal |
| User wants custom policy | Offer to write one — template provided in skill |
| `context: fork` not supported | Skill degrades gracefully — runs in main session instead |
| Pattern matches in test files | Skip `tests/`, `test_*.py`, `*_test.py` in scan |

---

## A.7 Implementation Order

### PRE-IMPLEMENTATION CHECKPOINT

1. Read `enact/client.py` and all 4 connector files — confirm the API surface in the skill matches actual code
2. Read `enact/policies/__init__.py` — confirm all policy names in the skill exist
3. Read `index.html` — find exact insertion point

### Cycle 1: Skill file

**Goal:** `skills/enact-setup/SKILL.md` exists, frontmatter is valid, content follows the step-by-step flow above

| Phase | Action |
|-------|--------|
| Write | Create `skills/` dir + `skills/enact-setup/SKILL.md` with full content |
| Verify | Read back the file — confirm frontmatter parses (name, description, disable-model-invocation, context, agent, allowed-tools all present) |
| Verify | Confirm skill content covers all 7 steps with no placeholder text |

**Commit:** `"feat: add /enact-setup Claude Code skill"`

### Cycle 2: Landing page section

**Goal:** `index.html` has a skill install section with the curl command and `/enact-setup` usage

| Phase | Action |
|-------|--------|
| Read | Read index.html, find insertion point |
| Write | Add skill section using existing design language |
| Verify | Start preview server, visually confirm section renders correctly |

**Commit:** `"feat: add enact-setup skill section to landing page"`

---

## A.8 Success Criteria

- [ ] `skills/enact-setup/SKILL.md` exists with valid frontmatter
- [ ] Skill content covers all 7 steps (orient → scan → map → present → propose → write → wrap up)
- [ ] All policy names in skill match `enact/policies/__init__.py` exports
- [ ] All connector class names in skill match actual connector files
- [ ] `EnactClient` constructor call in skill matches `enact/client.py` signature
- [ ] Landing page has skill install section with correct curl command
- [ ] Landing page section matches existing design language
- [ ] Existing tests still pass: `pytest -v`
