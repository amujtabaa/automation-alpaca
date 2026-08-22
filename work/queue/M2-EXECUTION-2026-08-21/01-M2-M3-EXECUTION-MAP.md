# Fresh M2 execution and M3 preparation map

Status: **PREPARATION CANDIDATE — ONLY M2-I1 HUMAN-ACTIVATED — IMPLEMENTATION HELD**

## Current position

The architecture question is settled. Human Gate B ratified the six-slice M2 sequence. The missing
piece was an executable, checkpoint-oriented work-order chain suitable for a local coding LLM.
This packet supplies that chain without implementing it.

## Work-order chain

| Order | State in this packet | Purpose | Plain-language outcome | Activation boundary |
| --- | --- | --- | --- | --- |
| `WO-0165` / M2-I1 | `ACTIVE`, pre-implementation hold | Immutable M1 value/profile codecs and independent known answers | Important identities and exact values can be stored and recovered without changing meaning | Already human-authorized; code waits for preparation-baseline merge |
| `WO-0166` / M2-I2 | `READY` | Schema and direct-current-proof constraints | SQLite is given a fail-closed shape that prevents duplicate or contradictory authority | Fresh human approval of the exact DDL and temporary-DB test plan |
| `WO-0167` / M2-I3 | `READY` | Narrow SQLite repository hydration | Current state loads and saves by direct keys without replaying history or creating another engine | M2-I2 accepted and separately activated |
| `WO-0168` / M2-I4 | `READY` | Atomic unit of work, claims, outbox eligibility, receipts | A crash leaves the old whole state or new whole state, never half of each | M2-I3 accepted and separately activated |
| `WO-0169` / M2-I5 | `READY` | Startup, reconciliation, owner lock, ADR-023 cold recovery | Restart refuses service until ownership, effects, state, and market evidence are trustworthy | M2-I4 accepted and separately activated |
| `WO-0170` / M2-I6 | `READY` | Crash/restore/fault closeout and boundedness proof | The complete M2 build survives injected failures and has evidence another reviewer can reproduce | M2-I5 accepted and separately activated |
| `WO-0171` / M3-P1 | `READY-BLOCKED-BY-M2` | Deterministic broker simulator, normalized tape, virtual clock | Future scenarios run the same way every time without touching a real broker | M2-I6 accepted and M3 separately activated |
| `WO-0172` / M3-P2 | `READY-BLOCKED-BY-M2` | Semantic trace comparator and permanent regression corpus | M3 can prove equivalent behavior and retain minimized failures | M3-P1 accepted and separately activated |

`READY` means executable specification prepared, not implementation authority. Only `WO-0165` is
active, and its implementation is deliberately held until the documentation-only starting point is
merged under separate human authority.

## Mandatory sequence

```text
preparation baseline merge
  -> M2-I1 codec/profile contract
  -> M2-I2 human-gated schema
  -> M2-I3 repository hydration
  -> M2-I4 atomic transition/effect claims
  -> M2-I5 startup/reconciliation/cold recovery
  -> M2-I6 crash/restore closeout
  -> M3-P1 simulator/tape/clock
  -> M3-P2 trace comparator/regression corpus
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
