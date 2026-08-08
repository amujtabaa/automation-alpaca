# WO-0148 final R2, repository, and coverage evidence

Date: 2026-08-04

## Scope and preflight

- Starting tracked `HEAD`: `6696743337f9eae8dad0567be6d49333d9d100cc`.
- Branch: `codex/arch-reset-2026-07-r1`.
- `BROKER_ADAPTER=mock`; `MARKET_DATA_FEED=mock`.
- `ALPACA_PAPER_API_KEY`, `ALPACA_PAPER_API_SECRET`, `APCA_API_KEY_ID`, and
  `APCA_API_SECRET_KEY` were absent.
- The unchanged `.github/workflows/ci.yml` SHA-256 was
  `5F6C0386B8955E01A34144BBD9D3DCEC5CD39100D023A712EEAFC6082FC8AC2F`.
- Existing fixtures were authorized to execute SQL/DDL only against disposable test-only SQLite
  files. No credential, Alpaca/broker/network call, persistent application database, runtime
  wiring, or CI-workflow change was used.

## Preserved non-acceptance sequence

1. `adr023-root-final-gate-01`: the R2 oracle passed 61/61; the first full run timed out after
   1,200.8 seconds at approximately 30% without a reported test failure. It is incomplete evidence.
2. `adr023-root-final-gate-02`: all 5,846 tests completed with zero failures/errors and 12 skipped,
   but raw combined coverage was `92.98798233300236%`, four covered units short of the unchanged
   93% floor. Coverage JSON SHA-256:
   `F37213BCF058227EF7E6BA076BADE17341D09987FD78B7715751C5D5C71581D9`; JUnit SHA-256:
   `79FEF03EF552F5D2557BD23F76043E26539C94836CEA412F918BB1E575968BCB`.
3. `adr023-root-final-gate-03`: an initial runtime-envelope test produced 5,847 tests with zero
   failures/errors, 12 skipped, and `93.00510151675968%` coverage. Independent bounded review then
   found its string counterfeit could not distinguish exact `bytes` from `isinstance`; this run is
   superseded. Coverage JSON SHA-256:
   `15DEDD2F53362927E6D98C77A2594C9BF21C538047F1EEFBCFB7BFBD8F87D04C`; JUnit SHA-256:
   `B2199895CDABF8D1F38C2618C4EEB4A37FD1B087CF61FADC61D58008C8E12582`.
4. `adr023-root-final-gate-04`: the corrected exact-bytes-subclass test completed 5,847 tests with
   zero failures/errors and 12 skipped, but coverage was `92.99825384325675%`, one unit below the
   floor. Exact report comparison showed only an unrelated existing `app/store/core.py` branch
   varied from gate 03, moving two covered units. Coverage JSON SHA-256:
   `E6AC5879A9B00D969D1E6564DFA5CAD890D4068DC38533D930CC43BFCAB744B4`; JUnit SHA-256:
   `684E55A8D4DED939C9792823F108DEBFAB8E4095D76CFBE6C8370218616B8FC7`.
5. `adr023-root-final-gate-05`: targeted measurement confirmed the projection-seal control added
   two deterministic protection-runtime units; no full-suite result from this candidate is used.

No non-acceptance or superseded result is relied upon for closeout.

## Root correction and independent review

The final test `test_runtime_rejects_non_exact_protection_envelopes` covers four coherent runtime
boundaries. It uses authentic-payload `NonExactBytes(bytes)` counterexamples for the three exact
byte envelopes and a non-exact object for the proof envelope:

- the private transition proof commitment;
- the private projection seal;
- the protection-state commitment; and
- a non-exact proof object.

The focused run executes the formerly missing error lines 700, 1000, 2316, and 2319 and their four
corresponding branch arcs, adding eight deterministic combined units. The bounded independent
review preserved its initial P1, reviewed each correction, and ended `ACCEPT`, P0=0/P1=0/P2=0.
Separate in-memory weaker-guard counterfactuals for the proof commitment, projection seal, and state
commitment each made the focused test fail. Review SHA-256:
`0593DB346D234464D4CB222F42BF192BD6E2294CA7EC3BC591D5D7606E10B1EA`.

## Definitive exact-candidate results

Evidence root: `work/review/REV-0050/evidence/adr023-root-final-gate-06/`.

- Focused runtime-envelope test: 1/1 pass.
- R2 conformance oracle: 61/61 pass.
- Full repository JUnit: 5,847 tests, zero failures, zero errors, 12 skipped, 1,601.407 seconds.
- Statements: 19,985/21,081 covered.
- Branches: 7,181/8,126 covered.
- Combined: 27,166/29,207, or `93.01194919026261%`.
- Configured floor: unchanged 93%; passed.
- Full command wall time: 1,604.9 seconds.

Artifact SHA-256 values:

- `coverage.json`:
  `5D52BE328816C7420A3BA5F8FFA4D89FF0417F2BEFB9C619647F9E61387FDE61`
- `full.junit.xml`:
  `867322EF47D13590A264195D545594813E8DC3413AE565D13494720AB76A7B93`
- `r2.junit.xml`:
  `C8A91FBE8B78F8CFF43789066CF79C3F0F3E213C5C647D9A1570C816C52F8E76`
- `coverage-targeted.json`:
  `F248A944A1F52A9F2FFB539E9209378A8D991AB1FD2ACEAED179A8FBFAA4D065`

## Final governance and static checks

- Work-order disposition, append-only ledger, PKL, Fable DONE, AI-OS install, and AI-OS version
  checks: pass.
- Exact activation-base work-order scope and `git diff --check`: pass.
- Ruff repository lint and changed-test format check: pass.
- Mypy: 86 application source files, zero issues.
- Import Linter: 6/6 contracts kept.
- Python 3.11 static grammar parse for the changed test: pass. A local Python 3.11 interpreter was
  unavailable, so actual Python 3.11 execution remains assigned to the exact-head CI job.
- All nine auxiliary registered worktrees: clean. The primary worktree contains only the intended
  staged closeout plus preserved unstaged evidence artifacts.
- Final bounded staged-closeout review: `ACCEPT`, P0=0/P1=0/P2=0; external exact-head CI was the
  only unverified item and remains explicitly deferred.

## Acceptance boundary

This proves the local pure/test candidate only. WO-0148's filed `CLOSED` metadata remains
effectively `REVIEW` until the immutable closeout `HEAD` passes both unchanged exact-head GitHub
Actions Python 3.11 and 3.12 jobs. No WO-0149 activation, M2 implementation, runtime wiring,
persistent application-database work, broker activity, merge, deletion, or cleanup is implied.
