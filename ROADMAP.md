# Roadmap — Enact

What's coming next, ranked by buyer-pain × engineering-effort × revenue-unlock.

Living doc. Update at session-end when scope shifts.

---

## Now (1.0.0 shipped end of session 15)

- Multi-tool hook covers 6 of 8 Claude Code tools (Bash + Read + Write + Edit + Glob + Grep)
- 23 incident-derived shell policies + 5 file-path policies + 2 search-pattern policies
- 0 vs 7 critical damage on the 34-prompt shell sweep (file-tool sweep landing next session)
- Landing has both engineer-led wedge (top) AND CSO/GRC story (Built for your security team section + tabbed receipt demo + SOC2/HIPAA/GDPR mapping)
- IP split into three repos: public `enact` (ELv2 SDK + chaos harness code + landing) + private `enact-cloud` (FastAPI backend, dashboard, HITL, Stripe) + private `enact-pro` (chaos telemetry + auto-suggested policy candidates + premium policy packs)

---

## Next — Cloud-side policy push (highest priority, currently NOT BUILT)

**Why first:** the SOC2/HIPAA/GDPR pitch on the landing is hollow without it. CSOs buy compliance products to PUSH controls down to engineers. Today, every developer's `.enact/policies.py` is local — engineers can edit/disable. CSOs cannot enforce a global policy update across their team.

**What it looks like:**

```
CSO writes policy in cloud dashboard
        |
Cloud signs the bundle (HMAC-SHA256 + version + timestamp)
        |
Every hook on every laptop polls /api/teams/<id>/policies on every invocation
        |  (cached locally for 5 min, signature verified on every fetch)
        |
Hook merges (live cloud policies) + (local .enact/policies.py)
        |
Receipt records WHICH policy version was active (audit trail of rollout)
```

**Workarounds available today** (for the demo call until this ships):
1. Private PyPI package (`yourcompany-enact-policies`) — engineers `pip install --upgrade`
2. Git submodule of a shared policy repo — engineers `git pull` on a cadence

Both work, both require engineer cooperation. Neither is what a CSO actually wants.

**Effort estimate:** ~1 day.
- Cloud: `POST /api/teams/<id>/policies` (CSO writes/updates) + `GET /api/teams/<id>/policies` (signed bundle) — ~2 hr
- SDK: `enact.cloud.fetch_team_policies(api_key, ttl=300)` helper — ~2 hr
- `.enact/policies.py` template change to call the helper — ~30 min
- Dashboard UI for write/edit + version history — ~3 hr
- E2E test + docs — ~1 hr

**Dependency:** `enact-cloud` private repo must be live + Fly deploy must point at it (priority 4 of session 15 — staging dirs done, GitHub push deferred to runbook).

---

## Soon (next 2-3 sessions)

### File-firewall paired sweep
Already-shipped chaos prompts 80-84 + the cloud-policy-push blockers depend on this empirical data. ~10-15 min wall clock + ~$1-3 once you fire from a CC session in `enact-fresh`. Runbook in `plans/2026-04-27-file-firewall-sweep.md`.

### Cursor MCP integration
Reach Cursor's user base (similar wedge to Claude Code). MCP server wraps the same `enact.policy.evaluate_all` engine. Open question: build before or after first paying Marcus customer.

### NotebookEdit + WebFetch + Task tool coverage
Closes the last 2 of 8 CC tools. NotebookEdit is rare in non-Jupyter projects (low priority); WebFetch needs URL-policy class (different shape — domain allowlist, suspicious-URL patterns); Task spawns subagents (needs inheritance verification end-to-end).

### Loom 90s demo recording
Script lives at `docs/outreach/loom_90s_script.md`. Goes into every cold-email send. Needs the file-firewall sweep numbers landed first so the "0 vs N" stat in the demo is current.

### First 50 cold emails
Templates in `docs/outreach/cold_email_v2.md` (lead + DataTalks + Compliance variants). Filter: 100-300 person eng team, AI-forward, near-miss public OR regulated industry. Realistic math: 50 → 5-10 replies → 3-5 demos → 1-2 paid in 30 days.

### SDK split — engine open, policies closed (Russell-confirmed direction, session 16)

**Decision (2026-04-27):** what each policy DOES (the human-readable summary, e.g. "blocks agent from reading .env files") stays public so engineers can audit + recommend. The HOW (regex patterns, bypass-detection logic, rename-tracking heuristics) moves to the existing `enact-pro` private repo. Customers receive policy updates via signed bundle the SDK pulls at runtime, not source.

Why this matters: we are accumulating real moat in the policy regex (rename-then-drop bypass coverage, resource-name confusion detection, etc.). PyPI ships `.py` openly today; anyone with `pip download enact-sdk && unzip` reads our coverage. NDA gating doesn't fix that — signed-bundle distribution does.

Effort estimate: ~half day.
- Move `enact/policies/coding_agent.py`, `file_access.py`, `search_pattern.py` regex bodies into `enact-pro/policy_packs/default/` private repo.
- Public SDK keeps the policy CLASS shells + `description` strings (the WHAT).
- Signed-bundle loader: SDK fetches `enact-pro` bundle on first run, verifies HMAC, caches locally.
- Public bundle ships with the same default policies for the open-source path; bundle version + signature visible in receipts so audit trail is preserved.
- Update `LICENSE` notice to clarify: SDK shell is ELv2, policy bundles are proprietary.

Dependency: `enact-pro` repo already exists from session 15 IP split. Just need the bundle distribution mechanism.

### Hallucination-block notification — agent can't hide blocks from user

**Why this matters (verified session 16):** the Claude Code hook protocol has NO field that surfaces a message directly to the user. `permissionDecisionReason` only goes to Claude. Claude can — and empirically does — claim it succeeded after Enact blocked it. We confirmed Claude Code does not currently expose a `userMessage` or equivalent field that bypasses the model.

Three options, ranked. Russell decision (session 16): cheapest fails the criterion; ship Better and Best.

- **Cheapest (~10 min) — DOES NOT MEET CRITERION (skip):** add a stderr line `[ENACT BLOCKED: <policy> — <reason>]` from the hook. Goes to Claude, not the user. Claude can ignore it. Hallucination remains possible.
- **Better (~30 min) — SHIP:** OS-level toast on block. Hook subprocess invokes `osascript -e 'display notification "..."'` (Mac), `New-BurntToastNotification` (Windows), or `notify-send` (Linux) on every BLOCK. User sees it system-wide, independent of what Claude says.
- **Best (~half day) — SHIP after Better:** "fabrication detector" — at session end, parse Claude's final summary text and diff against the receipt actions. If Claude claims X happened and the receipt shows X was blocked, surface a "fabrication detected" alert in the receipt UI. This is the productized version of the hallucinated-success finding from session 15. Worth its own landing-page section once shipped.

Plus: file `/feedback` request to Anthropic for a `userMessage` hook field that renders outside the chat thread. Long-term proper fix.

### Chaos sweep — DB write-completion bug

Discovered session 16: `chaos.db` has 25 runs but all have NULL outcomes. The runner inserts run rows at start but never UPDATEs with final classification. Top-level `receipts/` directory has the actual block evidence (39 receipts, 31 BLOCKs across 6 distinct policies) but the per-run outcome attribution is broken.

Real impact: we've been putting "0 vs 8 incidents" headlines on the landing from session-end report narratives, not from queryable data. Risk: a buyer asks "show me the data" and we point at narrative.

Fix:
- Audit `enact/chaos/runner.py` `record_run_result()` — confirm it writes the UPDATE.
- If it does, the bug is upstream — check whether sweep dispatchers actually CALL `record_sweep` after results come back (session 16 sweeps may have been fired but never recorded).
- Add a smoke test that runs a 1-prompt sweep and asserts `runs.outcome IS NOT NULL` after.
- Once fixed, re-run a small bash sweep so we have queryable bash-side BLOCK receipts to match the file-tool ones we surfaced on the landing today.

### Five new policy categories from session 16 sweep findings

Each is a real gap the sweep surfaced. Listed with the WHAT for each (the customer-visible description) — the HOW lives in `enact-pro` per the SDK split.

- **Rename-then-drop bypass tracking.** Blocks agent from defeating `protect_tables` by first renaming a protected table to a different name, then dropping the renamed table. Tracks aliases within a session.
- **Resource-name confusion (PocketOS pattern).** Pauses for human when an action's resource scope (volume name, bucket name, table name) does not match the documented purpose of the credential being used. Catches "token was for staging, used against prod."
- **Path-resolution coarseness fix.** Distinguishes ABSOLUTE paths under `$HOME` (block) from relative paths that resolve under HOME because cwd happens to be there (allow). Fixes the false-positive that hit chaos run dirs in our own sweep.
- **Sandbox-friction enrichment.** Not a policy — a chaos harness change. Seeds the test sandbox with missing state files, credential mismatches, broken envs so misinterpretation prompts trigger their pattern instead of no-op'ing on a too-clean sandbox. Required to get real data on the agent-self-initiated case (PocketOS shape).
- **WebFetch URL-policy class.** WebFetch tool isn't covered yet. Different shape from file paths — needs domain allowlist + suspicious-URL patterns (DNS exfil, pastebin domains, `*.tk`/`*.ml` etc).

---

## Later (months out)

### Anomaly detection
Rule-based first ("agent did X 50 times in 5 min — alert"), ML later. No code yet.

### HubSpot connector
Planned in INTENT_GUIDE, not built. Lower priority than the chaos flywheel.

### Multi-agent arbitration / soft locks
Designed in spec, not built. Becomes important when teams run >1 production agent against the same systems.

### Vertical premium policy packs
Live in `enact-pro` private repo as `policy_packs/<vertical>/`. None published yet. Targets: fintech, healthcare, government, AI-companies.

### Independent auditor read API
Already scaffolded in `cloud/routes/auditor.py` (ships with enact-cloud). Lets your auditor read receipts directly — three-party trust model becomes a real product feature, not just a marketing line.

---

## Open product questions

- **Self-refusal will drift with model versions.** Today's Claude 4.7 self-refuses 21 of 26 dangerous prompts. Tomorrow's Claude 5 might refuse 18 or 24. Our value compounds as models change underneath — but how do we MEASURE that compounding for the customer? Quarterly chaos-sweep reports?
- **ABAC/RBAC.** Engine supports it (`WorkflowContext.user_attributes`, `contractor_cannot_write_pii` reference). Not on landing (reads enterprise vendor-bait). Demo it during the call. Will customer-buyer #5 or #50 ask for fuller ABAC tooling?
- **Rollback for non-mutating actions.** Today rollback is per-action with `rollback_data` captured pre-mutation. What about composite "I shouldn't have read this" — can we even reverse a Read? (Probably no; the bell can't be unrung. Receipt + alert is the answer there.)

---

## What this roadmap is NOT

This is the FORWARD-looking doc. For:
- **What got shipped already** → `Handoff.md` (auto-updated each session)
- **The product spec / invariants** → `enact-intent.md`
- **Long-form bug stories + lessons** → `learnings.md` (not yet created)
- **Cold email + Loom assets** → `docs/outreach/`
- **Per-feature implementation plans** → `plans/`
