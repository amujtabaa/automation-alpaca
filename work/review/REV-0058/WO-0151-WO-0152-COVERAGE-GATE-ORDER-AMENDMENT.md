# WO-0151 / WO-0152 coverage-gate ordering amendment

Status: **AUTHORIZED — documentation reconciliation and E3 preflight only**

[FABLE - FULL - verification: DIRECT plus independent review - task: break the
E2/E3 coverage-gate ordering cycle without weakening the coverage gate]

## Authority and exact evidence

The user authorized this narrow amendment on 2026-08-07. It records exact-head
GitHub Actions push run #741, ID `31185454392`, for
`a2b84abc1914517cf591f27fb88f0b20b2a47ef7`. Python 3.11 job
`92888729393` and Python 3.12 job `92888729623` each completed the
functional/static gates and reported 5,934 passed tests, 11 skipped, and one
expected failure. Both failed only the unchanged 93% combined coverage gate at
91.34%.

## Narrow effect

1. Run #741 is positive functional/static exact-head evidence and negative
   coverage evidence; it is not an overall CI success or an E2/M1 closeout.
2. WO-0151 remains effectively `REVIEW`: its accepted E2 implementation and
   historical closeout evidence are preserved, but its effective closure now
   depends on the paired E2/E3 external gate.
3. WO-0152 may be drafted and independently preflighted while it remains
   `DRAFT`. Only an exact independent E3 `ACCEPT` with P0=0/P1=0 may satisfy
   its activation prerequisite under this amendment.
4. The 93% threshold is unchanged. The final paired E2/E3 exact-head Python
   3.11/3.12 run must pass it before either order is effectively `CLOSED` or
   M1 is claimed complete.
5. The separately retained attempt-02 diagnostic records why a 340-line E2
   private-seam coverage experiment was removed rather than expanded.

## Non-effect and stop conditions

This is not an ADR amendment, a production change, a coverage exclusion,
threshold reduction, pragma, CI-workflow change, database/SQL/DDL authority,
runtime wiring, broker/credential/network authority, M2 work, master merge,
PR, cleanup, force-push, or rebase. E3 remains test-only and must stop on a
production defect for bounded E1/E2 remediation. Two focused E3 batches that
do not meet the unchanged gate require a new adjudication rather than another
coverage treadmill.

```yaml
fable_gate:
  goal: "Let the E3 proof layer supply its own behavior-first coverage while preserving the E2 implementation and the unchanged paired 93% closeout gate."
  assumptions:
    - claim: "Run #741 is exact-head functional/static success but overall coverage failure."
      status: VERIFIED
      evidence: "Run 31185454392; jobs 92888729393 and 92888729623; 5,934 passed per job; 91.34% versus 93%."
    - claim: "WO-0151 implementation is independently accepted locally."
      status: VERIFIED
      evidence: "Remediation manifest 2538656a49ea643c6befc8e4c55882cf27534f266d2335ef4a630a73182af853 and recheck 96d08654369894eeaeda0b1b22f8e869735d179daa336c5c3e69d7f19e0e68fd."
  approach: "Reconcile present posture, preflight a bounded test-only E3 contract, and require paired exact-head closure."
  out_of_scope:
    - "Production code, coverage configuration, CI workflow, runtime, database/SQL/DDL, broker/network, credentials, M2, merge, PR, cleanup, force-push, and rebase."
  done_when:
    - behavior: "The amendment and historical evidence are mutually consistent."
      test: "Static scope, ledger, PKL, disposition, hash, and diff checks."
    - behavior: "E3 implementation begins only after independent exact RED-contract ACCEPT."
      test: "Frozen E3 review packet and result."
  blast_radius: "WO-0151/WO-0152 lifecycle and evidence records only."
```

