"""
API key authentication for Enact Cloud.

Keys are random 32-char strings (prefix: enact_live_).
Only the SHA-256 hash is stored in the DB — same as how GitHub stores PATs.

Usage:
    team_id = resolve_api_key("enact_live_abc123...")
    # raises HTTPException(401) if invalid
"""
import hashlib
from fastapi import Header, HTTPException
from cloud.db import db


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def resolve_api_key(x_enact_api_key: str = Header(...)) -> str:
    """
    FastAPI dependency. Resolves X-Enact-Api-Key header to a team_id.
    Raises 401 if key not found.
    """
    key_hash = hash_key(x_enact_api_key)
    with db() as conn:
        row = conn.execute(
            "SELECT team_id FROM api_keys WHERE key_hash = ?", (key_hash,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return row["team_id"]


def create_api_key(team_id: str, raw_key: str, label: str | None = None):
    """
    Store a new API key for a team. Call this directly in admin scripts.
    Never store the raw key — only the hash.
    """
    key_hash = hash_key(raw_key)
    with db() as conn:
        conn.execute(
            "INSERT INTO api_keys (key_hash, team_id, label) VALUES (?, ?, ?)",
            (key_hash, team_id, label),
        )
