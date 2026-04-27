"""Tests for URL-policy class — covers WebFetch tool exfil + downgrade attacks.

Surfaces:
  - block_dns_exfil_domains: known data-exfil destinations (pastebin, webhooks, ngrok, etc.)
  - block_suspicious_tlds: free TLDs (.tk, .ml, .cf, .ga, .gq) over-represented in malware
  - block_raw_ip_urls: bare IP addresses (almost never legit for a coding agent)
  - require_https: plain http:// is downgrade-attackable
  - webfetch_domain_allowlist(allowed): factory; closure-policy with custom allowlist
"""
from enact.models import WorkflowContext
from enact.policies.url import (
    block_dns_exfil_domains,
    block_suspicious_tlds,
    block_raw_ip_urls,
    require_https,
    webfetch_domain_allowlist,
)


def _ctx(url: str = "") -> WorkflowContext:
    return WorkflowContext(
        workflow="tool.webfetch",
        user_email="test@local",
        payload={"url": url, "tool_name": "WebFetch"} if url else {},
    )


# --- block_dns_exfil_domains ---


def test_dns_exfil_passes_safe_domain():
    assert block_dns_exfil_domains(_ctx("https://github.com/anthropic/claude-sdk")).passed is True


def test_dns_exfil_blocks_pastebin():
    assert block_dns_exfil_domains(_ctx("https://pastebin.com/raw/abc123")).passed is False


def test_dns_exfil_blocks_webhook_site():
    assert block_dns_exfil_domains(_ctx("https://webhook.site/abc-def")).passed is False


def test_dns_exfil_blocks_ngrok():
    assert block_dns_exfil_domains(_ctx("https://abc.ngrok.io/x")).passed is False


def test_dns_exfil_blocks_ngrok_app():
    assert block_dns_exfil_domains(_ctx("https://abc.ngrok-free.app/x")).passed is False


def test_dns_exfil_blocks_discord_webhooks():
    assert block_dns_exfil_domains(
        _ctx("https://discord.com/api/webhooks/123/abc")
    ).passed is False


def test_dns_exfil_passes_discord_main():
    """The main discord.com domain is fine; only api/webhooks are blocked."""
    assert block_dns_exfil_domains(_ctx("https://discord.com/channels/123")).passed is True


def test_dns_exfil_blocks_telegram_bot_api():
    assert block_dns_exfil_domains(
        _ctx("https://api.telegram.org/bot12345:abc/sendMessage")
    ).passed is False


def test_dns_exfil_passes_when_no_url():
    assert block_dns_exfil_domains(_ctx()).passed is True


# --- block_suspicious_tlds ---


def test_tlds_passes_com():
    assert block_suspicious_tlds(_ctx("https://example.com/path")).passed is True


def test_tlds_blocks_tk():
    assert block_suspicious_tlds(_ctx("https://example.tk/path")).passed is False


def test_tlds_blocks_ml():
    assert block_suspicious_tlds(_ctx("https://foo.ml/path")).passed is False


def test_tlds_blocks_cf():
    assert block_suspicious_tlds(_ctx("https://foo.cf/")).passed is False


def test_tlds_blocks_ga():
    assert block_suspicious_tlds(_ctx("https://foo.ga/")).passed is False


def test_tlds_blocks_gq():
    assert block_suspicious_tlds(_ctx("https://foo.gq/")).passed is False


# --- block_raw_ip_urls ---


def test_raw_ip_passes_domain():
    assert block_raw_ip_urls(_ctx("https://example.com/x")).passed is True


def test_raw_ip_blocks_ipv4():
    assert block_raw_ip_urls(_ctx("http://10.0.0.1/x")).passed is False


def test_raw_ip_blocks_private_ipv4():
    assert block_raw_ip_urls(_ctx("http://192.168.1.1/")).passed is False


def test_raw_ip_blocks_localhost_ip():
    assert block_raw_ip_urls(_ctx("http://127.0.0.1:8000/")).passed is False


# --- require_https ---


def test_https_passes_https():
    assert require_https(_ctx("https://example.com/")).passed is True


def test_https_passes_file_scheme():
    assert require_https(_ctx("file:///tmp/data.json")).passed is True


def test_https_blocks_http():
    assert require_https(_ctx("http://example.com/")).passed is False


# --- webfetch_domain_allowlist factory ---


def test_allowlist_pass_when_match():
    policy = webfetch_domain_allowlist(["docs.enact.cloud"])
    assert policy(_ctx("https://docs.enact.cloud/api")).passed is True


def test_allowlist_blocks_when_no_match():
    policy = webfetch_domain_allowlist(["docs.enact.cloud"])
    assert policy(_ctx("https://evil.com/x")).passed is False


def test_allowlist_off_when_empty():
    """Empty allowlist = policy is off (default), passes everything."""
    policy = webfetch_domain_allowlist([])
    assert policy(_ctx("https://anything.com/x")).passed is True


def test_allowlist_subdomain_match():
    """Suffix match — api.docs.enact.cloud matches docs.enact.cloud entry."""
    policy = webfetch_domain_allowlist(["enact.cloud"])
    assert policy(_ctx("https://api.enact.cloud/x")).passed is True
