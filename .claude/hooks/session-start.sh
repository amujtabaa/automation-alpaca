#!/bin/bash
# SessionStart hook — make Claude Code on the web sessions match the project's
# documented runtime (Python 3.12+, see README.md / AGENTS.md) and install the
# backend + cockpit + test dependencies so the suite runs immediately.
#
# Why this exists: fresh web containers boot with Python 3.11 as the default
# `python` and none of requirements.txt installed. This hook pins the default
# to 3.12 and installs deps so `python -m pytest` works on session start.
#
# Idempotent: safe to run on every session start (startup/resume/clear/compact).
set -euo pipefail

# Only act in the remote (Claude Code on the web) environment; never touch a
# developer's local machine.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Prefer 3.12, fall back to a newer 3.x if 3.12 isn't present in the image.
PY312="$(command -v python3.12 || true)"
if [ -z "$PY312" ]; then
  PY312="$(command -v python3.13 || true)"
fi
if [ -z "$PY312" ]; then
  echo "session-start: no python3.12/3.13 interpreter found; leaving default python as-is" >&2
  exit 0
fi

# Repoint the default `python`/`python3` to the chosen 3.12+ interpreter so the
# documented runtime is what the session uses. /usr/local/bin precedes
# /usr/bin on PATH, so these symlinks win.
ln -sf "$PY312" /usr/local/bin/python
ln -sf "$PY312" /usr/local/bin/python3

# Point `pip`/`pip3` at the same interpreter's pip.
cat > /usr/local/bin/pip <<EOF
#!/bin/sh
exec "$PY312" -m pip "\$@"
EOF
cp /usr/local/bin/pip /usr/local/bin/pip3
chmod +x /usr/local/bin/pip /usr/local/bin/pip3

# Install project dependencies into the 3.12 interpreter. The web image marks
# the system interpreter as PEP 668 externally-managed and this project uses a
# system-wide (no-venv) layout, so --break-system-packages matches the existing
# setup. The container caches its state after the hook, so a plain install
# (not a clean reinstall) is the cheaper choice on resume.
"$PY312" -m pip install --break-system-packages -r "$CLAUDE_PROJECT_DIR/requirements.txt"

echo "session-start: default python -> $("$PY312" --version 2>&1), requirements installed"
