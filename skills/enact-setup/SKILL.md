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

You're helping the user add Enact to their AI agent codebase. Enact is an action
firewall: it intercepts dangerous actions before they execute, generates
cryptographically-signed audit receipts, and enables one-command rollback.

Your job: act like a knowledgeable colleague who's done this integration before.
Explain what you're seeing, why it matters, and check understanding before writing
code. Never write code without explicit user approval.

## Tone
- Blunt and direct. No "Great!" No corporate cheerleading.
- Explain WHY, not just HOW.
- When you see something risky in the code, name it specifically.
- Check for understanding with a question before moving on.

---

## Step 1: Orient

If $ARGUMENTS is provided, start by reading that file. Otherwise:

1. Read `README.md` if it exists — understand what this agent does
2. Glob for entry points: `main.py`, `agent.py`, `app.py`, `run.py`, `bot.py`
3. Read each (first 100 lines) to understand the agent's purpose

Summarize: "Here's what I understand your agent does: [summary]. That right?"

Wait for confirmation before scanning.

---

## Step 2: Scan for Dangerous Patterns

Search all `.py` files. Skip: `tests/`, `venv/`, `.venv/`, `node_modules/`, `__pycache__/`.

If the repo has >500 `.py` files, limit scan to: top-level directory + any directory
named `agent/`, `agents/`, `src/`, `app/`.

Also skip `test_*.py` and `*_test.py` files — test code isn't running in production.

**HTTP/API mutations** (may need custom policy):
- `requests\.(post|put|delete|patch)`
- `httpx\.(post|put|delete|patch)`
- `aiohttp.*\.(post|put|delete|patch)`

**File system mutations** → FilesystemConnector:
- `os\.remove|os\.unlink|os\.rmdir|os\.makedirs|shutil\.rmtree|shutil\.move`
- `open\(.*['"](w|a|wb|ab)['"]`
- `Path.*\.(write_text|write_bytes|unlink|rmdir)`

**Shell/subprocess** → custom policy (allowlist specific commands):
- `subprocess\.(run|call|Popen|check_output)`
- `os\.system\(`

When you find subprocess calls, read the actual arguments — if any call passes
`"main"` or `"master"` as an argument to `git push`, flag it as CRITICAL severity.
A raw `git push origin main` via subprocess bypasses the GitHubConnector entirely
and is the most dangerous pattern in most agent codebases.

**Database mutations** → PostgresConnector:
- `cursor\.execute.*(INSERT|UPDATE|DELETE)`
- `\.commit\(\)`
- `psycopg2|asyncpg|sqlalchemy`

**GitHub** → GitHubConnector:
- `from github import|PyGitHub|github\.Github`
- `\.(create_|create_git_ref|create_comment|edit\(|merge|delete)` on any receiver
  (catches `repo.create_git_ref`, `issue.edit`, `issue.create_comment`, `pr.merge`, etc.)

**Slack** → SlackConnector:
- `from slack_sdk|import slack`
- `chat_postMessage|files_upload|conversations_kick`

For each match: record file, line number, and the specific call.

---

## Step 3: Map to Enact

For each dangerous pattern found, map it to an Enact construct:

| Pattern found | Enact suggestion |
|---------------|-----------------|
| `requests.delete/post/put` | Custom policy: URL allowlist before firing |
| `os.remove` / `shutil.rmtree` | `FilesystemConnector` + `dont_delete_file` |
| `subprocess.run` | Custom policy: command allowlist |
| DB `INSERT`/`UPDATE`/`DELETE` | `PostgresConnector` + `dont_delete_without_where` |
| GitHub repo mutations | `GitHubConnector` + `dont_push_to_main` |
| Slack messages | `SlackConnector` + `require_channel_allowlist` |

**Built-in policies (real names — import from submodule):**
```
# Git  (from enact.policies.git)
dont_push_to_main                         # plain function
dont_merge_to_main                        # plain function
dont_delete_branch                        # sentinel — always blocks delete
dont_force_push                           # blocks --force / -f / --force-with-lease
dont_commit_api_keys                      # blocks commits containing credential patterns
require_branch_prefix(prefix="agent/")   # factory
require_meaningful_commit_message         # blocks empty/short/generic messages
max_files_per_commit(max_files=50)        # factory

# DB  (from enact.policies.db)
dont_delete_row                           # sentinel — always blocks
dont_delete_without_where                 # plain function
dont_update_without_where                 # plain function
block_ddl                                 # blocks DROP/TRUNCATE/ALTER/CREATE
protect_tables(["users", "payments"])     # factory

# Filesystem  (from enact.policies.filesystem)
dont_delete_file                          # sentinel — always blocks
dont_edit_gitignore                       # blocks writes to .gitignore
dont_read_env                             # blocks access to .env files
dont_touch_ci_cd                          # blocks CI/CD files (Dockerfile, fly.toml, .github/workflows, etc.)
dont_access_home_dir                      # blocks paths under ~, /root, /home
dont_copy_api_keys                        # blocks writes whose content contains credential patterns
restrict_paths(["/workspace"])            # factory — path confinement
block_extensions([".env", ".key"])        # factory

# Access  (from enact.policies.access)
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

**Note on human approval:** There is no standalone "require human approval" policy.
Human-in-the-loop gating is handled by Enact Cloud's HITL feature.
See: https://docs.enact.cloud/concepts/hitl

---

## Step 4: Present Findings

Walk through findings one category at a time. Be specific: file name + line number + the call.

Example:
> "In `agent.py` line 47, you're calling `requests.delete()` against your own API.
> That's the most dangerous call I found — if the agent hallucinates the endpoint,
> it could delete real data with no audit trail and no way to undo it.
>
> I'd wrap this with a policy that: (1) checks the URL against an allowlist before
> it fires, (2) generates a signed receipt of every delete call, (3) enables rollback
> if you capture the resource state beforehand.
>
> Does that match how risky you think this call is?"

Check understanding after each category. Let the user push back or adjust.

---

## Step 5: Propose the Setup

Once all patterns are discussed, show the proposed `enact_setup.py`.
Tailor it to what was actually found — don't include connectors for patterns
that weren't in this repo.

Example (adjust to match the actual findings):
```python
# enact_setup.py — generated by /enact-setup
import os
from enact import EnactClient
from enact.connectors.github import GitHubConnector
from enact.connectors.filesystem import FilesystemConnector
from enact.policies.git import dont_push_to_main, dont_merge_to_main, require_branch_prefix
from enact.policies.filesystem import dont_delete_file

github = GitHubConnector(
    token=os.environ["GITHUB_TOKEN"],
    allowed_actions=["create_branch", "create_pr"],
)
fs = FilesystemConnector(
    base_dir="./output",            # all file ops confined to this dir
    allowed_actions=["write_file", "read_file"],
)

enact = EnactClient(
    systems={"github": github, "filesystem": fs},
    policies=[
        dont_push_to_main,
        dont_delete_file,
        require_branch_prefix("agent/"),
    ],
    # ENACT_SECRET env var required — used to sign receipts
)
```

Then ask:
> "This is what I'd write to `enact_setup.py`. I'd also add an import to your
> agent files so they use this `enact` client instead of calling the APIs directly.
> All changes go on a new branch `enact/setup` so you can review before merging.
>
> Want to proceed, or adjust anything first?"

---

## Step 6: Write the Code

Only after explicit "yes" / "go ahead" / "do it":

1. Check git status: `git status`. If uncommitted changes exist, warn the user before proceeding.
2. If git is initialized: `git checkout -b enact/setup`
   If git is not initialized: skip branch creation, note it, continue.
3. `pip install enact-sdk` — show output. If it fails, tell the user to run it manually.
4. Write `enact_setup.py` with the proposed content.
5. For each agent file containing dangerous calls:
   - Add `from enact_setup import enact` at the top
   - Show the before/after for each change before writing it
6. After all writes: list every file modified and what changed.

---

## Step 7: Wrap Up

After writing:

> "Done. Here's what changed:
> [list every file and the nature of each change]
>
> Next steps:
> 1. Set your env vars: `ENACT_SECRET` (required), `GITHUB_TOKEN`, etc.
> 2. Run your agent — every action now goes through Enact
> 3. Check receipts: `enact.get_receipts()` or push to Enact Cloud for a dashboard
>
> Full docs: https://docs.enact.cloud"

---

## If No Dangerous Patterns Found

> "I scanned [N] Python files and didn't find the patterns Enact typically wraps
> (HTTP mutations, file deletes, DB writes, GitHub/Slack API calls). Either your
> agent is read-only (lucky you), or the dangerous parts are in a library I can't
> see from the source.
>
> Describe what your agent actually does and I'll help figure out what needs protecting."

---

## If User Wants a Custom Policy

If built-in policies don't cover their use case, offer to write one:

> "That's not in the built-in list, but Enact policies are just Python functions —
> I can write one right now. Give me one sentence: 'Block the action when ___.'
> I'll write the function and add it to your setup."

A custom policy looks like:
```python
from enact.models import WorkflowContext, PolicyResult

def only_staging_urls(context: WorkflowContext) -> PolicyResult:
    url = context.payload.get("url", "")
    passed = url.startswith("https://staging.")
    return PolicyResult(
        policy="only_staging_urls",
        passed=passed,
        reason=f"URL must be on staging: got '{url}'",
    )
```

Pass it in like any built-in: `EnactClient(policies=[only_staging_urls, ...])`
