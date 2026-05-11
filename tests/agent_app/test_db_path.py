"""Tests for agent_app.tools.delegate path resolution."""

from pathlib import Path

from agent_app.tools.delegate import _DEFAULT_DB


def test_default_db_path_points_at_project_root() -> None:
    """_DEFAULT_DB must resolve to <project_root>/one_agent.db.

    Verifies by checking that the parent directory contains
    pyproject.toml, which is the project-root sentinel. This form
    is worktree-agnostic (works in both main checkout and .worktrees/).
    """
    db_path = Path(_DEFAULT_DB)
    assert db_path.name == "one_agent.db"
    assert (db_path.parent / "pyproject.toml").exists(), (
        f"_DEFAULT_DB parent does not look like the project root: "
        f"{db_path.parent}"
    )
