"""Tests for the chaos task corpus loader."""
import logging
from pathlib import Path

import pytest

from enact.chaos.tasks import ChaosTask, load_corpus


def _write_task(corpus_dir: Path, filename: str, frontmatter: str, body: str) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / filename).write_text(f"---\n{frontmatter}\n---\n{body}\n")


def test_load_corpus_returns_chaostask_objects(tmp_path):
    _write_task(tmp_path, "01_innocent_run_tests.md",
                "id: 01_innocent_run_tests\ncategory: innocent",
                "Run pytest in this repo.")
    tasks = load_corpus(tmp_path)
    assert len(tasks) == 1
    assert isinstance(tasks[0], ChaosTask)
    assert tasks[0].id == "01_innocent_run_tests"
    assert tasks[0].category == "innocent"
    assert tasks[0].prompt == "Run pytest in this repo."


def test_load_corpus_returns_all_files_alphabetically(tmp_path):
    _write_task(tmp_path, "20_dangerous.md",
                "id: 20_dangerous\ncategory: dangerous",
                "Drop the customers table.")
    _write_task(tmp_path, "01_innocent.md",
                "id: 01_innocent\ncategory: innocent",
                "Run tests.")
    _write_task(tmp_path, "10_ambig.md",
                "id: 10_ambig\ncategory: ambig",
                "Clean up old data.")
    tasks = load_corpus(tmp_path)
    assert [t.id for t in tasks] == ["01_innocent", "10_ambig", "20_dangerous"]


def test_load_corpus_skips_malformed_frontmatter(tmp_path, caplog):
    """Malformed frontmatter should warn and skip, not crash the sweep."""
    _write_task(tmp_path, "good.md",
                "id: good\ncategory: innocent",
                "Run tests.")
    # No frontmatter delimiters
    (tmp_path / "broken.md").write_text("just a body, no frontmatter\n")
    # Frontmatter but no required fields
    (tmp_path / "missing_fields.md").write_text(
        "---\nrandom: stuff\n---\nbody\n"
    )

    with caplog.at_level(logging.WARNING):
        tasks = load_corpus(tmp_path)

    assert [t.id for t in tasks] == ["good"]
    # Both broken files should have produced warning logs
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) >= 2


def test_load_corpus_returns_empty_on_missing_dir(tmp_path):
    missing = tmp_path / "does_not_exist"
    assert load_corpus(missing) == []


def test_load_corpus_strips_prompt_whitespace(tmp_path):
    _write_task(tmp_path, "x.md",
                "id: x\ncategory: innocent",
                "  \n  Run tests.  \n  ")
    tasks = load_corpus(tmp_path)
    assert tasks[0].prompt == "Run tests."


def test_load_corpus_ignores_non_md_files(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    _write_task(tmp_path, "good.md",
                "id: good\ncategory: innocent",
                "ok")
    (tmp_path / "README.txt").write_text("not markdown")
    (tmp_path / ".DS_Store").write_text("junk")
    tasks = load_corpus(tmp_path)
    assert [t.id for t in tasks] == ["good"]


def test_chaostask_dataclass_equality():
    a = ChaosTask(id="x", category="innocent", prompt="p")
    b = ChaosTask(id="x", category="innocent", prompt="p")
    assert a == b
