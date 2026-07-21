# Repository Primer

## What This Repo Is

`automation-alpaca` is a browser-operated, paper-first Alpaca trading platform for one local
beta operator. FastAPI is the durable backend; Streamlit is only a thin cockpit client. No live
trading belongs in beta: credentials, when deliberately configured, are Alpaca **Paper** only.

## Product / Feature Structure

| Module | Responsibility |
| --- | --- |
| Cockpit | Displays backend state and submits typed intents through the API client. |
| Backend | Owns candidate, approval, order, fill, position, reconciliation, and kill-switch rules. |
| Broker adapter | The only Alpaca SDK boundary; paper adapter or credential-free mock. |
| Strategy/CAPI | Produces candidates and applies pre-trade risk limits; it does not bypass approval. |
| Tape recorder | Optional, read-only market-data corpus capture; it has no order-flow or StateStore access. |

## Tech Stack and Boundaries

- Python 3.12, FastAPI, Streamlit, SQLite, and an in-memory store for tests; dependencies are
  pinned by `constraints.txt`. A new dependency needs an ADR first.
- Required flow: `ui → api → facade → engine → adapter/store`. Imports cross only approved seams;
  `alpaca-py` stays in the adapter and Streamlit imports only the typed API client.
- The execution engine is the single writer. Submitted is not filled; only deduplicated fills
  change position quantity. The kill switch blocks new order intent.
- No authentication, billing, or public production ingress is part of this beta. Do not add one
  without its own approved architecture decision.

## Project Structure

```text
app/                 FastAPI backend, engine, adapters, stores, configuration
cockpit/             Streamlit thin client and typed API client
tests/               Unit, integration, import-boundary, oracle, and mutation pins
audit_harness/        Replay/parity and audit utilities
docs/                Invariants, specifications, and accepted/proposed ADRs
pkl/                 Project knowledge and architecture/process records
work/                Work orders, review packets, append-only ledger, completed artifacts
harness/bootstrap.py Fresh-clone environment bootstrap and smoke gate
```

## Important Paths

| Path | Purpose |
| --- | --- |
| `CLAUDE.md` | Binding safety core and repository-wide engineering contract. |
| `AGENTS.md` | AI Project OS adapter and independent-review rules. |
| `app/config.py` | Complete runtime configuration inventory and validation. |
| `docs/INVARIANTS.md` | Living invariant registry and review oracle. |
| `docs/adr/` | Architecture decisions; amendments require a tracked review packet. |
| `.ai-os/core/15_CROSS_MODEL_REVIEW.md` | Packet ownership and review-disposition protocol. |
| `.env.example` | Safe, complete configuration template; `.env` is ignored. |
| `work/ledger.jsonl` | Append-only evidence ledger; close-outs retain every line. |

## Build and Verification Commands

Run `python harness/bootstrap.py` for a fresh clone. It creates/refreshes `.venv`, installs pinned
dependencies, and executes a smoke gate without reading credentials, state files, or databases.

```powershell
ruff check .
ruff format --check .
mypy app/
lint-imports
pytest -q --basetemp (Join-Path ([System.IO.Path]::GetTempPath()) 'pytest-<unique-id>')
python tests/r2_conformance_oracle.py
pytest -q tests/test_wo0113_repair_scaling.py
```

Use an explicit unique OS-temp `--basetemp` on Windows; never create pytest scratch under the
repository root. The conformance oracle is an AST/spec check, not a substitute for behavioral
tests. The scaling gate is structural plus measured evidence; do not claim capacity from a passing
unit test alone.

## Environment Variables

All configuration reads are documented in `.env.example`. With both paper keys blank,
`BROKER_ADAPTER=auto` and `MARKET_DATA_FEED=auto` remain credential-free mock paths. `STATE_STORE`
defaults to SQLite; use `memory` only for tests. Keep `ENABLE_TAPE_RECORDER=false` unless a
deliberate corpus capture supplies `TAPE_RECORDER_SYMBOLS`; recorder output is separate from
execution truth. Never commit `.env`, credentials, or a live-key variable.

## Common Gotchas

1. Test state changes on both in-memory and SQLite stores; dual-store parity is mandatory for
   order/fill/position/reconciliation/kill-switch behavior.
2. Inject clocks and deterministic IDs/queues in engine tests; no bare wall-clock calls or
   unseeded randomness.
3. Human-gated surfaces are order submission, cancel/replace, kill switch, flatten, live/shadow
   config, schema/migration, event-log truth, and test/doc/ADR deletion. Stop for explicit scope
   approval beyond the ratified decision block.
4. Close a work order atomically: status, allowed disposition, ledger line, required knowledge
   update, and file move ship in the finishing commit. A green change without that ratchet is open.

## Working Protocol

1. Read `AGENTS.md`, `CLAUDE.md`, the assigned work order, and only its linked context. Apply
   Fable v3: GATE, red-first proof, implementation, FIX root cause, fresh evidence, then DONE.
2. Use isolated worktrees for safe parallel work and serialize work orders sharing a file or ledger
   append conflict. Preserve both append-only ledger lines when resolving a conflict.
3. After pause or compaction, re-read the batch kickoff, state file, active WO, then verify
   `git log` and `git status`; the state file's pasted decision block is authoritative.
4. A reviewer owns `work/review/REV-*/result.md`: the reviewed party never edits it in place.
   Corrections are separate disclosed addenda. Every gated-surface change receives a tracked
   `REV-*` packet even if review discussion occurs in PR threads; record that PR verdict there.

## Execution Preference

Use the locally strongest model for human-gated, event-truth, execution, and other perilous work.
Cloud is suitable for bounded mid-tier documentation, bootstrap, or bookkeeping work. When in
doubt, treat a gated surface as local work; never use an archive-only `recommended_model`
frontmatter convention as an execution decision.

