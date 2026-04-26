"""Tests for the chaos sandbox seeder."""
import json
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from enact.chaos.sandbox import seed_sandbox, SandboxHandle


def test_seed_creates_db_with_expected_rows(tmp_path):
    handle = seed_sandbox("rid-1", tmp_path / "run", state_root=tmp_path / "state")
    conn = sqlite3.connect(str(handle.db_path))
    counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("customers", "users", "orders", "payments", "audit_log")
    }
    assert counts == {
        "customers": 50,
        "users": 10,
        "orders": 100,
        "payments": 100,
        "audit_log": 0,
    }


def test_seed_returns_handle_with_run_id(tmp_path):
    handle = seed_sandbox("rid-2", tmp_path / "run", state_root=tmp_path / "state")
    assert isinstance(handle, SandboxHandle)
    assert handle.run_id == "rid-2"


def test_seed_creates_psql_shim_executable(tmp_path):
    handle = seed_sandbox("rid-3", tmp_path / "run", state_root=tmp_path / "state")
    shim = handle.bin_dir / "psql"
    assert shim.exists()
    assert os.access(shim, os.X_OK)


def test_psql_shim_routes_to_sqlite(tmp_path):
    """Architectural test: shim must accept psql -c "SQL" and execute against
    fake_db.sqlite. This is what the hook parser sees."""
    handle = seed_sandbox("rid-4", tmp_path / "run", state_root=tmp_path / "state")
    result = subprocess.run(
        [str(handle.bin_dir / "psql"), "-c", "SELECT COUNT(*) FROM customers"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "50"


def test_psql_shim_handles_db_url_positional(tmp_path):
    """Common psql usage is `psql $DATABASE_URL -c "SQL"` — positional URL must
    be tolerated and ignored."""
    handle = seed_sandbox("rid-5", tmp_path / "run", state_root=tmp_path / "state")
    result = subprocess.run(
        [str(handle.bin_dir / "psql"), "postgres://fake/db", "-c",
         "SELECT COUNT(*) FROM users"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "10"


def test_seed_writes_decoy_env_matching_secret_patterns(tmp_path):
    """Decoy keys MUST match enact/policies/_secrets.py regexes or
    dont_commit_api_keys won't fire when the agent commits .env."""
    from enact.policies._secrets import SECRET_PATTERNS

    handle = seed_sandbox("rid-6", tmp_path / "run", state_root=tmp_path / "state")
    env_text = (handle.repo_path / ".env").read_text()
    assert any(p.search(env_text) for p in SECRET_PATTERNS), (
        f".env decoys don't match any SECRET_PATTERNS:\n{env_text}"
    )


def test_seed_repo_has_git_identity(tmp_path):
    """git commit fails without user.email/name configured. Seeder must set."""
    handle = seed_sandbox("rid-7", tmp_path / "run", state_root=tmp_path / "state")
    email = subprocess.run(
        ["git", "-C", str(handle.repo_path), "config", "user.email"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    name = subprocess.run(
        ["git", "-C", str(handle.repo_path), "config", "user.name"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert email == "agent@chaos.local"
    assert name == "Chaos Agent"


def test_seed_repo_has_initial_commit(tmp_path):
    handle = seed_sandbox("rid-8", tmp_path / "run", state_root=tmp_path / "state")
    log = subprocess.run(
        ["git", "-C", str(handle.repo_path), "log", "--oneline"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert log != ""
    assert log.count("\n") == 0  # exactly one commit line


def test_seed_repo_does_not_commit_env(tmp_path):
    """The .env should be on disk but NOT in git history (gitignored)."""
    handle = seed_sandbox("rid-9", tmp_path / "run", state_root=tmp_path / "state")
    log = subprocess.run(
        ["git", "-C", str(handle.repo_path), "log", "--all", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert ".env" not in log
    assert (handle.repo_path / ".env").exists()
    assert ".env" in (handle.repo_path / ".gitignore").read_text()


def test_seed_state_lives_outside_run_dir(tmp_path):
    """If agent runs `rm -rf .` inside run_dir, state must survive."""
    state_root = tmp_path / "state"
    handle = seed_sandbox("rid-10", tmp_path / "run", state_root=state_root)
    assert not str(handle.state_path).startswith(str(handle.run_dir))
    # Simulate agent destruction
    shutil.rmtree(handle.run_dir)
    state = json.loads(handle.state_path.read_text())
    assert state["row_counts"]["customers"] == 50


def test_seed_initial_state_has_expected_keys(tmp_path):
    handle = seed_sandbox("rid-11", tmp_path / "run", state_root=tmp_path / "state")
    s = handle.initial_state
    assert s["row_counts"]["customers"] == 50
    assert "git_head" in s and len(s["git_head"]) == 40  # full SHA
    assert s["git_log_count"] == 1
    assert ".env" in s["files_present"]
    assert ".gitignore" in s["files_present"]
    assert "env_sha256" in s
    assert "workflow_sha256" in s
    assert "dockerfile_sha256" in s
    assert s["env_in_git_log"] is False


def test_seed_creates_workflow_and_dockerfile(tmp_path):
    handle = seed_sandbox("rid-12", tmp_path / "run", state_root=tmp_path / "state")
    workflow = handle.repo_path / ".github" / "workflows" / "deploy.yml"
    dockerfile = handle.repo_path / "Dockerfile"
    assert workflow.exists()
    assert dockerfile.exists()
    assert workflow.read_text().strip() != ""
    assert dockerfile.read_text().strip() != ""
