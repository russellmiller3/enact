"""Run this to create a test HITL request and get click-able URLs."""
import sys
import os
import urllib.request
import json

os.environ.setdefault("CLOUD_SECRET", "changeme")

try:
    url = "http://localhost:8000/hitl/request"
    payload = {
        "workflow": "delete_customer_data",
        "payload": {"customer_id": "cust_123", "action": "permanent_delete"},
        "notify_email": "russell@example.com",
        "expires_in_seconds": 3600,
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Content-Type": "application/json",
            "X-Enact-Api-Key": "enact_live_devkey_russell",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    hitl_id = result["hitl_id"]
    sys.stderr.write(f"hitl_id: {hitl_id}\n")

    from cloud.token import make_token
    approve_token = make_token(hitl_id, "approve")
    deny_token = make_token(hitl_id, "deny")

    base = "http://localhost:8000"
    sys.stderr.write(f"\nAPPROVE PAGE:\n{base}/hitl/{hitl_id}/approve?t={approve_token}\n")
    sys.stderr.write(f"\nDENY PAGE:\n{base}/hitl/{hitl_id}/deny?t={deny_token}\n")

except Exception as e:
    sys.stderr.write(f"ERROR: {e}\n")
    sys.exit(1)
