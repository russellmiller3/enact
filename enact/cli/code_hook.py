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
import re


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
