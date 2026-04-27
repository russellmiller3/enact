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
