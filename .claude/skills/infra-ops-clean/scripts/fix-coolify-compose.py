#!/usr/bin/env python3
"""
Pin Coolify dashboard (port 8000) + Soketi realtime (6001, 6002) to 127.0.0.1.
Security playbook item #1 from the <DATE> incident.

Idempotent: running twice is a no-op.
"""
import sys
from pathlib import Path

PATH = Path("/data/coolify/source/docker-compose.prod.yml")

REPLACEMENTS = [
    ('- "${APP_PORT:-8000}:8080"',     '- "127.0.0.1:${APP_PORT:-8000}:8080"'),
    ('- "${SOKETI_PORT:-6001}:6001"',  '- "127.0.0.1:${SOKETI_PORT:-6001}:6001"'),
    ('- "6002:6002"',                  '- "127.0.0.1:6002:6002"'),
]

content = PATH.read_text()
changed = False
for old, new in REPLACEMENTS:
    if new in content:
        print(f"  already-pinned: {new.strip()}")
        continue
    if old not in content:
        print(f"  NOT FOUND (manual review needed): {old}")
        sys.exit(2)
    content = content.replace(old, new)
    changed = True
    print(f"  pinned: {old.strip()} -> {new.strip()}")

if changed:
    PATH.write_text(content)
    print("written")
else:
    print("no changes needed")
