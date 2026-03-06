"""
Thin HTTP client for the Enact Cloud API.

Used by EnactClient when cloud_api_key is set. Not imported by default —
only loaded when the user opts into cloud features.

Why a separate file: keeps cloud dependencies (urllib) out of the
core SDK import path. Users who don't use cloud don't pay the import cost.

ZERO-KNOWLEDGE ENCRYPTION
-------------------------
When encryption_key is provided, receipts are split into:
  - metadata (searchable by cloud): run_id, workflow, decision, timestamp
  - encrypted_payload (unreadable by cloud): user_email, payload, policy_results, actions_taken

The cloud LITERALLY cannot read the payload — it's encrypted with a key
that never leaves the customer's machine. Same model as 1Password, Proton Mail.
"""
import json
import time
import urllib.request
import urllib.error
from enact.models import Receipt
from enact.encryption import encrypt_payload, split_receipt_for_cloud


class CloudClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://enact.cloud",
        encryption_key: bytes | None = None,
        receipt_dir: str = "receipts",
    ):
        """
        Initialize the cloud client.

        Args:
            api_key         — Enact Cloud API key
            base_url        — API endpoint (default: https://enact.cloud)
            encryption_key  — Optional 32-byte key for zero-knowledge encryption.
                              If provided, receipt payloads are encrypted before upload.
                              The cloud CANNOT read encrypted payloads — only metadata.
            receipt_dir     — Directory for local receipt queue (default: "receipts")
        """
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._encryption_key = encryption_key
        self._receipt_dir = receipt_dir

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

    def push_receipt(self, receipt: Receipt, queue_on_failure: bool = True) -> dict:
        """
        Push a signed receipt to cloud storage.

        If encryption_key was provided at init, the receipt is split:
          - metadata (run_id, workflow, decision, timestamp, policy_names) sent in clear
          - payload (user_email, payload, policy_results, actions_taken) encrypted

        The cloud can search metadata but CANNOT read the encrypted payload.

        Args:
            receipt         — Signed Receipt to push
            queue_on_failure — If True, queue locally if cloud is unreachable

        Returns:
            {"status": "ok", "run_id": ...} on success
            {"status": "queued", "run_id": ..., "reason": ...} if queued locally

        Raises:
            ConnectionError if cloud is unreachable and queue_on_failure=False
        """
        receipt_dict = receipt.model_dump()

        if self._encryption_key:
            # Zero-knowledge mode: encrypt the payload
            metadata, payload = split_receipt_for_cloud(receipt_dict)
            encrypted_payload = encrypt_payload(payload, self._encryption_key)
            body = {
                "encrypted": True,
                "metadata": metadata,
                "payload_blob": encrypted_payload,
            }
        else:
            # Legacy mode: send full receipt (for backward compatibility)
            metadata = {
                "run_id": receipt.run_id,
                "workflow": receipt.workflow,
                "decision": receipt.decision,
            }
            body = {
                "run_id": receipt.run_id,
                "workflow": receipt.workflow,
                "decision": receipt.decision,
                "receipt": receipt_dict,
            }

        try:
            return self._post("/receipts", body)
        except Exception as e:
            if not queue_on_failure:
                raise ConnectionError(f"Cloud unreachable: {e}") from e

            # Queue locally for later retry
            from enact.local_queue import enqueue_receipt
            if self._encryption_key:
                enqueue_receipt(
                    self._receipt_dir,
                    metadata=metadata,
                    payload_blob=encrypted_payload,
                )
            else:
                enqueue_receipt(
                    self._receipt_dir,
                    metadata=metadata,
                    full_receipt=receipt_dict,
                )

            return {
                "status": "queued",
                "run_id": receipt.run_id,
                "reason": str(e),
            }

    def drain_queue(self) -> tuple[int, int]:
        """
        Attempt to push all queued receipts to cloud.

        Call this after a successful push to retry any previously queued receipts.

        Returns:
            (success_count, failure_count)
        """
        from enact.local_queue import drain_queue, load_queued_receipt, remove_queued_receipt

        def push_queued(metadata: dict, payload_blob: str | None = None, full_receipt: dict | None = None) -> dict:
            if payload_blob:
                return self._post("/receipts", {
                    "encrypted": True,
                    "metadata": metadata,
                    "payload_blob": payload_blob,
                })
            else:
                return self._post("/receipts", {
                    "run_id": metadata["run_id"],
                    "workflow": metadata["workflow"],
                    "decision": metadata["decision"],
                    "receipt": full_receipt,
                })

        return drain_queue(self._receipt_dir, push_queued)

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
