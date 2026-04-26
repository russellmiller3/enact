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
import re
import secrets as secrets_module
import sys
from pathlib import Path


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
