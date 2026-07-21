# ULTRA review-remediation state

Session branch: `codex/ultra-beta-batch`

Synced starting head: `d7b63b91d9bc3efbee0055944a8b36dbc7602e61`

Session posture: **ACTIVE — review remediation in progress**

Authoritative kickoff: `work/queue/CODEX-KICKOFF-REMEDIATION.md`

## Preconditions

- VERIFIED: the starting worktree was clean before sync.
- VERIFIED: `d7b63b9` contains required planning head `8d589fe`.
- VERIFIED: `work/queue/REVIEW-REMEDIATION-BATCH.md` exists.
- VERIFIED: reviewer-owned results exist for REV-0034, REV-0035, REV-0036, and REV-0037.
- VERIFIED: paper-only work; no credentials, broker calls, live trading, merge, or PR are in scope.

## Per-work-order scoreboard

| WO | Status | Branch commits | Notes |
|---|---|---|---|
| WO-0130 | ACTIVE | activation: this commit | Recorder one-segment retention and bootstrap external-venv guard; GATE and red-first evidence pending. |
| WO-0132 | QUEUED | — | Direct `HUMAN_ATTESTED` fill-rail mutation pin plus conservative missing-occurrence handling; REV-0035 re-verification remains out-of-session. |
| WO-0131 | QUEUED | — | Gated replay FSM legality; must end at REVIEW with REV-0038 staged, never self-close. |
| WO-0133 | QUEUED | — | ADR-009 anchor/range re-baseline; runs last after application anchors settle. |

## Running NEEDS-INPUT list

- None.

## Deferred by contract

- REV-0035 pin re-verification and REV-0038 independent review run in the Claude seat after this session.
- ADR-012 and ADR-009 acceptance remain human-only gates.
- REV-0037 malformed-lineage visibility and per-child escalation advisories remain future work.
- The independent reviewers' Python 3.12 full-run caveat is verification work, not a product change.
