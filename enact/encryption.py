"""
Zero-knowledge encryption for receipt payloads.

The core insight: split receipts into two parts:
  - METADATA (searchable, sent in clear): run_id, workflow, decision, timestamp
  - PAYLOAD (encrypted, unreadable by cloud): user_email, payload, policy_results, actions_taken

The cloud can index and search metadata but literally cannot read the payload
because it's encrypted with a key the customer controls.

Why AES-256-GCM?
----------------
- AES-256: NIST-approved, widely trusted, hardware-accelerated on most CPUs
- GCM (Galois/Counter Mode): authenticated encryption — detects tampering
- No need for separate HMAC; GCM provides integrity automatically
- Same model as 1Password, Proton Mail, Signal

Key management:
---------------
The user provides a 32-byte key (or we derive one from a passphrase).
The key NEVER leaves the customer's machine. Enact Cloud never sees it.

Usage:
    from enact.encryption import encrypt_payload, decrypt_payload

    key = derive_key("my-secret-passphrase")
    encrypted = encrypt_payload({"sensitive": "data"}, key)
    decrypted = decrypt_payload(encrypted, key)
"""

import base64
import hashlib
import json
import os
import secrets
from typing import Any


def derive_key(passphrase: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """
    Derive a 32-byte encryption key from a passphrase using PBKDF2.

    Returns (key, salt). Store the salt — you need it to derive the same key later.
    The salt is NOT secret; it just ensures the same passphrase produces different keys.

    Args:
        passphrase — user-provided secret string
        salt       — 16-byte salt (generates random if not provided)

    Returns:
        (32-byte key, 16-byte salt)
    """
    if salt is None:
        salt = secrets.token_bytes(16)
    elif len(salt) != 16:
        raise ValueError(f"Salt must be 16 bytes, got {len(salt)}")

    key = hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        iterations=100_000,  # OWASP recommendation as of 2023
        dklen=32,
    )
    return key, salt


def encrypt_payload(payload: dict[str, Any], key: bytes) -> str:
    """
    Encrypt a payload dict with AES-256-GCM.

    Returns a base64-encoded string containing: nonce (12 bytes) + ciphertext + tag (16 bytes).
    The nonce is random per-encryption, so the same payload encrypts differently each time.

    Args:
        payload — dict to encrypt (will be JSON-serialized)
        key     — 32-byte encryption key

    Returns:
        base64-encoded encrypted blob
    """
    if len(key) != 32:
        raise ValueError(f"Key must be 32 bytes for AES-256, got {len(key)}")

    # Serialize payload to JSON
    plaintext = json.dumps(payload, sort_keys=True).encode("utf-8")

    # Generate random nonce (12 bytes for GCM)
    nonce = secrets.token_bytes(12)

    # Encrypt using AES-256-GCM
    # We use the cryptography library if available, otherwise fall back to PyCryptodome
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)  # ciphertext includes tag
    except ImportError:
        try:
            from Crypto.Cipher import AES
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            ciphertext, tag = cipher.encrypt_and_digest(plaintext)
            ciphertext = ciphertext + tag  # append tag
        except ImportError:
            raise ImportError(
                "No AES-GCM implementation found. Install either:\n"
                "  pip install cryptography\n"
                "  pip install pycryptodome"
            )

    # Combine nonce + ciphertext and base64 encode
    encrypted = nonce + ciphertext
    return base64.b64encode(encrypted).decode("ascii")


def decrypt_payload(encrypted_b64: str, key: bytes) -> dict[str, Any]:
    """
    Decrypt a base64-encoded encrypted payload.

    Args:
        encrypted_b64 — base64 string from encrypt_payload()
        key           — 32-byte encryption key (must be the same key used to encrypt)

    Returns:
        Original payload dict
    """
    if len(key) != 32:
        raise ValueError(f"Key must be 32 bytes for AES-256, got {len(key)}")

    # Decode base64
    encrypted = base64.b64decode(encrypted_b64)

    # Extract nonce (first 12 bytes) and ciphertext+tag (rest)
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]

    # Decrypt using AES-256-GCM
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    except ImportError:
        try:
            from Crypto.Cipher import AES
            # GCM tag is last 16 bytes
            ct, tag = ciphertext[:-16], ciphertext[-16:]
            cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
            plaintext = cipher.decrypt_and_verify(ct, tag)
        except ImportError:
            raise ImportError(
                "No AES-GCM implementation found. Install either:\n"
                "  pip install cryptography\n"
                "  pip install pycryptodome"
            )

    # Deserialize JSON
    return json.loads(plaintext.decode("utf-8"))


def split_receipt_for_cloud(receipt_dict: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """
    Split a receipt into searchable metadata and encrypted payload.

    Metadata (sent in clear, searchable by cloud):
        - run_id
        - workflow
        - decision
        - timestamp
        - policy_names (list of policy names that ran, not results)

    Payload (encrypted, unreadable by cloud):
        - user_email
        - payload
        - policy_results (full details)
        - actions_taken
        - signature

    Args:
        receipt_dict — Receipt.model_dump() output

    Returns:
        (metadata_dict, encrypted_payload_b64)
    """
    # Metadata: what the cloud can see and search
    metadata = {
        "run_id": receipt_dict["run_id"],
        "workflow": receipt_dict["workflow"],
        "decision": receipt_dict["decision"],
        "timestamp": receipt_dict["timestamp"],
        # Just the policy names, not the full results (those may contain sensitive data)
        "policy_names": [pr["policy"] for pr in receipt_dict.get("policy_results", [])],
    }

    # Payload: everything sensitive
    payload = {
        "user_email": receipt_dict["user_email"],
        "payload": receipt_dict["payload"],
        "policy_results": receipt_dict.get("policy_results", []),
        "actions_taken": receipt_dict.get("actions_taken", []),
        "signature": receipt_dict.get("signature", ""),
    }

    return metadata, payload


def generate_encryption_key() -> bytes:
    """
    Generate a random 32-byte encryption key.

    Use this if the user doesn't want to provide a passphrase.
    Store the key securely — losing it means losing access to all encrypted receipts.
    """
    return secrets.token_bytes(32)
