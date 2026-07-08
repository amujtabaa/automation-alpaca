#!/usr/bin/env python3
"""PKL frontmatter checker.

Fails (exit 1) on pages missing required frontmatter keys. Warns (exit 0) when
an `authority: high` page has a `last_verified` older than `pkl_staleness_days`
from rules/ai-os-rules.yaml (default 90) — 04's lint spec: "last_verified is
not stale for high-authority pages".

Usage:
  python scripts/check_pkl.py pkl/
"""
from __future__ import annotations
import sys
from datetime import date, datetime
from pathlib import Path

from ai_os_paths import find_root, get_pkl_root, load_scalar

REQUIRED = {"type", "title", "status", "authority", "owner", "last_verified", "tags"}

def parse_frontmatter(text: str) -> dict[str, str] | None:
    if not text.startswith('---\n'):
        return None
    end = text.find('\n---\n', 4)
    if end == -1:
        return None
    block = text[4:end]
    data = {}
    for line in block.splitlines():
        if ':' in line and not line.lstrip().startswith('#'):
            k, v = line.split(':', 1)
            data[k.strip()] = v.strip()
    return data


def main() -> int:
    repo = find_root()
    if len(sys.argv) > 1:
        root_dir = Path(sys.argv[1])
    else:
        root_dir = get_pkl_root(repo) if repo else Path('pkl')
    staleness_days = int(load_scalar(repo, 'pkl_staleness_days') or 90) if repo else 90
    failures = []
    warnings = []
    for p in root_dir.rglob('*.md'):
        if p.name in {'index.md', 'log.md'}:
            continue
        fm = parse_frontmatter(p.read_text(encoding='utf-8'))
        if fm is None:
            failures.append(f'{p}: missing YAML frontmatter')
            continue
        missing = REQUIRED - set(fm)
        if missing:
            failures.append(f'{p}: missing {sorted(missing)}')
        if fm.get('authority') == 'high' and fm.get('last_verified'):
            try:
                verified = datetime.strptime(fm['last_verified'], '%Y-%m-%d').date()
            except ValueError:
                warnings.append(f'{p}: unparseable last_verified {fm["last_verified"]!r}')
            else:
                age = (date.today() - verified).days
                if age > staleness_days:
                    warnings.append(f'{p}: stale last_verified for high-authority page ({age} days > {staleness_days})')
    for w in warnings:
        print('WARNING -', w)
    if failures:
        print('PKL CHECK FAILED')
        for f in failures:
            print('-', f)
        return 1
    print('PKL CHECK PASSED')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
