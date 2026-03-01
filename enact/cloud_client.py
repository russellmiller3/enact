"""
Thin HTTP client for the Enact Cloud API.

Used by EnactClient when cloud_api_key is set. Not imported by default —
only loaded when the user opts into cloud features.

Why a separate file: keeps cloud dependencies (urllib) out of the
core SDK import path. Users who don't use cloud don't pay the import cost.
"""
import json
import time
import urllib.request
import urllib.error
from enact.models import Receipt


class CloudClient:
    def __init__(self, api_key: str, base_url: str = "https://enact.cloud"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def _headers(self) -> dict:
        return {
            "X-Enact-Api-Key": self._api_key,
            "Content-Type": "application/json",
        }

    def _post(self, path: str, body: dict) -> dict:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{self._base_url}{path}",
            data=data,
            headers=self._headers(),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    def _get(self, path: str) -> dict:
        req = urllib.request.Request(
            f"{self._base_url}{path}",
            headers=self._headers(),
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())

    def push_receipt(self, receipt: Receipt) -> dict:
        """Push a signed receipt to cloud storage."""
        return self._post("/receipts", {
            "run_id": receipt.run_id,
            "workflow": receipt.workflow,
            "decision": receipt.decision,
            "receipt": receipt.model_dump(),
        })

    def request_hitl(
        self,
        workflow: str,
        payload: dict,
        notify_email: str,
        expires_in_seconds: int = 3600,
    ) -> dict:
        """Create a HITL request. Returns {hitl_id, status, expires_at}."""
        return self._post("/hitl/request", {
            "workflow": workflow,
            "payload": payload,
            "notify_email": notify_email,
            "expires_in_seconds": expires_in_seconds,
        })

    def get_hitl_status(self, hitl_id: str) -> dict:
        """Poll for HITL status. Returns {hitl_id, status, ...}."""
        return self._get(f"/hitl/{hitl_id}")

    def poll_until_decided(
        self,
        hitl_id: str,
        poll_interval_seconds: int = 5,
        timeout_seconds: int = 3600,
    ) -> str:
        """
        Block until HITL is APPROVED, DENIED, or EXPIRED.
        Returns the final status string.
        """
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            result = self.get_hitl_status(hitl_id)
            status = result["status"]
            if status != "PENDING":
                return status
            time.sleep(poll_interval_seconds)
        return "EXPIRED"
