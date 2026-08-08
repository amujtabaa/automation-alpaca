---
type: Work Order
title: "Architecture reset M0: ratified documentation landing"
status: CLOSED
work_order_id: WO-0144
wave: ARCH-RESET-M0
model_tier: strong
risk: high
disposition: [ADR_CREATED, PKL_UPDATED, RESULT_SUMMARY_KEPT]
owner: Codex implementation seat
created: 2026-07-31
branch: codex/arch-reset-2026-07-r1
base_sha: 6d5937492788aa0ab1cf8348321fa01ee57df920
---

# WO-0144 — Architecture reset M0 documentation landing

`[FABLE • FULL • verification: DIRECT; independent review required • task: M0 documentation landing]`

## Authorization

Ameen ratified the unchanged `ARCH-RESET-2026-07-R1` unit with:

- authority-manifest SHA-256 `c81e49ac3b36d7d99f0974cf34f2f89330e3336eea5877341f3b170aec1a2258`;
- archive SHA-256 `51e4bb1a7ce0c00f16cce57c0fa6f15aad33773f0c62ea57d637b55e8eba053f`;
- authority limited to the M0 documentation landing and nothing else.

The user subsequently assigned this task to the implementation seat, permitting one local documentation-only
commit for review. It does not permit a push, pull request, merge, production/test implementation or execution,
SQL/DDL/database tooling, broker/credential access, Paper/live-shadow/live activity, deletion, or cleanup.

On 2026-07-31 the user later authorized broader local implementation, verification, and in-flight remediation;
credentials remain unavailable. Mock-only local gates do not widen M0, accept it, or activate `RESET-WO-01`.

## Fable gate

```yaml
fable_gate:
  goal: "Land the exact ratified reset authority and reconcile repository documentation without changing production behavior."
  assumptions:
    - "The repository-retained manifest and covered files reproduce their quoted SHA-256 values; the human-approved complete-archive digest is provenance and is not independently rehashable from this checkout."
    - "master and origin/master remain at the frozen base SHA and all registered worktrees are clean."
    - "ADR-020 through ADR-022, WO-0144, and branch codex/arch-reset-2026-07-r1 are conflict-free across all recorded refs."
  approach: "Preserve packet and ADR bytes exactly; put acceptance and hashes in a separate index; make only bounded status, backlink, and generation-qualification edits."
  out_of_scope:
    - "Any implementation or activation of RESET-WO-01 or a later milestone."
    - "Any schema, SQL, migration, database, application, test, broker, credential, or network execution."
    - "Any push, PR, merge, R6 integration, deletion, cleanup, or legacy artifact removal."
  done_when:
    - "The reset branch parent is the frozen master SHA and R6 remains separate."
    - "The canonical packet and three ADR copies reproduce the ratified hashes."
    - "Required ADR/backlink/index/PKL/overview consistency edits are documentation-only."
    - "Static file, link, scope, and diff checks pass and one local commit is ready for independent review."
  blast_radius: "Documentation and governance only; no production behavior change."
```

Documentation-only exception to Fable red-first: executable behavior is forbidden. Failure-capable
evidence consists of byte/hash comparisons, link existence, allowed-path checks, and Git diff checks.

## Context packet

Read only these first:

1. `AGENTS.md` and `CLAUDE.md`.
2. Ratified packet files `06-roadmap.md`, `10-ratification.md`, `11-first-work-order.md`, and
   `12-proposed-adr-set.md`.
3. Ratified packet file `13-proposed-adr-current-state-kernel.md`.
4. Ratified packet file `14-proposed-adr-protection-execution.md`.
5. Ratified packet file `15-proposed-adr-reset-scope.md`.
6. Existing ADRs `004`, `008`, `009`, `010`, and `013`.
7. `docs/01_ARCHITECTURE.md`, `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md`, and
   `docs/INVARIANTS.md`.
8. PKL architecture, migration, goals, and safety pages named in allowed paths.
9. `.github/workflows/ci.yml` and `pyproject.toml`, read-only, for the Python 3.11/3.12 gate record.

## Allowed paths

```yaml
allowed_paths:
  - work/queue/WO-0144-architecture-reset-m0-documentation-landing.md
  - work/queue/ARCH-RESET-2026-07/**
  - docs/adr/ADR-004-event-log-truth-migration.md
  - docs/adr/ADR-008-order-status-event-provenance.md
  - docs/adr/ADR-009-signal-seat-boundary.md
  - docs/adr/ADR-010-execution-envelope.md
  - docs/adr/ADR-013-external-ingress.md
  - docs/adr/ADR-020-current-state-execution-kernel.md
  - docs/adr/ADR-021-position-protection-liquidity-execution.md
  - docs/adr/ADR-022-reset-beta-scope-cutover-governance.md
  - docs/adr/ARCH-RESET-2026-07-RATIFICATION.md
  - AGENTS.md
  - CLAUDE.md
  - README.md
  - START_HERE.md
  - docs/00_START_HERE.md
  - docs/00_START_HERE_SPINE_UPGRADE.md
  - docs/01_ARCHITECTURE.md
  - docs/02_DATA_AND_PERSISTENCE.md
  - docs/04_IMPLEMENTATION_PLAN.md
  - docs/INVARIANTS.md
  - docs/REARCHITECTURE_ROADMAP.md
  - docs/SPINE_EXECUTION_ARCHITECTURE_v2.md
  - pkl/index.md
  - pkl/project/goals.md
  - pkl/architecture/architecture-map.md
  - pkl/architecture/testing-model.md
  - pkl/architecture/signal-seat.md
  - pkl/process/migration-history.md
  - pkl/safety/invariants-rationale.md
  - pkl/log.md
```

## Forbidden paths and actions

```yaml
forbidden_paths:
  - app/**
  - tests/**
  - cockpit/**
  - harness/**
  - .github/**
  - migrations/**
  - work/ledger.jsonl
  - work/active/**
  - work/completed/**
  - work/review/**
```

- Do not alter any ratified source byte or the preserved R1 archive/manifest.
- Do not execute code, tests, SQL, DDL, a database engine/client/parser/ORM, or broker-facing tools.
- Do not delete, clean up, rename, merge, cherry-pick, push, or create a pull request.

## Required landing

1. Copy the 15 numbered authority documents byte-for-byte into
   `work/queue/ARCH-RESET-2026-07/`; also copy the packet `README.md` and detached manifest as
   non-authoritative navigation/evidence. Do not copy the superseded planning-seat handoff.
2. Copy packet files 13–15 byte-for-byte to:
   - `docs/adr/ADR-020-current-state-execution-kernel.md` — SHA-256
     `35c6782ff7c09ec125b2acad859b4080302660531004db47b8c544b4cf2a5838`;
   - `docs/adr/ADR-021-position-protection-liquidity-execution.md` — SHA-256
     `ca822fe682bc2ccca32b5a7915ea4f07bd4ad2319e62d48312edd12c3f8f44f0`;
   - `docs/adr/ADR-022-reset-beta-scope-cutover-governance.md` — SHA-256
     `93f2c55b77e832687e1d1ac8256f34ad4442b4a4072a8b79c7a1d8294c558798`.
3. Create `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md` as the separate acceptance/index record.
   Record exact manifest/archive/source hashes, frozen master/R6 SHAs, canonical ADR mappings,
   body-status caveat, M0-only boundary, prohibited DDL incident inadmissibility, and later gates.
4. Add narrow reset-disposition backlinks to ADR-004, ADR-008, ADR-009, ADR-010, and ADR-013.
   Preserve every clause retained by the packet matrix; do not imply whole-file supersession.
5. Refresh `AGENTS.md`, `CLAUDE.md`, the named PKL pages, architecture/invariant overviews, and
   root navigation so reset target authority and frozen legacy evidence cannot be confused.
6. Preserve Python 3.11 + 3.12 support, 3.12 development default, and the no-3.12-only-syntax rule.
   Record that `.github/workflows/ci.yml` already has both legs and `pyproject.toml` targets 3.11;
   do not edit either file and do not run the gates in M0.
7. Leave `11-first-work-order.md` byte-exact and staged. Do not assign its future canonical ID,
   replace commands, activate it, or implement it.

## Static verification

- Rehash the repository-retained authority manifest, all 15 manifest-covered files, and all
  canonical ADR copies. Record the human-approved complete-archive digest as provenance, but mark
  its rehash `UNVERIFIED_IN_CHECKOUT` unless the exact archive bytes are in the immutable review
  context.
- Rehash all canonical packet and ADR copies; comparison must be exact.
- Verify every new relative Markdown link resolves and no packet-internal link was rewritten.
- Verify branch parent/base, R6 separation, allowed paths, `git diff --check`, and documentation-only
  file types.
- Compare uppercase bracketed template markers in the frozen M0 Markdown scope against an exact
  path/line/token/multiplicity allowlist. Fail on any unexpected, missing, moved, duplicated, or
  out-of-file marker, packet hash drift, or activation of the staged work order. Separately search
  for accidental activation language, database or implementation completion claims, and
  live/broker authorization.
- Record exact commands and decisive output below. Do not use prohibited executables.

## Stop conditions

Stop without committing if a ratified hash differs; a source byte requires editing; a canonical ADR
number/path conflicts; a required correction needs a forbidden path; the base/worktree is dirty; or
the landing would activate implementation, schema, broker, Paper, live-shadow, or live trading.

## Review gate

The implementation seat may make exactly one local documentation-only commit. It must not review or
accept its own landing. A fresh review seat must inspect the frozen commit, exact diff, byte/hash
identity, backlinks, navigation, PKL consistency, and scope before M0 is accepted or `RESET-WO-01`
receives a canonical ID or activation.

## Evidence and Fable DONE

```yaml
evidence:
  - {command: "SHA-256 recheck of authority manifest, 15 records, and ADR-020..022", result: PASS, decisive_output: "manifest matched; 15 records / 0 mismatches; 3 ADRs / 0 mismatches"}
  - {command: "SHA-256 recheck of complete R1 archive", result: UNVERIFIED_IN_CHECKOUT, decisive_output: "bytes absent from committed review context; approved 51e4bb1a...a053f was not recomputed from checkout"}
  - {command: "Git branch/ref and registered-worktree inspection", result: PASS, decisive_output: "base/R6 exact; identities conflict-free; current tree M0-only; nine linked worktrees clean"}
  - {command: "Allowed-path and document-type scan", result: PASS, decisive_output: "47 paths; 0 outside scope; 0 non-document; 0 delete/rename/copy records"}
  - {command: "Fail-fast relative-link and fence checks", result: PASS, decisive_output: "46 Markdown files; 70 links / 0 broken; 0 unbalanced fences"}
  - {command: "Static PKL frontmatter/source-ref check", result: PASS, decisive_output: "6 changed PKL pages / 0 errors"}
  - {command: "Exact allowlisted uppercase bracket-token scan and git diff --check", result: PASS, decisive_output: "46 files; 21 occurrences / 14 unique; prompt 16, staged WO 5; unexpected/missing/multiplicity/outside/hash errors 0"}
```

```yaml
fable_done:
  task: "Architecture reset M0 documentation landing"
  done_when_results:
    - "Exact packet, manifest, and ADR bodies preserved"
    - "Accepted status, hashes, partial supersession, legacy boundary, and retained gates recorded"
    - "Only authorized documentation paths changed"
    - "RESET-WO-01 remains byte-exact, staged, unnumbered, and inactive"
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence:
    - "Static file/hash/link/scope checks above"
    - "REV-0047 addendum 01 independently returned ACCEPT for remediation target 116822d"
    - "Supplemental Python 3.12 verification forced the broker adapter to mock and is not packet/archive evidence"
  status: CLOSED
```

Repository-retained-byte verification passed; complete-R1-archive rehashing stays `UNVERIFIED_IN_CHECKOUT`.
REV-0047 addendum 01 returned `ACCEPT`; M0 is closed and `RESET-WO-01` remains inactive.
