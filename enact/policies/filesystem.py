"""
Filesystem safety policies — prevent dangerous file operations by AI agents.

These policies answer the question: "Is this filesystem operation safe to perform?"
They read from context.payload. Workflows are responsible for putting the relevant
fields in the payload before calling enact.run():

  payload["path"] — the file or directory path the workflow intends to operate on

Sentinel policy
----------------
no_delete_file is a sentinel — it always blocks regardless of payload. Register it
on a client where file deletion should never happen. Same pattern as no_delete_row
and no_delete_branch.

Factory policies
-----------------
restrict_paths and block_extensions are factories — they accept configuration and
return a closure satisfying (WorkflowContext) -> PolicyResult:

    EnactClient(policies=[
        no_delete_file,
        restrict_paths(["/workspace/project", "/tmp/scratch"]),
        block_extensions([".env", ".key", ".pem", ".pfx"]),
    ])

Path safety note
-----------------
restrict_paths resolves both the allowed dirs and the target path via pathlib
before comparing, so traversal attempts like "/workspace/../etc/passwd" are
caught even when the payload contains the un-normalized form.

Payload keys used by this module
----------------------------------
  "path" — the file or directory path the workflow intends to operate on
"""
from pathlib import Path
from enact.models import WorkflowContext, PolicyResult


def no_delete_file(context: WorkflowContext) -> PolicyResult:
    """
    Block all file deletion on this client — regardless of path.

    Sentinel policy: register this on any client where delete_file should
    never run. No payload keys are read — the block is unconditional.

    Args:
        context — WorkflowContext (payload not inspected)

    Returns:
        PolicyResult — always passed=False
    """
    return PolicyResult(
        policy="no_delete_file",
        passed=False,
        reason="File deletion is not permitted on this client",
    )


def restrict_paths(allowed_dirs: list[str]):
    """
    Factory: return a policy that blocks operations on paths outside allowed directories.

    Resolves both the allowed directories and the target path before comparing,
    so traversal sequences like "../../etc/passwd" are caught even in their
    un-normalized form. If no path is present in the payload, the policy passes
    through — it can only block what it can see.

    If allowed_dirs is empty, all paths are blocked (nothing is allowed).

    Example:
        EnactClient(policies=[restrict_paths(["/workspace/project"])])

    Payload keys:
        "path" — the file or directory path the workflow intends to operate on.

    Args:
        allowed_dirs — list of directory paths that are safe to operate within

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """
    resolved_allowed = [Path(d).resolve() for d in allowed_dirs]

    def _policy(context: WorkflowContext) -> PolicyResult:
        path_str = context.payload.get("path", "")
        if not path_str:
            return PolicyResult(
                policy="restrict_paths",
                passed=True,
                reason="No path specified in payload",
            )
        target = Path(path_str).resolve()
        for allowed in resolved_allowed:
            try:
                target.relative_to(allowed)
                return PolicyResult(
                    policy="restrict_paths",
                    passed=True,
                    reason=f"Path '{path_str}' is within allowed directory '{allowed}'",
                )
            except ValueError:
                continue
        return PolicyResult(
            policy="restrict_paths",
            passed=False,
            reason=(
                f"Path '{path_str}' is outside all allowed directories. "
                f"Allowed: {[str(d) for d in resolved_allowed]}"
            ),
        )

    return _policy


def block_extensions(extensions: list[str]):
    """
    Factory: return a policy that blocks operations on files with sensitive extensions.

    Protects secret files (.env, .key, .pem, etc.) from being read, overwritten,
    or deleted by agents. The check is case-insensitive so ".ENV" and ".env" are
    both caught. If no path is present in the payload, the policy passes through.

    If extensions is empty, all files are allowed (nothing is blocked).

    Example:
        EnactClient(policies=[block_extensions([".env", ".key", ".pem", ".pfx"])])

    Payload keys:
        "path" — the file path the workflow intends to operate on.

    Args:
        extensions — list of file extensions to block, including the dot (e.g. ".env")

    Returns:
        callable — (WorkflowContext) -> PolicyResult
    """
    blocked_set = {ext.lower() for ext in extensions}

    def _policy(context: WorkflowContext) -> PolicyResult:
        path_str = context.payload.get("path", "")
        if not path_str:
            return PolicyResult(
                policy="block_extensions",
                passed=True,
                reason="No path specified in payload",
            )
        p = Path(path_str)
        suffix = p.suffix.lower()
        # Dotfiles like ".env" have no suffix in pathlib (name IS the stem).
        # Treat the full name as the extension for blocking purposes.
        if not suffix and p.name.startswith("."):
            suffix = p.name.lower()
        if suffix in blocked_set:
            return PolicyResult(
                policy="block_extensions",
                passed=False,
                reason=f"File extension '{suffix}' is blocked — operations on '{path_str}' not permitted",
            )
        return PolicyResult(
            policy="block_extensions",
            passed=True,
            reason=f"File extension '{suffix}' is not blocked",
        )

    return _policy
