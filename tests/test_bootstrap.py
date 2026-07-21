"""Boundary pins for the repository-local development bootstrap."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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


def test_main_rejects_external_venv_before_running_any_command(monkeypatch):
    monkeypatch.setattr(
        bootstrap,
        "_parse_args",
        lambda: SimpleNamespace(venv=str(Path("..") / "shared-venv")),
    )

    def fail_if_called(*args, **kwargs):
        pytest.fail(f"bootstrap command ran for an external venv: {args!r} {kwargs!r}")

    monkeypatch.setattr(bootstrap, "_run", fail_if_called)

    with pytest.raises(RuntimeError, match="inside the repository root"):
        bootstrap.main()
