# Enact

**You just gave an LLM access to real APIs. What happens when it does something stupid?**

It already has. [Replit's agent deleted a production database](https://fortune.com/2025/07/23/ai-coding-tool-replit-wiped-database-called-it-a-catastrophic-failure/). [Amazon Kiro caused a 13-hour AWS outage](https://awesomeagents.ai/news/amazon-kiro-ai-aws-outages/). [Claude Code ran `rm -rf` on a home directory](https://byteiota.com/claude-codes-rm-rf-bug-deleted-my-home-directory/). These weren't bugs — the agents did exactly what they were told. The problem: nothing was checking _whether they should_.

Enact is the missing layer between your agent and the real world:

1. **Block dangerous actions before they fire** — Python policies run before anything executes. Agent tries to push to main? Blocked. Tries to delete without a WHERE clause? Blocked.
2. **Execute deterministically** — LLMs hallucinate. They call functions that don't exist, use wrong argument names, get column names wrong. Plain Python workflows do exactly what you wrote — they can be unit tested, reviewed in a PR, and `git diff`'d. LLM-generated actions cannot.
3. **Prove what happened** — Every run (PASS or BLOCK) writes a cryptographically-signed JSON receipt: who ran what, which policies passed, what changed.
4. **Roll back in one call** — When your agent wipes a database table, deletes the wrong branch, or trashes two hours of work, `enact.rollback(run_id)` brings it all back. Deleted rows restored. Branches recreated. PRs closed.

```
pip install enact-sdk
```

---

## Quickstart (30 seconds)

```bash
git clone https://github.com/russellmiller3/enact
cd enact
pip install enact-sdk
python examples/quickstart.py
```

That's it. Three runs — one BLOCK, one PASS, one ROLLBACK — with signed receipts.

Want the full show? `python examples/demo.py` runs a 3-act scenario: an agent blocked from pushing to main, a normal PR workflow, and a database wipe rolled back in one command. No credentials needed.

---

## Already have an agent? Migration takes 10 minutes.

Your agent's reasoning and planning logic doesn't change. You're adding a safety layer between it and your systems. Same calls, same results — now with policy enforcement, a signed audit trail, and rollback.

**Three steps:**

1. **Register your systems** — swap your existing SDK clients for Enact connectors (same credentials, now policy-gated)
2. **Move your guard logic** — any `if/else` checks you write become Python policy functions, or use our 24 built-in ones
3. **Replace direct calls** — `tool.do_thing()` becomes `enact.run()`

**Before (your agent today):**

```python
import github_sdk, psycopg2

# direct call — no policy check, no audit trail
github_sdk.create_pr(repo="myorg/app", branch="agent/fix-123", title="Fix bug")

# no WHERE protection — deletes every row
db.execute("DELETE FROM sessions")
```

**After (wrapped with Enact):**

```python
from enact import EnactClient
from enact.connectors.github import GitHubConnector
from enact.connectors.postgres import PostgresConnector
from enact.policies.git import dont_push_to_main
from enact.policies.db import dont_delete_without_where

# one-time setup — replaces your SDK clients
enact = EnactClient(
    secret="...",
    systems={
        "github":   GitHubConnector(token="..."),
        "postgres": PostgresConnector(dsn="postgresql://..."),
    },
    policies=[dont_push_to_main, dont_delete_without_where],
)

# same intent — now policy-gated, receipt-backed, rollback-able
result, receipt = enact.run(
    workflow="agent_pr_workflow",
    user_email="agent@company.com",
    payload={"repo": "myorg/app", "branch": "agent/fix-123"},
)
```

Works with LangChain, CrewAI, OpenAI, Claude tool_use — any framework that can call a Python function. Your agent's prompting and reasoning stay exactly as-is.

---

## Core Concepts

Think of Enact like a **foreman supervising an AI carpenter**. The carpenter is capable and fast, but needs oversight. When the carpenter says "I want to tear down this wall":

1. **Permit check** — Before any tool is picked up, the foreman checks the plans. Load-bearing? Utilities inside? Approved? If not: work stops, written reason recorded.
2. **Blueprint** — If approved, the carpenter follows exact step-by-step instructions — not just "tear down the wall" but each specific action in order. No improvising.
3. **Work log** — A signed record of every nail pulled, every stud removed, exact before-and-after state. Cryptographically sealed so it can't be altered later.
4. **Change order** — If the carpenter tore down the WRONG wall, the foreman issues a change order. Enact uses the work log to reverse every step and put it back.

### The Four Pieces

| Piece        | What it is                                  | Analogy                             |
| ------------ | ------------------------------------------- | ----------------------------------- |
| **Policy**   | A Python function that returns pass/fail    | The permit check                    |
| **Workflow** | A Python function that does the actual work | The blueprint the carpenter follows |
| **Receipt**  | A signed JSON record of what happened       | The signed work log                 |
| **Rollback** | One call that reverses an entire run        | The change order + teardown         |

### How They Fit Together

```
Agent wants to do something
         |
         v
    +----------+
    | POLICIES |  <-- "Is this approved?" (permit check)
    +----------+
         |
    PASS |  BLOCK --> Receipt (denied + reason)
         v
    +-----------+
    | WORKFLOW  |  <-- "Follow the blueprint, step by step"
    +-----------+
         |
         v
    +----------+
    | RECEIPT  |  <-- "Signed work log — what happened, what changed"
    +----------+
         |
    if needed:
         v
    +----------+
    | ROLLBACK |  <-- "Change order — reverse every step using the work log"
    +----------+
```

### Why This Matters

These weren't bugs — the agents did exactly what they were told. The problem was no permit check, no work log, no way to undo it:

| Incident        | What Happened                                                             | Source                                                                                                                     |
| --------------- | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **Replit**      | Agent deleted a production database containing data for 2,400+ executives | [Fortune, Jul 2025](https://fortune.com/2025/07/23/ai-coding-tool-replit-wiped-database-called-it-a-catastrophic-failure/) |
| **Amazon Kiro** | Agent deleted an EC2 environment → 13-hour AWS outage                     | [Awesome Agents, Feb 2026](https://awesomeagents.ai/news/amazon-kiro-ai-aws-outages/)                                      |
| **Claude Code** | Agent ran `rm -rf ~/` — wiped developer's entire home directory           | [ByteIota, Dec 2025](https://byteiota.com/claude-codes-rm-rf-bug-deleted-my-home-directory/)                               |

---

## How It Works

### Prerequisite: The Connector

**WHY:** Your agent shouldn't call GitHub directly. You want a middleman that (a) limits what the agent can do and (b) records what actually happened. That's the Connector.

A **Connector** is a pre-built class that wraps an external system. You create one, hand it to Enact, and Enact passes it to your workflow. You never call GitHub (or Postgres, or the filesystem) directly anymore — you call the connector.

Think of it like handing a contractor a limited toolbox before you leave for work. The toolbox only contains the tools you specifically put in it. If the contractor hallucinates and decides to demolish a load-bearing wall — too bad, there's no sledgehammer in the box.

Here is how you create and use a connector:

```python
from enact.connectors.github import GitHubConnector

# Create the connector — you only allow the two actions you actually need
gh = GitHubConnector(
    token="ghp_...",                              # Your GitHub Personal Access Token
    allowed_actions=["create_branch", "create_pr"] # ONLY these methods can be called
)

# Now call an action on it
result = gh.create_branch(repo="owner/repo", branch="agent/fix-149")

# Every action returns an ActionResult — a mini-receipt for that one action
print(result.success)  # True or False
print(result.output)   # {"branch": "agent/fix-149"}
```

**Why `allowed_actions` matters:** Policies are your smart rules — they enforce your business logic and the scenarios you anticipated. `allowed_actions` is your hardcoded floor: even if your agent tries something you never thought to write a policy for, it simply can't execute an action that isn't on the list. Policies handle what you thought of. `allowed_actions` handles everything you didn't.

```python
# This is what happens if the agent goes rogue:
gh.delete_branch(repo="owner/repo", branch="main")
# -> PermissionError: Action 'delete_branch' not in allowlist
```

Enact ships connectors for GitHub, Postgres, the filesystem, and Slack. You don't write these — you import and configure them.

### Prerequisite: The Context

The `WorkflowContext` is the "bag of data" that travels through the entire system — passed to every policy check and every action.

Think of it like a delivery package. The context contains:

1. **Who sent it** (`user_email`)
2. **What they want done** (`payload`)
3. **The tools they can use** (`systems`)

Here is what a `WorkflowContext` looks like in memory:

```python
# Enact builds this automatically — you never create it manually.
# It's shown here so you understand what your workflow receives.
context = WorkflowContext(
    user_email="agent@company.com",             # Who is making the request
    payload={                                   # The data the agent wants to act on
        "repo": "owner/repo",
        "branch": "agent/fix-149",
    },
    systems={                                   # The connectors, keyed by name
        "github": GitHubConnector(              # The actual connector you configured
            token="ghp_...",
            allowed_actions=["create_branch", "create_pr"],
        ),
    },
)
```

### Step 1: Define what your agent should do

**WHY:** Instead of your agent running arbitrary code against GitHub, you give it a script to follow — a plain Python function. Enact runs that function. This way, every action is recorded, every failure is caught, and you can roll back the whole thing.

A workflow is a Python function that takes a `context` (the bag from above) and returns a list of `ActionResult` objects — one per action taken.

```python
from enact.models import WorkflowContext, ActionResult

def agent_pr_workflow(context: WorkflowContext) -> list[ActionResult]:
    # Pull the connector and payload data out of the context bag
    gh = context.systems["github"]      # The GitHubConnector you configured
    repo = context.payload["repo"]      # "owner/repo"
    branch = context.payload["branch"]  # "agent/fix-149"

    results = []

    # Take the first action — create the branch
    result1 = gh.create_branch(repo=repo, branch=branch)
    results.append(result1)  # Keep a running log of everything that happened

    # Stop early if it failed — no point creating a PR for a branch that doesn't exist
    if not result1.success:
        return results

    # Take the second action — open the pull request
    # f"Agent: {branch}" is Python string interpolation: becomes "Agent: agent/fix-149"
    result2 = gh.create_pr(repo=repo, title=f"Agent: {branch}", body="Automated PR", head=branch)
    results.append(result2)

    return results  # Enact signs this list into a receipt
```

### Step 2: Define the policies it should follow

**WHY:** The workflow does whatever you tell it to. Policies decide _whether it should run at all_. They run first, before any action fires. If any policy fails, the whole run is blocked and you get a receipt explaining why.

A policy is a plain Python function — no LLMs, no magic. It reads the context and returns pass or fail with a reason.

Here's a concrete example. The standard engineering rule is: no one pushes directly to `main`. Instead, changes go into a separate branch, get reviewed by a human in a Pull Request (PR), and only then get merged. This gives you a checkpoint before anything goes live.

Agents break this rule constantly. They push directly to `main` because no one told them not to — and because they can. The Amazon Kiro incident was exactly this pattern: an agent made a direct infrastructure change with no review step, and caused a 13-hour AWS outage. This policy is the guardrail: if the agent tries to target `main`, the run is blocked before any code is touched.

```python
from enact.models import WorkflowContext, PolicyResult

def dont_push_to_main(context: WorkflowContext) -> PolicyResult:
    branch = context.payload.get("branch", "")
    branch_is_not_main = branch.lower() not in ("main", "master")
    return PolicyResult(
        policy="dont_push_to_main",
        passed=branch_is_not_main,
        reason="Branch is not main/master" if branch_is_not_main else f"Direct push to '{branch}' is blocked",
    )
```

**How the check works — three logical steps:**

```
┌─────────────────────────────────────────────────────────┐
│  STEP 1: Read the branch name from the agent's request  │
│    context.payload.get("branch", "")  -->  "main"       │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 2: Is this branch safe to push to?                │
│    branch_is_not_main = branch not in ("main","master") │
│                                                         │
│    "agent/fix-149" -->  branch_is_not_main = True   ✅  │
│    "main"          -->  branch_is_not_main = False  🚫  │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 3: passed = branch_is_not_main                    │
│                                                         │
│    True   -->  PASS ✅                                  │
│    False  -->  BLOCK 🚫                                 │
└─────────────────────────────────────────────────────────┘
```

You don't need to write most policies yourself — Enact ships 24 built-in ones. See [Built-in Policies](#built-in-policies) below.

### Step 3: Wire it all up and run

**WHY:** Now you hand everything to `EnactClient` — your connectors, policies, and workflows. Then you call `enact.run()` the same way your agent would. Enact handles the policy check, the execution, and the receipt.

```python
from enact import EnactClient
from enact.connectors.github import GitHubConnector
from enact.workflows.agent_pr_workflow import agent_pr_workflow
from enact.policies.git import dont_push_to_main, require_branch_prefix

enact = EnactClient(
    systems={
        "github": GitHubConnector(
            token="ghp_...",                                 # Your GitHub PAT
            allowed_actions=["create_branch", "create_pr"], # Only these are allowed
        )
    },
    policies=[
        dont_push_to_main,           # A plain policy function (defined above)
        require_branch_prefix("agent/"),  # A policy *factory* — calling it with "agent/"
                                          # returns a configured policy function
    ],
    workflows=[agent_pr_workflow],   # Register the workflow by passing the function
    secret="your-secret-here",       # Min 32 chars. Or: export ENACT_SECRET="..." in shell
)

# This is what your agent calls. It returns two things:
result, receipt = enact.run(
    workflow="agent_pr_workflow",        # Which workflow to run (must be registered above)
    user_email="agent@company.com",      # Who is making the request (for audit trail)
    payload={"repo": "owner/repo", "branch": "agent/fix-149"},  # Data for the workflow
)

print(result.decision)   # "PASS" or "BLOCK"
print(receipt.run_id)    # UUID — use this to look up or roll back the run
```

### Step 4: Read the receipts

Every run — PASS or BLOCK — writes a signed JSON receipt to `receipts/`:

```json
{
  "run_id": "a1b2c3d4-...",
  "workflow": "agent_pr_workflow",
  "user_email": "agent@company.com",
  "decision": "PASS",
  "policy_results": [
    {
      "policy": "dont_push_to_main",
      "passed": true,
      "reason": "Branch is not main/master"
    },
    {
      "policy": "require_branch_prefix",
      "passed": true,
      "reason": "Branch 'agent/fix-149' has required prefix"
    }
  ],
  "actions_taken": [
    { "action": "create_branch", "system": "github", "success": true },
    { "action": "create_pr", "system": "github", "success": true }
  ],
  "timestamp": "2026-02-26T03:30:00Z",
  "signature": "hmac-sha256-hex..."
}
```

Verify a receipt hasn't been tampered with:

```python
from enact.receipt import verify_signature
is_valid = verify_signature(receipt, secret="your-secret")
```

### Receipt Browser (local UI)

Browse, filter, and verify your receipts locally — no cloud required.

```bash
enact-ui                           # serves receipts/ on http://localhost:8765
enact-ui --port 9000               # custom port
enact-ui --dir /path/to/receipts   # custom directory
enact-ui --secret YOUR_SECRET      # enables signature verification in the UI
```

The browser shows every run (PASS / BLOCK / ROLLED_BACK), lets you click into the full JSON, and highlights invalid signatures. Dark mode toggle included. Zero extra dependencies — ships with `enact-sdk`.

### Step 5: Rollback (if something goes wrong)

**WHY:** Say the `agent_pr_workflow` from Step 1 ran — it created `agent/fix-149`, opened a PR, and merged it straight to `main` by mistake. You need to undo all three steps. One call.

`rollback()` does four things in order:

1. **Loads the receipt** by `run_id` — looks up `receipts/a1b2c3d4-....json`
2. **Verifies the signature** — if the receipt was tampered with, rollback refuses to run
3. **Walks `actions_taken` in reverse** — last action first, so nothing is orphaned
4. **Calls the undo action** for each step and writes a new rollback receipt

Here's what "in reverse" looks like for a workflow that created a branch, opened a PR, then merged it:

```
Original run (forward):          Rollback (reverse):

  Step 1: create_branch           Step 3 undone: revert_commit  (new commit on main)
  Step 2: create_pr            →  Step 2 undone: close_pr
  Step 3: merge_pr                Step 1 undone: delete_branch
```

Why reverse? `merge_pr` happened last — you have to undo it first before closing the PR makes sense. Reverse order preserves the dependency chain.

`revert_commit` is `git revert -m 1 <sha>` under the hood — it adds a new commit to `main` that restores its pre-merge state. Safe on protected branches; no force-push needed. The merge SHA is captured automatically in the receipt when `merge_pr` runs.

```python
# receipt.run_id came from the enact.run() call in Step 3
rollback_result, rollback_receipt = enact.rollback(receipt.run_id)

print(rollback_result.decision)          # "ROLLED_BACK"
print(rollback_result.actions_reversed)  # ["revert_commit", "close_pr", "delete_branch"]
```

The rollback receipt looks like this — note the `revert_sha` showing exactly what was created on `main`:

```json
{
  "run_id": "rb-9f8e7d6c-...",
  "original_run_id": "a1b2c3d4-...",
  "workflow": "agent_pr_workflow",
  "decision": "ROLLED_BACK",
  "actions_reversed": [
    {
      "action": "revert_commit",
      "system": "github",
      "success": true,
      "output": { "revert_sha": "f7c3a1b...", "reverted_merge": "e9d2c4a...", "base_branch": "main" }
    },
    { "action": "close_pr",      "system": "github", "success": true },
    { "action": "delete_branch", "system": "github", "success": true }
  ],
  "timestamp": "2026-02-26T03:35:00Z",
  "signature": "hmac-sha256-hex..."
}
```

**One caveat on re-merging:** A revert doesn't erase history. If you fix the issue and try to re-merge the same branch later, Git will skip those commits (it thinks they're already in `main`). You'd need to `git revert <revert_sha>` first — "undo the undo" — then merge. This is standard Git behavior, not an Enact quirk.

**What if an action truly can't be undone?** `push_commit` has no safe inverse without a force-push, which GitHub blocks on protected branches. If rollback hits one of these, it stops, records which action couldn't be reversed, and tells you exactly what to fix manually. It won't silently skip it.

---

## Built-in Policies

Enact ships 26 built-in policies across 7 categories so you don't have to write them from scratch:

| Category       | Policies                                                                                                                                                          | What they block                                              |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| **Git**        | `dont_push_to_main`, `require_branch_prefix`, `max_files_per_commit`, `dont_delete_branch`, `dont_merge_to_main`                                                  | Direct pushes to main, wrong branch names, blast radius      |
| **Database**   | `dont_delete_row`, `dont_delete_without_where`, `dont_update_without_where`, `protect_tables`, `block_ddl`                                                        | Dangerous deletes, unscoped updates, DDL like `DROP TABLE`   |
| **Filesystem** | `dont_delete_file`, `restrict_paths`, `block_extensions`                                                                                                          | File deletions, path traversal, sensitive files (.env, .key) |
| **Access**     | `contractor_cannot_write_pii`, `require_actor_role`, `require_user_role`, `dont_read_sensitive_tables`, `dont_read_sensitive_paths`, `require_clearance_for_path` | Unauthorized access, PII exposure                            |
| **CRM**        | `dont_duplicate_contacts`, `limit_tasks_per_contact`                                                                                                              | Duplicate records, rate limiting                             |
| **Time**       | `within_maintenance_window`, `code_freeze_active`                                                                                                                 | Actions outside allowed hours, during code freezes           |
| **Slack**      | `require_channel_allowlist`, `block_dms`                                                                                                                          | Off-list channel posts, direct messages to users             |

```python
from enact.policies.git import dont_push_to_main, require_branch_prefix
from enact.policies.db import protect_tables, block_ddl
from enact.policies.time import code_freeze_active
from enact.policies.slack import require_channel_allowlist, block_dms
```

---

## How It Flows

```
agent calls enact.run()
        |
        v
+-------------------+
|  Policy Gate      |  All policies run. Any failure = BLOCK.
|  (pure Python,    |  No LLMs. Versioned in Git. Testable.
|   no LLMs)        |
+--------+----------+
    PASS |  BLOCK
         |        +-->  Receipt (decision=BLOCK, actions_taken=[])
         v
+-------------------+
|  Workflow runs    |  Enact executes the workflow against real systems.
|  against real     |  Each action produces an ActionResult.
|  systems          |
+--------+----------+
         |
         v
+-------------------+
|  Signed Receipt   |  HMAC-SHA256 signed. Captures who/what/why/
|                   |  pass-fail/what changed.
+--------+----------+
         |
         v
  (RunResult, Receipt) returned to caller
```

---

## Connectors & Allowed Actions

You might be thinking: _"Don't we already have Policies?"_ Yes — but `allowed_actions` adds a complementary layer that works differently.

- **Policies** are your business rules: "You can push code, but not to the `master` branch."
- **`allowed_actions`** is your hardcoded floor: "This connector can only ever call these two methods. Full stop."

Policies handle the scenarios you anticipated. `allowed_actions` caps the blast radius for everything else — even actions you never thought to write a policy for. The list is checked before any API call, every time, with no exceptions.

### Available Actions by Connector

| System         | Actions                                                                   | Rollback                               | Idempotent                      |
| -------------- | ------------------------------------------------------------------------- | -------------------------------------- | ------------------------------- |
| **GitHub**     | `create_branch`, `create_pr`, `create_issue`, `delete_branch`, `merge_pr` | Yes — `merge_pr` via `revert_commit`; except `push_commit` | Yes — `already_done` convention |
| **Postgres**   | `select_rows`, `insert_row`, `update_row`, `delete_row`                   | Yes — pre-SELECT captures state        | Yes                             |
| **Filesystem** | `read_file`, `write_file`, `delete_file`, `list_dir`                      | Yes — content captured before mutation | Yes                             |
| **Slack**      | `post_message`, `delete_message`                                          | Yes — `post_message` via `delete_message` (bot token must have `chat:delete` scope) | No — posting the same text twice is two messages, not a duplicate |

### What Rollback Can and Can't Undo

| Action | Rollback? | How |
| -------------------- | --------- | --- |
| `github.create_branch` | ✅ | Deletes the branch |
| `github.create_pr` | ✅ | Closes the PR |
| `github.merge_pr` | ✅ | `git revert -m 1 <sha>` — adds a new commit to the base branch restoring pre-merge state. Safe on protected branches; no force-push. |
| `github.delete_branch` | ✅ | Recreates branch at the captured SHA |
| `github.push_commit` | ❌ | Un-pushing requires a destructive force-push, which GitHub blocks on protected branches |
| `postgres.insert_row` | ✅ | Deletes the inserted row |
| `postgres.update_row` | ✅ | Restores pre-update values (pre-SELECT captures state) |
| `postgres.delete_row` | ✅ | Re-inserts every deleted row (pre-SELECT captures state) |
| `postgres.DROP TABLE` | ❌ | Not a connector action — blocked by `block_ddl` policy. Even with captured rows, you'd lose indexes, constraints, sequences, and foreign keys. Prevention beats fake recovery. |
| `postgres.TRUNCATE` | ❌ | Same as above — blocked by `block_ddl` |
| `filesystem.write_file` | ✅ | Restores previous content (or deletes if file was new) |
| `filesystem.delete_file` | ✅ | Recreates file with captured content |
| `slack.post_message` | ✅ | Deletes the posted message via `chat.delete` using the `ts` timestamp captured at post time |
| `slack.delete_message` | ❌ | You can't un-delete a Slack message |

**One caveat on `merge_pr` rollback:** After reverting a merge, if you fix the issue and try to re-merge the same branch, Git will skip those commits (they look already-merged). Revert the revert commit first (`git revert <revert_sha>`), then re-merge. This is standard Git behavior.

---

## Security

Receipts are HMAC-SHA256 signed. The signature covers **every field** — tampering with any field invalidates it.

```bash
export ENACT_SECRET="$(openssl rand -hex 32)"
```

Or pass `secret=` to `EnactClient`. Minimum 32 characters. No default.

For dev/testing only: `EnactClient(..., secret="short", allow_insecure_secret=True)`

Rollback verifies the receipt signature before executing any reversal — tampered receipts can't trigger unintended operations.

---

## Cloud Features

Push receipts to the Enact cloud and use human-in-the-loop gates from any workflow.

```python
from enact import EnactClient

enact = EnactClient(
    systems={"github": gh},
    policies=[dont_push_to_main],
    workflows=[agent_pr_workflow],
    secret="your-secret",
    cloud_api_key="eak_...",   # get at enact.cloud — enables cloud features
)
```

**Push receipts to cloud storage:**

```python
result, receipt = enact.run(...)
enact.push_receipt_to_cloud(receipt)   # receipt now searchable in cloud UI
```

**Human-in-the-loop gate** — pause a workflow and email a human to approve before continuing:

```python
result, receipt = enact.run_with_hitl(
    workflow="agent_pr_workflow",
    user_email="agent@company.com",
    payload={"repo": "myorg/app", "branch": "agent/nuke-main"},
    notify_email="ops@company.com",    # who gets the approve/deny email
    timeout_seconds=3600,              # auto-deny after 1 hour of silence
)

print(result.decision)   # "PASS" if approved, "BLOCK" if denied or timed out
```

The approval email contains a signed link. Clicking approve or deny fires a callback and writes a HITL receipt. No credentials or login needed for the approver.

**Status badge** — embed in your README to show real-time pass/block rate for a workflow:

```markdown
![agent_pr_workflow](https://enact.cloud/badge/your-team-id/agent_pr_workflow.svg)
```

---

## Run Tests

```bash
pytest tests/ -v
# 356+ tests, 0 failures (SDK + cloud)
```

---

## Environment Variables

| Variable           | Required                | Purpose                                            |
| ------------------ | ----------------------- | -------------------------------------------------- |
| `ENACT_SECRET`     | Yes (or pass `secret=`) | HMAC signing key. 32+ characters.                  |
| `GITHUB_TOKEN`     | For GitHubConnector     | GitHub PAT or App token                            |
| `SLACK_BOT_TOKEN`  | For SlackConnector      | Slack bot token (xoxb-...). Needs `chat:write` scope; add `chat:delete` to enable rollback. |
| `ENACT_FREEZE`     | Optional                | Set to `1` to activate `code_freeze_active` policy |
| `CLOUD_API_KEY`    | For cloud features      | API key from enact.cloud — enables receipt push + HITL |
| `CLOUD_SECRET`     | Cloud backend only      | Server-side signing secret for the cloud backend   |
| `ENACT_EMAIL_DRY_RUN` | Cloud backend only   | Set to `1` to skip real email sends in dev/test    |

---

## Deployment

The Enact landing page is hosted on **Vercel** with DNS managed via **Porkbun**.

- **URL:** [https://enact.cloud](https://enact.cloud)
- **Frontend:** Static HTML (`index.html`)
- **CI/CD:** Auto-deploy on push to `master` branch
