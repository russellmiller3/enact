"""
HITL (Human-in-the-Loop) endpoints.

POST /hitl/request     — SDK calls this to request human approval
GET  /hitl/{id}        — SDK polls this to check status
GET  /hitl/{id}/approve?t=TOKEN  — human clicks this in email (confirm page)
POST /hitl/{id}/approve?t=TOKEN  — human confirms approve
GET  /hitl/{id}/deny?t=TOKEN     — human clicks this in email (confirm page)
POST /hitl/{id}/deny?t=TOKEN     — human confirms deny
"""
import hmac
import hashlib
import json
import logging
import os
import threading
import urllib.request
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from cloud.auth import resolve_api_key
from cloud.db import db
from cloud.token import verify_token
from cloud.approval_email import send_approval_email

router = APIRouter()

_HITL_STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0b1020;--surface:#131b2e;--border:#2a3447;--text:#fff;--muted:#94a3b8;--subtle:#64748b;--accent:#4A6FA5;--green:#059669;--red:#dc2626;--amber:#d97706;--mono:'IBM Plex Mono','Courier New',monospace;--sans:'Inter',sans-serif}
body{font-family:var(--sans);background:var(--bg);color:var(--text);min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px;-webkit-font-smoothing:antialiased}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;width:100%;max-width:520px;overflow:hidden}
.card-header{padding:20px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px}
.logo{font-family:'Roboto',var(--sans);font-weight:700;font-size:16px;letter-spacing:3px}
.logo-badge{font-family:var(--mono);font-size:10px;font-weight:600;color:var(--accent);background:rgba(74,111,165,0.08);border:1px solid var(--accent);padding:2px 7px;border-radius:4px;letter-spacing:0.06em;text-transform:uppercase}
.card-body{padding:28px 24px}
.card-title{font-size:18px;font-weight:700;margin-bottom:16px}
.field{display:flex;margin-bottom:10px;font-size:13px}
.field-label{width:100px;flex-shrink:0;color:var(--muted);font-size:12px}
.field-val{font-family:var(--mono);font-size:12px}
.section-title{font-size:11px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:var(--accent);margin:20px 0 10px}
.policy-row{display:flex;align-items:center;gap:8px;padding:8px 10px;background:var(--bg);border-radius:6px;margin-bottom:4px;font-size:12px;font-family:var(--mono)}
.dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.dot-pass{background:var(--green)}.dot-fail{background:var(--red)}
.timer{text-align:center;margin:20px 0 4px;font-family:var(--mono);font-size:13px;color:var(--amber)}
.timer-label{font-size:11px;color:var(--subtle);text-align:center;margin-bottom:20px}
.actions{display:flex;gap:12px}
.btn{flex:1;padding:14px;border:none;border-radius:8px;font-size:15px;font-weight:700;font-family:var(--mono);cursor:pointer;transition:opacity 0.15s}
.btn:hover{opacity:0.85}
.btn-approve{background:var(--green);color:#fff}
.btn-deny{background:var(--red);color:#fff}
.note{text-align:center;margin-top:16px;font-size:11px;color:var(--subtle);line-height:1.5}
.badge{display:inline-block;padding:3px 10px;border-radius:5px;font-size:11px;font-weight:700;font-family:var(--mono)}
.badge-pass{background:rgba(5,150,105,0.12);color:var(--green);border:1px solid rgba(5,150,105,0.25)}
.badge-block{background:rgba(220,38,38,0.1);color:var(--red);border:1px solid rgba(220,38,38,0.2)}
.result-icon{font-size:48px;text-align:center;margin-bottom:16px}
.result-title{font-size:22px;font-weight:700;text-align:center;margin-bottom:8px}
.result-desc{font-size:14px;color:var(--muted);text-align:center;line-height:1.6}
@media(max-width:480px){.card{border-radius:0;border-left:0;border-right:0}.actions{flex-direction:column}}
</style>
"""

_HITL_HEADER = """
<div class="card-header">
    <span class="logo">ENACT</span>
    <span class="logo-badge">HITL</span>
</div>
"""


class HitlRequest(BaseModel):
    workflow: str
    payload: dict
    notify_email: str
    expires_in_seconds: int = 3600          # 1 hour default
    callback_url: str | None = None         # if set, POST decision here; SDK doesn't need to poll


@router.post("/hitl/request", status_code=201)
def create_hitl_request(body: HitlRequest, team_id: str = Depends(resolve_api_key)):
    hitl_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=body.expires_in_seconds)
    # Store as fixed UTC format — Python 3.9's fromisoformat can't parse isoformat()'s +00:00 suffix.
    # All datetime storage in this module uses "%Y-%m-%dT%H:%M:%SZ".
    expires_at_str = expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    with db() as conn:
        conn.execute(
            """INSERT INTO hitl_requests
               (hitl_id, team_id, workflow, payload, notify_email, callback_url, expires_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (hitl_id, team_id, body.workflow, json.dumps(body.payload),
             body.notify_email, body.callback_url, expires_at_str),
        )

    send_approval_email(
        hitl_id=hitl_id,
        workflow=body.workflow,
        payload=body.payload,
        notify_email=body.notify_email,
        expires_at=expires_at_str,
    )

    return {"hitl_id": hitl_id, "status": "PENDING", "expires_at": expires_at_str}


@router.get("/hitl/{hitl_id}")
def get_hitl_status(hitl_id: str, team_id: str = Depends(resolve_api_key)):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM hitl_requests WHERE hitl_id = %s AND team_id = %s",
            (hitl_id, team_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="HITL request not found")

        # Auto-expire if past deadline and still PENDING.
        # strptime used instead of fromisoformat because Python 3.9/3.10's
        # fromisoformat cannot parse timezone offsets (+00:00 / Z suffix).
        # Dates are stored as "%Y-%m-%dT%H:%M:%SZ" (always UTC) so strptime is safe.
        status = row["status"]
        if status == "PENDING":
            expires_at = datetime.strptime(row["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                status = "EXPIRED"
                conn.execute(
                    "UPDATE hitl_requests SET status = 'EXPIRED' WHERE hitl_id = %s",
                    (hitl_id,),
                )

    return {
        "hitl_id": hitl_id,
        "status": status,
        "workflow": row["workflow"],
        "decided_at": row["decided_at"],
    }


# ── Approve flow ──────────────────────────────────────────────────────────────

@router.get("/hitl/{hitl_id}/approve", response_class=HTMLResponse)
def approve_confirm_page(hitl_id: str, t: str = Query(...)):
    if not verify_token(t, hitl_id, "approve"):
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    return _render_confirm_page(hitl_id, action="approve")


@router.post("/hitl/{hitl_id}/approve", response_class=HTMLResponse)
def approve_hitl(hitl_id: str, t: str = Query(...)):
    if not verify_token(t, hitl_id, "approve"):
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM hitl_requests WHERE hitl_id = %s", (hitl_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="HITL request not found")
        if row["status"] not in ("PENDING",):
            return _render_result_page(
                icon="&#9888;", title="Already decided",
                desc=f"This request was already {row['status']}.",
            )
        decided_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "UPDATE hitl_requests SET status = 'APPROVED', decided_at = %s WHERE hitl_id = %s",
            (decided_at, hitl_id),
        )
        _write_hitl_receipt(conn, row, decision="APPROVED", decided_at=decided_at)

    if row["callback_url"]:
        _fire_callback(row["callback_url"], hitl_id, "APPROVED")

    return _render_result_page(
        icon="&#10003;", title="Approved",
        desc="The agent will proceed. You can close this tab.",
        color="var(--green)",
    )


# ── Deny flow ─────────────────────────────────────────────────────────────────

@router.get("/hitl/{hitl_id}/deny", response_class=HTMLResponse)
def deny_confirm_page(hitl_id: str, t: str = Query(...)):
    if not verify_token(t, hitl_id, "deny"):
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    return _render_confirm_page(hitl_id, action="deny")


@router.post("/hitl/{hitl_id}/deny", response_class=HTMLResponse)
def deny_hitl(hitl_id: str, t: str = Query(...)):
    if not verify_token(t, hitl_id, "deny"):
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM hitl_requests WHERE hitl_id = %s", (hitl_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="HITL request not found")
        if row["status"] not in ("PENDING",):
            return _render_result_page(
                icon="&#9888;", title="Already decided",
                desc=f"This request was already {row['status']}.",
            )
        decided_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "UPDATE hitl_requests SET status = 'DENIED', decided_at = %s WHERE hitl_id = %s",
            (decided_at, hitl_id),
        )
        _write_hitl_receipt(conn, row, decision="DENIED", decided_at=decided_at)

    if row["callback_url"]:
        _fire_callback(row["callback_url"], hitl_id, "DENIED")

    return _render_result_page(
        icon="&#10005;", title="Denied",
        desc="The agent has been blocked. You can close this tab.",
        color="var(--red)",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _render_confirm_page(hitl_id: str, action: str) -> str:
    """Render a branded HITL confirmation page with workflow context and countdown."""
    from markupsafe import escape
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM hitl_requests WHERE hitl_id = %s", (hitl_id,)
        ).fetchone()
    if not row:
        return _render_result_page(icon="&#9888;", title="Not found", desc="This request does not exist.")

    if row["status"] != "PENDING":
        return _render_result_page(
            icon="&#9888;", title="Already decided",
            desc=f"This request was already {row['status']}.",
        )

    workflow = escape(row["workflow"])
    payload = json.loads(row["payload"])
    payload_summary = escape(json.dumps(payload, indent=2)[:300])
    expires_at = row["expires_at"]
    is_approve = action == "approve"

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Enact — Human Approval Required</title>
{_HITL_STYLES}
</head><body>
<div class="card">
{_HITL_HEADER}
<div class="card-body">
    <div class="card-title">{'Approve' if is_approve else 'Deny'} this workflow run?</div>
    <div class="field"><span class="field-label">Workflow</span><span class="field-val">{workflow}</span></div>
    <div class="field"><span class="field-label">Request ID</span><span class="field-val">{escape(hitl_id[:12])}...</span></div>
    <div class="field"><span class="field-label">Expires</span><span class="field-val">{escape(expires_at)}</span></div>
    <div class="section-title">Action Requested</div>
    <pre style="background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:12px;font-family:var(--mono);font-size:11px;color:var(--muted);overflow-x:auto;white-space:pre-wrap">{payload_summary}</pre>
    <div class="timer" id="countdown"></div>
    <div class="timer-label">remaining</div>
    <form method="POST">
        <div class="actions">
            {'<button type="submit" class="btn btn-approve">Approve</button>' if is_approve else '<button type="submit" class="btn btn-deny">Deny</button>'}
        </div>
    </form>
    <div class="note">This action is cryptographically signed. Token is single-use and time-bound.</div>
</div></div>
<script>
(function(){{
    var exp = new Date("{expires_at}").getTime();
    var el = document.getElementById("countdown");
    function tick(){{
        var diff = exp - Date.now();
        if(diff <= 0){{ el.textContent = "EXPIRED"; return; }}
        var m = Math.floor(diff/60000), s = Math.floor((diff%60000)/1000);
        el.textContent = m + "m " + (s<10?"0":"") + s + "s";
        setTimeout(tick, 1000);
    }}
    tick();
}})();
</script>
</body></html>"""


def _render_result_page(icon: str, title: str, desc: str, color: str = "var(--text)") -> str:
    """Render a branded HITL result page."""
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Enact — {title}</title>
{_HITL_STYLES}
</head><body>
<div class="card">
{_HITL_HEADER}
<div class="card-body" style="text-align:center;padding:48px 24px">
    <div class="result-icon" style="color:{color}">{icon}</div>
    <div class="result-title">{title}</div>
    <div class="result-desc">{desc}</div>
</div></div>
</body></html>"""


def _write_hitl_receipt(conn, row, decision: str, decided_at: str):
    """
    Write a signed HITL approval/denial receipt to hitl_receipts table.
    This is the tamper-proof audit record that a human made a specific decision.

    decided_at is passed in (not re-computed) so it matches the value already
    written to hitl_requests.decided_at in the same transaction.

    Signature is computed over the canonical JSON (sort_keys, compact separators)
    and the same canonical string is stored in receipt_json. This means the
    test can verify: hmac(receipt_json.encode()) == signature without any
    re-serialization gymnastics.
    """
    receipt = {
        "hitl_id": row["hitl_id"],
        "workflow": row["workflow"],
        "decision": decision,
        "decided_by": row["notify_email"],
        "decided_at": decided_at,
    }
    # Canonical JSON: same bytes used for both signing and storage.
    receipt_json = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    secret = os.environ.get("CLOUD_SECRET", "")
    signature = hmac.new(secret.encode(), receipt_json.encode(), hashlib.sha256).hexdigest()

    conn.execute(
        """INSERT INTO hitl_receipts
           (hitl_id, team_id, workflow, decision, decided_by, decided_at, receipt_json, signature)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (hitl_id) DO NOTHING""",
        (row["hitl_id"], row["team_id"], row["workflow"], decision,
         row["notify_email"], decided_at, receipt_json, signature),
    )


def _fire_callback(callback_url: str, hitl_id: str, status: str):
    """
    Fire-and-forget POST to callback_url with the HITL decision.
    Failures are logged but don't affect the response to the approver.
    """
    def _post():
        try:
            data = json.dumps({"hitl_id": hitl_id, "status": status}).encode()
            req = urllib.request.Request(
                callback_url, data=data,
                headers={"Content-Type": "application/json"}, method="POST"
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logging.warning(f"HITL callback failed for {hitl_id}: {e}")

    threading.Thread(target=_post, daemon=True).start()
