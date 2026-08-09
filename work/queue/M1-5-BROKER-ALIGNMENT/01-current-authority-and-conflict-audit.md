# Current authority and provider-literal conflict audit

This is an authority classification, not an implementation inventory. Existing
code, tests, credentials, and the abandoned Cloud candidate were not used.

| Class | Exact current anchor | Authority and treatment | Risk if misread |
| --- | --- | --- | --- |
| A — accepted intentional beta boundary | `ADR-022` lines 19–24; `ARCH-RESET` lines 39–41; `pkl/project/goals.md` lines 230–233 | Alpaca Paper, one account, paper/live-shadow restrictions, and no live trading are accepted beta values. Preserve them. | Replacing the beta provider or authorizing live operation. |
| A — accepted cutover guard | `ADR-022` lines 45–56; `04-persistence-and-cutover.md` lines 1004–1055; roadmap lines 183–186 and 229–236 | Exact broker/environment/account/origin/credential-fingerprint comparison is a fail-closed selected-generation fence. Preserve the comparison. | An unsafe profile mismatch or second broker authority. |
| B — adapter implementation detail | `pkl/architecture/architecture-map.md` lines 105–127; roadmap lines 277–319 | `alpaca-py` belongs only in the future adapter and M4 is the broker-correlation milestone. It is not a durable identity model. | Treating an SDK import boundary as a permanent database provider constraint. |
| C — proposed M2 durable assumption | `04-persistence-and-cutover.md` lines 31–800, especially `execution_facts.broker` and `.environment`; roadmap lines 160–241 | The old proposed DDL and M2 fence encode `ALPACA`/`PAPER` directly in durable relations. It is planning evidence only; M2 DDL remains unapproved. | A future provider recutover would require rewriting capital-relevant historical rows or an unreviewed schema break. |
| D — historical/frozen evidence | `REV-0059/handoff.md` “Schema-neutral durable field and projection map”; `ARCH-RESET` lines 62–69 | The DDL incident and frozen M1 handoff demonstrate boundaries but do not authorize schema work. Preserve as evidence; do not rewrite. | Reusing prohibited DDL or asserting persistence evidence from M1. |
| E — current knowledge/roadmap statement | roadmap lines 10–17, 160–416; `pkl/project/goals.md` lines 18–36; architecture map lines 18–35 | M1 is closed; M2 through M8 are sequenced, but M2/runtime/broker activity is inactive. The roadmap names Alpaca Paper for M4–M8. | Premature M2 activation or an accidental Webull milestone. |
| F — conflict requiring ADR resolution | `ADR-022` lines 45–51 and 55–56 versus `04-persistence-and-cutover.md` proposed provider literals; `ADR-020` lines 49, 79, 85, and 107 | ADR-022 requires exact selected values at every capital-relevant comparison; M2 planning risks treating those values as permanent table literals rather than commitment coordinates. ADR-024 must preserve the former and narrowly supersede the latter inference. | Either weakening Paper cutover checks or permanently encoding Alpaca as the only provider. |

## Direct findings

1. Accepted authority already requires a single application-generation/broker/
   environment/account fence and final-claim revalidation. It does **not**
   accept multiple active connections, routing, or provider hot-swap.
2. The M1 kernel is intentionally provider-neutral but still binds capital facts
   to the external authority coordinates. This makes profile commitment binding
   additive to safety rather than a new execution model.
3. `broker='ALPACA'` and `environment='PAPER'` in the proposed M2 DDL are
   admissible as selected profile values for M2–M8; they are inadmissible as an
   eternal physical-schema rule for every durable capital row.
4. Market stream identity is already distinct from application generation under
   ADR-020 and ADR-023. Execution provider must therefore not be used to infer
   market-source authority.

## Required resolution boundary

ADR-024 will retain the exact current selected Alpaca Paper profile for M2–M8,
including all mismatch refusals, while requiring future M2 schema work to bind
rows to an immutable profile identity/commitment. It does not approve a schema,
provider change, or M2 implementation.
