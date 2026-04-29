# Enact blocked Claude from editing its own gitignore — that's the feature

*A short, real-time follow-up to "Hooking into Claude Code: 39 paired runs and the 80/20 refusal asymmetry." Same session, same hook, live evidence of the safety property the longer post argues for.*

---

## TL;DR

- Mid-session, Claude (running in Claude Code) tried to add a line to `.gitignore` during a benign repo-cleanup task. Twice — once via the Edit tool, once via Bash redirection.
- Both attempts hit Enact's PreToolUse hook. **Both were blocked.**
- The block was correct in principle (the policy exists to prevent agents from leaking secrets by removing entries from `.gitignore`) and inconvenient in practice (the agent's intent was to *add* internal-only paths, not remove tracked secrets).
- That tradeoff — false positives over false negatives on irreversible-action gates — is exactly the architecture the longer post defends. The policy can't tell intent from bytes. So it errs on the side of stop.
- Receipt was signed; deny reason routed back to the agent; agent worked around by skipping the gitignore step. No drama, no surprise, no recovery. Live evidence in ~30 seconds.

---

## What happened

The session was a portfolio-cleanup pass: move a handful of internal AI working docs (`Handoff.md`, `INTENT_GUIDE.md`, planning files) out of repo root into a local-only `.internal/` directory. Hiring-manager-friendly cleanup, no code changes.

Step 1 of the agent's plan was to add `.internal/` to `.gitignore` so the moved files stay local. Tool call:

```
Edit(file_path=".gitignore", old_string="...", new_string="...\n.internal/")
```

The hook fired:

```
Enact blocked (1 policy): dont_edit_gitignore:
Editing '.gitignore' is not permitted — changes could expose
sensitive files to version control
```

The agent shrugged, switched to a Bash workaround:

```bash
printf '\n.internal/\n' >> .gitignore
```

Hook fired again, this time on the Bash matcher:

```
Enact blocked (1 policy): block_gitignore_edit:
.gitignore edit blocked — agents bypass secret guards by editing the ignore file
```

Two policies, two surfaces, same wall. Defense in depth across Bash AND Edit — exactly the multi-tool coverage the longer post details.

The agent surfaced both blocks to me in chat, with verbatim deny reasons. Then it pivoted: skip the gitignore step, leave `.internal/` as a known-untracked directory, document the workaround for next session. Total time lost: about 90 seconds.

---

## Why the policy is correct in principle

Agents that can edit `.gitignore` can defeat `.env`-detection policies trivially:

```python
# Step 1: agent adds .env to gitignore
echo ".env" >> .gitignore

# Step 2: agent commits .env (secret-detection policy
# still fires on the file content, but the surface
# area for novel secret patterns has just widened)
git add -f .env  # or wait for an unrelated workflow to add it

# Step 3: agent's PR ships with creds in tree
```

A gate that blocks `.gitignore` edits unilaterally cuts off the most common bypass class for secret-leak detection. The cost is real: legitimate edits get caught too. The benefit is also real: an agent that's actively trying to leak a secret (or, more often, an agent that's been prompt-injected into trying) hits a hard wall.

This is the core tradeoff for any irreversible-action gate. **You can't tell intent from bytes.** The agent's request to add `.internal/` looks identical to a request to add `.env`. The policy fires on the SHAPE of the action, not the model's narrative about it.

The longer post argued: *"RLHF-shaped safety operates on the model's interpretation of intent. A PreToolUse policy operates on the bytes of the tool call."* The gitignore block is a tiny, concrete instance of that. The model's intent was benign; the bytes still tripped the gate.

---

## Why the workaround was easy

Critically, the agent didn't get *stuck*. The hook's deny reason routed back to it cleanly. It re-planned in two tool calls: skip the gitignore add, document the consequence (`.internal/` files appear as untracked in `git status`), keep moving.

That's the right shape for a safety layer. Hard stop on the dangerous-shape action; agent picks a different path; user notices nothing unless they read the receipts. The model didn't brick. The IDE didn't brick. The work shipped.

If the gate had been an LLM-mediated check ("is this gitignore edit dangerous?") instead of a deterministic byte-pattern gate, the agent could have argued itself past it: *"I'm only ADDING entries, not removing them"* is a perfectly reasonable LLM response that an LLM judge might accept. A policy regex doesn't argue.

---

## What this evidence is, and isn't

It is:
- A live demonstration of the longer post's central architectural claim: a deterministic gate that runs *before* the model decides anything will sometimes block legitimate work, and that's the correct failure mode.
- Empirical proof that defense in depth works: the same policy fired across two different surfaces (Edit tool + Bash redirection), neither of which the agent had pre-planned to use.

It is not:
- An argument that the current `.gitignore` policy is at the right strictness. There's a real product question about whether a once-per-install acknowledgment ("I am the repo owner, allow gitignore edits this session") is worth shipping. The current default — block always, document the workaround — is a 1.0 default, not the final answer.

---

## What's next

The longer post listed five next-up roadmap items. None of them solve the gitignore tradeoff directly. A small follow-up worth scoping:

- **Owner-mode override.** A signed `enact policy unlock <policy-name> --once` command that uses the install secret to mint a single-use override receipt. The receipt is auditable; the override is bounded. The policy-vs-friction tradeoff becomes a configurable knob, not a fixed default.

If you've thought about this product surface — particularly anyone running policy-as-code or signed-receipt audit infra — feedback welcome on the longer post's repo: [github.com/russellmiller3/enact](https://github.com/russellmiller3/enact).

— Russell

[Read the longer post →](2026-04-28-claude-code-asymmetry.md)