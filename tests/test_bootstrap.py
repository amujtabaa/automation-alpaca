"""Boundary pins for the repository-local development bootstrap."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness import bootstrap


@pytest.mark.parametrize("configured", (Path("..") / "shared-venv", Path.cwd().anchor))
def test_resolve_venv_rejects_paths_outside_repository(tmp_path, configured):
    root = tmp_path / "checkout"
    root.mkdir()

    with pytest.raises(RuntimeError, match="inside the repository root"):
        bootstrap._resolve_venv(root, configured)


def test_resolve_venv_rejects_repository_root_itself(tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()

    with pytest.raises(RuntimeError, match="inside the repository root"):
        bootstrap._resolve_venv(root, ".")


def test_resolve_venv_accepts_nested_repository_path(tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()

    assert bootstrap._resolve_venv(root, ".venv") == (root / ".venv").resolve()
