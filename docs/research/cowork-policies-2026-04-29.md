# Cowork-specific policy set — design notes (2026-04-29)

What policies make sense for Enact-for-Cowork that DON'T already make sense for Enact-for-Claude-Code?

**Premise:** Cowork's security wedge is different from CC's. CC is "agent has root on one developer's laptop." Cowork is "agent has access to a team's shared infra — Box, Gmail, Calendar, Drive, Slack, plus first-class plugins and curated skills, all multi-tenant by default." Same engine; different threat catalog.

The 5 failure modes Cowork-specific policies need to cover, with proposed policies under each.

---

## 1. Cross-user blast radius

One user's agent operates on a shared resource at a scale or scope they didn't intend. The shared resource has many other stakeholders.

| Policy | What it blocks | Source pattern |
|---|---|---|
| `block_destructive_on_shared_resources` | Delete / archive / move on resources marked shared (shared Drive folders, shared Box folders, shared Slack channels, team calendars). Default: pause-for-human. | Generalization of the Replit/PocketOS pattern to multi-user resources |
| `rate_limit_bulk_operations` | N destructive operations per time window. N=10 default. Beyond threshold = pause. | Stops the "agent loops on 5000 emails / 200 calendar events" pattern. Real incident: any bulk-delete script that runs unsupervised |
| `block_team_admin_actions_from_non_admin_role` | Only admin role can change team settings, role assignments, billing, plugin installs | Confused-deputy: agent escalates beyond user's role |

---

## 2. Cross-tenant / cross-domain exfil

Agent reads from an internal connector (Box, Drive, internal Slack, Gmail with @company.com) and writes to an external connector (Gmail external, public Slack channel, public Drive folder). Classic exfil shape.

| Policy | What it blocks | Source pattern |
|---|---|---|
| `block_internal_to_external_attach` | Box/Drive internal doc attached to email outside `@company.com`. Pause-for-human. | The "agent emailed customer database to wrong recipient" failure mode |
| `flag_external_email_with_attachment` | Email with attachment to non-allowlisted domain triggers human approval | OpenClaw 2026 / Comment-and-Control pattern |
| `domain_allowlist_per_user` | Outbound emails restricted by per-user allowlist (sales rep can email customers; engineer cannot email arbitrary external) | Phishing-via-agent + accidental data leak |
| `block_drive_share_to_external` | Sharing a Drive doc / Box folder externally requires explicit user click — agent cannot share | Real incident: agents auto-sharing internal docs with prompt-injected "everyone with link" perms |

---

## 3. Confused-deputy / privilege creep across user boundaries

User A invokes an agent. The agent calls a tool that uses User B's credentials (or runs in B's context). Agent inherits B's authority unintentionally.

| Policy | What it blocks | Source pattern |
|---|---|---|
| `enforce_actor_token_match` | Every action must be authorized by a token belonging to the user who initiated the session, not the user the agent is "currently helping with" | OpenClaw Feb 2026 (Meta AI safety lead's own inbox); Comment-and-Control across Claude/Gemini/Copilot |
| `block_cross_user_private_resource_access` | User A's agent cannot read User B's private docs/inbox even if they share a workspace | Multi-tenant agent-as-confused-deputy |
| `require_fresh_auth_for_cross_user_action` | Action affecting another user's resource requires fresh auth from THAT user, not just the invoking user | The Meta March 2026 incident (agent-as-confused-deputy across two humans) |

---

## 4. Skill / plugin abuse

Cowork has curated skills (anthropic-skills, project-specific skills) and a plugin marketplace. Both are MCP-shaped; both add capability. Both can be invoked in contexts they weren't designed for.

| Policy | What it blocks | Source pattern |
|---|---|---|
| `restrict_skill_to_role` | Admin/billing/destructive skills only available to admin role. Junior-dev role can't invoke admin skills even if workspace has them. | Privilege escalation via skill chain |
| `block_unverified_plugin_install` | Only signed plugins from curated registry can install. Prompt-injected install requests denied. | Plugin supply-chain attack |
| `audit_plugin_data_egress` | Plugins must declare data egress (which connectors they read/write). Deviation = block + alert. | Comment-and-Control via plugin |
| `block_skill_chain_root` | Composed skills inherit the most-restrictive policy of any constituent | Bypass-via-composition: combine 2 benign skills to make 1 dangerous one |

---

## 5. Bulk operation cascades

Agent operates on N items where N is much larger than the user said. "Clean up old emails" → 5000 deletions. "Reorganize calendar" → 200 event mutations. "Standardize file names" → 1500 renames in shared Drive.

| Policy | What it blocks | Source pattern |
|---|---|---|
| `pause_at_N_destructive_operations` | N=10 default for irreversible ops (delete email, delete event, delete file). Configurable per role. | The "agent loops on 5000 emails" pattern |
| `confirm_at_bulk_recipients` | Sending to 50+ recipients in one batch = pause-for-human | Mass-send incidents (Slack/Gmail) |
| `flag_calendar_event_modify_at_scale` | N+ calendar event mutations in one session = pause | Calendar hijack pattern |
| `cap_share_link_creation` | N share-link creations per session = pause (catches the "share everything externally" exfil shape) | Cross-tenant exfil at scale |

---

## Cowork-only architecture patterns the engine needs

Beyond the policies, Cowork's enforcement layer needs three things CC doesn't:

1. **Skill-aware payloads.** When a skill fires, the engine sees both the skill name AND the underlying tool calls. Policy can fire on either layer. Single-tool policies (block destructive Bash) AND skill-level policies (block `admin:reset-team`) compose.
2. **Connector-aware identity.** Each tool call carries the connector ID + the user's auth principal in that connector. Policies use principal vs initiator-user mismatch as a signal (the confused-deputy detection above).
3. **Team-scoped policy bundles.** Admin writes once, signs, distributes to every Cowork user via the cloud-side push (already on ROADMAP, was Next #4, becomes Next #1 if Cowork is the new wedge).

---

## What's the wedge first?

If forced to ship 5 policies first, in order of buyer-pain × engineering-effort:

1. **`pause_at_N_destructive_operations`** — universal, easy to spec, real value Day 1
2. **`block_internal_to_external_attach`** — the exfil headline; SOC2/HIPAA/GDPR all care
3. **`enforce_actor_token_match`** — closes the OpenClaw class; differentiates from "just a content filter"
4. **`block_destructive_on_shared_resources`** — the multi-user generalization of CC's wedge
5. **`audit_plugin_data_egress`** — Cowork's ecosystem plugin layer is brand new; getting in front of supply-chain risk is high-leverage

This is the order to write the Cowork product spec around. Each is shippable in a half-day to a day; together they're the "Enact for Cowork" v1 surface.

---

## Source mapping (for the eventual product page)

| Cowork policy | Shape inherits from |
|---|---|
| `pause_at_N_destructive_operations` | CC's `dont_force_push` extended to a counter |
| `block_internal_to_external_attach` | CC's `dont_read_env` generalized to data-egress shape |
| `enforce_actor_token_match` | New — no CC analog because CC is single-user |
| `block_destructive_on_shared_resources` | CC's `protect_tables` generalized to "shared resource registry" |
| `audit_plugin_data_egress` | CC's WebFetch URL policies (planned in ROADMAP) generalized to MCP plugin manifests |

Three of five inherit cleanly. Two are net-new. That's a good ratio for "we already have most of the engine" framing.