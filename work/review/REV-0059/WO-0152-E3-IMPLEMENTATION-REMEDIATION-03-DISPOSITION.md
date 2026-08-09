# WO-0152 E3 implementation remediation 03 disposition

Date: 2026-08-08
Status: READY FOR FINAL FOCUSED INDEPENDENT RECHECK

The remediation-02 result is retained byte-for-byte at SHA-256
`191a2641766e83c93059267df12f1c43f962398f3eb3eb150259c649e9fafccc`.
Its verdict was `ACCEPT-WITH-CHANGES`, P0=0/P1=3/P2=0. That result is a
provisional diagnostic written immediately before the implementation seat's
explicit hold; it remains retained negative evidence and is not rewritten.

This third and final focused remediation changes only the E3 test module. It
closes the three residual proof gaps at their owning semantic controls:

1. The source-policy verifier rejects direct `patch(...)`, every comprehension
   form in the fixed mandate-schedule fixture, and any private venue-reducer
   call outside the one exact terminal-certification site. Three isolated
   source mutants prove those routes fail independently.
2. E1 AC-01 maps to the actual known-answer/replay/coordinate owner,
   `test_identity_known_answers_replay_and_well_formed_variants_are_data_only`,
   and pins its genesis and successor known answers, replay equalities,
   coordinate sensitivity, and canonical variants. Assertion erasure removes
   every required predicate.
3. The real 32-generation oracle now consumes each public binding view's
   predecessor-or-genesis head, emergency-recovery compatibility commitment,
   and aggregate binding commitment in addition to application, scope,
   generation, ordinal, capacity, dual-mandate binding, one-LIVE, economics,
   codec, and bounded-routing conclusions. Every decisive comparison has both
   omission and false-value mutants.

Fresh exact-candidate evidence:

- complete E3 module: 18 passed, exit 0;
- focused three remediation controls: 3 passed, exit 0;
- coverage-validator controls: 11 passed, exit 0;
- full repository: 5,977 passed, 11 skipped, 1 xfailed, 19 warnings, exit 0;
- lines: 24,825/26,530 = 93.573313%;
- branches: 8,461/9,920 = 85.292339%;
- coverage JSON SHA-256:
  `bf4fa815cd1679c50d15af1eb1bc67dda5302de48ea720c66eb92bc4deb8ac47`;
- Ruff check/format, Mypy on 90 source files, six import contracts, the
  61-case R2 oracle, install/version/ledger/PKL/disposition, and ordinary diff
  checks: pass.

No application production file changed in any WO-0152 implementation
remediation. The final focused reviewer must recheck only the three
remediation-02 P1 findings against the replacement manifest. P0=0 and P1=0
are required before publication. Exact-head unchanged Python 3.11/3.12 CI and
records-only closeout remain unsatisfied.
