# REV-0074 R12 independent relational findings

Exact candidate reviewed: `78f96af9f2597fe981f3b760f72923c5e331e379`, tree
`c3fe51651d906707934f78c66107c9dca10a9969`.

## P1 — Authority semantic keys can still cross application generations at the schema boundary

Location: frozen contract existing semantic-key relation and R12 schema closure.

Mechanism: the record validator requires authority key application generation to equal its owning
input generation, but the frozen relational rules did not require an equivalent database check.

Impact: an authority collision-domain key could be attached to a valid durable input from another
application generation after restart.

Smallest complete correction: add a table-local authority-kind check/trigger that enforces equality
and exact parent profile/scope bindings, plus a two-valid-generation rejection control.

## P1 — Receipt/outcome linkage does not require one coherent terminal result

Location: frozen contract R12 receipt/outcome linkage and durable-input finalization rule.

Mechanism: the outcome foreign key selected a receipt but did not force equal owner domain,
disposition, result digest, or nullable checkpoint reference; finalization required only terminal
technical state.

Impact: a terminal input could retain contradictory receipt and outcome evidence.

Smallest complete correction: add a null-safe cross-record trigger requiring every duplicated result
field to match before outcome insertion and finalization, with an independent mutation for each
field.

## Verdict

**ACCEPT-WITH-CHANGES**

- P0: 0
- P1: 2
- P2: 0

Unverified: No SQLite, DDL installation, database creation, runtime composition, tests, network,
broker, or order features were executed.
