"""WO-0018 — package hygiene regressions.

1. Bare-clock ban: no `datetime.now(`, `time.time(`, or `utcnow(` anywhere in
   `app/sellside/` — the injected clock is the ONLY time source (engine
   discipline, CLAUDE.md §Testing; the LASE v1 spike was deleted for exactly
   this violation, ADR-010 D-4).
2. The import-linter contract for the package exists in `.importlinter`, so
   CI enforces the purity boundary (models/marketdata types only).
"""

from __future__ import annotations

import re
from pathlib import Path

SELLSIDE = Path(__file__).resolve().parent.parent / "app" / "sellside"

BANNED = re.compile(r"datetime\.now\(|time\.time\(|utcnow\(")


def test_no_bare_clock_reads_in_sellside():
    assert SELLSIDE.is_dir(), "app/sellside/ package missing"
    offenders = []
    for path in sorted(SELLSIDE.rglob("*.py")):
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if BANNED.search(line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, (
        "bare clock reads in app/sellside/ (injected clock only):\n"
        + "\n".join(offenders)
    )


def test_sellside_import_contract_is_registered():
    config = (Path(__file__).resolve().parent.parent / ".importlinter").read_text()
    assert "sellside" in config, (
        ".importlinter has no sellside contract — the purity boundary "
        "(models/marketdata types only) must be CI-enforced"
    )
