"""
POST /receipts — store a signed receipt from the SDK.

Supports two modes:
  1. Legacy: full receipt JSON (backward compatible)
  2. Zero-knowledge: encrypted payload + searchable metadata

ZERO-KNOWLEDGE ENCRYPTION
-------------------------
When the SDK provides encryption_key, receipts are split:
  - metadata (searchable): run_id, workflow, decision, timestamp, policy_names
  - payload_blob (encrypted): user_email, payload, policy_results, actions_taken

The cloud CANNOT read the encrypted payload — it's AES-256-GCM encrypted
with a key that never leaves the customer's machine.

APPEND-ONLY STORAGE
-------------------
Receipts are append-only. Once stored, they cannot be modified or deleted.
This ensures audit trail integrity for compliance (SOC 2, SOX, EU AI Act).
"""
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from cloud.auth import resolve_api_key
from cloud.db import db

router = APIRouter()


class ReceiptPayloadLegacy(BaseModel):
    """Legacy format: full receipt JSON."""
    run_id: str
    workflow: str
    decision: str
    receipt: dict  # full receipt JSON as a dict


class ReceiptPayloadEncrypted(BaseModel):
    """Zero-knowledge format: encrypted payload + searchable metadata."""
    encrypted: bool = True
    metadata: dict  # run_id, workflow, decision, timestamp, policy_names
    payload_blob: str  # base64-encoded AES-256-GCM encrypted payload


class ReceiptPayload(BaseModel):
    """Accepts either legacy or encrypted format."""
    # Legacy fields (optional)
    run_id: Optional[str] = None
    workflow: Optional[str] = None
    decision: Optional[str] = None
    receipt: Optional[dict] = None
    # Encrypted fields (optional)
    encrypted: bool = False
    metadata: Optional[dict] = None
    payload_blob: Optional[str] = None


@router.post("/receipts", status_code=201)
def push_receipt(body: ReceiptPayload, team_id: str = Depends(resolve_api_key)):
    """
    Store a receipt. Supports both legacy and zero-knowledge encrypted formats.

    Append-only: once stored, receipts cannot be modified or deleted.
    """
    # Determine format
    if body.encrypted and body.metadata and body.payload_blob:
        # Zero-knowledge encrypted format
        run_id = body.metadata.get("run_id")
        workflow = body.metadata.get("workflow")
        decision = body.metadata.get("decision")
        timestamp = body.metadata.get("timestamp")
        policy_names = body.metadata.get("policy_names", [])
        
        if not run_id:
            raise HTTPException(status_code=400, detail="metadata.run_id is required")
    else:
        # Legacy format
        run_id = body.run_id
        workflow = body.workflow
        decision = body.decision
        timestamp = body.receipt.get("timestamp") if body.receipt else None
        policy_names = [pr.get("policy") for pr in body.receipt.get("policy_results", [])] if body.receipt else []
        
        if not run_id:
            raise HTTPException(status_code=400, detail="run_id is required")

    # Check for duplicate run_id (idempotent push)
    with db() as conn:
        existing = conn.execute(
            "SELECT run_id FROM receipts WHERE run_id = ?", (run_id,)
        ).fetchone()
        if existing:
            return {"run_id": run_id, "already_stored": True}

        # Store receipt (append-only)
        if body.encrypted:
            conn.execute(
                """INSERT INTO receipts
                   (run_id, team_id, workflow, decision, timestamp, policy_names, metadata_json, payload_blob, encrypted)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (
                    run_id,
                    team_id,
                    workflow,
                    decision,
                    timestamp,
                    json.dumps(policy_names),
                    json.dumps(body.metadata),
                    body.payload_blob,
                ),
            )
        else:
            conn.execute(
                """INSERT INTO receipts
                   (run_id, team_id, workflow, decision, timestamp, policy_names, receipt_json, encrypted)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                (
                    run_id,
                    team_id,
                    workflow,
                    decision,
                    timestamp,
                    json.dumps(policy_names),
                    json.dumps(body.receipt),
                ),
            )
    return {"run_id": run_id, "stored": True}


@router.get("/receipts/{run_id}")
def get_receipt(run_id: str, team_id: str = Depends(resolve_api_key)):
    """
    Get receipt metadata by run_id.

    For encrypted receipts, returns metadata only (payload_blob is not returned).
    For legacy receipts, returns the full receipt.
    """
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM receipts WHERE run_id = ? AND team_id = ?",
            (run_id, team_id),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    response = {
        "run_id": row["run_id"],
        "workflow": row["workflow"],
        "decision": row["decision"],
        "timestamp": row["timestamp"],
        "created_at": row["created_at"],
        "encrypted": bool(row["encrypted"]),
        "user_email": None,
        "systems": [],
    }

    # For legacy receipts, include the full receipt + extract metadata
    if not row["encrypted"] and row["receipt_json"]:
        rj = json.loads(row["receipt_json"])
        response["receipt"] = rj
        response["user_email"] = rj.get("user_email")
        response["systems"] = list(set(
            a.get("system", "")
            for a in rj.get("actions_taken", [])
            if a.get("system")
        ))

    return response


@router.get("/receipts")
def list_receipts(
    team_id: str = Depends(resolve_api_key),
    workflow: Optional[str] = None,
    decision: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    List receipts for a team. Supports filtering by workflow and decision.

    Returns metadata only (encrypted payloads are never returned).
    """
    query = "SELECT * FROM receipts WHERE team_id = ?"
    params = [team_id]
    
    if workflow:
        query += " AND workflow = ?"
        params.append(workflow)
    if decision:
        query += " AND decision = ?"
        params.append(decision)
    
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    with db() as conn:
        rows = conn.execute(query, params).fetchall()
    
    receipts = []
    for row in rows:
        item = {
            "run_id": row["run_id"],
            "workflow": row["workflow"],
            "decision": row["decision"],
            "timestamp": row["timestamp"],
            "created_at": row["created_at"],
            "encrypted": bool(row["encrypted"]),
            "user_email": None,
            "systems": [],
        }
        # Extract user_email + systems from receipt JSON (legacy only)
        if not row["encrypted"] and row["receipt_json"]:
            try:
                rj = json.loads(row["receipt_json"])
                item["user_email"] = rj.get("user_email")
                item["systems"] = list(set(
                    a.get("system", "")
                    for a in rj.get("actions_taken", [])
                    if a.get("system")
                ))
            except (json.JSONDecodeError, TypeError):
                pass
        receipts.append(item)

    # Count total matching rows (for pagination)
    count_query = "SELECT COUNT(*) FROM receipts WHERE team_id = ?"
    count_params: list = [team_id]
    if workflow:
        count_query += " AND workflow = ?"
        count_params.append(workflow)
    if decision:
        count_query += " AND decision = ?"
        count_params.append(decision)

    with db() as conn:
        total = conn.execute(count_query, count_params).fetchone()[0]

    return {
        "receipts": receipts,
        "count": total,
    }
