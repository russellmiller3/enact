"""Tests for zero-knowledge encryption."""

import pytest
from enact.encryption import (
    derive_key,
    encrypt_payload,
    decrypt_payload,
    split_receipt_for_cloud,
    generate_encryption_key,
)


def test_derive_key_deterministic():
    """Same passphrase + salt = same key."""
    key1, salt = derive_key("my-secret-passphrase")
    key2, _ = derive_key("my-secret-passphrase", salt)
    assert key1 == key2
    assert len(key1) == 32
    assert len(salt) == 16


def test_derive_key_different_salts():
    """Different salts = different keys (same passphrase)."""
    key1, _ = derive_key("my-secret-passphrase")
    key2, _ = derive_key("my-secret-passphrase")
    assert key1 != key2  # Different salts produce different keys


def test_encrypt_decrypt_roundtrip():
    """Encrypt then decrypt = original payload."""
    key = generate_encryption_key()
    payload = {"user_email": "agent@company.com", "payload": {"sensitive": "data"}}
    
    encrypted = encrypt_payload(payload, key)
    decrypted = decrypt_payload(encrypted, key)
    
    assert decrypted == payload


def test_encrypt_different_each_time():
    """Same payload encrypts differently each time (random nonce)."""
    key = generate_encryption_key()
    payload = {"data": "same"}
    
    encrypted1 = encrypt_payload(payload, key)
    encrypted2 = encrypt_payload(payload, key)
    
    # Different ciphertexts (due to random nonce)
    assert encrypted1 != encrypted2
    # But both decrypt to the same payload
    assert decrypt_payload(encrypted1, key) == payload
    assert decrypt_payload(encrypted2, key) == payload


def test_encrypt_wrong_key_fails():
    """Decrypting with wrong key raises error."""
    key1 = generate_encryption_key()
    key2 = generate_encryption_key()  # Different key
    payload = {"secret": "data"}
    
    encrypted = encrypt_payload(payload, key1)
    
    with pytest.raises(Exception):  # cryptography raises InvalidTag
        decrypt_payload(encrypted, key2)


def test_split_receipt_for_cloud():
    """Split receipt into metadata and payload."""
    receipt = {
        "run_id": "abc-123",
        "workflow": "test_workflow",
        "decision": "PASS",
        "timestamp": "2026-03-05T00:00:00Z",
        "user_email": "agent@company.com",
        "payload": {"repo": "owner/repo"},
        "policy_results": [
            {"policy": "dont_push_to_main", "passed": True, "reason": "OK"}
        ],
        "actions_taken": [{"action": "create_pr", "success": True}],
        "signature": "abc123",
    }
    
    metadata, payload = split_receipt_for_cloud(receipt)
    
    # Metadata contains searchable fields
    assert metadata["run_id"] == "abc-123"
    assert metadata["workflow"] == "test_workflow"
    assert metadata["decision"] == "PASS"
    assert metadata["policy_names"] == ["dont_push_to_main"]
    
    # Payload contains sensitive fields
    assert payload["user_email"] == "agent@company.com"
    assert payload["payload"] == {"repo": "owner/repo"}
    assert len(payload["policy_results"]) == 1
    assert payload["signature"] == "abc123"


def test_generate_encryption_key():
    """Generated key is 32 bytes."""
    key = generate_encryption_key()
    assert len(key) == 32
    # Each call produces a different key
    key2 = generate_encryption_key()
    assert key != key2