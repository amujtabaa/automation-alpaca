# Automation Alpaca architecture reset — R1

Status: **PROPOSED — R1 amendment and focused review complete only when the separately recorded
manifest/archive evidence verifies; no M0 landing or implementation is authorized by this
packet.**

Review label: **ADVERSARIAL PLANNING-SEAT REVIEW—NOT AN INDEPENDENT EXTERNAL AUDIT**. A third R1
review seat is not required. The DDL-incident provenance and its inadmissible-evidence rule are
recorded in [10-ratification.md](10-ratification.md).

Prepared from:

- `master@6d5937492788aa0ab1cf8348321fa01ee57df920`;
- the unresolved R6 evidence branch
  `codex/signal-r6a-rails-store@39a6ed8b9a7562f61afc9ec5c0f9fad2c3918c80`;
- Ameen's operator-ratified D-7(a) runtime decision recorded on that evidence branch: Python 3.11
  and 3.12 supported, 3.12 the development default, and 3.12-only syntax prohibited;
- the two July 2026 historical research reports supplied by Ameen;
- current primary documentation and source material for NautilusTrader, LEAN, Barter-rs,
  Exchange Core, Hypothesis, Lumibot, CppTrader, Vibe-Trading, and
  `cedwies/low-latency-trading`.

## Outcome

Pause the current implementation campaign and replace its operational core with a bounded
side-by-side architecture:

1. One sequenced, event-driven command lane.
2. One pure transition kernel.
3. One production persistence implementation: SQLite.
4. Transactional current state plus a broker-effect outbox.
5. An append-only audit trail that explains decisions but is not folded on the live path.
6. A broker-neutral `PositionProtectionSupervisor`.
7. One side-symmetric liquidity executor used by BUY acquisition and SELL liquidation.
8. Alpaca Paper only until the revised promotion gates are passed.
9. Signal Seat disabled and removed from execution startup until the protection beta is proved.
10. One process owner plus a committed bootstrap/reconciliation/serving fence.
11. One-to-many concrete broker acceptances and human-attested recovery kept explicit.
12. Occurrence-level `OPEN|CLOSED|INVALIDATED`, immutable claim facts, and generation-bound client/
    owner identity before successor work.
13. Immutable broker fill corrections/busts and a bounded active-leg checkpoint.
14. A cross-generation Alpaca/Paper/account/origin/credential activation fence that legacy or live
    launch paths cannot bypass.

This is a controlled replacement of the semantic center, not a wholesale rewrite. Existing
broker, protection, reconciliation, simulator, recorder, and sell-policy work becomes a source
corpus. Existing store/event choreography does not become the new foundation.

## Non-negotiable correction

The revised model separates:

- `hard_bail_trigger_price`: the price observation that activates emergency escalation; and
- `execution_price_guard`: the independent limit/slippage authority for a child order.

The hard-bail trigger is **not** a minimum allowed order or fill price. In a falling market,
authorized SELL limits and actual fills may be below it. This explicitly supersedes the
incompatible “absolute floor price” meaning in ADR-010 and `app/sellside/policy.py`.

## How to use this packet

| Need | Read |
|---|---|
| Why reset instead of patch | [01-evidence-and-disposition.md](01-evidence-and-disposition.md) |
| Components and truth ownership | [02-target-architecture.md](02-target-architecture.md) |
| Protection, trailing, BUY/SELL execution semantics | [03-domain-specification.md](03-domain-specification.md) |
| New database and cutover | [04-persistence-and-cutover.md](04-persistence-and-cutover.md) |
| What to borrow and what remains proprietary | [05-borrowing-plan.md](05-borrowing-plan.md) |
| Build sequence and promotion gates | [06-roadmap.md](06-roadmap.md) |
| Refutation and failure scenarios | [07-war-game.md](07-war-game.md) |
| Low-friction AI development process | [08-delivery-process.md](08-delivery-process.md) |
| Copy/paste seat prompts | [09-seat-prompts.md](09-seat-prompts.md) |
| One consolidated approval | [10-ratification.md](10-ratification.md) |
| First bounded implementation contract | [11-first-work-order.md](11-first-work-order.md) |
| Clause-level authority migration | [12-proposed-adr-set.md](12-proposed-adr-set.md) |
| Exact proposed authority ADR | [13-proposed-adr-current-state-kernel.md](13-proposed-adr-current-state-kernel.md) |
| Exact proposed protection ADR | [14-proposed-adr-protection-execution.md](14-proposed-adr-protection-execution.md) |
| Exact proposed scope ADR | [15-proposed-adr-reset-scope.md](15-proposed-adr-reset-scope.md) |

## Revised archive inventory and authority classes

The R1 archive has one top-level directory named
`Automation-Alpaca-Architecture-Reset-Handoff-2026-07-R1/` and exactly eighteen file entries:

- **Ratified authority candidate:** the fifteen numbered documents
  `ARCH-RESET-2026-07/01-*.md` through `ARCH-RESET-2026-07/15-*.md`, including
  `10-ratification.md`.
- **Navigation, not ratified authority:** `ARCH-RESET-2026-07/README.md`.
- **Detached identity index, not self-covered:** `AUTHORITY-MANIFEST.sha256`. Its human-approved
  SHA-256 binds the exact fifteen numbered documents under the canonical procedure in
  `10-ratification.md`.
- **Superseded historical context, not ratified authority:** `PLANNING-SEAT-HANDOFF.md`. It is
  retained for provenance only and may not override R1.

The human approval record remains outside the archive authority unit. Neither the manifest nor a
manifest-covered document embeds the final manifest or archive digest.

## What happens on approval

Approval is valid only when Ameen quotes the verified detached-manifest and complete-archive
SHA-256 values using the placeholder procedure in `10-ratification.md`. It then authorizes only
the bounded local M0 documentation landing: create/switch the reset branch from frozen master,
apply the exact documentation/ADR/backlink/index changes, and make one local documentation-only
commit for review. The first work order remains staged until the exact canonical ADR text,
consistency refresh, independent review, and M0 evidence are landed. Approval does not authorize a
push, pull request, merge to master, code/test implementation, Paper or live trading, broker
orders, credentials, an R6 merge, deletion of legacy material, or later roadmap stages.

No planning branch, commit, push, or pull request is created by this artifact revision.
