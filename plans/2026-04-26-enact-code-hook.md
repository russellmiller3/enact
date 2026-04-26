# Plan 2026-04-26: Enact Code Hook (Template A — Full TDD)

## Step 0: Critical Rules Checklist

- [x] Read last 10 commits for context (done — see Handoff.md session 8-9)
- [x] Branch already created: `claude/add-guardrails-ai-tools-Mk20f`
- [ ] Update tests in same step as code changes
- [ ] Preserve unrelated code — touch nothing outside hook scope
- [ ] Simplest solution first — reuse existing policies, no new ShellConnector
- [ ] Plan goes in `plans/`, written in chunks ≤150 lines

## A.1 What We're Building

A Claude Code `PreToolUse` / `PostToolUse` hook that intercepts `Bash` tool calls,
runs them through Enact's existing policy engine in dry-run mode, and returns
`permissionDecision: deny` JSON when any policy blocks.

Ships as one new binary `enact-code-hook` with three subcommands:
- `enact-code-hook init` → writes `.claude/settings.json` and creates `.enact/` config
- `enact-code-hook pre` → reads PreToolUse JSON from stdin, returns deny/allow JSON
- `enact-code-hook post` → reads PostToolUse JSON from stdin, appends action to receipt

```
BEFORE (today)
  Claude Code → Bash → executes whatever it wants → user finds out at 3am

AFTER (this plan)
  Claude Code → PreToolUse hook → enact policies (dry-run)
                                     ├─ all pass → exit 0 (CC proceeds)
                                     └─ any block → emit deny JSON
                                                    (CC sees reason, tells user)
              → Bash executes (only if allowed)
              → PostToolUse hook → append ActionResult to session receipt
```

**Key Decisions:**

1. **No new ShellConnector** — hook does light regex extraction of `table`,
   `where`, `sql`, `args`, `command` from the raw bash command string and
   stuffs them into `payload`. Existing policies fire as-is. Saves ~200 lines
   and one whole connector vs. building a real shell execution layer.
2. **One binary, three subcommands** — `enact-code-hook init|pre|post`.
   Cleaner than three separate entry points; matches how `git` works.
3. **Synthetic action name** — every Bash call becomes
   `payload` for action name `"shell.bash"`. We do NOT register this as a
   real `@action` — the hook calls `evaluate_all()` directly via a thin
   wrapper, since we want policy gating without execution.
4. **Bash tool ONLY for v1** — Edit/Write/MultiEdit deferred. The killer
   demo is a destructive psql command; that runs through Bash. Ship the
   demo, not the platform.
5. **Receipt-per-session, not per-tool-call** — `init` creates a session
   receipt file at session-start; each `post` call appends; final receipt
   signed at session-end. Avoids the 200-receipts-per-session spam problem.
   *NOTE for v1:* defer the session receipt machinery — `post` writes a
   single Receipt per Bash call for now. Session batching is v1.1.

## A.2 Existing Code to Read First

| File | Why |
|---|---|
| `enact/client.py` | `EnactClient` shape; we'll instantiate it in the hook |
| `enact/policy.py` | `evaluate_all(context, policies)` — what the hook calls |
| `enact/models.py` | `WorkflowContext`, `PolicyResult`, `Receipt` shapes |
| `enact/policies/git.py` | `dont_force_push` reads `payload["args"]` or `["command"]` |
| `enact/policies/db.py` | `protect_tables`, `dont_delete_without_where`, `block_ddl` payload keys |
| `enact/policies/time.py` | `code_freeze_active` reads `ENACT_FREEZE` env var (no payload deps) |
| `enact/receipt.py` | `build_receipt`, `sign_receipt`, `write_receipt` — for `post` subcommand |
| `tests/test_action.py` | Test pattern reference (fixtures, registry cleanup) |
| `pyproject.toml` | Need to ADD `[project.scripts]` section |

## A.3 Data Flow Diagram

```
Claude Code session starts
       │
       ▼
  ┌──────────────────────────────────────┐
  │ User: "clean up old customer rows"   │
  └─────────────────┬────────────────────┘
                    ▼
            Claude proposes:
   Bash(command="psql $DB -c \"DELETE FROM customers\"")
                    │
                    ▼
   ┌────────────────────────────────────────────┐
   │ PreToolUse hook fires                      │
   │   stdin: {tool_name, tool_input, ...}      │
   │                                            │
   │   1. Parse command → extract:              │
   │        sql       = "DELETE FROM customers" │
   │        table     = "customers"             │
   │        where     = {} (no WHERE found)     │
   │        args      = ["psql", "$DB", "-c", …]│
   │        command   = "psql $DB -c \"...\""   │
   │                                            │
   │   2. Build WorkflowContext(payload=above)  │
   │                                            │
   │   3. evaluate_all(ctx, configured_policies)│
   │        protect_tables(["customers",…])     │
   │           → BLOCK: 'customers' protected   │
   │        dont_delete_without_where           │
   │           → BLOCK: where clause required   │
   │        code_freeze_active                  │
   │           → BLOCK: ENACT_FREEZE=1          │
   │                                            │
   │   4. Emit deny JSON to stdout              │
   └────────────────────┬───────────────────────┘
                        ▼
        Claude sees deny; tells user the reason.
        User adjusts intent, retries, or escalates.

  ON ALLOW (no policy fired):
     hook exits 0 silently → Claude executes Bash normally
     PostToolUse hook fires → appends ActionResult to receipts/<run_id>.json
```

## A.4 Files to Create

### File 1 — `enact/cli/__init__.py`

Empty package marker. One line:

```python
"""Enact CLI entry points."""
```

### File 2 — `enact/cli/code_hook.py` (Part 1: imports, defaults, parser)

**Path:** `enact/cli/code_hook.py`

```python
"""
Enact Code — Claude Code hook for blocking dangerous Bash commands.

Three subcommands:
  enact-code-hook init   — write .claude/settings.json, create .enact/ config
  enact-code-hook pre    — PreToolUse handler; emit deny JSON if any policy blocks
  enact-code-hook post   — PostToolUse handler; write Receipt to disk

Reads JSON from stdin (CC hook protocol), writes JSON to stdout (deny output),
or exits silently with code 0 (allow / fall through to default behaviour).

Failure mode: any unexpected error → exit 0 (fail open). Reasoning: a buggy
hook should never permanently block CC; the user can always remove the hook
config. Loud failures here would be worse than silent ones.
"""
import json
import os
import re
import sys
import secrets as secrets_module
from pathlib import Path

from enact.models import WorkflowContext, ActionResult
from enact.policy import evaluate_all, all_passed
from enact.receipt import build_receipt, sign_receipt, write_receipt


DEFAULT_POLICIES_PY = '''\
"""Enact Code policies — edit to customize what gets blocked."""
from enact.policies.git import dont_force_push, dont_commit_api_keys
from enact.policies.db import (
    protect_tables,
    dont_delete_without_where,
    block_ddl,
)
from enact.policies.time import code_freeze_active

POLICIES = [
    code_freeze_active,
    block_ddl,
    dont_force_push,
    dont_commit_api_keys,
    dont_delete_without_where,
    protect_tables(["users", "customers", "orders", "payments", "audit_log"]),
]
'''


# Light SQL extraction so existing policies fire on raw shell commands.
_PSQL_C_RE = re.compile(r'-c\s+["\']([^"\']+)["\']')
_TABLE_RE = re.compile(
    r'\b(?:DELETE\s+FROM|UPDATE|INSERT\s+INTO|TRUNCATE|DROP\s+TABLE)\s+["\']?(\w+)',
    re.IGNORECASE,
)
_WHERE_RE = re.compile(r'\bWHERE\b\s+(.+?)(?:\s*;|\s*$)', re.IGNORECASE | re.DOTALL)


def parse_bash_command(command: str) -> dict:
    """
    Map a raw shell command into the payload shape existing policies expect.

    For psql -c "..." patterns, extracts the SQL and pulls out table + WHERE.
    Always populates command, args, diff, content so string-scanning policies
    (dont_force_push, dont_commit_api_keys, block_ddl) fire correctly.

    Empty fields → policies treat as pass-through per existing payload contract
    (e.g. protect_tables passes if no table specified). Conservative by design.
    """
    payload = {
        "command": command,
        "args": command.split(),
        "diff": command,
        "content": command,
    }

    sql_match = _PSQL_C_RE.search(command)
    sql = sql_match.group(1) if sql_match else ""
    if sql:
        payload["sql"] = sql
        payload["action"] = sql

        table_match = _TABLE_RE.search(sql)
        if table_match:
            payload["table"] = table_match.group(1)

        where_match = _WHERE_RE.search(sql)
        if where_match:
            payload["where"] = {"clause": where_match.group(1).strip()}

    return payload
```

### File 2 — `enact/cli/code_hook.py` (Part 2: subcommands + entry)

```python
def _is_enact_hook_entry(entry: dict) -> bool:
    """Detect a previously-installed enact-code-hook entry, for idempotent reinstall."""
    for h in entry.get("hooks", []):
        if "enact-code-hook" in h.get("command", ""):
            return True
    return False


def cmd_init() -> int:
    """Write .claude/settings.json and bootstrap .enact/ config in cwd."""
    cwd = Path.cwd()
    claude_dir = cwd / ".claude"
    enact_dir = cwd / ".enact"
    claude_dir.mkdir(exist_ok=True)
    enact_dir.mkdir(exist_ok=True)

    settings_path = claude_dir / "settings.json"
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    settings.setdefault("hooks", {})

    pre_entry = {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "enact-code-hook pre"}],
    }
    post_entry = {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "enact-code-hook post"}],
    }

    # Merge: keep user's existing hooks for other tools / matchers; replace any
    # prior enact-code-hook entry so re-running init never duplicates ours.
    existing_pre = settings["hooks"].get("PreToolUse", [])
    existing_post = settings["hooks"].get("PostToolUse", [])
    settings["hooks"]["PreToolUse"] = (
        [e for e in existing_pre if not _is_enact_hook_entry(e)] + [pre_entry]
    )
    settings["hooks"]["PostToolUse"] = (
        [e for e in existing_post if not _is_enact_hook_entry(e)] + [post_entry]
    )
    settings_path.write_text(json.dumps(settings, indent=2))

    policies_path = enact_dir / "policies.py"
    if not policies_path.exists():
        policies_path.write_text(DEFAULT_POLICIES_PY)

    secret_path = enact_dir / "secret"
    if not secret_path.exists():
        secret_path.write_text(secrets_module.token_hex(32))
        secret_path.chmod(0o600)

    gitignore = cwd / ".gitignore"
    line = ".enact/\n"
    if gitignore.exists():
        contents = gitignore.read_text()
        if ".enact/" not in contents:
            gitignore.write_text(contents.rstrip() + "\n" + line)
    else:
        gitignore.write_text(line)

    print("Enact Code initialized.", file=sys.stderr)
    print(f"  - {settings_path}", file=sys.stderr)
    print(f"  - {policies_path}  (edit to customize policies)", file=sys.stderr)
    return 0


def _load_policies() -> list:
    """Import .enact/policies.py from cwd and return its POLICIES list."""
    policies_path = Path.cwd() / ".enact" / "policies.py"
    if not policies_path.exists():
        return []
    import importlib.util
    spec = importlib.util.spec_from_file_location("enact_user_policies", policies_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "POLICIES", [])


def cmd_pre() -> int:
    """PreToolUse handler. Emit deny JSON to stdout if any policy blocks.

    Wraps the entire body in try/except so any unexpected error (broken
    .enact/policies.py, ImportError, policy bug) results in fail-open
    behaviour. A buggy hook must NEVER permanently brick CC.
    """
    try:
        try:
            event = json.loads(sys.stdin.read() or "{}")
        except json.JSONDecodeError:
            return 0  # fail open on malformed stdin

        if event.get("tool_name") != "Bash":
            return 0  # only Bash for v1

        command = event.get("tool_input", {}).get("command", "")
        if not command:
            return 0

        payload = parse_bash_command(command)
        context = WorkflowContext(
            workflow="shell.bash",
            user_email="claude-code@local",
            payload=payload,
        )
        results = evaluate_all(context, _load_policies())

        if all_passed(results):
            return 0  # silent allow

        failed = [r for r in results if not r.passed]
        reasons = "; ".join(f"{r.policy}: {r.reason}" for r in failed)
        plural = "y" if len(failed) == 1 else "ies"
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Enact blocked ({len(failed)} polic{plural}): {reasons}"
                ),
            }
        }
        print(json.dumps(output))
        return 0
    except Exception:
        # Fail open — broken policies, import errors, bad policy logic.
        return 0


def cmd_post() -> int:
    """PostToolUse handler. Write a signed Receipt for the executed action.

    Receipt always carries decision="PASS" — we only reach PostToolUse if the
    PreToolUse policy gate allowed the call. Whether the bash command itself
    succeeded operationally is recorded in actions_taken[0].success and the
    exit_code in its output dict. The receipt records what was attempted and
    its outcome; the policy decision is separate.
    """
    try:
        try:
            event = json.loads(sys.stdin.read() or "{}")
        except json.JSONDecodeError:
            return 0

        if event.get("tool_name") != "Bash":
            return 0

        secret_path = Path.cwd() / ".enact" / "secret"
        if not secret_path.exists():
            return 0  # not initialized — skip silently

        secret = secret_path.read_text().strip()
        command = event.get("tool_input", {}).get("command", "")
        tool_response = event.get("tool_response") or {}

        # Reflect bash exit status in ActionResult.success; do not change
        # decision="PASS" — that field reflects the policy gate, not bash.
        exit_code = tool_response.get("exit_code", 0)
        interrupted = tool_response.get("interrupted", False) is True
        bash_succeeded = (exit_code == 0) and not interrupted

        action_result = ActionResult(
            action="shell.bash",
            system="shell",
            success=bash_succeeded,
            output={
                "command": command,
                "exit_code": exit_code,
                "interrupted": interrupted,
                "already_done": False,
            },
        )

        payload = {
            "command": command,
            "session_id": event.get("session_id", ""),
        }

        receipt = build_receipt(
            workflow="shell.bash",
            user_email="claude-code@local",
            payload=payload,
            policy_results=[],
            decision="PASS",
            actions_taken=[action_result],
        )
        receipt = sign_receipt(receipt, secret)
        write_receipt(receipt, "receipts")
        return 0
    except Exception:
        return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: enact-code-hook {init|pre|post}", file=sys.stderr)
        return 1
    cmd = sys.argv[1]
    if cmd == "init":
        return cmd_init()
    if cmd == "pre":
        return cmd_pre()
    if cmd == "post":
        return cmd_post()
    print(f"Unknown subcommand: {cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

### File 3 — `tests/test_code_hook.py`

**Path:** `tests/test_code_hook.py`

```python
"""Tests for the Enact Code Claude Code hook."""
import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from enact.cli.code_hook import (
    parse_bash_command,
    cmd_init,
    cmd_pre,
    cmd_post,
    main,
)


# -- parser tests --

class TestParseBashCommand:
    def test_plain_command_populates_command_and_args(self):
        p = parse_bash_command("ls -la /tmp")
        assert p["command"] == "ls -la /tmp"
        assert p["args"] == ["ls", "-la", "/tmp"]
        assert "table" not in p
        assert "where" not in p

    def test_psql_delete_extracts_table_no_where(self):
        cmd = 'psql $DB -c "DELETE FROM customers"'
        p = parse_bash_command(cmd)
        assert p["table"] == "customers"
        assert "where" not in p
        assert "DELETE FROM" in p["sql"]

    def test_psql_delete_extracts_where_clause(self):
        cmd = "psql -c \"DELETE FROM users WHERE id = 1\""
        p = parse_bash_command(cmd)
        assert p["table"] == "users"
        assert "where" in p
        assert "id = 1" in p["where"]["clause"]

    def test_drop_table_extracts_table_and_sql(self):
        cmd = 'psql -c "DROP TABLE customers"'
        p = parse_bash_command(cmd)
        assert p["table"] == "customers"
        assert "DROP TABLE" in p["sql"]

    def test_force_push_args_visible(self):
        p = parse_bash_command("git push --force origin main")
        assert "--force" in p["args"]


# -- pre-hook tests --

@pytest.fixture
def in_tmp_with_init(tmp_path, monkeypatch):
    """Run cmd_init in a tmp dir so .enact/policies.py exists for cmd_pre."""
    monkeypatch.chdir(tmp_path)
    cmd_init()
    return tmp_path


def _run_pre(stdin_json: dict) -> tuple[int, str]:
    """Invoke cmd_pre with mocked stdin/stdout. Return (rc, stdout)."""
    stdin = io.StringIO(json.dumps(stdin_json))
    stdout = io.StringIO()
    with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
        rc = cmd_pre()
    return rc, stdout.getvalue()


class TestCmdPre:
    def test_non_bash_tool_passes_silently(self, in_tmp_with_init):
        rc, out = _run_pre({"tool_name": "Read", "tool_input": {"path": "/x"}})
        assert rc == 0
        assert out == ""

    def test_safe_command_passes_silently(self, in_tmp_with_init):
        rc, out = _run_pre({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
        assert rc == 0
        assert out == ""

    def test_protected_table_blocks(self, in_tmp_with_init):
        rc, out = _run_pre({
            "tool_name": "Bash",
            "tool_input": {"command": 'psql -c "DELETE FROM customers WHERE id=1"'},
        })
        assert rc == 0
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "customers" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_force_push_blocks(self, in_tmp_with_init):
        rc, out = _run_pre({
            "tool_name": "Bash",
            "tool_input": {"command": "git push --force origin main"},
        })
        assert rc == 0
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "force" in result["hookSpecificOutput"]["permissionDecisionReason"].lower()

    def test_freeze_blocks(self, in_tmp_with_init, monkeypatch):
        monkeypatch.setenv("ENACT_FREEZE", "1")
        rc, out = _run_pre({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert rc == 0
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "freeze" in result["hookSpecificOutput"]["permissionDecisionReason"].lower()

    def test_malformed_stdin_fails_open(self, in_tmp_with_init):
        stdin = io.StringIO("not json{{{")
        with patch.object(sys, "stdin", stdin):
            assert cmd_pre() == 0

    def test_no_policies_file_passes_through(self, tmp_path, monkeypatch):
        """No .enact/policies.py → empty policies list → silent allow."""
        monkeypatch.chdir(tmp_path)  # do NOT call cmd_init
        stdin = io.StringIO(json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
        }))
        stdout = io.StringIO()
        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            assert cmd_pre() == 0
        assert stdout.getvalue() == ""

    def test_broken_policies_file_fails_open(self, tmp_path, monkeypatch):
        """Syntax-broken or import-broken policies.py → fail open silently."""
        monkeypatch.chdir(tmp_path)
        cmd_init()
        (tmp_path / ".enact" / "policies.py").write_text(
            "import this_module_does_not_exist\nPOLICIES = []\n"
        )
        stdin = io.StringIO(json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": 'psql -c "DELETE FROM customers"'},
        }))
        stdout = io.StringIO()
        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            assert cmd_pre() == 0
        # Even a destructive command falls through when the hook itself is broken
        # — we never want a buggy hook to permanently brick CC. User must fix policies.py.
        assert stdout.getvalue() == ""


# -- init tests --

class TestCmdInit:
    def test_writes_settings_and_creates_dirs(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rc = cmd_init()
        assert rc == 0
        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert "PreToolUse" in settings["hooks"]
        assert (tmp_path / ".enact" / "policies.py").exists()
        assert (tmp_path / ".enact" / "secret").exists()
        assert ".enact/" in (tmp_path / ".gitignore").read_text()

    def test_init_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        original_secret = (tmp_path / ".enact" / "secret").read_text()
        cmd_init()
        assert (tmp_path / ".enact" / "secret").read_text() == original_secret

    def test_init_preserves_existing_unrelated_hooks(self, tmp_path, monkeypatch):
        """Pre-existing hooks for other tools/matchers must survive cmd_init."""
        monkeypatch.chdir(tmp_path)
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        prior = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Read",
                        "hooks": [{"type": "command", "command": "some-other-tool check"}],
                    }
                ]
            },
            "theme": "dark",
        }
        (claude_dir / "settings.json").write_text(json.dumps(prior))

        cmd_init()

        settings = json.loads((claude_dir / "settings.json").read_text())
        assert settings["theme"] == "dark"  # unrelated key preserved
        pre_hooks = settings["hooks"]["PreToolUse"]
        assert len(pre_hooks) == 2
        matchers = {e["matcher"] for e in pre_hooks}
        assert matchers == {"Read", "Bash"}
        # The other tool's command is still present
        all_commands = [
            h["command"]
            for entry in pre_hooks
            for h in entry["hooks"]
        ]
        assert "some-other-tool check" in all_commands

    def test_init_replaces_prior_enact_entry_no_duplicate(self, tmp_path, monkeypatch):
        """Re-running init must not stack duplicate enact-code-hook entries."""
        monkeypatch.chdir(tmp_path)
        cmd_init()
        cmd_init()
        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        for hook_event in ("PreToolUse", "PostToolUse"):
            entries = settings["hooks"][hook_event]
            enact_entries = [
                e for e in entries
                if any("enact-code-hook" in h.get("command", "") for h in e.get("hooks", []))
            ]
            assert len(enact_entries) == 1, f"{hook_event} duplicated enact entry"

    def test_init_does_not_double_add_gitignore_line(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        cmd_init()
        contents = (tmp_path / ".gitignore").read_text()
        assert contents.count(".enact/") == 1


# -- post-hook tests --

class TestCmdPost:
    def _run_post(self, stdin_json: dict) -> int:
        stdin = io.StringIO(json.dumps(stdin_json))
        with patch.object(sys, "stdin", stdin):
            return cmd_post()

    def test_writes_signed_receipt_with_action(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        rc = self._run_post({
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "tool_response": {"exit_code": 0, "stdout": "file1\nfile2\n"},
            "session_id": "abc-123",
        })
        assert rc == 0
        receipts = list((tmp_path / "receipts").glob("*.json"))
        assert len(receipts) == 1
        body = json.loads(receipts[0].read_text())
        assert body["decision"] == "PASS"
        assert body["signature"] != ""
        assert len(body["actions_taken"]) == 1
        action = body["actions_taken"][0]
        assert action["action"] == "shell.bash"
        assert action["system"] == "shell"
        assert action["success"] is True
        assert action["output"]["command"] == "ls -la"
        assert action["output"]["exit_code"] == 0
        assert action["output"]["already_done"] is False

    def test_failed_bash_reflected_in_action_success(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        rc = self._run_post({
            "tool_name": "Bash",
            "tool_input": {"command": "false"},
            "tool_response": {"exit_code": 1, "stderr": "fail"},
        })
        assert rc == 0
        body = json.loads(list((tmp_path / "receipts").glob("*.json"))[0].read_text())
        # Decision still PASS — the policy gate let it through.
        # ActionResult.success captures the operational outcome.
        assert body["decision"] == "PASS"
        assert body["actions_taken"][0]["success"] is False
        assert body["actions_taken"][0]["output"]["exit_code"] == 1

    def test_interrupted_bash_marks_action_failed(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        rc = self._run_post({
            "tool_name": "Bash",
            "tool_input": {"command": "sleep 100"},
            "tool_response": {"exit_code": 0, "interrupted": True},
        })
        assert rc == 0
        body = json.loads(list((tmp_path / "receipts").glob("*.json"))[0].read_text())
        assert body["actions_taken"][0]["success"] is False
        assert body["actions_taken"][0]["output"]["interrupted"] is True

    def test_no_secret_skips_silently(self, tmp_path, monkeypatch):
        """If cmd_init was never run, cmd_post must not crash or write anything."""
        monkeypatch.chdir(tmp_path)
        rc = self._run_post({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert rc == 0
        assert not (tmp_path / "receipts").exists()

    def test_non_bash_tool_skipped(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        rc = self._run_post({"tool_name": "Read", "tool_input": {"path": "/x"}})
        assert rc == 0
        assert not (tmp_path / "receipts").exists()


# -- main dispatcher --

class TestMain:
    def test_unknown_subcommand_returns_1(self):
        with patch.object(sys, "argv", ["enact-code-hook", "bogus"]):
            assert main() == 1

    def test_no_subcommand_returns_1(self):
        with patch.object(sys, "argv", ["enact-code-hook"]):
            assert main() == 1
```

## A.5 Files to Modify

### File — `pyproject.toml`

**Path:** `pyproject.toml`
**Insert after** the existing `[project.optional-dependencies]` section (around line 32),
**before** `[tool.setuptools]`:

```toml
[project.scripts]
enact-code-hook = "enact.cli.code_hook:main"
```

That's the only modification needed — registers the `enact-code-hook` console
script so `pip install -e .` makes it available on PATH.

### File — `enact/__init__.py`

**No changes.** The hook is a CLI binary, not part of the Python public API.
Keep `enact` package surface unchanged.

## A.6 Edge Cases & Error Handling

| Scenario | Handling | Test? |
|---|---|---|
| Stdin is not valid JSON | `cmd_pre` / `cmd_post` return 0 (fail open) | yes — `test_malformed_stdin_fails_open` |
| Tool is not Bash (Read, Grep, etc.) | `cmd_pre` returns 0 silently, no policy run | yes — `test_non_bash_tool_passes_silently` |
| Empty command string | `cmd_pre` returns 0 silently | yes — covered by `test_safe_command_passes_silently` (ls case) |
| `.enact/policies.py` missing | `_load_policies` returns `[]`, silent allow | yes — `test_no_policies_file_passes_through` |
| `.enact/policies.py` is broken (ImportError, SyntaxError) | Outer try/except in `cmd_pre` catches; fail open | yes — `test_broken_policies_file_fails_open` |
| `.enact/secret` missing in `cmd_post` | `cmd_post` returns 0 (skip receipt write); never crashes | yes — `test_no_secret_skips_silently` |
| `.claude/settings.json` already has unrelated hooks for other tools | `cmd_init` MERGES — keeps existing entries, replaces only prior enact entries | yes — `test_init_preserves_existing_unrelated_hooks` |
| Re-running `cmd_init` with a prior enact entry already present | `cmd_init` removes the prior enact entry before appending the new one (no duplicates) | yes — `test_init_replaces_prior_enact_entry_no_duplicate` |
| `.gitignore` already contains `.enact/` | `cmd_init` skips re-adding the line | yes — `test_init_does_not_double_add_gitignore_line` |
| Bash command exited non-zero | `cmd_post` reflects `exit_code` in `ActionResult.success`; receipt `decision` stays `PASS` | yes — `test_failed_bash_reflected_in_action_success` |
| Bash command was interrupted (Ctrl-C) | `cmd_post` marks `ActionResult.success=False`, records `interrupted=True` in output | yes — `test_interrupted_bash_marks_action_failed` |
| Heredoc SQL (`psql <<EOF\nDELETE FROM x;\nEOF`) | NOT parsed by `_PSQL_C_RE` for v1; `block_ddl` still catches DROP/TRUNCATE etc. via `payload["sql"]` content scan; documented limitation | manual — v1 acceptable, fix in v1.1 |
| SQL with embedded escaped quotes (`-c "DELETE FROM x WHERE name = \"foo\""`) | NOT parsed correctly by `_PSQL_C_RE` for v1; falls through to other policies (e.g. `protect_tables` won't fire) | manual — v1 acceptable, fix in v1.1 |
| psql command with single quotes vs double | `_PSQL_C_RE` handles both quote styles | yes — `test_psql_delete_extracts_where_clause` |
| Multi-statement SQL (`SELECT 1; DELETE FROM x`) | `_TABLE_RE` matches first DELETE/UPDATE/etc. found; `block_ddl` covers DROP/TRUNCATE/etc. via word-boundary regex | yes — `test_drop_table_extracts_table_and_sql` |
| Force-push variants (`-f`, `--force`, `--force-with-lease`) | Existing `dont_force_push` policy already handles all three | yes — `test_force_push_blocks` covers `--force` |
| Code freeze active | `ENACT_FREEZE` env passes through to `code_freeze_active` policy unchanged | yes — `test_freeze_blocks` |
| User customizes `.enact/policies.py` after init | `_load_policies` reloads on every invocation (no caching) | manual — covered by usage |
| API key in command (e.g. `curl -H "Authorization: Bearer sk-..."`) | `dont_commit_api_keys` scans `payload["diff"]` (= raw command) for vendor patterns | manual — already covered by existing policy tests |

**Failure philosophy:** the hook fails OPEN on any unexpected error. A buggy
hook should never permanently brick CC; the user can always remove the hook
config from `.claude/settings.json`. Loud failures here are worse than silent
ones because they break the development environment.

## A.7 Implementation Order (Kent Beck TDD)

### PRE-IMPLEMENTATION CHECKPOINT

1. **Can this be simpler?** Yes — `parse_bash_command` is regex-only,
   `_load_policies` reads a Python file directly (no pluggy/entry-point
   machinery). All four files together are <500 lines including tests.
2. **Do I understand the task?** Ship a CC hook that blocks dangerous Bash
   commands using existing policies. Demo: prod-DB DELETE blocked.
3. **Scope discipline:** NOT touching `enact/client.py`, NOT touching
   `enact/policies/*`, NOT building a ShellConnector, NOT adding session
   receipts (deferred to v1.1), NOT supporting Edit/Write/MultiEdit (v2).

### Cycle 1: `parse_bash_command` extracts table + sql + where

**Goal:** prove the regex extraction works on the demo command.

| Phase | Action |
|---|---|
| RED | Write `TestParseBashCommand::test_psql_delete_extracts_where_clause` |
| GREEN | Implement `parse_bash_command` with `_PSQL_C_RE`, `_TABLE_RE`, `_WHERE_RE` |
| REFACTOR | Extract regex constants to module level |
| VERIFY | `pytest tests/test_code_hook.py::TestParseBashCommand -v` |

**Files changed:** `enact/cli/__init__.py`, `enact/cli/code_hook.py` (parser only),
`tests/test_code_hook.py` (parser tests)
**Commit:** `feat(code): bash command parser extracts SQL/table/where for policies`

### Cycle 2: `cmd_init` writes settings + bootstraps `.enact/` (with merge logic)

**Goal:** one command stands up the hook config in any repo, preserving any
pre-existing user hooks and idempotent on repeat runs.

| Phase | Action |
|---|---|
| RED | Write `test_writes_settings_and_creates_dirs`, `test_init_preserves_existing_unrelated_hooks`, `test_init_replaces_prior_enact_entry_no_duplicate`, `test_init_does_not_double_add_gitignore_line`, `test_init_idempotent` |
| GREEN | Implement `cmd_init` + `_is_enact_hook_entry` helper. Merge logic: filter out prior enact entries from existing list, append new entries. |
| REFACTOR | Extract `DEFAULT_POLICIES_PY` constant; ensure `_is_enact_hook_entry` is well-named |
| VERIFY | `pytest tests/test_code_hook.py::TestCmdInit -v` (5 tests pass) |

**Files changed:** `enact/cli/code_hook.py` (+cmd_init, +_is_enact_hook_entry), `tests/test_code_hook.py` (+TestCmdInit, 5 tests)
**Commit:** `feat(code): enact-code-hook init bootstraps .claude + .enact config (merge-safe)`

### Cycle 3: `cmd_pre` allow path (silent pass on safe commands)

**Goal:** non-Bash tools and safe Bash commands fall through silently.

| Phase | Action |
|---|---|
| RED | Write `test_non_bash_tool_passes_silently` and `test_safe_command_passes_silently` |
| GREEN | Implement `cmd_pre` early-returns for non-Bash and empty command |
| REFACTOR | Extract `_load_policies` helper |
| VERIFY | `pytest tests/test_code_hook.py::TestCmdPre -v -k "passes_silently"` |

**Files changed:** `enact/cli/code_hook.py` (+cmd_pre allow path), `tests/test_code_hook.py` (+TestCmdPre allow tests)
**Commit:** `feat(code): pre-hook allow path passes safe Bash commands through`

### Cycle 4: `cmd_pre` deny path emits permission decision JSON

**Goal:** the demo. Block destructive psql against protected table.

| Phase | Action |
|---|---|
| RED | Write `test_protected_table_blocks` |
| GREEN | Implement deny JSON emission in `cmd_pre` |
| REFACTOR | Pluralize "policy/policies" cleanly; verify reason string is human-readable |
| VERIFY | `pytest tests/test_code_hook.py::TestCmdPre::test_protected_table_blocks -v` |

**Files changed:** `enact/cli/code_hook.py` (cmd_pre deny path), `tests/test_code_hook.py` (deny tests)
**Commit:** `feat(code): pre-hook emits permissionDecision deny JSON on policy block`

### Cycle 5: cover remaining deny scenarios + fail-open paths

**Goal:** force-push, code freeze, malformed input, missing policies file, and
broken policies file all behave correctly. Verifies the broader try/except
wrapper in `cmd_pre` actually catches non-JSON errors.

| Phase | Action |
|---|---|
| RED | Write `test_force_push_blocks`, `test_freeze_blocks`, `test_malformed_stdin_fails_open`, `test_no_policies_file_passes_through`, `test_broken_policies_file_fails_open` |
| GREEN | Wrap entire `cmd_pre` body in outer try/except (return 0 on any exception). Confirm `_load_policies` reload-on-each-call works. |
| REFACTOR | Confirm the docstring on `cmd_pre` calls out fail-open behaviour |
| VERIFY | `pytest tests/test_code_hook.py::TestCmdPre -v` (8 tests pass) |

**Files changed:** `enact/cli/code_hook.py` (cmd_pre outer try/except), `tests/test_code_hook.py` (+5 tests)
**Commit:** `test(code): cover force-push, code-freeze, fail-open, broken-policies paths`

### Cycle 6: `cmd_post` writes signed Receipt with `actions_taken`

**Goal:** every executed Bash call leaves a signed audit trail with the
command, exit code, and interrupt status. Receipt decision stays "PASS"
because the policy gate allowed it; bash exit status lives in the
`ActionResult` so audit retains the operational outcome separately.

| Phase | Action |
|---|---|
| RED | Write `test_writes_signed_receipt_with_action`, `test_failed_bash_reflected_in_action_success`, `test_interrupted_bash_marks_action_failed`, `test_no_secret_skips_silently`, `test_non_bash_tool_skipped` |
| GREEN | Implement `cmd_post`: read `tool_response`, build ActionResult with success=`(exit_code == 0 and not interrupted)`, attach to receipt via `actions_taken=[action_result]`, sign + write |
| REFACTOR | Confirm receipt fields match Receipt schema; `already_done: False` is present in action output |
| VERIFY | `pytest tests/test_code_hook.py::TestCmdPost -v` (5 tests pass) |

**Files changed:** `enact/cli/code_hook.py` (+cmd_post), `tests/test_code_hook.py` (+TestCmdPost class, 5 tests)
**Commit:** `feat(code): post-hook writes signed Receipt with ActionResult and exit_code`

### Cycle 7: `main` dispatcher + `pyproject.toml` entry point

**Goal:** `pip install -e .` exposes `enact-code-hook` on PATH.

| Phase | Action |
|---|---|
| RED | Write `TestMain::test_unknown_subcommand_returns_1` |
| GREEN | Implement `main` and add `[project.scripts]` block to `pyproject.toml` |
| REFACTOR | Verify `pip install -e .` works in a fresh shell |
| VERIFY | `pytest tests/test_code_hook.py -v && which enact-code-hook` |

**Files changed:** `enact/cli/code_hook.py` (+main), `pyproject.toml` (+[project.scripts]), `tests/test_code_hook.py` (+TestMain)
**Commit:** `feat(code): register enact-code-hook entry point`

### Cycle 8: end-to-end manual smoke test

**Goal:** prove the demo works in a real CC session before recording the Loom.

```bash
# In a scratch repo:
pip install -e /path/to/enact
cd /tmp/scratch
enact-code-hook init

# Open Claude Code in this dir, then:
#   "delete all rows from the customers table"
# Expected: CC writes psql command, hook returns deny, CC tells user
#   "I tried to run that but Enact blocked it because customers is protected."

# Verify receipt was NOT written (since action was blocked):
ls receipts/   # should be empty or contain only PASS receipts from prior runs
```

No code changes. Document any UX issues discovered for v1.1 polish pass.

**Commit:** none (manual verification only)

## A.8 Test Strategy

```bash
# Run hook tests only
pytest tests/test_code_hook.py -v

# Run a single class
pytest tests/test_code_hook.py::TestCmdPre -v

# Full suite (must stay green)
pytest -v
```

**Success Criteria:**

- [ ] `parse_bash_command` extracts table + sql + where from psql commands
- [ ] `cmd_init` writes valid `.claude/settings.json` and `.enact/policies.py`
- [ ] `cmd_pre` returns deny JSON when any policy fails
- [ ] `cmd_pre` returns 0 silently when all policies pass
- [ ] `cmd_pre` fails open on malformed stdin
- [ ] `cmd_post` writes a signed Receipt to `receipts/`
- [ ] `main` dispatches to all three subcommands and rejects unknown ones
- [ ] `pip install -e .` exposes `enact-code-hook` on PATH
- [ ] `cmd_post` writes a Receipt with non-empty `actions_taken` containing the command and exit_code
- [ ] `cmd_post` reflects bash exit status in `ActionResult.success` (PASS decision regardless)
- [ ] Re-running `cmd_init` does NOT duplicate enact entries in `.claude/settings.json`
- [ ] `cmd_init` preserves user's pre-existing hooks for other tools/matchers
- [ ] All existing 530+ tests still pass
- [ ] At least 23 new tests in `tests/test_code_hook.py` (parser × 5, pre × 8, init × 5, post × 5, main × 2)

## A.9 Cleanup & Handoff

- [ ] Run `pytest -v` — full suite green
- [ ] Manual smoke test in a real CC session (Cycle 8)
- [ ] Update `Handoff.md`:
  - "Session 10: shipped Enact Code hook (`enact-code-hook init|pre|post`)"
  - Next step: record demo Loom, build outbound list of 50 targets
- [ ] Update `enact-intent.md` Actions section with `cmd_init`, `cmd_pre`, `cmd_post`
- [ ] Update `README.md` — add an Enact Code section under Quickstart
- [ ] Update landing page (`index.html`) — add Enact Code feature card
- [ ] No dead code added; nothing unused
- [ ] Commit + push branch (`commit-and-push` skill)
- [ ] **Russell:** record Loom demo (90 sec, prod-DB block) before merging

## Out of Scope (for follow-on plans)

- **Edit/Write/MultiEdit hook coverage** — v2; same hook binary, new matchers.
- **Session-batched receipts** — currently one Receipt per Bash call. Batching
  to one Receipt per CC session is v1.1.
- **MCP server for Cursor / Codex / Cline** — separate plan, ~2 weeks.
- **Cloud activity feed dashboard for teams** — paid-tier upgrade hook.
- **Rollback for Bash commands** — generally infeasible (shell side effects);
  defer until we have a real ShellConnector with structured rollback_data.
