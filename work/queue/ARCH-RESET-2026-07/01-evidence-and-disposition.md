# Evidence and disposition

## Executive diagnosis

The project does not have a “models are incapable of coding this” problem. It has a semantic
ownership problem: the same state is repeatedly derived in the event projector, the memory
store, the SQLite store, and orchestration code, then protected with more rails when those
derivations disagree.

The R6 campaign is unusually strong evidence. At its latest observed state it added roughly
3,181 application lines, 8,877 test lines, 5,731 work/documentation lines, and 59 commits over
master, yet remains blocked after repeated P0/P1 sequence and recovery findings. More review
effort around the same topology is unlikely to change that pattern.

The reset therefore removes independent decision-making from persistence adapters and narrows
the beta before adding more functionality.

## Repository facts

| Fact | Verified state |
|---|---|
| Remote `master` | `6d5937492788aa0ab1cf8348321fa01ee57df920` |
| R6 evidence branch | `39a6ed8b9a7562f61afc9ec5c0f9fad2c3918c80`, 59 commits ahead when inspected |
| R6 review gate | Still blocked; no round-4 reviewer result |
| Signal Seat | Disabled |
| Existing stores | SQLite and memory contain independent business decisions |
| Active-branch store sizes | SQLite 9,177 lines; memory 6,727; core 6,531; projector 1,941 |
| Present protection cadence | Default 15-second monitor loop |
| Present trailing granularity | 30-second bars; historical ratchet recomputation is \(O(n^2)\) |
| Present market shape | Bid/ask/last/cumulative volume; no displayed size or depth |
| BUY-side liquidity executor | Absent |

The current project is a valuable safety prototype, but it is not yet the intended fast,
liquidity-aware two-sided engine.

## Findings from the historical reports

The reports correctly established:

- a small, inspectable, single-operator equity system;
- local protection because broker-native order types do not provide uniform session coverage;
- the hard floor as an escalation threshold, never a guaranteed fill;
- fill-only position mutation;
- no blind resubmission after an ambiguous broker response;
- replace/fill races as first-class scenarios;
- deterministic clocks, simulated broker faults, replay, and staged authority;
- no Kubernetes, distributed consensus, active-active writer, HFT stack, or premature Rust
  rewrite.

They did not fully specify:

- the hybrid trailing formula and activation;
- the BUY-side acquisition state machine;
- exact normal-exit versus hard-bail behavior;
- RTH/native handoff;
- trigger corroboration;
- current-state ownership after restart.

Those gaps are supplied by this packet.

## The semantics conflict that must be retired

The current repository has two incompatible “floor” meanings:

1. `app/protection.py` treats a floor crossing as an exit trigger and can price an aggressive
   protective limit below the current market.
2. ADR-010 and `app/sellside/policy.py` treat `floor_price` as a minimum permitted SELL limit
   and freeze the envelope if a child limit is below it.

The second meaning can strand shares during the exact collapse in which `HARD_BAIL` is needed.
The revised domain uses separate fields and separate checks.

## Preserve, re-express, defer

### Preserve as binding behavior

- Paper-only and live-shadow beta.
- Thin Streamlit client; no direct broker calls.
- One logical capital-mutating writer.
- Deduplicated fills alone change local position quantity.
- Deterministic client order IDs and effect IDs.
- Unknown submit/cancel/replace outcomes block new attempts and enter reconciliation.
- Every venue order has one durable owner.
- One local effect may own multiple distinct concrete broker acceptances; each closes
  independently.
- Human-attested missing-fill ingestion remains separate from non-economic exact-leg release.
- One live exit attempt per symbol mandate unless a broker-specific replace protocol proves
  overlap safe.
- Reduce-only SELL sizing uses the smaller trustworthy residual.
- Broker-authoritative overfills remain visible and halt affected execution.
- Startup/reconnect reconciliation and targeted order queries.
- Invalid or stale market data cannot directly drive a new order.
- Manual flatten and cancellation remain engine-mediated and audited.
- Monotonic trailing protection over a mandate lifetime.

### Preserve as source material, not architecture

- `app/protection.py` trigger calculations.
- `app/sellside/*` trail, filtering, regime, and participation prototypes.
- `app/broker/adapter.py` outcome taxonomy and deterministic identity requirements.
- Applicable portions of `app/broker/alpaca_paper.py`.
- Reconciliation scenarios in `app/reconciliation.py`.
- `app/broker/sim.py`, recorder concepts, invariants, and shrunk regression histories.
- Existing tests whose assertions express the preserved behavior above.

Reuse means porting a rule into the new kernel with a focused test. It does not mean importing
the current store choreography.

### Supersede after ratification

- ADR-004's universal “event log as durable operational truth” design.
- ADR-010's floor-as-minimum-execution-price rule.
- Dual hand-written memory/SQLite behavior parity.
- Full-history folds on a live decision or startup path.
- Signal Seat R6 as a beta prerequisite.
- Mandatory independent review after every tiny wave.

The original documents remain historical evidence. Accepted ADRs remain canonical until the
proposed superseding ADRs are explicitly approved and landed.

### Defer

- Multiple untrusted signal producers and quarantine epochs.
- Poison/heal/re-poison state.
- Public or tailnet signal ingress.
- Webull, IBKR, and Tradier implementation inside this Alpaca reset.
- Full depth-dependent authority until a suitable data source is validated.
- Runtime AI execution authority.
- Partial-profit tranches enabled by default.
- Active/passive failover, microservices, Kafka, Kubernetes, C++/Rust optimization.
- Compatibility with pre-reset SQLite databases and event logs.

## Branch disposition

1. Freeze `master@6d593749`.
2. Freeze the R6 branch at an explicitly recorded SHA as an evidence and regression corpus.
3. Do not merge R6 into the reset.
4. Start the reset from master on a new branch after ratification.
5. Port selected rules and tests intentionally; do not cherry-pick broad implementation commits.
6. Preserve old databases, logs, and both branches read-only until the paper-beta cutover is
   accepted. Direct compatibility is not required.

## Realistic labor conclusion

Codex and Claude can perform most implementation if the architecture remains this narrow and
each work order has one semantic center. The evidence does not support hiring a $5,000–$10,000
freelancer now. A human specialist becomes cost-effective later for a bounded broker-adapter
review, production operations review, or a stubborn external API integration—not as a substitute
for repairing an ambiguous domain model.
