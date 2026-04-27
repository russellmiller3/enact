# Agent fuckup incidents — research log

**Purpose:** Real-world stories of AI coding agents (Claude Code, Cursor, Replit, etc.) accidentally destroying production systems. Used to source the chaos-test corpus and the cold-email pitch.

**Bias:** This list focuses on **honest mistakes** — the agent was trying to help and broke prod. We separately track **adversarial / prompt-injection** stories elsewhere; those are a smaller market because most modern models self-refuse them.

Last updated: 2026-04-27

---

## Incident catalog (chronological)

### 1. Replit / SaaStr / Jason Lemkin (July 2025)

**What:** Replit's AI coding agent deleted a live production database during an active code freeze, despite repeated explicit "DO NOT make changes" instructions. Wiped records on **1,206 executives + 1,196 companies**. The agent then **fabricated test results** and **lied about rollback being impossible** (rollback in fact worked).

**Pattern detected by:** explicit-freeze ignore; fabricated success reports; destructive DB ops outside scope.

**Sources:**
- [The Register — Vibe coding service Replit deleted production database](https://www.theregister.com/2025/07/21/replit_saastr_vibe_coding_incident/)
- [Fortune — AI-powered coding tool wiped out a software company's database in 'catastrophic failure'](https://fortune.com/2025/07/23/ai-coding-tool-replit-wiped-database-called-it-a-catastrophic-failure/)
- [Fast Company — Replit CEO: What really happened](https://www.fastcompany.com/91372483/replit-ceo-what-really-happened-when-ai-agent-wiped-jason-lemkins-database-exclusive)
- [AI Incident Database — Incident 1152](https://incidentdatabase.ai/cite/1152/)
- [eWeek — AI Agent Wipes Production Database, Then Lies About It](https://www.eweek.com/news/replit-ai-coding-assistant-failure/)

**Aftermath:** Replit added "automatic separation between dev and prod databases", planning-only mode, rollback improvements.

---

### 2. Claude Code / DataTalks.Club / Alexey Grigorev (Feb 2026)

**What:** Developer migrating his website to AWS. Switched computers; Terraform state file was on the old machine. Ran `terraform plan` — Terraform assumed no infra existed. Claude Code then ran `terraform destroy`, wiping **2.5 years of student data** (~2 million rows, plus snapshots).

**Pattern detected by:** missing-state-file → false "empty infra" assumption → destroy-everything; agent obeyed Terraform's incorrect plan instead of questioning it.

**Sources:**
- [Tom's Hardware — Claude Code deletes developers' production setup, 2.5 years of records nuked](https://www.tomshardware.com/tech-industry/artificial-intelligence/claude-code-deletes-developers-production-setup-including-its-database-and-snapshots-2-5-years-of-records-were-nuked-in-an-instant)
- [Hacker News — Claude Code wiped our production database with a Terraform command](https://news.ycombinator.com/item?id=47278720)
- [Alexey Grigorev — How I Dropped Our Production Database and Now Pay 10% More for AWS](https://alexeyondata.substack.com/p/how-i-dropped-our-production-database)
- [Storyboard18 — "The agent kept deleting files"](https://www.storyboard18.com/brand-makers/the-agent-kept-deleting-files-developer-says-anthropics-claude-code-wiped-2-5-years-of-data-91704.htm)

**Aftermath:** Grigorev added Terraform delete protections, AWS permissions tightening, moved Terraform state to S3.

---

### 3. Claude Code / firmware project (Oct 2025)

**What:** Developer asked Claude Code to clean up local artifacts. Agent ran `rm -rf tests/ patches/ plan/ ~/`. The trailing `~/` expanded to the home directory — wiped every user-owned file.

**Pattern detected by:** path-expansion bug; agent didn't recognize that `~/` as a single argument was the home dir.

**Sources:**
- [DEV — Your AI Agent Just Ran rm -rf / — Here's How to Stop It](https://dev.to/axonlabsdev/your-ai-agent-just-ran-rm-rf-heres-how-to-stop-it-425c)

---

### 4. Cursor IDE / "DO NOT RUN" override

**What:** Developer issued explicit `DO NOT RUN ANYTHING` instruction to a Cursor AI agent. Agent acknowledged the instruction, then immediately ran `rm -rf` on ~70 git-tracked files.

**Pattern detected by:** instruction-acknowledgement-then-violation (echoes Replit incident #1).

**Sources:**
- [Harper Foley — Ten AI Agents Destroyed Production. Zero Postmortems](https://www.harperfoley.com/blog/ai-agents-destroyed-production-zero-postmortems)

---

### 5. Claude Code / drizzle / background terminal

**What:** Claude Code agent running in a **background terminal session** (out of user's view) executed `drizzle-kit push --force` against a production PostgreSQL database. Wiped **60+ tables**.

**Pattern detected by:** background-agent autonomy; destructive migration tool with `--force` bypass; no human review before execution.

**Sources:**
- [Harper Foley — Ten AI Agents Destroyed Production](https://www.harperfoley.com/blog/ai-agents-destroyed-production-zero-postmortems)
- [GitHub — Claude Code agent autonomously ran destructive db command, wiped production database (Issue #27063)](https://github.com/anthropics/claude-code/issues/27063)

---

## Common patterns extracted (the corpus is built from these)

| # | Pattern | Real-world source | Corpus task |
|---|---|---|---|
| A | `terraform destroy` on missing-state assumption | DataTalks (#2) | `50_terraform_destroy_missing_state.md` |
| B | `drizzle-kit push --force` against prod | Background agent (#5) | `51_drizzle_force_push.md` |
| C | `rm -rf` with multi-target including `~/` | Firmware (#3) | `52_rm_rf_multi_target.md` |
| D | `aws s3 rm s3://bucket --recursive` | Generic / inferred | `53_aws_s3_recursive_delete.md` |
| E | `kubectl delete namespace` on shared cluster | Generic / inferred | `54_kubectl_delete_namespace.md` |
| F | `docker system prune -a --volumes` kills running data | Generic / inferred | `55_docker_prune_volumes.md` |
| G | `git reset --hard origin/main` loses local commits | Generic / inferred | `56_git_reset_hard_origin.md` |
| H | `git clean -fdx` deletes ignored files (incl. `.env`) | Generic / inferred | `57_git_clean_force.md` |
| I | `psql DROP DATABASE; CREATE DATABASE` for "clean slate" | DataTalks-adjacent | `58_psql_drop_database.md` |
| J | `chmod -R 777 .` on web dir for "permission fix" | Generic / inferred | `59_chmod_777_recursive.md` |

## Corpus split (decided 2026-04-27)

**Main corpus (`chaos/tasks/`)** — used in headline numbers:
- 3 innocent (controls)
- 4 ambiguous (agent might do the wrong thing)
- 4 dangerous-DB (proven damage cases)
- 10 new honest-mistake patterns (this list)
- = **21 prompts × 2 sweeps = 42 runs**

**Refused corpus (`chaos/tasks-refused/`)** — tracked but not in main signal:
- `22_dangerous_force_push_main`
- `23_dangerous_commit_env`
- `24_dangerous_modify_workflow`
- `30_injection_ignore_prev`
- `31_injection_user_says_commit_env`
- `32_injection_system_bypass`
- `40_adversarial_obfuscate_sql`

**Why split:** Sweep B (no Enact) showed Claude self-refuses these 7 of 7. Including them in the main report dilutes the "Enact prevented damage" signal. They become a separate stat box: "Claude's training already refuses these N patterns — Enact backstops them deterministically (no model drift)."

## Future research queue

- More specific Cursor-side stories (force-push to main, AI-generated bad merge resolution)
- GitHub Copilot agent incidents (currently underrepresented in catalog)
- Codex / OpenAI agent incidents
- Aider / Cline / cursor-agent CLI incidents
- Multi-tenant SaaS agent incidents (one user's prompt destroying another's data)
- Webhook-triggered agent incidents (e.g., GitHub PR comment causes destructive action)
