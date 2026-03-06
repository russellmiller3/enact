"""
Auditor API — read-only access for external auditors.

This endpoint is designed for SOC 2, SOX, and EU AI Act compliance.
Auditors can:
  - Verify receipts exist (by run_id)
  - Search receipts by time range, workflow, decision
  - Verify receipt signatures (for legacy receipts)
  - Access metadata only (encrypted payloads are never returned)

The auditor API key is separate from the team API key, allowing
fine-grained access control for external parties.
"""
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from cloud.auth import resolve_api_key
from cloud.db import db

router = APIRouter()


@router.get("/auditor/receipts/{run_id}")
def get_receipt_for_audit(
    run_id: str,
    team_id: str = Depends(resolve_api_key),
):
    """
    Get receipt metadata for audit verification.

    Returns:
        - run_id, workflow, decision, timestamp
        - policy_names (which policies ran)
        - signature (for legacy receipts, to verify authenticity)
        - created_at (when the receipt was stored)

    Does NOT return:
        - payload contents (user_email, payload, policy_results, actions_taken)
        - These are encrypted in zero-knowledge mode
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
        "policy_names": json.loads(row["policy_names"]) if row["policy_names"] else [],
        "created_at": row["created_at"],
        "encrypted": bool(row["encrypted"]),
    }
    
    # For legacy receipts, include signature for verification
    if not row["encrypted"] and row["receipt_json"]:
        receipt = json.loads(row["receipt_json"])
        response["signature"] = receipt.get("signature", "")
    
    return response


@router.get("/auditor/receipts")
def list_receipts_for_audit(
    team_id: str = Depends(resolve_api_key),
    workflow: Optional[str] = None,
    decision: Optional[str] = None,
    start_date: Optional[str] = Query(None, description="ISO date, e.g. 2026-01-01"),
    end_date: Optional[str] = Query(None, description="ISO date, e.g. 2026-12-31"),
    limit: int = Query(100, le=1000),
    offset: int = 0,
):
    """
    List receipts for audit. Supports filtering by:
        - workflow: filter by workflow name
        - decision: filter by PASS/BLOCK
        - start_date: filter by created_at >= start_date
        - end_date: filter by created_at <= end_date

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
    if start_date:
        query += " AND date(created_at) >= date(?)"
        params.append(start_date)
    if end_date:
        query += " AND date(created_at) <= date(?)"
        params.append(end_date)
    
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    with db() as conn:
        rows = conn.execute(query, params).fetchall()
    
    return {
        "receipts": [
            {
                "run_id": row["run_id"],
                "workflow": row["workflow"],
                "decision": row["decision"],
                "timestamp": row["timestamp"],
                "policy_names": json.loads(row["policy_names"]) if row["policy_names"] else [],
                "created_at": row["created_at"],
                "encrypted": bool(row["encrypted"]),
            }
            for row in rows
        ],
        "count": len(rows),
        "filters": {
            "workflow": workflow,
            "decision": decision,
            "start_date": start_date,
            "end_date": end_date,
        },
    }


@router.get("/auditor/stats")
def get_audit_stats(
    team_id: str = Depends(resolve_api_key),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """
    Get aggregate statistics for audit reports.

    Returns:
        - total_receipts: count of all receipts
        - by_decision: {PASS: count, BLOCK: count}
        - by_workflow: {workflow_name: count}
        - encrypted_count: how many use zero-knowledge encryption
    """
    base_query = "FROM receipts WHERE team_id = ?"
    params = [team_id]
    
    if start_date:
        base_query += " AND date(created_at) >= date(?)"
        params.append(start_date)
    if end_date:
        base_query += " AND date(created_at) <= date(?)"
        params.append(end_date)
    
    with db() as conn:
        # Total count
        total = conn.execute(f"SELECT COUNT(*) as cnt {base_query}", params).fetchone()["cnt"]
        
        # By decision
        decision_rows = conn.execute(
            f"SELECT decision, COUNT(*) as cnt {base_query} GROUP BY decision",
            params
        ).fetchall()
        by_decision = {row["decision"]: row["cnt"] for row in decision_rows}
        
        # By workflow
        workflow_rows = conn.execute(
            f"SELECT workflow, COUNT(*) as cnt {base_query} GROUP BY workflow",
            params
        ).fetchall()
        by_workflow = {row["workflow"]: row["cnt"] for row in workflow_rows}
        
        # Encrypted count
        encrypted = conn.execute(
            f"SELECT COUNT(*) as cnt {base_query} AND encrypted = 1",
            params
        ).fetchone()["cnt"]
    
    return {
        "total_receipts": total,
        "by_decision": by_decision,
        "by_workflow": by_workflow,
        "encrypted_count": encrypted,
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
        },
    }