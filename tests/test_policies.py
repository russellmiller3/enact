"""
Tests for CRM, access, and time policies.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from enact.policies.crm import dont_duplicate_contacts, limit_tasks_per_contact
from enact.policies.access import (
    contractor_cannot_write_pii,
    require_actor_role,
    dont_read_sensitive_tables,
    dont_read_sensitive_paths,
    require_clearance_for_path,
    require_user_role,
)
from enact.policies.time import within_maintenance_window, code_freeze_active
from enact.models import WorkflowContext, ActionResult


def make_context(payload=None, systems=None, user_attributes=None):
    return WorkflowContext(
        workflow="test",
        user_email="agent@test.com",
        payload=payload or {},
        systems=systems or {},
        user_attributes=user_attributes or {},
    )


# ─── CRM Policies ────────────────────────────────────────────────────────────

class TestNoDuplicateContacts:
    def test_passes_when_no_email_in_payload(self):
        ctx = make_context(payload={})
        result = dont_duplicate_contacts(ctx)
        assert result.passed is True
        assert "No email" in result.reason

    def test_passes_when_no_hubspot_system(self):
        ctx = make_context(payload={"email": "jane@acme.com"}, systems={})
        result = dont_duplicate_contacts(ctx)
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
        result = dont_duplicate_contacts(ctx)
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
        result = dont_duplicate_contacts(ctx)
        assert result.passed is True

    def test_policy_name(self):
        ctx = make_context()
        result = dont_duplicate_contacts(ctx)
        assert result.policy == "dont_duplicate_contacts"


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


# ─── ABAC: Sensitive Read Policies ───────────────────────────────────────────

class TestDontReadSensitiveTables:
    def test_passes_for_non_sensitive_table(self):
        ctx = make_context(payload={"table": "orders"})
        result = dont_read_sensitive_tables(["users", "credit_cards"])(ctx)
        assert result.passed is True
        assert result.policy == "dont_read_sensitive_tables"

    def test_blocks_for_sensitive_table(self):
        ctx = make_context(payload={"table": "credit_cards"})
        result = dont_read_sensitive_tables(["users", "credit_cards"])(ctx)
        assert result.passed is False
        assert "credit_cards" in result.reason

    def test_passes_when_no_table_in_payload(self):
        ctx = make_context(payload={})
        result = dont_read_sensitive_tables(["users"])(ctx)
        assert result.passed is True

    def test_blocks_only_exact_match(self):
        # "user_data" should not match "users"
        ctx = make_context(payload={"table": "user_data"})
        result = dont_read_sensitive_tables(["users"])(ctx)
        assert result.passed is True


class TestDontReadSensitivePaths:
    def test_passes_for_non_sensitive_path(self):
        ctx = make_context(payload={"path": "/home/user/docs/report.txt"})
        result = dont_read_sensitive_paths(["/etc", "/root"])(ctx)
        assert result.passed is True

    def test_blocks_for_path_under_sensitive_prefix(self):
        ctx = make_context(payload={"path": "/etc/passwd"})
        result = dont_read_sensitive_paths(["/etc", "/root"])(ctx)
        assert result.passed is False
        assert "/etc/passwd" in result.reason

    def test_blocks_for_nested_path_under_prefix(self):
        ctx = make_context(payload={"path": "/etc/ssh/sshd_config"})
        result = dont_read_sensitive_paths(["/etc"])(ctx)
        assert result.passed is False

    def test_does_not_match_path_with_similar_prefix(self):
        # /etchosts must NOT match /etc prefix
        ctx = make_context(payload={"path": "/etchosts"})
        result = dont_read_sensitive_paths(["/etc"])(ctx)
        assert result.passed is True

    def test_passes_when_no_path_in_payload(self):
        ctx = make_context(payload={})
        result = dont_read_sensitive_paths(["/etc"])(ctx)
        assert result.passed is True

    def test_blocks_exact_prefix_match(self):
        # /etc itself (not just things under it) should also be blocked
        ctx = make_context(payload={"path": "/etc"})
        result = dont_read_sensitive_paths(["/etc"])(ctx)
        assert result.passed is False


class TestRequireClearanceForPath:
    def test_passes_when_sufficient_clearance(self):
        ctx = make_context(
            payload={"path": "/sensitive/data.csv"},
            user_attributes={"clearance_level": 3},
        )
        result = require_clearance_for_path(["/sensitive"], 2)(ctx)
        assert result.passed is True

    def test_blocks_when_insufficient_clearance(self):
        ctx = make_context(
            payload={"path": "/sensitive/data.csv"},
            user_attributes={"clearance_level": 1},
        )
        result = require_clearance_for_path(["/sensitive"], 2)(ctx)
        assert result.passed is False
        assert "clearance" in result.reason.lower()
        assert "1" in result.reason
        assert "2" in result.reason

    def test_passes_for_non_sensitive_path_regardless_of_clearance(self):
        ctx = make_context(
            payload={"path": "/public/readme.txt"},
            user_attributes={"clearance_level": 0},
        )
        result = require_clearance_for_path(["/sensitive"], 2)(ctx)
        assert result.passed is True

    def test_blocks_when_clearance_missing_from_attributes(self):
        ctx = make_context(
            payload={"path": "/sensitive/data.csv"},
            user_attributes={},
        )
        result = require_clearance_for_path(["/sensitive"], 1)(ctx)
        assert result.passed is False
        assert "0" in result.reason  # defaults to 0

    def test_passes_when_no_path_in_payload(self):
        ctx = make_context(payload={}, user_attributes={})
        result = require_clearance_for_path(["/sensitive"], 5)(ctx)
        assert result.passed is True

    def test_passes_at_exact_clearance_level(self):
        ctx = make_context(
            payload={"path": "/sensitive/data.csv"},
            user_attributes={"clearance_level": 2},
        )
        result = require_clearance_for_path(["/sensitive"], 2)(ctx)
        assert result.passed is True


class TestRequireUserRole:
    def test_passes_for_allowed_role(self):
        ctx = make_context(user_attributes={"role": "admin"})
        result = require_user_role("admin", "engineer")(ctx)
        assert result.passed is True
        assert result.policy == "require_user_role"

    def test_passes_for_second_allowed_role(self):
        ctx = make_context(user_attributes={"role": "engineer"})
        result = require_user_role("admin", "engineer")(ctx)
        assert result.passed is True

    def test_blocks_for_disallowed_role(self):
        ctx = make_context(user_attributes={"role": "contractor"})
        result = require_user_role("admin", "engineer")(ctx)
        assert result.passed is False
        assert "contractor" in result.reason

    def test_blocks_when_role_missing(self):
        ctx = make_context(user_attributes={})
        result = require_user_role("admin")(ctx)
        assert result.passed is False
        assert "unknown" in result.reason

    def test_blocks_when_user_attributes_empty(self):
        ctx = make_context()
        result = require_user_role("admin")(ctx)
        assert result.passed is False


# ─── Time: Code Freeze ────────────────────────────────────────────────────────

class TestCodeFreezeActive:
    def test_passes_when_freeze_not_set(self, monkeypatch):
        monkeypatch.delenv("ENACT_FREEZE", raising=False)
        ctx = make_context()
        result = code_freeze_active(ctx)
        assert result.passed is True
        assert result.policy == "code_freeze_active"

    def test_blocks_when_freeze_is_1(self, monkeypatch):
        monkeypatch.setenv("ENACT_FREEZE", "1")
        ctx = make_context()
        result = code_freeze_active(ctx)
        assert result.passed is False
        assert "freeze" in result.reason.lower()

    def test_blocks_when_freeze_is_true(self, monkeypatch):
        monkeypatch.setenv("ENACT_FREEZE", "true")
        ctx = make_context()
        result = code_freeze_active(ctx)
        assert result.passed is False

    def test_blocks_when_freeze_is_yes(self, monkeypatch):
        monkeypatch.setenv("ENACT_FREEZE", "yes")
        ctx = make_context()
        result = code_freeze_active(ctx)
        assert result.passed is False

    def test_blocks_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("ENACT_FREEZE", "TRUE")
        ctx = make_context()
        result = code_freeze_active(ctx)
        assert result.passed is False

    def test_passes_when_freeze_is_0(self, monkeypatch):
        monkeypatch.setenv("ENACT_FREEZE", "0")
        ctx = make_context()
        result = code_freeze_active(ctx)
        assert result.passed is True

    def test_passes_when_freeze_is_empty_string(self, monkeypatch):
        monkeypatch.setenv("ENACT_FREEZE", "")
        ctx = make_context()
        result = code_freeze_active(ctx)
        assert result.passed is True
