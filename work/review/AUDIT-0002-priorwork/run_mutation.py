"""Run one existing pytest pin under a packet-local runtime mutation."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


PACKET = Path(__file__).resolve().parent


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: run_mutation.py <mutation> <pytest-node>")
    mutation, node = sys.argv[1:]
    sys.path.insert(0, str(PACKET))
    os.environ["AUDIT_0002_MUTATION"] = mutation
    return int(
        pytest.main(
            [
                "-q",
                "-p",
                "no:cacheprovider",
                "-p",
                "mutation_plugin",
                node,
            ]
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
