# WO-0152 E3 implementation remediation 01 disposition

Date: 2026-08-08  
Status: READY FOR FOCUSED INDEPENDENT RECHECK

The predecessor implementation result is retained byte-for-byte at SHA-256
`a8279d770bc226670745342f2247f480d3e35723f94cd98318fe20521d4905a9`.
Its verdict was `ACCEPT-WITH-CHANGES`, P0=0/P1=4/P2=0.

The four findings are remediated only in
`tests/execution_core/test_acquisition_stateful.py`:

1. AC-01 now records an exact E1/E2 requirement, owning test path, owning test
   name, and failure-capable assertion minimum; the inventory test parses the
   named files and refuses missing or weakened controls.
2. The R2-R5 self-source policy now pins exact zero-argument fixture signatures,
   bounded schedule-loop and direct private-mint shape, fixed duplicate-stream
   probe provenance/isolation, positive-chain exclusion, and pre-genesis
   ordering. Named mutated-source specimens kill each control family.
3. AC-04 now runs a complete 32-generation public serial lane, performs the
   three live decisions under all sixteen public history-materialization
   tripwires, and proves direct earliest/current generation lookups. A separate
   rooted late-fact lane under the same tripwire proves direct fact routing and
   exact-once economics without inventing a cross-lane production state.
4. AC-05 now uses one exact set of decisive comparisons consumed by the real
   long-sequence behavior proof. Removing any comparison makes the named
   omission mutant fail.

Fresh evidence after remediation:

- complete E3 module: exit 0;
- full repository: 5,977 passed, 11 skipped, 1 xfailed, 19 warnings, exit 0;
- lines: 24,825/26,530 = 93.573313%;
- branches: 8,461/9,920 = 85.292339%;
- coverage JSON SHA-256:
  `220e370e82d99b61962e0d4b7460fe711cd97ad2f430bce6b7c3c0484f0e36f2`;
- Ruff, exact changed-file format, Mypy, and ordinary diff checks: pass.

No production file changed for this remediation. The focused reviewer must
recheck only the four predecessor P1 findings against the replacement manifest.
P0=0 and P1=0 are required before publication. Exact-head Python 3.11/3.12 CI
and later records-only closeout remain unsatisfied.
