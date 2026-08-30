# Fresh M2 execution and M3 preparation map

Status: **M2 COMPLETE — M3 PREPARED, NOT ACTIVATED**

## Current position

All six serial M2 work orders are independently accepted and closed. WO-0170's canonical closeout
is `6edd8fbae0cd0eb7868826cfd0450860c63df70e`, tree
`8c918f3a1cf46333ed0eef79d3ef51d0503de88a`. REV-0119 accepted the combined terminal candidate
`8499845f668c0e0b71100e2420d000b0657606a6`, tree
`79382c952ceacf5e777c13a7a44f4e3ccddb32f7`, with P0=0/P1=0/P2=0 and nothing unverified. The
implementation boundary is frozen and the documentation-only M3 entry contracts are prepared.

## Work-order chain

| Order | State in this packet | Purpose | Plain-language outcome | Activation boundary |
| --- | --- | --- | --- | --- |
| `WO-0165` / M2-I1 | `CLOSED` | Immutable M1 value/profile codecs and independent known answers | Important identities and exact values can be stored and recovered without changing meaning | REV-0070 accepted |
| `WO-0166` / M2-I2 | `CLOSED` | Schema and direct-current-proof constraints | SQLite has a fail-closed shape that prevents duplicate or contradictory authority | REV-0071 accepted |
| `WO-0167` / M2-I3 | `CLOSED` | Narrow SQLite repository hydration | Current state loads and saves by direct keys without replaying history or creating another engine | REV-0073 accepted |
| `WO-0168` / M2-I4 | `CLOSED` | Atomic unit of work, claims, outbox eligibility, receipts | A crash leaves the old whole state or new whole state, never half of each | REV-0115 accepted |
| `WO-0169` / M2-I5 | `CLOSED` | Startup, reconciliation, owner lock, ADR-023 cold recovery | Restart refuses service until ownership, effects, state, and market evidence are trustworthy | REV-0117 accepted |
| `WO-0170` / M2-I6 | `CLOSED` | Crash/restore/fault closeout and boundedness proof | The M2 build has reproducible crash, restore, fault, and boundedness evidence | REV-0118 and terminal REV-0119 accepted |
| `WO-0171` / M3-P1 | `READY-BLOCKED` | Deterministic broker simulator, normalized tape, virtual clock | Future scenarios run the same way every time without touching a real broker | Separate human M3-P1 activation required |
| `WO-0172` / M3-P2 | `READY-BLOCKED` | Semantic trace comparator and permanent regression corpus | M3 can prove equivalent behavior and retain minimized failures | Accepted M3-P1 plus separate human M3-P2 activation |

`READY-BLOCKED` means REV-0119 accepted the executable specification but granted no implementation
authority. Each M3 order still requires a separate human activation, fresh branch, exact
predecessor, allowed-path inventory, and independent review identity.

## Mandatory sequence

```text
M2-I1 codec/profile contract [CLOSED]
  -> M2-I2 human-gated schema [CLOSED]
  -> M2-I3 repository hydration [CLOSED]
  -> M2-I4 atomic transition/effect claims [CLOSED]
  -> M2-I5 startup/reconciliation/cold recovery [CLOSED]
  -> M2-I6 crash/restore closeout [CLOSED]
  -> terminal M2 + M3-entry review [REV-0119 ACCEPTED]
  -> M3-P1 simulator/tape/clock [SEPARATE ACTIVATION REQUIRED]
  -> M3-P2 trace comparator/regression corpus [SEPARATE ACTIVATION REQUIRED]
```

No order may absorb its successor merely because implementation is convenient. A discovered need
for a later concept becomes a checkpoint, not scope creep.

## Definition of M2 complete

M2 is complete only when all six M2 orders are independently accepted on exact heads and the
combined candidate proves:

- one sequenced writer and one pure semantic owner;
- direct bounded current proof without serving-time history fold;
- one atomic fact/state/effect/claim/receipt boundary;
- no blind resend after ambiguity or restart;
- fail-closed owner lock, startup, reconciliation, and market-source recovery;
- exact profile-scoped authority with Alpaca Paper remaining the sole M2-M8 mutation profile;
- fresh temporary-database fault evidence, restore evidence, and required boundedness controls; and
- every unrun operational, broker, soak, promotion, and R16 gate remains honestly unpassed.

## Definition of M3 prepared

M3 is prepared—not implemented—when:

- its two queued work orders have exact M2 entry conditions and no dependency on legacy runtime
  truth;
- the simulator is structurally outside engine-state mutation authority;
- normalized tape, virtual clock, semantic trace, and shrunk-corpus contracts are specified;
- the minimum histories from the accepted reset roadmap, including AR-02 through AR-09, are mapped;
- M3 cannot begin until the accepted M2 persisted interface and checkpoint vocabulary are frozen.

No broker adapter, credentials, Alpaca calls, orders, live-shadow mode, M4 capability evidence, or
promotion follows from M3 preparation.
