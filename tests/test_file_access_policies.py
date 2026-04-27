"""Tests for file_access policies — Glob/Grep specific patterns."""
from enact.models import WorkflowContext
from enact.policies.file_access import (
    block_grep_secret_patterns,
    block_glob_credentials_dirs,
    FILE_ACCESS_POLICIES,
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

    def test_grep_for_secret_key_blocks(self):
        r = block_grep_secret_patterns(_ctx({"grep_pattern": "secret_key"}))
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

    def test_glob_double_star_aws_credentials_blocks(self):
        r = block_glob_credentials_dirs(_ctx({"glob_pattern": "**/.aws/credentials"}))
        assert r.passed is False

    def test_glob_pem_files_blocks(self):
        r = block_glob_credentials_dirs(_ctx({"glob_pattern": "**/*.pem"}))
        assert r.passed is False

    def test_glob_id_rsa_blocks(self):
        r = block_glob_credentials_dirs(_ctx({"glob_pattern": "**/id_rsa"}))
        assert r.passed is False

    def test_glob_credentials_word_boundary_blocks(self):
        # "credentials" appears as a whole word — block (intentional)
        r = block_glob_credentials_dirs(_ctx({"glob_pattern": "**/update_credentials_form.html"}))
        assert r.passed is False

    def test_glob_credit_substring_passes(self):
        # "credit" is NOT "credential" — word boundary prevents false positive
        r = block_glob_credentials_dirs(_ctx({"glob_pattern": "src/credit/*.py"}))
        assert r.passed is True

    def test_glob_innocent_python_pattern_passes(self):
        r = block_glob_credentials_dirs(_ctx({"glob_pattern": "src/**/*.py"}))
        assert r.passed is True

    def test_no_glob_pattern_passes(self):
        r = block_glob_credentials_dirs(_ctx({}))
        assert r.passed is True


class TestFileAccessPoliciesExport:
    def test_file_access_policies_exports_both(self):
        names = {p.__name__ for p in FILE_ACCESS_POLICIES}
        assert "block_grep_secret_patterns" in names
        assert "block_glob_credentials_dirs" in names
