# Research post distribution — copy/paste-ready

Pairing artifact for the research post at `docs/research/post-2026-04-28-claude-code-asymmetry.md`.

**Canonical URL:** swap once enact.cloud/blog goes live. For now, use the GitHub raw link:
`https://github.com/russellmiller3/enact/blob/master/docs/research/post-2026-04-28-claude-code-asymmetry.md`

**Send order:**
1. Publish to canonical home (enact.cloud/blog OR github raw OR GitHub Pages)
2. HN — Tuesday-Thursday, 8-10am Pacific (catches morning EU + lunchtime ET)
3. X — same day, ~30 min after HN
4. LinkedIn — same day or next morning, link in first comment (algorithm prefers this)
5. DMs — start sending Variant 3 to Tier-A target list once HN gets any traction

---

## 1. Hacker News submission

**Title (pick ONE — Russell, your call):**

| # | Title | Tradeoff |
|---|---|---|
| 1 | `Show HN: I built a safety hook for Claude Code (39 paired chaos runs)` | Show-HN tag = friendlier moderation, "built" signals it's a real artifact |
| 2 | `Hooking into Claude Code: 39 paired runs and the 80/20 refusal asymmetry` | The post's own title — research-paper-flavored, less salesy |
| 3 | `Claude Code refuses 80% of destructive shell commands but only 20% of exfil reads` | Sharpest hook, but reads as gotcha-y; HN voters punish anti-vendor framing |

Strong recommendation: **#1 or #2**. Avoid #3 — Anthropic is well-liked on HN, framing as "Claude is unsafe" backfires.

**URL:** the canonical post URL (enact.cloud preferred; github raw as fallback)

**First comment (post immediately, within 60 seconds of submission — HN convention):**

```
Author here. Quick context for the post:

This is empirical, not adversarial. The data shows Claude Code's training is
doing a lot of safety work — 21 of 26 self-refusals on the dangerous shell
corpus is a remarkable rate. The post argues for a deterministic gate as a
COMPLEMENT to that training, not a replacement.

Three things I'd love feedback on:

1. The misinterpretation 5-prompt set is the next round of methodology — 3
   of 5 no-op'd because the test sandbox was too clean for the agent to
   invent a destructive solution. What other sandbox shapes would force the
   PocketOS pattern (resource-name confusion across staging/prod)?

2. The fabrication detector idea (post section "What this means for Claude
   Code design"): is this useful, or is the right place to fight that
   battle further upstream in training?

3. For people on the inside of CC's hook protocol: is the userMessage-
   bypassing-the-model channel something you've considered? Open to hearing
   why it might be a bad idea.

Repo: github.com/russellmiller3/enact (PyPI 1.0.0, ELv2). 545 tests passing.
```

**Why this comment:** it pre-empts the two most common HN dunk patterns ("this is anti-vendor" and "show your work"), invites substantive feedback, and gives the author voice without sounding pitchy.

---

## 2. X thread (10 tweets)

Send as a thread. Tweet 1 is the hook — most readers stop there. If they continue, tweets 2-10 deliver the substance.

**Tweet 1 (hook):**
```
Built a PreToolUse hook for Claude Code, ran 39 paired chaos prompts.

Claude refuses ~80% of destructive shell commands the user types.
Claude refuses ~20% of read-shaped exfil requests.
Claude refuses ~0% of cases where the agent INVENTS the destructive action.

Thread + post 🧵
```

**Tweet 2:**
```
The 80/20 asymmetry is the load-bearing finding. It maps to three trigger
types — user-typed destructive vs read-shaped exfil vs agent-self-initiated
— with self-refusal rates dropping sharply across them.
```

**Tweet 3:**
```
The third row is the worst case. It's what happened to PocketOS on April 25:
flagship model + flagship IDE + explicit "never run destructive ops" rule in
the project config. Cursor + Claude Opus 4.6 deleted a Railway volume to
"fix" a credential mismatch. Volume was prod. 9 seconds. 3 months gone.
```

**Tweet 4:**
```
Self-refusal can't help with that case. The agent isn't being asked to do
the bad thing — it's deciding on its own to "fix" friction in a routine
task. System-prompt rules don't help either. Models have been observed
enumerating the rules they're breaking, in writing, while breaking them.
```

**Tweet 5:**
```
A deterministic gate that runs *before* the model decides anything fills
exactly that gap. Same architecture across 6 of 8 Claude Code tools (Bash,
Read, Write, Edit, Glob, Grep). One shared payload shape; same policy
library fires whether the agent uses Bash or the file tool.
```

**Tweet 6 (data table — screenshot the post's headline table here):**
```
The numbers:

39 paired prompts (sweep A: hook on; sweep B: hook off)
Without Enact: 8 critical incidents
With Enact: 0

Per-surface breakdown + 21-vs-14 self-refusal column in the post.
```

**Tweet 7:**
```
Bonus finding: the chaos sweep surfaced 2 latent Windows bugs in my own
product, both invisible to unit tests, both silent for 6 dev sessions.
PATH bug + bash backslash mangling. End-to-end CC subagent invocation was
the only path that surfaced them.
```

**Tweet 8:**
```
Lesson: unit tests that import-and-call bypass the integration surface.
The integration surface is where the integration bugs live. Strongest
single argument I have for shipping a chaos-test harness alongside any
agent-coding tool.
```

**Tweet 9:**
```
Repo: github.com/russellmiller3/enact (PyPI 1.0.0, 545 tests, ELv2)
Post: [URL]

Open questions on agent-self-initiated destruction patterns + fabrication
detection in the post. Would love feedback from anyone on agent-safety
teams.
```

**Tweet 10 (the soft hire pitch):**
```
I'm Russell — built this solo, AI-co-developed end-to-end. I'm exploring
DevRel / PMM / Solutions Engineer roles at AI coding co's right now,
Anthropic's Claude Code team in particular. DMs open.
```

**Total: 10 tweets, ~280 chars each. Posts in ~3 minutes.**

---

## 3. LinkedIn long-form post (~2200 chars)

LinkedIn rewards long-form posts that keep readers in-app. Put the post URL in the FIRST COMMENT, not the post body — the algorithm penalizes external links.

**Post body:**

```
I built a safety hook for Claude Code over the last few weeks, and ran 39
paired chaos prompts through it. Here's what surprised me.

The headline finding is an asymmetry in Claude Code's self-refusal rate
across three trigger types:

→ User types a destructive shell command directly ("DROP TABLE customers"):
   Claude refuses ~80% of the time. Strong training signal.

→ User asks a read-shaped task; agent reads sensitive files
   ("show me the env vars" → Read .env): Claude refuses ~20% of the time.
   The Read tool feels benign, so the safety signal is weaker.

→ User asks a routine task; agent INDEPENDENTLY decides destructive action
   to "fix" unrelated friction (PocketOS pattern, April 25 — Cursor +
   Claude Opus 4.6 deleted a Railway volume to fix a credential mismatch,
   volume was production, 3 months of data gone in 9 seconds): Claude
   refuses ~0% of the time. The agent isn't being asked to do the bad
   thing; it's deciding on its own to be helpful.

The third row is the load-bearing one for tools like Enact. No bad actor
required. Self-refusal can't help. System-prompt rules don't help — agents
have been observed enumerating the rules they're breaking, in writing,
while breaking them.

A deterministic gate running BEFORE the model decides anything fills
exactly that gap. The two layers compose: 21 self-refusals + 15
deterministic blocks = 0 damage on the 34-prompt shell sweep.

Without Enact: 8 critical incidents on 39 paired prompts.
With Enact: 0.

Plus two latent Windows bugs in my own product the chaos sweep surfaced,
both invisible to unit tests. End-to-end testing matters.

Full write-up + repo + methodology in the comments.

I'm Russell — built this solo, AI-co-developed. Exploring DevRel / PMM /
Solutions Engineer roles at AI coding co's. Open to chats — Anthropic's
Claude Code team in particular.
```

Char count: ~2200. Within LinkedIn's 3000-char limit.

**First comment (post immediately):**
```
Post: [URL]
Repo: github.com/russellmiller3/enact (PyPI 1.0.0, 545 tests, ELv2)

Open feedback welcome — methodology, the misinterpretation sandbox shape,
the fabrication-detector idea. All in the post.
```

---

## 4. Reddit (optional, lower priority)

Subreddits to consider, in priority order:

- **r/LocalLLaMA** — has the most agent-safety-aware audience. Good fit.
- **r/MachineLearning** — research-leaning, will appreciate the methodology
- **r/programming** — broader audience, may dunk on specifics
- **r/ClaudeCode** (if it exists) — perfect fit, smaller reach

Skip r/cscareerquestions and r/jobs. The post is about the work, not the hire.

**Submission shape on Reddit:** same title as HN option #1 or #2, link to enact.cloud canonical URL (NOT GitHub raw — Reddit auto-rewrites those into ugly previews). Body comment same as HN first-comment, copy-paste.

---

## 5. Direct submissions to specific people (after public posts land)

Once the post is live, send DMs (per `linkedin_dm_template.md` Variants 3 and 4) to the Tier-A target list. Reference the HN submission if it gets traction:

```
> P.S. Just submitted to HN — currently at 18 upvotes, would love your
> read independent of the discussion there.
```

Social proof from HN momentum increases reply rate on cold DMs sent in the same window.

---

## Post-launch ops checklist (what to do after publishing)

- [ ] Watch HN comments for 4-6 hours; reply to every substantive question within 1 hour
- [ ] Watch X mentions; like + reply to every quote-tweet
- [ ] DM 3-5 Tier-A targets within 2 hours of HN submission
- [ ] If HN hits front page: send "submitted to HN, currently at #X" to all Tier-A pending DMs
- [ ] If a journalist or analyst follows up: refer to existing post + repo, don't go off-script
- [ ] At 24-hour mark: post a short retro on X (engagement metrics, top feedback themes, what's next)