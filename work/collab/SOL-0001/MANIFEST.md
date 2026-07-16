# SOL-0001 — rival sell-side policy manifest

**Status:** implementation and conformance evidence green; packet finalization pending  
**Frozen base:** `5a194104ee5d542e0b838929dacee7008c6d3336` (`5a19410`)  
**Branch:** `collab/sol-0001`  
**Final `impl/sol_policy.py` SHA-256:** `<FINAL_SHA256>`

Replace the SHA placeholder only after every SOL-0001 file is final, then rerun the commands
below against that exact file. Numeric policy constants are harness-tunable defaults, not
calibrated claims or trading recommendations.

## Packet files

Present in the implementation packet:

- `MANIFEST.md` — packet index, evidence, reproducible commands, and limitations.
- `impl/sol_policy.py` — complete rival `decide()` implementation behind the frozen WO-0018
  public contract.
- `impl/test_sol_policy.py` — independent deterministic and Hypothesis tests for the rival.
- `impl/sol_conformance_plugin.py` — pre-collection adapter that binds the incumbent portable
  tests to the rival `decide()` and reports the tested file hash.
- `findings.md` — evidence-tagged incumbent contract defects and empirical hypotheses routed out
  of this implementation lane.

Required companion deliverables `design-memo.md` and `tapes.md` are pending packet finalization.
The finalizer must verify they are present before committing. Generated `__pycache__`,
`.pytest_cache`, and Hypothesis database files are not packet artifacts.

## Design synopsis

The rival preserves the frozen return vocabulary and reuses
`app.sellside.policy.validate_action`, while deliberately changing the policy mechanism:

- quote-mid 30-second structural bars prevent isolated off-market prints from becoming highs;
  cumulative-volume resets re-baseline rather than creating false volume;
- median true-range ATR, signed path efficiency, ATR expansion, and volume behavior classify the
  five required regimes;
- urgency is calculated causally at each completed bar, the mutable current bar is excluded from
  the ratchet, and the working stop is monotone across the tape and restored from event history;
- spread and gap stress widen uncertainty within approved bounds and suppress opportunistic
  tranches; participation sizing clamps and emits `ClampNote` metadata;
- the envelope's own ordered history drives cooldown, replace budget, prior stop, tranche, and
  max-one-child accounting; pending cancel and ambiguous child states block new action; a
  cancelled/unfilled tranche can retry, while a deduped positive fill consumes its entitlement;
- wrong-symbol, stale, non-finite, nonpositive, crossed, off-quote, or non-monotonic latest data
  fails closed before it can drive a plan.

This packet contains policy research code only. It makes no venue call and does not modify order
submission, cancel/replace execution, kill switch, manual flatten, stores, schemas, broker
adapters, event-log truth, `app/**`, or `tests/**`.

## Red → green evidence

The first two red results below are contemporaneous development-loop evidence; they are retained
because a test that cannot fail is a defect. They are not re-created against the final file.

1. **RED — import seam.** Initial collection of `impl/test_sol_policy.py` failed with:

   ```text
   ModuleNotFoundError: No module named 'sol_policy'
   ```

   The implementation module was then added behind the test module's explicit local import seam.

2. **RED — participation edge.** The next run had one failure: a scenario expected an actionable
   plan but received `NoAction(reason=NO_LIQUIDITY)`. Recent-volume accounting was incorrectly
   anchored to injected decision time, which was later than the synthetic tape. It was corrected
   to anchor the participation window to the latest accepted observation, preserving the
   distinction between zero capacity and a positive capped quantity.

3. **GREEN — independent rival checkpoint.** The next complete rival run passed all 29 tests:

   ```text
   .............................                                            [100%]
   ```

4. **GREEN — expanded participation checkpoint.** Two additional protective-participation
   regressions were subsequently added, producing a 31-test green checkpoint:

   ```text
   work/collab/SOL-0001/impl/test_sol_policy.py: 31
   ...............................                                          [100%]
   ```

5. **GREEN — current independent rival suite.** Tranche retry and deduped-fill accounting
   regressions were then added. Fresh collection and execution now show 33 tests:

   ```text
   work/collab/SOL-0001/impl/test_sol_policy.py: 33
   .................................                                        [100%]
   ```

6. **GREEN — static checks.** Fresh output:

   ```text
   All checks passed!
   3 files already formatted
   Success: no issues found in 2 source files
   ```

7. **GREEN — portable rival-facing WO-0018 conformance.** Fresh output for the 35 nodes that
   actually bind and exercise the rival `decide()`:

   ```text
   ...................................                                      [100%]
   ```

8. **GREEN — full prescribed hybrid run.** Fresh output:

   ```text
   ....................................................                     [100%]
   ```

   This is **35 rival-facing + 17 incumbent/shared = 52 total**, not 52 rival tests. The 17 are:
   11 regime tests bound directly to incumbent classifier/trail internals, two incumbent
   working-stop properties, two hygiene tests that scan `app/sellside/**` and `.importlinter`,
   and two tests of the shared incumbent `validate_action`.

## Reproducible commands (PowerShell, repository root)

Common setup:

```powershell
$python = (Resolve-Path ".\.venv-review\Scripts\python.exe").Path
$impl = (Resolve-Path "work\collab\SOL-0001\impl").Path
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPATH = $impl
$env:SOL_POLICY_TARGET = (Resolve-Path "$impl\sol_policy.py").Path
Get-FileHash -Algorithm SHA256 $env:SOL_POLICY_TARGET
```

Static checks:

```powershell
$files = @(
  "$impl\sol_policy.py",
  "$impl\test_sol_policy.py",
  "$impl\sol_conformance_plugin.py"
)
& $python -m ruff check $files
& $python -m ruff format --check $files
& $python -m mypy --follow-imports=skip `
  "$impl\sol_policy.py" `
  "$impl\sol_conformance_plugin.py"
```

Independent rival tests:

```powershell
$rivalTemp = Join-Path ([IO.Path]::GetTempPath()) (
  "sol0001-rival-" + [guid]::NewGuid().ToString("N")
)
& $python -m pytest -q -p no:cacheprovider `
  --basetemp $rivalTemp `
  "$impl\test_sol_policy.py"
```

Portable rival-facing conformance — exactly 35 selected nodes:

```powershell
$facingTemp = Join-Path ([IO.Path]::GetTempPath()) (
  "sol0001-facing-" + [guid]::NewGuid().ToString("N")
)
& $python -m pytest -q -p no:cacheprovider -p sol_conformance_plugin `
  --basetemp $facingTemp `
  tests\test_wo0018_sellside_policy.py `
  tests\test_wo0018_sellside_properties.py `
  -k "not validator and not working_stop_is_monotone_over_a_growing_tape and not trail_floor_holds_at_every_step"
```

Full prescribed hybrid run — 52 total, with the 35/17 attribution above:

```powershell
$hybridTemp = Join-Path ([IO.Path]::GetTempPath()) (
  "sol0001-hybrid-" + [guid]::NewGuid().ToString("N")
)
& $python -m pytest -q -p no:cacheprovider -p sol_conformance_plugin `
  --basetemp $hybridTemp `
  tests\test_wo0018_sellside_policy.py `
  tests\test_wo0018_sellside_regime.py `
  tests\test_wo0018_sellside_hygiene.py `
  tests\test_wo0018_sellside_properties.py
```

## Limitations and interpretation

- The 52-node hybrid result must never be presented as 52 rival tests; 17 nodes prove only
  incumbent/shared behavior.
- The portable policy tests also pin some incumbent scenario choices, so passing them is useful
  compatibility evidence but not a design-neutral empirical comparison.
- Candidate trail-floor behavior is not observable through the frozen `decide()` return type in
  every state. The rival suite therefore checks both its internal candidate result and the
  black-box monotonic stop reported by `decide()`.
- Tests use deterministic synthetic, paper/simulated tapes only. They do not establish live-market
  performance, fill quality, or parameter fitness for thin extended-hours penny stocks.
- No W4 pessimistic-fill replay or five-metric regime-bucket bake-off has run here. Mechanism
  selection remains an empirical W4 decision.
- Engine atomicity, kill/flatten precedence, durable event parity, quarantine recovery, and actual
  venue behavior are outside this pure-policy lane and are not proven by this packet.
