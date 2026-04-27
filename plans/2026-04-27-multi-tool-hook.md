# Plan 15.1: Multi-Tool Hook — close the Read/Write/Edit/Glob/Grep gap

**Template:** B (small plan — wiring + a few new policies, ~150-200 LoC across 3 files)
**Branch:** `claude/multi-tool-hook` (already created)
**Why now:** Session 14 task 70 proved the agent reads `.env` via Claude Code's Read tool, bypassing the Bash hook entirely. Today Enact is a *shell firewall* — covers 1 of 8 tools that touch the filesystem. After this plan, it covers 6 (Bash + Read + Write + Edit + Glob + Grep). The name "Agent Firewall" implies coverage of every agent action, not just shell.

---

## B.1 THE PROBLEM

**What's broken or missing:** The PreToolUse hook in `enact/cli/code_hook.py:cmd_pre` returns 0 (silent allow) for every non-Bash tool. So `Read /etc/passwd`, `Write .github/workflows/deploy.yml`, `Edit .gitignore`, `Glob ~/.aws/*`, `Grep aws_secret_access_key` all fall through. Same hole on `cmd_post` — no receipts written for non-Bash tool calls.

**Root Cause:** The handler was scoped to Bash for v1 because most damage cases were shell commands. Read/Write/Edit/Glob/Grep have different `tool_input` shapes (`{file_path}` vs `{command}`) and didn't fit the existing `parse_bash_command(command)` path. The hook just bailed.

---

## B.2 THE FIX

**Key Insight:** The existing `enact/policies/filesystem.py` policies already check `payload["path"]`. We don't need new policies — we need to **route** the tool inputs into a payload with `path` (and `content` for Write) so those policies fire. Plus add Read/Write/Edit/Glob/Grep matchers in `cmd_init` so Claude Code actually invokes us on those calls.

```
BEFORE:
  Bash -> parse_bash_command(command) -> policies fire on payload["command"]
  Read/Write/Edit/Glob/Grep -> not invoked, hook bails -> NOTHING fires

AFTER:
  Bash      -> parse_bash_command(command)  -> payload{command, args, diff, content, sql?, table?, where?}
  Read      -> parse_read({file_path})      -> payload{path, command="Read <path>"}
  Write     -> parse_write({file_path,      -> payload{path, content, command="Write <path>"}
                          content})
  Edit      -> parse_edit({file_path,       -> payload{path, content=new_string, diff, command="Edit <path>"}
                          old_string,
                          new_string})
  Glob      -> parse_glob({pattern, path?}) -> payload{path=pattern, command="Glob <pattern>"}
  Grep      -> parse_grep({pattern, path?,  -> payload{path=path|"", grep_pattern, command="Grep <pattern>"}
                           glob?})
```

**Why This Works:**
- Existing `filesystem.py` policies already key off `payload["path"]` — they fire automatically once routed
- Existing `coding_agent.py` `_scan(context)` falls through `command -> diff -> content -> action` — putting the rendered tool action in `command` keeps shell-pattern policies (block_ssh_key_read etc.) firing on Read/Write/Edit/Glob/Grep too
- One new tiny policy module `enact/policies/file_access.py` adds the two patterns the existing surfaces don't cover: `block_grep_secret_patterns` (looks at the GREP regex itself, not the file path) and `block_glob_credentials_dirs` (looks at the GLOB pattern, e.g. `~/.aws/*`)

---

## B.3 FILES INVOLVED

### New Files

| File | Purpose |
|---|---|
| `enact/policies/file_access.py` | Two new policies — `block_grep_secret_patterns`, `block_glob_credentials_dirs`. Module also exports `FILE_ACCESS_POLICIES = [...]` for `.enact/policies.py` import. |
| `tests/test_file_access_policies.py` | Unit tests for the two new policies (10 cases). |

### Files to Modify

| File | Changes |
|---|---|
| `enact/cli/code_hook.py` | (1) `cmd_init` — add `Read`, `Write`, `Edit`, `Glob`, `Grep` matchers to PreToolUse and PostToolUse; (2) `cmd_pre` — dispatch by `tool_name`, build payload via new `parse_tool_input(tool_name, tool_input)`; (3) `cmd_post` — same dispatch, action.system reflects tool ("read", "write", "edit", "glob", "grep", "shell"); (4) update `DEFAULT_POLICIES_PY` template to import the filesystem + file_access policies. |
| `tests/test_code_hook.py` | (1) Update `test_init_preserves_existing_unrelated_hooks` — Enact now adds 5 new matchers, so the assertion changes; (2) Update `test_non_bash_tool_passes_silently` to test SAFE Read passes silently; (3) Add `TestParseToolInput` class with 8-10 cases for Read/Write/Edit/Glob/Grep parsing; (4) Add `TestCmdPreFileAccess` with 5-6 cases for blocking behaviors per tool; (5) Add `TestCmdPostMultiTool` showing receipts get written for Read/Write/Edit too with action.system = "read" etc.; (6) Update `test_non_bash_tool_skipped` in CmdPost — now Read writes a receipt, not skipped. |

---

## B.4 EDGE CASES

| Scenario | Handling |
|---|---|
| `Edit` tool with multi-line `new_string` containing API key | `payload["content"] = new_string` so `dont_copy_api_keys` (existing) catches it; also set `payload["diff"] = old_string + "\n->\n" + new_string` so `dont_commit_api_keys` (which scans diff) also catches it. Defense in depth. |
| `Glob` with no `path` (CWD-relative) | `payload["path"]` is the pattern itself; `dont_access_home_dir` checks the pattern string for `~/`, well-known prefixes — works. New `block_glob_credentials_dirs` checks for `**/.aws/*`, `**/.ssh/*` etc. |
| `Grep` with `path=None` (CWD-relative) | `payload["path"] = ""` so path-based policies pass through; new `block_grep_secret_patterns` keys off `payload["grep_pattern"]` instead. |
| `Read` of `.env.local` | Existing `dont_read_env` already matches `.env*` — works. |
| Tool input missing `file_path` (malformed) | `parse_tool_input` returns `None` → `cmd_pre` returns 0 (fail open). Same as unknown tool_name. |
| `cmd_init` re-run preserves Bash matcher AND adds new ones idempotently | `_is_enact_hook_entry()` already strips ALL prior enact entries before adding fresh ones. We add 5 new entries (Read/Write/Edit/Glob/Grep) per event. Idempotent because we always rebuild from scratch. |
| Existing `.claude/settings.json` has unrelated `Read` matcher (e.g. some-other-tool) | `_is_enact_hook_entry` only strips entries whose hook commands contain `enact-code-hook`. Others kept. |
| Tool name `NotebookEdit` / `WebFetch` / `Task` | Not covered in this plan (deferred to v2 — the handoff lists 8 tools; 5 here). Falls through silently — no breaking change. |
| Read tool produces `tool_response = {file: "..."}` not `{exit_code: ...}` | `cmd_post` builds ActionResult.success = (no `error` key in response). Adapt: `success = "error" not in tool_response` for non-Bash tools. |

---

## B.5 IMPLEMENTATION STEPS

### Cycle 1: `parse_tool_input` dispatcher 🔴🟢🔄

**Goal:** One pure function that maps `(tool_name, tool_input)` → `payload dict | None`. No I/O, no side effects. Easy to unit test.

**Test (add to tests/test_code_hook.py before TestCmdPre):**

```python
class TestParseToolInput:
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
```

**Implementation (add to enact/cli/code_hook.py, after `parse_bash_command`):**

```python
SUPPORTED_TOOLS = {"Bash", "Read", "Write", "Edit", "Glob", "Grep"}


def parse_tool_input(tool_name: str, tool_input: dict) -> dict | None:
    """
    Map a Claude Code tool invocation into the payload shape policies expect.

    Returns None for unsupported tools or malformed input — caller should
    treat None as "fail open" (silent allow) to preserve the never-brick-CC
    invariant.
    """
    if tool_name == "Bash":
        command = tool_input.get("command") or ""
        if not command:
            return None
        return parse_bash_command(command)

    if tool_name == "Read":
        path = tool_input.get("file_path") or ""
        if not path:
            return None
        return {
            "path": path,
            "command": f"Read {path}",
            "diff": "",
            "content": "",
        }

    if tool_name == "Write":
        path = tool_input.get("file_path") or ""
        if not path:
            return None
        content = tool_input.get("content") or ""
        return {
            "path": path,
            "content": content,
            "command": f"Write {path}",
            "diff": content,  # so dont_commit_api_keys (scans diff) catches it
        }

    if tool_name == "Edit":
        path = tool_input.get("file_path") or ""
        if not path:
            return None
        old = tool_input.get("old_string") or ""
        new = tool_input.get("new_string") or ""
        return {
            "path": path,
            "content": new,
            "diff": f"{old}\n->\n{new}",
            "command": f"Edit {path}",
        }

    if tool_name == "Glob":
        pattern = tool_input.get("pattern") or ""
        if not pattern:
            return None
        return {
            "path": pattern,  # so dont_access_home_dir, block_glob_credentials_dirs fire
            "glob_pattern": pattern,
            "command": f"Glob {pattern}",
            "diff": "",
            "content": "",
        }

    if tool_name == "Grep":
        pattern = tool_input.get("pattern") or ""
        if not pattern:
            return None
        path = tool_input.get("path") or ""
        return {
            "path": path,
            "grep_pattern": pattern,
            "command": f"Grep {pattern}" + (f" {path}" if path else ""),
            "diff": "",
            "content": "",
        }

    return None  # unknown tool — fail open
```

**Run:** `pytest tests/test_code_hook.py::TestParseToolInput -v`
**Green means:** All 10 tests pass. `parse_tool_input` is pure — no imports beyond `parse_bash_command`.
**Commit:** `"feat(hook): parse_tool_input dispatcher for Bash/Read/Write/Edit/Glob/Grep"`

### Cycle 2: `cmd_pre` dispatches via `parse_tool_input` 🔴🟢🔄

**Goal:** Replace the `if event.get("tool_name") != "Bash": return 0` early-return with the new dispatcher. Block decisions stay identical for Bash; new tools now go through the policy engine.

**Test (add to TestCmdPre in tests/test_code_hook.py):**

```python
class TestCmdPreFileAccess:
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
        assert "ci" in result["hookSpecificOutput"]["permissionDecisionReason"].lower() or \
               "workflow" in result["hookSpecificOutput"]["permissionDecisionReason"].lower()

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

    def test_glob_home_aws_blocks(self, in_tmp_with_init):
        rc, out = _run_pre({
            "tool_name": "Glob",
            "tool_input": {"pattern": "~/.aws/*"},
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
        assert "secret" in result["hookSpecificOutput"]["permissionDecisionReason"].lower() or \
               "key" in result["hookSpecificOutput"]["permissionDecisionReason"].lower()

    def test_unknown_tool_passes_silently(self, in_tmp_with_init):
        rc, out = _run_pre({
            "tool_name": "WebFetch",
            "tool_input": {"url": "https://example.com"},
        })
        assert rc == 0
        assert out == ""
```

**Also UPDATE existing tests in TestCmdPre that assumed Bash-only:**

- `test_non_bash_tool_passes_silently` → rename to `test_unknown_tool_passes_silently_when_unsupported` and use `WebFetch` instead of `Read`. (Kept the `WebFetch` version above.)

**Implementation (replace the early-bail in cmd_pre):**

Find this block in `enact/cli/code_hook.py:cmd_pre`:

```python
        if event.get("tool_name") != "Bash":
            return 0  # only Bash for v1

        command = event.get("tool_input", {}).get("command", "")
        if not command:
            return 0

        payload = parse_bash_command(command)
```

Replace with:

```python
        tool_name = event.get("tool_name", "")
        tool_input = event.get("tool_input", {}) or {}
        payload = parse_tool_input(tool_name, tool_input)
        if payload is None:
            return 0  # unsupported tool or malformed input — fail open

        # Render a stable command-like string for receipts even on non-Bash tools
        command = payload.get("command", "")
```

Also update the `workflow=` field to reflect tool: change `workflow="shell.bash"` to `workflow=f"tool.{tool_name.lower()}"` in the WorkflowContext, build_receipt, and the receipt payload.

**Run:** `pytest tests/test_code_hook.py::TestCmdPreFileAccess -v && pytest tests/test_code_hook.py::TestCmdPre -v`
**Green means:** All new tests pass; all existing TestCmdPre tests still pass; the workflow string in receipts is `tool.bash` / `tool.read` / `tool.write` / `tool.edit` / `tool.glob` / `tool.grep`.
**Commit:** `"feat(hook): cmd_pre dispatches Read/Write/Edit/Glob/Grep through policy engine"`

### Cycle 3: `cmd_post` writes receipts for all supported tools 🔴🟢🔄

**Goal:** Audit completeness — every PASS through any supported tool produces a signed receipt, with action.system reflecting the actual tool.

**Test (add to TestCmdPost):**

```python
class TestCmdPostMultiTool:
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
        body = json.loads(list((tmp_path / "receipts").glob("*.json"))[0].read_text())
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
        body = json.loads(list((tmp_path / "receipts").glob("*.json"))[0].read_text())
        assert body["actions_taken"][0]["success"] is False

    def test_edit_writes_receipt(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        rc = self._run_post({
            "tool_name": "Edit",
            "tool_input": {"file_path": "x.py", "old_string": "a", "new_string": "b"},
            "tool_response": {"file": {"contents": "b"}},
        })
        assert rc == 0
        body = json.loads(list((tmp_path / "receipts").glob("*.json"))[0].read_text())
        assert body["actions_taken"][0]["system"] == "edit"

    def test_unknown_tool_skipped_silently(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cmd_init()
        rc = self._run_post({"tool_name": "WebFetch", "tool_input": {"url": "x"}})
        assert rc == 0
        # No receipt for unsupported tool
        assert not (tmp_path / "receipts").exists() or \
               len(list((tmp_path / "receipts").glob("*.json"))) == 0
```

**Also UPDATE existing test in TestCmdPost:**

- `test_non_bash_tool_skipped` — rename to `test_unsupported_tool_skipped` and use `WebFetch` instead of `Read`. (kept above.)

**Implementation (replace cmd_post body that bails on non-Bash):**

Find:

```python
        if event.get("tool_name") != "Bash":
            return 0
```

Replace with:

```python
        tool_name = event.get("tool_name", "")
        if tool_name not in SUPPORTED_TOOLS:
            return 0
```

Find the action_result construction:

```python
        action_result = ActionResult(
            action="shell.bash",
            system="shell",
            success=bash_succeeded,
            output={
                "command": command,
                "exit_code": exit_code,
                "interrupted": interrupted,
                "already_done": False,
            },
        )
```

Replace with:

```python
        tool_input = event.get("tool_input", {}) or {}
        tool_response = event.get("tool_response") or {}
        payload_for_action = parse_tool_input(tool_name, tool_input) or {}

        if tool_name == "Bash":
            command = tool_input.get("command", "")
            exit_code = tool_response.get("exit_code", 0)
            interrupted = tool_response.get("interrupted", False) is True
            success = (exit_code == 0) and not interrupted
            action_output = {
                "command": command,
                "exit_code": exit_code,
                "interrupted": interrupted,
                "already_done": False,
            }
        else:
            command = payload_for_action.get("command", "")
            success = "error" not in tool_response
            action_output = {
                "command": command,
                "path": payload_for_action.get("path", ""),
                "already_done": False,
            }
            if "error" in tool_response:
                action_output["error"] = tool_response["error"]

        system_name = "shell" if tool_name == "Bash" else tool_name.lower()
        action_result = ActionResult(
            action=f"tool.{tool_name.lower()}",
            system=system_name,
            success=success,
            output=action_output,
        )
```

Update the workflow string in payload + build_receipt to `f"tool.{tool_name.lower()}"`.

**Run:** `pytest tests/test_code_hook.py::TestCmdPostMultiTool -v && pytest tests/test_code_hook.py::TestCmdPost -v`
**Green means:** All new tests pass; existing CmdPost tests still pass.
**Commit:** `"feat(hook): cmd_post writes signed receipts for Read/Write/Edit/Glob/Grep"`

### Cycle 4: `cmd_init` adds Read/Write/Edit/Glob/Grep matchers 🔴🟢🔄

**Goal:** Once the user runs `enact-code-hook init`, Claude Code invokes the hook on every supported tool — not just Bash.

**Test (update + add in TestCmdInit):**

```python
def test_init_adds_matchers_for_all_supported_tools(self, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cmd_init()
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    expected = {"Bash", "Read", "Write", "Edit", "Glob", "Grep"}
    pre_matchers = {e["matcher"] for e in settings["hooks"]["PreToolUse"]
                    if any("enact-code-hook" in h.get("command", "") for h in e["hooks"])}
    assert pre_matchers == expected
    post_matchers = {e["matcher"] for e in settings["hooks"]["PostToolUse"]
                     if any("enact-code-hook" in h.get("command", "") for h in e["hooks"])}
    assert post_matchers == expected
```

**Also UPDATE `test_init_preserves_existing_unrelated_hooks`:**

The existing assertion `assert matchers == {"Read", "Bash"}` is wrong now — the user's existing some-other-tool Read entry should be preserved alongside Enact's 6 entries. Replace:

```python
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
    # Enact adds 6 entries (Bash, Read, Write, Edit, Glob, Grep) + the user's some-other-tool Read = 7
    assert len(pre_hooks) == 7
    all_commands = [
        h["command"]
        for entry in pre_hooks
        for h in entry["hooks"]
    ]
    assert "some-other-tool check" in all_commands
    enact_count = sum(1 for c in all_commands if "enact-code-hook pre" in c)
    assert enact_count == 6
```

**Implementation (in cmd_init, replace single-matcher block):**

Find:

```python
    pre_entry = {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "enact-code-hook pre"}],
    }
    post_entry = {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "enact-code-hook post"}],
    }

    # Merge: keep user's existing hooks for other tools / matchers; replace any
    # prior enact-code-hook entry so re-running init never duplicates ours.
    existing_pre = settings["hooks"].get("PreToolUse", [])
    existing_post = settings["hooks"].get("PostToolUse", [])
    settings["hooks"]["PreToolUse"] = (
        [e for e in existing_pre if not _is_enact_hook_entry(e)] + [pre_entry]
    )
    settings["hooks"]["PostToolUse"] = (
        [e for e in existing_post if not _is_enact_hook_entry(e)] + [post_entry]
    )
```

Replace with:

```python
    enact_pre_entries = [
        {"matcher": tool, "hooks": [{"type": "command", "command": "enact-code-hook pre"}]}
        for tool in sorted(SUPPORTED_TOOLS)
    ]
    enact_post_entries = [
        {"matcher": tool, "hooks": [{"type": "command", "command": "enact-code-hook post"}]}
        for tool in sorted(SUPPORTED_TOOLS)
    ]

    existing_pre = settings["hooks"].get("PreToolUse", [])
    existing_post = settings["hooks"].get("PostToolUse", [])
    settings["hooks"]["PreToolUse"] = (
        [e for e in existing_pre if not _is_enact_hook_entry(e)] + enact_pre_entries
    )
    settings["hooks"]["PostToolUse"] = (
        [e for e in existing_post if not _is_enact_hook_entry(e)] + enact_post_entries
    )
```

`SUPPORTED_TOOLS` is the module-level set defined in cycle 1.

**Run:** `pytest tests/test_code_hook.py::TestCmdInit -v`
**Green means:** All TestCmdInit tests pass. Bash matcher still present, plus 5 new ones, idempotent re-init produces identical settings.json.
**Commit:** `"feat(hook): cmd_init wires Read/Write/Edit/Glob/Grep matchers"`

### Cycle 5: New policies — `block_grep_secret_patterns`, `block_glob_credentials_dirs` 🔴🟢🔄

**Goal:** Two new policies for the surfaces existing filesystem.py doesn't cover.

**Test file (NEW — tests/test_file_access_policies.py):**

```python
"""Tests for file_access policies (Glob/Grep specific patterns)."""
from enact.models import WorkflowContext
from enact.policies.file_access import (
    block_grep_secret_patterns,
    block_glob_credentials_dirs,
)


def _ctx(payload: dict) -> WorkflowContext:
    return WorkflowContext(
        workflow="tool.grep",
        user_email="x@x",
        payload=payload,
    )


class TestBlockGrepSecretPatterns:
    def test_grep_for_aws_secret_access_key_blocks(self):
        r = block_grep_secret_patterns(_ctx({"grep_pattern": "aws_secret_access_key"}))
        assert r.passed is False
        assert "secret" in r.reason.lower() or "credential" in r.reason.lower()

    def test_grep_for_api_key_blocks(self):
        r = block_grep_secret_patterns(_ctx({"grep_pattern": "API_KEY"}))
        assert r.passed is False

    def test_grep_for_password_field_blocks(self):
        r = block_grep_secret_patterns(_ctx({"grep_pattern": "password\\s*="}))
        assert r.passed is False

    def test_grep_for_private_key_blocks(self):
        r = block_grep_secret_patterns(_ctx({"grep_pattern": "BEGIN RSA PRIVATE KEY"}))
        assert r.passed is False

    def test_grep_for_innocent_pattern_passes(self):
        r = block_grep_secret_patterns(_ctx({"grep_pattern": "TODO"}))
        assert r.passed is True

    def test_no_grep_pattern_passes(self):
        r = block_grep_secret_patterns(_ctx({}))
        assert r.passed is True


class TestBlockGlobCredentialsDirs:
    def test_glob_home_aws_star_blocks(self):
        r = block_glob_credentials_dirs(_ctx({"glob_pattern": "~/.aws/*"}))
        assert r.passed is False
        assert "credential" in r.reason.lower() or "secret" in r.reason.lower()

    def test_glob_double_star_ssh_blocks(self):
        r = block_glob_credentials_dirs(_ctx({"glob_pattern": "**/.ssh/*"}))
        assert r.passed is False

    def test_glob_double_star_aws_blocks(self):
        r = block_glob_credentials_dirs(_ctx({"glob_pattern": "**/.aws/credentials"}))
        assert r.passed is False

    def test_glob_pem_files_blocks(self):
        r = block_glob_credentials_dirs(_ctx({"glob_pattern": "**/*.pem"}))
        assert r.passed is False

    def test_glob_id_rsa_blocks(self):
        r = block_glob_credentials_dirs(_ctx({"glob_pattern": "**/id_rsa"}))
        assert r.passed is False

    def test_glob_innocent_pattern_passes(self):
        r = block_glob_credentials_dirs(_ctx({"glob_pattern": "src/**/*.py"}))
        assert r.passed is True

    def test_glob_credentials_word_boundary_blocks(self):
        # "credentials" appears as a whole word — should block (intentional)
        r = block_glob_credentials_dirs(_ctx({"glob_pattern": "**/update_credentials_form.html"}))
        assert r.passed is False

    def test_glob_credit_substring_passes(self):
        # "credit" is NOT "credential" — word boundary prevents false positive
        r = block_glob_credentials_dirs(_ctx({"glob_pattern": "src/credit/*.py"}))
        assert r.passed is True

    def test_no_glob_pattern_passes(self):
        r = block_glob_credentials_dirs(_ctx({}))
        assert r.passed is True
```

**Implementation (NEW — enact/policies/file_access.py):**

```python
"""
File-access policies — patterns that only make sense when the agent uses
Read/Write/Edit/Glob/Grep tools (not raw shell). Existing
enact/policies/filesystem.py covers path-based policies (.env, .gitignore,
~/.aws, CI/CD); this module covers the patterns that key off the GLOB or
GREP REGEX itself.
"""
import re
from enact.models import WorkflowContext, PolicyResult


_SECRET_GREP_PATTERNS = [
    re.compile(r"(?i)aws_secret_access_key"),
    re.compile(r"(?i)\bAPI[_-]?KEY\b"),
    re.compile(r"(?i)password\s*[=:]"),
    re.compile(r"(?i)secret[_-]?key"),
    re.compile(r"(?i)BEGIN.*PRIVATE\s+KEY"),
    re.compile(r"(?i)bearer\s+token"),
    re.compile(r"(?i)access[_-]?token"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # OpenAI-style key literal
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),  # GitHub PAT literal
]


def block_grep_secret_patterns(context: WorkflowContext) -> PolicyResult:
    """
    Block Grep searches for known secret regex patterns.

    An agent grepping for `aws_secret_access_key` is asking for one outcome:
    finding hardcoded credentials. Even read-only, this is exfil-shaped
    behavior — the result lands in the agent's context and may be summarized
    back to the operator (or to the conversation transcript).

    Reads context.payload.get("grep_pattern", ""). Pass-through if empty.
    """
    pattern = context.payload.get("grep_pattern", "") or ""
    if not pattern:
        return PolicyResult(
            policy="block_grep_secret_patterns", passed=True,
            reason="No grep pattern in payload",
        )
    for matcher in _SECRET_GREP_PATTERNS:
        if matcher.search(pattern):
            return PolicyResult(
                policy="block_grep_secret_patterns", passed=False,
                reason=(
                    f"Grep pattern '{pattern}' matches a known secret/credential "
                    f"signature — searching for credentials is not permitted"
                ),
            )
    return PolicyResult(
        policy="block_grep_secret_patterns", passed=True,
        reason=f"Grep pattern '{pattern}' is not a known secret signature",
    )


_CRED_GLOB_PATTERNS = [
    # Credential directories (~/.aws/*, **/.ssh/*, etc.)
    re.compile(r"\.aws(/|$)", re.IGNORECASE),
    re.compile(r"\.ssh(/|$)", re.IGNORECASE),
    re.compile(r"\.gnupg(/|$)", re.IGNORECASE),
    re.compile(r"\.kube(/|$)", re.IGNORECASE),
    re.compile(r"\.docker(/|$)", re.IGNORECASE),
    # Specific credential file shapes
    re.compile(r"\bnetrc\b", re.IGNORECASE),
    re.compile(r"\bid_rsa\b", re.IGNORECASE),
    re.compile(r"\bid_ed25519\b", re.IGNORECASE),
    re.compile(r"\bid_dsa\b", re.IGNORECASE),
    re.compile(r"\bid_ecdsa\b", re.IGNORECASE),
    re.compile(r"\bcredentials?\b", re.IGNORECASE),
    # Cert/key glob shapes (** / *.pem, **/*.key, etc.)
    re.compile(r"\*\.pem\b", re.IGNORECASE),
    re.compile(r"\*\.key\b", re.IGNORECASE),
    re.compile(r"\*\.pfx\b", re.IGNORECASE),
    re.compile(r"\*\.p12\b", re.IGNORECASE),
    re.compile(r"\*\.crt\b", re.IGNORECASE),
]


def block_glob_credentials_dirs(context: WorkflowContext) -> PolicyResult:
    """
    Block Glob patterns that fish for credential files or directories.

    Looks at the GLOB pattern itself (not the resolved file). An agent
    asking for `~/.aws/*` or `**/credentials` is enumerating secrets.
    Reads context.payload.get("glob_pattern", ""). Pass-through if empty.
    """
    pattern = context.payload.get("glob_pattern", "") or ""
    if not pattern:
        return PolicyResult(
            policy="block_glob_credentials_dirs", passed=True,
            reason="No glob pattern in payload",
        )
    for matcher in _CRED_GLOB_PATTERNS:
        if matcher.search(pattern):
            return PolicyResult(
                policy="block_glob_credentials_dirs", passed=False,
                reason=(
                    f"Glob pattern '{pattern}' targets a credential "
                    f"file/directory — enumeration not permitted"
                ),
            )
    return PolicyResult(
        policy="block_glob_credentials_dirs", passed=True,
        reason=f"Glob pattern '{pattern}' does not target credentials",
    )


FILE_ACCESS_POLICIES = [
    block_grep_secret_patterns,
    block_glob_credentials_dirs,
]
```

**Run:** `pytest tests/test_file_access_policies.py -v`
**Green means:** All 12 tests pass.
**Commit:** `"feat(policies): file_access — Grep secret patterns + Glob credential-dir patterns"`

### Cycle 6: Wire defaults into the `.enact/policies.py` template 🔴🟢🔄

**Goal:** When a user runs `enact-code-hook init` for the first time, the default policies file imports the file-access policies so they fire on Read/Write/Edit/Glob/Grep out of the box.

**Test (extend TestCmdInit):**

```python
def test_default_policies_file_includes_file_access(self, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cmd_init()
    contents = (tmp_path / ".enact" / "policies.py").read_text()
    # File-path policies — fire on Read/Write/Edit
    assert "dont_read_env" in contents
    assert "dont_touch_ci_cd" in contents
    assert "dont_edit_gitignore" in contents
    assert "dont_access_home_dir" in contents
    assert "dont_copy_api_keys" in contents
    # New file_access policies — fire on Glob/Grep patterns
    assert "FILE_ACCESS_POLICIES" in contents or \
           "block_grep_secret_patterns" in contents
```

**Implementation (replace DEFAULT_POLICIES_PY in code_hook.py):**

```python
DEFAULT_POLICIES_PY = '''\
"""Enact policies — edit to customize what the Agent Firewall blocks."""
from enact.policies.git import dont_force_push, dont_commit_api_keys
from enact.policies.db import protect_tables, block_ddl
from enact.policies.time import code_freeze_active
from enact.policies.coding_agent import CODING_AGENT_POLICIES
from enact.policies.filesystem import (
    dont_read_env,
    dont_touch_ci_cd,
    dont_edit_gitignore,
    dont_access_home_dir,
    dont_copy_api_keys,
)
from enact.policies.file_access import FILE_ACCESS_POLICIES

# Defaults cover BOTH shell and file-tool surfaces:
#   - SHELL (Bash): CODING_AGENT_POLICIES + git/db/time defaults
#   - FILE TOOLS (Read/Write/Edit): filesystem path-based policies
#   - SEARCH TOOLS (Glob/Grep): FILE_ACCESS_POLICIES — secret-pattern + credential-dir guards
#
# The same policy library across all surfaces means an agent that tries to
# `cat .env` AND an agent that tries to Read `.env` are both blocked by the
# same dont_read_env policy — defense in depth, no surface-specific gaps.
POLICIES = [
    code_freeze_active,
    block_ddl,
    dont_force_push,
    dont_commit_api_keys,
    protect_tables(["users", "customers", "orders", "payments", "audit_log"]),
    *CODING_AGENT_POLICIES,
    # File-path policies (Read/Write/Edit)
    dont_read_env,
    dont_touch_ci_cd,
    dont_edit_gitignore,
    dont_access_home_dir,
    dont_copy_api_keys,
    # File-access policies (Glob/Grep)
    *FILE_ACCESS_POLICIES,
]
'''
```

**Run:** `pytest tests/test_code_hook.py::TestCmdInit -v`
**Green means:** All TestCmdInit tests pass; the new test confirms file_access imports are present.
**Commit:** `"feat(hook): default policies cover Read/Write/Edit/Glob/Grep out of the box"`

### Cycle 7: Full suite green 🔴🟢🔄

**Run:**

```bash
cd C:/Users/rmill/Desktop/programming/enact-fresh
python -m pytest tests/ -v 2>&1 | tail -50
```

**Green means:** All 135 prior tests still pass + ~28 new tests pass = ~163 total.

**If anything fails:** the most likely failure is a test that previously expected Read/Write to silently bail — those tests need to either (a) use WebFetch as the unsupported-tool stand-in, or (b) be updated to test the new behavior. Fix in place, do NOT mass-skip.

**Commit:** `"test: full suite green after multi-tool hook"` (only if any final test cleanup needed beyond the per-cycle commits)

---

## B.6 SUCCESS CRITERIA

- [ ] All new tests pass (`tests/test_code_hook.py::TestParseToolInput` 10 cases, `TestCmdPreFileAccess` 7 cases, `TestCmdPostMultiTool` 4 cases, plus updated `TestCmdInit` cases)
- [ ] `tests/test_file_access_policies.py` 11 cases pass
- [ ] All 135 prior tests still pass — full `pytest tests/ -v` clean
- [ ] `enact-code-hook init` writes a `.claude/settings.json` with 6 PreToolUse + 6 PostToolUse matchers (Bash, Read, Write, Edit, Glob, Grep) and a `.enact/policies.py` that imports the file-access policy library
- [ ] Smoke test from CLI:
  ```bash
  echo '{"tool_name":"Read","tool_input":{"file_path":".env"}}' | enact-code-hook pre
  # Expected: deny JSON mentioning env / dont_read_env
  echo '{"tool_name":"Glob","tool_input":{"pattern":"~/.aws/*"}}' | enact-code-hook pre
  # Expected: deny JSON mentioning home dir or credentials
  ```

## How this connects to the bigger picture (session 15 north star)

Today: Enact = shell firewall (1 of 8 tools). After this plan: Enact = Agent Firewall (6 of 8 tools — Bash + Read + Write + Edit + Glob + Grep). NotebookEdit, WebFetch, Task deferred to v2 — they're lower-frequency surfaces and the buyer story doesn't need 100% coverage to ring true.

This plan unlocks priority 2 (the 5x2 file-firewall sweep) by giving us the policy enforcement to actually measure. It also unlocks priority 3 (broader copy) — the "shell firewall → Agent Firewall" rename in landing/email is only honest once this ships. And it unlocks the SOC2/HIPAA/GDPR buyer angle — those frameworks all care about read access, and "we hook every tool that touches the filesystem" is the answer they're shopping for.
