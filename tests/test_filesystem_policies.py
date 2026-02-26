"""
Tests for filesystem safety policies (enact/policies/filesystem.py).

All policies are pure functions over WorkflowContext — no filesystem access needed.
"""
import pytest
from enact.policies.filesystem import dont_delete_file, restrict_paths, block_extensions
from enact.models import WorkflowContext


def make_context(payload=None):
    return WorkflowContext(
        workflow="test",
        actor_email="agent@test.com",
        payload=payload or {},
        systems={},
    )


# ── dont_delete_file ─────────────────────────────────────────────────────────────

class TestNoDeleteFile:
    def test_always_blocks(self):
        ctx = make_context()
        result = dont_delete_file(ctx)
        assert result.passed is False

    def test_blocks_even_with_path(self):
        ctx = make_context({"path": "logs/old.log"})
        result = dont_delete_file(ctx)
        assert result.passed is False

    def test_reason_mentions_deletion(self):
        ctx = make_context()
        result = dont_delete_file(ctx)
        assert "deletion" in result.reason.lower()

    def test_policy_name(self):
        ctx = make_context()
        result = dont_delete_file(ctx)
        assert result.policy == "dont_delete_file"


# ── restrict_paths ─────────────────────────────────────────────────────────────

class TestRestrictPaths:
    def test_blocks_path_outside_allowed_dirs(self):
        policy = restrict_paths(["/workspace/project"])
        ctx = make_context({"path": "/etc/passwd"})
        result = policy(ctx)
        assert result.passed is False

    def test_allows_path_inside_allowed_dir(self):
        policy = restrict_paths(["/workspace/project"])
        ctx = make_context({"path": "/workspace/project/src/main.py"})
        result = policy(ctx)
        assert result.passed is True

    def test_allows_path_in_any_of_multiple_allowed_dirs(self):
        policy = restrict_paths(["/workspace/project", "/tmp/scratch"])
        ctx = make_context({"path": "/tmp/scratch/notes.txt"})
        result = policy(ctx)
        assert result.passed is True

    def test_blocks_traversal_that_escapes_allowed_dir(self):
        policy = restrict_paths(["/workspace/project"])
        ctx = make_context({"path": "/workspace/project/../../etc/passwd"})
        result = policy(ctx)
        assert result.passed is False

    def test_missing_path_passes(self):
        """No path in payload → can't determine target → pass through."""
        policy = restrict_paths(["/workspace"])
        ctx = make_context({})
        result = policy(ctx)
        assert result.passed is True

    def test_reason_mentions_path_on_block(self):
        policy = restrict_paths(["/workspace"])
        ctx = make_context({"path": "/etc/passwd"})
        result = policy(ctx)
        assert "/etc/passwd" in result.reason

    def test_policy_name(self):
        policy = restrict_paths(["/workspace"])
        ctx = make_context({"path": "/workspace/file.txt"})
        result = policy(ctx)
        assert result.policy == "restrict_paths"

    def test_empty_allowed_list_blocks_everything(self):
        """No allowed dirs → nothing is allowed."""
        policy = restrict_paths([])
        ctx = make_context({"path": "/workspace/file.txt"})
        result = policy(ctx)
        assert result.passed is False


# ── block_extensions ───────────────────────────────────────────────────────────

class TestBlockExtensions:
    def test_blocks_blocked_extension(self):
        policy = block_extensions([".env", ".key", ".pem"])
        ctx = make_context({"path": "/workspace/.env"})
        result = policy(ctx)
        assert result.passed is False

    def test_blocks_key_file(self):
        policy = block_extensions([".env", ".key", ".pem"])
        ctx = make_context({"path": "/workspace/id_rsa.key"})
        result = policy(ctx)
        assert result.passed is False

    def test_allows_safe_extension(self):
        policy = block_extensions([".env", ".key", ".pem"])
        ctx = make_context({"path": "/workspace/main.py"})
        result = policy(ctx)
        assert result.passed is True

    def test_extension_check_is_case_insensitive(self):
        """Block .ENV as well as .env."""
        policy = block_extensions([".env"])
        ctx = make_context({"path": "/workspace/.ENV"})
        result = policy(ctx)
        assert result.passed is False

    def test_missing_path_passes(self):
        policy = block_extensions([".env"])
        ctx = make_context({})
        result = policy(ctx)
        assert result.passed is True

    def test_reason_mentions_extension_on_block(self):
        policy = block_extensions([".env"])
        ctx = make_context({"path": "/workspace/.env"})
        result = policy(ctx)
        assert ".env" in result.reason

    def test_policy_name(self):
        policy = block_extensions([".env"])
        ctx = make_context({"path": "/workspace/ok.txt"})
        result = policy(ctx)
        assert result.policy == "block_extensions"

    def test_empty_blocked_list_allows_everything(self):
        policy = block_extensions([])
        ctx = make_context({"path": "/workspace/.env"})
        result = policy(ctx)
        assert result.passed is True
