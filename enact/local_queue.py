"""
Local receipt queue for offline resilience.

When the cloud is unreachable, receipts are queued locally and pushed later.
This ensures agents keep working even if Enact Cloud is down.

How it works:
1. If cloud push fails, save receipt to local queue (JSON file)
2. On next successful push, also drain the queue
3. Queue files are stored in <receipt_dir>/queue/

Queue file format:
    <receipt_dir>/queue/<timestamp>_<run_id>.json

Each file contains the encrypted payload (or full receipt if no encryption).
"""

import json
import os
import time
from pathlib import Path
from typing import Any


def get_queue_dir(receipt_dir: str) -> Path:
    """Get or create the queue directory."""
    queue_dir = Path(receipt_dir) / "queue"
    queue_dir.mkdir(parents=True, exist_ok=True)
    return queue_dir


def enqueue_receipt(
    receipt_dir: str,
    metadata: dict[str, Any],
    payload_blob: str | None = None,
    full_receipt: dict[str, Any] | None = None,
) -> Path:
    """
    Save a receipt to the local queue for later retry.

    Args:
        receipt_dir   — base receipt directory
        metadata       — searchable metadata (always saved)
        payload_blob  — encrypted payload (if using encryption)
        full_receipt  — full receipt dict (if NOT using encryption)

    Returns:
        Path to the queued file
    """
    queue_dir = get_queue_dir(receipt_dir)
    timestamp = int(time.time() * 1000)
    run_id = metadata.get("run_id", "unknown")
    filename = f"{timestamp}_{run_id}.json"

    queue_entry = {
        "metadata": metadata,
        "queued_at": timestamp,
    }

    if payload_blob:
        queue_entry["payload_blob"] = payload_blob
        queue_entry["encrypted"] = True
    elif full_receipt:
        queue_entry["receipt"] = full_receipt
        queue_entry["encrypted"] = False

    filepath = queue_dir / filename
    with open(filepath, "w") as f:
        json.dump(queue_entry, f)

    return filepath


def get_queued_receipts(receipt_dir: str) -> list[Path]:
    """
    Get all queued receipt files, oldest first.

    Returns:
        List of Path objects for queued JSON files
    """
    queue_dir = get_queue_dir(receipt_dir)
    files = sorted(queue_dir.glob("*.json"))
    return files


def load_queued_receipt(filepath: Path) -> dict[str, Any]:
    """Load a queued receipt from disk."""
    with open(filepath, "r") as f:
        return json.load(f)


def remove_queued_receipt(filepath: Path) -> None:
    """Remove a queued receipt after successful push."""
    filepath.unlink(missing_ok=True)


def drain_queue(
    receipt_dir: str,
    push_fn: callable,
    max_retries: int = 10,
) -> tuple[int, int]:
    """
    Attempt to push all queued receipts.

    Args:
        receipt_dir  — base receipt directory
        push_fn      — function to call: push_fn(metadata, payload_blob=None, full_receipt=None) -> dict
        max_retries  — max receipts to attempt (prevents infinite loops)

    Returns:
        (success_count, failure_count)
    """
    queued = get_queued_receipts(receipt_dir)
    success = 0
    failure = 0

    for filepath in queued[:max_retries]:
        try:
            entry = load_queued_receipt(filepath)

            if entry.get("encrypted"):
                push_fn(
                    metadata=entry["metadata"],
                    payload_blob=entry["payload_blob"],
                )
            else:
                push_fn(
                    metadata=entry["metadata"],
                    full_receipt=entry["receipt"],
                )

            remove_queued_receipt(filepath)
            success += 1
        except Exception:
            # Leave it in the queue for next time
            failure += 1
            continue

    return success, failure