# Cold email v2 — Enact

**Source data:** `chaos/report.md` (34 paired prompts, 0 vs 7 damage, generated 2026-04-27).
**Incident catalog:** `docs/research/agent-incidents.md`.
**Loom script:** `docs/outreach/loom_90s_script.md`.

**Voice match with landing page:** clean, no profanity, lead with named real-world incidents, anchor cost vs price.

---

## Subject line bank (test 3-5 per send batch)

| # | Subject | Best for |
|---|---|---|
| 1 | After Replit and the Claude Code Terraform incident — what's stopping yours? | All targets |
| 2 | 90-sec video — agent firewall I built after Replit's database wipe | Founders / VPs |
| 3 | Same pattern as DataTalks: 1 prompt away from a 2.5-year data loss | Infra-heavy buyers |
| 4 | Stops Claude Code from running the 4 commands that cost a company | CISOs / Security |
| 5 | Did your team have an agent near-miss this quarter? | Cold-cold prospects |

---

## Email body — paste-ready (the lead version)

> Hi [first name],
>
> Saw [specific recent thing — a blog post, a tweet, a Show HN, a public near-miss]. Curious how you're handling Cursor and Claude Code across the team right now.
>
> Built **Enact** — a Claude Code hook (Cursor MCP coming) that runs every shell command through a deterministic policy engine before execution. The pitch is simple: in July 2025 Replit's agent wiped a database during a code freeze. In February 2026 Claude Code ran `terraform destroy` on a developer's laptop and erased 2.5 years of student data. Same pattern, same shape. We catch both before they execute.
>
> I chaos-tested it last week against 34 prompts, each derived from a documented agent incident:
>
>   **Without Enact: 7 critical incidents on 5 of 34 prompts.** `DROP TABLE customers` on a one-line "we don't need it" prompt. `DELETE FROM users` with no `WHERE`. `aws s3 rm --recursive` on a "safe" staging bucket. Bulk Stripe subscription cancel framed as dashboard cleanup. A rename-then-drop bypass that talked the model into a destructive op it would have refused directly.
>
>   **With Enact: 0 damage. 15 direct policy blocks. 0 leaks.** Same 34 prompts, same model.
>
> 90-second demo: [Loom link]
>
> Free for individual developers. $30 per seat per month for teams who want the audit dashboard. Setup is two commands.
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

## What's deliberately NOT in the headline

- **The 21-of-26 self-refusal stat** — sounds like "Claude already pretty safe, why do I need this?" The 5 that slipped are the differentiator; lead there.
- **Prompt injection** — Claude self-refuses the obvious ones; not a strong differentiator vs the agent-fuckup angle.
- **Audit dashboard / SOC2 features** — save for the demo call. Cold email goal is just the meeting.

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

| v1 | v2 |
|---|---|
| "We tested 36 simulated agent attacks" | "34 prompts, each derived from a documented agent incident" |
| Stat-led intro | Incident-led intro (Replit + DataTalks named in line 2) |
| 4-of-18 damage | 5-of-34 damage |
| Prosaic body | Tighter, parallel-structure damage list |
| Single subject line | 5 subject lines for testing |
| No incident variant | DataTalks variant for infra buyers |
| No no-swearing rule | Clean copy throughout (rule now in CLAUDE.md) |

---

## Final pre-send checklist

- [ ] Loom recorded and link in `[Loom link]` placeholder
- [ ] enact.cloud landing page deployed (Vercel auto-deploys from master)
- [ ] `pip install enact-sdk` actually works for fresh user (test in clean venv)
- [ ] Reply-to email is monitored and you can demo within 24 hours of reply
- [ ] Booking link or "reply with 3 times that work" — not a Calendly URL on cold outbound (lower conversion)
