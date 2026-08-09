# WO-0152 E3 implementation evidence

Date: 2026-08-08

Branch: `codex/arch-reset-2026-07-r1`

Base before the E3 candidate: `ae626f56fb05c09b312a7383326ebbf9ba584cd3`

## Behavior proof

The test-only E3 module now covers:

- a fixed immutable 32-mandate pre-genesis schedule and a 32-generation serial
  aborted-successor trace with one LIVE generation;
- public A/B/C rooted lifecycle, first/follow-on and retired FILL/CORRECT/BUST
  facts, late-A recovery, stale-claim refusal, and B first-fill after R13;
- deterministic seeded state-machine traces and schema-neutral replay/restart
  observer equivalence with corruption/reordering refusal;
- public create/claim refusal and venue duplicate/replay/reorder/fork matrices;
- semantic protection rebase and atomic single-flight BUY preemption;
- an exact 16-target history-materialization tripwire around live decisions;
- failure-capable source-policy and observer mutations;
- bounded test-only configuration and terminal-certification setup exceptions
  frozen by the accepted R2-R5 contract.

No application production file changed in WO-0152.

## Coverage-gate correction

The independently accepted R1 gate manifest is
`230a5ec0d5aeccc68518a7def172e49d52aad7e22e218da692aa04a54aec8309`;
result SHA-256
`d8931dda45422622c668927ba5c0777b5c4dda836ddcc17b1c2354f0bbad2d5c`
is `ACCEPT`, P0=0/P1=0/P2=0. It enforces independent `93.00%` line and
`85.25%` branch ratchets. Eleven focused validator tests passed, including CI
command/order pins, exact thresholds, line-only and branch-only failures,
negative/type/non-branch/impossible totals, and unreadable/invalid JSON.

## Fresh full local evidence

Command:

```text
BROKER_ADAPTER=mock python -m pytest --basetemp=.pytest-e3-ci-20260808-03 --cov=app --cov-branch --cov-report=term-missing --cov-report=json:coverage-e3-final-r1.json
```

Result: exit 0; 5,977 passed; 11 skipped; one expected failure; 19 warnings;
38m20s. Exact JSON SHA-256:
`220e370e82d99b61962e0d4b7460fe711cd97ad2f430bce6b7c3c0484f0e36f2`.

- lines: 24,825 / 26,530 = `93.573313%` (`>= 93.00%`);
- branches: 8,461 / 9,920 = `85.292339%` (`>= 85.25%`).

The separate validator exited 0 and printed both passing conclusions.

## Static and governance evidence

- Ruff check: pass;
- Ruff format on every changed Python file: pass;
- Mypy: 87 application source files, zero issues;
- import-linter: 123 files, 634 dependencies, six contracts kept;
- R2 conformance oracle: 61 passed;
- AI-OS install, version, ledger, PKL, and disposition checks: pass;
- contamination guard and ordinary diff check: pass;
- repository-wide Ruff format check reported ten unrelated pre-existing
  deviations; none is an allowed WO-0152 path and none was reformatted.

The local `.pytest_cache` ACL warning is non-functional and did not alter the
exit result; isolated `--basetemp` prevented the protected global pytest temp
tree from affecting fixtures.

## Independent implementation remediation 01

The first final review result is retained at SHA-256
`a8279d770bc226670745342f2247f480d3e35723f94cd98318fe20521d4905a9`
with `ACCEPT-WITH-CHANGES`, P0=0/P1=4/P2=0. The remediation is test-only and
closes its four evidence gaps with an exact E1/E2 ownership inventory,
failure-capable source-policy specimens, a public 32-generation boundedness
proof combined with a rooted retired-fact route, and a real decisive-comparison
oracle whose omission mutants fail. The complete E3 module and the fresh full
repository run above both passed after these changes. No production file was
changed for the remediation.

## Remaining gates

This evidence does not claim M1 closeout. The exact implementation candidate
requires fresh independent `ACCEPT`, normal commit/push, and successful
unchanged Python 3.11 and 3.12 GitHub Actions on that exact SHA. A later
documentation-only exact-head reconciliation must itself receive successful
dual-version CI before effective WO-0151/WO-0152 closure.

## Independent implementation remediation 02

The first focused remediation result is retained at SHA-256
`1fa71ac536e339b602255d17ef511c32415e5b9353c418af791b3426caba3091`
with `ACCEPT-WITH-CHANGES`, P0=0/P1=3/P2=0. It closed AC-04 and retained
three test-evidence gaps: incomplete exact setup privilege controls, an AC-01
inventory that did not prove every frozen criterion's semantic assertions,
and AC-05 labels that did not yet prove head advancement, generation-local
capacity, or identity coordinates.

The second test-only remediation closes those three gaps. Four new mutated
source specimens exercise unauthorized copy, patch, setter, and schedule-loop
control flow. AC-01 maps all fifteen frozen E1/E2 acceptance criteria to exact
owning tests and semantic predicates, and assertion-erasure mutants remove
every required predicate. AC-05 now verifies 32 unique controller heads,
terminal ordinal, one LIVE record, per-generation capacity and mandate-binding
commitments, and every generation's application/scope/ordinal coordinates.

Fresh exact-candidate command:

```text
BROKER_ADAPTER=mock python -m pytest -q --basetemp=.pytest-e3-ci-20260808-05 --cov=app --cov-branch --cov-report=term --cov-report=json:coverage-e3-final-r3.json
```

Result: exit 0; 5,977 passed; 11 skipped; one expected failure; 19 warnings.
Exact JSON SHA-256:
`331b6886b8aa55bc1dd512074e67e5faa4578df8f701a1d33efd177966ae06bc`.

- lines: 24,826 / 26,530 = `93.577083%` (`>= 93.00%`);
- branches: 8,462 / 9,920 = `85.302419%` (`>= 85.25%`).

The independent ratchet validator, complete E3 module, eleven validator tests,
Ruff check/format, and MyPy across 90 source files all passed. This remains a
candidate, not M1 closeout: focused independent acceptance, exact publication,
and unchanged exact-head Python 3.11/3.12 CI are still mandatory.

## Independent implementation remediation 03

The remediation-02 reviewer result is retained at SHA-256
`191a2641766e83c93059267df12f1c43f962398f3eb3eb150259c649e9fafccc`
with `ACCEPT-WITH-CHANGES`, P0=0/P1=3/P2=0. The final test-only remediation
rejects the three remaining lexical setup bypasses, maps E1 AC-01 to its exact
known-answer/replay/coordinate owner, and consumes every public generation
binding coordinate in the real 32-generation oracle with both omission and
false-value mutants.

Fresh exact-candidate command:

```text
BROKER_ADAPTER=mock python -m pytest -q --basetemp=.pytest-e3-ci-20260808-06 -p no:cacheprovider --cov=app --cov-branch --cov-report=term --cov-report=json:coverage-e3-final-r4.json
```

Result: exit 0; 5,977 passed; 11 skipped; one expected failure; 19 warnings.
Exact JSON SHA-256:
`bf4fa815cd1679c50d15af1eb1bc67dda5302de48ea720c66eb92bc4deb8ac47`.

- lines: 24,825 / 26,530 = `93.573313%` (`>= 93.00%`);
- branches: 8,461 / 9,920 = `85.292339%` (`>= 85.25%`).

The complete 18-test E3 module, three focused remediation controls, eleven
coverage-validator tests, Ruff, Mypy across 90 source files, six import
contracts, 61 R2 oracle cases, install/version/ledger/PKL/disposition checks,
and ordinary diff check all passed. No application production file changed.
This remains a candidate until final focused independent acceptance, normal
publication, and exact-head unchanged Python 3.11/3.12 CI succeed.
