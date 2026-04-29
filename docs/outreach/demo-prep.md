# Demo prep — DevRel/PMM/SE interview & demo runbook

For when a Tier A or Tier B target replies with "send a Loom" or "let's chat next week." This is the playbook from "DM accepted" → "interview booked" → "offer."

**Three demo loop stages:**
1. **Async (Loom + 1-pager)** — they reply, you send, they decide whether to book live
2. **Live demo (15-30 min)** — first call, mostly listening, ends with a clear "what would I work on first 30 days?"
3. **Take-home or panel** — the company-specific test of fit; varies wildly across companies

Each stage has its own copy/templates. Russell prepares once; uses for every target.

---

## Stage 1 — Async (Loom + 1-pager) reply

### Trigger phrases from the target
- "Send me a Loom"
- "What would you build first?"
- "Got a deck?"
- "Walk me through the architecture"
- "Why's this different from [Cursor / Copilot / Continue / etc.]"

### Reply template (paste-ready)

```
Hi [first name],

Thanks for the reply — happy to send a Loom and a 1-pager.

Loom (90s, the live demo of a block firing): [LOOM URL]

1-pager (architecture + the 80/20 finding + how I work): https://enact.cloud/about.html

Calendar for a 15-min chat next week: [Calendly link]
Open: Tue/Wed/Thu, 10am–2pm Pacific.

If easier to async, happy to answer any specific question by reply.
Pushback on the post welcome too — I'd rather hear "actually X is wrong"
than nothing.

— Russell
```

### What's in the 1-pager (already built — `/about.html`)

The portfolio/about page at [enact.cloud/about.html](https://enact.cloud/about.html) doubles as the 1-pager:

- **Top:** Russell + role openness signal (DevRel / PMM / SE at AI coding co's)
- **Middle:** the 4-stat grid (39 prompts, 8→0 incidents, 545 tests, PyPI 1.0.0) + the asymmetry table (the 3-row trigger-type breakdown)
- **Artifacts row:** post + follow-up + repo + PyPI + landing
- **How I work:** AI-co-development is default, empirical-first, plain English, ship the boring decisions
- **Bottom:** project roadmap + contact

Same URL for every target — no per-recipient customization needed. Vercel auto-deploys on push so the page is always current with the latest research.

---

## Stage 2 — Live demo (15-30 min)

The 15-min chat is **80% you listening**, 20% you talking. Most candidates fail here by talking too much. The hiring manager wants to know: can you have a real conversation? Are you curious about their problem? Will you be pleasant to work with?

### Pre-call (15 min before)

- Re-skim their LinkedIn for last week's activity. Note 1-2 specific things to reference.
- Re-skim the company's last week of public output (blog, GitHub, Twitter). Note 1 specific shipment.
- Have ready: Loom link + 1-pager link + repo link + the post link. Don't fumble for them.
- Open: target list note + DM history with this person.

### The opening (90 seconds)

Don't open with "tell me about the role." Open with appreciation + the specific reason you reached out:

> "Hey [name], thanks for the time. Quick context: I sent the post because [specific recent thing they did]. Mainly here to ask questions — I have a hypothesis about what your team's biggest leverage point is, but I'd rather hear it from you. What's been on your mind this week?"

Then **shut up and listen.** They will tell you the role's real shape in 5 minutes if you let them.

### Listening posture

- **Active note-taking, visibly.** Not on a screen they can see. Pen + paper or a screen they can't see.
- **Ask "what does success look like in 90 days?" early.** Their answer reveals what they're really hiring for vs the JD.
- **Listen for stories of frustration.** "We tried X but it didn't quite work" — that's the hidden requirement. Ask what specifically didn't work.
- **Don't fill silences.** If they pause, wait. They'll keep going.

### When you DO talk

- **Concrete, recent, specific.** "When I built the multi-tool dispatcher, the variance across tool input shapes was the actual bottleneck — I solved it with a normalization layer at line X. Took 4 hours; saved every downstream policy from per-tool branching." Beats "I'm a problem solver."
- **Mention the artifact, link to it, move on.** Don't deep-dive unprompted. They have the post; they've already decided you can write.
- **One opinion per topic.** "I'd ship the Loom on the company X account first, not Russell's, because [reason]." Hiring managers test for clarity of judgment, not breadth of opinions.

### The questions you MUST ask (rotate 2-3 per call)

1. "What's the first thing a new DevRel hire would touch in their first 2 weeks?" (Reveals real role priorities.)
2. "Who else is the team trying to hire?" (Reveals team shape + your fit.)
3. "What's the metric this role moves?" (Reveals what they actually measure.)
4. "What's the worst version of someone in this role you've seen?" (Reveals dealbreakers.)
5. "What's something the team got wrong in the last quarter?" (Reveals self-awareness + culture.)
6. "What does your week look like? Is this manager-of-managers or hands-on?" (Reveals workload.)

### Closing the call

- Don't ask "what are next steps?" — passive. Try: "I'd be excited to do a take-home or technical screen as the next step. Is there a written role spec I should look at first?"
- Send a thank-you within 4 hours (template below).

---

## Stage 3 — Post-call follow-up

### Thank-you email (send within 4 hours of the call)

```
Hi [first name],

Thanks for the time today — particularly appreciated [specific thing they
said, paraphrased back so they know you listened].

Two follow-up notes:

1. You mentioned [specific challenge they raised]. I went and read [whatever
they referenced] after the call; here's a 3-sentence take: [your read].

2. Re: the [specific topic] you flagged — I drafted a short note on what I'd
do in the first 30 days [if they expressed interest], or [the relevant
artifact link if not yet at "what would you do" stage].

If a take-home or technical screen is the right next step, I'm ready.
Calendar still open for a follow-up: [Calendly link].

— Russell
```

### "What I'd do in the first 30 days" doc (only if asked)

This is the "show your work" artifact. Build per-company; don't reuse generically.

Format:
- **Week 1-2: Listen and document.** Specific things you'd read, people you'd shadow, products you'd ship-track. Be concrete: "Read all 47 of [Company]'s public agent-tool blog posts and tag by audience."
- **Week 3-4: One concrete deliverable.** The thing you'd ship that proves fit. Not "I'd write more posts" — say which post, with what hook, for which audience.
- **30-day metric.** What success looks like at day 30. "Two new external dev advocates running with [Company]'s tooling" or "[Specific KPI] up 15%."

This is the difference between "candidate" and "hire on the verge." Most candidates don't build it because it's actual work.

---

## Per-company prep notes

### Anthropic (Alex Albert / Cat Wu)

**Listening cues to watch for:**
- "We're underfunded on [team]" — Cat said this on Lenny. If the role she routes you to is one of those teams, you're in.
- "We don't have a strong [content type] yet" — directly answer what you'd ship, with specifics.
- The Claude Code "verbosity revert" cycle in April 2026 was a public hiccup — be ready to discuss what good post-incident comms looks like, since that's literally the role.

**Questions to ask Alex specifically:**
- "What's the gap between Developer Education Lead and the original Developer Relations Lead role posting?"
- "How does @ClaudeDevs's editorial line get set?"

**What they'll test:**
- Writing quality (you've already shown this with the post)
- Whether you understand Claude as a *product*, not just an LLM
- Whether you're a competitor or a fan (be a fan with constructive criticism, not a fan-with-no-edges)

### Cursor (Lee Robinson)

**Listening cues:**
- "Millions of new devs without strong foundations" — his thesis, repeat back if relevant.
- Any reference to scaling Vercel's DevRel team — he'll tell you what worked + what he'd do differently. Cursor is his redo.

**Questions to ask:**
- "What's the editorial line between 'cookbook' content and 'opinion' content at Cursor?"
- "How do you balance educating new devs vs serving expert devs without splitting the audience?"

**What they'll test:**
- Whether you can write content for a beginner audience (most of Cursor's growth is from new devs)
- Speed of iteration (Vercel-DevRel pace is fast)

### Cline (Saoud Rizwan)

**Listening cues:**
- Anything about enterprise-security positioning. Cline's wedge is the safety-aware agent for enterprises.
- "Plan/Act mode" — this is his architectural baby. Compliment the architecture, don't compete with it.

**Questions to ask:**
- "What's the first 90-day deliverable for a founding DevRel?"
- "How do you think about open-source community vs enterprise sales motion?"

**What they'll test:**
- Whether you'd represent Cline well in the enterprise-buyer conversation
- Whether your safety angle complements vs competes with Plan/Act

### Replit (Manny Bernabe / Tala Awwad)

**Listening cues:**
- The Lemkin DB-wipe incident is everyone's elephant. Don't dance around it; address it directly.
- Tala's creator program is the bigger growth lever right now — be ready to talk creator ecosystem, not just dev relations.

**Questions to ask:**
- "How does the safety-positioning storytelling map to the creator-program audience? Different language?"
- "What's the metric on Agent 4 adoption that you're watching?"

**What they'll test:**
- Whether you can speak to non-developer creators (Replit's growth audience is broader than CC's)
- Whether you can hold the safety story without making it feel like the lawyer-led version

---

## What to avoid in every call

- **Don't pitch enact during the interview.** They've read the post. The post is the pitch. The interview is about *you fitting their team*, not selling them the toolkit.
- **Don't claim AI-co-development is a workaround for not being a "real engineer."** Frame it as "I AI-co-develop because that's the future, and I've shipped real artifacts to prove it." The artifact is the proof.
- **Don't apologize for being self-taught.** Most CTOs at AI co's are skeptical of CS-degree credentialism by now.
- **Don't go over time.** End at 28 min on a 30-min slot. Respect their calendar; book a follow-up if needed.
- **Don't oversell.** If you don't know something, say "I don't know — but I'd find out by [specific approach]." That's the senior-IC answer.

---

## Tracking

Update target list with stage progression:

| Target | DM sent | Reply | Stage 1 (async) | Stage 2 (live) | Stage 3 (followup) | Outcome |
|---|---|---|---|---|---|---|
| Alex Albert | | | | | | |
| Cat Wu | | | | | | |
| Lee Robinson | | | | | | |
| Saoud Rizwan | | | | | | |
| Manny Bernabe | | | | | | |

Goal: 1-2 reach Stage 3 (post-call followup) by day 14. If 0 reach Stage 3 by day 14, the DMs/post need iteration — re-read replies for what's missing.