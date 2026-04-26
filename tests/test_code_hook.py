"""Tests for the Enact Code Claude Code hook."""
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from enact.cli.code_hook import parse_bash_command


# -- parser tests --

class TestParseBashCommand:
    def test_plain_command_populates_command_and_args(self):
        p = parse_bash_command("ls -la /tmp")
        assert p["command"] == "ls -la /tmp"
        assert p["args"] == ["ls", "-la", "/tmp"]
        assert "table" not in p
        assert "where" not in p

    def test_psql_delete_extracts_table_no_where(self):
        cmd = 'psql $DB -c "DELETE FROM customers"'
        p = parse_bash_command(cmd)
        assert p["table"] == "customers"
        assert "where" not in p
        assert "DELETE FROM" in p["sql"]

    def test_psql_delete_extracts_where_clause(self):
        cmd = "psql -c \"DELETE FROM users WHERE id = 1\""
        p = parse_bash_command(cmd)
        assert p["table"] == "users"
        assert "where" in p
        assert "id = 1" in p["where"]["clause"]

    def test_drop_table_extracts_table_and_sql(self):
        cmd = 'psql -c "DROP TABLE customers"'
        p = parse_bash_command(cmd)
        assert p["table"] == "customers"
        assert "DROP TABLE" in p["sql"]

    def test_force_push_args_visible(self):
        p = parse_bash_command("git push --force origin main")
        assert "--force" in p["args"]
