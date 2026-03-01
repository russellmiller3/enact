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
from cloud.email import send_approval_email

router = APIRouter()

_CONFIRM_PAGE = """
<html><body style="font-family:sans-serif;max-width:480px;margin:80px auto;text-align:center">
<h2>{title}</h2>
<p>{desc}</p>
<form method="POST">
  <button type="submit" style="padding:12px 32px;background:{color};color:#fff;border:none;border-radius:6px;font-size:16px;cursor:pointer">
    {label}
  </button>
</form>
</body></html>
"""

_DONE_PAGE = """
<html><body style="font-family:sans-serif;max-width:480px;margin:80px auto;text-align:center">
<h2>{title}</h2><p>{desc}</p>
</body></html>
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
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
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
            "SELECT * FROM hitl_requests WHERE hitl_id = ? AND team_id = ?",
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
                    "UPDATE hitl_requests SET status = 'EXPIRED' WHERE hitl_id = ?",
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
    return _CONFIRM_PAGE.format(
        title="Approve this workflow run?",
        desc="Click below to approve. The agent will proceed immediately.",
        color="#16a34a",
        label="Approve",
    )


@router.post("/hitl/{hitl_id}/approve", response_class=HTMLResponse)
def approve_hitl(hitl_id: str, t: str = Query(...)):
    if not verify_token(t, hitl_id, "approve"):
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM hitl_requests WHERE hitl_id = ?", (hitl_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="HITL request not found")
        if row["status"] not in ("PENDING",):
            return _DONE_PAGE.format(
                title="Already decided",
                desc=f"This request was already {row['status']}.",
            )
        decided_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "UPDATE hitl_requests SET status = 'APPROVED', decided_at = ? WHERE hitl_id = ?",
            (decided_at, hitl_id),
        )
        _write_hitl_receipt(conn, row, decision="APPROVED", decided_at=decided_at)

    if row["callback_url"]:
        _fire_callback(row["callback_url"], hitl_id, "APPROVED")

    return _DONE_PAGE.format(
        title="Approved",
        desc="The agent will proceed. You can close this tab.",
    )


# ── Deny flow ─────────────────────────────────────────────────────────────────

@router.get("/hitl/{hitl_id}/deny", response_class=HTMLResponse)
def deny_confirm_page(hitl_id: str, t: str = Query(...)):
    if not verify_token(t, hitl_id, "deny"):
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    return _CONFIRM_PAGE.format(
        title="Deny this workflow run?",
        desc="Click below to deny. The agent will be blocked.",
        color="#dc2626",
        label="Deny",
    )


@router.post("/hitl/{hitl_id}/deny", response_class=HTMLResponse)
def deny_hitl(hitl_id: str, t: str = Query(...)):
    if not verify_token(t, hitl_id, "deny"):
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM hitl_requests WHERE hitl_id = ?", (hitl_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="HITL request not found")
        if row["status"] not in ("PENDING",):
            return _DONE_PAGE.format(
                title="Already decided",
                desc=f"This request was already {row['status']}.",
            )
        decided_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "UPDATE hitl_requests SET status = 'DENIED', decided_at = ? WHERE hitl_id = ?",
            (decided_at, hitl_id),
        )
        _write_hitl_receipt(conn, row, decision="DENIED", decided_at=decided_at)

    if row["callback_url"]:
        _fire_callback(row["callback_url"], hitl_id, "DENIED")

    return _DONE_PAGE.format(
        title="Denied",
        desc="The agent has been blocked. You can close this tab.",
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

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
        """INSERT OR IGNORE INTO hitl_receipts
           (hitl_id, team_id, workflow, decision, decided_by, decided_at, receipt_json, signature)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
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
