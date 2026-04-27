"""
Credential-scope policies — catch the PocketOS-class failure mode.

The pattern: agent uses a credential (API token, OAuth key, etc.) created for
purpose A to perform action B that operates on a different scope. The token
carries a documented purpose; the action operates on a resource. When their
scopes don't match, the policy pauses for human approval rather than blocks
outright — some cross-scope ops are legitimate, and a human can arbitrate.

Real incident: PocketOS, Apr 25 2026. Agent used a Railway token created for
"domain operations" to call `volumeDelete` on a production storage volume. 9
seconds, 3 months of customer data gone.

WHAT (public): pauses for human approval when an action's resource scope does
not match the credential's documented purpose.

HOW (moat — eventually moves to enact-pro): the keyword sets, the matcher
heuristics, the chain-of-scope inference. Today it's a simple keyword bag;
later versions read structured token metadata from the credential vault.
"""
from enact.models import WorkflowContext, PolicyResult


# Scope keyword bags. Maps a SCOPE-NAME to the keywords that classify a
# string into that scope. Multi-keyword bags cover synonyms ("dns" / "domain"
# / "registrar") so the policy isn't tripped up by the user's vocabulary.
_SCOPES: dict[str, tuple[str, ...]] = {
    "dns": ("domain", "dns", "registrar"),
    "storage": ("volume", "storage", "disk"),
    "compute": ("compute", "vm", "container"),
    "billing": ("billing", "subscription", "invoice"),
    "identity": ("user", "auth", "team"),
}


def _classify(text: str) -> str | None:
    """Return the first matching scope name, or None if no scope matched.

    Lowercase substring match. First-match wins to keep the matcher simple
    and predictable. Order matters when keywords could overlap (none currently
    do, but kept in declaration order for stability).
    """
    if not text:
        return None
    haystack = text.lower()
    for scope, keywords in _SCOPES.items():
        for kw in keywords:
            if kw in haystack:
                return scope
    return None


def pause_on_resource_purpose_mismatch(context: WorkflowContext) -> PolicyResult:
    """Pause for human approval when credential purpose ≠ resource scope.

    Reads:
      - context.payload["credential_purpose"]: human-readable purpose label
        of the credential being used (e.g. "domain registration", "storage admin")
      - context.payload["resource_target"]: human-readable description of the
        resource being touched (e.g. "volume delete", "user provisioning")

    Returns passed=False (interpreted as PAUSE / HITL by the cloud flow) when
    both fields are present AND classified into different scopes. Returns
    passed=True if either field is missing OR if both classify to the same
    scope OR if neither classifies (don't be noisy on unknown vocabulary).

    PocketOS reproduction: credential_purpose="domain registration",
    resource_target="volume delete" → scopes "dns" vs "storage" → mismatch
    → BLOCK.
    """
    purpose = context.payload.get("credential_purpose")
    resource = context.payload.get("resource_target")

    if not purpose or not resource:
        return PolicyResult(
            policy="pause_on_resource_purpose_mismatch",
            passed=True,
            reason="No credential purpose or resource target provided — policy passes",
        )

    purpose_scope = _classify(purpose)
    resource_scope = _classify(resource)

    if purpose_scope is None or resource_scope is None:
        return PolicyResult(
            policy="pause_on_resource_purpose_mismatch",
            passed=True,
            reason=(
                f"Could not classify either purpose ({purpose!r}) or resource "
                f"({resource!r}) into a known scope — policy passes (unclassified)"
            ),
        )

    if purpose_scope == resource_scope:
        return PolicyResult(
            policy="pause_on_resource_purpose_mismatch",
            passed=True,
            reason=(
                f"Credential purpose '{purpose}' and resource target '{resource}' "
                f"both classify as '{purpose_scope}' scope — match"
            ),
        )

    return PolicyResult(
        policy="pause_on_resource_purpose_mismatch",
        passed=False,
        reason=(
            f"Credential scope mismatch: credential purpose is '{purpose}' "
            f"({purpose_scope}) but action targets '{resource}' ({resource_scope}). "
            f"Agent should request a credential scoped to '{resource_scope}' before "
            f"proceeding. Real incident: PocketOS, Apr 2026 — domain-ops token "
            f"used against production storage volume."
        ),
    )


# Default registry — importable from .enact/policies.py
CREDENTIAL_POLICIES = [
    pause_on_resource_purpose_mismatch,
]
