# CONSULT-0001 — WO-0168c architecture consultation record (2026-08-26)

Blinded two-model consultation commissioned by Ameen Mujtabaa to resolve the WO-0168c
review treadmill (REV-0079…REV-0105, non-converging; REV-0105 BLOCK P0=7/P1=5). Each model
answered independently, first-pass, without seeing the other's memo. This folder is decision
provenance: why the scanner was deleted and the hybrid gate adopted. Files are immutable evidence.

## Artifacts

| File | Author | SHA-256 |
| --- | --- | --- |
| `claude-first-pass-memo.md` | Claude (Fable 5), blinded first pass, frozen | `1f60d2aff3e85437b399fe86e9fba443dc8bbdd671998982e2a45514658e9cf7` |
| `memo-comparison.md` | Claude, disclosed second-pass reconciliation | `a5d25e7acd2effc7cf7975c6126f5a373f2dee989d1ed29dfdb0cf44dc5ed34a` |
| ChatGPT memo (not stored here) | ChatGPT Pro, clean context | `4360d614c8a0498d3984fddb41798b2ca181659a3630b2924a32ce4392268ab6` |

The ChatGPT artifact is `WO-0168c_ARCHITECTURE_DECISION_MEMO_v1.1.0_CONSOLIDATED.md` (1,355
lines, "ADEG-1.1"), retained by Ameen outside the repository; the hash above pins its identity.

## Outcome

Both models independently reached the same root cause (the scanner's claim — sound static
verification of arbitrary Python — is unbounded), the same disposition (delete, don't repair),
the same threat model (accidents in scope; deliberate evasion and host owner out), and the same
stop-rule philosophy. They diverged on enforcement locus and machinery size: ChatGPT proposed an
external two-plane execution platform (~1,200–2,050 SLOC + Docker); Claude proposed ~400 lines of
in-repo boundary checks around the existing runtime gates. Ameen ratified the hybrid on
2026-08-26 ("Ratified: hybrid points 1–10; scanner deletion approved; prohibition re-scoped per
point 5"), adopting from ChatGPT the expected-digest lifecycle separation (ADEG §7.5), held-suite
relocation, and counted-attempt approvals; and from Claude the minimal in-repo boundary layer,
restored pytest, GitHub-as-external-enforcement, and DDL-review-first sequencing. Implementation:
`work/active/WO-0168d-m2-i3-5-hybrid-gate-simplification.md`. Codified policy: ADR-023.
