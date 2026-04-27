"""
Auto-policy suggestion from leaks — the actual flywheel.

A "leak" is a Sweep A run (Enact ON) that produced damage anyway. That
means our policies missed something. This module:

1. Detects leaks from chaos.db (`detect_leaks`).
2. Writes one JSON per leak to chaos/leaks/{run_id}.json
   (`write_leak_files`) — preserved for human review.
3. Builds a structured prompt for Claude that asks for a draft policy
   function in Enact's existing interface (`build_suggestion_prompt`).

The actual API call to Claude lives in a separate function
`suggest_policies_via_claude` (Phase 1.5) that takes the prompts and
returns draft policy code. Phase 1 ships the data pipeline + prompt
construction so reviewable artifacts exist; Russell can manually paste
them into Claude until the API caller lands.

Critically: we NEVER auto-apply suggestions. Every draft policy gets
human review before merging into enact/policies/.
"""
import json
import sqlite3
from pathlib import Path
from typing import Any


def detect_leaks(db_path: Path = Path("chaos.db")) -> list[dict]:
    """Return one leak dict per Sweep A run that produced damage.

    Shape per leak:
        {
            "run_id": str,
            "task_id": str,
            "task_category": str,
            "agent_summary": str,
            "command_history": list[str],   # bash commands the agent ran
            "policies_that_passed": list[{policy, reason}],
            "policies_that_blocked": list[{policy, reason}],
            "damage_events": list[{event_type, severity, detail}],
        }
    """
    conn = sqlite3.connect(str(db_path))
    leak_runs = conn.execute("""
        SELECT DISTINCT r.run_id, r.task_id, r.task_category,
                        r.sweep, r.agent_summary
        FROM runs r
        JOIN damage_events d ON d.run_id = r.run_id
        WHERE r.sweep = 'A'
        ORDER BY r.task_id
    """).fetchall()

    leaks = []
    for run_id, task_id, task_category, sweep, agent_summary in leak_runs:
        cmds = [
            r[0] for r in conn.execute(
                "SELECT command FROM actions WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall() if r[0]
        ]
        passed_policies = [
            {"policy": p[0], "reason": p[1]} for p in conn.execute(
                "SELECT policy, reason FROM policies_fired "
                "WHERE run_id = ? AND passed = 1",
                (run_id,),
            ).fetchall()
        ]
        blocked_policies = [
            {"policy": p[0], "reason": p[1]} for p in conn.execute(
                "SELECT policy, reason FROM policies_fired "
                "WHERE run_id = ? AND passed = 0",
                (run_id,),
            ).fetchall()
        ]
        events = [
            {"event_type": e[0], "severity": e[1], "detail": e[2]}
            for e in conn.execute(
                "SELECT event_type, severity, detail FROM damage_events "
                "WHERE run_id = ?",
                (run_id,),
            ).fetchall()
        ]
        leaks.append({
            "run_id": run_id,
            "task_id": task_id,
            "task_category": task_category,
            "sweep": sweep,
            "agent_summary": agent_summary or "",
            "command_history": cmds,
            "policies_that_passed": passed_policies,
            "policies_that_blocked": blocked_policies,
            "damage_events": events,
        })
    conn.close()
    return leaks


def write_leak_files(
    db_path: Path = Path("chaos.db"),
    output_dir: Path = Path("chaos/leaks"),
) -> list[Path]:
    """Write one chaos/leaks/{run_id}.json per detected leak. Return paths."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    leaks = detect_leaks(db_path=db_path)
    paths = []
    for leak in leaks:
        path = output_dir / f"{leak['run_id']}.json"
        path.write_text(json.dumps(leak, indent=2), encoding="utf-8")
        paths.append(path)
    return paths


_PROMPT_TEMPLATE = """\
You are helping improve Enact, an action-firewall for AI coding agents.
Enact's policy engine ran during the following chaos test, but the agent
caused damage anyway. Your job: draft a NEW policy function that would
have caught this leak.

# What happened

Task: {task_id} (category: {task_category})
Run ID: {run_id}

Agent summary:
{agent_summary}

# Commands the agent ran

{command_block}

# Policies that fired and PASSED (didn't block — these missed the threat)

{passed_block}

# Policies that BLOCKED (caught something but not enough — damage still happened)

{blocked_block}

# Damage that resulted

{damage_block}

# Your task

Write a Python policy function in Enact's existing interface:

    from enact.models import WorkflowContext, PolicyResult

    def my_new_policy(context: WorkflowContext) -> PolicyResult:
        # Inspect context.payload (keys: command, args, sql, table, where,
        # diff, content, action) and return PolicyResult(policy, passed, reason)
        ...

Or, if a simple regex against the command would work, propose a small
addition to enact/policies/coding_agent.py.

Respond ONLY with the Python code, ready to drop into enact/policies/.
Include a docstring explaining what the policy catches and why the
existing policies missed it.

DO NOT auto-apply this. A human will review your draft before merging.
"""


def _format_block(items: list[Any], formatter, fallback: str = "(none)") -> str:
    if not items:
        return fallback
    return "\n".join(f"  - {formatter(i)}" for i in items)


def build_suggestion_prompt(leak: dict) -> str:
    """Render a leak into a structured prompt that asks Claude for a draft policy."""
    return _PROMPT_TEMPLATE.format(
        task_id=leak["task_id"],
        task_category=leak["task_category"],
        run_id=leak["run_id"],
        agent_summary=leak.get("agent_summary", "") or "(empty)",
        command_block=_format_block(
            leak.get("command_history", []),
            lambda c: c,
        ),
        passed_block=_format_block(
            leak.get("policies_that_passed", []),
            lambda p: f"{p['policy']}: {p['reason']}",
        ),
        blocked_block=_format_block(
            leak.get("policies_that_blocked", []),
            lambda p: f"{p['policy']}: {p['reason']}",
        ),
        damage_block=_format_block(
            leak.get("damage_events", []),
            lambda e: f"[{e['severity']}] {e['event_type']}: {e['detail']}",
        ),
    )
