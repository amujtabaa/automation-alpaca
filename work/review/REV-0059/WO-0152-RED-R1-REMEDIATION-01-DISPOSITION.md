# WO-0152 R1 remediation 01 disposition

Status: DRAFT CORRECTION — NOT ACTIVE  
Date: 2026-08-07  
Work order: WO-0152  
Packet: REV-0059

## Retained R1 result

The initial R1 candidate and its independent result remain immutable retained
evidence:

- R1 contract SHA-256: 3b2ba052df61f8e128f82b4ee408568774ff8cdd62a815e4387a821ab6f9709b;
- R1 manifest SHA-256: 86ba85d531186567d289f761fca7ba1f5e658768ff1818ea4d978329b9e48888;
- R1 request SHA-256: a830a1aa75a790c4d54db008c483abe72c363fb3a9f2a16579ae1209b69a1098;
- R1 independent result SHA-256:
  880a4f2f8874d9e14a77523301a400ef84d02893d421e48822dfb648aa249408;
- R1 verdict: ACCEPT-WITH-CHANGES, P0=0/P1=2/P2=0.

R1 P1-1 correctly found that the terminal fixture’s exact AST table omitted
the one copy.copy plus one object.__setattr__(copied_authority, "venue",
applied.book) operation necessary to install the permitted copied venue result.

R1 P1-2 correctly found that an APPLIED/CLOSED result is not itself a
pre-transition proof of clear effect reconciliation. The contract prohibited
both reconciliation-history scanning and an extra private reader, so it needed
a source-proven public-chain proof before the temporary hook could be entered.

No production defect or third fixture capability was found.

## R1 remediation 01 — exact root correction

The replacement composite may add no private production name, no public API,
and no third fixture. It corrects only the two P1s:

1. add the single copied-authority venue replacement explicitly to the
   terminal fixture’s exact AST allowlist, including literal target and
   field-name negative controls;
2. make the terminal fixture own one exact straight-line public
   claim/discovery/terminal-observation/final-canonical-fact/reducer suffix
   from a fresh APPLIED claim result. The terminal observation must precede the
   final flattening canonical fact and its acquisition reduction so the final
   authority/book/execution pair is current before the private close. It must
   derive all pre-close values locally, require every suffix transition
   APPLIED, and reject before the patch/private call if any result is not exact
   or current.

The source proof starts with the accepted claim gate, which already requires
the exact target effect to be reconciliation-clean. Each permitted public
suffix input must be APPLIED; the only effect-level reconciliation append paths
return RECONCILIATION_REQUIRED rather than APPLIED. The fixture additionally
requires CONSISTENT execution and account_reconciliation_required false.
Because it owns the suffix and never accepts caller-supplied pre-close
transitions/book/execution, a splice or public reconciliation injection
changes the local chain and causes refusal before the hook/private call.

The composite must add a named public reconciliation-injection control that
produces RECONCILIATION_REQUIRED in the local suffix and proves that the
private-transition entry marker remains false, the hook is not entered, no
venue replacement is returned, and all original objects remain unchanged.

Pre-freeze source validation also established the only constructible ordering
inside that same local proof: the public terminal observation must precede the
final flattening canonical fact and its acquisition reduction. A terminal
observation alone advances the venue book without a lawful authority refresh;
the final canonical reducer result realigns authority, book, execution, and
controller before the private close. This is an exact ordering correction to
the existing P1-2 witness, not a third capability or a new authority claim.

The inherited unrelated-symbol account-history scenario remains in scope and
is constructible before target bootstrap through a public same-account sibling
BUY lifecycle. The generic target BUY refusal applies after the target’s
bootstrap/currentness reservation; it does not prohibit the earlier sibling
history.

R1 remediation 01 remains DRAFT until its replacement manifest independently
returns ACCEPT with P0=0/P1=0. No E3 test creation/execution, production/API
change, database/SQL/DDL, runtime, broker/network, CI, M2, merge, deletion,
cleanup, force-push, or rebase is authorized by this record.
