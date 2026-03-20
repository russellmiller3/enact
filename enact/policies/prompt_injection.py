"""
Prompt injection detection policies — block payloads containing injection attempts.

These policies scan payload values for regex patterns commonly used in prompt
injection attacks. When an AI agent passes user-supplied text through to an
action, these policies catch attempts to hijack the agent's instructions.

Two policies:

  block_prompt_injection     — plain function, scans ALL string values in the
                               payload recursively. Blocks if any match.

  block_prompt_injection_fields(fields)
                             — factory, scans only named fields.
                               Use when you know which payload keys contain
                               user-supplied text.

Usage:
    from enact.policies.prompt_injection import (
        block_prompt_injection,
        block_prompt_injection_fields,
    )

    # Scan everything in the payload
    EnactClient(policies=[block_prompt_injection], ...)

    # Scan only specific fields
    EnactClient(policies=[block_prompt_injection_fields(["message", "title"])], ...)

Payload keys used by this module
----------------------------------
  (any) — block_prompt_injection scans all string values recursively
  Named fields only for block_prompt_injection_fields
"""
import re
from enact.models import WorkflowContext, PolicyResult

# Patterns that indicate prompt injection attempts.
# Each tuple: (compiled regex, human-readable description)
# All patterns are case-insensitive.
_INJECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Direct instruction override
    (re.compile(r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|directions?)", re.IGNORECASE),
     "instruction override"),
    (re.compile(r"disregard\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|context)", re.IGNORECASE),
     "instruction override"),
    (re.compile(r"forget\s+(everything|all|your)\s+(you|instructions?|rules?|were|about)", re.IGNORECASE),
     "instruction override"),

    # Role hijacking
    (re.compile(r"you\s+are\s+now\s+(a|an|the|my)\s+", re.IGNORECASE),
     "role hijacking"),
    (re.compile(r"act\s+as\s+(a|an|if|though)\s+", re.IGNORECASE),
     "role hijacking"),
    (re.compile(r"pretend\s+(you\s+are|to\s+be|you're)\s+", re.IGNORECASE),
     "role hijacking"),
    (re.compile(r"from\s+now\s+on,?\s+you\s+(are|will|should|must)", re.IGNORECASE),
     "role hijacking"),

    # System prompt extraction
    (re.compile(r"(show|reveal|print|output|display|repeat|give)\s+(me\s+)?(your|the)\s+(system\s+prompt|instructions?|rules?|initial\s+prompt)", re.IGNORECASE),
     "system prompt extraction"),
    (re.compile(r"what\s+(are|is|were)\s+your\s+(system\s+)?(instructions?|rules?|prompt|directives?)", re.IGNORECASE),
     "system prompt extraction"),

    # New instruction injection
    (re.compile(r"(new|updated|revised|actual)\s+(instructions?|rules?|directives?|prompt)\s*:", re.IGNORECASE),
     "injected instructions"),
    (re.compile(r"\[?\s*system\s*(message|prompt|instruction)\s*\]?\s*:", re.IGNORECASE),
     "injected system message"),
    (re.compile(r"<\s*system\s*>", re.IGNORECASE),
     "injected system tag"),

    # Delimiter attacks
    (re.compile(r"-{5,}\s*(begin|start|end|new)\s*(system|instructions?|prompt)", re.IGNORECASE),
     "delimiter attack"),
    (re.compile(r"#{3,}\s*(system|instructions?|new\s+rules?|override)", re.IGNORECASE),
     "delimiter attack"),

    # Jailbreak phrases
    (re.compile(r"(do\s+anything\s+now|DAN\s+mode|developer\s+mode|jailbreak)", re.IGNORECASE),
     "jailbreak attempt"),
    (re.compile(r"bypass\s+(your\s+)?(safety|content|ethical|security)\s+(filter|policy|guard|restriction|rule)", re.IGNORECASE),
     "safety bypass"),
]


def _extract_strings(obj, depth: int = 0) -> list[str]:
    """Recursively extract all string values from a nested dict/list structure."""
    if depth > 10:
        return []
    strings = []
    if isinstance(obj, str):
        strings.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            strings.extend(_extract_strings(v, depth + 1))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            strings.extend(_extract_strings(item, depth + 1))
    return strings


def _scan_text(text: str) -> tuple[bool, str]:
    """Scan a single string for injection patterns. Returns (is_clean, reason)."""
    for pattern, description in _INJECTION_PATTERNS:
        if pattern.search(text):
            match = pattern.search(text)
            snippet = text[max(0, match.start() - 20):match.end() + 20].strip()
            return False, f"{description}: '...{snippet}...'"
    return True, "clean"


def block_prompt_injection(context: WorkflowContext) -> PolicyResult:
    """
    Block payloads containing prompt injection patterns.

    Scans ALL string values in context.payload recursively. If any string
    matches a known injection pattern, the action is blocked.

    This is a broad scan — use block_prompt_injection_fields() if you want
    to limit scanning to specific payload keys.
    """
    strings = _extract_strings(context.payload)

    for text in strings:
        is_clean, reason = _scan_text(text)
        if not is_clean:
            return PolicyResult(
                policy="block_prompt_injection",
                passed=False,
                reason=f"Prompt injection detected — {reason}",
            )

    return PolicyResult(
        policy="block_prompt_injection",
        passed=True,
        reason="No prompt injection patterns detected",
    )


def block_prompt_injection_fields(fields: list[str]):
    """
    Factory: block payloads where specific fields contain injection patterns.

    Use when you know which payload keys contain user-supplied text:

        block_prompt_injection_fields(["message", "user_input", "title"])

    Only the named fields are scanned. Nested values within those fields
    are scanned recursively.

    Args:
        fields: list of payload key names to scan
    """
    def policy(context: WorkflowContext) -> PolicyResult:
        for field in fields:
            value = context.payload.get(field)
            if value is None:
                continue
            strings = _extract_strings(value)
            for text in strings:
                is_clean, reason = _scan_text(text)
                if not is_clean:
                    return PolicyResult(
                        policy="block_prompt_injection_fields",
                        passed=False,
                        reason=f"Prompt injection in '{field}' — {reason}",
                    )

        return PolicyResult(
            policy="block_prompt_injection_fields",
            passed=True,
            reason="No prompt injection patterns detected",
        )

    policy.__name__ = "block_prompt_injection_fields"
    return policy
