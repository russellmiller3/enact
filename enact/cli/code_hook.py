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
import secrets as secrets_module
import sys
from pathlib import Path

from enact.models import WorkflowContext, ActionResult
from enact.policy import evaluate_all, all_passed
from enact.receipt import build_receipt, sign_receipt, write_receipt


DEFAULT_POLICIES_PY = '''\
"""Enact policies - edit to customize what the Agent Firewall blocks."""
from enact.policies.git import dont_force_push, dont_commit_api_keys
from enact.policies.db import protect_tables, block_ddl
from enact.policies.time import code_freeze_active
from enact.policies.coding_agent import CODING_AGENT_POLICIES
from enact.policies.filesystem import (
    dont_read_env,
    dont_touch_ci_cd,
    dont_edit_gitignore,
    dont_access_home_dir,
    dont_copy_api_keys,
)

# Defaults cover BOTH shell and file-tool surfaces:
#   SHELL (Bash):                 CODING_AGENT_POLICIES + git/db/time defaults
#   FILE TOOLS (Read/Write/Edit): filesystem path-based policies
#
# Same policy library across surfaces means an agent that tries to
# "cat .env" AND an agent that tries to Read ".env" are both blocked
# by the same dont_read_env policy - defense in depth, no surface gaps.
#
# CODING_AGENT_POLICIES blocks 23 documented real-world incident patterns
# (terraform destroy, drizzle force, aws s3 rm --recursive, kubectl delete
# namespace, etc.). See docs/research/agent-incidents.md for sources.
POLICIES = [
    code_freeze_active,
    block_ddl,
    dont_force_push,
    dont_commit_api_keys,
    protect_tables(["users", "customers", "orders", "payments", "audit_log"]),
    *CODING_AGENT_POLICIES,
    # File-path policies - fire on Read/Write/Edit (and Bash via diff/content)
    dont_read_env,
    dont_touch_ci_cd,
    dont_edit_gitignore,
    dont_access_home_dir,
    dont_copy_api_keys,
]
'''


# Light SQL extraction so existing policies fire on raw shell commands.
_PSQL_C_RE = re.compile(r'-c\s+["\']([^"\']+)["\']')
_TABLE_RE = re.compile(
    r'\b(?:DELETE\s+FROM|UPDATE|INSERT\s+INTO|TRUNCATE|DROP\s+TABLE)\s+["\']?(\w+)',
    re.IGNORECASE,
)
_WHERE_RE = re.compile(r'\bWHERE\b\s+(.+?)(?:\s*;|\s*$)', re.IGNORECASE | re.DOTALL)

# Inline-env-var run-id extractor. Subagents prefix bash commands with
# `ENACT_CHAOS_RUN_ID=<uuid> <cmd>` — that sets the var in the child shell
# but NOT in the hook's process. Parse it directly from the command text so
# per-run receipt scoping works without requiring the parent CC env to be set.
_RUN_ID_RE = re.compile(r'\bENACT_CHAOS_RUN_ID=([0-9a-f-]{8,})')


def _resolve_chaos_run_id(command: str) -> str | None:
    """Return chaos run id from os.environ first, then from inline cmd prefix."""
    env_id = os.environ.get("ENACT_CHAOS_RUN_ID")
    if env_id:
        return env_id
    m = _RUN_ID_RE.search(command or "")
    return m.group(1) if m else None


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


SUPPORTED_TOOLS = ("Bash", "Read", "Write", "Edit", "Glob", "Grep")


def parse_tool_input(tool_name: str, tool_input: dict) -> dict | None:
    """
    Map a Claude Code tool invocation into the payload shape policies expect.

    Returns None for unsupported tools or malformed input — caller should
    treat None as "fail open" (silent allow) to preserve the never-brick-CC
    invariant.

    Each tool's payload is shaped so existing policies fire correctly:
      Bash  -> command/args/diff/content (+ sql/table/where if psql)
      Read  -> path + rendered command for shell-pattern policies
      Write -> path + content (so dont_copy_api_keys catches keys in content)
      Edit  -> path + diff (old->new) so dont_commit_api_keys catches diff secrets
      Glob  -> path=pattern (so dont_access_home_dir fires) + glob_pattern
      Grep  -> grep_pattern (for block_grep_secret_patterns) + path
    """
    if tool_name == "Bash":
        command = tool_input.get("command") or ""
        if not command:
            return None
        return parse_bash_command(command)

    if tool_name == "Read":
        path = tool_input.get("file_path") or ""
        if not path:
            return None
        return {
            "path": path,
            "command": f"Read {path}",
            "diff": "",
            "content": "",
        }

    if tool_name == "Write":
        path = tool_input.get("file_path") or ""
        if not path:
            return None
        content = tool_input.get("content") or ""
        return {
            "path": path,
            "content": content,
            "command": f"Write {path}",
            # so dont_commit_api_keys (scans diff) catches secrets in the new file
            "diff": content,
        }

    if tool_name == "Edit":
        path = tool_input.get("file_path") or ""
        if not path:
            return None
        old = tool_input.get("old_string") or ""
        new = tool_input.get("new_string") or ""
        return {
            "path": path,
            "content": new,
            "diff": f"{old}\n->\n{new}",
            "command": f"Edit {path}",
        }

    if tool_name == "Glob":
        pattern = tool_input.get("pattern") or ""
        if not pattern:
            return None
        return {
            # path=pattern so dont_access_home_dir / block_glob_credentials_dirs fire
            "path": pattern,
            "glob_pattern": pattern,
            "command": f"Glob {pattern}",
            "diff": "",
            "content": "",
        }

    if tool_name == "Grep":
        pattern = tool_input.get("pattern") or ""
        if not pattern:
            return None
        path = tool_input.get("path") or ""
        return {
            "path": path,
            "grep_pattern": pattern,
            "command": f"Grep {pattern}" + (f" {path}" if path else ""),
            "diff": "",
            "content": "",
        }

    return None  # unknown tool — fail open


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
    settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    settings.setdefault("hooks", {})

    # One entry per supported tool (Bash, Read, Write, Edit, Glob, Grep) —
    # CC requires a separate matcher per tool name. Sorted for stable diffs.
    enact_pre_entries = [
        {"matcher": tool, "hooks": [{"type": "command", "command": "enact-code-hook pre"}]}
        for tool in sorted(SUPPORTED_TOOLS)
    ]
    enact_post_entries = [
        {"matcher": tool, "hooks": [{"type": "command", "command": "enact-code-hook post"}]}
        for tool in sorted(SUPPORTED_TOOLS)
    ]

    # Merge: strip ALL prior enact entries (idempotent re-init), keep user's
    # other-tool hooks, append fresh enact set.
    existing_pre = settings["hooks"].get("PreToolUse", [])
    existing_post = settings["hooks"].get("PostToolUse", [])
    settings["hooks"]["PreToolUse"] = (
        [e for e in existing_pre if not _is_enact_hook_entry(e)] + enact_pre_entries
    )
    settings["hooks"]["PostToolUse"] = (
        [e for e in existing_post if not _is_enact_hook_entry(e)] + enact_post_entries
    )
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")

    policies_path = enact_dir / "policies.py"
    if not policies_path.exists():
        # utf-8 explicit so non-ASCII chars in the docstring (em dashes etc.)
        # round-trip cleanly on Windows where the system default is cp1252.
        # Without this, the import in cmd_pre fails with SyntaxError and the
        # hook silently fail-opens — the bug is invisible until policies stop firing.
        policies_path.write_text(DEFAULT_POLICIES_PY, encoding="utf-8")

    secret_path = enact_dir / "secret"
    if not secret_path.exists():
        secret_path.write_text(secrets_module.token_hex(32), encoding="utf-8")
        secret_path.chmod(0o600)

    gitignore = cwd / ".gitignore"
    line = ".enact/\n"
    if gitignore.exists():
        contents = gitignore.read_text(encoding="utf-8")
        if ".enact/" not in contents:
            gitignore.write_text(contents.rstrip() + "\n" + line, encoding="utf-8")
    else:
        gitignore.write_text(line, encoding="utf-8")

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

        tool_name = event.get("tool_name", "")
        tool_input = event.get("tool_input", {}) or {}
        payload = parse_tool_input(tool_name, tool_input)
        if payload is None:
            return 0  # unsupported tool or malformed input - fail open

        # Stable command-like string for receipts even on non-Bash tools
        command = payload.get("command", "")
        workflow = f"tool.{tool_name.lower()}"

        context = WorkflowContext(
            workflow=workflow,
            user_email="claude-code@local",
            payload=payload,
        )
        results = evaluate_all(context, _load_policies())

        if all_passed(results):
            return 0  # silent allow

        failed = [r for r in results if not r.passed]
        reasons = "; ".join(f"{r.policy}: {r.reason}" for r in failed)
        plural = "y" if len(failed) == 1 else "ies"

        # Write a BLOCK receipt so downstream telemetry (chaos sweeps,
        # audit dashboards) can count denials. PostToolUse never fires
        # for blocked commands, so this is the only place to log them.
        secret_path = Path.cwd() / ".enact" / "secret"
        if secret_path.exists():
            try:
                secret = secret_path.read_text(encoding="utf-8").strip()
                receipt = build_receipt(
                    workflow=workflow,
                    user_email="claude-code@local",
                    payload={
                        "command": command,
                        "tool_name": tool_name,
                        "session_id": event.get("session_id", ""),
                    },
                    policy_results=results,
                    decision="BLOCK",
                    actions_taken=[],
                )
                receipt = sign_receipt(receipt, secret)
                chaos_run_id = _resolve_chaos_run_id(command)
                if chaos_run_id:
                    receipt_dir = str(Path("chaos") / "runs" / chaos_run_id / "receipts")
                else:
                    receipt_dir = "receipts"
                write_receipt(receipt, receipt_dir)
            except Exception:
                pass  # never let receipt-writing brick the deny

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

        tool_name = event.get("tool_name", "")
        if tool_name not in SUPPORTED_TOOLS:
            return 0

        secret_path = Path.cwd() / ".enact" / "secret"
        if not secret_path.exists():
            return 0  # not initialized - skip silently

        secret = secret_path.read_text(encoding="utf-8").strip()
        tool_input = event.get("tool_input", {}) or {}
        tool_response = event.get("tool_response") or {}
        parsed = parse_tool_input(tool_name, tool_input) or {}
        command = parsed.get("command", "")
        workflow = f"tool.{tool_name.lower()}"

        if tool_name == "Bash":
            # Bash uses the existing exit_code / interrupted signals
            exit_code = tool_response.get("exit_code", 0)
            interrupted = tool_response.get("interrupted", False) is True
            success = (exit_code == 0) and not interrupted
            action_output = {
                "command": command,
                "exit_code": exit_code,
                "interrupted": interrupted,
                "already_done": False,
            }
        else:
            # File/search tools: success unless tool_response carries an error
            success = "error" not in tool_response
            action_output = {
                "command": command,
                "path": parsed.get("path", ""),
                "already_done": False,
            }
            if "error" in tool_response:
                action_output["error"] = tool_response["error"]

        system_name = "shell" if tool_name == "Bash" else tool_name.lower()
        action_result = ActionResult(
            action=workflow,
            system=system_name,
            success=success,
            output=action_output,
        )

        payload = {
            "command": command,
            "tool_name": tool_name,
            "session_id": event.get("session_id", ""),
        }

        receipt = build_receipt(
            workflow=workflow,
            user_email="claude-code@local",
            payload=payload,
            policy_results=[],
            decision="PASS",
            actions_taken=[action_result],
        )
        receipt = sign_receipt(receipt, secret)
        # Per-run receipt scoping: env first, inline-prefix fallback so parallel
        # chaos sweeps work even when subagents set the var as a command prefix
        # (which never reaches the hook's own environment).
        chaos_run_id = _resolve_chaos_run_id(command)
        if chaos_run_id:
            receipt_dir = str(Path("chaos") / "runs" / chaos_run_id / "receipts")
        else:
            receipt_dir = "receipts"
        write_receipt(receipt, receipt_dir)
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
