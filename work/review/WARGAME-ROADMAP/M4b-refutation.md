# M4b — Pre-ratification refutation pass (fresh-context adversarial panel)

- **Protocol:** `.ai-os/core/18_WARGAME_PROTOCOL.md` §M4b — a fresh-context agent briefed to **refute the
  decision block from code**, not to build or improve.
- **Shape:** four diverse lenses (anchor-integrity, control-efficacy, sequencing-collision,
  omission-and-overreach), each finding then facing **two independent refuters** (one for P2) per
  `.ai-os/core/17` R9. A finding survived only if **no** refuter could kill it. 61 agents, 0 errors.
- **Verdict: NOT RATIFIABLE AS WRITTEN. Ratifiable with the three amendments below**, all of which are
  applied to the deliverables in the same commit as this file.

**Three findings survived. Two are P0 and both attack load-bearing text — including the packet's own
headline. The planning seat re-verified all three directly against code and all three hold.**

This file is the honest record of the war-game catching its own Class-1 failure. That is the outcome
protocol 18 exists to produce, one stage earlier than a launched session.

---

## F1 (P0) — W0.1's `.importlinter` edit cannot enforce INV-052

**Broke:** the `README.md` headline's third "live fail-open path", `sequencing-proposal.md` §1's worked
example and §2 row W0.1, and D-WG-1's "free wins" framing.

Contract 3 is a **venue-agnosticism** contract. Its `forbidden_modules` (`.importlinter:82-88`) are only
the concrete venue implementations plus the SDK — `app.broker.alpaca_paper`, `app.broker.mock`,
`app.broker.sim`, `app.marketdata.alpaca_stream`, `app.marketdata.fake`, `alpaca`. **The abstract port
`app.broker.adapter` is deliberately permitted**, stated verbatim in the contract header
(`.importlinter:61-64`): *"Engine modules may depend on the abstract PORTS (app.broker.adapter,
app.marketdata.service)."*

INV-052's hazard is *awaiting a broker call while holding the store lock*. A store doing that would call
through exactly that sanctioned port — or through an adapter passed in as a call argument, which no
import contract sees at all. `allow_indirect_imports = True` (`:69`) further narrows the contract to
**direct** edges. And `app/store/` contains zero adapter imports today; the only matches across all five
modules are prose comments (`app/store/core.py:3109`, `app/store/base.py:764`).

**So the proposed edit forbids something the store already does not do, is blind to what INV-052
actually prohibits, and would buy false assurance on a safety invariant.** `docs/INVARIANTS.md:420-422`
already concedes INV-052 is "*Pinned by:* structural"; the edit would let the roadmap record it as
closed while leaving it exactly as unenforced.

**Root cause, stated plainly:** the planning seat read `.importlinter:66-82`, saw `app.store` absent from
`source_modules`, and inferred a control that the next six lines refute. The *fact* was traced; the
*inference built on it* was not. That is the Class-1 shape — a load-bearing claim carrying a `TRACED`
label it did not earn.

**A stronger diagnosis the panel supplied:** import-linter is an import-graph tool with no concept of a
call site, an `await`, or a lock context. **No import-linter contract can express INV-052 at any
setting.** Only the AST check can.

**Amendment (TRACED fix), applied:** W0.1 is split. **W0.1a** — `app.store` into Contract 3 — is
re-labelled a narrow direct-edge guard against `app.store.* → app.broker.{alpaca_paper,mock,sim}`, cost
S, value marginal, **explicitly not an INV-052 control**. **W0.1b** — the AST check plus committed
negative fixture — carries the whole INV-052 claim and is re-priced **M, not S**. The third fail-open
path is struck from the headline.

---

## F2 (P0) — "No P&L-based control anywhere in the system" is false, and was written into ADR gate text as verified

**Broke:** `hazard-register.md` ROW 5, `phase-gate-ADRs.md` ADR-018 gate F3, `sequencing-proposal.md`
D-3, and the D-3 ratification box in `README.md`.

`app/protection.py` is an always-on per-position hard stop-loss: `stop_loss_pct: float = 0.08` (`:48`),
`floor_price = average_price * (1.0 - stop_loss_pct)` (`:66-70`), producing a full-exit `FloorBreach`.
It ships **enabled by default** — `protection_enabled: bool = True` (`app/config.py:295`), under a
comment that states the intent outright (`:293`): *"On by default: a beta operator shouldn't have to opt
in to a stop-loss."*

That is a P&L-based control by any ordinary reading: unrealized loss measured against average cost,
enforced by an order.

**Root cause:** the grep was `daily_loss|max_daily|drawdown|daily_pnl` — an *account-level daily*
search. It found the absence of an account-level daily control and the planning seat reported it as the
absence of **any** control. This is precisely the by-name/by-literal failure mode this packet's own
Standing limitations warn about, committed by the packet.

**Why this was the most damaging error in the set:** it was promoted into ADR-018's evidence table
marked *verified*, where it would have told a ratifying operator they have **zero loss control today**
when an 8% stop-loss is on by default. That materially changes whether "pre-live" is a safe answer to
D-3.

**Amendment (TRACED fix), applied:** ROW 5 and gate F3 now state what is true — *no account-level daily-loss
or drawdown control exists; a per-position hard stop-loss exists and is on by default, with named
residual exposure to gap-through, halted books, and stale-feed non-evaluation (XA-13/XA-14)*. The word
"verified" is requalified to name the search that was actually run. The capital-limit inventory is
corrected from three knobs to six. **D-3 may not be ratified until the operator is reading the corrected
inventory.**

---

## F3 (P2) — W0.2 is not a one-line S-cost edit; its cost is unpriced

**Broke:** `sequencing-proposal.md` §2 row W0.2 and D-WG-1's "all S-cost" framing.

`.ai-os/scripts/tests/` has never run under this repo's root pytest configuration and the proposal
verified nothing about whether it can. That tree ships its own `conftest.py` which would load alongside
the repo-root `conftest.py`; the root config promotes `ResourceWarning` and
`PytestUnraisableExceptionWarning` to session-wide errors (`pyproject.toml:24-27`); and
`[tool.ruff] extend-exclude = [".ai-os", ...]` (`:46`) means those files have never been linted or
format-checked by this repo's gates. The packet's own standing limitation says no test suite was
executed — so the ~30 red/green pairs are **asserted** to pass, not observed to.

**Amendment (named gate), applied:** W0.2 is re-costed **unpriced pending a spike** and gated: it may
not be authorized until one throwaway run of `pytest .ai-os/scripts/tests/` under the root config is
pasted as evidence, with the conftest-collision and warnings-promotion outcomes stated. If red, W0.2 is
remediation work, not a free win.

---

## Findings the panel raised and refutation killed

Recorded so the surviving set is not mistaken for everything that was tried. **Twenty-four attacks were
mounted and refuted.**

- **D-WG-1's collision analysis survived five separate attacks** — that Wave 0 touches the R6a producer
  rail, that it disturbs in-flight REV-0045 round-3 evidence, that the six items are not mutually
  independent, that the P-1 tripwire ordering is inconsistent, and that "the only wave for which that is
  true" is overstated. None landed.
- **W0.3, W0.4, W0.5 and W0.6 each held** as genuinely S-cost and prerequisite-free. The mispricing is
  confined to W0.1 and W0.2.
- **The duplicate-order 422 fail-open path** (`app/broker/alpaca_paper.py:741-743` vs `:804-808`) was
  attacked as a misread **and held.** It remains the packet's highest-yield concrete finding.
- **D-WG-2's six effect authorities**, **D-WG-5**, **D-WG-8**, **D-WG-9**, **D-WG-10's "counts to one"
  argument**, and **D-WG-4** all held on their cited anchors.
- **XA-08 and XA-15 held as `CONTRADICTED`.**
- An **omission attack** on the absence of an ingress-authentication hazard row was mounted and refuted.

## Two of the packet's own rhetorical claims were refuted and are corrected

1. **"Five of the seven seed controls are instances of the defect classes they claim to cure"** — refuted
   as unsupported by an enumeration. Corrected to name the specific controls rather than assert a count.
2. **"`tests/test_features.py:148-160` affirmatively pins the wrong half-day answer"** — refuted on
   framing. The test honestly documents itself as a known limitation; "pins current behaviour under an
   explicit docstring recording that it is wrong" is accurate, "affirmatively certifies the wrong
   answer" is loaded. Softened.

## Ratifiability

Protocol §M4b: *"A FULL design is ratifiable only after M4a's causes and M4b's findings each resolve to a
`TRACED` resolution or a named gate — none left un-resolved."*

- F1 → `TRACED` fix applied (W0.1 split; headline corrected).
- F2 → `TRACED` fix applied (ROW 5, gate F3, inventory corrected; D-3 re-gated).
- F3 → **named gate** applied (W0.2 blocked on a pasted spike run).

All three resolved. **The decision block is ratifiable as amended** — and, per protocol, this remains the
first net and never the only one.
