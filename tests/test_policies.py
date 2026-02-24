"""
Tests for CRM, access, and time policies.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from enact.policies.crm import no_duplicate_contacts, limit_tasks_per_contact
from enact.policies.access import contractor_cannot_write_pii, require_actor_role
from enact.policies.time import within_maintenance_window
from enact.models import WorkflowContext, ActionResult


def make_context(payload=None, systems=None):
    return WorkflowContext(
        workflow="test",
        actor_email="agent@test.com",
        payload=payload or {},
        systems=systems or {},
    )


# ─── CRM Policies ────────────────────────────────────────────────────────────

class TestNoDuplicateContacts:
    def test_passes_when_no_email_in_payload(self):
        ctx = make_context(payload={})
        result = no_duplicate_contacts(ctx)
        assert result.passed is True
        assert "No email" in result.reason

    def test_passes_when_no_hubspot_system(self):
        ctx = make_context(payload={"email": "jane@acme.com"}, systems={})
        result = no_duplicate_contacts(ctx)
        assert result.passed is True
        assert "No HubSpot" in result.reason

    def test_blocks_when_contact_exists(self):
        mock_hs = MagicMock()
        mock_hs.get_contact.return_value = ActionResult(
            action="get_contact",
            system="hubspot",
            success=True,
            output={"found": True, "id": "hs-123"},
        )
        ctx = make_context(
            payload={"email": "jane@acme.com"},
            systems={"hubspot": mock_hs},
        )
        result = no_duplicate_contacts(ctx)
        assert result.passed is False
        assert "already exists" in result.reason

    def test_passes_when_contact_not_found(self):
        mock_hs = MagicMock()
        mock_hs.get_contact.return_value = ActionResult(
            action="get_contact",
            system="hubspot",
            success=True,
            output={"found": False},
        )
        ctx = make_context(
            payload={"email": "new@acme.com"},
            systems={"hubspot": mock_hs},
        )
        result = no_duplicate_contacts(ctx)
        assert result.passed is True

    def test_policy_name(self):
        ctx = make_context()
        result = no_duplicate_contacts(ctx)
        assert result.policy == "no_duplicate_contacts"


class TestLimitTasksPerContact:
    def test_blocks_when_over_limit(self):
        policy = limit_tasks_per_contact(max_tasks=3, window_days=7)
        ctx = make_context(payload={"recent_task_count": 3})
        result = policy(ctx)
        assert result.passed is False
        assert "3" in result.reason

    def test_passes_when_under_limit(self):
        policy = limit_tasks_per_contact(max_tasks=3, window_days=7)
        ctx = make_context(payload={"recent_task_count": 2})
        result = policy(ctx)
        assert result.passed is True

    def test_zero_tasks_always_passes(self):
        policy = limit_tasks_per_contact(max_tasks=3)
        ctx = make_context(payload={})  # recent_task_count defaults to 0
        result = policy(ctx)
        assert result.passed is True

    def test_policy_name(self):
        policy = limit_tasks_per_contact()
        ctx = make_context()
        result = policy(ctx)
        assert result.policy == "limit_tasks_per_contact"


# ─── Access Policies ─────────────────────────────────────────────────────────

class TestContractorCannotWritePii:
    def test_blocks_contractor_writing_pii(self):
        ctx = make_context(payload={
            "actor_role": "contractor",
            "pii_fields": ["ssn", "dob"],
            "data": {"ssn": "123-45-6789", "name": "Jane"},
        })
        result = contractor_cannot_write_pii(ctx)
        assert result.passed is False
        assert "PII" in result.reason

    def test_allows_employee_writing_pii(self):
        ctx = make_context(payload={
            "actor_role": "employee",
            "pii_fields": ["ssn"],
            "data": {"ssn": "123-45-6789"},
        })
        result = contractor_cannot_write_pii(ctx)
        assert result.passed is True

    def test_allows_contractor_writing_non_pii(self):
        ctx = make_context(payload={
            "actor_role": "contractor",
            "pii_fields": ["ssn"],
            "data": {"name": "Jane", "company": "Acme"},  # no pii fields
        })
        result = contractor_cannot_write_pii(ctx)
        assert result.passed is True

    def test_allows_no_pii_fields_defined(self):
        ctx = make_context(payload={
            "actor_role": "contractor",
            "data": {"email": "jane@acme.com"},
        })
        result = contractor_cannot_write_pii(ctx)
        assert result.passed is True  # no pii_fields defined → no violation

    def test_policy_name(self):
        ctx = make_context()
        result = contractor_cannot_write_pii(ctx)
        assert result.policy == "contractor_cannot_write_pii"


class TestRequireActorRole:
    def test_blocks_unauthorized_role(self):
        policy = require_actor_role(allowed_roles=["admin", "engineer"])
        ctx = make_context(payload={"actor_role": "viewer"})
        result = policy(ctx)
        assert result.passed is False
        assert "viewer" in result.reason

    def test_allows_authorized_role(self):
        policy = require_actor_role(allowed_roles=["admin", "engineer"])
        ctx = make_context(payload={"actor_role": "engineer"})
        result = policy(ctx)
        assert result.passed is True

    def test_blocks_unknown_role(self):
        policy = require_actor_role(allowed_roles=["admin"])
        ctx = make_context(payload={})  # actor_role defaults to "unknown"
        result = policy(ctx)
        assert result.passed is False
        assert "unknown" in result.reason

    def test_policy_name(self):
        policy = require_actor_role(allowed_roles=["admin"])
        ctx = make_context(payload={"actor_role": "admin"})
        result = policy(ctx)
        assert result.policy == "require_actor_role"


# ─── Time Policies ────────────────────────────────────────────────────────────

class TestWithinMaintenanceWindow:
    def _make_policy_with_mocked_hour(self, current_hour, start, end):
        """Helper: create policy and mock datetime to return a specific UTC hour."""
        policy = within_maintenance_window(start, end)
        mock_now = MagicMock()
        mock_now.hour = current_hour
        return policy, mock_now

    def test_inside_window(self):
        policy = within_maintenance_window(start_hour_utc=2, end_hour_utc=6)
        with patch("enact.policies.time.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 4
            ctx = make_context()
            result = policy(ctx)
        assert result.passed is True
        assert "inside" in result.reason

    def test_outside_window(self):
        policy = within_maintenance_window(start_hour_utc=2, end_hour_utc=6)
        with patch("enact.policies.time.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 10
            ctx = make_context()
            result = policy(ctx)
        assert result.passed is False
        assert "outside" in result.reason

    def test_at_start_of_window(self):
        policy = within_maintenance_window(start_hour_utc=2, end_hour_utc=6)
        with patch("enact.policies.time.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 2  # at start — inside
            ctx = make_context()
            result = policy(ctx)
        assert result.passed is True

    def test_at_end_of_window_is_outside(self):
        policy = within_maintenance_window(start_hour_utc=2, end_hour_utc=6)
        with patch("enact.policies.time.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 6  # end is exclusive
            ctx = make_context()
            result = policy(ctx)
        assert result.passed is False

    def test_midnight_crossing_window_inside(self):
        # Window 22:00-06:00 (crosses midnight)
        policy = within_maintenance_window(start_hour_utc=22, end_hour_utc=6)
        with patch("enact.policies.time.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 23  # inside (after 22)
            ctx = make_context()
            result = policy(ctx)
        assert result.passed is True

    def test_midnight_crossing_window_inside_early_morning(self):
        # Window 22:00-06:00 crossing midnight
        policy = within_maintenance_window(start_hour_utc=22, end_hour_utc=6)
        with patch("enact.policies.time.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 3  # inside (before 06)
            ctx = make_context()
            result = policy(ctx)
        assert result.passed is True

    def test_midnight_crossing_window_outside(self):
        # Window 22:00-06:00 crossing midnight
        policy = within_maintenance_window(start_hour_utc=22, end_hour_utc=6)
        with patch("enact.policies.time.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 14  # outside
            ctx = make_context()
            result = policy(ctx)
        assert result.passed is False

    def test_policy_name(self):
        policy = within_maintenance_window(start_hour_utc=0, end_hour_utc=24)
        with patch("enact.policies.time.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 12
            ctx = make_context()
            result = policy(ctx)
        assert result.policy == "within_maintenance_window"
