---
type: Work Order
title: "Single-source replace-budget projection: one counter for enforcement AND display (CC-05 remainder, re-cut from WO-0029)"
status: ACTIVE
work_order_id: WO-0126
wave: W3-debt closure (re-cut per O-1, AUDIT-0002 F005)
model_tier: mid
risk: low
disposition: []
owner: Ameen / Codex implementer
created: 2026-07-20
gated_surface: none (read-model truthfulness; enforcement semantics unchanged)
---

# Work Order: `replaces_used` shows the same truth it enforces

## Goal

Close WO-0029's verified-open CC-05 remainder: the cancel/replace budget count is derived from
ONE shared source — the `ENVELOPE_ACTION` event log — consumed by BOTH the policy enforcement
(`app.sellside.policy._replaces_used`) and the read/cockpit projection, so display and
enforcement cannot drift. No second stored writer (the "same truth derived twice" anti-pattern
AUDIT-0001 flagged); the stored `replaces_used` field either becomes derived-only or is removed.

## Context packet

- `work/review/FINDING-W3-envelope-lifecycle-eventing-gaps.md` (CC-05) +
  `work/completed/WO-0029-envelope-eventing-terminal-semantics.md` (superseded umbrella; the
  WO-0036 F5 partial: the false models.py comment is already fixed — the read-model is the gap)
- `work/review/AUDIT-0002-priorwork/report.md` F005
- `app/sellside/policy.py` (`_replaces_used` — the enforcement-side counter to share)
- `app/models.py` (the stored `replaces_used` field) + the cockpit envelope column
- `docs/adr/ADR-010-execution-envelope.md` §2/§5 (budget is a hard rail; refused_stale never counts)

## Allowed paths

```yaml
allowed_paths:
  - app/events/**            # the shared counter lives with the projections
  - app/sellside/policy.py   # consume the shared counter (behavior-preserving; pins prove it)
  - app/api/**               # read-model surface exposing the derived value
  - app/facade/**            # only if the read path routes through the facade queries
  - cockpit/**               # the column shows the derived truth
  - app/models.py            # ONLY if the stored field is removed/annotated (flag explicitly)
  - app/store/core.py        # D-0126: delete the obsolete draft-field dependency only
  - app/store/sqlite.py      # D-0126: stop hydrating/writing the field; no DDL/migration
  - tests/**
  - work/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/monitoring.py
  - docs/adr/**
```

All other `app/store/**` paths remain out of scope. The operator's pasted D-0126 is the narrow
scope update for the two named store files: remove every application read/write/hydration/draft
use of `replaces_used`. The existing SQLite column remains an inert compatibility tombstone so
old databases continue opening without DDL; it is not read, written, cached, or enforced from.

## Required behavior

- [ ] One pure shared counter over the `ENVELOPE_ACTION` log (respecting `refused_stale` never
      counting, per ADR-010 §5) consumed by BOTH enforcement and display.
- [ ] Enforcement behavior is UNCHANGED — pinned by the existing budget tests staying green plus
      a differential pin (old inline derivation vs shared counter agree across the action corpus).
- [ ] Cockpit/API show the derived value; the stored field cannot drift from it (removed, or
      demoted to a documented cache that nothing enforces from — decision recorded in the WO).
- [ ] Red-first for the read-model truth; both stores where the API reads differ.

## Acceptance criteria

- [ ] Zero drift possible between enforced and displayed budget (single derivation, pinned).
- [ ] Full gates green; Fable DONE with evidence; close-out + ledger with the work.

## Stop conditions

Stop if the shared counter would change any enforcement verdict on the existing corpus — that
means the old derivations disagreed, which is a FINDING to surface, not silently resolve.
Independent of Lane P (disjoint files); may run any time.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]`.

## Fable gate

`[FABLE • FULL • verification: DIRECT • task: WO-0126 single-source replace-budget projection]`

```yaml
fable_gate:
  goal: "Make the ENVELOPE_ACTION log the only application truth for replace-budget enforcement and display, with no stored domain counter."
  assumptions:
    - "Until WO-0124, the frozen incumbent budget corpus is reprice + cancel; refused_stale, submit, resize, and unrelated events do not count."
    - "D-0126 authorizes removal of the application field and the exact core/sqlite compatibility edits above, but no DDL or migration."
    - "The policy history and facade store seam expose the complete execution-event history needed for deterministic projection."
  approach: "Write differential, mutation-capable, dual-store/reopen/API/cockpit red tests; add one pure event counter under app/events; consume it from policy and a derived API read view; remove every domain/store dependency on the obsolete field."
  out_of_scope:
    - "any execution-event write or event-schema change"
    - "DDL, database migration, or physical removal of the historical SQLite column"
    - "WO-0124 disposition-cancel convergence or its future reprice-only budget decision"
    - "app/monitoring.py, ADR text, or any store file beyond core.py/sqlite.py"
  done_when:
    - "A single pure ENVELOPE_ACTION-derived counter is consumed by both enforcement sites and every displayed envelope read."
    - "The old and new counters agree across the complete incumbent action corpus and existing enforcement verdicts stay green."
    - "Memory and reopened SQLite API reads expose identical derived usage; cockpit renders it without a zero fallback."
    - "ExecutionEnvelope and active store code contain no replaces_used field read/write/hydration/cache semantics."
    - "Focused, mutation, full static/test, AI-OS, scope, ledger, and hygiene gates pass with fresh evidence."
    - "Close-out status, disposition, ledger, move, and batch scoreboard ship atomically."
  blast_radius: "app/events projection helper; sell-side policy reads; envelope API/facade read model; cockpit display; narrow model/core/sqlite field deletion; tests/work records"
```

## Activation evidence

```yaml
evidence:
  - command: "incumbent envelope model/policy/cockpit/replay tests with cache disabled and unique OS-temp basetemp"
    result: PASS
    decisive_output: "87 passed in 1.86s"
  - command: "ruff check scoped incumbent surfaces"
    result: PASS
    decisive_output: "All checks passed!"
  - command: "mypy app/"
    result: PASS
    decisive_output: "Success: no issues found in 70 source files"
  - command: "lint-imports"
    result: PASS
    decisive_output: "Analyzed 99 files, 484 dependencies; 6 contracts kept, 0 broken"
```

## Red-first evidence

```yaml
evidence:
  - command: "WO-0126 + incumbent model/policy/cockpit tests before production changes, cache disabled, unique OS-temp basetemp"
    result: FAIL
    decisive_output: "13 failed, 72 passed in 2.95s: missing shared projector; both HTTP stores returned stale 0; hostile SQLite tombstone blocked reopen; domain field remained accepted; policy/facade wiring and cockpit missing-truth pins failed."
  - command: "cockpit-only red refinement"
    result: FAIL
    decisive_output: "1 failed, 4 passed: a payload missing replaces_used was silently rendered as zero; the nonzero 2/5 rendering control passed."
```

The accepted import-linter contract explicitly forbids `app.sellside` from importing
`app.events`. The single projector therefore remains in the pure sell-side policy module and is
consumed downward by no stateful dependency and upward by the facade read model. This preserves
the accepted architecture while still providing one computation to both enforcement and display.
