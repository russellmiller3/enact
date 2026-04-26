"""Tests for the Enact Code Claude Code hook."""
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from enact.cli.code_hook import parse_bash_command, cmd_init, cmd_pre


# -- parser tests --

class TestParseBashCommand:
    def test_plain_command_populates_command_and_args(self):
        p = parse_bash_command("ls -la /tmp")
        assert p["command"] == "ls -la /tmp"
        assert p["args"] == ["ls", "-la", "/tmp"]
        assert "table" not in p
        assert "where" not in p

    def test_psql_delete_extracts_table_no_where(self):
        cmd = 'psql $DB -c "DELETE FROM customers"'
        p = parse_bash_command(cmd)
        assert p["table"] == "customers"
        assert "where" not in p
        assert "DELETE FROM" in p["sql"]

    def test_psql_delete_extracts_where_clause(self):
        cmd = "psql -c \"DELETE FROM users WHERE id = 1\""
        p = parse_bash_command(cmd)
        assert p["table"] == "users"
        assert "where" in p
        assert "id = 1" in p["where"]["clause"]

    def test_drop_table_extracts_table_and_sql(self):
        cmd = 'psql -c "DROP TABLE customers"'
        p = parse_bash_command(cmd)
        assert p["table"] == "customers"
        assert "DROP TABLE" in p["sql"]

    def test_force_push_args_visible(self):
        p = parse_bash_command("git push --force origin main")
        assert "--force" in p["args"]


# -- pre-hook tests --

@pytest.fixture
def in_tmp_with_init(tmp_path, monkeypatch):
    """Run cmd_init in a tmp dir so .enact/policies.py exists for cmd_pre."""
    monkeypatch.chdir(tmp_path)
    cmd_init()
    return tmp_path


def _run_pre(stdin_json: dict) -> tuple[int, str]:
    """Invoke cmd_pre with mocked stdin/stdout. Return (rc, stdout)."""
    stdin = io.StringIO(json.dumps(stdin_json))
    stdout = io.StringIO()
    with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
        rc = cmd_pre()
    return rc, stdout.getvalue()


class TestCmdPre:
    def test_non_bash_tool_passes_silently(self, in_tmp_with_init):
        rc, out = _run_pre({"tool_name": "Read", "tool_input": {"path": "/x"}})
        assert rc == 0
        assert out == ""

    def test_safe_command_passes_silently(self, in_tmp_with_init):
        rc, out = _run_pre({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
        assert rc == 0
        assert out == ""

    def test_protected_table_blocks(self, in_tmp_with_init):
        rc, out = _run_pre({
            "tool_name": "Bash",
            "tool_input": {"command": 'psql -c "DELETE FROM customers WHERE id=1"'},
        })
        assert rc == 0
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert result["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert "customers" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_force_push_blocks(self, in_tmp_with_init):
        rc, out = _run_pre({
            "tool_name": "Bash",
            "tool_input": {"command": "git push --force origin main"},
        })
        assert rc == 0
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "force" in result["hookSpecificOutput"]["permissionDecisionReason"].lower()

    def test_freeze_blocks(self, in_tmp_with_init, monkeypatch):
        monkeypatch.setenv("ENACT_FREEZE", "1")
        rc, out = _run_pre({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert rc == 0
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "freeze" in result["hookSpecificOutput"]["permissionDecisionReason"].lower()

    def test_malformed_stdin_fails_open(self, in_tmp_with_init):
        stdin = io.StringIO("not json{{{")
        with patch.object(sys, "stdin", stdin):
            assert cmd_pre() == 0

    def test_no_policies_file_passes_through(self, tmp_path, monkeypatch):
        """No .enact/policies.py → empty policies list → silent allow."""
        monkeypatch.chdir(tmp_path)  # do NOT call cmd_init
        stdin = io.StringIO(json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
        }))
        stdout = io.StringIO()
        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            assert cmd_pre() == 0
        assert stdout.getvalue() == ""

    def test_broken_policies_file_fails_open(self, tmp_path, monkeypatch):
        """Syntax-broken or import-broken policies.py → fail open silently."""
        monkeypatch.chdir(tmp_path)
        cmd_init()
        (tmp_path / ".enact" / "policies.py").write_text(
            "import this_module_does_not_exist\nPOLICIES = []\n"
        )
        stdin = io.StringIO(json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": 'psql -c "DELETE FROM customers"'},
        }))
        stdout = io.StringIO()
        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            assert cmd_pre() == 0
        assert stdout.getvalue() == ""


# -- init tests --

class TestCmdInit:
    def test_writes_settings_and_creates_dirs(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rc = cmd_init()
        assert rc == 0
        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert "PreToolUse" in settings["hooks"]
        assert (tmp_path / ".enact" / "policies.py").exists()
        assert (tmp_path / ".enact" / "secret").exists()
        assert ".enact/" in (tmp_path / ".gitignore").read_text()

    def test_init_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        original_secret = (tmp_path / ".enact" / "secret").read_text()
        cmd_init()
        assert (tmp_path / ".enact" / "secret").read_text() == original_secret

    def test_init_preserves_existing_unrelated_hooks(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        prior = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Read",
                        "hooks": [{"type": "command", "command": "some-other-tool check"}],
                    }
                ]
            },
            "theme": "dark",
        }
        (claude_dir / "settings.json").write_text(json.dumps(prior))

        cmd_init()

        settings = json.loads((claude_dir / "settings.json").read_text())
        assert settings["theme"] == "dark"
        pre_hooks = settings["hooks"]["PreToolUse"]
        assert len(pre_hooks) == 2
        matchers = {e["matcher"] for e in pre_hooks}
        assert matchers == {"Read", "Bash"}
        all_commands = [
            h["command"]
            for entry in pre_hooks
            for h in entry["hooks"]
        ]
        assert "some-other-tool check" in all_commands

    def test_init_replaces_prior_enact_entry_no_duplicate(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        cmd_init()
        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        for hook_event in ("PreToolUse", "PostToolUse"):
            entries = settings["hooks"][hook_event]
            enact_entries = [
                e for e in entries
                if any("enact-code-hook" in h.get("command", "") for h in e.get("hooks", []))
            ]
            assert len(enact_entries) == 1, f"{hook_event} duplicated enact entry"

    def test_init_does_not_double_add_gitignore_line(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        cmd_init()
        contents = (tmp_path / ".gitignore").read_text()
        assert contents.count(".enact/") == 1
