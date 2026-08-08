# REV-0048 Addendum 03 — independent review result

**Reviewed diff:** `a7dbc0390a0cf3f06c0769b29389de34ea2fed10..ba70c46b05f3ec3d653159f00193c03711ba82e7`

## P1 — The replacement guard misses retained-leaf mutation

**Location:** `tests/execution_core/test_fill_position_stateful.py:235-238`; supporting
mechanism at `app/execution_core/fills.py:425-431`, `:1066-1080`, and `:1378-1393`.

**Impact:** `_apply()` now compares cached component commitments instead of an independently
derived semantic snapshot. In a reversible exact-replay probe, a hostile reducer used
`object.__setattr__` after its second call to change the retained exact `RootHead.quantity` from 3
to 10. Both reducer results shared the mutated predecessor, while the radix node's cached value and
ancestor commitments remained unchanged, so `_apply()` returned without raising. Fresh probe
output was:

```text
root_head_mutant=SURVIVED
actual_semantics_changed=True
root_commitment_unchanged=True
root_binding_repr_unchanged=True
cached_signed_quantity=3; actual_head_quantity=10
restored=True
```

The old `repr(root_heads)` snapshot changed under this mutation and would have killed it. The same
cached-leaf gap applies to retained `SeenFact` values and position persistent-sequence leaves. This
disproves the requested claim that malicious component-state mutation remains detected and weakens
the assertion this repair is required to preserve. It is a WO stop even though no production file
changed.

**Resolution:** Add this retained-leaf mutation as a failing regression pin, then use a
Python-3.11-safe semantic fingerprint independently re-derived from the actual retained leaves. If
constant-work detection remains mandatory, first make it impossible for retained semantic values
to change while cached commitments remain unchanged; cached commitments alone cannot prove this
against arbitrary in-place leaf mutation. Re-run the focused gates and obtain a new independent
review before exact-head closeout CI.

## Fresh verification

- The three nodes that failed run `30746436486` and the complete stateful file passed locally under Python 3.12.13 (`3/3` and `7/7`). Ruff check, Ruff format-check, `git diff --check`, and the WO scope checker passed.
- GitHub run `30746436486` was independently inspected: it checked out `4b9b47de1936a179478f1c638c4872a4b0935719`; Python 3.11.15 job `91492722592` failed the three named nodes at old `_apply()` line 234 while evaluating `repr(root_heads)`, and Python 3.12 job `91492722638` passed.
- The exact repair diff changes only the stateful test and WO FIX record; `app/**` is unchanged. The test and preserved coverage artifact sizes/hashes match the implementation evidence. The PKL posture keeps WO-0146 effectively in `REVIEW`, and no WO-0147 work-order file exists.
- The implementation-seat R2/full-repository claims were not independently rerun. No local Python 3.11 runtime was available. Successor exact-head Python 3.11/3.12 CI is external and **UNVERIFIED**.

## Verdict

**BLOCK** — the central immutable-input assertion is bypassable, which is an explicit WO stop. External successor CI cannot clear this finding.
