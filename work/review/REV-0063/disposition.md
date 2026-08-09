# REV-0063 disposition — remediation 01

Author: Codex local architecture and delivery seat

The reviewer-owned `result.md` is preserved unchanged. Its exact original
reviewed candidate and `ACCEPT-WITH-CHANGES` verdict remain historical evidence.

| Finding | Disposition | Root cause | Bounded correction | Re-review requirement |
| --- | --- | --- | --- | --- |
| P1-1 self-referential execution-profile commitment | Accepted and fixed | The prose said the digest committed every listed field, including the digest output itself. | Define opaque non-digest-derived IDs and domain-separated canonical commitment preimages that exclude their own output fields for both execution and market-source profiles. | Fresh manifest plus focused independent verification of constructibility and exact binding. |
| P1-2 capability evidence lifecycle cycle | Accepted and fixed | The profile digest was described as containing measured evidence even though M4 is the credential-gated producer of that evidence. | Freeze an immutable required-capability contract in the profile; bind append-only evidence to it and permit `PAPER_MUTATION_ELIGIBLE` only after M4's existing human gate supplies complete matching evidence. | Fresh manifest plus focused independent verification that no credential/API authority leaks into M2 and no in-place profile rewrite is needed. |

No P0 or P2 finding was disputed. No source, test, DDL, database, runtime,
broker, credential, dependency, workflow, or Cloud-candidate file changed.
