"""
URL policies — covers Claude Code's WebFetch tool.

WebFetch is shaped differently from file tools: input is a URL (and a prompt),
not a path. The risk surface is exfiltration via known data-drop services
(pastebin, requestbin, webhook.site, ngrok), suspicious top-level domains,
bare IP addresses, and http:// downgrade attacks.

WHAT (public): five policies cover exfil-domain enumeration, suspicious TLDs,
raw-IP URLs, http downgrade, and a per-deployment domain allowlist factory.

HOW (moat — eventually moves to enact-pro): the exact domain list, the TLD
set, the IP detection logic. Today's lists are starter-kit; production
deployments override or extend via the .enact/policies.py file.
"""
import re
from urllib.parse import urlparse

from enact.models import WorkflowContext, PolicyResult


def _url_from(context: WorkflowContext) -> str:
    """Pull the URL string out of the context payload. Return '' if missing."""
    return (context.payload.get("url") or "").strip()


# --- block_dns_exfil_domains -----------------------------------------------

# Substring patterns matched against URL host + path. Each entry is a
# (description, regex) tuple. Substring match is sufficient — these domains
# don't have legitimate uses for a coding agent's webfetch.
_EXFIL_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("pastebin", re.compile(r"\bpastebin\.com\b", re.IGNORECASE)),
    ("paste.ee", re.compile(r"\bpaste\.ee\b", re.IGNORECASE)),
    ("hastebin", re.compile(r"\bhastebin\.com\b", re.IGNORECASE)),
    ("transfer.sh", re.compile(r"\btransfer\.sh\b", re.IGNORECASE)),
    ("requestbin", re.compile(r"\brequestbin\.com\b", re.IGNORECASE)),
    ("webhook.site", re.compile(r"\bwebhook\.site\b", re.IGNORECASE)),
    ("ngrok", re.compile(r"\bngrok\.(?:io|app)\b", re.IGNORECASE)),
    ("ngrok-free.app", re.compile(r"\bngrok-free\.app\b", re.IGNORECASE)),
    # gist raw user-content (not the main gist.github.com)
    ("gist user content", re.compile(r"\bgist\.githubusercontent\.com\b", re.IGNORECASE)),
    # Discord webhooks specifically — not the main discord.com
    ("discord webhook", re.compile(r"\bdiscord\.com/api/webhooks\b", re.IGNORECASE)),
    # Telegram bot API — used for exfil-via-bot pattern
    ("telegram bot api", re.compile(r"\bapi\.telegram\.org/bot", re.IGNORECASE)),
)


def block_dns_exfil_domains(context: WorkflowContext) -> PolicyResult:
    """Block URLs targeting known data-exfiltration domains."""
    url = _url_from(context)
    if not url:
        return PolicyResult(
            policy="block_dns_exfil_domains",
            passed=True,
            reason="No url in payload",
        )
    for label, pat in _EXFIL_PATTERNS:
        if pat.search(url):
            return PolicyResult(
                policy="block_dns_exfil_domains",
                passed=False,
                reason=(
                    f"URL targets known data-exfil destination ({label}). "
                    f"WebFetch to drop-shaped services is blocked by default "
                    f"because it's a primary exfil vector for AI agents."
                ),
            )
    return PolicyResult(
        policy="block_dns_exfil_domains",
        passed=True,
        reason="URL is not on the known-exfil list",
    )


# --- block_suspicious_tlds -------------------------------------------------

_SUSPICIOUS_TLDS = ("tk", "ml", "cf", "ga", "gq")


def block_suspicious_tlds(context: WorkflowContext) -> PolicyResult:
    """Block URLs ending in free TLDs widely used by attackers (.tk/.ml/.cf/.ga/.gq).

    These TLDs are free to register, anonymous, and have an over-representation
    in malware/phishing telemetry. Coding agents almost never have a legitimate
    reason to fetch from them. False-positive rate against real dev work is
    near zero.
    """
    url = _url_from(context)
    if not url:
        return PolicyResult(
            policy="block_suspicious_tlds",
            passed=True,
            reason="No url in payload",
        )
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        host = ""
    if not host:
        return PolicyResult(
            policy="block_suspicious_tlds",
            passed=True,
            reason="Could not extract host from URL",
        )
    last = host.rsplit(".", 1)[-1] if "." in host else host
    if last in _SUSPICIOUS_TLDS:
        return PolicyResult(
            policy="block_suspicious_tlds",
            passed=False,
            reason=(
                f"URL host ends in '.{last}' — free TLD over-represented in "
                f"malware/phishing. WebFetch blocked by default. Override per-deployment "
                f"if your team genuinely fetches from this TLD."
            ),
        )
    return PolicyResult(
        policy="block_suspicious_tlds",
        passed=True,
        reason=f"URL host TLD '.{last}' is not on the suspicious list",
    )


# --- block_raw_ip_urls -----------------------------------------------------

_IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
_IPV6_BRACKET_RE = re.compile(r"^\[[0-9a-fA-F:]+\]$")


def block_raw_ip_urls(context: WorkflowContext) -> PolicyResult:
    """Block URLs whose host is a bare IP address (almost never legit for an agent)."""
    url = _url_from(context)
    if not url:
        return PolicyResult(
            policy="block_raw_ip_urls",
            passed=True,
            reason="No url in payload",
        )
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        host = ""
    if _IPV4_RE.match(host) or _IPV6_BRACKET_RE.match(host or ""):
        return PolicyResult(
            policy="block_raw_ip_urls",
            passed=False,
            reason=(
                f"URL host '{host}' is a bare IP address. Coding agents rarely "
                f"have a legitimate reason to fetch by IP — typical exfil/scan pattern."
            ),
        )
    return PolicyResult(
        policy="block_raw_ip_urls",
        passed=True,
        reason="URL host is a domain name, not a bare IP",
    )


# --- require_https ---------------------------------------------------------

_HTTP_DOWNGRADE_RE = re.compile(r"^http://", re.IGNORECASE)


def require_https(context: WorkflowContext) -> PolicyResult:
    """Block plain http:// URLs (downgrade-attackable). Allow https://, file://, data:."""
    url = _url_from(context)
    if not url:
        return PolicyResult(
            policy="require_https",
            passed=True,
            reason="No url in payload",
        )
    if _HTTP_DOWNGRADE_RE.match(url):
        return PolicyResult(
            policy="require_https",
            passed=False,
            reason=(
                f"URL uses plain http:// — downgrade-attackable. Use https:// "
                f"or, for local resources, file:// or data:."
            ),
        )
    return PolicyResult(
        policy="require_https",
        passed=True,
        reason="URL is not plain http://",
    )


# --- webfetch_domain_allowlist factory -------------------------------------


def webfetch_domain_allowlist(allowed: list[str]):
    """Closure-policy factory: allow only URLs whose host suffix-matches `allowed`.

    Empty allowlist = policy is OFF (returns pass for everything). When non-empty,
    a URL passes if its hostname ENDS WITH any allowed entry (so 'enact.cloud'
    matches 'docs.enact.cloud' and 'api.enact.cloud').

    Use this in a deployment that wants to lock WebFetch to a narrow set of
    domains — e.g. only docs sites, only the company's own API.
    """
    def policy(context: WorkflowContext) -> PolicyResult:
        if not allowed:
            return PolicyResult(
                policy="webfetch_domain_allowlist",
                passed=True,
                reason="Allowlist is empty — policy is off",
            )
        url = _url_from(context)
        if not url:
            return PolicyResult(
                policy="webfetch_domain_allowlist",
                passed=True,
                reason="No url in payload",
            )
        try:
            host = (urlparse(url).hostname or "").lower()
        except ValueError:
            host = ""
        for allowed_domain in allowed:
            ad = allowed_domain.lower().lstrip(".")
            if host == ad or host.endswith("." + ad):
                return PolicyResult(
                    policy="webfetch_domain_allowlist",
                    passed=True,
                    reason=f"Host '{host}' matches allowlist entry '{ad}'",
                )
        return PolicyResult(
            policy="webfetch_domain_allowlist",
            passed=False,
            reason=(
                f"Host '{host}' is not on the WebFetch allowlist "
                f"({', '.join(allowed)}). Add the domain to .enact/policies.py "
                f"or use a different fetch surface."
            ),
        )
    return policy


# Default registry — importable from .enact/policies.py.
# webfetch_domain_allowlist is intentionally NOT in the default list because
# it requires a deployment-specific allowed list. Callers opt in.
URL_POLICIES = [
    block_dns_exfil_domains,
    block_suspicious_tlds,
    block_raw_ip_urls,
    require_https,
]
