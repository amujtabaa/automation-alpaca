### [P1] Controls do not prove that venue checkpoint projection uses the post-write proof

- Location: `tests/execution_core/test_persistence_unit_of_work.py:2075`, `:2131`, `:5255-5263`
- Why it matters: The stale-proof root is not failure-capably protected. Both controls pass if `_store_successor_checkpoint` regresses to project using `prepared.selection_proof`: the first stubs completion, while the second supplies the same proof and ignores projector arguments. That regression recreates the real fail-closed `UNRESOLVED_EFFECTS` path.
- Resolution: Use distinct predecessor/post-write proofs and a proof-sensitive projector; drive the venue route through the real completion/checkpoint path and assert storage uses only the post-write proof.

Verdict: ACCEPT-WITH-CHANGES  
P0: 0  
P1: 1  
P2: 0  

Evidence reproduced: candidate/tree and pinned file hashes matched; exact range changed only the three allowed paths; `git diff --check` clean; authorized six-file pure pytest exited 0 at 100%; two direct controls passed.

Unverified: Fresh-file SQLite/held execution was not run, as prohibited.
