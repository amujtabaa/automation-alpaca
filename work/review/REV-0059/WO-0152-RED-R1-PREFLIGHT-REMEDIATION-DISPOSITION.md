# WO-0152 R1 preflight remediation disposition

Status: DRAFT CORRECTION — NOT ACTIVE  
Date: 2026-08-07  
Owner: implementation/planning seat

## Retained initial result

The initial frozen WO-0152 RED candidate is retained unchanged:

- contract SHA-256: ce27017d419b2b537d88b618dfc0bdecdc1b01a0a7df3db5f0b5c69b6adf9ce4;
- manifest SHA-256: ba9428c2db4bbb9fc0327f9fae9b3de51c16b1fe93c0d98ea4c59bc008116cfe;
- independent result SHA-256:
  ae398751c5c64478748c4fd15a9a9a4124858c449a604d9052b2034f1e592b57;
- verdict: ACCEPT-WITH-CHANGES, P0=0/P1=1/P2=0.

The result established that strict public-only E3 setup cannot construct an
authentic DualMandateBinding for the required initial and successor mandates.
A focused static follow-up also established that public terminal-leg evidence
cannot close the parent acceptance set required for a root-owning retired A to
admit B: the public venue reducer rejects CloseAcceptanceSet and external
closure certification is deliberately unavailable in pure M1.

Neither observation is a production defect. Both are deliberate deferrals of
operator configuration and adapter completeness certification. Adding a public
configuration or certification API would be prohibited production-surface
work, not an E3 correction.

## User-ratified R1 root correction

The user authorized exactly two separately named, test-only setup exceptions:

1. _approved_acquisition_mandates_fixture may call only
   app.execution_core.acquisition._mint_dual_mandate_binding at its exact
   statically whitelisted call site to mint fixed complete immutable A/B/C
   approved-mandate inputs before genesis.
2. _certified_terminal_parent_fixture may, only after the public
   claim/discovery/terminal-observation lifecycle, apply one exact sealed
   CloseAcceptanceSet through the existing internal venue transition under an
   isolated temporary certification hook. It must require exact
   claim/effect/scope identity, all owned legs terminal, no active attempt,
   flat consistent execution, clear reconciliation, OPEN predecessor, and one
   fixed proof digest; it may install only the resulting venue book into a
   copied authority state.

The mandate fixture is configuration input only. The terminal fixture is
deferred M2 adapter-certification setup only. Neither grants execution,
controller, currentness, effect, claim, broker, runtime, persistence, or
actor authority. All production calls after setup remain public.

## R1 preflight requirements

The R1 candidate must prove statically that:

- exactly the two listed private setup capabilities occur only inside their
  separately named local fixture functions;
- the terminal fixture changes no authority coordinate except the copied
  authority state's venue book and restores the temporary hook;
- every terminal-closure precondition and the CLOSED postcondition are
  asserted; and
- no additional private import/access, opaque construction, post-setup
  mutation, production/API change, database/SQL/DDL, runtime, network,
  CI-workflow, M2, merge, deletion, or cleanup work appears.

R1 remains DRAFT until a new exact manifest receives an independent ACCEPT
with P0=0/P1=0. No E3 test implementation or execution is authorized before
that result.

