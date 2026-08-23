# REV-0075 R9 test-critic result

Exact candidate reviewed: `5932294ee28a848c58aa6bcfda665b96c42526e4`, tree
`4b51e1c60d59d7d497f461cabae0b3fb574e10c5`.

## P0 — Reported `git diff --check` evidence is false

Location: `work/review/REV-0075/disposition-r6.md:3`.

Evidence: `git diff --check d51ade6b402470a7d76858dc84357e9fd9647d58
5932294ee28a848c58aa6bcfda665b96c42526e4` exited 1 for trailing whitespace
on that line.

Impact: the packet's claimed green static evidence is not reproducible for the
exact candidate.

Smallest complete correction: remove the trailing spaces (or correct the
evidence claim), then rerun and record the exact command/result.

## P1 — Execution decoder accepts a re-signed self-consistent state/proof pair

Locations: `app/execution_core/persistence/checkpoint_codec.py:318`,
`app/execution_core/position.py:690` and `:1243`; inadequate control at
`tests/execution_core/test_position.py:418`.

Mechanism: `_M2ExecutionObservationProof._is_authentic()` recomputes only its
own commitment. Replacing wire `raw_quantity` or a fully shaped unbound
`tail_fold_input`, recomputing the resulting state commitment, assigning it to
`proof.state_commitment`, and recomputing the outer proof commitment preserves
the map witnesses. The decoder then accepts the altered state because it only
compares that re-signed proof commitment to the decoded commitment.

Impact: a forged checkpoint can hydrate execution scalar/tail members that are
not authenticated by the direct-current proof.

Smallest complete correction: bind the execution proof to an independently
authenticated current-state source/selection, rather than only a recomputable
`state_commitment`; add pure controls that re-sign the proof after changing
`raw_quantity` and a complete but wrong tail predecessor proof.

## P1 — Authority semantic keys can bind across application generations

Location: `app/execution_core/persistence/records.py:366`.

Mechanism: an authority-key document with coordinates
`(application A, profile, scope)` is accepted when
`input_application_generation_id` is application B. The validator checks key
coordinates and domain but does not require those application-generation values
to match.

Impact: an authority collision-domain key can point at a durable input from
another application generation, violating the frozen coordinate/owning-input
binding and enabling cross-generation semantic misclassification.

Smallest complete correction: for authority kinds require
`key_application_generation_id == input_application_generation_id`; add a
negative test changing only the owning input application generation.

## Verified prior concerns

- Protection expected-wire vectors no longer reuse production policy or
  optional-M1 codecs, and the corpus includes distinguishable real flat,
  formula-unavailable, halted, and exhausted states.
- Execution enum/fixed-order controls, flat/pending null forms, copied-shape
  rejection, and post-construction state mutation rejection are present.
- Direct-row radix membership is checked through the owner seam with complete
  labelled-child witnesses.

R8 state authentication is not fully resolved because of the re-signed proof
bypass above.

## Verdict

**BLOCK** — P0=1, P1=2, P2=0.

Unverified: author-reported pure tests, Ruff, format, and mypy were not rerun
because the review checkout was not the exact candidate tree. No SQLite,
database creation, runtime composition, network, broker, or order code was
invoked.
