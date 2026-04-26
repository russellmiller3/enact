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

**Date:** 2026-04-26 (session 10)
**Project:** Enact — action firewall for AI agents (`pip install enact-sdk`)

### Git State

- Branch: `claude/add-guardrails-ai-tools-Mk20f` (feature → merge to `master`)
- Remote: `origin` + `backup` (D drive)
- Vercel: `www.enact.cloud` — deployed
- PyPI: `enact-sdk 0.5.1` — published (next bump: 0.6.0 after merge)
- Working tree: **dirty during cleanup; clean after final commit**

### What Was Done (session 10) — Enact Code (CC hook)

**Shipped `enact-code-hook` binary** — drop-in Claude Code PreToolUse/PostToolUse hook
that runs every Bash call through enact's policy engine before execution.

- `enact/cli/code_hook.py` (NEW, ~250 lines) — three subcommands:
  - `enact-code-hook init` — writes `.claude/settings.json` (merge-safe — preserves
    existing user hooks for other tools), bootstraps `.enact/policies.py`,
    generates 32-byte HMAC secret with 0600 perms, gitignores `.enact/`
  - `enact-code-hook pre` — reads PreToolUse JSON from stdin; runs `parse_bash_command`
    + `evaluate_all`; emits deny JSON or exits 0 silently. Outer try/except = fail-open
    on any unexpected error (broken policies.py, ImportError, etc).
  - `enact-code-hook post` — writes signed Receipt with `actions_taken[0]`
    containing command + exit_code + interrupted flag. Decision="PASS" reflects
    policy gate; ActionResult.success reflects bash exit status.
- `enact/cli/__init__.py` (NEW) — package marker
- `pyproject.toml` — added `[project.scripts]` registering `enact-code-hook`
- `tests/test_code_hook.py` (NEW) — 25 tests:
  - parser × 5 (table/where/sql/args extraction from psql + git push)
  - cmd_pre × 8 (allow + deny + force-push + freeze + fail-open + missing/broken policies)
  - cmd_init × 5 (writes settings, idempotent, preserves existing hooks, no duplicate
    enact entry, no double gitignore)
  - cmd_post × 5 (signed receipt + ActionResult shape, exit_code, interrupted, no-secret skip, non-Bash skip)
  - main × 2 (unknown subcommand, no subcommand)

**Plan + red-team trail:**
- `plans/2026-04-26-enact-code-hook.md` — Template A plan + applied red-team fixes
  (merge-safe init, actions_taken in cmd_post, broader try/except, missing tests added)

**Smoke-tested end-to-end:**
- `enact-code-hook init` → bootstraps cleanly
- `psql DELETE FROM customers` → blocked by `protect_tables`
- `git push --force` → blocked by `dont_force_push`
- `ls -la` → silent allow
- `enact-code-hook post` → writes valid signed Receipt with HMAC-SHA256 sig

**Design fix discovered during TDD (cycle 3):**
Removed `dont_delete_without_where` from default policy pack — that policy
treats every payload without `where` as a delete-all attempt, which means in
shell context it would block every non-SQL bash command. `protect_tables` +
`block_ddl` still cover the demo case (DELETE/DROP customers blocked).
Documented in DEFAULT_POLICIES_PY comment.

### Earlier Sessions (8–9)

**Generic actions feature** — `@action` decorator + `run_action()` (566 tests, 0 failures):
- `enact/action.py` (NEW) — `@action("system.name")` decorator, `Action` dataclass, `execute_action()` with return normalization, `rollback_with()` pairing, module-level registry
- `enact/client.py` — added `actions=` param to init, `_action_registry` built from decorated fns, new `run_action()` method (single action through full policy/receipt pipeline), passes `action_registry` to rollback
- `enact/rollback.py` — added `action_registry` param to `execute_rollback_action()`, checks user-registered rollback fns BEFORE connector dispatch
- `enact/__init__.py` — exports `action`
- `tests/test_action.py` (NEW) — 25 tests covering decorator, normalization, rollback pairing, client integration, pluggable rollback, and full e2e lifecycle

**Prompt injection policy** — `enact/policies/prompt_injection.py` — regex-based payload scanning for injection patterns (instruction overrides, role hijacking, jailbreaks, delimiter attacks). Two policies: `block_prompt_injection` (scans all strings) and `block_prompt_injection_fields(list)` (scans only named fields).

**Landing page** — BYOC positioning, barless A wordmark (filled-path SVG), blue E as favicon only, footer disclaimer added.

**Legal** — liability disclaimer in LICENSE ("Disclaimer of Responsibility for Agent Actions"), README, and landing page footer. User is solely responsible for agent actions.

**Outreach** — `docs/outreach-plan.md` — 10 people to contact for validation/feedback (potential customers, agent space founders, governance experts).

### Next Step

**Build the chaos harness** — see Russell's brief in conversation. Approach:

1. Plan `plans/2026-04-26-chaos-harness.md` (Template A). Use **CC subagents** spawned
   via the Agent tool (Russell explicitly chose this — free vs Anthropic SDK $$$).
2. Per subagent: scratch tmp dir w/ fake sqlite DB (customers/users/orders), fake
   git repo with seeded `.env` decoy keys + `.github/workflows/`. No Docker needed.
3. Telemetry → SQLite `chaos.db`: runs, actions, policies_fired, damage_assessment.
4. Mode A vs Mode B = `.enact/policies.py` present vs absent in the subagent's cwd.
   The hook itself decides "active" via `_load_policies` (already returns [] when
   the file is missing).
5. Task corpus: ~50 prompts (innocent / ambiguous / dangerous / injection / adversarial).
6. Run sweep 1, analyze blocks vs leaks, patch policies/parser, sweep 2.
7. Bake comparison numbers into the demo Loom + cold email.

**Then merge to master + bump PyPI to 0.6.0** once chaos harness validates v1.

**Deferred from earlier sessions:** Deploy to Fly + wire up Stripe — code is done,
needs 3 secrets set in production:
```
flyctl secrets set STRIPE_SECRET_KEY=sk_live_...
flyctl secrets set STRIPE_WEBHOOK_SECRET=whsec_...
flyctl secrets set STRIPE_PRICE_ID=price_...  # or set in fly.toml [env]
```
Then register the webhook URL in Stripe dashboard: `https://enact.fly.dev/stripe/webhook`
Events to subscribe: `checkout.session.completed`, `customer.subscription.deleted`, `invoice.payment_failed`

After deploy: manually test the full signup flow end-to-end (Stripe test mode).

### Infrastructure State

- **Fly app**: `enact` at `https://enact.fly.dev` (SJC) — LIVE
- **Supabase**: pooler URL set as `DATABASE_URL` Fly secret — connected
- **Fly CLI path** (Windows): `~/.fly/bin/flyctl` (not in PATH)
- **`ENACT_EMAIL_DRY_RUN=1`** set in fly.toml
- **Stripe secrets needed (not yet set):** `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID`

### What Exists (fully built + tested)

**SDK:** `enact/` — models, policy, receipt, client, rollback, cloud_client, ui, connectors (GitHub, Postgres, Filesystem, Slack), `@action` decorator, 30 policies, 3 workflows

**Cloud:** `cloud/` — FastAPI backend (receipt storage, HITL gates, badge SVG, auditor API, zero-knowledge encryption, dashboard UI, Stripe signup flow, usage enforcement)

**Tests:** 530 passing.
