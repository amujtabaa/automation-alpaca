---
type: Review Result
rev_id: REV-0109
round: 2 of 2 maximum
work_order_id: WO-0168d
reviewer_model: OpenAI Codex independent review seat
review_target_commit: 0b8398531563414bab9f56a44cb2461278134c8a
verdict: BLOCK
date: 2026-08-28
---

# REV-0109 round two — independent findings-only result

## Finding

### [P1] The accepted unlock lifecycle still requires the superseded REV-0108 parent

- Location: `docs/adr/ADR-026-interim-ddl-gate-threat-model.md:79`
- Governing requirement: `AGENTS.md` makes accepted ADRs authoritative and requires architecture
  changes to be approved. The round-two execution plan requires any future flag-only unlock to
  branch from the exact accepted round-two source candidate
  (`work/review/REV-0109/request-r2.md:131`), while preserving the route and catalog remediations in
  `0b8398531563414bab9f56a44cb2461278134c8a`.
- Evidence level: `reproduced-live` for Git identity/diff and source inspection;
  `static-reasoning` for the mutually exclusive future unlock paths.
- Evidence: The candidate amends ADR-026's status and catalog lifecycle, but its exact unlock rule
  still says that a valid unlock must have the REV-0108-accepted candidate as its parent. That
  candidate is `70dc59cb11a8a8f5b9e50c876fb7e5ed0945815c`, whereas the reviewed remediation candidate is
  `0b8398531563414bab9f56a44cb2461278134c8a`. A direct diff confirms that the latter changes
  `schema.py` and three directly relevant test files relative to `70dc59c`; it contains the two
  route triggers and the observed-catalog lifecycle that the old parent lacks. The round-two
  request and remediation manifest instead require a flag-only unlock from the accepted source
  candidate (`request-r2.md:131-136`; `38-REV-0109-R2-DDL-MANIFEST.md:60-61`).
- Concrete impact: No future unlock commit can satisfy both authorities. Parenting the unlock at
  `70dc59c` preserves the old 178,755-byte DDL and omits the accepted remediations; parenting it at
  `0b83985` preserves the remediations but violates the currently accepted ADR's exact-parent rule.
  This leaves a human-gated DDL execution step with conflicting authority and blocks acceptance of
  the proposed lifecycle even though the flag remains closed today.
- Smallest complete resolution: Before any unlock, obtain Ameen's explicit disposition and amend
  the accepted lifecycle authority so the exact parent is the zero-open-P0/P1 remediation source
  candidate named by the later execution approval, while retaining the flag-only diff and all
  identity rechecks. Because this changes the exact reviewed source candidate after REV-0109's
  final round, return the blocker to Ameen rather than silently opening a third REV-0109 packet or
  treating wrapper prose as an ADR override.
- Disproof pass: I checked the later approved Amendment 14, the compact remediation manifest, the
  round-two request, and the packet-only invariant clarification. They consistently anticipate an
  accepted remediation candidate but do not remove or explicitly supersede ADR-026's exact
  REV-0108-parent clause. I also checked whether `70dc59c` and `0b83985` were product-equivalent;
  they are not. The contradiction therefore survives the later-source, ancestry, and equivalence
  disproof attempts.

## Static evidence and disproof pass

- Exact identity recomputation matched every recorded value: repository URL and branch; parent
  `6271f353...` / tree `90bb3901...`; candidate `0b839853...` / tree `834790e5...`; predecessor
  `70dc59cb...` / tree `f5ee0646...`; schema blob `0a42fa50...`; schema file SHA-256
  `94fce06f...`; 180,858-byte DDL and expected digest `75d68e53...`; exact boolean human flag
  `False`; 28 tables, 29 indexes, 150 triggers, zero views; R4/R5 hashes `99aab5f4...` and
  `4e69ea8b...`; remediation-manifest hash `8a1e21fe...`; and unchanged round-one result and
  disposition hashes `d34901ef...` and `2a23fdf6...`.
- Published wrapper verification matched the packet rule. Local HEAD and the local origin tracking
  ref both resolve to `bcecbaf79aeb06e7181cd3531e98893a50f3d646`; `d690cf9` adds only one
  append-only `work/ledger.jsonl` record and `request-r2.md`, and `bcecbaf` changes only that
  request with the invariant-applicability clarification. No product, test, ADR, manifest, or gate
  source differs from `0b839853...` in the wrapper, and tracked state was clean before this result.
- The invariant clarification is consistent with the candidate diff: no `INV-*` entry was added or
  amended, so fresh invariant-probe lines are not applicable. The route-splice held cases probe
  existing FR-6/FR-7 durable-state requirements.
- The round-one route counterexamples are closed statically. Removing the market-route trigger or
  its session comparison makes the separately valid other-session stream case admissible; removing
  the outbox trigger or its scope/acquisition comparison makes the corresponding cross-route case
  admissible. The exact MARKET_OCCURRENCE, scope-wide AUTHORITY, and acquisition-specific CLAIM
  positive paths satisfy the new predicates. Parent/input/outbox immutability and retention guards
  prevent a later coordinate rewrite.
- The catalog lifecycle remains non-authorizing before connection access: the still-False human
  flag, expected exact DDL digest, and caller-approved digest are checked before the installer
  touches its supplied connection. The installer records the observed post-install catalog in an
  immutable metadata row; verification rejects missing/wrong identity, malformed retained digest,
  and current-catalog mismatch by source inspection. Removing the catalog comparison defeats both
  spoof and post-install-mutation held controls, so those controls are failure-capable.
- Attempt two is now textually restricted to an environmental/interruption retry with zero tracked
  changes, a distinct fresh `--basetemp`, clean/local-origin/identity rechecks, and no source, DDL,
  test, fixture, or expectation repair. The open P1 above is the remaining exact-parent authority
  contradiction, not the corrected retry rule.
- Fresh permitted checks: focused no-I/O tests `22 passed`; Ruff check clean; Ruff format check
  clean; mypy clean across 95 source files; import-linter 6 kept/0 broken; ledger check passed;
  candidate and wrapper `git diff --check` passed; and in-memory compilation of the four exact
  committed Python sources passed without import or execution.

## NOT_RUN boundaries

No SQLite connection was opened; no file or in-memory database was created; no DDL was installed
or executed; and nothing under `tests_gated/` was collected, imported, or executed. No migration,
human-flag change, unlock, runtime composition, configured-data access, broker/network/order action,
later work order, promotion, merge, commit, or push occurred. Held files were inspected and compiled
as source only. Database-bearing broader suites remain NOT_RUN.

Verdict: BLOCK

P0: 0

P1: 1

P2: 0

Unverified: SQLite syntax/catalog/runtime constraint behavior and every held-suite outcome, which
the packet expressly forbids this review from executing.
