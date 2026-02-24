import pytest
from enact.policy import evaluate_all, all_passed
from enact.models import WorkflowContext, PolicyResult


def make_context(**overrides):
    """Helper to build a WorkflowContext with defaults."""
    defaults = {
        "workflow": "test_workflow",
        "actor_email": "agent@test.com",
        "payload": {"key": "value"},
        "systems": {},
    }
    defaults.update(overrides)
    return WorkflowContext(**defaults)


def policy_always_pass(ctx: WorkflowContext) -> PolicyResult:
    return PolicyResult(policy="always_pass", passed=True, reason="Always passes")


def policy_always_fail(ctx: WorkflowContext) -> PolicyResult:
    return PolicyResult(policy="always_fail", passed=False, reason="Always fails")


def policy_check_email(ctx: WorkflowContext) -> PolicyResult:
    valid = "@" in ctx.actor_email
    return PolicyResult(
        policy="check_email",
        passed=valid,
        reason="Valid email" if valid else "Invalid email format",
    )


class TestEvaluateAll:
    def test_all_pass(self):
        ctx = make_context()
        results = evaluate_all(ctx, [policy_always_pass, policy_check_email])
        assert len(results) == 2
        assert all(r.passed for r in results)

    def test_one_fails(self):
        ctx = make_context()
        results = evaluate_all(ctx, [policy_always_pass, policy_always_fail])
        assert len(results) == 2
        assert results[0].passed is True
        assert results[1].passed is False

    def test_never_bails_early(self):
        """Even when first policy fails, ALL policies still run."""
        ctx = make_context()
        results = evaluate_all(
            ctx, [policy_always_fail, policy_always_pass, policy_always_fail]
        )
        assert len(results) == 3  # All 3 ran, not just the first failure

    def test_empty_policies(self):
        ctx = make_context()
        results = evaluate_all(ctx, [])
        assert results == []

    def test_policy_receives_context(self):
        """Verify the context is passed through to each policy."""
        received = {}

        def capture_policy(ctx):
            received["email"] = ctx.actor_email
            return PolicyResult(policy="capture", passed=True, reason="ok")

        ctx = make_context(actor_email="special@test.com")
        evaluate_all(ctx, [capture_policy])
        assert received["email"] == "special@test.com"


class TestAllPassed:
    def test_all_true(self):
        results = [
            PolicyResult(policy="a", passed=True, reason="ok"),
            PolicyResult(policy="b", passed=True, reason="ok"),
        ]
        assert all_passed(results) is True

    def test_one_false(self):
        results = [
            PolicyResult(policy="a", passed=True, reason="ok"),
            PolicyResult(policy="b", passed=False, reason="nope"),
        ]
        assert all_passed(results) is False

    def test_empty_list(self):
        assert all_passed([]) is True


class TestDeterminism:
    """Same input + same policies = same results. Always."""

    def test_idempotent(self):
        ctx = make_context()
        policies = [policy_always_pass, policy_always_fail, policy_check_email]
        run1 = evaluate_all(ctx, policies)
        run2 = evaluate_all(ctx, policies)
        assert len(run1) == len(run2)
        for r1, r2 in zip(run1, run2):
            assert r1.policy == r2.policy
            assert r1.passed == r2.passed
            assert r1.reason == r2.reason
