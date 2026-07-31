# Consolidated ratification — R1

Status: **PROPOSED — not human-ratified.**

Review label: **ADVERSARIAL PLANNING-SEAT REVIEW—NOT AN INDEPENDENT EXTERNAL AUDIT**.

Human approval of the detached authority identity described below authorizes only the M0
documentation landing. The first implementation work order requires a later activation after M0
proves that the exact canonical ADR text, backlinks, consistency refresh, and review disposition
landed unchanged. No packet text, manifest, archive, plan, or review result is execution authority.

## Decision block

- [ ] **RESET-D1 — freeze and branch.** Freeze
  `master@6d5937492788aa0ab1cf8348321fa01ee57df920` and preserve the R6 branch as evidence; do
  not merge R6. Create a new reset branch from master only under a later authorized M0 landing.
- [ ] **RESET-D2 — modular monolith.** Adopt one sequenced writer, one pure transition kernel,
  fast/slow path separation, and no microservices or new runtime language.
- [ ] **RESET-D3 — authority.** Current transactional state governs live decisions. Immutable
  execution facts (`FILL`, broker-authoritative `TRADE_CORRECT`, and broker-authoritative
  `TRADE_BUST`), dispatch-claim facts, effect closure/invalidation records, venue owners, and
  terminal closures enforce economic identity, dedupe, and ownership. Audit and replay are
  evidence/testing, not full-history live truth.
- [x] **RESET-D4 — clean datastore (already decided by Ameen).** Old SQLite databases and event
  logs need not remain directly usable. Archive them read-only and create a new schema/database.
- [ ] **RESET-D5 — one production store.** SQLite is the sole beta persistence implementation.
  Tests use the pure reference model and only a thin repository harness, not a second hand-coded
  memory trading engine.
- [ ] **RESET-D6 — hard-bail semantics.** The immutable protection mandate authorizes the
  hard-bail loss/reference derivation rule and exact-arithmetic/upward-valid-tick conversion;
  mutable protection state stores the derived, monotone-tightening
  `armed_hard_bail_trigger_price`. That price is an escalation trigger, not a minimum order/fill
  price. Favorable activation uses the same exact-then-upward conversion; execution
  price/slippage guards are separate. Tick/scale incompatibility may withhold formula authority but
  never reject, clamp, or delay an authoritative broker execution fact.
- [ ] **RESET-D7 — domain baseline.** Adopt the state machines, hybrid-trail formula, distinct
  trigger corroboration, BUY/SELL separation, executor stages, and paper calibration defaults in
  `03-domain-specification.md`.
- [ ] **RESET-D8 — beta scope.** Alpaca Paper, one account, a small symbol count, and manual
  acquisition/protection approval. Signal Seat remains disabled and unmounted; defer R6 producer
  machinery and other broker adapters.
- [ ] **RESET-D9 — borrowing.** Borrow contracts/tests/patterns as listed in
  `05-borrowing-plan.md`; do not adopt a surveyed runtime wholesale in the foundation.
- [ ] **RESET-D10 — process.** Adopt the clarification batching, work-order scope, fresh blind
  review, and design/build/patch stop-loss rules in `08-delivery-process.md`.
- [ ] **RESET-D11 — staffing.** Use Codex/Claude for the reset. Do not hire a broad freelancer
  now; reconsider only for a later capped specialist deliverable.
- [ ] **RESET-D12 — authorization boundary.** Approval authorizes M0 documentation landing only.
  Specifically, after exact digest approval it authorizes creation/switching of the local reset
  branch from frozen master, the exact documentation/ADR/backlink/index consistency edits defined
  by M0, and one local documentation-only commit for review. It stages but does not activate
  `11-first-work-order.md`. It does not authorize a push, pull request, merge to master, code or
  test implementation, broker call, credential use, schema execution, legacy deletion, or any
  Paper, live-shadow, or live-trading activity. Before that external digest approval, no branch or
  repository mutation is authorized.
- [ ] **RESET-D13 — future schema shape.** Approve the exact generation-1 DDL proposed in
  `04-persistence-and-cutover.md` for later M2 implementation. This records the schema decision
  now but does not activate M2 or execute the DDL.
- [ ] **RESET-D14 — detached authority binding.** The ratification unit is the exact bytes of all
  fifteen numbered documents, `01` through `15`, including this document. A detached manifest
  records their exact relative paths and SHA-256 identities. Human approval must quote both the
  detached-manifest SHA-256 and the complete R1 archive SHA-256. The approval record stays outside
  the packet and archive authority unit. Any later byte change invalidates that approval.
- [x] **RESET-D15 — Python runtime contract (already decided by Ameen as D-7(a), 2026-07-29).**
  Python 3.11 and 3.12 are both supported; Python 3.12 is the development default; 3.12-only syntax
  is prohibited. M0 must preserve this decision and verify that the reset branch carries an
  enforceable Python-3.11 syntax gate and both CI interpreter legs before any implementation work
  order is activated. The R6 branch records this human decision as evidence; R6 code does not
  become target authority. Durable ruling evidence is
  `codex/signal-r6a-rails-store@39a6ed8b9a7562f61afc9ec5c0f9fad2c3918c80` at
  `work/queue/R6A-CONSOLIDATION-PROGRAM.md` §1 D-7, corroborated by
  `work/active/SIGNAL-R6aR-STATE.md`.

## Detached authority manifest

`AUTHORITY-MANIFEST.sha256` is stored at the R1 archive top level, beside the packet directory. It
is generated only after all fifteen numbered documents are final.

Its canonical representation is:

1. exactly fifteen records, one for each numbered document `01` through `15`;
2. each record is `<64 lowercase hexadecimal SHA-256 characters><two ASCII spaces><relative path>`;
3. relative paths start with `ARCH-RESET-2026-07/`, use `/`, and preserve exact case;
4. records are in ordinal lexicographic order by the UTF-8 bytes of the complete relative path;
5. the manifest is UTF-8 without BOM, uses LF (`0A`) line endings, and has one terminal LF;
6. it contains no header, blank line, comment, placeholder, or path outside the numbered unit;
7. it does not hash itself.

`README.md`, `AUTHORITY-MANIFEST.sha256`, and `PLANNING-SEAT-HANDOFF.md` are not numbered
authority documents. The manifest is the detached identity index whose own hash is quoted by the
human approval. `README.md` is navigation. `PLANNING-SEAT-HANDOFF.md` is retained only as
superseded historical context.

Neither this document nor any other manifest-covered document embeds the final manifest hash or
archive hash. The final values exist only in the separately preserved R1 evidence record and the
later human approval record, preventing a digest cycle.

## R1 authorization and provenance

R1 is a packet-artifact amendment only. Its source is the preserved original archive
`Automation-Alpaca-Architecture-Reset-Handoff-2026-07.zip`, whose authorized recovery control
requires SHA-256
`633ecfbc05942f5a906336c471233317f1c7af4a8e09970c5c4f0bb499ddefb5`. R1 creates no repository,
branch, worktree, database, broker, Paper, implementation, M0, or work-order authority by itself;
only the later external exact-digest approval can grant the bounded D12 M0 documentation actions.

During the first partial R1 pass, a delegated pass executed the proposed DDL against an in-memory
SQLite database. That exceeded the explicit prohibition. No persistent database or database-like
artifact was found; the main repository and all ten registered worktrees remained clean; and work
stopped immediately after discovery. The execution result is inadmissible as evidence that the
schema is valid, executable, migration-safe, or operationally correct. R1 accepts no conclusion
from it. Schema conclusions in this packet are limited to static clause comparison, relational
invariant reasoning, and focused counterexamples; actual schema execution and repository behavior
remain future M2 gates under separate authorization.

## R1 amendment closure map

The table records where each accepted disposition is addressed. Closure is earned only by the
separate static R1 evidence record and final hash/archive verification; this table is not itself a
review pass.

| Amendment | Finding(s) addressed | Authority location |
|---|---|---|
| PA-01 | AR-01 | RESET-D14, manifest procedure, placeholder approval wording |
| PA-02 | AR-02 | Occurrence-level `OPEN|CLOSED|INVALIDATED`, immutable claim absence, generation-bound client identity, exact owner scope, and execution gate |
| PA-03 | AR-03 | Cross-generation Alpaca/Paper/account/origin/credential activation fence and post-effect rollback prohibition |
| PA-04 | AR-04 | Immutable linked fill/correction/bust economic facts and unified chain |
| PA-05 | AR-05 | Active-leg checkpoint plus immutable terminal-closure ledger |
| PA-06 | AR-06 through AR-09 | Distinct trigger observations, formula authority, policy-preserving BUY wait, protected late-fill recovery |

## Approval wording

After focused adversarial planning-seat verification and final file-level packaging checks
substitute both lowercase digests, Ameen may approve the unchanged R1 unit with exactly:

```text
Approve ARCH-RESET-2026-07-R1 authority manifest SHA-256 <MANIFEST_SHA256> and archive SHA-256 <ARCHIVE_SHA256>; authorize the M0 documentation landing only; authorize nothing else.
```

The placeholders are procedural text, not approval. A missing, mismatched, edited, or
non-reproducible digest returns the packet to the planning seat. No current packet byte authorizes
M0 or implementation.

## Gates deliberately retained

The following cannot be pre-authorized honestly:

1. Activation of the first implementation work order after M0 landing evidence.
2. First outbound Alpaca Paper call or credential use.
3. Broker-native replace or RTH protection handoff after paper traces exist.
4. Deletion of legacy code, tests, databases, logs, or historical evidence.
5. Any promotion beyond paper/live-shadow.

They are batched at milestone boundaries rather than raised during ordinary implementation.
