# WARGAME-ROADMAP — packet index and decision block

**Everything in this packet is a proposal awaiting operator ratification. Nothing self-executes.**

| File | Deliverable |
|---|---|
| `M4a-prospective-hindsight.md` | Protocol §M4a — eight past-tense incident narratives, written before any agent |
| `hazard-register.md` | **Deliverable 1** — seven seed rows attacked, extended, priced; six new rows; verification record |
| `external-assumption-register.md` | **Deliverable 2** — 30 XA rows + the machine-join design that keeps it from rotting |
| `phase-gate-ADRs.md` | **Deliverable 3** — ADR-016…019 drafts in evidence-ratchet form |
| `sequencing-proposal.md` | **Deliverable 4** — one ordered plan, reconciled with the standing queue |
| `M4b-refutation.md` | Protocol §M4b — adversarial panel over the decision block below. **Read this first: it found two P0s against this packet, including one against its own headline** |

- **Protocol:** `.ai-os/core/18_WARGAME_PROTOCOL.md`, **FULL scope** (M1–M4).
- **Base:** `14ff12f`, branch `claude/wargame-roadmap-kickoff-2v2tan`.
- **Method:** M4a inline → four fresh-context analysts (tiered/budgeted per `.ai-os/core/17` R7–R9) →
  planning-seat re-verification of every load-bearing claim against code → M4b refutation.
- **Read-only:** no code changed, no gated surface touched, no test weakened.

## Headline

*(Corrected after M4b — see `M4b-refutation.md`. The original headline overstated two of its three
claims and both corrections are recorded rather than quietly removed.)*

The seven seed hazards are all real, but **several seed *controls* are themselves instances of the
defect classes they claim to cure** — specifically: the tape-recorder extension (inverts the recorder's
own isolation spec), the assumption register as a table (the prose form already died once in REV-0011),
the INV registry tier (structurally blind to the missing row its own title names first), the
runbook-script class (would manufacture a second recovery implementation), and the control manifest
(would certify roughly half its census wrongly today).

**Two live fail-open paths** were found and verified, both in the broker adapter:

1. **Duplicate-order path** — `app/broker/alpaca_paper.py:741-743` vs `:804-808`: 422 matches *both* the
   duplicate branch and the terminal branch, disambiguated only by a substring test against Alpaca's
   error prose. A duplicate rejection worded differently classifies a live venue order as
   never-submitted. *(Attacked in M4b and held — the packet's highest-yield concrete finding.)*
2. **Stranded-position path** — `:1171-1172` → `app/monitoring.py:2937-2946`: a 404 is read as "never
   landed"; an aged-out filled order resolves to `REJECTED`, stranding real shares with no protective
   sell.

A third claimed path — that `.importlinter:70-81` omitting `app.store` leaves lock-starvation unguarded
— **was refuted by M4b (F1) and is withdrawn.** Contract 3 forbids only *concrete* adapters; the
abstract port is deliberately permitted, so the proposed edit could not have enforced INV-052. Only the
AST check can, and it is M-cost, not a one-line edit.

## Decision block — M1 assumption ledger

Per §M1: every load-bearing line carries `TRACED(file:line)` (verified against code now),
`INHERITED(source)` (from a named prior ratified decision) or `ASSUMED`. **The load-bearing rule: no
`ASSUMED` line may be pre-checked in a FULL decision block.** The one `ASSUMED` line below is therefore
*not* pre-checked — it is converted into a named operator gate, which is the protocol's other permitted
resolution.

| # | Decision | Label |
|---|---|---|
| D-WG-1 | **Wave 0 runs now, in parallel with the Codex round-3 critical path.** No Wave 0 item touches the R6a producer-rail surface | `TRACED` — collision analysis in `sequencing-proposal.md §5`; each item's paths enumerated |
| D-WG-2 | **The seed map's "build the kernel before the surface" principle is replaced** by "buy failure-capability first, where it is cheapest." The six effect authorities predate R7; R7 is a seventh consumer | `TRACED(app/store/base.py:665,731,814,876,1550,1573)` |
| D-WG-3 | **"Extend the tape recorder to venue event streams" is rejected as scoped** — it inverts the recorder's isolation property and presumes a stream that does not exist | `TRACED(docs/spec/replay/tape-format.md:3-5; app/recorder/runner.py:24-40)` + no `TradingStream`/`trade_updates` in `app/` |
| D-WG-4 | **The external-assumption register lands as a keyed machine-joined artifact with a CI checker and a negative fixture under `tests/`** — never as a markdown table alone | `TRACED(work/review/REV-0011/disposition.md:42-45)` — the prose version was already run and already died |
| D-WG-5 | **ADR-016 (LIVE_SHADOW architecture) precedes ADR-017–019.** A gate ratified over a mode with no code substrate binds nothing | `TRACED(app/config.py:176-304, 220-221; app/broker/factory.py:24-64)` |
| D-WG-6 | **P-0 — amending `pkl/project/goals.md` and the CLAUDE.md safety core — is the first ratification**, before any phase-gate ADR | `TRACED(pkl/project/goals.md:22; CLAUDE.md:27-28)` |
| D-WG-7 | **One shared lane registry (W2.4) replaces five separately queued enumerations** — P-2, P-7, Row 1's permit lanes, Row 5's INV quantifier upgrade, Row 12's compensation registry | `TRACED(.ai-os/templates/work-order.md:46-75)` + AUDIT-0003 P-2/P-7 |
| D-WG-8 | **R7 gains a cut by gated surface**, in addition to the ratified cut by side. This amends a ratified plan and needs explicit operator ratification | `INHERITED(work/queue/SIGNAL-SEAT-R5b-TO-D2a-SEQUENCING-PLAN.md:133-165)` + `TRACED(docs/spec/signal-seat/05-conversion.md:133,135-137)` |
| D-WG-9 | **P-5 is RATIFY-AFTER the mutation ratchet has a baseline.** Mandating currency certificates while `MAX_SURVIVORS=999` mandates an artifact that structurally cannot fail | `TRACED(.github/workflows/mutation-nightly.yml:27,38)` |
| D-WG-10 | **P-14 is ratified together with a quantifier upgrade.** As written it would not catch INV-060 — a universal claim pinned by three tests covering two of six lanes passes a checker that counts to one | `TRACED(docs/INVARIANTS.md:428-452; app/store/base.py:1550,1573)` |
| D-WG-11 | **New rows 8–13 are admitted to the hazard map** (float money arithmetic; ungated startup migration; incomplete post-incident evidence; no store I/O-failure semantics; uncompensated in-request transactions; the mock/sim as unratified venue spec) | `TRACED` — each row carries verified anchors in `hazard-register.md` |
| D-WG-12 | **D-1…D-5 are operator decisions the planning seat cannot resolve**, and three of them gate later waves | `TRACED` for D-1/D-2/D-3/D-5 (each anchored in the register) |
| **D-WG-13** | **"WO-A/B/C kernel program" and "WO-E permits" — the kickoff's own named queue items — have no content anywhere in the repo.** Wave 3 is scoped from hazard analysis, not from these names, and may be wrong about their intent | **`ASSUMED` → NOT PRE-CHECKED. Converted to named operator gate D-4.** Per the governing principle, the planning seat declines to reconstruct them by inference |

### M4b status

The panel returned **three surviving findings — two P0** — against this block. All three are resolved
per protocol §M4b (two `TRACED` fixes, one named gate) and the amendments are applied above and in the
deliverables. **The block is ratifiable as amended.** Two of the P0s attacked this packet's own headline
and its ADR gate text; both corrections are recorded in place rather than silently removed. Read
`M4b-refutation.md` before ratifying.

### Ratification boxes (operator)

- [ ] **Wave 0 — ungated subset** (W0.1a, W0.1b, W0.5, W0.6) authorized to run now, in parallel with the
      critical path
- [ ] **Wave 0 — gated subset** (W0.3 order submission; W0.4 event-log truth): explicit scope approval,
      each with a tracked `REV-*` packet. *These are the two highest-value items in the wave; they are
      cheap but they are not routine*
- [ ] **W0.2** stays gated pending a pasted `pytest .ai-os/scripts/tests/` run under the root config
      (M4b F3)
- [ ] **P-0** — amend `pkl/project/goals.md` + CLAUDE.md safety core to admit a live-capital
      destination. *No Wave 0 item depends on this; it gates only the Wave 5 phase-gate ADRs. Deferring
      it costs nothing*
- [ ] **D-1** live-paper probe: permitted / not permitted
- [ ] **D-2** calendar source: `GetCalendarRequest` / committed static table
- [ ] **D-3** **account-level** daily-loss ceiling: beta requirement / pre-live requirement — *note the
      M4b F2 correction: a per-position 8% stop-loss already exists and is on by default*
- [ ] **D-4** clarify "WO-A/B/C kernel program" and "WO-E permits" *(blocks Wave 3 scoping)*
- [ ] **D-5** ADR-019: one ADR for two transitions / split
- [ ] Hazard rows 8–13 admitted
- [ ] Sequencing waves 1–5 accepted as the ordering
- [ ] P-item dispositions (§6 of the sequencing proposal) accepted

## Standing limitations

- **No test suite was executed.** Absence-of-coverage claims derive from `grep` over `tests/`, which
  finds by name and literal. The exception is `tests/test_features.py:148-160`, read in full.
- **Two register rows are unresolved and marked as such** — XA-08's SDK pagination behaviour
  (`alpaca` is not importable in this container) and XA-28's budget value.
- **`app/reconciliation.py` is 1,989 lines; roughly 150 were read.**
- **This is the first net, never the only one.** A design clearing a FULL war-game still takes its
  mid-session GATEs, `.ai-os/core/17` internal review, and `15` cross-model review.
