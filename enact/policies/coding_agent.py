"""
Coding-agent shell policies — block real-world AI-coding-agent fuckup patterns.

Each policy here maps 1:1 to a documented incident in
docs/research/agent-incidents.md. Pattern-based: scans payload["command"]
(populated by enact.cli.code_hook.parse_bash_command for every Bash tool
call) for the shape of the destructive operation.

These are deliberately broad — false positive on "agent ran terraform
destroy in a sandbox" is a much better outcome than false negative on
"agent ran terraform destroy in prod." If a developer wants the operation
through, they can disable the specific policy in .enact/policies.py or
run the command outside Claude Code.
"""
import re
from enact.models import WorkflowContext, PolicyResult


def _scan(context: WorkflowContext) -> str:
    """Return the command text we should scan. Falls back across keys."""
    for k in ("command", "diff", "content", "action"):
        v = context.payload.get(k) or ""
        if v:
            return v
    return ""


_TERRAFORM_DESTROY_RE = re.compile(
    r'\bterraform\b(?:\s+\S+)*\s+(?:destroy|apply)\b', re.IGNORECASE
)


def block_terraform_destroy(context: WorkflowContext) -> PolicyResult:
    """Block `terraform destroy` and unguarded `terraform apply`.

    DataTalks/Grigorev (Feb 2026): missing-state-file → terraform plan →
    apply destroyed 2.5 years of student data. The destroy verb is
    unconditional; we also catch `apply` since `apply` against a stale
    state is the same outcome.
    """
    cmd = _scan(context)
    if _TERRAFORM_DESTROY_RE.search(cmd):
        return PolicyResult(
            policy="block_terraform_destroy",
            passed=False,
            reason=(
                "terraform destroy/apply blocked — see DataTalks Feb 2026 incident "
                "(missing state file → 2.5 years of data wiped)"
            ),
        )
    return PolicyResult(
        policy="block_terraform_destroy", passed=True,
        reason="No terraform destroy/apply detected",
    )


_DRIZZLE_FORCE_RE = re.compile(
    r'\bdrizzle(?:-kit)?\b.*\b(?:--force|-f)\b', re.IGNORECASE
)


def block_drizzle_force_push(context: WorkflowContext) -> PolicyResult:
    """Block `drizzle-kit push --force` (background-agent prod-wipe pattern)."""
    cmd = _scan(context)
    if _DRIZZLE_FORCE_RE.search(cmd):
        return PolicyResult(
            policy="block_drizzle_force_push",
            passed=False,
            reason="drizzle-kit push --force blocked — background-agent prod-wipe pattern",
        )
    return PolicyResult(
        policy="block_drizzle_force_push", passed=True,
        reason="No drizzle force-push detected",
    )


_AWS_S3_RECURSIVE_RE = re.compile(
    r'\baws\b\s+s3\s+rm\b.*--recursive\b', re.IGNORECASE
)
_AWS_IAM_DELETE_USER_RE = re.compile(
    r'\baws\b\s+iam\s+delete-user\b', re.IGNORECASE
)


def block_aws_s3_recursive_delete(context: WorkflowContext) -> PolicyResult:
    """Block `aws s3 rm s3://bucket --recursive` — one-line bucket wipe."""
    cmd = _scan(context)
    if _AWS_S3_RECURSIVE_RE.search(cmd):
        return PolicyResult(
            policy="block_aws_s3_recursive_delete",
            passed=False,
            reason="aws s3 rm --recursive blocked — one-line bucket wipe pattern",
        )
    return PolicyResult(
        policy="block_aws_s3_recursive_delete", passed=True,
        reason="No recursive S3 delete detected",
    )


def block_aws_iam_delete_user(context: WorkflowContext) -> PolicyResult:
    """Block `aws iam delete-user` — likely service-account collateral damage."""
    cmd = _scan(context)
    if _AWS_IAM_DELETE_USER_RE.search(cmd):
        return PolicyResult(
            policy="block_aws_iam_delete_user",
            passed=False,
            reason="aws iam delete-user blocked — service-account collateral risk",
        )
    return PolicyResult(
        policy="block_aws_iam_delete_user", passed=True,
        reason="No iam delete-user detected",
    )


_KUBECTL_NS_DELETE_RE = re.compile(
    r'\bkubectl\b\s+delete\s+(?:namespace|ns)\b', re.IGNORECASE
)


def block_kubectl_namespace_delete(context: WorkflowContext) -> PolicyResult:
    """Block `kubectl delete namespace` — kills every workload + PVC in scope."""
    cmd = _scan(context)
    if _KUBECTL_NS_DELETE_RE.search(cmd):
        return PolicyResult(
            policy="block_kubectl_namespace_delete",
            passed=False,
            reason="kubectl delete namespace blocked — wipes every workload + PVC",
        )
    return PolicyResult(
        policy="block_kubectl_namespace_delete", passed=True,
        reason="No kubectl namespace delete detected",
    )


_DOCKER_PRUNE_VOLUMES_RE = re.compile(
    r'\bdocker\b.*\bprune\b.*--volumes\b', re.IGNORECASE | re.DOTALL
)


def block_docker_prune_volumes(context: WorkflowContext) -> PolicyResult:
    """Block `docker system prune --volumes` — deletes named volumes incl. DB data."""
    cmd = _scan(context)
    if _DOCKER_PRUNE_VOLUMES_RE.search(cmd):
        return PolicyResult(
            policy="block_docker_prune_volumes",
            passed=False,
            reason="docker prune --volumes blocked — deletes named volumes incl. DB data",
        )
    return PolicyResult(
        policy="block_docker_prune_volumes", passed=True,
        reason="No docker prune --volumes detected",
    )


_GIT_RESET_HARD_RE = re.compile(r'\bgit\b.*\breset\b\s+--hard\b', re.IGNORECASE | re.DOTALL)
_GIT_CLEAN_FORCE_RE = re.compile(r'\bgit\b.*\bclean\b\s+-[a-z]*f[a-z]*d', re.IGNORECASE | re.DOTALL)


def block_git_reset_hard(context: WorkflowContext) -> PolicyResult:
    """Block `git reset --hard` — discards local commits + uncommitted work."""
    cmd = _scan(context)
    if _GIT_RESET_HARD_RE.search(cmd):
        return PolicyResult(
            policy="block_git_reset_hard",
            passed=False,
            reason="git reset --hard blocked — discards local commits + uncommitted work",
        )
    return PolicyResult(
        policy="block_git_reset_hard", passed=True,
        reason="No git reset --hard detected",
    )


def block_git_clean_force(context: WorkflowContext) -> PolicyResult:
    """Block `git clean -fd` — deletes untracked files (.env, .vscode, local config)."""
    cmd = _scan(context)
    if _GIT_CLEAN_FORCE_RE.search(cmd):
        return PolicyResult(
            policy="block_git_clean_force",
            passed=False,
            reason="git clean -fd blocked — deletes untracked files incl. local config",
        )
    return PolicyResult(
        policy="block_git_clean_force", passed=True,
        reason="No git clean -fd detected",
    )


_CHMOD_777_RE = re.compile(
    r'\bchmod\b\s+(?:-R\s+777|777\s+-R)\b', re.IGNORECASE
)


def block_chmod_777_recursive(context: WorkflowContext) -> PolicyResult:
    """Block `chmod -R 777` — security catastrophe, world-writable file tree."""
    cmd = _scan(context)
    if _CHMOD_777_RE.search(cmd):
        return PolicyResult(
            policy="block_chmod_777_recursive",
            passed=False,
            reason="chmod -R 777 blocked — security catastrophe (world-writable tree)",
        )
    return PolicyResult(
        policy="block_chmod_777_recursive", passed=True,
        reason="No chmod -R 777 detected",
    )


# DROP DATABASE catches both "psql -c \"DROP DATABASE\"" via SQL extraction
# and bare "DROP DATABASE" in command text. block_ddl in db.py already
# catches DROP — but block_ddl needs payload["sql"] populated. This policy
# scans the raw command text as a belt-and-suspenders.
_DROP_DATABASE_RE = re.compile(r'\bDROP\s+DATABASE\b', re.IGNORECASE)


def block_drop_database(context: WorkflowContext) -> PolicyResult:
    """Block `DROP DATABASE` — full database obliteration.

    Defense in depth alongside block_ddl; this rule scans the raw shell
    command text so it catches `psql -c \"DROP DATABASE production\"`
    even if the SQL extractor misses the quoting.
    """
    cmd = _scan(context)
    if _DROP_DATABASE_RE.search(cmd):
        return PolicyResult(
            policy="block_drop_database",
            passed=False,
            reason="DROP DATABASE blocked — full database obliteration",
        )
    return PolicyResult(
        policy="block_drop_database", passed=True,
        reason="No DROP DATABASE detected",
    )


# All policies in one list, importable from .enact/policies.py
CODING_AGENT_POLICIES = [
    block_terraform_destroy,
    block_drizzle_force_push,
    block_aws_s3_recursive_delete,
    block_aws_iam_delete_user,
    block_kubectl_namespace_delete,
    block_docker_prune_volumes,
    block_git_reset_hard,
    block_git_clean_force,
    block_chmod_777_recursive,
    block_drop_database,
]
