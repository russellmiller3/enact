"""
Receipt writer — builds and HMAC-SHA256 signs audit receipts.
"""
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

from enact.models import Receipt, PolicyResult, ActionResult


def build_receipt(
    workflow: str,
    actor_email: str,
    payload: dict,
    policy_results: list[PolicyResult],
    decision: str,
    actions_taken: list[ActionResult] | None = None,
) -> Receipt:
    """Build a Receipt with timestamp. Signature is empty until sign() is called."""
    return Receipt(
        workflow=workflow,
        actor_email=actor_email,
        payload=payload,
        policy_results=policy_results,
        decision=decision,
        actions_taken=actions_taken or [],
        timestamp=datetime.now(timezone.utc).isoformat(),
        signature="",
    )


def sign_receipt(receipt: Receipt, secret: str) -> Receipt:
    """
    HMAC-SHA256 sign the receipt.
    The signature covers: run_id + workflow + actor + decision + timestamp.
    Returns a new Receipt with the signature field set.
    """
    message = f"{receipt.run_id}:{receipt.workflow}:{receipt.actor_email}:{receipt.decision}:{receipt.timestamp}"
    sig = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return receipt.model_copy(update={"signature": sig})


def verify_signature(receipt: Receipt, secret: str) -> bool:
    """Verify that a receipt's signature is valid."""
    message = f"{receipt.run_id}:{receipt.workflow}:{receipt.actor_email}:{receipt.decision}:{receipt.timestamp}"
    expected = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(receipt.signature, expected)


def write_receipt(receipt: Receipt, directory: str = "receipts") -> str:
    """Write receipt to JSON file. Returns the file path."""
    os.makedirs(directory, exist_ok=True)
    filename = f"{receipt.run_id}.json"
    filepath = os.path.join(directory, filename)
    with open(filepath, "w") as f:
        json.dump(receipt.model_dump(), f, indent=2)
    return filepath
