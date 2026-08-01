# Architecture reset ratification index — ARCH-RESET-2026-07-R1

## Status

**Accepted as architecture authority; M0 documentation landing independently accepted.** This
index records Ameen's 2026-07-31 approval of the unchanged R1 authority unit. It does not activate implementation,
`RESET-WO-01`, DDL/schema execution, a database, broker access, credentials, Paper activity,
live-shadow, live trading, deletion, cleanup, push, pull request, or merge.

The three canonical ADR bodies below remain byte-for-byte copies of their ratified proposed texts.
Their embedded `Proposed` sentences are preserved deliberately; this separate index records their
accepted status without changing a ratified byte.

## Detached authority identity

- Authority manifest SHA-256:
  `c81e49ac3b36d7d99f0974cf34f2f89330e3336eea5877341f3b170aec1a2258`
- Human-approved complete R1 archive SHA-256:
  `51e4bb1a7ce0c00f16cce57c0fa6f15aad33773f0c62ea57d637b55e8eba053f`.
  This digest is approval provenance. The archive bytes are not retained in this repository and
  cannot be independently rehashed from a clean checkout.
- Frozen reset base: `master@6d5937492788aa0ab1cf8348321fa01ee57df920`
- Frozen R6 evidence only: `codex/signal-r6a-rails-store@39a6ed8b9a7562f61afc9ec5c0f9fad2c3918c80`
- Canonical packet copy: `work/queue/ARCH-RESET-2026-07/`

The R6 branch is evidence and a regression corpus. It is not merged, broadly cherry-picked, or
treated as target authority.

## Canonical accepted ADR mapping

ADR-014 through ADR-016 are already occupied by different accepted decisions on the frozen R6
evidence branch at `39a6ed8b9a7562f61afc9ec5c0f9fad2c3918c80`. ADR-017 through ADR-019 are
reserved as draft gate identities on recorded ref
`origin/claude/wargame-roadmap-kickoff-2v2tan@fb6e93e556e94c3c5904b9218d530865c0f3a84b`.
The first three globally conflict-free canonical identities are therefore ADR-020 through ADR-022.

| Canonical ADR | Ratified source | SHA-256 of unchanged body | Disposition |
|---|---|---|---|
| [ADR-020 — Current-state execution kernel and audit separation](ADR-020-current-state-execution-kernel.md) | `13-proposed-adr-current-state-kernel.md` | `35c6782ff7c09ec125b2acad859b4080302660531004db47b8c544b4cf2a5838` | Accepted by exact-digest approval; implementation deferred |
| [ADR-021 — Position protection and side-symmetric liquidity execution](ADR-021-position-protection-liquidity-execution.md) | `14-proposed-adr-protection-execution.md` | `ca822fe682bc2ccca32b5a7915ea4f07bd4ad2319e62d48312edd12c3f8f44f0` | Accepted by exact-digest approval; implementation deferred |
| [ADR-022 — Reset beta scope, cutover, and development governance](ADR-022-reset-beta-scope-cutover-governance.md) | `15-proposed-adr-reset-scope.md` | `93f2c55b77e832687e1d1ac8256f34ad4442b4a4072a8b79c7a1d8294c558798` | Accepted by exact-digest approval; implementation deferred |

The complete clause-by-clause disposition remains the unchanged
[`12-proposed-adr-set.md`](../../work/queue/ARCH-RESET-2026-07/12-proposed-adr-set.md).
Preserved clauses in ADR-001 through ADR-013 remain binding. Partial supersession is explicit in
that matrix and in backlinks added to ADR-004, ADR-008, ADR-009, ADR-010, and ADR-013; nothing is
superseded merely because the new authority is aggregated differently.

## Runtime and cutover record

- Python 3.11 and 3.12 are supported; Python 3.12 is the development default; production code may
  not require 3.12-only syntax. The reset base already carries both CI interpreter legs and a
  Python-3.11 static target. M0 records that fact but runs no code or tests.
- SQLite is the sole reset-beta production persistence implementation. The existing SQLite and
  in-memory implementations remain read-only evidence until separately authorized cutover work;
  neither is migrated or executed by M0.
- ADR-022 requires a cross-generation Alpaca/Paper/account/origin/credential fence at future
  cutover. M0 neither implements nor verifies that fence and grants or activates neither generation.
- Signal Seat is disabled and unmounted for the reset beta. ADR-009's untrusted-advisor principle
  remains preserved for any separately authorized future reintroduction.

## DDL incident provenance

During the first partial R1 packet pass, a delegated pass executed proposed DDL against an
in-memory SQLite database, exceeding the explicit prohibition. No persistent database or
database-like artifact was found, repository and worktree state remained clean, and work stopped
when the incident was discovered. That result is inadmissible as evidence of validity,
executability, migration safety, or operational correctness. No R1 or M0 conclusion relies on it;
schema execution remains a separately authorized future M2 gate.

## Retained gates

1. REV-0047 initially returned `BLOCK`; remediation target `116822d` corrected all three findings,
   and reviewer-owned addendum 01 returned `ACCEPT`. The M0 independent-review gate is satisfied.
2. `RESET-WO-01` remains the unchanged staged packet document. It receives no canonical `WO-NNNN`
   identity and no activation until the dual-version CI gate passes and Ameen explicitly authorizes it.
3. No outbound Alpaca Paper call or credential use is authorized.
4. No broker-native replace/RTH handoff, legacy deletion, cleanup, or promotion beyond
   Paper/live-shadow is authorized.
