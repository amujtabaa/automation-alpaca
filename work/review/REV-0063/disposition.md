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

## Remediation-01 focused re-review disposition

`result-remediation-01.md` is preserved unchanged. Its P1-2 accepted the
capability lifecycle correction. Its remaining P1-1 is accepted and corrected:
the proposed ADR now defines exact domain framing, length prefixes, field order,
text normalization/encoding, opaque-ID and digest bytes, origin canonicalization,
lowercase output, and self-output exclusion for both commitment algorithms.
The correction also requires independent literal known-answer and mutation
controls before M2 implementation reliance. It changes no M1/M2 operating
authority or forbidden surface. A fresh independent remediation-02 review must
verify constructibility and absence of safety regression before any `ACCEPT`.

## Remediation-02 focused re-review disposition

`result-remediation-02.md` is preserved unchanged. Its two P1 findings are
accepted and corrected without disputing the reviewer evidence:

| Finding | Disposition | Root cause | Bounded correction | Re-review requirement |
| --- | --- | --- | --- | --- |
| P1-1 origin host canonicalization was implementation-selected | Accepted and fixed | The origin rule specified scheme, broad host case, and port treatment but not a complete accepted host language. | Define a lowercase ASCII DNS-label grammar, total/label lengths, no IP or encoded forms, and an explicit 1--65535 non-default port range; require rejection before any URL-library normalization. | Fresh reviewer independently tests the stated boundary spellings and verifies byte-stable profile framing. |
| P1-2 ratification named a historical negative result | Accepted and fixed | The prebuilt request referenced `result.md` despite later immutable remediation addenda. | Name `result-remediation-03.md` as the only terminal accepting result; preserve every earlier result as negative provenance, and reconcile README/manifest text. | Fresh reviewer verifies the named terminal artifact, hash routing, provenance retention, and no ratification bypass. |

The subsequent focused review must write only
`result-remediation-03.md`. It must return `ACCEPT`, P0=0, P1=0 before this
work stops for human ratification; otherwise no human gate may be presented.

## Remediation-03 focused re-review disposition

`result-remediation-03.md` is preserved unchanged. Its P1 is accepted and
corrected without disputing the reviewer evidence:

| Finding | Disposition | Root cause | Bounded correction | Re-review requirement |
| --- | --- | --- | --- | --- |
| P1 account coordinate could not prove selected provider account | Accepted and fixed | `account_identity` was called opaque and activation-minted, leaving no equality bridge to the exact provider account required by ADR-022. | Define `account_identity` as a domain-separated immutable commitment to exactly one adapter-versioned, provider-authoritative non-secret account identifier; define its bytes, extractor, equality/re-derivation, mismatch refusal, and no-raw-account-publication rule. | Fresh reviewer reconstructs the assertion hash, attempts alias/normalization/missing/plural substitution, and verifies ADR-022 account-fence preservation. |

The subsequent focused review must write only
`result-remediation-04.md`. It must return `ACCEPT`, P0=0, P1=0 before this
work stops for human ratification; otherwise no human gate may be presented.
