"""
Chaos sweep orchestrator — one-shot setup + record across many tasks.

Eliminates the manual run_one → dispatch → record_run_result loop. Parent
CC session calls run_sweep() once to set up all sandboxes, dispatches
Agent tools in parallel, then calls record_sweep() once with all the
agent summaries to flush telemetry.

Phase 1 contract:
    1. Parent calls dispatches = run_sweep(tasks, sweep, ...)
    2. Parent dispatches one Agent tool per dispatch in PARALLEL
       (safe now that ENACT_CHAOS_RUN_ID scopes receipts per-run).
    3. Parent collects {run_id, agent_summary} for each.
    4. Parent calls results = record_sweep(summaries, ...) once.
    5. Parent calls reporter.generate_report().

Phase 2 (out of scope): replace the parent-LLM-dispatch with an
Anthropic-SDK loop so the entire sweep runs from a single Python script.
"""
import logging
import uuid
from pathlib import Path

from enact.chaos.runner import run_one, record_run_result
from enact.chaos.tasks import ChaosTask


def run_sweep(
    tasks: list[ChaosTask],
    sweep: str,
    chaos_dir: Path = Path("chaos/runs"),
    db_path: Path = Path("chaos.db"),
) -> list[dict]:
    """Set up sandboxes for all tasks. Return one dispatch dict per task.

    Each dispatch dict has the shape returned by run_one(): run_id, run_dir,
    subagent_prompt, pre_run_receipts, task_id, task_category. Parent CC
    session feeds subagent_prompt to its Agent tool (one per dispatch,
    safe to parallelize when ENACT_CHAOS_RUN_ID scopes receipts).
    """
    dispatches = []
    for task in tasks:
        run_id = str(uuid.uuid4())
        info = run_one(task, sweep=sweep, run_id=run_id,
                       chaos_dir=chaos_dir, db_path=db_path)
        dispatches.append(info)
    return dispatches


def record_sweep(
    summaries: list[dict],
    db_path: Path = Path("chaos.db"),
    chaos_dir: Path = Path("chaos/runs"),
) -> list[dict]:
    """Flush telemetry for every run in `summaries`.

    Each summary dict must have:
        run_id        — the chaos run UUID
        agent_summary — the subagent's final response text

    Optionally:
        pre_run_receipts — fallback set if per-run receipt dir is empty.
                           Defaults to empty set when not provided
                           (safe because per-run dir is the preferred path).

    Returns one result dict per summary with outcome + counts. Unknown
    run_ids log a warning and produce {"run_id": ..., "error": "..."}
    instead of crashing the whole sweep.
    """
    import sqlite3
    results = []
    for s in summaries:
        run_id = s.get("run_id")
        if not run_id:
            logging.warning("chaos.orchestrate: summary missing run_id; skipping")
            continue
        # Verify run exists in chaos.db before recording
        conn = sqlite3.connect(str(db_path))
        exists = conn.execute(
            "SELECT 1 FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        conn.close()
        if not exists:
            logging.warning(
                "chaos.orchestrate: run_id %s not in chaos.db; skipping", run_id
            )
            results.append({"run_id": run_id, "error": "unknown run_id"})
            continue

        try:
            result = record_run_result(
                run_id=run_id,
                agent_summary=s.get("agent_summary", ""),
                pre_run_receipts=s.get("pre_run_receipts", set()),
                db_path=db_path,
                chaos_dir=chaos_dir,
            )
            result["run_id"] = run_id
            results.append(result)
        except Exception as e:
            logging.warning(
                "chaos.orchestrate: record_run_result failed for %s: %s",
                run_id, e,
            )
            results.append({"run_id": run_id, "error": str(e)})
    return results
