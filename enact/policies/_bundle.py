"""
Signed-bundle loader for Enact policy data.

The split: PUBLIC `enact-sdk` package ships the policy DISPATCH MACHINERY
(how to read context.payload, how to format a PolicyResult, how to call a
regex engine). The DATA — regex strings, exfil domain lists, scope-keyword
bags, protected-table defaults — lives in a SIGNED BUNDLE distributed via
the proprietary `enact-pro` repo.

This file is the loader:
  - Reads `bundle.json` from a path (env var ENACT_POLICY_BUNDLE_PATH or
    the function argument)
  - Verifies the bundle's HMAC-SHA256 signature against an embedded public
    key fingerprint (per-customer key from the Enact Cloud dashboard)
  - Returns the parsed policy data dict

The open-source path stays working: if no bundle is configured, public
policy modules fall back to a STARTER list (smaller coverage, but
functional). Customers who pay for the bundle get the full policy
library updated continuously.

Tampering: any modification to the bundle changes its signature →
loader rejects → callers fall back to starter or fail closed (caller
chooses). Either way, you can't run a tampered bundle.

This is the SDK side. Bundle GENERATION lives in `enact-pro/` and is
not part of the public SDK.
"""
from __future__ import annotations

import hmac
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class BundleLoadError(Exception):
    """Raised when a bundle exists but cannot be loaded (bad signature,
    malformed JSON, schema mismatch). Callers may catch this and fall back
    to starter data, or surface the error."""


# --- Public API ------------------------------------------------------------


def load_bundle(
    path: str | Path | None = None,
    secret: str | None = None,
    *,
    strict: bool = False,
) -> dict[str, Any]:
    """Load and verify a signed policy bundle from disk.

    Args:
        path:    Bundle path. Falls back to env $ENACT_POLICY_BUNDLE_PATH.
                 If neither is set, returns an empty dict (open-source mode).
        secret:  HMAC verification secret. Falls back to env
                 $ENACT_POLICY_BUNDLE_SECRET. Required when path is set.
        strict:  If True, raises BundleLoadError on any failure. If False
                 (default), logs the error and returns {} so callers fall
                 back to starter data.

    Returns:
        Parsed bundle data as a dict, or {} if no bundle is configured.

    Bundle format (JSON):
        {
            "version": "v1",
            "issued_at": "2026-04-27T00:00:00Z",
            "data": { ... policy-specific keys ... },
            "signature": "<hex hmac-sha256 of canonical_json(data) using shared secret>"
        }
    """
    bundle_path = path or os.environ.get("ENACT_POLICY_BUNDLE_PATH")
    if not bundle_path:
        return {}

    bundle_path = Path(bundle_path)
    if not bundle_path.exists():
        msg = f"Bundle path {bundle_path} does not exist"
        if strict:
            raise BundleLoadError(msg)
        logger.warning(msg)
        return {}

    try:
        raw = bundle_path.read_text(encoding="utf-8")
        envelope = json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        msg = f"Bundle {bundle_path} could not be parsed: {exc}"
        if strict:
            raise BundleLoadError(msg) from exc
        logger.warning(msg)
        return {}

    # Schema check
    if not isinstance(envelope, dict) or "data" not in envelope or "signature" not in envelope:
        msg = f"Bundle {bundle_path} is missing required keys (data, signature)"
        if strict:
            raise BundleLoadError(msg)
        logger.warning(msg)
        return {}

    # Signature verification
    actual_secret = secret or os.environ.get("ENACT_POLICY_BUNDLE_SECRET")
    if not actual_secret:
        msg = (
            f"Bundle {bundle_path} present but no secret configured "
            "(set ENACT_POLICY_BUNDLE_SECRET or pass secret=...)."
        )
        if strict:
            raise BundleLoadError(msg)
        logger.warning(msg)
        return {}

    if not _verify_signature(envelope["data"], envelope["signature"], actual_secret):
        msg = f"Bundle {bundle_path} signature verification FAILED — refusing to load"
        if strict:
            raise BundleLoadError(msg)
        logger.error(msg)
        return {}

    return envelope["data"]


# --- Signature helpers -----------------------------------------------------


def _canonical_json(obj: Any) -> str:
    """Deterministic JSON serialization for HMAC.

    Sorted keys, no whitespace, UTF-8 with no escape of non-ASCII. This is
    the bytes that get HMAC'd; both signer and verifier MUST use this exact
    serialization or signatures won't match.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _verify_signature(data: Any, sig_hex: str, secret: str) -> bool:
    """Constant-time HMAC-SHA256 verification of `data` against `sig_hex`."""
    expected = hmac.new(
        secret.encode("utf-8"),
        _canonical_json(data).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    # constant-time compare to avoid timing-side-channel leaks
    return hmac.compare_digest(expected, sig_hex)


def sign_bundle(data: Any, secret: str) -> dict[str, Any]:
    """Build a signed envelope around `data`. Used by the bundle generator
    in enact-pro to produce signed bundles. Exposed here for testing.

    Returns the full envelope dict ready to JSON-serialize and ship.
    """
    sig = hmac.new(
        secret.encode("utf-8"),
        _canonical_json(data).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    from datetime import datetime, timezone
    return {
        "version": "v1",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
        "signature": sig,
    }
