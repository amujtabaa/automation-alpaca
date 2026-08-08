# ADR-023 R1 proof-isolation successor review

## Immutable review boundary

- Parent: `3f54df45d7234e0d5f678522686730dc1f374a60`
- Candidate: `b7ae0d7db900557d54784ede2a27a7df65be0ae4`
- Exact candidate paths:
  - `tests/execution_core/test_import_boundary.py`
  - `tests/execution_core/test_protection.py`
  - `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md`

Review only this immutable delta. Exclude the dirty application working tree and every preserved
untracked artifact from candidate evidence.

## Required independent determination

Determine whether the candidate closes both P1 findings in the preceding review:

1. A complete fragment with the exact derived occurrence field must require one exact lifecycle
   setter even when `__post_init__` is omitted or renamed, while a complete fragment with no
   occurrence class and a non-complete standalone field fixture remain valid.
2. The exit-provenance commitment case must vary only `_exit_provenance` plus the resulting main
   commitment, and an omitted provenance commitment part must be failure-capable.

Also review the new coordinated-identity RED pin. It must fail the pre-correction implementation
when identity text plus seal, or cached bytes plus seal, are changed inconsistently. Its end-to-end
case must prove that this forgery can alter exact-replay classification unless state authentication
fails closed. Confirm the associated import allowance names only one canonical private identity
helper and does not admit arbitrary aliases or calls.

Author-side focused evidence is 27/27 with the excluded in-progress application. The identity test
was separately observed RED against the pre-correction implementation. Reproduce only proportionate
pure/static evidence; do not run database, SQL, broker, network, credential, runtime-wiring, M2,
merge, deletion, or cleanup activity.

Write findings only to `result.md`, with severity, file and line, concrete impact, and smallest root
correction. End with `ACCEPT`, `ACCEPT-WITH-CHANGES`, or `BLOCK`, explicit P0/P1/P2 counts, and any
unverified claim. Do not edit `request.md`, application code, tests, ADRs, PKL, ledger, or the work
order.
