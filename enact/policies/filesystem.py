"""
Filesystem safety policies — prevent dangerous file operations by AI agents.

These policies answer the question: "Is this filesystem operation safe to perform?"
They read from context.payload. Workflows are responsible for putting the relevant
fields in the payload before calling enact.run():

  payload["path"] — the file or directory path the workflow intends to operate on

Sentinel policy
----------------
dont_delete_file is a sentinel — it always blocks regardless of payload. Register it
on a client where file deletion should never happen. Same pattern as dont_delete_row
and dont_delete_branch.

Factory policies
-----------------
restrict_paths and block_extensions are factories — they accept configuration and
return a closure satisfying (WorkflowContext) -> PolicyResult:

    EnactClient(policies=[
        dont_delete_file,
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
import os
from pathlib import Path
from enact.models import WorkflowContext, PolicyResult
from enact.policies._secrets import SECRET_PATTERNS


def dont_delete_file(context: WorkflowContext) -> PolicyResult:
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
        policy="dont_delete_file",
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


def dont_edit_gitignore(context: WorkflowContext) -> PolicyResult:
    """
    Block any write or delete operation targeting .gitignore.

    Agents that can modify .gitignore can un-ignore secret files (like .env or
    *.pem) and cause them to be committed to version control on the next push.
    Reads context.payload.get("path", ""). Pass-through if no path in payload.

    Args:
        context — WorkflowContext; reads payload["path"]

    Returns:
        PolicyResult — passed=False if path basename is ".gitignore"
    """
    path_str = context.payload.get("path", "")
    if not path_str:
        return PolicyResult(
            policy="dont_edit_gitignore",
            passed=True,
            reason="No path specified in payload",
        )
    if Path(path_str).name == ".gitignore":
        return PolicyResult(
            policy="dont_edit_gitignore",
            passed=False,
            reason=(
                f"Editing '.gitignore' is not permitted — changes could expose "
                f"sensitive files to version control"
            ),
        )
    return PolicyResult(
        policy="dont_edit_gitignore",
        passed=True,
        reason=f"Path '{path_str}' is not .gitignore",
    )


def dont_read_env(context: WorkflowContext) -> PolicyResult:
    """
    Block any read or write operation targeting .env files.

    .env files typically contain API keys, database passwords, and other secrets.
    Agents reading them risk exfiltrating credentials; agents writing them risk
    overwriting secrets. Matches: ".env", ".env.local", ".env.production",
    ".env.test", any file with a ".env" extension.

    Reads context.payload.get("path", ""). Pass-through if no path in payload.

    Args:
        context — WorkflowContext; reads payload["path"]

    Returns:
        PolicyResult — passed=False if path is an env file
    """
    path_str = context.payload.get("path", "")
    if not path_str:
        return PolicyResult(
            policy="dont_read_env",
            passed=True,
            reason="No path specified in payload",
        )
    p = Path(path_str)
    name = p.name
    is_env_file = name == ".env" or name.startswith(".env.") or p.suffix == ".env"
    if is_env_file:
        return PolicyResult(
            policy="dont_read_env",
            passed=False,
            reason=f"Accessing env file '{path_str}' is not permitted — it may contain secrets",
        )
    return PolicyResult(
        policy="dont_read_env",
        passed=True,
        reason=f"Path '{path_str}' is not an env file",
    )


_CI_CD_FILENAMES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "fly.toml",
    ".travis.yml",
    ".gitlab-ci.yml",
    "Jenkinsfile",
}

_CI_CD_DIR_PREFIXES = (
    ".github/workflows",
    ".github/actions",
    ".circleci",
)


def dont_touch_ci_cd(context: WorkflowContext) -> PolicyResult:
    """
    Block writes to CI/CD pipeline files and directories.

    An agent that can modify CI/CD config can inject arbitrary commands into the
    build pipeline — effectively granting itself root on build runners, access to
    all pipeline secrets, and the ability to publish to production without review.

    Blocks writes to:
      - Named files: Dockerfile, docker-compose.yml/yaml, fly.toml, Jenkinsfile,
        .travis.yml, .gitlab-ci.yml
      - Directories: .github/workflows/, .github/actions/, .circleci/

    Reads context.payload.get("path", ""). Pass-through if no path in payload.

    Args:
        context — WorkflowContext; reads payload["path"]

    Returns:
        PolicyResult — passed=False if path is a CI/CD file or under a CI/CD dir
    """
    path_str = context.payload.get("path", "")
    if not path_str:
        return PolicyResult(
            policy="dont_touch_ci_cd",
            passed=True,
            reason="No path specified in payload",
        )
    if Path(path_str).name in _CI_CD_FILENAMES:
        return PolicyResult(
            policy="dont_touch_ci_cd",
            passed=False,
            reason=(
                f"Modifying CI/CD file '{path_str}' is not permitted — "
                f"changes could compromise the build pipeline or expose secrets"
            ),
        )
    # Normalize separators; strip leading "./" only (not bare "."), preserving ".github"
    normalized = path_str.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    for prefix in _CI_CD_DIR_PREFIXES:
        if normalized.startswith(prefix + "/") or normalized == prefix:
            return PolicyResult(
                policy="dont_touch_ci_cd",
                passed=False,
                reason=(
                    f"Path '{path_str}' is under a CI/CD directory — "
                    f"modifications not permitted"
                ),
            )
    return PolicyResult(
        policy="dont_touch_ci_cd",
        passed=True,
        reason=f"Path '{path_str}' is not a CI/CD file",
    )


def dont_access_home_dir(context: WorkflowContext) -> PolicyResult:
    """
    Block any file operation targeting a user's home directory.

    Home directories contain SSH keys, shell configs (.bashrc, .zshrc),
    browser profiles, credential files (~/.aws/credentials, ~/.ssh/id_rsa),
    and other high-value targets. The Claude Code rm -rf incident (2025) was
    a home directory wipe. This policy prevents that class of accident.

    Expands ~ before resolving, so "~/secrets.txt" is caught. Blocks paths
    under /home/, /root/, and the current user's home directory.

    Reads context.payload.get("path", ""). Pass-through if no path in payload.

    Args:
        context — WorkflowContext; reads payload["path"]

    Returns:
        PolicyResult — passed=False if path resolves into a home directory
    """
    path_str = context.payload.get("path", "")
    if not path_str:
        return PolicyResult(
            policy="dont_access_home_dir",
            passed=True,
            reason="No path specified in payload",
        )
    # Normalize to forward slashes for cross-platform string checks
    normalized = path_str.replace("\\", "/")

    # Tilde shorthand — always a home dir reference
    if normalized == "~" or normalized.startswith("~/"):
        return PolicyResult(
            policy="dont_access_home_dir",
            passed=False,
            reason=f"Path '{path_str}' resolves into a home directory — access not permitted",
        )

    # Well-known Unix home prefixes (string-based, works on all platforms)
    unix_prefixes = ("/root", "/home")
    for prefix in unix_prefixes:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return PolicyResult(
                policy="dont_access_home_dir",
                passed=False,
                reason=f"Path '{path_str}' resolves into a home directory — access not permitted",
            )

    # Cross-platform: check against the actual current user's home dir,
    # but ONLY for absolute paths. Relative paths resolve against cwd, and
    # most dev projects live under home (e.g. ~/projects/myrepo). Treating
    # every "src/main.py" as a home-dir attack would block normal work.
    # The intent of this policy is to catch EXPLICIT home references
    # (~/, /root/, /home/<user>/, or absolute path under home) — not
    # incidental cwd-relative reads.
    if os.path.isabs(path_str):
        try:
            home = Path.home()
            resolved = Path(path_str).resolve()
            resolved.relative_to(home)
            return PolicyResult(
                policy="dont_access_home_dir",
                passed=False,
                reason=f"Path '{path_str}' resolves into a home directory — access not permitted",
            )
        except (ValueError, Exception):
            pass

    return PolicyResult(
        policy="dont_access_home_dir",
        passed=True,
        reason=f"Path '{path_str}' is not under a home directory",
    )


def dont_copy_api_keys(context: WorkflowContext) -> PolicyResult:
    """
    Block file writes whose content contains API key patterns.

    Prevents agents from writing files that contain credentials — for example,
    an LLM-generated code fix that hardcodes a token, or a script that embeds
    an API key as a constant. Checks payload["content"] against known vendor
    key formats (OpenAI, GitHub, Slack, AWS, Google).

    Workflows must put the file content in payload["content"] for this policy
    to inspect it. If no "content" key is present, the policy passes through.

    Detection is conservative by design — it matches known vendor formats rather
    than arbitrary high-entropy strings, to keep false positives low.

    Args:
        context — WorkflowContext; reads payload["content"]

    Returns:
        PolicyResult — passed=False if content matches a known API key pattern
    """
    content = context.payload.get("content", "")
    if not content:
        return PolicyResult(
            policy="dont_copy_api_keys",
            passed=True,
            reason="No content in payload",
        )
    for pattern in SECRET_PATTERNS:
        if pattern.search(content):
            return PolicyResult(
                policy="dont_copy_api_keys",
                passed=False,
                reason="Possible API key detected in file content — writing credentials to files is not permitted",
            )
    return PolicyResult(
        policy="dont_copy_api_keys",
        passed=True,
        reason="No API key patterns detected in content",
    )
