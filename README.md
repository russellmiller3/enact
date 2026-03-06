# Enact

**You just gave an LLM access to real APIs. What happens when it does something stupid?**

It already has. [Replit's agent deleted a production database](https://fortune.com/2025/07/23/ai-coding-tool-replit-wiped-database-called-it-a-catastrophic-failure/). [Amazon Kiro caused a 13-hour AWS outage](https://awesomeagents.ai/news/amazon-kiro-ai-aws-outages/). [Claude Code ran `rm -rf` on a home directory](https://byteiota.com/claude-codes-rm-rf-bug-deleted-my-home-directory/). These weren't bugs — the agents did exactly what they were told. The problem: nothing was checking _whether they should_.

Enact is the missing layer between your agent and the real world:

1. **Block dangerous actions before they fire** — Python policies run before anything executes
2. **Execute deterministically** — plain Python workflows, not LLM-generated actions
3. **Prove what happened** — cryptographically-signed receipt on every run
4. **Roll back in one call** — `enact.rollback(run_id)` reverses the entire run

**Now with zero-knowledge encryption.** Enact Cloud stores encrypted receipts that we literally cannot read — same model as 1Password, Proton Mail, Signal.

```
pip install enact-sdk
```

---

## How It Works

Think of Enact like a **foreman supervising an AI carpenter**. When the carpenter says "I want to tear down this wall":

1. **Permit check _(Policies)_** — Before any tool is picked up, the foreman checks the plans. Load-bearing? Approved? If not: work stops, written reason recorded.
2. **Blueprint _(Workflow)_** — If approved, the carpenter follows exact step-by-step instructions — not just "tear down the wall" but each specific action in order. No improvising.
3. **Work log _(Receipt)_** — A signed record of every nail pulled, every stud removed, before-and-after state. Cryptographically sealed so it can't be altered later.
4. **Change order _(Rollback)_** — If the carpenter tore down the WRONG wall, the foreman issues a change order. Enact uses the work log to reverse every step and put it back.

---

## Zero-Knowledge Encryption

When you use Enact Cloud with an encryption key, we can't read your receipts. Here's what that looks like:

**Your receipt (what you see):**
```json
{
  "run_id": "a1b2c3d4",
  "workflow": "create_pr",
  "user_email": "agent@company.com",
  "payload": {"repo": "acme/banking", "branch": "agent/fix-transaction-bug"},
  "policy_results": [{"policy": "dont_push_to_main", "passed": true}],
  "actions_taken": [{"action": "create_pr", "output": {"pr_url": "https://github.com/..."}}]
}
```

**What Enact Cloud sees:**
```json
{
  "run_id": "a1b2c3d4",
  "workflow": "create_pr",
  "decision": "PASS",
  "timestamp": "2026-03-05T12:00:00Z",
  "policy_names": ["dont_push_to_main"],
  "payload_blob": "AES-256-GCM encrypted... (we can't read this)"
}
```

The key never leaves your machine. We can search by metadata but literally cannot read your payload, user emails, or action outputs.

```python
from enact.encryption import generate_encryption_key

key = generate_encryption_key()  # 32 bytes, store securely
enact = EnactClient(
    systems={"github": github},
    policies=[dont_push_to_main],
    workflows=[create_pr],
    cloud_api_key="your-api-key",
    encryption_key=key,  # <-- This key never leaves your machine
)
```

---

## Quickstart

```bash
pip install enact-sdk
python examples/quickstart.py
```

Three runs — one BLOCK, one PASS, one ROLLBACK — with signed receipts. No credentials needed.

---

## Docs

**[docs.enact.cloud](https://docs.enact.cloud)**

- [Getting Started](https://docs.enact.cloud/getting-started)
- [Migration Guide](https://docs.enact.cloud/migration) — wrap your existing agent in 10 minutes
- [Connectors](https://docs.enact.cloud/concepts/connectors) — GitHub, Postgres, Filesystem, Slack
- [Built-in Policies](https://docs.enact.cloud/concepts/policies) — 30 policies, 9 categories
- [Rollback](https://docs.enact.cloud/concepts/rollback) — what can and can't be undone
- [Integrations](https://docs.enact.cloud/integrations) — Anthropic skills, MCP, LangChain, CrewAI

---

## License

[ELv2](LICENSE) + no-resale clause. Free to use, self-host, and modify. Cannot be resold as a competing product.
