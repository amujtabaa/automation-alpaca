"""Create a reproducible development environment and run the baseline smoke gates."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from collections.abc import Sequence


PYTHON_VERSION = (3, 12)


def _venv_python(venv: Path) -> Path:
    """Return the platform-specific Python executable inside *venv*."""
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def _is_python_312(executable: str) -> bool:
    probe = subprocess.run(
        [executable, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
        capture_output=True,
        check=False,
        text=True,
    )
    return probe.returncode == 0 and probe.stdout.strip() == "3.12"


def _find_python_312() -> str:
    if sys.version_info[:2] == PYTHON_VERSION:
        return sys.executable

    candidates: list[str] = []
    if os.name == "nt" and shutil.which("py"):
        launcher_probe = subprocess.run(
            ["py", "-3.12", "-c", "import sys; print(sys.executable)"],
            capture_output=True,
            check=False,
            text=True,
        )
        if launcher_probe.returncode == 0:
            candidates.append(launcher_probe.stdout.strip())

    for name in ("python3.12", "python3.12.exe"):
        candidate = shutil.which(name)
        if candidate:
            candidates.append(candidate)

    for candidate in candidates:
        if _is_python_312(candidate):
            return candidate

    msg = "Python 3.12 is required but was not found. Install it, then rerun this command."
    raise RuntimeError(msg)


def _run(command: Sequence[str], *, cwd: Path) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True, cwd=cwd)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or refresh the Python 3.12 development environment and smoke-check it."
    )
    parser.add_argument(
        "--venv",
        default=".venv",
        metavar="PATH",
        help="virtual-environment path relative to the repository root (default: .venv)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    root = Path(__file__).resolve().parent.parent
    venv = (root / args.venv).resolve()
    requirements = root / "requirements.txt"
    constraints = root / "constraints.txt"

    if not requirements.is_file() or not constraints.is_file():
        raise RuntimeError("Run this script from a checkout containing requirements.txt and constraints.txt.")

    python = _venv_python(venv)
    if python.is_file():
        print(f"Reusing virtual environment: {venv}", flush=True)
    else:
        venv.parent.mkdir(parents=True, exist_ok=True)
        _run([_find_python_312(), "-m", "venv", str(venv)], cwd=root)

    _run([str(python), "-m", "pip", "install", "--upgrade", "pip"], cwd=root)
    _run(
        [str(python), "-m", "pip", "install", "-r", "requirements.txt", "-c", "constraints.txt"],
        cwd=root,
    )
    _run([str(python), "-m", "ruff", "check", "."], cwd=root)
    _run([str(python), "-m", "mypy", "app/"], cwd=root)
    _run([str(python), "-m", "pytest", "-q", "--collect-only"], cwd=root)
    print("Bootstrap complete: smoke gates are runnable.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"bootstrap: error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
