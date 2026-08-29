"""Deterministic WO-0170 fault-soak driver with evidence-faithful status."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from time import monotonic
from typing import Final, Sequence

from harness.m2.closeout import SOAK_NODEIDS


REQUIRED_SOAK_SECONDS: Final = 24 * 60 * 60


def soak_status(
    *, configured_seconds: float, elapsed_seconds: float, passed: bool
) -> str:
    if not passed:
        return "FAILED"
    if (
        configured_seconds < REQUIRED_SOAK_SECONDS
        or elapsed_seconds < REQUIRED_SOAK_SECONDS
    ):
        return "NOT_RUN"
    return "PASSED"


def _utc_text() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_soak(
    *,
    repository_root: Path,
    python: Path,
    evidence_directory: Path,
    duration_seconds: float,
    max_cycles: int | None,
) -> int:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    if max_cycles is not None and max_cycles <= 0:
        raise ValueError("max_cycles must be positive when supplied")
    root = repository_root.resolve(strict=True)
    interpreter = python.resolve(strict=True)
    evidence = evidence_directory.resolve(strict=False)
    if evidence.exists():
        raise FileExistsError("evidence directory must be new")
    evidence.mkdir(parents=True)

    started = monotonic()
    cycle = 0
    passed = True
    records: list[dict[str, object]] = []
    while monotonic() - started < duration_seconds:
        if max_cycles is not None and cycle >= max_cycles:
            break
        cycle += 1
        cycle_root = evidence / f"cycle-{cycle:06d}"
        command = (
            str(interpreter),
            "-m",
            "pytest",
            *SOAK_NODEIDS,
            "--basetemp",
            str(cycle_root / "pytest"),
        )
        cycle_started = monotonic()
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            check=False,
        )
        output = completed.stdout + completed.stderr
        log_path = evidence / f"cycle-{cycle:06d}.log"
        log_path.write_bytes(output)
        record = {
            "cycle": cycle,
            "finished_at_utc": _utc_text(),
            "elapsed_seconds": monotonic() - cycle_started,
            "returncode": completed.returncode,
            "command": command,
            "output_sha256": sha256(output).hexdigest(),
            "log": log_path.name,
        }
        records.append(record)
        with (evidence / "cycles.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        if completed.returncode != 0:
            passed = False
            break

    elapsed = monotonic() - started
    summary = {
        "status": soak_status(
            configured_seconds=duration_seconds,
            elapsed_seconds=elapsed,
            passed=passed,
        ),
        "configured_seconds": duration_seconds,
        "required_seconds": REQUIRED_SOAK_SECONDS,
        "elapsed_seconds": elapsed,
        "cycles": cycle,
        "all_cycles_passed": passed,
        "nodeids": SOAK_NODEIDS,
        "records": len(records),
    }
    (evidence / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if passed else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-seconds", type=float, default=REQUIRED_SOAK_SECONDS)
    parser.add_argument("--max-cycles", type=int)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--evidence-directory", type=Path)
    parser.add_argument("--list", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.list:
        print("\n".join(SOAK_NODEIDS))
        return 0
    if arguments.evidence_directory is None:
        raise SystemExit("--evidence-directory is required unless --list is used")
    root = Path(__file__).resolve().parents[2]
    return run_soak(
        repository_root=root,
        python=arguments.python,
        evidence_directory=arguments.evidence_directory,
        duration_seconds=arguments.duration_seconds,
        max_cycles=arguments.max_cycles,
    )


if __name__ == "__main__":
    raise SystemExit(main())
