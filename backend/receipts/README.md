# Access Decision Receipts

This folder stores human-readable receipts for every access decision.

## Format

Each receipt is named: `REQ-{id}_{date}.txt`

Example: `REQ-82471_2026-02-16.txt`

## Contents

Each receipt answers:
- **WHO** requested access (email)
- **WHAT** dataset they want (and access level)
- **REASON** for the request (justification)
- **DECISION** (APPROVED / ESCALATED / DENIED)
- **WHY** that decision was made (which ABAC checks passed/failed)

Technical log is at the bottom for debugging.

## Demo Instructions

During the demo, Russell can:
1. Show this folder to prove receipts are actually saved
2. Open a receipt in VS Code to show the human-readable format
3. Point out that these are permanent audit trails, not just UI

## Sample Receipt

```
DECISION: APPROVED

WHO: analyst@visa.com
WHAT: fraud_detection_models (READ access)
REASON: Analyze Q1 false positive rates for risk analysis project

WHY APPROVED:
  ✓ Role Authorization: Senior Data Analyst
  ✓ Clearance Level: Level 3 (verified)
  ✓ Access Level Restriction: Requesting READ access
  ✓ PII Restriction: N/A
  ✓ Training Requirements: Completed 2026-01-15
  ✓ Employment Type: FTE (verified via HR system)
  ✓ MNPI Blackout: N/A - Dataset is Internal
  ✓ Time-Limited Access: Expiry will be set to +90 days

ACCESS GRANTED UNTIL: 2026-05-17

────────────────────────────────────────────
Technical Log:
  15:30:00 | IntakeAgent extracted request (782 tokens)
  15:30:01 | ABAC checked 8 policies (8 passed)
  15:30:01 | Access token generated (visa-token-91847)
  15:30:02 | 4 notifications sent
```
