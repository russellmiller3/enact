# Roadmap — Enact

What's coming next, ranked by buyer-pain × engineering-effort × revenue-unlock.

Living doc. Update at session-end when scope shifts.

---

## Now (1.0.0 shipped end of session 15; expanded research + distribution end of session 17)

**SDK and engine:**
- Multi-tool hook covers 6 of 8 Claude Code tools (Bash + Read + Write + Edit + Glob + Grep)
- 23 incident-derived shell policies + 5 file-path policies + 2 search-pattern policies
- IP split into three repos: public `enact` (ELv2 SDK + chaos harness code + landing) + private `enact-cloud` (FastAPI backend, dashboard, HITL, Stripe) + private `enact-pro` (chaos telemetry + auto-suggested policy candidates + premium policy packs)

**Empirical:**
- 39 paired chaos prompts, 8 critical incidents without Enact, 0 with — across both shell and file-tool surfaces
- 80/20 self-refusal asymmetry surfaced: Claude Code refuses ~80% of user-typed destructive commands, ~20% of read-shaped exfil, ~0% of agent-self-initiated destruction (the PocketOS pattern). Deterministic gate fills the third row.
- Two latent Windows bugs found by the chaos harness and fixed (PATH + bash backslash mangling)

**Distribution and research (session 17):**
- Research post live at [enact.cloud/blog/2026-04-28-claude-code-asymmetry.html](https://enact.cloud/blog/2026-04-28-claude-code-asymmetry.html) (the long-form study) + [follow-up at /blog/2026-04-28-gitignore-block.html](https://enact.cloud/blog/2026-04-28-gitignore-block.html) (live evidence of the safety property)
- Landing-page research callout band linking to the post above the fold
- Cross-post variants prepped for HN, X, LinkedIn (in `docs/outreach/`)
- Target list of 10 hiring managers (5 TIER A all HIGH confidence)
- 8 pre-personalized DMs (5 Tier A + 3 Tier B) ready to fire
- HN-submission FAQ with 12 pre-drafted answers for the comment window

---

## Next — technical priorities (re-ranked end of session 17)

The cloud-side policy push (was #1) is now demoted to "when first paying customer materializes." It's a sales-driven build; without an active buyer pipeline, finishing it is speculative. The current technical priorities in order:

### 1. Cursor MCP integration

Closes the second-largest agent-coding surface. MCP server wraps the same `enact.policy.evaluate_all` engine. Reaches Cursor's user base directly. Effort: ~half day.

### 2. WebFetch URL policies (the last 2 of 8 CC tools)

WebFetch needs a URL-policy class — domain allowlist + suspicious-URL patterns (DNS exfil, pastebin, `*.tk`/`*.ml`). Different shape from file paths; new policy module. Effort: ~half day. Closes the engine's coverage of every CC tool except NotebookEdit (which is rare in non-Jupyter projects).

### 3. Fabrication detector

At session end, parse Claude's narrative against the receipt log; surface cases where Claude claimed it ran an action that the hook actually blocked. Real failure mode observed in the chaos sweep — agent told user "git reset --hard succeeded" after Enact denied it. Productizing this becomes a landing-page section once shipped. Effort: ~half day.

### 4. Cloud-side policy push (deferred — was #1)

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

### Loom 90s demo recording
Script lives at `docs/outreach/loom_90s_script.md` — refreshed end of session 17 with the new "39 paired prompts, 0 vs 8 incidents" headline + a PocketOS-led hook + an asymmetry close-out at 1:08. Needs Russell to record once.

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

### OS-level toast on block (companion to fabrication detector in "Next")

The fabrication-detector approach surfaces hallucinated-success at session end. A cheaper companion: OS-level toast on every BLOCK so the user sees it in real time, independent of what Claude says. `osascript -e 'display notification "..."'` (Mac), `New-BurntToastNotification` (Windows), `notify-send` (Linux). ~30 min.

Plus: file `/feedback` request to Anthropic for a `userMessage` hook field that renders outside the chat thread — the long-term proper fix referenced in the research post.

### Chaos sweep — DB write-completion bug (deferred)

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
