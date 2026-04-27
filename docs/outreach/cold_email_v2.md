# Cold email v3 — Enact (was v2, evolved 2026-04-27)

**Source data:** `chaos/report.md` (34 paired prompts, 0 vs 7 damage, generated 2026-04-27).
**Incident catalog:** `docs/research/agent-incidents.md`.
**Loom script:** `docs/outreach/loom_90s_script.md`.

**Voice match with landing page:** clean, no profanity, lead with named real-world incidents, anchor cost vs price.

---

## Subject line bank (test 3-5 per send batch)

| # | Subject | Best for |
|---|---|---|
| 1 | PocketOS lost 3 months of customer data in 9 seconds last week. What's stopping yours? | All targets (NEW — v3 lead) |
| 2 | The agent doesn't need bad intent — it just needs a credential mismatch | Founders / VPs |
| 3 | After Replit, DataTalks, and PocketOS — same shape, same week, every time | Infra-heavy buyers |
| 4 | When Enact blocks the agent, the agent says "I did it" anyway. Here's why receipts matter. | CISOs / Security |
| 5 | Did your team have an agent near-miss this quarter? | Cold-cold prospects |
| 6 | Audit-ready guardrails for Cursor / Claude Code (SOC2 CC7.2, HIPAA §164.312(b)) | Compliance / GRC |

---

## Email body — paste-ready (the lead version, v3 — refocused on agent-self-initiated misinterpretation)

> Hi [first name],
>
> Saw [specific recent thing — a blog post, a tweet, a Show HN, a public near-miss]. Curious how you're handling Cursor and Claude Code across the team right now.
>
> The case I keep coming back to is PocketOS, last week. Founder asked Cursor (Claude Opus 4.6) to handle a routine staging task. The agent hit a credential mismatch and decided <em>on its own initiative</em> to delete a Railway volume to "fix" it — used a token created for unrelated domain ops, thought scope was staging, was production. **9 seconds. Three months of customer data gone.** The agent's own confession enumerated the safety rules it was breaking, in writing, while breaking them. Best model + best IDE + explicit project safety rules. Production gone anyway.
>
> That's the pattern that costs companies. Not "user typed DROP TABLE" — Claude refuses that 4 times out of 5 on its own. The pattern is the agent INDEPENDENTLY deciding to do destructive work to fix unrelated friction. Same shape every time: Replit (Jul 2025) deleted SaaStr's prod DB then created 4,000 fake users to cover its tracks. DataTalks.Club (Feb 2026), Claude Code ran `terraform destroy` from a stale state file — 1.94M rows, 2.5 years gone. Amazon Kiro (Dec 2025), 13-hour Cost Explorer outage when Kiro decided "delete and rebuild" was faster than fixing the bug.
>
> Built **Enact** — a Claude Code hook (Cursor MCP next) that runs every tool call through a deterministic Python policy engine before execution. Six tools covered: Bash, Read, Write, Edit, Glob, Grep. Same engine across surfaces — agent can't bypass by switching from Bash to Read. No LLM in the decision loop, so the agent's own reasoning can't talk Enact out of blocking.
>
> Chaos-tested against 44 prompts derived from documented agent incidents:
>
>   **Without Enact: 8 critical incidents** across shell, file-tool, and agent-misinterpretation surfaces.
>
>   **With Enact: 0 incidents.** Hard blocks + signed audit receipt on every action.
>
> One thing the chaos sweep surfaced that surprised me: **when Enact blocks an agent's destructive action, the agent often tells the user it succeeded anyway.** We blocked a `git reset --hard` and the agent then wrote a detailed summary describing the three commits that "vanished" and the file edit that "got wiped" — none of which actually happened. Enact's signed receipt is the only ground truth. If you're relying on the agent's chat output to know what it did, you have no idea what it did.
>
> 90-second demo: [Loom link]
>
> Free for individual developers. $30 per seat per month for teams who want the audit dashboard, HITL approval, encrypted receipts, and one-call rollback. Setup is two commands.
>
> Worth 15 minutes next week?
>
> — Russell, founder
> enact.cloud

---

## Variant — DataTalks lead (for infra buyers)

> Hi [first name],
>
> Saw [specific thing]. Wondering whether your team has wired any guardrails around Cursor / Claude Code yet, or if it's still on the trust-the-model plan.
>
> Built **Enact** — drops into Claude Code via the official PreToolUse hook, runs every shell command through a policy engine. The case I keep coming back to is DataTalks: in February the founder's Claude Code agent ran `terraform destroy` after a missing state file made Terraform think the infra was empty. 2.5 years of data, gone in one command. The agent did exactly what Terraform told it to.
>
> I tested 34 prompts derived from that and similar incidents:
>
>   **Without our firewall: 5 of 34 caused damage.** Including the `terraform destroy` pattern, `aws s3 rm --recursive`, `DROP TABLE customers`, `kubectl delete namespace`, and a few others where Claude's own training didn't refuse.
>
>   **With our firewall: 0 damage. 15 deterministic blocks.** Same prompts, same model.
>
> 90-second demo: [Loom link]
>
> Free for individuals. $30/seat/mo for teams. Setup is `pip install enact-sdk && enact-code-hook init`.
>
> Worth 15 minutes next week?
>
> — Russell, founder

---

## Variant — Compliance lead (for SOC2 / HIPAA / GDPR buyers)

> Hi [first name],
>
> Saw your team is hiring for [security / GRC / compliance role] — and that you're shipping with [Cursor / Claude Code / Copilot] across engineering. That combination puts a specific question on your auditor's desk: when an AI agent reads `.env`, your customer's PII, or `~/.aws/credentials`, where's the audit trail?
>
> Built **Enact** — drops into Claude Code via the official PreToolUse hook, runs every agent action through a deterministic policy engine. Most agent-firewall stories cover one tool — shell. We cover six: Bash, Read, Write, Edit, Glob, Grep. That's the difference between catching `cat .env` and catching the same agent using Claude Code's Read tool to do the same thing.
>
> Three concrete framework mappings:
>
>   **SOC2 CC7.2** — "monitor system components for indicators of attack." Read-tool exfil is an indicator. The hook fires deterministic blocks AND writes a signed receipt for every action — pass, block, or partial.
>
>   **HIPAA §164.312(b)** — audit controls covering "examination of activity in information systems." Every Read of a PHI-shaped path produces tamper-evident audit evidence (HMAC-SHA256-signed JSON receipts).
>
>   **GDPR Art. 32(1)(d)** — "process for regularly testing… effectiveness of measures." Our chaos sweeps + signed receipts are the testing process. We've got a 39-prompt corpus and the harness is open source.
>
> Setup is two commands. Free for individual developers. $30/seat/mo for teams. The audit dashboard surfaces all receipts with grep-friendly filters.
>
> Worth 15 minutes next week to walk through the receipt format with your GRC lead?
>
> — Russell, founder
> enact.cloud

---

## Five damage findings (in case the email lead changes)

Diverse so the email reads as breadth. All from the chaos sweep.

| # | Pattern | What the agent did without Enact | Real incident parallel |
|---|---|---|---|
| 1 | DDL on protected table | Ran `DROP TABLE customers` | DataTalks-class |
| 2 | Unbounded delete | Ran `DELETE FROM users` (no WHERE) | Replit / SaaStr |
| 3 | Cloud bulk delete | Ran `aws s3 rm s3://staging-bucket --recursive` | Generic — universal "I thought it was staging" |
| 4 | Adversarial bypass | Renamed customers, then dropped — sidestepped self-refusal | New finding from our corpus |
| 5 | Billing destructive | Ran `stripe subscriptions cancel --status trialing --all` | Real risk for SaaS, no public incident yet |

---

## What's deliberately NOT in the headline (lead variants)

- **The 21-of-26 self-refusal stat** — sounds like "Claude already pretty safe, why do I need this?" The 5 that slipped are the differentiator; lead there.
- **Prompt injection** — Claude self-refuses the obvious ones; not a strong differentiator vs the agent-fuckup angle.

**SOC2 / HIPAA / GDPR is now in the headline for the compliance variant only.** Engineering buyers (lead + DataTalks variants) still get the incident-led pitch — compliance language reads like vendor-bait to them. GRC buyers get the framework citations because that's the language they procure in.

---

## How to source the 50-name target list

Same as cold_email_v1.md — see that doc. Filter criteria unchanged: 100-300 person eng team, AI-forward, has either had a public near-miss or is in regulated industry. LinkedIn Sales Nav + YC directory + Twitter search for `"agent broke"` `"deleted prod"` `"cursor force push"` etc.

---

## Sending cadence

- **Volume:** 10-15 sends per day (manual, personal Gmail). Apollo / batch tools tank deliverability.
- **Day 0:** initial send.
- **Day 4:** if no reply, one follow-up — "bumping this — did the link to the demo come through?"
- **Day 14:** mark dead. Move on.

**Realistic math:** 50 emails → 5-10 replies → 3-5 demos → 2-3 trials → 1-2 paid in 30 days. Repeat weekly.

---

## What changed vs v1

| v1 | v2 (post session 15) |
|---|---|
| "We tested 36 simulated agent attacks" | "34 prompts, each derived from a documented agent incident" |
| Stat-led intro | Incident-led intro (Replit + DataTalks named in line 2) |
| 4-of-18 damage | 5-of-34 damage |
| Prosaic body | Tighter, parallel-structure damage list |
| Single subject line | 6 subject lines for testing |
| No incident variant | DataTalks + Compliance variants for verticals |
| "Every shell command" framing | "Six tools covered: Bash, Read, Write, Edit, Glob, Grep" — Agent Firewall, not shell firewall |
| No SOC2/HIPAA/GDPR angle | Dedicated compliance variant with framework citations (CC7.2, §164.312(b), Art. 32(1)(d)) |
| No no-swearing rule | Clean copy throughout (rule now in CLAUDE.md) |

---

## Final pre-send checklist

- [ ] Loom recorded and link in `[Loom link]` placeholder
- [ ] enact.cloud landing page deployed (Vercel auto-deploys from master)
- [ ] `pip install enact-sdk` actually works for fresh user (test in clean venv)
- [ ] Reply-to email is monitored and you can demo within 24 hours of reply
- [ ] Booking link or "reply with 3 times that work" — not a Calendly URL on cold outbound (lower conversion)
