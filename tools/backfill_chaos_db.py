"""
Backfill chaos.db from on-disk evidence.

Use case: a chaos sweep was dispatched but the parent never called
record_sweep() to flush telemetry. The runs/ table has rows with NULL
outcomes, the receipts/ dir has all the BLOCK / PASS records, and the
chaos/runs/<id>/agent_summary.txt files have the agent narratives.

This script does what record_sweep would have done, but with explicit
receipt-to-run attribution (via the ENACT_CHAOS_RUN_ID marker) so
top-level receipts/ files are correctly assigned even when per-run
receipt directories are empty.

Usage:
    python tools/backfill_chaos_db.py
    python tools/backfill_chaos_db.py --db chaos.db --runs-dir chaos/runs

Idempotent: only NULL-outcome rows are processed. Re-running on an
already-backfilled DB is a no-op.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make `enact` importable whether the script is run from repo root or tools/
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from enact.chaos.damage import assess_damage  # noqa: E402
from enact.chaos.runner import _compute_outcome  # noqa: E402
from enact.chaos.sandbox import SandboxHandle  # noqa: E402
from enact.chaos.telemetry import (  # noqa: E402
    init_db,
    write_action,
    write_damage_event,
    write_policy_fired,
    update_run_end,
    read_command_history,
)


# Match ENACT_CHAOS_RUN_ID=<uuid> in the receipt's payload.command. The
# chaos harness embeds this marker as either an env-var prefix or an
# `export` statement so receipts can be attributed back to their run.
RUN_ID_MARKER_RE = re.compile(
    r"ENACT_CHAOS_RUN_ID[= ]([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
PATH_RUN_ID_RE = re.compile(
    r"chaos[/\\]runs[/\\]([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


def find_run_id_for_receipt(receipt: dict) -> str | None:
    """Extract the chaos run_id this receipt belongs to, if any.

    Looks at:
      1. payload.command — chaos harness embeds ENACT_CHAOS_RUN_ID=<uuid>
      2. payload.file_path — file-tool calls have paths under chaos/runs/<id>/
      3. any string field containing the marker (last-ditch)
    """
    payload = receipt.get("payload") or {}

    cmd = payload.get("command", "") or ""
    m = RUN_ID_MARKER_RE.search(cmd)
    if m:
        return m.group(1)
    m = PATH_RUN_ID_RE.search(cmd)
    if m:
        return m.group(1)

    fp = payload.get("file_path", "") or ""
    if fp:
        m = PATH_RUN_ID_RE.search(fp)
        if m:
            return m.group(1)

    for v in payload.values():
        if isinstance(v, str):
            m = RUN_ID_MARKER_RE.search(v) or PATH_RUN_ID_RE.search(v)
            if m:
                return m.group(1)
    return None


def gather_receipts_by_run(repo_root: Path) -> dict[str, list[Path]]:
    """Walk receipts/*.json + chaos/runs/*/receipts/*.json. Group by run_id.

    Per-run receipts directories are authoritative (the dir name IS the
    run_id). Top-level receipts/ are attributed by ENACT_CHAOS_RUN_ID
    marker in the receipt body.
    """
    by_run: dict[str, list[Path]] = {}

    runs_dir = repo_root / "chaos" / "runs"
    if runs_dir.exists():
        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            receipts_dir = run_dir / "receipts"
            if not receipts_dir.exists():
                continue
            run_id = run_dir.name
            for r in receipts_dir.glob("*.json"):
                by_run.setdefault(run_id, []).append(r)

    top_receipts = repo_root / "receipts"
    if top_receipts.exists():
        for r in top_receipts.glob("*.json"):
            try:
                data = json.loads(r.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            run_id = find_run_id_for_receipt(data)
            if run_id:
                by_run.setdefault(run_id, []).append(r)

    return by_run


def ingest_one_receipt(
    conn: sqlite3.Connection,
    run_id: str,
    receipt_path: Path,
) -> tuple[int, int]:
    """Write one receipt's actions + policies into the DB.

    Returns (n_actions_written, n_blocks_written).
    """
    try:
        r = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return (0, 0)

    payload = r.get("payload") or {}
    tool_name = payload.get("tool_name", "Bash") or "Bash"
    cmd = payload.get("command") or payload.get("file_path") or ""

    actions_written = 0
    blocks_written = 0

    # PASS receipts have actions_taken with the executed commands
    for a in r.get("actions_taken") or []:
        output = a.get("output") or {}
        cmd_a = output.get("command", "") or cmd
        write_action(
            conn, run_id,
            tool_name=tool_name,
            command=cmd_a,
            blocked=False,
            block_reason=None,
        )
        actions_written += 1

    # policy_results — record every check, passed or failed
    for p in r.get("policy_results") or []:
        passed = bool(p.get("passed"))
        write_policy_fired(
            conn, run_id,
            policy=p.get("policy", ""),
            passed=passed,
            reason=p.get("reason", ""),
        )

    # BLOCK receipts: record the attempted action as blocked so damage
    # rules can distinguish "agent did it" vs "agent attempted, blocked"
    if r.get("decision") == "BLOCK":
        failed = [
            p for p in (r.get("policy_results") or [])
            if not p.get("passed")
        ]
        reason = "; ".join(
            f"{p.get('policy')}: {p.get('reason', '')}" for p in failed
        )
        write_action(
            conn, run_id,
            tool_name=tool_name,
            command=cmd,
            blocked=True,
            block_reason=reason,
        )
        blocks_written += 1

    return (actions_written, blocks_written)


def reconstruct_handle(run_dir: Path, run_id: str) -> SandboxHandle | None:
    """Build a minimal SandboxHandle from on-disk run dir for damage assessment.

    Returns None if the run dir is missing or the initial-state snapshot
    can't be loaded.
    """
    if not run_dir.exists():
        return None
    chaos_dir = run_dir.parent
    state_path = chaos_dir / ".state" / f"{run_id}.json"
    initial_state = {}
    if state_path.exists():
        try:
            initial_state = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return SandboxHandle(
        run_id=run_id,
        run_dir=run_dir,
        db_path=run_dir / "fake_db.sqlite",
        repo_path=run_dir / "fake_repo",
        bin_dir=run_dir / "bin",
        state_path=state_path,
        initial_state=initial_state,
    )


def backfill(repo_root: Path, db_path: Path) -> dict:
    """Process every NULL-outcome run: ingest receipts, run damage rules,
    compute outcome, write_end."""
    by_run = gather_receipts_by_run(repo_root)

    conn = init_db(str(db_path))
    null_runs = conn.execute(
        "SELECT run_id, run_dir, sweep, task_id FROM runs "
        "WHERE outcome IS NULL"
    ).fetchall()

    summary = {
        "null_runs_found": len(null_runs),
        "runs_backfilled": 0,
        "receipts_attributed": 0,
        "outcomes": {},
        "unattributed_top_receipts": 0,
    }

    # Quick stat: receipts in top-level receipts/ that have no run_id match
    top_receipts = repo_root / "receipts"
    attributed_paths: set[Path] = set()
    for paths in by_run.values():
        attributed_paths.update(paths)
    if top_receipts.exists():
        for r in top_receipts.glob("*.json"):
            if r not in attributed_paths:
                summary["unattributed_top_receipts"] += 1

    print(f"Found {len(null_runs)} runs with NULL outcome.")
    print(
        f"Found {summary['unattributed_top_receipts']} top-level receipts "
        "with no matching run_id (likely test fixtures or HITL synthetics)."
    )
    print()

    for run_id, run_dir, sweep, task_id in null_runs:
        receipts = by_run.get(run_id, [])
        # Ingest each receipt's actions + policies
        for r_path in receipts:
            ingest_one_receipt(conn, run_id, r_path)
            summary["receipts_attributed"] += 1

        # Read agent summary
        run_dir_path = Path(run_dir)
        agent_summary = ""
        summary_file = run_dir_path / "agent_summary.txt"
        if summary_file.exists():
            try:
                agent_summary = summary_file.read_text(
                    encoding="utf-8", errors="replace"
                )
            except OSError:
                pass

        # Run damage rules against the reconstructed sandbox
        handle = reconstruct_handle(run_dir_path, run_id)
        if handle is not None:
            history = read_command_history(conn, run_id)
            try:
                events = assess_damage(handle, history)
                for e in events:
                    write_damage_event(
                        conn, run_id, e.event_type, e.severity, e.detail
                    )
            except Exception as exc:
                print(f"  WARN: damage assessment failed for {run_id[:8]}: {exc}")

        # Compute outcome and finalize the run row
        outcome = _compute_outcome(conn, run_id, agent_summary)
        ended_at = datetime.now(timezone.utc).isoformat()
        update_run_end(conn, run_id, ended_at, agent_summary, outcome=outcome)

        summary["runs_backfilled"] += 1
        summary["outcomes"][outcome] = summary["outcomes"].get(outcome, 0) + 1
        print(
            f"  {run_id[:8]} | task={task_id} sweep={sweep} | "
            f"receipts={len(receipts)} | outcome={outcome}"
        )

    conn.close()
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="chaos.db", help="Path to chaos.db")
    p.add_argument(
        "--repo-root", default=".",
        help="Repo root (used to locate receipts/ + chaos/runs/)",
    )
    args = p.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    db_path = (
        (repo_root / args.db)
        if not Path(args.db).is_absolute() else Path(args.db)
    )

    print(f"Backfilling {db_path} from on-disk evidence under {repo_root}")
    print(f"  receipts dir: {repo_root / 'receipts'}")
    print(f"  runs dir:     {repo_root / 'chaos' / 'runs'}")
    print()

    summary = backfill(repo_root, db_path)

    print()
    print("Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
