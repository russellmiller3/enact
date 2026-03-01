"""
HMAC-signed tokens for HITL approval/denial links.

Token format: hmac_sha256(CLOUD_SECRET, "{hitl_id}:{action}")[:32]
Action is "approve" or "deny".

These tokens go in email URLs. They're single-use-safe because the DB
transition is idempotent — approving an already-approved request is a no-op.
"""
import hmac
import hashlib
import os


def make_token(hitl_id: str, action: str) -> str:
    secret = os.environ.get("CLOUD_SECRET", "")
    if not secret:
        raise RuntimeError("CLOUD_SECRET env var is not set")
    msg = f"{hitl_id}:{action}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()[:32]


def verify_token(token: str, hitl_id: str, action: str) -> bool:
    try:
        expected = make_token(hitl_id, action)
        return hmac.compare_digest(token, expected)
    except RuntimeError:
        return False
