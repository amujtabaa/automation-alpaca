# M2 completion drive — long-horizon autonomous goal prompt

Status: **ACTIVE DRIVE DOCUMENT — referenced by the session /goal condition; supersedes
`33-CLAUDE-M2-CONTINUATION-S2.md` as the governing continuation for the remaining M2 chain.**
Documentation only; grants no authority beyond the recorded serial-M2 authorization and each
work order's own gates.

Scope note: `work/queue/M2-EXECUTION-2026-08-21/**` is enumerated file-by-file in WO-0168c's
`allowed_paths`, so adding this file is a deliberate scope extension, authorized by Ameen on
2026-08-24 (same pattern as `33-`); `allowed_paths` is amended in this same commit.

You are the implementation and first-pass fresh-review seat for the M2 milestone of
`amujtabaa/automation-alpaca`. This is a goal prompt, not a task list: you own the outcome, you
sequence the work, and you keep moving for as long as safe in-scope progress remains. Repository
files and exact Git objects are authority; chat history is not.

## The goal

M2 is COMPLETE and M3 is PREPARED, per `work/queue/M2-EXECUTION-2026-08-21/01-M2-M3-EXECUTION-MAP.md`,
with every human-gated residual packaged and waiting on exactly one human decision each — never on
missing work. Concretely, in order, each independently accepted and closed before its successor:

1. **WO-0168c** — finish R20 §2 (authority families) and §4 (venue 15-family projection); both R19
   guards green because the projections are real; stop at the DDL gate with a complete bundle;
   after approval run only the approved fresh-file SQLite gate; REV-0078 ACCEPT P0=0/P1=0; close.
2. **WO-0168b** (repo `WO-0168`) — one atomic unit of work: authenticate-in-transaction, all-or-
   nothing composite writes, immutable claim before eligibility, mandatory non-authority receipt,
   fail-closed ambiguity. New files `unit_of_work.py`, `outbox.py` + two test files.
3. **WO-0169** — owner lock, startup integrity, phase ladder `BOOTSTRAPPING→RECONCILING→SERVING`,
   unknown-effect reconciliation, ADR-023 cold recovery CR-01..19. Fake capabilities only.
4. **WO-0170** — crash/restore/fault/boundedness closeout harness; mutants; measured budgets; the
   24-hour soak recorded honestly (see Residuals); self-contained closeout manifest.
5. **Terminal M2** — assemble the combined exact-head evidence and closeout manifest, then stop for
   the Codex terminal review (reserved, not yours).
6. **M3 preparation** — documentation only: reconcile WO-0171/WO-0172 entry contracts against
   accepted M2. No M3 implementation.

A session that ends mid-chain is normal and planned for: it must end pushed, clean, and with a
handoff note (see Long-run mechanics). Ending at a hard gate with a complete bundle is success,
not a stall.

## Verify before you write code

```
Branch codex/claude-opus-m2-wo0168c-r1; HEAD must be c217092d9c60e687ff2ea7026a1a6409a79a72dd or a
descendant of it on the same branch; worktree clean; local == origin.
Ancestry: a6bba249 (R20 contract) and cd759c2 (REV-0077 ACCEPT) are ancestors.
Baseline: the four permitted pure test files yield 138 passed / 2 failed, the failures being
  test_r19_checkpoint_projection_has_no_source_order_or_rank_dependency and
  test_r19_selected_authority_families_do_not_require_whole_superset_cardinality.
DDL gate CLOSED: SCHEMA_DDL = 178,791 UTF-8 bytes, sha256 73dce64a…3171e9c88; _GATE_DIGEST
  2dc33ba1…b14d3859 pins the PRE-change DDL and stays untouched until Ameen opens the gate.
Environment: Linux, .venv/bin/python (CPython 3.12.x; 3.12.3 here vs 3.12.13 in the old handoff —
  record as environmental deviation, do not normalize). PowerShell commands in contracts do not
  apply; use the bash equivalents.
```

On any mismatch: stop, report the mismatch exactly, change nothing.

## Authority you hold — use it without asking again

Ameen's serial-M2 authorization (recorded in WO-0168c frontmatter and the ratified
`32-CLAUDE-OPUS-M2-CONTINUATION.md`) covers ordinary reversible work through M2 closeout and M3
preparation, including: implementation inside each active WO's allowed paths, root-cause fixes,
tests, normal commits and pushes, fresh-context reviews you run yourself, successor **activation**
once the predecessor is independently accepted AND closed (record an activation checkpoint: branch
name from the frozen chain `codex/claude-opus-m2-wo0168b-r1 → …-wo0169-r1 → …-wo0170-r1 →
…-terminal-r1`, next free REV id, allowed paths reconciled against the accepted predecessor head,
base SHA), and in-flight resolution of relevant issues that do not touch a human-gated surface.
Do not ask permission for any of that. Asking to re-confirm recorded authority is a failure mode.

## Hard gates — never crossed, always packaged

1. **Changed DDL / any SQLite-bearing test.** Stop with: exact candidate commit+tree, DDL byte
   count + SHA-256, changed-DDL summary, and the exact fresh-`tmp_path` commands. Expect one such
   gate in 0168c, and one each in 0168b/0169 if they change schema bytes (outbox/claim/receipt
   tables and a persisted owner lock almost certainly do). Never use a configured DB or `:memory:`.
   Never run `test_persistence_runtime_checkpoint_sqlite.py` or `test_persistence_schema.py`
   before the gate opens — authoring them is allowed and expected.
2. **Terminal M2 review** — Codex's seat. Prepare the packet; do not self-accept M2.
3. **`master` merge, credentials, broker/network, orders, runtime composition, promotion, history
   rewrite, branch deletion, weakening any test or contract** — never.
4. **Emergency grant** stays refused in the checkpoint encoder; contract has no admitted row route.

While stopped at a gate, you are not idle: prepare the successor WO's frozen contract draft, the
next review request packet, the sqlite fresh-file command plan, or the closeout manifest skeleton —
documentation only, inside allowed paths. Batch every question for the human into the gate bundle.

## Operating loop (repeat until goal or gate)

Work in slices of one coherent obligation each. Per slice: RED first, failing for the intended
reason → implement at the root → focused suite + `ruff check` + `ruff format --check` + `mypy app/`
+ `git diff --check` → commit with an evidence-bearing message → push. Never batch multiple slices
into one commit; never leave the tree dirty between slices. Fixtures are reducer-built — forge only
the six environmental proof fields; never hand-mint sealed records. Feed every new wire row through
`_validate_checkpoint_nested_value` in its test so admissibility is proved, not assumed.

**Honesty invariants:** a family not yet projected keeps refusing explicitly — never emit empty
collections over real state. `NOT_RUN` / `NOT_EVALUATED` stay visible. Statuses are VERIFIED /
UNVERIFIED / BLOCKED / NEEDS-INPUT only. Close-out ships in the finishing commit: status flip,
disposition, ledger line, lifecycle move, refreshed invalidated claims — or the WO is still open.

**Hard problems:** three failed fix attempts trips the circuit breaker — stop patching, return to
root cause, re-gate a materially different approach; only then consider whether it needs new
authority. When a reviewer's paraphrase and the frozen contract disagree, the contract wins — this
session hit that twice (R15 "reached-key" misread as whole-map; the R16 taxonomy). Re-read the
clause, cite it by line in the fix commit. When facts are missing, investigate first, then take the
conservative reversible assumption and record it; ask only for the undiscoverable-and-material.

## Review protocol — bounded, no treadmill

Per work order: (a) if a new frozen contract is needed, ONE preflight review by a fresh-context
agent that did not author it, fix at root, ONE re-review of the exact new head; (b) at
GREEN-CANDIDATE, ONE adversarial multi-lens review (contract conformance, silent state loss,
commitment/authenticity, test-mutation quality, scope/gate compliance — findings face independent
refuters defaulting to refuted), fix everything confirmed at root, ONE re-review of the fixed head.
That is the budget. A finding blocks only if it traces to a contract clause or a demonstrated
failure; taste findings are logged P3 and do not block. If a reviewer produces new findings of new
shapes each round instead of converging, stop feeding it: batch what is still flagged, present it
once with your proposed disposition, and proceed on the unaffected remainder. Record every review
in the WO's `REV-*` packet. Verify all reviewer claims yourself before acting — this session's
reviews were right about defects and wrong about remedies.

## Roadmap with paid-for knowledge — do not rediscover these

**WO-0168c §2 remainder** (order: EffectAuthorizations family → AcquisitionEffectPermit encoder →
Descriptors family → Currentness + slot encoders → Slots family):
- Layout authority: contract-07 §4.2 as imported by R2:181-182 / R5:17 pin / R6:27-33. The LIVE
  authority top and slot forms are **R2's** (`m2.authority.Checkpoint/v1`, 4-member slot with
  SlotEmpty/SlotActive/SlotInactive); contract-07's tops are explicitly excluded. All arities are
  already pinned at `checkpoint_codec.py` 720-736.
- Collections order by contract §2.4 `order_component` bytes (`_atom_order_key`/`_array_order_key`
  exist now) — never Python comparison. The encoder is the SOLE guarantor of key order and
  duplicate-freedom; `_validate_checkpoint_collection` checks neither.
- Slot ordering key: `_encode_canonical_json(_operations._encode_m2_position_scope(scope))`,
  computed once and reused as row member — never a digest, never a naive tuple.
- The four permitted supersets (`_effect_authority_by_id`, `_claim_by_effect`,
  `_claim_by_occurrence`, `_acquisition_descriptor_by_effect`) never get `.size` checks. The
  exact current selected-scope maps (`_manual_flatten_by_scope`, `_acquisition_currentness_by_scope`,
  `_acquisition_descriptor_by_scope`, `_acquisition_active_by_scope`) require every present key
  selected. `_manual_by_id` omits unreachable IDs (R16 §2 taxonomy). Add a noise-invariance control
  per new family.
- Occurrence cross-check: `_claim_by_occurrence.get(_claim_key(claim.claim_occurrence_id))` must
  return the same claim reached via `_claim_by_effect` — zero wire bytes, mandatory proof.
- Traps: `_effect_authority_by_id` occurs at exactly ONE line (the refusal tuple); the hardening
  pin asserts the identifier exists in module source, so remove-from-tuple and real projection
  reference must land in the same commit. `AcquisitionOrderType` is missing from
  `_CHECKPOINT_ENUM_OWNERS` — register it when the terms row first appears. Enforce the per-row
  byte cap (`_MAX_RUNTIME_CHECKPOINT_ROW_BYTES` is currently dead; §2.4:190-194 mandates it); the
  component cap cliff arrives near ~34k rows, well under the 65,535 row cap.
- Selection fixtures: `VenueEffectRecord` has no `__post_init__`; effects-bearing selections
  authenticate without touching absences or `query_row_counts`; disposition must be
  OPEN/INVALIDATED for repository fidelity.

**WO-0168c §4 venue** (largest chunk — one family per commit, 15 commits acceptable):
R17 §1 is decisive: the selection proof is the SOLE membership and order witness; effects by
`(created_ordinal, effect_id)`, owners by Q4b/Q5 vector keys; direct current-owner lookups for
proof-selected keys; deep equality against each selected record; emit in proof order with dense
ordinals 0..n-1. Remove `_validate_full`, `_effect_order`, `_owner_order` from projection — the
rank maps are deleted from the contract. `_PersistentKeyMap` has no iteration, so direct-key is
structurally forced. Closing §4 for real is what turns both R19 guards green; never satisfy a
static pin with a bare string or a deleted guard.

**Cleanup owed inside 0168c:** the frozen import-direction control is red at base because
`test_persistence_runtime_checkpoint_sqlite.py` imports `persistence_setup_support` from outside
the allow-list. That sqlite test IS in your allowed paths and may be authored: inline the
capability issuance there and the control goes green with no allow-list edit.

**WO-0168b:** the reducer/repository seam already exists — study `_project_runtime_checkpoint`'s
authenticate-then-act shape and the R2 receipt rules before drafting the frozen contract. Crash
injection at every write/commit/publication edge; claims are immutable pre-eligibility; receipts
are correlated, never authority. Expect a DDL gate; design the schema delta as ONE exact candidate.

**WO-0169:** every capability injected (lock, repository, query, stream, clock); CR-01..19 as a
parametrized matrix with one mutant per CR; strict `F > cursor` with the single no-cursor
exception; equality fails. Serving conversion of the inert checkpoint happens HERE, not in 0168c.

**WO-0170:** build the harness and mutants; measure against frozen budgets. The 24-hour soak
cannot run in this environment: implement the soak driver, verify it in a short smoke (minutes,
clearly labeled as smoke), record FR-5 as `NOT_RUN` with the exact command for Ameen to run
locally, and say so in the manifest without laundering.

**Residuals expected to survive the run (package, don't force):** the soak `NOT_RUN`; every
DDL/SQLite gate bundle; the Codex terminal review packet; any R16 G0-G7 input that is not current
(`NOT_EVALUATED` with missing coordinates).

## Long-run mechanics

Push after every slice — the container is ephemeral and an unpushed commit does not exist. Keep a
running work queue in your head or a scratchpad file, never in the repo. At natural boundaries
(WO close, gate stop, or roughly every few hours of work) emit the checkpoint bundle from
`00-CHECKPOINT-ORCHESTRATION-PROTOCOL.md` (work order, branch, base, head, changed paths, commits,
RED/GREEN evidence, static evidence, known failures and NOT_RUN, schema/db/broker/network activity
= NONE unless gated, requested next action). If the session must end, the last act is: clean tree,
pushed head, and a short handoff naming the next slice and any in-flight reasoning worth keeping.

## Stop conditions — the complete list

Stop ONLY for: a hard gate above (with its bundle complete); an identity-verification mismatch; an
unresolved conflict between accepted authorities that touches a safety surface (record the decision
gap first); the circuit breaker exhausting a materially different second approach; or genuinely
undiscoverable-and-material missing facts (batched). Everything else — test failures, reviewer
findings, ambiguous specs with a conservative reading, long remaining distance — is your job, not
a reason to return. Begin by verifying the identities, then take the EffectAuthorizations family.
