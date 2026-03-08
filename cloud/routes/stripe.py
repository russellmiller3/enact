"""
Stripe integration endpoints.

POST /stripe/create-checkout-session  — unauthenticated; returns Stripe Checkout URL
POST /stripe/webhook                  — Stripe webhook handler (signature verified)
GET  /stripe/success                  — branded success page (polls for API key)
GET  /stripe/status/{session_id}      — JSON polling endpoint; one-time key read
"""
import hashlib
import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from cloud.auth import hash_key
from cloud.db import db

router = APIRouter(prefix="/stripe")
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stripe_configured() -> bool:
    return bool(os.environ.get("STRIPE_SECRET_KEY")) and bool(os.environ.get("STRIPE_PRICE_ID"))


class CheckoutRequest(BaseModel):
    customer_email: str | None = None


@router.post("/create-checkout-session")
def create_checkout_session(body: CheckoutRequest, request: Request):
    """Create a Stripe Checkout session and return the hosted URL."""
    if not _stripe_configured():
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    import stripe as stripe_lib
    stripe_lib.api_key = os.environ["STRIPE_SECRET_KEY"]
    price_id = os.environ["STRIPE_PRICE_ID"]

    base_url = str(request.base_url).rstrip("/")
    kwargs = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": f"{base_url}/stripe/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": base_url,
    }
    if body.customer_email:
        kwargs["customer_email"] = body.customer_email

    session = stripe_lib.checkout.Session.create(**kwargs)
    return {"checkout_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.

    checkout.session.completed  — provision team + API key + subscription
    customer.subscription.deleted — mark subscription canceled
    invoice.payment_failed       — mark subscription past_due
    """
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook secret not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    import stripe as stripe_lib
    stripe_lib.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

    try:
        event = stripe_lib.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event["type"]
    event_data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(event_data)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(event_data)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(event_data)
    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)

    return {"received": True}


def _handle_checkout_completed(session: dict):
    """
    Provision team + API key + subscription in one atomic transaction.
    Idempotent: skips if stripe_customer_id already exists in subscriptions.
    """
    stripe_customer_id = session.get("customer", "")
    stripe_subscription_id = session.get("subscription", "")
    customer_email = session.get("customer_details", {}).get("email") or session.get("customer_email", "")
    stripe_session_id = session.get("id", "")

    with db() as conn:
        # Idempotency check — skip if already provisioned for this customer
        existing = conn.execute(
            "SELECT team_id FROM subscriptions WHERE stripe_customer_id = %s",
            (stripe_customer_id,),
        ).fetchone()
        if existing:
            logger.info("Duplicate webhook for customer %s — skipping", stripe_customer_id)
            return

        team_id = str(uuid.uuid4())
        raw_key = f"enact_live_{secrets.token_hex(16)}"
        key_hash = hash_key(raw_key)
        team_name = customer_email or f"team-{team_id[:8]}"

        conn.execute(
            "INSERT INTO teams (team_id, name, plan) VALUES (%s, %s, %s)",
            (team_id, team_name, "cloud"),
        )
        conn.execute(
            "INSERT INTO api_keys (key_hash, team_id, label) VALUES (%s, %s, %s)",
            (key_hash, team_id, "default"),
        )
        conn.execute(
            """INSERT INTO subscriptions
               (team_id, stripe_customer_id, stripe_subscription_id, status, plan_name)
               VALUES (%s, %s, %s, %s, %s)""",
            (team_id, stripe_customer_id, stripe_subscription_id, "active", "cloud"),
        )
        conn.execute(
            """INSERT INTO checkout_sessions
               (session_id, team_id, raw_api_key, customer_email, status)
               VALUES (%s, %s, %s, %s, %s)""",
            (stripe_session_id, team_id, raw_key, customer_email, "completed"),
        )

    logger.info("Provisioned team %s for customer %s", team_id, stripe_customer_id)


def _handle_subscription_deleted(subscription: dict):
    stripe_subscription_id = subscription.get("id", "")
    with db() as conn:
        conn.execute(
            "UPDATE subscriptions SET status = %s, updated_at = %s WHERE stripe_subscription_id = %s",
            ("canceled", _now_iso(), stripe_subscription_id),
        )
    logger.info("Subscription %s marked canceled", stripe_subscription_id)


def _handle_payment_failed(invoice: dict):
    stripe_subscription_id = invoice.get("subscription", "")
    with db() as conn:
        conn.execute(
            "UPDATE subscriptions SET status = %s, updated_at = %s WHERE stripe_subscription_id = %s",
            ("past_due", _now_iso(), stripe_subscription_id),
        )
    logger.info("Subscription %s marked past_due", stripe_subscription_id)


# ── Success page + polling ────────────────────────────────────────────────────

_SUCCESS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Enact Cloud — Setup Complete</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{--bg:#0b1020;--surface:#131b2e;--border:#2a3447;--text:#fff;--muted:#94a3b8;--subtle:#64748b;--accent:#4A6FA5;--green:#059669;--mono:'IBM Plex Mono','Courier New',monospace;--sans:'Inter',sans-serif}}
body{{font-family:var(--sans);background:var(--bg);color:var(--text);min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px;-webkit-font-smoothing:antialiased}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;width:100%;max-width:560px;overflow:hidden}}
.card-header{{padding:20px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px}}
.logo{{font-family:'Roboto',var(--sans);font-weight:700;font-size:16px;letter-spacing:3px}}
.logo-badge{{font-family:var(--mono);font-size:10px;font-weight:600;color:var(--accent);background:rgba(74,111,165,0.08);border:1px solid var(--accent);padding:2px 7px;border-radius:4px;letter-spacing:0.06em;text-transform:uppercase}}
.card-body{{padding:32px 24px}}
.status-icon{{font-size:48px;text-align:center;margin-bottom:16px}}
.title{{font-size:22px;font-weight:700;text-align:center;margin-bottom:8px}}
.subtitle{{font-size:14px;color:var(--muted);text-align:center;margin-bottom:28px;line-height:1.6}}
.key-label{{font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:var(--accent);margin-bottom:8px}}
.key-box{{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:14px 16px;font-family:var(--mono);font-size:13px;word-break:break-all;margin-bottom:12px;position:relative}}
.copy-btn{{margin-top:8px;width:100%;padding:10px;border:1px solid var(--border);background:transparent;color:var(--text);font-family:var(--mono);font-size:12px;border-radius:6px;cursor:pointer;transition:background 0.15s}}
.copy-btn:hover{{background:var(--border)}}
.warning{{background:rgba(217,119,6,0.08);border:1px solid rgba(217,119,6,0.25);border-radius:8px;padding:12px 16px;font-size:12px;color:#fbbf24;margin-bottom:20px;line-height:1.5}}
.docs-link{{display:block;text-align:center;margin-top:20px;font-size:13px;color:var(--accent);text-decoration:none}}
.spinner{{width:32px;height:32px;border:3px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 16px}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
</style>
</head>
<body>
<div class="card">
  <div class="card-header">
    <span class="logo">ENACT</span>
    <span class="logo-badge">CLOUD</span>
  </div>
  <div class="card-body" id="content">
    <div class="spinner"></div>
    <div class="title">Setting up your account&hellip;</div>
    <div class="subtitle">This takes a few seconds. Please don&rsquo;t close this tab.</div>
  </div>
</div>
<script>
const sessionId = new URLSearchParams(location.search).get('session_id');
let attempts = 0;
const MAX = 30;

async function poll() {{
  if (!sessionId || attempts >= MAX) {{
    document.getElementById('content').innerHTML = '<div class="status-icon">&#x26A0;&#xFE0F;</div><div class="title">Something went wrong</div><div class="subtitle">Please email <a href="mailto:support@enact.cloud">support@enact.cloud</a> and we&#39;ll sort it out.</div>';
    return;
  }}
  attempts++;
  try {{
    const r = await fetch('/stripe/status/' + sessionId);
    const data = await r.json();
    if (data.status === 'ready') {{
      showKey(data.api_key);
    }} else if (data.status === 'already_retrieved') {{
      document.getElementById('content').innerHTML = '<div class="status-icon">&#x2705;</div><div class="title">Key already shown</div><div class="subtitle">Your API key was already displayed. Check your browser history or contact support.</div>';
    }} else {{
      setTimeout(poll, 1500);
    }}
  }} catch(e) {{
    setTimeout(poll, 2000);
  }}
}}

function showKey(key) {{
  document.getElementById('content').innerHTML = `
    <div class="status-icon">&#x2705;</div>
    <div class="title">You're in.</div>
    <div class="subtitle">Copy your API key now. For security, it won't be shown again.</div>
    <div class="warning">&#x26A0;&#xFE0F; Save this key somewhere safe. It cannot be recovered.</div>
    <div class="key-label">Your API Key</div>
    <div class="key-box" id="key-text">${{key}}</div>
    <button class="copy-btn" onclick="copyKey('${{key}}')">Copy to clipboard</button>
    <a class="docs-link" href="https://enact.cloud/docs">Get started &rarr;</a>
  `;
}}

function copyKey(key) {{
  navigator.clipboard.writeText(key).then(() => {{
    document.querySelector('.copy-btn').textContent = 'Copied!';
    setTimeout(() => {{ document.querySelector('.copy-btn').textContent = 'Copy to clipboard'; }}, 2000);
  }});
}}

poll();
</script>
</body>
</html>"""


@router.get("/success", response_class=HTMLResponse)
def stripe_success(session_id: str = ""):
    return HTMLResponse(content=_SUCCESS_HTML)


@router.get("/status/{session_id}")
def stripe_status(session_id: str):
    """
    Poll for provisioning status after Stripe Checkout.
    One-time key read: returns raw_api_key once, then NULLs it from DB.
    """
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM checkout_sessions WHERE session_id = %s",
            (session_id,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Session not found")

        if row["status"] == "pending":
            return {"status": "pending"}

        if row["raw_api_key"] is None:
            return {"status": "already_retrieved"}

        # First retrieval — return key and immediately NULL it out
        api_key = row["raw_api_key"]
        conn.execute(
            "UPDATE checkout_sessions SET raw_api_key = NULL, retrieved_at = %s WHERE session_id = %s",
            (_now_iso(), session_id),
        )

    return {"status": "ready", "api_key": api_key}
