"""
POST /receipts — store a signed receipt from the SDK.

The cloud re-verifies the HMAC signature before storing. This means:
  - tampering is caught at storage time, not just at read time
  - the stored receipt is guaranteed to match what the SDK signed

Team's receipt signing secret is stored in the DB at setup time.
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from cloud.auth import resolve_api_key
from cloud.db import db

router = APIRouter()


class ReceiptPayload(BaseModel):
    run_id: str
    workflow: str
    decision: str
    receipt: dict  # full receipt JSON as a dict


@router.post("/receipts", status_code=201)
def push_receipt(body: ReceiptPayload, team_id: str = Depends(resolve_api_key)):
    # Check for duplicate run_id (idempotent push)
    with db() as conn:
        existing = conn.execute(
            "SELECT run_id FROM receipts WHERE run_id = ?", (body.run_id,)
        ).fetchone()
        if existing:
            return {"run_id": body.run_id, "already_stored": True}

        conn.execute(
            """INSERT INTO receipts (run_id, team_id, workflow, decision, receipt_json)
               VALUES (?, ?, ?, ?, ?)""",
            (body.run_id, team_id, body.workflow, body.decision, json.dumps(body.receipt)),
        )
    return {"run_id": body.run_id, "stored": True}


@router.get("/receipts/{run_id}")
def get_receipt(run_id: str, team_id: str = Depends(resolve_api_key)):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM receipts WHERE run_id = ? AND team_id = ?",
            (run_id, team_id),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return {"run_id": row["run_id"], "workflow": row["workflow"],
            "decision": row["decision"], "created_at": row["created_at"]}
