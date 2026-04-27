"""
File-access policies — patterns that only make sense when the agent uses
Read/Write/Edit/Glob/Grep tools (not raw shell).

Existing enact/policies/filesystem.py covers path-based policies for
the file surfaces (.env, .gitignore, ~/.aws, CI/CD). This module covers
the patterns that key off the GLOB or GREP REGEX itself — things you
can only see when the agent is using a search tool, not a file path.

Two policies live here:

  block_grep_secret_patterns
    Looks at payload["grep_pattern"]. Blocks Grep searches for known
    secret/credential signatures (aws_secret_access_key, password=,
    BEGIN PRIVATE KEY, etc.). An agent grepping for these is asking
    one question: "where are the credentials?"

  block_glob_credentials_dirs
    Looks at payload["glob_pattern"]. Blocks Glob patterns that fish
    for credential directories (~/.aws/*, **/.ssh/*) or specific
    credential file shapes (id_rsa, *.pem, *.key, **/credentials).
"""
import re
from enact.models import WorkflowContext, PolicyResult


_SECRET_GREP_PATTERNS = [
    re.compile(r"(?i)aws_secret_access_key"),
    re.compile(r"(?i)\bAPI[_-]?KEY\b"),
    # Match the WORD "password" — agents grep for password\s*=, password:, etc.
    # The pattern itself is a regex string the agent wrote; we match on its text.
    re.compile(r"(?i)\bpassword\b"),
    re.compile(r"(?i)secret[_-]?key"),
    re.compile(r"(?i)BEGIN.*PRIVATE\s+KEY"),
    re.compile(r"(?i)bearer\s+token"),
    re.compile(r"(?i)access[_-]?token"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # OpenAI-style key literal
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),  # GitHub PAT literal
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key literal
]


def block_grep_secret_patterns(context: WorkflowContext) -> PolicyResult:
    """
    Block Grep searches for known secret regex patterns.

    An agent grepping for `aws_secret_access_key` is asking for one
    outcome: finding hardcoded credentials. Even read-only, this is
    exfil-shaped behavior — the result lands in the agent's context
    and may be summarized back to the operator (or the conversation
    transcript stored on Anthropic's servers).

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
    # No \b boundaries — "credentials" embedded in update_credentials_form
    # is a real concern (might be a creds template). "credit" still passes
    # because credentials? requires the literal "credential" prefix.
    re.compile(r"credentials?", re.IGNORECASE),
    # Cert/key glob shapes (**/*.pem, **/*.key, etc.)
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
    asking for `~/.aws/*` or `**/credentials` or `**/*.pem` is
    enumerating secrets — the only legitimate next step would be to
    read them, which is itself a credential exfiltration attempt.

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
