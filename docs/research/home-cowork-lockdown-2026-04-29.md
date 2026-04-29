# Home-user Cowork lockdown — the OpenClaw policy set (2026-04-29)

What policies a single home user running Claude Cowork would install to keep the agent from accidentally fucking their shit up — keys, files, money, email autonomy, calendar, browser-borne malware, persistence.

**Honest state of the world (2026-04-29):** the Enact engine is Claude Code only today. Cowork integration is the spec below. None of these 10 policies are installable yet. This doc IS the v1 product spec for "Enact for Cowork — home user lockdown pack."

## The threat catalog (what a home Cowork user actually fears)

| Worry | Concrete shape |
|---|---|
| Expose keys | Agent reads `.env`, `~/.aws/credentials`, `~/.ssh/id_rsa`, browser password DB, macOS Keychain |
| Delete files | Agent runs `rm -rf` somewhere bad, or hits "Delete" in Drive UI on the wrong file |
| Charge credit card | Agent's browser automation clicks Subscribe/Buy on a page with stored card |
| Email autonomy | Agent sends email to wrong person, attaches sensitive doc, mass-sends |
| Calendar mayhem | Agent deletes events at scale, modifies wrong calendar |
| Browser-borne malware | Agent downloads a `.dmg` from a sketchy site |
| Persistent damage | Agent creates a scheduled task that fires later |

## The 10-policy lockdown set (priority order)

| # | Policy name | What it blocks | Cowork tool it gates |
|---|---|---|---|
| 1 | `dont_read_credential_files` | Reading `.env`, `~/.aws/credentials`, `~/.ssh/id_rsa`, `~/.config/gh/hosts.yml`, browser password DB paths, Keychain access tools | Bash, Read, computer-use |
| 2 | `block_rm_rf_under_home` | `rm -rf` on absolute paths under `$HOME` (excluding `~/Trash`, `~/Downloads/.cache`) | Bash |
| 3 | `confirm_drive_delete` | Pauses every Drive/Box file delete for human confirmation; agent cannot batch-delete | Drive `delete`, Box `delete` |
| 4 | `block_payment_form_submit` | Browser detecting `<input type="submit">` on a page containing credit-card-shaped fields (16-digit number, CVV, expiry) — pause | claude-in-chrome `form_input` + `left_click` |
| 5 | `block_subscribe_button_click` | Click target text matches `subscribe`, `buy now`, `complete purchase`, `confirm payment`, `start trial` — pause | claude-in-chrome `left_click` |
| 6 | `confirm_email_send_to_external` | Gmail send/draft where ANY recipient domain is outside your allowlist — pause | Gmail `send`, `create_draft` |
| 7 | `block_email_attachment_to_external` | Email with attachment to non-allowlisted domain — block (not pause) | Gmail `send` with `attachments` |
| 8 | `cap_calendar_modifications_per_session` | More than 5 calendar event mutations (create/update/delete) in one session — pause | Calendar `create_event`, `update_event`, `delete_event` |
| 9 | `block_download_executable` | Browser download of `.exe`, `.dmg`, `.pkg`, `.app`, `.msi`, `.deb`, `.rpm` — block | claude-in-chrome `navigate` to URL ending in those extensions |
| 10 | `block_schedule_with_admin_priv` | Scheduled task that requests admin/sudo — block. Cap recurring frequency at N=24/day for non-admin tasks. | scheduled-tasks `create_scheduled_task` |

## What "install" looks like for v1

Cowork's tool calls all flow through MCP. The Enact-for-Cowork install pattern is:

```
Cowork agent → MCP request → enact-cowork-mcp server
                                ↓ (policy engine evaluates payload)
                                ↓ DENY / PASS / PAUSE_FOR_HUMAN
                                ↓
                              actual MCP tool (Gmail / Drive / etc.)
```

The `enact-cowork-mcp` server sits between Cowork and the real MCP tools. Same engine as the CC hook; different transport (MCP shim vs PreToolUse subprocess).

Install on Mac/Linux/Windows:

```bash
pip install enact-sdk[cowork]
enact-cowork install --profile=home
# Writes ~/.cowork/mcp-shim.json with the engine wired
# in front of Gmail / Drive / Calendar / Box / chrome / scheduled-tasks
```

`--profile=home` ships with the 10 policies above ON by default. `--profile=team` ships with the team policies from `cowork-policies-2026-04-29.md` instead.

## How this composes with Cowork's built-in approval UX

Cowork already pauses for approval on certain actions (sends, deletes, etc). The risk: approval fatigue → user clicks "always allow" → no protection.

Enact's role is to AUTO-DECIDE the easy cases so the user only sees Cowork's approval UI when something is GENUINELY ambiguous:

| Case | Without Enact | With Enact |
|---|---|---|
| Send benign email to your mom | Cowork prompts | `confirm_email_send_to_external` allowlists `gmail.com`/`mom@whatever`; agent sends silently |
| Send email with attachment to lawyer.com | Cowork prompts | `block_email_attachment_to_external` blocks (lawyer.com not on allowlist); user has to send manually |
| Read `.env` for an unrelated task | Cowork might or might not prompt | `dont_read_credential_files` blocks deterministically |
| Buy a $9.99 SaaS subscription | Cowork prompts | `block_subscribe_button_click` blocks; user does it manually |
| Create one calendar event | Cowork prompts | Allowed silently |
| Create 47 calendar events | Cowork prompts on each (47 prompts) | `cap_calendar_modifications_per_session` pauses once at 6 |

The wedge for the home user: **fewer pop-ups for safe stuff, hard stop on dangerous stuff.** Approval fatigue solved by deterministic policy.

## What the home user actually does day-1

```bash
pip install enact-sdk[cowork]
enact-cowork install --profile=home
```

Then in Cowork, the next 100 actions are silently policy-evaluated. The user sees Cowork's prompt only when:
- The policy returns PAUSE_FOR_HUMAN (genuinely ambiguous case)
- An action falls outside any policy's domain (default: pass through to Cowork's normal approval flow)

After a week of use, the user reads `~/.cowork/receipts/` to see what got blocked + what passed. Tunes their allowlists. Adds custom policies for their own risks.

## What's NOT in the home-user pack but IS in the team pack

| Policy | Reason it's team-only |
|---|---|
| `enforce_actor_token_match` | Single user — no actor mismatch possible |
| `restrict_skill_to_role` | No roles for home user |
| `audit_plugin_data_egress` | Home user installs plugins themselves; the auditing-someone-else case doesn't exist |
| `block_team_admin_actions_from_non_admin_role` | No team admin |

Five team-level policies become irrelevant for home use. The 10 above are the home-user-distilled set.

## Effort estimate (if Russell wants this built)

| Component | Time |
|---|---|
| `enact-cowork-mcp` shim server (intercepts MCP, wraps engine) | 1 day |
| Connector-aware payload parsers (Gmail/Drive/Box/Calendar/chrome/scheduled-tasks) | 1 day |
| 10 policies above (regex + simple heuristics, all maps to existing engine) | 1 day |
| `enact-cowork install` CLI | 0.5 day |
| Tests (paired sweep on a Cowork sandbox — same methodology as the 39-prompt CC sweep) | 1 day |
| Docs + landing-page section | 0.5 day |
| **Total** | **~5 days for v1** |

5 days for a real product surface that nobody else is building, that maps directly to a buyer-pain Russell himself feels every day. That's the highest-leverage Cowork build.

## Recommended path

1. Build `enact-cowork-mcp` shim with the 10 policies above
2. Russell dogfoods on his own machine for a week
3. Tune the policies based on his receipts
4. Ship as `enact-sdk[cowork]` extra on PyPI
5. Write a short post: "What I installed on my Cowork to keep my keys, files, money, and inbox safe." Companion to the 39-paired-runs research post; same audience; bigger market (Cowork users > Claude Code-only users).

That post + the existing CC research post = two pillars of the portfolio. Anthropic-team conversation gets stronger.