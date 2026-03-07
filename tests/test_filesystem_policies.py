"""
Tests for filesystem safety policies (enact/policies/filesystem.py).

All policies are pure functions over WorkflowContext — no filesystem access needed.
"""
import pytest
from enact.policies.filesystem import (
    dont_delete_file, restrict_paths, block_extensions,
    dont_edit_gitignore, dont_read_env, dont_touch_ci_cd,
    dont_access_home_dir, dont_copy_api_keys,
)
from enact.models import WorkflowContext


def make_context(payload=None):
    return WorkflowContext(
        workflow="test",
        user_email="agent@test.com",
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


# ── dont_edit_gitignore ───────────────────────────────────────────────────────

class TestDontEditGitignore:
    def test_blocks_gitignore(self):
        ctx = make_context({"path": ".gitignore"})
        result = dont_edit_gitignore(ctx)
        assert result.passed is False
        assert ".gitignore" in result.reason

    def test_blocks_gitignore_in_subdir(self):
        ctx = make_context({"path": "subdir/.gitignore"})
        result = dont_edit_gitignore(ctx)
        assert result.passed is False

    def test_allows_other_dotfiles(self):
        ctx = make_context({"path": ".gitattributes"})
        result = dont_edit_gitignore(ctx)
        assert result.passed is True

    def test_allows_file_named_gitignore_without_dot(self):
        ctx = make_context({"path": "gitignore"})
        result = dont_edit_gitignore(ctx)
        assert result.passed is True

    def test_pass_through_on_no_path(self):
        ctx = make_context({})
        result = dont_edit_gitignore(ctx)
        assert result.passed is True

    def test_policy_name(self):
        ctx = make_context({"path": ".gitignore"})
        assert dont_edit_gitignore(ctx).policy == "dont_edit_gitignore"


# ── dont_read_env ─────────────────────────────────────────────────────────────

class TestDontReadEnv:
    def test_blocks_dotenv(self):
        ctx = make_context({"path": ".env"})
        result = dont_read_env(ctx)
        assert result.passed is False

    def test_blocks_dotenv_local(self):
        ctx = make_context({"path": ".env.local"})
        result = dont_read_env(ctx)
        assert result.passed is False

    def test_blocks_dotenv_production(self):
        ctx = make_context({"path": ".env.production"})
        result = dont_read_env(ctx)
        assert result.passed is False

    def test_blocks_env_extension(self):
        ctx = make_context({"path": "config/secrets.env"})
        result = dont_read_env(ctx)
        assert result.passed is False

    def test_allows_envelope_py(self):
        ctx = make_context({"path": "envelope.py"})
        result = dont_read_env(ctx)
        assert result.passed is True

    def test_allows_envconfig_json(self):
        ctx = make_context({"path": "envconfig.json"})
        result = dont_read_env(ctx)
        assert result.passed is True

    def test_pass_through_on_no_path(self):
        ctx = make_context({})
        result = dont_read_env(ctx)
        assert result.passed is True

    def test_policy_name(self):
        ctx = make_context({"path": ".env"})
        assert dont_read_env(ctx).policy == "dont_read_env"


# ── dont_touch_ci_cd ──────────────────────────────────────────────────────────

class TestDontTouchCiCd:
    def test_blocks_dockerfile(self):
        ctx = make_context({"path": "Dockerfile"})
        result = dont_touch_ci_cd(ctx)
        assert result.passed is False

    def test_blocks_docker_compose(self):
        ctx = make_context({"path": "docker-compose.yml"})
        result = dont_touch_ci_cd(ctx)
        assert result.passed is False

    def test_blocks_fly_toml(self):
        ctx = make_context({"path": "fly.toml"})
        result = dont_touch_ci_cd(ctx)
        assert result.passed is False

    def test_blocks_jenkinsfile(self):
        ctx = make_context({"path": "Jenkinsfile"})
        result = dont_touch_ci_cd(ctx)
        assert result.passed is False

    def test_blocks_github_workflows_dir(self):
        ctx = make_context({"path": ".github/workflows/deploy.yml"})
        result = dont_touch_ci_cd(ctx)
        assert result.passed is False

    def test_blocks_circleci_dir(self):
        ctx = make_context({"path": ".circleci/config.yml"})
        result = dont_touch_ci_cd(ctx)
        assert result.passed is False

    def test_allows_regular_yaml(self):
        ctx = make_context({"path": "config/app.yml"})
        result = dont_touch_ci_cd(ctx)
        assert result.passed is True

    def test_allows_src_dockerfile_in_name_only(self):
        # A file named Dockerfile is blocked regardless of location
        ctx = make_context({"path": "src/Dockerfile"})
        result = dont_touch_ci_cd(ctx)
        assert result.passed is False

    def test_pass_through_on_no_path(self):
        ctx = make_context({})
        result = dont_touch_ci_cd(ctx)
        assert result.passed is True

    def test_policy_name(self):
        ctx = make_context({"path": "Dockerfile"})
        assert dont_touch_ci_cd(ctx).policy == "dont_touch_ci_cd"


# ── dont_access_home_dir ──────────────────────────────────────────────────────

class TestDontAccessHomeDir:
    def test_blocks_root_home(self):
        ctx = make_context({"path": "/root/.ssh/id_rsa"})
        result = dont_access_home_dir(ctx)
        assert result.passed is False

    def test_blocks_home_prefix(self):
        ctx = make_context({"path": "/home/ubuntu/.bashrc"})
        result = dont_access_home_dir(ctx)
        assert result.passed is False

    def test_blocks_tilde_expansion(self):
        ctx = make_context({"path": "~/.aws/credentials"})
        result = dont_access_home_dir(ctx)
        assert result.passed is False

    def test_allows_workspace_path(self):
        ctx = make_context({"path": "/workspace/project/main.py"})
        result = dont_access_home_dir(ctx)
        assert result.passed is True

    def test_allows_tmp_path(self):
        ctx = make_context({"path": "/tmp/output.json"})
        result = dont_access_home_dir(ctx)
        assert result.passed is True

    def test_pass_through_on_no_path(self):
        ctx = make_context({})
        result = dont_access_home_dir(ctx)
        assert result.passed is True

    def test_policy_name(self):
        ctx = make_context({"path": "/root/secrets"})
        assert dont_access_home_dir(ctx).policy == "dont_access_home_dir"


# ── dont_copy_api_keys ────────────────────────────────────────────────────────

class TestDontCopyApiKeys:
    def test_blocks_openai_key(self):
        ctx = make_context({"content": "api_key = 'sk-abcdefghijklmnopqrstu12345'"})
        result = dont_copy_api_keys(ctx)
        assert result.passed is False

    def test_blocks_github_pat(self):
        ctx = make_context({"content": "token = 'ghp_" + "a" * 36 + "'"})
        result = dont_copy_api_keys(ctx)
        assert result.passed is False

    def test_blocks_aws_access_key(self):
        ctx = make_context({"content": "aws_key = 'AKIAIOSFODNN7EXAMPLE'"})
        result = dont_copy_api_keys(ctx)
        assert result.passed is False

    def test_blocks_slack_bot_token(self):
        ctx = make_context({"content": "token = 'xoxb-123456789-987654321-abcdefghijk'"})
        result = dont_copy_api_keys(ctx)
        assert result.passed is False

    def test_allows_clean_content(self):
        ctx = make_context({"content": "def hello():\n    return 'world'\n"})
        result = dont_copy_api_keys(ctx)
        assert result.passed is True

    def test_pass_through_on_no_content(self):
        ctx = make_context({})
        result = dont_copy_api_keys(ctx)
        assert result.passed is True

    def test_pass_through_on_empty_content(self):
        ctx = make_context({"content": ""})
        result = dont_copy_api_keys(ctx)
        assert result.passed is True

    def test_policy_name(self):
        ctx = make_context({"content": "sk-" + "x" * 25})
        assert dont_copy_api_keys(ctx).policy == "dont_copy_api_keys"
