"""
Filesystem connector — safe, allowlist-gated file operations for AI agents.

Design: allowlist-first
------------------------
Same pattern as GitHubConnector and PostgresConnector. Every public method
calls _check_allowed() before touching the filesystem. Even if a bug in Enact
somehow invokes the wrong action, the connector refuses to execute it unless
that action was explicitly permitted at init time.

Path safety (base_dir)
-----------------------
Every path argument is resolved relative to base_dir. If the resolved path
falls outside base_dir (e.g. via "../../../etc/passwd"), the method returns
ActionResult(success=False) rather than executing. This is the connector-level
hard constraint; the restrict_paths policy adds a separate, receipt-visible
policy-layer check.

The two layers:
  1. Connector base_dir check  — silent, always active, not in receipt
  2. restrict_paths policy     — visible in receipt, configurable per client

Use both for defense in depth.

Idempotency (already_done convention)
--------------------------------------
write_file: already_done="written" if content unchanged; False for a real write
delete_file: already_done="deleted" if file didn't exist; False for a real delete
read_file / list_dir: not mutating, no already_done field

Rollback data
--------------
write_file:  {"path": relative_path, "previous_content": str | None}
             previous_content=None means the file didn't exist before the write;
             rollback = delete the file
delete_file: {"path": relative_path, "content": str}
             rollback = recreate the file with stored content
read_file / list_dir: rollback_data={} (read-only, nothing to undo)

Payload keys for policies
--------------------------
Workflows should put the path in payload before calling enact.run() so that
filesystem policies (restrict_paths, block_extensions, no_delete_file) can
inspect it:

    WorkflowContext(
        workflow="...",
        payload={"path": "src/main.py"},
        systems={"fs": filesystem_connector},
    )
"""
from pathlib import Path
from enact.models import ActionResult


class FilesystemConnector:
    """
    Thin wrapper around stdlib filesystem operations with per-instance
    action allowlisting and base_dir path confinement.
    """

    ALLOWED_ACTIONS = ["read_file", "write_file", "delete_file", "list_dir"]

    def __init__(self, base_dir: str, allowed_actions: list[str] | None = None):
        """
        Args:
            base_dir        — all file paths are resolved relative to this directory;
                              operations that escape it are rejected
            allowed_actions — explicit list of permitted action names; defaults to
                              all four actions if None
        """
        self._base = Path(base_dir).resolve()
        self._allowed = set(allowed_actions if allowed_actions is not None else self.ALLOWED_ACTIONS)

    # ── internal helpers ──────────────────────────────────────────────────────

    def _check_allowed(self, action: str) -> None:
        if action not in self._allowed:
            raise PermissionError(
                f"Action '{action}' is not in the allowed_actions list for this FilesystemConnector. "
                f"Allowed: {sorted(self._allowed)}"
            )

    def _resolve(self, path: str) -> Path | None:
        """
        Resolve path relative to base_dir. Returns None if the resolved path
        escapes base_dir (path traversal attempt).
        """
        resolved = (self._base / path).resolve()
        try:
            resolved.relative_to(self._base)
            return resolved
        except ValueError:
            return None

    # ── public actions ─────────────────────────────────────────────────────────

    def write_file(self, path: str, content: str) -> ActionResult:
        """
        Write content to a file, creating it (and any parent directories) if needed.

        Idempotency: if the file already exists with identical content, returns
        already_done="written" without touching the filesystem.

        Args:
            path    — relative path from base_dir (e.g. "src/main.py")
            content — text content to write (UTF-8)

        Returns:
            ActionResult — success=True with {"path": path, "already_done": bool|str}
        """
        self._check_allowed("write_file")
        resolved = self._resolve(path)
        if resolved is None:
            return ActionResult(
                action="write_file", system="filesystem", success=False,
                output={"error": f"Path '{path}' resolves outside base_dir — operation blocked"},
            )
        try:
            previous_content = None
            if resolved.exists():
                previous_content = resolved.read_text(encoding="utf-8")
                if previous_content == content:
                    return ActionResult(
                        action="write_file", system="filesystem", success=True,
                        output={"path": path, "already_done": "written"},
                        rollback_data={},
                    )
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            return ActionResult(
                action="write_file", system="filesystem", success=True,
                output={"path": path, "already_done": False},
                rollback_data={"path": path, "previous_content": previous_content},
            )
        except Exception as e:
            return ActionResult(
                action="write_file", system="filesystem", success=False,
                output={"error": str(e)},
            )

    def read_file(self, path: str) -> ActionResult:
        """
        Read and return the text content of a file.

        Args:
            path — relative path from base_dir

        Returns:
            ActionResult — success=True with {"content": str}, or
                           success=False with {"error": str}
        """
        self._check_allowed("read_file")
        resolved = self._resolve(path)
        if resolved is None:
            return ActionResult(
                action="read_file", system="filesystem", success=False,
                output={"error": f"Path '{path}' resolves outside base_dir — operation blocked"},
            )
        try:
            content = resolved.read_text(encoding="utf-8")
            return ActionResult(
                action="read_file", system="filesystem", success=True,
                output={"path": path, "content": content},
                rollback_data={},
            )
        except FileNotFoundError:
            return ActionResult(
                action="read_file", system="filesystem", success=False,
                output={"error": f"File not found: {path}"},
            )
        except Exception as e:
            return ActionResult(
                action="read_file", system="filesystem", success=False,
                output={"error": str(e)},
            )

    def delete_file(self, path: str) -> ActionResult:
        """
        Delete a file. Idempotent — if the file doesn't exist, returns
        already_done="deleted" rather than failing.

        Stores file content in rollback_data before deleting so the action
        can be reversed via rollback.

        Args:
            path — relative path from base_dir

        Returns:
            ActionResult — success=True with {"path": path, "already_done": bool|str}
        """
        self._check_allowed("delete_file")
        resolved = self._resolve(path)
        if resolved is None:
            return ActionResult(
                action="delete_file", system="filesystem", success=False,
                output={"error": f"Path '{path}' resolves outside base_dir — operation blocked"},
            )
        try:
            if not resolved.exists():
                return ActionResult(
                    action="delete_file", system="filesystem", success=True,
                    output={"path": path, "already_done": "deleted"},
                    rollback_data={},
                )
            content = resolved.read_text(encoding="utf-8")
            resolved.unlink()
            return ActionResult(
                action="delete_file", system="filesystem", success=True,
                output={"path": path, "already_done": False},
                rollback_data={"path": path, "content": content},
            )
        except Exception as e:
            return ActionResult(
                action="delete_file", system="filesystem", success=False,
                output={"error": str(e)},
            )

    def list_dir(self, path: str) -> ActionResult:
        """
        List the names of entries (files and subdirectories) in a directory.

        Args:
            path — relative path from base_dir ("." for the base directory itself)

        Returns:
            ActionResult — success=True with {"path": path, "entries": list[str]}, or
                           success=False with {"error": str}
        """
        self._check_allowed("list_dir")
        resolved = self._resolve(path)
        if resolved is None:
            return ActionResult(
                action="list_dir", system="filesystem", success=False,
                output={"error": f"Path '{path}' resolves outside base_dir — operation blocked"},
            )
        try:
            entries = [entry.name for entry in sorted(resolved.iterdir())]
            return ActionResult(
                action="list_dir", system="filesystem", success=True,
                output={"path": path, "entries": entries},
                rollback_data={},
            )
        except FileNotFoundError:
            return ActionResult(
                action="list_dir", system="filesystem", success=False,
                output={"error": f"Directory not found: {path}"},
            )
        except Exception as e:
            return ActionResult(
                action="list_dir", system="filesystem", success=False,
                output={"error": str(e)},
            )
