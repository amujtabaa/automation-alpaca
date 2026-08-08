# ADR-023 GREEN feasibility pre-flight

Date: 2026-08-04

Target RED freeze: `e886fead41dca94e86e666a993f4f976507ece8d`

Exact RED review: `ACCEPT`, P0=0/P1=0/P2=0, recorded at
`work/review/REV-0050/adr023-red-freeze/result.md`.

## Material findings

### P1 — retained last-primary digest cannot support required step comparison

- ADR-023 Section 3 requires a single optional last-primary price commitment in retained state and
  a fixed 32-byte commitment as cursor part 13.
- The frozen RED state inventory types `_market_last_primary` as `bytes | None`; its literal helper
  defines the value as SHA-256 over the canonical reported-price encoding.
- The behavior contract compares a later eligible BID or TRADE primary to the last eligible
  primary, including across market kinds.
- SHA-256 is not reversible, and the exact state inventory contains no retained numeric prior
  primary. Existing economic fields cannot substitute without changing their independent meaning.

Impact: any GREEN implementation would have to omit the step rule, weaken the frozen state shape,
or hide duplicate truth. All are unacceptable. The root correction is one fixed-cardinality
`ReportedPrice | None`, committed as the same 32-byte cursor part.

### P1 — derived dataclass field shape is forbidden by the import oracle

- The public contract requires `MarketOccurrence.occurrence_id` to appear in dataclass field
  metadata with `Field.init is False` and not appear in the constructor signature.
- The frozen import allowlist permits `dataclasses.dataclass` but not `dataclasses.field`.
- A class-wide `dataclass(init=False)` does not make the individual field metadata report
  `init=False`; the standard field-level spelling is `field(init=False)`.

Direct Python 3.12.13 language check:

```text
@dataclass(init=False) field metadata: True
@dataclass with field(init=False) metadata: False
```

Impact: no ordinary dataclass declaration can satisfy both frozen controls. The root correction is
a narrow, source-position-specific allowance for canonical private `_field(init=False)` on only
`MarketOccurrence.occurrence_id`, with negative controls for all broader uses.

## Materiality and stop decision

Both findings affect implementability of required production behavior and the ability of the
accepted RED contract to admit an honest implementation. They are not style, refactor preference,
or speculative hardening. Production editing remains stopped because the first correction changes
accepted ADR-023 text and requires exact human ratification. No database, SQL, broker, network,
runtime, or application execution was used to reach these conclusions.
