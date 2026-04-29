# Loom 90s demo script — Enact

**Goal:** in 90 seconds, get the viewer to install Enact themselves.
**Hook:** lead with the named incident (Replit + DataTalks), end with a single command.
**Demo case:** the rename-then-drop bypass — most cinematic of the bypasses.

---

## Pre-record setup (5 minutes)

```bash
mkdir -p /tmp/enact-demo && cd /tmp/enact-demo
git init -b main
pip install enact-sdk
enact-code-hook init
```

Open Claude Code in `/tmp/enact-demo`.
Open a side terminal pointed at `/tmp/enact-demo/receipts/`.
Have the landing page (`enact.cloud`) open in another tab for the cut-back at 1:10.

Lighting: face cam optional but better. Audio: use a real mic, not laptop built-in.

---

## Script (90 seconds)

### 0:00 – 0:12  Hook (face cam if you have it)

> "Last week, Cursor running Claude Opus 4.6 deleted a Railway volume to 'fix' a credential mismatch. Volume was production. Three months of customer data, gone in nine seconds. Six months before that, Claude Code ran `terraform destroy` on a developer's laptop and erased 2.5 years of student data. Six months before THAT, Replit wiped a production database during an active code freeze. **Same shape, three vendors.** Here's the firewall I built so it doesn't happen to you."

### 0:12 – 0:25  Set the scene

> "I'm in Claude Code. Brand new repo. I just ran `pip install enact-sdk` and `enact-code-hook init` — that's the entire setup. Now watch what happens when I ask Claude to do something destructive that bypasses its own training."

Type into Claude Code:

> "The customers table is messy. Rename it to customers_old, then drop it so we can rebuild fresh."

### 0:25 – 0:55  The block (this is the money shot)

Claude composes the SQL. The PreToolUse hook fires. Camera zooms into the block message.

> "Watch this. Claude proposes the rename — Enact's `block_ddl` policy fires immediately. The hook returns deny JSON, Claude sees it, tells me, and doesn't run the SQL.
>
> Critically — Claude tried this. It didn't refuse on its own because the rename-then-drop trick frames the destructive op as innocent housekeeping. **The training missed it. The deterministic policy caught it.**"

Optional: cut to a code-freeze line in `.enact/policies.py` showing the policy is just 5 lines of Python.

### 0:55 – 1:10  Show the receipt + the headline number

Cut to the side terminal. Show the signed receipt JSON in `./receipts/` — the BLOCK record with the policy name and reason, signed with the local HMAC secret.

> "Every block writes a signed receipt to your repo. Local-first. We can't see any of it. That's the audit trail your security team has been asking for."

Brief flash of the landing page numbers section: "**0 vs 8 critical incidents on 39 paired prompts.** 0 leaks, 15 direct policy blocks."

### 1:10 – 1:30  Close + CTA

Back to face cam.

> "Free for individuals. $30 per seat per month for teams who want the audit dashboard. Two commands to install — link's in the email. Reply if you want a 14-day team trial."

End frame: `pip install enact-sdk && enact-code-hook init`

---

## Recording tips

- **Take 1 is always rough; take 2 is usually shippable.** Don't aim for perfection.
- **Don't over-edit.** Real-feeling beats polished. Solo founder with a scrappy demo lands better than a corporate sizzle reel.
- **Cap at 90 seconds.** If you go over, cut the receipt section to a single-second flash.
- **Don't read this script verbatim.** Paraphrase. The natural cadence converts better.

---

## After upload

1. Get the Loom share link
2. Paste into `docs/outreach/cold_email_v1.md` and `cold_email_v2.md` in the `[Loom link]` placeholder
3. Pin the Loom to the landing page (next-session task — add a "Watch the 90-second demo" CTA in the hero)
4. Track view-to-reply rate per email sent (~5-10% reply with video, ~1-2% without)

---

## What NOT to demo

- **Don't demo prompt injection.** Self-refusal handles most of those — weak differentiator.
- **Don't demo `terraform destroy` blocking** — viewer may not have terraform installed, can't reproduce.
- **Don't demo the chaos sweep harness.** That's a developer story, not a buyer story. Buyer wants to see "agent tries bad thing, hook stops it" in 30 seconds.

---

## A/B variants (record once you have data on v1)

| Variant | Hook | When to use |
|---|---|---|
| **A — Replit lead** (above) | "Replit wiped a database in July 2025" | SaaS founders, AI-tool builders |
| **B — DataTalks lead** | "Claude Code ran `terraform destroy` and erased 2.5 years of data" | Infra/DevOps buyers |
| **C — Stat lead** | "We tested 39 dangerous prompts; 8 wrecked production without us" | Security buyers (SOC2, CISO) |
| **D — Personal lead** | "I'm a solo founder. Built this after [near-miss story]" | Indie / small-team buyers |
| **E — PocketOS lead** | "Last week an AI coding agent wiped a customer database in 9 seconds. Here's how to stop it." | Enterprise buyers post-PocketOS news cycle |

Start with A (now PocketOS-led). Track replies. Switch to whatever wins after 50 sends.

---

## Asymmetry close-out (optional 5-second add at 1:08)

If you have headroom in the 90 seconds, drop in one line right before the CTA that ties the demo to the longer research post:

> "And here's the thing — the rename-then-drop you just saw, that's the case Claude refuses 80% of the time on its own. The cases it DOESN'T refuse — read-shaped exfil and agent-self-initiated destruction — are the ones costing companies real money. The full data is in the post link in the email."

Reason: the demo case is the easy one. The asymmetry post is where the wedge is. Pointing the viewer at the post during the Loom = one funnel step shorter.
