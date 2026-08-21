# Exact retirement and human Gate-B evidence

Status: **READY_FOR_HUMAN_M2_REGENERATION_RATIFICATION — GATE B**

This is a documentation/governance terminal record for WO-0164. It does not authorize M2
implementation, schema/DDL, a database, runtime, broker or credential activity, provider
selection, promotion, or merge to `master`.

## Accepted candidate and independent review

| Evidence | Exact identity |
| --- | --- |
| Accepted base | `177ea5fcd959b9e7d7d5a3172070f90f89ece963` |
| Accepted base tree | `99338a7832509645f17ed4f51c511e7dffb6c41f` |
| Candidate commit | `fd7a5ec0319547145acb6a349d95fd5ce99f604c` |
| Candidate tree | `cb88dddeb8bd50cfd5e921030a7012456695ac73` |
| Candidate manifest SHA-256 | `e59b2d70f1511a741372a3ee01d0c8feb07d68ea60a0e583a64b300da0f83d4c` |
| Published review/disposition head before retirement | `a441c388591c948cc890d77cba643871f6863c1f` |
| Published pre-retirement tree | `00b230a18a1fb550a2a42a275a67d5e6aa4136e8` |
| Independent result | `ACCEPT`, P0=0, P1=0, P2=0, no findings |
| Reviewer-owned `result.md` SHA-256 | `c1e153e737f4f0cf3d4d5eb159f3be87f4f12cf91d0773afa3fceea93f529764` |
| Author `disposition.md` pre-closeout SHA-256 | `4a2889e4342d224060fa0829385f7633f63b1757e3b4467cfe71074546feb0ff` |

The reviewer seat itself removed five Markdown hard-break space pairs and restored the terminal LF;
no visible word, value, verdict, count, or ordering changed. `git diff --check` passed afterward.

Ancestry was reproduced immediately before retirement: accepted base to successor exited `0`; c9
to successor exited `1`. The successor therefore descends from accepted `master` and not from c9.

## Comparison evidence retained

- Actual quarantined tar SHA-256:
  `f163ac6cca5a1dbebdf17d585bb9dfa3e2bd4197f048fbbafa1364ac69ab4604`.
- Input-manifest file SHA-256:
  `abba3d37ace9bd1ad38582404d8e6e418eaace5d29def2b23bdfd7b56312a048`.
- The input manifest's 63-character tar token remains negative evidence; it was not rewritten.
- Two independent frozen handoffs bound the correct 64-character tar digest.
- All six inner members matched valid manifest rows; the inner manifest SHA-256 was
  `4cd8b8062dd8575334e63364e2fed62b1387821cbcb9a9aaca96a533069a8b08`.
- The canonical `G|` stream reproduced exactly 89 rows and SHA-256
  `95e826f2ce22aa3125ce258a457ea22ea9f7dc529be2d7386b11c324d3cda5ed`.

## Path-total sole-material reconciliation

The exact sorted base-to-c9 changed-path inventory contained 45 rows and SHA-256
`6f10444281008a79ddcbe828e8eb213223868e1548478a1155629b4f29c45cdb`. Every row falls into
exactly one terminal group:

| Group | Count | Disposition |
| --- | ---: | --- |
| Branch-local PKL/ledger lifecycle metadata | 4 | Superseded by accepted `master` plus WO-0164 records; no accepted architecture delta |
| Source/authority audits and comparison surfaces | 8 | Exact accepted authority or reproducible facts from retained base `177ea5f`; retained semantics map to O-03 through O-13 and O-18 |
| Abandoned planning packet and draft work orders | 10 | DROP/REWRITE under O-01/O-02/O-14/O-16/O-17/O-19 |
| Old REV-0064/0065/0066 review history | 23 | Historical evidence for the abandoned lane; findings/negative controls are reconciled by O-20 and the fresh candidate/review |
| **Total** | **45** | **Path-total** |

Exact inventory:

```text
A work/active/WO-0158b-m2a3-governing-authority-audit.md
A work/completed/keep/WO-0158-m2a1-shared-value-source-audit.md
A work/completed/keep/WO-0158a-m2a2-controller-authority-protection-source-audit.md
A work/queue/M2-PERSISTENCE-CRASH/00-frozen-authority-and-owner-inventory.md
A work/queue/M2-PERSISTENCE-CRASH/01-preflight-development-path.md
A work/queue/M2-PERSISTENCE-CRASH/02-dependency-and-authority-map.md
A work/queue/M2-PERSISTENCE-CRASH/03-activation-decision-request.md
A work/queue/M2-PERSISTENCE-CRASH/04-shared-value-construction-and-reducer-contract.md
A work/queue/M2-PERSISTENCE-CRASH/05-controller-authority-protection-reducer-contract.md
A work/queue/M2-PERSISTENCE-CRASH/06-governing-authority-and-cold-restart-contract.md
A work/queue/M2-PERSISTENCE-CRASH/AUTHORITY-MANIFEST.sha256
A work/queue/M2-PERSISTENCE-CRASH/README.md
A work/queue/WO-0158c-m2a4-persistence-architecture-contract.md
A work/queue/WO-0159-m2b-shared-execution-venue-hydration-hooks.md
A work/queue/WO-0160-m2c-controller-authority-protection-hydration-hooks.md
A work/queue/WO-0161-m2d-profile-codec-schema-foundation.md
A work/queue/WO-0162-m2e-atomic-sqlite-unit-of-work.md
A work/queue/WO-0163-m2f-startup-recovery-crash-closeout.md
A work/review/REV-0064/disposition-remediation-01.md
A work/review/REV-0064/disposition-remediation-02.md
A work/review/REV-0064/disposition-remediation-03.md
A work/review/REV-0064/disposition.md
A work/review/REV-0064/request-remediation-01.md
A work/review/REV-0064/request-remediation-02.md
A work/review/REV-0064/request-remediation-03.md
A work/review/REV-0064/request-remediation-04.md
A work/review/REV-0064/request.md
A work/review/REV-0064/result-remediation-01.md
A work/review/REV-0064/result-remediation-02.md
A work/review/REV-0064/result-remediation-03.md
A work/review/REV-0064/result-remediation-04.md
A work/review/REV-0064/result.md
A work/review/REV-0064/terminal-acceptance.md
A work/review/REV-0065/disposition.md
A work/review/REV-0065/request.md
A work/review/REV-0065/result.md
A work/review/REV-0065/terminal-acceptance.md
A work/review/REV-0066/disposition.md
A work/review/REV-0066/request.md
A work/review/REV-0066/result.md
A work/review/REV-0066/terminal-acceptance.md
M pkl/architecture/architecture-map.md
M pkl/log.md
M pkl/project/goals.md
M work/ledger.jsonl
```

The c9 range changed no `app/**`, `tests/**`, `migrations/**`, schema, or accepted ADR path. Its
source-audit products are deterministic facts of retained accepted-base source and can be freshly
regenerated as required by O-03/O-18; they grant no implementation authority. The accepted ADR-023
and ADR-024 bytes and all indispensable accepted semantics remain in current accepted authority.
The fresh matrix and independently accepted successor carry every retained obligation. No
indispensable material existed only on the obsolete ref.

## Exact pre-delete freeze

Immediately before deletion:

- local target, remote-tracking target, and fresh live-remote target all equaled
  `c9b27dca6236606b3792dfc75c6418fd735be6cb`;
- successor local, remote-tracking, and fresh live-remote heads all equaled
  `a441c388591c948cc890d77cba643871f6863c1f`;
- the target was checked out in zero worktrees;
- the successor worktree was clean.

Unrelated local branches, canonical count 3, SHA-256
`05b94ed40eba5d5c576ce1d9796464ccca303639c90520886d50d2d3a63eb806`:

```text
refs/heads/codex/m1-5-broker-alignment-local-r1|177ea5fcd959b9e7d7d5a3172070f90f89ece963|
refs/heads/codex/m2-regeneration-gate-a-r1|a441c388591c948cc890d77cba643871f6863c1f|
refs/heads/master|177ea5fcd959b9e7d7d5a3172070f90f89ece963|
```

Unrelated remote-tracking refs, canonical count 4, SHA-256
`965bff5d10ea9888201e8920c9fb0b6d991cc30457d9230be90c5fee5ab9b241`:

```text
refs/remotes/origin/codex/m1-5-broker-alignment-local-r1|177ea5fcd959b9e7d7d5a3172070f90f89ece963|
refs/remotes/origin/codex/m2-regeneration-gate-a-r1|a441c388591c948cc890d77cba643871f6863c1f|
refs/remotes/origin/HEAD|177ea5fcd959b9e7d7d5a3172070f90f89ece963|refs/remotes/origin/master
refs/remotes/origin/master|177ea5fcd959b9e7d7d5a3172070f90f89ece963|
```

Worktree porcelain inventory, canonical line count 4, SHA-256
`d7a175cd2c137000635f95d71e6695d06d2fa54fcb93f1082dad156a1bfd3f4b`:

```text
worktree G:/dev-hdd/automation-alpaca
HEAD a441c388591c948cc890d77cba643871f6863c1f
branch refs/heads/codex/m2-regeneration-gate-a-r1

```

## Executed retirement and post-delete proof

Only these exact destructive commands ran:

```text
git branch -D codex/m2-planning-preflight-r1
git push origin --delete codex/m2-planning-preflight-r1
```

The local deletion reported `Deleted branch codex/m2-planning-preflight-r1 (was c9b27dc)`. Before
remote deletion, local absence was verified and both remote-tracking and live-remote target still
equaled the full c9 head. The remote deletion then reported only the named branch deleted.

Fresh post-delete evidence:

- local target lookup absent (`show-ref` exit `1`);
- remote-tracking target lookup absent (`show-ref` exit `1`);
- fresh live-remote target query returned no row;
- fresh live-remote successor remained `a441c388591c948cc890d77cba643871f6863c1f`;
- fresh live-remote `master` remained `177ea5fcd959b9e7d7d5a3172070f90f89ece963`;
- unrelated local count/hash remained exactly
  `3 / 05b94ed40eba5d5c576ce1d9796464ccca303639c90520886d50d2d3a63eb806`;
- unrelated remote-tracking count/hash remained exactly
  `4 / 965bff5d10ea9888201e8920c9fb0b6d991cc30457d9230be90c5fee5ab9b241`;
- worktree count/hash remained exactly
  `4 lines / d7a175cd2c137000635f95d71e6695d06d2fa54fcb93f1082dad156a1bfd3f4b`;
- target worktree matches remained zero; and
- the worktree remained clean.

No tag, bundle, archive, prune, clean, replacement ref, history rewrite, force-push, worktree move,
or unrelated ref mutation occurred. The exact obsolete local and remote branches are retired.

## Validation boundary and terminal state

Repository-native install, ledger, PKL, disposition, scope, context-hygiene, manifest, formatting,
ancestry, and diff checks are rerun during atomic closeout. Full pytest, Ruff, mypy, import-linter,
configured-database, broker/network, runtime, schema, restore, soak, and R16 checks remain
intentionally `NOT_RUN` or `NOT_EVALUATED`; this documentation-only record does not relabel them.

Terminal state:

`READY_FOR_HUMAN_M2_REGENERATION_RATIFICATION — GATE B`

Human Gate B may ratify only the exact fresh M2 planning packet. A separately activated future work
order is required before any implementation or `master` merge.
