"""
Tests for git safety policies and the agent_pr_workflow.
"""
import pytest
from unittest.mock import MagicMock
from enact.policies.git import dont_push_to_main, max_files_per_commit, require_branch_prefix, dont_delete_branch, dont_merge_to_main
from enact.workflows.agent_pr_workflow import agent_pr_workflow
from enact.models import WorkflowContext, ActionResult


def make_context(payload=None):
    return WorkflowContext(
        workflow="test",
        actor_email="agent@test.com",
        payload=payload or {},
        systems={},
    )


class TestNoPushToMain:
    def test_blocks_main(self):
        ctx = make_context({"branch": "main"})
        result = dont_push_to_main(ctx)
        assert result.passed is False
        assert "blocked" in result.reason

    def test_blocks_master(self):
        ctx = make_context({"branch": "master"})
        result = dont_push_to_main(ctx)
        assert result.passed is False

    def test_blocks_case_insensitive(self):
        ctx = make_context({"branch": "MAIN"})
        result = dont_push_to_main(ctx)
        assert result.passed is False

    def test_allows_feature_branch(self):
        ctx = make_context({"branch": "agent/new-feature"})
        result = dont_push_to_main(ctx)
        assert result.passed is True

    def test_allows_empty_branch(self):
        ctx = make_context({})
        result = dont_push_to_main(ctx)
        assert result.passed is True  # empty string not in blocked list

    def test_policy_name(self):
        ctx = make_context({"branch": "main"})
        result = dont_push_to_main(ctx)
        assert result.policy == "dont_push_to_main"


class TestMaxFilesPerCommit:
    def test_blocks_over_limit(self):
        policy = max_files_per_commit(max_files=10)
        ctx = make_context({"file_count": 11})
        result = policy(ctx)
        assert result.passed is False
        assert "11" in result.reason

    def test_allows_at_limit(self):
        policy = max_files_per_commit(max_files=10)
        ctx = make_context({"file_count": 10})
        result = policy(ctx)
        assert result.passed is True

    def test_allows_under_limit(self):
        policy = max_files_per_commit(max_files=50)
        ctx = make_context({"file_count": 5})
        result = policy(ctx)
        assert result.passed is True

    def test_default_limit_is_50(self):
        policy = max_files_per_commit()
        ctx = make_context({"file_count": 51})
        result = policy(ctx)
        assert result.passed is False

    def test_zero_files_passes(self):
        policy = max_files_per_commit(max_files=10)
        ctx = make_context({})  # file_count defaults to 0
        result = policy(ctx)
        assert result.passed is True

    def test_policy_name(self):
        policy = max_files_per_commit(max_files=5)
        ctx = make_context({"file_count": 3})
        result = policy(ctx)
        assert result.policy == "max_files_per_commit"


class TestRequireBranchPrefix:
    def test_blocks_missing_prefix(self):
        policy = require_branch_prefix(prefix="agent/")
        ctx = make_context({"branch": "feature-x"})
        result = policy(ctx)
        assert result.passed is False
        assert "agent/" in result.reason

    def test_allows_correct_prefix(self):
        policy = require_branch_prefix(prefix="agent/")
        ctx = make_context({"branch": "agent/new-feature"})
        result = policy(ctx)
        assert result.passed is True

    def test_default_prefix_is_agent(self):
        policy = require_branch_prefix()
        ctx = make_context({"branch": "main"})
        result = policy(ctx)
        assert result.passed is False

    def test_custom_prefix(self):
        policy = require_branch_prefix(prefix="fix/")
        ctx = make_context({"branch": "fix/bug-123"})
        result = policy(ctx)
        assert result.passed is True

    def test_policy_name(self):
        policy = require_branch_prefix(prefix="agent/")
        ctx = make_context({"branch": "agent/x"})
        result = policy(ctx)
        assert result.policy == "require_branch_prefix"


class TestNoDeleteBranch:
    def test_always_blocks(self):
        """Sentinel policy — blocks regardless of payload."""
        ctx = make_context()
        result = dont_delete_branch(ctx)
        assert result.passed is False

    def test_blocks_even_for_agent_branches(self):
        """Even agent-prefixed branches cannot be deleted on this client."""
        ctx = make_context({"branch": "agent/old-feature"})
        result = dont_delete_branch(ctx)
        assert result.passed is False

    def test_blocks_any_workflow(self):
        ctx = WorkflowContext(
            workflow="branch_cleanup", actor_email="agent@test.com",
            payload={"branch": "stale/branch"}, systems={},
        )
        result = dont_delete_branch(ctx)
        assert result.passed is False

    def test_reason_mentions_deletion(self):
        ctx = make_context()
        result = dont_delete_branch(ctx)
        assert "deletion" in result.reason.lower()

    def test_policy_name(self):
        ctx = make_context()
        result = dont_delete_branch(ctx)
        assert result.policy == "dont_delete_branch"


class TestNoMergeToMain:
    def test_blocks_merge_to_main(self):
        ctx = make_context({"base": "main"})
        result = dont_merge_to_main(ctx)
        assert result.passed is False

    def test_blocks_merge_to_master(self):
        ctx = make_context({"base": "master"})
        result = dont_merge_to_main(ctx)
        assert result.passed is False

    def test_blocks_case_insensitive(self):
        ctx = make_context({"base": "MAIN"})
        result = dont_merge_to_main(ctx)
        assert result.passed is False

    def test_allows_merge_to_staging(self):
        ctx = make_context({"base": "staging"})
        result = dont_merge_to_main(ctx)
        assert result.passed is True

    def test_allows_merge_to_feature_branch(self):
        ctx = make_context({"base": "agent/release-candidate"})
        result = dont_merge_to_main(ctx)
        assert result.passed is True

    def test_allows_empty_base(self):
        """Missing base → can't determine target → pass through."""
        ctx = make_context({})
        result = dont_merge_to_main(ctx)
        assert result.passed is True

    def test_reason_mentions_blocked_on_block(self):
        ctx = make_context({"base": "main"})
        result = dont_merge_to_main(ctx)
        assert "blocked" in result.reason.lower()

    def test_policy_name(self):
        ctx = make_context({"base": "main"})
        result = dont_merge_to_main(ctx)
        assert result.policy == "dont_merge_to_main"


class TestAgentPrWorkflow:
    def _make_gh_mock(self, branch_success=True, pr_success=True):
        gh = MagicMock()
        gh.create_branch.return_value = ActionResult(
            action="create_branch",
            system="github",
            success=branch_success,
            output={"branch": "agent/feature-x"} if branch_success else {"error": "failed"},
        )
        gh.create_pr.return_value = ActionResult(
            action="create_pr",
            system="github",
            success=pr_success,
            output={"pr_number": 42, "url": "https://github.com/owner/repo/pull/42"},
        )
        return gh

    def test_creates_branch_then_pr(self):
        gh = self._make_gh_mock()
        ctx = WorkflowContext(
            workflow="agent_pr_workflow",
            actor_email="agent@test.com",
            payload={"repo": "owner/repo", "branch": "agent/feature-x"},
            systems={"github": gh},
        )

        results = agent_pr_workflow(ctx)

        assert len(results) == 2
        assert results[0].action == "create_branch"
        assert results[0].success is True
        assert results[1].action == "create_pr"
        assert results[1].success is True

    def test_stops_if_branch_fails(self):
        gh = self._make_gh_mock(branch_success=False)
        ctx = WorkflowContext(
            workflow="agent_pr_workflow",
            actor_email="agent@test.com",
            payload={"repo": "owner/repo", "branch": "agent/feature-x"},
            systems={"github": gh},
        )

        results = agent_pr_workflow(ctx)

        assert len(results) == 1  # Only branch attempt, PR not tried
        assert results[0].action == "create_branch"
        assert results[0].success is False
        gh.create_pr.assert_not_called()

    def test_uses_custom_title_and_body(self):
        gh = self._make_gh_mock()
        ctx = WorkflowContext(
            workflow="agent_pr_workflow",
            actor_email="agent@test.com",
            payload={
                "repo": "owner/repo",
                "branch": "agent/feature-x",
                "title": "My custom title",
                "body": "My custom body",
            },
            systems={"github": gh},
        )

        agent_pr_workflow(ctx)

        gh.create_pr.assert_called_once_with(
            repo="owner/repo",
            title="My custom title",
            body="My custom body",
            head="agent/feature-x",
        )
