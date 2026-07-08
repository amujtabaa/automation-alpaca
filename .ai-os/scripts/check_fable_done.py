#!/usr/bin/env python3
"""Check a saved agent transcript for basic Fable DONE evidence.

Accepts both Fable block dialects (see 06_FABLE_V3_EXECUTION_PROTOCOL.md):
- canonical YAML blocks: `fable_done:` with `status: VERIFIED|...`
- skill-edition prose blocks: `[DONE] ... STATUS: VERIFIED|...`

Usage:
  python scripts/check_fable_done.py transcript.md
"""
from __future__ import annotations
import sys
from pathlib import Path

VALID = ['STATUS: VERIFIED', 'STATUS: UNVERIFIED', 'STATUS: BLOCKED', 'STATUS: NEEDS-INPUT', 'status: VERIFIED', 'status: UNVERIFIED', 'status: BLOCKED', 'status: NEEDS-INPUT']


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: check_fable_done_stub.py <transcript.md>')
        return 2
    text = Path(sys.argv[1]).read_text(encoding='utf-8')
    errors = []
    if '[DONE]' not in text and 'fable_done:' not in text:
        errors.append('missing DONE block')
    if not any(v in text for v in VALID):
        errors.append('missing valid status')
    if 'VERIFIED' in text and 'command:' not in text and 'Evidence:' not in text and 'evidence:' not in text:
        errors.append('VERIFIED appears without evidence/command marker')
    if errors:
        print('FABLE CHECK FAILED')
        for e in errors:
            print('-', e)
        return 1
    print('FABLE CHECK PASSED')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
