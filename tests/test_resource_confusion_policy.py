"""Tests for pause_on_resource_purpose_mismatch — PocketOS-class catch.

Real incident inspiration: PocketOS, Apr 25 2026. Founder asked Cursor (Claude
Opus 4.6) to handle a routine staging task. Agent hit a credential mismatch.
Independently decided to delete a Railway volume to "rebuild." Used a Railway
token created for "domain ops" — used it against `volumeDelete`. Volume was
production. 9 seconds, 3 months of customer data gone.

The policy catches this by reading the credential's intended PURPOSE and the
RESOURCE TARGET of the action. When their scopes don't match, it pauses for
human approval rather than blocking outright (some cross-scope ops are
legitimate; let a human arbitrate).
"""
from enact.models import WorkflowContext
from enact.policies.credential import pause_on_resource_purpose_mismatch


def _ctx(*, credential_purpose: str | None = None,
         resource_target: str | None = None) -> WorkflowContext:
    payload = {}
    if credential_purpose is not None:
        payload["credential_purpose"] = credential_purpose
    if resource_target is not None:
        payload["resource_target"] = resource_target
    return WorkflowContext(
        workflow="tool.api",
        user_email="test@local",
        payload=payload,
    )


def test_pocketos_shape_blocks():
    """Domain-ops token used against volume-delete → BLOCK (pause for human)."""
    ctx = _ctx(credential_purpose="domain registration", resource_target="volume delete")
    result = pause_on_resource_purpose_mismatch(ctx)
    assert result.passed is False
    assert "domain" in result.reason.lower()
    assert "volume" in result.reason.lower()


def test_matching_scope_passes():
    """storage-admin token used against volume-create → PASS."""
    ctx = _ctx(credential_purpose="storage admin", resource_target="volume create")
    result = pause_on_resource_purpose_mismatch(ctx)
    assert result.passed is True


def test_missing_purpose_passes():
    """Don't false-positive on missing data."""
    ctx = _ctx(credential_purpose=None, resource_target="volume delete")
    result = pause_on_resource_purpose_mismatch(ctx)
    assert result.passed is True


def test_missing_resource_passes():
    ctx = _ctx(credential_purpose="domain ops", resource_target=None)
    result = pause_on_resource_purpose_mismatch(ctx)
    assert result.passed is True


def test_both_missing_passes():
    ctx = _ctx()
    result = pause_on_resource_purpose_mismatch(ctx)
    assert result.passed is True


def test_dns_synonym_match():
    """DNS rotation token used against domain transfer → PASS (same scope)."""
    ctx = _ctx(credential_purpose="DNS rotation", resource_target="domain transfer")
    result = pause_on_resource_purpose_mismatch(ctx)
    assert result.passed is True


def test_compute_vs_storage_blocks():
    """Compute token used against storage volume → BLOCK."""
    ctx = _ctx(credential_purpose="vm provisioning", resource_target="disk delete")
    result = pause_on_resource_purpose_mismatch(ctx)
    assert result.passed is False


def test_billing_vs_identity_blocks():
    """Billing token used against user-management → BLOCK."""
    ctx = _ctx(credential_purpose="invoice issuing", resource_target="user delete")
    result = pause_on_resource_purpose_mismatch(ctx)
    assert result.passed is False


def test_unmatched_keywords_passes():
    """If neither side matches a known scope, don't block — too noisy."""
    ctx = _ctx(credential_purpose="quantum widget", resource_target="hyperflux gizmo")
    result = pause_on_resource_purpose_mismatch(ctx)
    assert result.passed is True


def test_reason_proposes_next_step():
    """The reason should suggest 'agent should request scoped credential'."""
    ctx = _ctx(credential_purpose="domain ops", resource_target="volume delete")
    result = pause_on_resource_purpose_mismatch(ctx)
    assert "credential" in result.reason.lower() or "scoped" in result.reason.lower()
