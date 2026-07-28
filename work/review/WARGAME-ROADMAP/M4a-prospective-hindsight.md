# M4a — Prospective-hindsight brief (planning seat, inline, pre-agent)

- **Protocol:** `.ai-os/core/18_WARGAME_PROTOCOL.md` §M4a. Written **before** any analyst was spawned;
  its causes seeded the four analyst briefs and are re-tested by them (several may be wrong — that is
  the point of writing them in advance and handing them to fresh context).
- **Scope gate:** FULL. The war-game drafts ADR text, creates new stateful artifacts
  (external-assumption register, divergence ledger, control manifest), and repurposes existing
  mechanisms (tape recorder → venue streams; ledger pattern → divergence ledger; INV registry → a
  capital-critical tier).
- **Frame (past tense, mandatory):** *It is 2026-11-15. The platform was promoted to live capital in
  October. On 2026-11-12 it caused a capital incident. From the code as it stands at
  `14ff12f`, explain how it happened.*

Nothing below is a prediction. Each narrative is written as an incident that already occurred, and
each names the cause that must become an M1 assumption to trace, an M2 edge to anchor, or an M3
reader to classify.

---

## N1 — The flip that was never a flip (hazard 4)

The promotion ADRs were ratified in August. `LIVE_SHADOW` soak ran twenty clean sessions and the
divergence ledger recorded zero class-A divergences, so the shadow→small-capital gate cleared on
schedule. It cleared because **`LIVE_SHADOW` was never an execution mode.** The identifier appears in
`CLAUDE.md:27` and `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md:337` as prose only; `app/config.py`
declares no execution-mode enum, and its only credential variables are
`ALPACA_PAPER_API_KEY`/`ALPACA_PAPER_API_SECRET` (`app/config.py:60-61`). The soak therefore ran the
paper adapter against the paper venue and compared the system to itself. Divergence was structurally
zero, not empirically zero.

**Cause:** a promotion gate whose oracle is the artifact it certifies is S-8 oracle capture at the
highest-stakes moment in the program. The gate ADR must name *what divergence is measured between*,
with code anchors for both sides, and the soak must be incapable of running when the two sides are
the same object.

## N2 — The assumption that was true in paper and false in live (hazard 2)

`UC-001`'s never-blind-resubmit safety rests on Alpaca rejecting a duplicate `client_order_id`.
REV-0011 verified the 409/422 duplicate-rejection branch against a **mock** and recorded the real-venue
confirmation as a *"beta pre-flight (not a code change)"* — prose in a closed disposition
(`work/review/REV-0011/disposition.md:42-45`). It was never run. At live the retention window for
`client_order_id` turned out to be finite; a `TIMEOUT_QUARANTINE` reconcile resubmitted under an id the
venue no longer considered taken, and the position doubled.

**Cause:** exactly the S-4 shape — an obligation whose only home was a dispositioned packet. The cure
is not "remember to check": it is a row with a probe and a **verified-against-recorded-reality bit that
CI reads**, such that an unverified bit blocks the promotion gate that depends on it. The register is
worthless if it is a table a human maintains.

## N3 — The calendar cell nobody generated (hazard 3)

The incident began at 13:00 ET on the day after Thanksgiving — a half-day close. An envelope stayed
`ACTIVE` past the close and the restart after the session boundary disagreed with the pre-close state
about which session it was in. Every engine test passed, because engine tests inject their clocks: the
injected clock is what *proves determinism* and simultaneously *lets every test author pick a
convenient timestamp*. No test ever chose a half-day, a DST transition, or a halt.

**Cause:** clock injection is necessary and is not calendar coverage. The calendar must be a
**generator dimension owned by the harness**, not a timestamp chosen by the test author, for every
session-touching work order.

## N4 — The kernel that arrived after the surface it was meant to protect (hazard 1)

R7 was the critical path, so it shipped before the WO-E effect-permit sink. R7 landed with six
independent effect authorities — approval, envelope, single-flight, kill-switch, dual-store,
replay — each enforcing the shared obligations in its own lane, which is the S-2 sibling-lane shape
that AUDIT-0003 P-2 explicitly refuses to call structurally closed until "the sink accepts only a
shared authorization/plan type." The permit type was retrofitted onto four lanes in September; the
fifth kept its bespoke check, and that is the lane the incident went through.

**Cause:** ordering. A shared-sink type is worth nothing if the surface that needs it is built first;
the sequencing proposal must make "sink before surface" a hard ordering constraint or explicitly re-cut
R7 into slices that can each be admitted through the sink as it exists.

## N5 — The invariant that became money (hazard 5)

A broker call issued under the store lock hit an Alpaca rate limit and retried with backoff, holding
the lock for tens of seconds. The kill switch — whose entire contract is to block new order intent —
needed the same lock and did not take effect for the duration. `INV-051` (lock reentrancy = whole-
process deadlock) has **zero tests** and `INV-052` (broker IO under the store lock) is *"structural"
prose only*, both recorded in `work/review/AUDIT-0003-addendum-01.md:28-31`. Nothing in the repo
measures kill-switch latency; the invariant is stated as a logical property and enforced as one.

**Cause:** a capital-critical invariant whose real failure mode is *timing* cannot be discharged by a
logical assertion. The capital-critical tier must require a **measured-latency probe with a recorded
number**, and INV-052 needs the AST scan (await-on-adapter-inside-lock) the addendum already says is
feasible and absent.

## N6 — The control manifest that certified itself (hazard 7)

The closure checker confirmed every control had a manifest entry and every entry pointed at a live CI
step. One of those steps was the nightly generated-mutation ratchet, which was still `MAX_SURVIVORS=999`
with `mutmut run || true` and an explicit REPORT-ONLY marker (AUDIT-0003 S-3). The manifest was green;
the ratchet was inert. The manifest had recorded **existence**, which is the exact distinction
AUDIT-0003's corrected meta-law draws between placement and control.

**Cause:** a control manifest must record **failure-capability** — the committed negative fixture and
the date it last went RED — not the presence of a step. A manifest that records existence is a new S-4
instance wearing the costume of the S-4 cure.

## N7 — The runbook that ran (hazard 6)

The executable runbook for "crash mid-submit" existed, had fixtures, and passed in CI the morning of
the incident. The real event was a crash mid-submit *while the kill switch was engaging and a
reconcile was in flight* — a three-fault composition no scripted fixture assembled. The runbook
executed correctly against a state the system was not in.

**Cause:** scripted single-fault fixtures certify the scenario, not the machine. Recovery procedures
must be exercised by **stateful operation-sequence generation** (the `RuleBasedStateMachine` adoption
the external audit already prioritized), with the scripted runbook as the human-readable projection of
it, never the proof.

## N8 — The war-game itself (meta)

The roadmap was ratified in July and followed for three months. By October three of its seven rows had
been quietly reinterpreted, because the only place those obligations lived was this packet in
`work/review/`. PROC-0001's incident carry-forward field died the same way when W3-STATE.md retired
(AUDIT-0003 S-4); `work/review/AUDIT-0003-addendum-01.md:44-48` states the through-line directly —
*every rule that bit had reached either `ci.yml` or a template a seat actually instantiates; every rule
that failed lived as prose in a core file or an instance.*

**Cause, and the one that governs the whole deliverable set:** any control this war-game proposes that
lands only as prose in `work/review/WARGAME-ROADMAP/` will decay on the same schedule as the hazards it
names. Every ratified row must terminate in `ci.yml`, a template a seat instantiates, or a committed
test — and the war-game's own sequencing proposal must be scored on that basis, not on
comprehensiveness.

---

## Seeding map (M4a → downstream obligation)

| Cause | Becomes |
|---|---|
| N1 | M1 assumption: "`LIVE_SHADOW` is an implementable mode" — trace or gate. M3: who reads execution mode? |
| N2 | The external-assumption register's core requirement: machine-read verified bit gating promotion |
| N3 | M2 edge: session-boundary transitions across calendar cells; generator dimension |
| N4 | Hard ordering constraint in the sequencing proposal (sink before surface) |
| N5 | Capital-critical INV tier: measured-latency probe + INV-052 AST scan |
| N6 | Control manifest records failure-capability + last-RED date, not existence |
| N7 | Stateful generation is the proof; the runbook is the projection |
| N8 | Scoring rule for every deliverable: terminates in CI/template/test, or it does not count |
