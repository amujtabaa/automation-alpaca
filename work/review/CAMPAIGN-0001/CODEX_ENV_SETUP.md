# CAMPAIGN-0001 — Reviewer environment setup (Python 3.12.3, authoritative)

**Purpose.** Wave-1 was reviewed on Python **3.14.5** with no gate tools, so its dynamic
reproductions were environment-limited and the crash/restart probe could not run. This document
provisions a **workspace-local Python 3.12** review environment matching the project pin
(`CLAUDE.md`: "Python 3.12"; CI: 3.11 + 3.12) so **future waves are authoritative** — repros, the
full suite, and the lint/type/import gate all run on the interpreter the code actually targets.

> The repo pins the **3.12 minor**, not a specific patch; any 3.12.x (e.g. 3.12.3) satisfies it.
> Do **not** substitute 3.13/3.14 for gating evidence.

## 1. Get a Python 3.12 interpreter
Codex's box currently has only 3.14. Install a 3.12 side-by-side (any ONE of these):

- **`uv` (recommended — fastest, no admin, cross-platform):**
  ```
  # install uv once: https://docs.astral.sh/uv/  (Windows: `winget install astral-sh.uv` or the PS installer)
  uv python install 3.12
  ```
- **python.org installer (Windows):** download "Windows installer (64-bit)" for the latest 3.12.x,
  install for-current-user, **do not** add to PATH globally (keep it side-by-side). Then use the
  launcher `py -3.12`.
- **pyenv-win:** `pyenv install 3.12.9` (or latest 3.12.x); `pyenv local 3.12.9` in the repo.

## 2. Create the venv + install the pinned toolchain
Run from the repo root (`automation-alpaca/`). The gate tools are in `requirements.txt`; the exact
versions are pinned by `constraints.txt` (`ruff==0.15.20`, `mypy==2.2.0`, `import-linter==2.13`,
`grimp==3.15`, `pytest==9.1.1`, `pytest-cov==7.1.0`).

- **With `uv`:**
  ```
  uv venv --python 3.12 .venv-review
  # Windows:  .\.venv-review\Scripts\activate      POSIX:  source .venv-review/bin/activate
  uv pip install -r requirements.txt -c constraints.txt
  ```
- **With stdlib venv + pip:**
  ```
  py -3.12 -m venv .venv-review          # POSIX: python3.12 -m venv .venv-review
  .\.venv-review\Scripts\activate         # POSIX: source .venv-review/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt -c constraints.txt
  ```
`.venv-review/` is workspace-local; add it to your local ignore if it isn't already covered.

## 3. Validate (all must pass before a review is called authoritative)
```
python --version                        # -> Python 3.12.x
python -c "import fastapi, pydantic, httpx, alpaca; print('deps ok')"
ruff --version                          # 0.15.20
mypy --version                          # mypy 2.2.0
lint-imports --version                  # import-linter 2.13
python -m pytest -q tests/test_position_folding.py   # sanity: passes
```
Gate commands the campaign relies on (run from repo root, venv active):
```
ruff check .
mypy app/
lint-imports
python -m pytest -q            # full suite (or `--cov=app` for the coverage floor)
```

## 4. Use it for every review
- Activate `.venv-review` before running any probe, repro, or gate command.
- In each `result.md`, state the interpreter (`Python 3.12.x`) and paste real command output —
  evidence is no longer "environment-limited."
- The frozen review base is still **`b600101`**; `git diff b600101 HEAD -- app` should be empty for
  a clean review checkout.

## Notes
- **This is a reviewer-environment fix, not a project change.** The project is correctly pinned to
  3.12; 3.14 is *newer* than the pin, so the earlier SQLite `ResourceWarning` failures under 3.14
  are a "not-yet-forward-ported" artifact, not staleness. Reviewing on 3.12 removes that noise.
- If installing 3.12 is impossible in the sandbox, keep labeling Python-dependent evidence as
  environment-limited — the author will continue re-running each finding in 3.12 (as for Wave 1).
