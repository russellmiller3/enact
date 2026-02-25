"""
Tests for FilesystemConnector.

Uses pytest's tmp_path fixture for real I/O with automatic cleanup.
No mocks — the connector wraps stdlib, so we test the real thing.
"""
import pytest
from pathlib import Path
from enact.connectors.filesystem import FilesystemConnector


# ── helpers ───────────────────────────────────────────────────────────────────

def make_connector(tmp_path, allowed_actions=None):
    return FilesystemConnector(
        base_dir=str(tmp_path),
        allowed_actions=allowed_actions or ["read_file", "write_file", "delete_file", "list_dir"],
    )


# ── allowlist gate ─────────────────────────────────────────────────────────────

class TestAllowlist:
    def test_disallowed_action_raises(self, tmp_path):
        conn = FilesystemConnector(base_dir=str(tmp_path), allowed_actions=["read_file"])
        with pytest.raises(PermissionError):
            conn.write_file("notes.txt", "hello")

    def test_allowed_action_does_not_raise(self, tmp_path):
        conn = FilesystemConnector(base_dir=str(tmp_path), allowed_actions=["write_file"])
        result = conn.write_file("notes.txt", "hello")
        assert result.success is True


# ── write_file ─────────────────────────────────────────────────────────────────

class TestWriteFile:
    def test_creates_new_file(self, tmp_path):
        conn = make_connector(tmp_path)
        result = conn.write_file("hello.txt", "world")
        assert result.success is True
        assert (tmp_path / "hello.txt").read_text() == "world"

    def test_already_done_false_for_new_file(self, tmp_path):
        conn = make_connector(tmp_path)
        result = conn.write_file("new.txt", "content")
        assert result.output["already_done"] is False

    def test_overwrites_existing_file(self, tmp_path):
        conn = make_connector(tmp_path)
        (tmp_path / "file.txt").write_text("old")
        result = conn.write_file("file.txt", "new")
        assert result.success is True
        assert (tmp_path / "file.txt").read_text() == "new"

    def test_idempotent_write_same_content(self, tmp_path):
        conn = make_connector(tmp_path)
        (tmp_path / "file.txt").write_text("same")
        result = conn.write_file("file.txt", "same")
        assert result.output["already_done"] == "written"

    def test_rollback_data_stores_previous_content(self, tmp_path):
        conn = make_connector(tmp_path)
        (tmp_path / "file.txt").write_text("old content")
        result = conn.write_file("file.txt", "new content")
        assert result.rollback_data["previous_content"] == "old content"

    def test_rollback_data_none_for_new_file(self, tmp_path):
        conn = make_connector(tmp_path)
        result = conn.write_file("brand_new.txt", "hello")
        assert result.rollback_data["previous_content"] is None

    def test_action_and_system_fields(self, tmp_path):
        conn = make_connector(tmp_path)
        result = conn.write_file("f.txt", "x")
        assert result.action == "write_file"
        assert result.system == "filesystem"

    def test_path_traversal_blocked(self, tmp_path):
        conn = make_connector(tmp_path)
        result = conn.write_file("../escape.txt", "evil")
        assert result.success is False
        assert "outside" in result.output["error"].lower()

    def test_creates_subdirectory_if_needed(self, tmp_path):
        conn = make_connector(tmp_path)
        result = conn.write_file("subdir/notes.txt", "hello")
        assert result.success is True
        assert (tmp_path / "subdir" / "notes.txt").read_text() == "hello"


# ── read_file ──────────────────────────────────────────────────────────────────

class TestReadFile:
    def test_reads_existing_file(self, tmp_path):
        (tmp_path / "data.txt").write_text("the content")
        conn = make_connector(tmp_path)
        result = conn.read_file("data.txt")
        assert result.success is True
        assert result.output["content"] == "the content"

    def test_fails_for_missing_file(self, tmp_path):
        conn = make_connector(tmp_path)
        result = conn.read_file("missing.txt")
        assert result.success is False
        assert "error" in result.output

    def test_path_traversal_blocked(self, tmp_path):
        conn = make_connector(tmp_path)
        result = conn.read_file("../../etc/passwd")
        assert result.success is False
        assert "outside" in result.output["error"].lower()

    def test_action_and_system_fields(self, tmp_path):
        (tmp_path / "f.txt").write_text("x")
        conn = make_connector(tmp_path)
        result = conn.read_file("f.txt")
        assert result.action == "read_file"
        assert result.system == "filesystem"

    def test_no_rollback_data_for_read(self, tmp_path):
        (tmp_path / "f.txt").write_text("x")
        conn = make_connector(tmp_path)
        result = conn.read_file("f.txt")
        assert result.rollback_data == {}


# ── delete_file ────────────────────────────────────────────────────────────────

class TestDeleteFile:
    def test_deletes_existing_file(self, tmp_path):
        (tmp_path / "bye.txt").write_text("gone")
        conn = make_connector(tmp_path)
        result = conn.delete_file("bye.txt")
        assert result.success is True
        assert not (tmp_path / "bye.txt").exists()

    def test_already_done_if_file_missing(self, tmp_path):
        conn = make_connector(tmp_path)
        result = conn.delete_file("nonexistent.txt")
        assert result.success is True
        assert result.output["already_done"] == "deleted"

    def test_already_done_false_for_fresh_delete(self, tmp_path):
        (tmp_path / "file.txt").write_text("content")
        conn = make_connector(tmp_path)
        result = conn.delete_file("file.txt")
        assert result.output["already_done"] is False

    def test_rollback_data_stores_content(self, tmp_path):
        (tmp_path / "important.txt").write_text("precious data")
        conn = make_connector(tmp_path)
        result = conn.delete_file("important.txt")
        assert result.rollback_data["content"] == "precious data"
        assert result.rollback_data["path"] == "important.txt"

    def test_rollback_data_empty_for_already_deleted(self, tmp_path):
        conn = make_connector(tmp_path)
        result = conn.delete_file("ghost.txt")
        assert result.rollback_data == {}

    def test_path_traversal_blocked(self, tmp_path):
        conn = make_connector(tmp_path)
        result = conn.delete_file("../sibling.txt")
        assert result.success is False
        assert "outside" in result.output["error"].lower()

    def test_action_and_system_fields(self, tmp_path):
        (tmp_path / "f.txt").write_text("x")
        conn = make_connector(tmp_path)
        result = conn.delete_file("f.txt")
        assert result.action == "delete_file"
        assert result.system == "filesystem"


# ── list_dir ───────────────────────────────────────────────────────────────────

class TestListDir:
    def test_lists_files_in_directory(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        conn = make_connector(tmp_path)
        result = conn.list_dir(".")
        assert result.success is True
        assert "a.txt" in result.output["entries"]
        assert "b.txt" in result.output["entries"]

    def test_lists_subdirectory(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "child.txt").write_text("hi")
        conn = make_connector(tmp_path)
        result = conn.list_dir("subdir")
        assert "child.txt" in result.output["entries"]

    def test_fails_for_missing_directory(self, tmp_path):
        conn = make_connector(tmp_path)
        result = conn.list_dir("no_such_dir")
        assert result.success is False

    def test_path_traversal_blocked(self, tmp_path):
        conn = make_connector(tmp_path)
        result = conn.list_dir("../../")
        assert result.success is False
        assert "outside" in result.output["error"].lower()

    def test_no_rollback_data(self, tmp_path):
        conn = make_connector(tmp_path)
        result = conn.list_dir(".")
        assert result.rollback_data == {}

    def test_action_and_system_fields(self, tmp_path):
        conn = make_connector(tmp_path)
        result = conn.list_dir(".")
        assert result.action == "list_dir"
        assert result.system == "filesystem"
