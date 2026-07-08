#!/usr/bin/env python3
"""Check changed files against a work order's scope and the repo rules.

Failures (exit 1): a changed path matches the work order's forbidden_paths,
falls outside its allowed_paths, or matches a `forbidden_patterns` entry from
rules/ai-os-rules.yaml (secrets-like files). Sensitive paths (`sensitive_paths`
in the rules file) produce a warning requiring the security checklist, not a
failure — a work order may legitimately touch them under review.

Usage:
  git diff --name-only main...HEAD | python scripts/check_work_order_scope.py work/active/WO-0001.md
"""
from __future__ import annotations
import fnmatch
import re
import sys
from pathlib import Path

from ai_os_paths import find_root, load_yaml_list


def extract_list(text: str, key: str) -> list[str]:
    pattern = re.compile(rf'{key}:\s*\n((?:\s+-\s+.*\n)+)', re.M)
    m = pattern.search(text)
    if not m:
        return []
    return [line.split('-', 1)[1].strip().strip('"\'') for line in m.group(1).splitlines() if '-' in line]


def match_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: check_work_order_scope.py <work-order.md> < changed-files')
        return 2
    work_order = Path(sys.argv[1]).read_text(encoding='utf-8')
    allowed = extract_list(work_order, 'allowed_paths')
    forbidden = extract_list(work_order, 'forbidden_paths')
    root = find_root()
    rule_forbidden = load_yaml_list(root, 'forbidden_patterns') if root else []
    sensitive = load_yaml_list(root, 'sensitive_paths') if root else []
    changed = [line.strip() for line in sys.stdin if line.strip()]
    failures = []
    warnings = []
    for path in changed:
        basename = path.replace('\\', '/').rsplit('/', 1)[-1]
        if forbidden and match_any(path, forbidden):
            failures.append(f'forbidden path changed: {path}')
        if rule_forbidden and (match_any(path, rule_forbidden) or match_any(basename, rule_forbidden)):
            failures.append(f'forbidden pattern from rules/ai-os-rules.yaml: {path}')
        if allowed and not match_any(path, allowed):
            failures.append(f'outside allowed paths: {path}')
        if sensitive and match_any(path, sensitive):
            warnings.append(f'sensitive path changed (security checklist required): {path}')
    for w in warnings:
        print('WARNING -', w)
    if failures:
        print('SCOPE CHECK FAILED')
        for f in failures:
            print('-', f)
        return 1
    print('SCOPE CHECK PASSED')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
