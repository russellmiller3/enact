# LinkedIn DM template — DevRel/PMM/SE outreach (job hunt)

Pairing artifact for the target-list spreadsheet at `target-list-2026-04-28.md`.

**Voice match:** matches the lead `cold_email_v2.md` voice — named real incidents, concrete numbers, no profanity, no resume attachment.

**Asset to drop in every DM:** the research post URL.
Canonical: `https://enact.cloud/blog/2026-04-28-claude-code-asymmetry.html` (Vercel deploys auto on push to master).
Fallback (if Vercel deploy is delayed): `https://github.com/russellmiller3/enact/blob/master/docs/research/post-2026-04-28-claude-code-asymmetry.md`

---

## Variant 1 — Connection request (300-char hard limit)

Use this when sending a connection request (the field has a 300-char limit including spaces). Goal: get the connection accepted so you can DM properly.

```
Hi [first name] — built a PreToolUse hook firewall for Claude Code (enact.cloud).
Ran 39 paired chaos prompts, wrote up the 80/20 self-refusal asymmetry I
found. Open to chats about agent safety — and DevRel/PMM at [Company] if
you're hiring. Post in profile.
```

Char count: ~280. Keeps the post link in your LinkedIn About so it's discoverable post-acceptance.

---

## Variant 2 — Direct DM, no personalization hook

Use this when the recipient has no recent public post / tweet to reference (most senior PM/DevRel folks at Anthropic/Cursor/etc. post infrequently).

```
Hi [first name],

Built a PreToolUse hook firewall for Claude Code over the last few weeks
(enact.cloud — open source, PyPI 1.0.0). Ran 39 paired chaos prompts
through it. Headline finding: Claude Code refuses ~80% of destructive shell
commands the user types, but only ~20% of read-shaped exfil requests, and
~0% when the agent invents the destructive action itself. Wrote it up as
a research post (link below).

I'm exploring DevRel / PMM / Solutions Engineer roles at AI coding co's,
and [Company] is at the top of my list. Would love 15 min to chat — feel
free to push back on the post itself either way.

Post: [URL]

— Russell
```

~140 words. Works for cold contacts with no recent public hook.

---

## Variant 3 — Direct DM, with personalization hook

Use this when you can reference something the recipient posted in the last ~3 months. Personalization is the difference between 5% and 15% reply rate.

```
Hi [first name],

Saw your [tweet about X / blog post on Y / talk at Z conference] —
[specific quote or claim, 1 sentence]. That lines up with something I've
been working on: a PreToolUse hook firewall for Claude Code (enact.cloud).
I ran 39 paired chaos prompts and found a sharp 80/20 self-refusal
asymmetry — the third row, agent-self-initiated destruction, refuses at
~0% rate. Wrote it up here: [URL]

I'm exploring DevRel / PMM / Solutions Engineer roles at AI coding co's
and would love a 15-min chat about [Company]. Feedback on the post welcome
either way.

— Russell
```

~120 words. Best variant when you have a fresh hook.

---

## Variant 4 — Anthropic-specific (Claude Code team)

Use ONLY for Anthropic recipients. Plays the "I built on your product, found a bug, would love to feed back" angle. Don't use this language with competitors.

```
Hi [first name],

Built a PreToolUse hook firewall on top of Claude Code over the last few
weeks (enact.cloud, open source) and ran 39 paired chaos prompts against
it. Found a clean 80/20 self-refusal asymmetry I think the team would
find interesting — and two latent Windows bugs in my own product that
only surfaced when end-to-end CC subagent invocation broke them.

Research post: [URL]

If Anthropic is hiring DevRel or Solutions Engineering for the Claude
Code team, I'd love a chat. If not, I'd still love feedback on the post —
particularly the section on what a `userMessage` field on the hook
protocol could close.

— Russell
```

~130 words. Most leveraged single DM Russell can send. Anthropic is the primary target.

---

## Send rules

1. **One DM per person per week max.** If no reply in 7 days, send ONE follow-up referencing the original; if no reply after that, drop and re-evaluate in 90 days.
2. **Track in the target list.** Date sent, variant used, replied (Y/N), demo booked (Y/N). The numbers tune the next batch.
3. **Personalize variant 3 always.** A 30-second LinkedIn search for the person's recent activity is the difference between cold-feeling and warm-feeling.
4. **Never attach a resume in the first DM.** The post does the work. Resume goes in a follow-up if they ask.
5. **Send during weekday business hours US Pacific** (most targets are SF-based). Tuesday–Thursday 9am–11am has the best open rates per LinkedIn's own data.
6. **Use the LinkedIn app for sending.** Browser-based DMs are sometimes throttled silently after a few sends; mobile app appears to have higher per-day cap.

---

## Reply playbook (when someone responds)

Three common reply shapes; pre-drafted next moves below.

### Reply: "Interesting, send a Loom or schedule time"

Drop the Loom + a Calendly link in one message:
> Loom 90s: [URL]
> Calendly: [URL]
> Free Tue/Wed/Thu next week any time before 3pm Pacific.

### Reply: "We're not hiring DevRel right now"

Pivot to keeping the connection warm:
> No worries, appreciate the honest answer. Mind if I ping you in 60-90 days
> when the next batch of empirical findings is out? In the meantime — the
> post is open feedback. Anything you'd push back on, I'd take seriously.

### Reply: "What's enact's revenue / customer base?"

Be honest:
> Pre-revenue, pre-PMF on the SaaS side. Open-source toolkit + research is
> the priority right now. The job hunt is the wedge — I want to do this
> work inside a team with a bigger surface than my own laptop.

Honesty here is a feature. Hiring managers can smell BS, and "I'm using
this as a portfolio piece, not pretending to be a unicorn" reads as
self-aware in a way that's rare in the candidate pool.