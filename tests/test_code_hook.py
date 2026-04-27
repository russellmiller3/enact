"""Tests for the Enact Code Claude Code hook."""
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from enact.cli.code_hook import parse_bash_command, cmd_init, cmd_pre, cmd_post, main


# -- parser tests --

class TestParseToolInput:
    """parse_tool_input dispatches Bash/Read/Write/Edit/Glob/Grep into a
    payload shape that existing path-/command-based policies can consume."""

    def test_bash_returns_existing_shape(self):
        from enact.cli.code_hook import parse_tool_input
        p = parse_tool_input("Bash", {"command": "ls -la /tmp"})
        assert p["command"] == "ls -la /tmp"
        assert p["args"] == ["ls", "-la", "/tmp"]

    def test_read_populates_path_and_command(self):
        from enact.cli.code_hook import parse_tool_input
        p = parse_tool_input("Read", {"file_path": "/etc/passwd"})
        assert p["path"] == "/etc/passwd"
        assert "Read" in p["command"]
        assert "/etc/passwd" in p["command"]

    def test_write_populates_path_content_and_command(self):
        from enact.cli.code_hook import parse_tool_input
        p = parse_tool_input("Write", {
            "file_path": ".github/workflows/deploy.yml",
            "content": "on: push",
        })
        assert p["path"] == ".github/workflows/deploy.yml"
        assert p["content"] == "on: push"
        assert "Write" in p["command"]

    def test_edit_populates_path_diff_content(self):
        from enact.cli.code_hook import parse_tool_input
        p = parse_tool_input("Edit", {
            "file_path": ".gitignore",
            "old_string": "node_modules/",
            "new_string": "node_modules/\n!.env",
        })
        assert p["path"] == ".gitignore"
        assert "node_modules/" in p["content"]
        assert "!.env" in p["content"]
        assert "node_modules/" in p["diff"]
        assert "!.env" in p["diff"]
        assert "Edit" in p["command"]

    def test_glob_populates_path_with_pattern(self):
        from enact.cli.code_hook import parse_tool_input
        p = parse_tool_input("Glob", {"pattern": "**/.aws/*"})
        assert p["path"] == "**/.aws/*"
        assert p["glob_pattern"] == "**/.aws/*"
        assert "Glob" in p["command"]

    def test_grep_populates_pattern_and_path(self):
        from enact.cli.code_hook import parse_tool_input
        p = parse_tool_input("Grep", {
            "pattern": "aws_secret_access_key",
            "path": "src/",
        })
        assert p["grep_pattern"] == "aws_secret_access_key"
        assert p["path"] == "src/"
        assert "Grep" in p["command"]

    def test_grep_no_path_defaults_to_empty(self):
        from enact.cli.code_hook import parse_tool_input
        p = parse_tool_input("Grep", {"pattern": "API_KEY"})
        assert p["grep_pattern"] == "API_KEY"
        assert p["path"] == ""

    def test_unknown_tool_returns_none(self):
        from enact.cli.code_hook import parse_tool_input
        assert parse_tool_input("WebFetch", {"url": "x"}) is None
        assert parse_tool_input("Task", {}) is None

    def test_read_missing_file_path_returns_none(self):
        from enact.cli.code_hook import parse_tool_input
        assert parse_tool_input("Read", {}) is None

    def test_glob_missing_pattern_returns_none(self):
        from enact.cli.code_hook import parse_tool_input
        assert parse_tool_input("Glob", {}) is None


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
    def test_unsupported_tool_passes_silently(self, in_tmp_with_init):
        # WebFetch isn't in SUPPORTED_TOOLS — fail-open silently
        rc, out = _run_pre({"tool_name": "WebFetch", "tool_input": {"url": "https://example.com"}})
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


class TestCmdPreFileAccess:
    """cmd_pre fires existing path-based policies for Read/Write/Edit
    once the dispatcher routes those tools and the default .enact/policies.py
    imports the filesystem policy library."""

    def test_read_env_file_blocks(self, in_tmp_with_init):
        rc, out = _run_pre({
            "tool_name": "Read",
            "tool_input": {"file_path": ".env"},
        })
        assert rc == 0
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "env" in result["hookSpecificOutput"]["permissionDecisionReason"].lower()

    def test_read_safe_file_passes_silently(self, in_tmp_with_init):
        rc, out = _run_pre({
            "tool_name": "Read",
            "tool_input": {"file_path": "src/main.py"},
        })
        assert rc == 0
        assert out == ""

    def test_write_to_workflow_blocks(self, in_tmp_with_init):
        rc, out = _run_pre({
            "tool_name": "Write",
            "tool_input": {
                "file_path": ".github/workflows/deploy.yml",
                "content": "on: push",
            },
        })
        assert rc == 0
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        reason = result["hookSpecificOutput"]["permissionDecisionReason"].lower()
        assert "ci" in reason or "workflow" in reason or "pipeline" in reason

    def test_edit_gitignore_blocks(self, in_tmp_with_init):
        rc, out = _run_pre({
            "tool_name": "Edit",
            "tool_input": {
                "file_path": ".gitignore",
                "old_string": ".env",
                "new_string": "",
            },
        })
        assert rc == 0
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "gitignore" in result["hookSpecificOutput"]["permissionDecisionReason"].lower()

    def test_read_aws_credentials_via_home_dir_blocks(self, in_tmp_with_init):
        rc, out = _run_pre({
            "tool_name": "Read",
            "tool_input": {"file_path": "~/.aws/credentials"},
        })
        assert rc == 0
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "home" in result["hookSpecificOutput"]["permissionDecisionReason"].lower()

    def test_write_with_api_key_in_content_blocks(self, in_tmp_with_init):
        # AWS access key format (AKIA + 16 alphanumerics) — matches SECRET_PATTERNS
        rc, out = _run_pre({
            "tool_name": "Write",
            "tool_input": {
                "file_path": "src/config.py",
                "content": 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"',
            },
        })
        assert rc == 0
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        reason = result["hookSpecificOutput"]["permissionDecisionReason"].lower()
        assert "key" in reason or "secret" in reason or "credential" in reason

    def test_glob_home_aws_blocks(self, in_tmp_with_init):
        # ~/.aws/* is caught by dont_access_home_dir (~/ prefix) AND
        # block_glob_credentials_dirs (.aws pattern). Either is fine.
        rc, out = _run_pre({
            "tool_name": "Glob",
            "tool_input": {"pattern": "~/.aws/*"},
        })
        assert rc == 0
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_glob_for_pem_files_blocks(self, in_tmp_with_init):
        # **/*.pem caught only by block_glob_credentials_dirs (no path policy
        # would fire since pattern is cwd-relative)
        rc, out = _run_pre({
            "tool_name": "Glob",
            "tool_input": {"pattern": "**/*.pem"},
        })
        assert rc == 0
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_grep_secret_pattern_blocks(self, in_tmp_with_init):
        rc, out = _run_pre({
            "tool_name": "Grep",
            "tool_input": {"pattern": "aws_secret_access_key"},
        })
        assert rc == 0
        result = json.loads(out)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
        reason = result["hookSpecificOutput"]["permissionDecisionReason"].lower()
        assert "secret" in reason or "credential" in reason

    def test_grep_innocent_pattern_passes(self, in_tmp_with_init):
        rc, out = _run_pre({
            "tool_name": "Grep",
            "tool_input": {"pattern": "TODO", "path": "src/"},
        })
        assert rc == 0
        assert out == ""


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

    def test_init_adds_matchers_for_all_supported_tools(self, tmp_path, monkeypatch):
        # Enact wires PreToolUse + PostToolUse for every member of SUPPORTED_TOOLS
        monkeypatch.chdir(tmp_path)
        from enact.cli.code_hook import SUPPORTED_TOOLS
        cmd_init()
        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
        for hook_event in ("PreToolUse", "PostToolUse"):
            entries = settings["hooks"][hook_event]
            enact_matchers = {
                e["matcher"] for e in entries
                if any("enact.cli.code_hook" in h.get("command", "") or "enact-code-hook" in h.get("command", "") for h in e.get("hooks", []))
            }
            assert enact_matchers == set(SUPPORTED_TOOLS), \
                f"{hook_event}: expected {set(SUPPORTED_TOOLS)}, got {enact_matchers}"

    def test_init_preserves_existing_unrelated_hooks(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from enact.cli.code_hook import SUPPORTED_TOOLS
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

        settings = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
        assert settings["theme"] == "dark"
        pre_hooks = settings["hooks"]["PreToolUse"]
        # 6 enact entries (Bash/Read/Write/Edit/Glob/Grep) + the user's Read = 7
        assert len(pre_hooks) == len(SUPPORTED_TOOLS) + 1
        all_commands = [
            h["command"]
            for entry in pre_hooks
            for h in entry["hooks"]
        ]
        assert "some-other-tool check" in all_commands
        enact_count = sum(1 for c in all_commands if "enact.cli.code_hook pre" in c or "enact-code-hook pre" in c)
        assert enact_count == len(SUPPORTED_TOOLS)

    def test_init_replaces_prior_enact_entry_no_duplicate(self, tmp_path, monkeypatch):
        # Re-running init must produce the same N enact entries (no duplication)
        monkeypatch.chdir(tmp_path)
        from enact.cli.code_hook import SUPPORTED_TOOLS
        cmd_init()
        cmd_init()
        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
        for hook_event in ("PreToolUse", "PostToolUse"):
            entries = settings["hooks"][hook_event]
            enact_entries = [
                e for e in entries
                if any("enact.cli.code_hook" in h.get("command", "") or "enact-code-hook" in h.get("command", "") for h in e.get("hooks", []))
            ]
            assert len(enact_entries) == len(SUPPORTED_TOOLS), \
                f"{hook_event} expected {len(SUPPORTED_TOOLS)} enact entries, got {len(enact_entries)}"

    def test_init_does_not_double_add_gitignore_line(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        cmd_init()
        contents = (tmp_path / ".gitignore").read_text()
        assert contents.count(".enact/") == 1

    def test_default_policies_file_includes_file_access(self, tmp_path, monkeypatch):
        # Out of the box, .enact/policies.py imports both the file-path
        # policies (Read/Write/Edit surfaces) AND the FILE_ACCESS_POLICIES
        # (Glob/Grep pattern surfaces).
        monkeypatch.chdir(tmp_path)
        cmd_init()
        contents = (tmp_path / ".enact" / "policies.py").read_text(encoding="utf-8")
        # File-path policies — fire on Read/Write/Edit
        assert "dont_read_env" in contents
        assert "dont_touch_ci_cd" in contents
        assert "dont_edit_gitignore" in contents
        assert "dont_access_home_dir" in contents
        assert "dont_copy_api_keys" in contents
        # File-access policies — fire on Glob/Grep patterns
        assert "FILE_ACCESS_POLICIES" in contents


# -- post-hook tests --

class TestCmdPost:
    def _run_post(self, stdin_json: dict) -> int:
        stdin = io.StringIO(json.dumps(stdin_json))
        with patch.object(sys, "stdin", stdin):
            return cmd_post()

    def test_writes_signed_receipt_with_action(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        rc = self._run_post({
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
            "tool_response": {"exit_code": 0, "stdout": "file1\nfile2\n"},
            "session_id": "abc-123",
        })
        assert rc == 0
        receipts = list((tmp_path / "receipts").glob("*.json"))
        assert len(receipts) == 1
        body = json.loads(receipts[0].read_text())
        assert body["decision"] == "PASS"
        assert body["signature"] != ""
        assert len(body["actions_taken"]) == 1
        action = body["actions_taken"][0]
        # action follows the new tool.<lower> convention; system stays "shell"
        # for Bash so audit dashboards can group shell vs file-tool ops.
        assert action["action"] == "tool.bash"
        assert action["system"] == "shell"
        assert action["success"] is True
        assert action["output"]["command"] == "ls -la"
        assert action["output"]["exit_code"] == 0
        assert action["output"]["already_done"] is False

    def test_failed_bash_reflected_in_action_success(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        rc = self._run_post({
            "tool_name": "Bash",
            "tool_input": {"command": "false"},
            "tool_response": {"exit_code": 1, "stderr": "fail"},
        })
        assert rc == 0
        body = json.loads(list((tmp_path / "receipts").glob("*.json"))[0].read_text())
        assert body["decision"] == "PASS"
        assert body["actions_taken"][0]["success"] is False
        assert body["actions_taken"][0]["output"]["exit_code"] == 1

    def test_interrupted_bash_marks_action_failed(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        rc = self._run_post({
            "tool_name": "Bash",
            "tool_input": {"command": "sleep 100"},
            "tool_response": {"exit_code": 0, "interrupted": True},
        })
        assert rc == 0
        body = json.loads(list((tmp_path / "receipts").glob("*.json"))[0].read_text())
        assert body["actions_taken"][0]["success"] is False
        assert body["actions_taken"][0]["output"]["interrupted"] is True

    def test_no_secret_skips_silently(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rc = self._run_post({"tool_name": "Bash", "tool_input": {"command": "ls"}})
        assert rc == 0
        assert not (tmp_path / "receipts").exists()

    def test_unsupported_tool_skipped(self, tmp_path, monkeypatch):
        # WebFetch isn't in SUPPORTED_TOOLS — no receipt
        monkeypatch.chdir(tmp_path)
        cmd_init()
        rc = self._run_post({"tool_name": "WebFetch", "tool_input": {"url": "https://x.com"}})
        assert rc == 0
        assert not (tmp_path / "receipts").exists()

    def test_env_var_chaos_run_id_routes_receipt_to_per_run_dir(
        self, tmp_path, monkeypatch
    ):
        """If ENACT_CHAOS_RUN_ID is set, receipts go to
        chaos/runs/{run_id}/receipts/ (per-run scoped) instead of cwd/receipts/.
        Lets parallel chaos sweeps run without timestamp-diff hack."""
        monkeypatch.chdir(tmp_path)
        cmd_init()
        chaos_run_id = "abc-test-run"
        run_dir = tmp_path / "chaos" / "runs" / chaos_run_id
        run_dir.mkdir(parents=True)
        monkeypatch.setenv("ENACT_CHAOS_RUN_ID", chaos_run_id)

        rc = self._run_post({
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_response": {"exit_code": 0},
        })
        assert rc == 0
        # Should NOT be in the default receipts/
        assert not (tmp_path / "receipts").exists() or \
               len(list((tmp_path / "receipts").glob("*.json"))) == 0
        # Should be in the per-run dir
        per_run_receipts = list((run_dir / "receipts").glob("*.json"))
        assert len(per_run_receipts) == 1

    def test_env_var_unset_defaults_to_cwd_receipts(self, tmp_path, monkeypatch):
        """When ENACT_CHAOS_RUN_ID is unset, receipts go to default
        cwd/receipts/. Existing CC users see no behavior change."""
        monkeypatch.chdir(tmp_path)
        cmd_init()
        monkeypatch.delenv("ENACT_CHAOS_RUN_ID", raising=False)

        rc = self._run_post({
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
            "tool_response": {"exit_code": 0},
        })
        assert rc == 0
        receipts = list((tmp_path / "receipts").glob("*.json"))
        assert len(receipts) == 1


class TestCmdPostMultiTool:
    """cmd_post writes signed receipts for every supported tool, with
    action.system reflecting the actual tool surface so audit dashboards
    can filter by tool type."""

    def _run_post(self, stdin_json: dict) -> int:
        stdin = io.StringIO(json.dumps(stdin_json))
        with patch.object(sys, "stdin", stdin):
            return cmd_post()

    def test_read_writes_receipt_with_read_action(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        rc = self._run_post({
            "tool_name": "Read",
            "tool_input": {"file_path": "src/main.py"},
            "tool_response": {"file": {"contents": "print('hi')"}},
        })
        assert rc == 0
        body = json.loads(list((tmp_path / "receipts").glob("*.json"))[0].read_text(encoding="utf-8"))
        assert body["decision"] == "PASS"
        assert body["actions_taken"][0]["system"] == "read"
        assert body["actions_taken"][0]["action"] == "tool.read"
        assert body["actions_taken"][0]["output"]["path"] == "src/main.py"
        assert body["actions_taken"][0]["success"] is True

    def test_write_failure_in_response_marks_action_failed(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        rc = self._run_post({
            "tool_name": "Write",
            "tool_input": {"file_path": "x.txt", "content": "hi"},
            "tool_response": {"error": "permission denied"},
        })
        assert rc == 0
        body = json.loads(list((tmp_path / "receipts").glob("*.json"))[0].read_text(encoding="utf-8"))
        assert body["actions_taken"][0]["system"] == "write"
        assert body["actions_taken"][0]["success"] is False
        assert body["actions_taken"][0]["output"]["error"] == "permission denied"

    def test_edit_writes_receipt_with_edit_action(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        rc = self._run_post({
            "tool_name": "Edit",
            "tool_input": {"file_path": "x.py", "old_string": "a", "new_string": "b"},
            "tool_response": {"file": {"contents": "b"}},
        })
        assert rc == 0
        body = json.loads(list((tmp_path / "receipts").glob("*.json"))[0].read_text(encoding="utf-8"))
        assert body["actions_taken"][0]["system"] == "edit"
        assert body["actions_taken"][0]["action"] == "tool.edit"

    def test_glob_writes_receipt_with_glob_action(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        rc = self._run_post({
            "tool_name": "Glob",
            "tool_input": {"pattern": "src/**/*.py"},
            "tool_response": {"files": ["src/main.py"]},
        })
        assert rc == 0
        body = json.loads(list((tmp_path / "receipts").glob("*.json"))[0].read_text(encoding="utf-8"))
        assert body["actions_taken"][0]["system"] == "glob"

    def test_grep_writes_receipt_with_grep_action(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        rc = self._run_post({
            "tool_name": "Grep",
            "tool_input": {"pattern": "TODO", "path": "src/"},
            "tool_response": {"matches": []},
        })
        assert rc == 0
        body = json.loads(list((tmp_path / "receipts").glob("*.json"))[0].read_text(encoding="utf-8"))
        assert body["actions_taken"][0]["system"] == "grep"


# -- main dispatcher --

class TestMain:
    def test_unknown_subcommand_returns_1(self):
        with patch.object(sys, "argv", ["enact-code-hook", "bogus"]):
            assert main() == 1

    def test_no_subcommand_returns_1(self):
        with patch.object(sys, "argv", ["enact-code-hook"]):
            assert main() == 1
