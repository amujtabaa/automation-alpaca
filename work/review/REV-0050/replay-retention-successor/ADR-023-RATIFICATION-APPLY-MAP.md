# ADR-023 ratification application map

Status: **PLANNING ONLY — DO NOT APPLY BEFORE EXACT HUMAN RATIFICATION**

## Exact precondition

- Branch: `codex/arch-reset-2026-07-r1`
- Pre-ratification HEAD: `488ce0e7cb954d7b1d19c2bc0127a925e069ea58`
- Proposal SHA-256: `898DA71EA959ED8B6F343DA23795E3E52D7DB94D8BAD255FDAC13475CED0F259`
- Proposal final reviews: three independent `ACCEPT`; P0=0/P1=0/P2=0
- Human ratification: absent when this map was written

Reconfirm every hash, HEAD, tracked/staged status, preserved untracked artifact, and the active WO
immediately before applying. A broad implementation instruction is not a substitute for exact
approval of this proposal and its named re-gate.

## Documentation-only ratification wave

### 1. New accepted ADR body

Create `docs/adr/ADR-023-bounded-market-occurrence-authority.md` as a byte-identical copy of
`work/review/REV-0050/replay-retention-successor/PROPOSED-ADR-023-bounded-market-occurrence-authority.md`.
Preserve its embedded proposed-status wording, following ADR-020 through ADR-022; the separate
ratification index records acceptance. The copied file must hash exactly to the proposal SHA above.

### 2. Active WO-0148 amendment

Current file SHA-256:
`0D79DC7B4FD01E12B50F60DE8886AED17021DB3F4208924E4033A2EB20CB49FF`.

- Add `docs/adr/ADR-023-bounded-market-occurrence-authority.md` to `allowed_paths`.
- Append a new ratified ADR-023 re-gate after the historical receipt-map successor section. Preserve
  every prior freeze/review/evidence entry as history; do not rewrite it into apparent acceptance.
- Prospectively supersede current market-evidence/replay clauses only where ADR-023 changes source
  generation/mode, occurrence identity, bounded cursor, replay/conflict/epoch classification,
  invalidation/baseline/restart, u64 exhaustion, or split reducers.
- Replace the current RED public-contract pin with exact additions:
  `MarketStreamGenerationId`; `MarketSequenceMode(SEQUENCED, SOURCE_TIME)`;
  `ProtectionAlert(LATE_POSITIVE_AFTER_FLAT, MARKET_BASELINE_REQUIRED,
  MARKET_COORDINATE_EXHAUSTED)`; ADR-023's exact `EvidencePolicy` and derived-ID
  `MarketOccurrence`; and exactly five entry points:
  `project_protection_venue`, `initialize_position_protection`,
  `reduce_position_protection`, `reduce_position_protection_market`, and
  `invalidate_position_protection_market`.
- State that ADR-023 supersedes ADR-021 lines 120–126 only for occurrence distinctness, aggregate
  identity retention, and replay/restart classification. Preserve every other ADR-021 formula,
  trigger, trail, guard, fill-truth, execution, and safety rule.
- Bar application edits until the replacement RED candidate receives independent exact-commit
  `ACCEPT` with zero P0/P1.

### 3. Append-only ratification addendum

Current `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md` SHA-256:
`9A6715AEA0E6BB386D0D2294E837F286A44937D0893486097E911BCD6DC6ADB8`.

Append one ADR-023 amendment section recording the exact approved hash, narrow ADR-021 partial
supersession, exact WO-0148 re-gate, RED-before-implementation condition, and retained prohibitions.
Do not rewrite the ADR-020–022 table/history, R1 manifest/archive provenance, DDL incident, or prior
activation entries.

### 4. Matching PKL reconciliation

- `pkl/project/goals.md`, current SHA-256
  `2BEA3312A6F38F226D78B4C64731FFC75687D530068947A72548F19177274806`: add ADR-023 to
  `source_refs`, refresh `last_verified`, and append a short authority/current-gate entry.
- `pkl/architecture/architecture-map.md`, current SHA-256
  `AE85F934901A35869D3344FF645572E3D7CBF3B14CF8272ADDC7B12FC3EB5B39`: add ADR-023 to
  `source_refs`, refresh `last_verified`, and append the bounded global-cursor/split-reducer rule
  while retaining the pure, unwired M1 boundary.
- `pkl/log.md`, current SHA-256
  `AECEFB36C83ABE94606374837224C860CDFBC31E4B418D848FDE796C5D946EC8`: append only the
  ratification/re-gate event.

## Explicitly unchanged in this wave

- `docs/adr/ADR-020-current-state-execution-kernel.md`
- `docs/adr/ADR-021-position-protection-liquidity-execution.md` (current accepted SHA-256
  `CA822FE682BC2CCCA32B5A7915EA4F07BD4AD2319E62D48312EDD12C3F8F44F0`)
- `docs/adr/ADR-022-reset-beta-scope-cutover-governance.md`
- `README.md`, `docs/04_IMPLEMENTATION_PLAN.md`, and `work/ledger.jsonl`
- architecture-reset packet files, historical review/evidence, retirement inventory, production
  source, tests, worktrees, and untracked artifacts

README/implementation-plan edits remain closeout-only. The ledger has no new lifecycle event while
WO-0148 remains active. No production/test edit belongs in the ratification wave.

## File-level verification after ratification application

1. Rehash the new ADR and require exact equality with the proposal hash.
2. Confirm the changed path set is exactly the new ADR, ratification index, active WO, and three PKL
   records.
3. Run `git diff --check`.
4. Feed the exact pre-ratification-HEAD-to-candidate changed paths to
   `.ai-os/scripts/check_work_order_scope.py` with the active WO; require `SCOPE CHECK PASSED`.
5. Run `.ai-os/scripts/check_pkl.py pkl`, `.ai-os/scripts/check_ledger.py`, and
   `.ai-os/scripts/check_work_order_disposition.py`; all must pass without a ledger edit.
6. Reconfirm accepted ADR-020/021/022 hashes and all registered worktrees unchanged.
7. Freeze the documentation re-gate before any RED edit; record exact file hashes and next gate.

## Next gate after the documentation wave

Create the replacement failure-first controls described in `ADR-023-RED-IMPLEMENTATION-MAP.md`
with production unchanged. Obtain a fresh independent exact-commit `ACCEPT` with zero P0/P1 before
editing `identity.py`, `protection.py`, or package exports. Runtime recovery-fence proof remains M2
and cannot be claimed by WO-0148.
