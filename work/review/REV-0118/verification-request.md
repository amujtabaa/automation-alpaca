# REV-0118 — P0 correction-only verification

Scope: verify only the exact P0 retained in `result-r1.md`; do not reopen design or the three
already-closed P1 findings.

- Candidate commit: `2051afe2bbc21918fac6b69875e0a536fe722e49`
- Candidate tree: `2d3fef0011412ec432fd26f43f526be6946ad00c`
- Parent request/publication head: `0704bdc31a942609e25663eb9e170b9e8e30186c`
- Original reviewed candidate: `0587c7069dfcea7b53e37a35b2cad89cf72bd69d`
- Original manifest candidate: `d801fb1730d9116334b5eee735577217abee7d9f`
- Corrected manifest SHA-256:
  `2c44d4d7191034d18ed1a91a374731df1dd3c155d0597024e76f806860ce061b`
- Corrected manifest blob: `35caa7429c7e13e7921918096804d6bf63a186d4`

Required checks:

1. `git diff --check d801fb1730d9116334b5eee735577217abee7d9f..2051afe2bbc21918fac6b69875e0a536fe722e49`
   exits zero.
2. `git diff --check c7e394f52782a9b398ed89bfdc55b45bc09499b4..2051afe2bbc21918fac6b69875e0a536fe722e49`
   exits zero.
3. The six named R6-R8 packet/result files have no extra EOF blank line.
4. `execution-packet-r7.md` names the corrected R6 packet hash, and the manifest/ledger bind the
   corrected affected hashes.
5. No application, test, DDL, schema flag, evidence outcome, or implementation-source byte changed
   between `0587c706...` and `2051afe...`; only review/governance Markdown and ledger evidence
   bookkeeping changed.

Return only `ACCEPT` or a finding showing one of those five checks still fails. No SQLite/database
or held-suite execution; no new design review. End with the standard verdict/count block.
