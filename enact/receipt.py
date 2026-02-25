"""
Receipt writer — builds, HMAC-SHA256 signs, verifies, and writes audit receipts.

Why HMAC instead of plain SHA256?
-----------------------------------
A plain hash (SHA256) lets anyone compute the expected hash from the receipt
contents — so a tampered receipt can simply be re-hashed to produce a valid
"signature". HMAC requires knowledge of the secret key, so an attacker who
can modify a receipt on disk cannot recompute a valid signature without the key.

What fields are covered by the signature?
------------------------------------------
The signature covers ALL receipt fields via JSON canonicalization:
    run_id, workflow, actor_email, decision, timestamp,
    payload, policy_results, actions_taken

If ANY field is changed after signing, verify_signature() returns False.
The payload and policy_results are serialised using sorted-key JSON for
deterministic canonicalization. This prevents an attacker from modifying
what actions were attempted or concealing that policies failed.

Why model_copy instead of in-place mutation?
---------------------------------------------
Pydantic v2 models are effectively immutable. sign_receipt() returns a brand
new Receipt with the signature field set rather than modifying the original.
This is consistent with the functional style used throughout Enact and means
the unsigned receipt is still available if the caller needs it.

Why hmac.compare_digest instead of ==?
----------------------------------------
Plain string equality (signature == expected) is vulnerable to timing attacks
in theory — the comparison may return early as soon as a byte differs, leaking
information about how close the attacker's guess is. hmac.compare_digest always
takes the same time regardless of where strings diverge, making timing attacks
infeasible.
"""
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from enact.models import Receipt, PolicyResult, ActionResult


# UUID v4 pattern — the only valid format for run_id.
# Rejects any string containing path traversal characters (../, ..\, /, \).
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def _validate_run_id(run_id: str) -> None:
    """
    Validate that run_id is a legitimate UUID v4 hex string.

    Prevents path traversal attacks where a malicious run_id like
    "../../etc/passwd" could read or write arbitrary files. Two-layer defense:
    the regex rejects anything that isn't a UUID, and callers additionally
    verify the resolved path stays inside the target directory.

    Raises:
        ValueError — if run_id doesn't match UUID v4 format
    """
    if not _UUID_PATTERN.match(run_id):
        raise ValueError(
            f"Invalid run_id: {run_id!r}. "
            "Must be a valid UUID (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)."
        )


def build_receipt(
    workflow: str,
    actor_email: str,
    payload: dict,
    policy_results: list[PolicyResult],
    decision: str,
    actions_taken: list[ActionResult] | None = None,
) -> Receipt:
    """
    Build a Receipt with a UTC timestamp. Signature field is empty ("") until
    sign_receipt() is called — the receipt must be signed before writing to disk.

    Args:
        workflow        — name of the workflow that was invoked
        actor_email     — identity of the caller
        payload         — the input payload passed to run()
        policy_results  — full list from evaluate_all(), including failures
        decision        — "PASS" or "BLOCK"
        actions_taken   — list of ActionResults from the workflow (None → [] for BLOCK)

    Returns:
        Receipt — with signature="" (unsigned); call sign_receipt() next
    """
    return Receipt(
        workflow=workflow,
        actor_email=actor_email,
        payload=payload,
        policy_results=policy_results,
        decision=decision,
        actions_taken=actions_taken or [],
        # Timestamp is set here once and never changed — it's part of the signature message.
        timestamp=datetime.now(timezone.utc).isoformat(),
        signature="",  # Populated by sign_receipt()
    )


def _build_signature_message(receipt: Receipt) -> str:
    """
    Build the canonical string that gets HMAC-signed.

    Covers ALL receipt fields: the five identity fields plus payload,
    policy_results, and actions_taken. JSON canonicalization (sorted keys,
    compact separators) ensures deterministic output regardless of dict
    insertion order.

    Previous versions only signed identity fields (run_id, workflow, actor_email,
    decision, timestamp). This left payload and policy_results modifiable without
    invalidating the signature — a tamper risk for forensic investigation.
    """
    canon = lambda obj: json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return (
        f"{receipt.run_id}:{receipt.workflow}:{receipt.actor_email}"
        f":{receipt.decision}:{receipt.timestamp}"
        f":{canon(receipt.payload)}"
        f":{canon([pr.model_dump() for pr in receipt.policy_results])}"
        f":{canon([a.model_dump() for a in receipt.actions_taken])}"
    )


def sign_receipt(receipt: Receipt, secret: str) -> Receipt:
    """
    HMAC-SHA256 sign the receipt and return a new Receipt with signature set.

    The signature covers ALL receipt fields via JSON canonicalization:
    run_id, workflow, actor_email, decision, timestamp, payload,
    policy_results, and actions_taken. Any modification invalidates
    the signature.

    Args:
        receipt — unsigned receipt from build_receipt()
        secret  — HMAC secret key; use ENACT_SECRET env var or a per-deployment key

    Returns:
        Receipt — new instance with signature field set to a 64-char hex digest
    """
    message = _build_signature_message(receipt)
    sig = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    # model_copy returns a new Pydantic model; does not mutate the original.
    return receipt.model_copy(update={"signature": sig})


def verify_signature(receipt: Receipt, secret: str) -> bool:
    """
    Verify that a receipt's signature matches what sign_receipt() would produce.

    Recomputes the expected HMAC from ALL receipt fields and compares
    using hmac.compare_digest (constant-time) to prevent timing attacks.

    Args:
        receipt — Receipt loaded from disk or received from another system
        secret  — the same secret key used when signing

    Returns:
        bool — True if signature is valid, False if tampered or wrong key
    """
    message = _build_signature_message(receipt)
    expected = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    # compare_digest is constant-time, preventing timing-based signature oracle attacks.
    return hmac.compare_digest(receipt.signature, expected)


def write_receipt(receipt: Receipt, directory: str = "receipts") -> str:
    """
    Serialise the receipt to a JSON file and write it to disk.

    The filename is the receipt's run_id (a UUID), so filenames are unique
    and sortable. The directory is created if it doesn't exist (os.makedirs
    with exist_ok=True is safe to call repeatedly).

    Security: validates run_id is a UUID and the resolved path stays inside
    the target directory. Prevents path traversal via crafted run_ids.

    Args:
        receipt   — signed receipt; should have signature != "" before calling this
        directory — path to write JSON files (default: "receipts/" in cwd)

    Returns:
        str — absolute or relative path to the written file

    Raises:
        ValueError — if run_id is not a valid UUID (path traversal protection)
    """
    _validate_run_id(receipt.run_id)
    os.makedirs(directory, exist_ok=True)
    filename = f"{receipt.run_id}.json"
    filepath = os.path.join(directory, filename)
    # Belt-and-suspenders: verify resolved path stays inside the directory
    resolved = Path(filepath).resolve()
    dir_resolved = Path(directory).resolve()
    if not str(resolved).startswith(str(dir_resolved)):
        raise ValueError(f"Path traversal detected: {filepath} escapes {directory}")
    with open(filepath, "w") as f:
        # indent=2 keeps files human-readable for manual audit inspection.
        json.dump(receipt.model_dump(), f, indent=2)
    return filepath


def load_receipt(run_id: str, directory: str = "receipts") -> Receipt:
    """
    Load a previously written receipt from disk by its run_id.

    Security: validates run_id is a UUID before constructing the file path.
    Prevents path traversal via crafted run_ids like "../../etc/passwd".

    Args:
        run_id    — the UUID run_id used as the filename (without .json extension)
        directory — directory to read from (must match the directory used in write_receipt)

    Returns:
        Receipt — validated Pydantic model

    Raises:
        ValueError        — if run_id is not a valid UUID (path traversal protection)
        FileNotFoundError — if no receipt file exists for the given run_id
    """
    _validate_run_id(run_id)
    filepath = os.path.join(directory, f"{run_id}.json")
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"No receipt found for run_id: {run_id}")
    with open(filepath) as f:
        return Receipt.model_validate(json.load(f))
