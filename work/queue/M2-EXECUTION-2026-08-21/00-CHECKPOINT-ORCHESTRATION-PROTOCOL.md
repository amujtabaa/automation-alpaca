# M2/M3 checkpoint orchestration protocol

Status: **PREPARATION CANDIDATE — DOCUMENTATION ONLY — NO IMPLEMENTATION OR MERGE AUTHORITY**

## Operating model

Ameen Mujtabaa runs the local coding LLM between checkpoints. Codex is the checkpoint governor,
not a continuously connected supervisor. The coding LLM receives one active work order and may
perform only that order's bounded implementation. Ameen returns to Codex when the coding LLM:

- reports a completed work order;
- reaches a named human or schema gate;
- cannot satisfy a required test or evidence obligation;
- proposes a path, dependency, architecture, or behavior outside the active order; or
- has a stable intermediate checkpoint Ameen wants independently inspected.

Codex then re-derives the result from the repository, reproduces proportionate evidence, records a
verdict or correction packet, and identifies the next permitted action. The coding LLM's prose is
a claim, not evidence.

## Branch and rollback model

1. The reviewed preparation packet lands on `master` only after a separate exact human merge
   authorization. That documentation-only `master` head is the saved fallback point.
2. M2-I1 starts on `codex/m2-i1-durable-codec-r1` from that exact saved head.
3. Each later M2 branch starts from the independently accepted predecessor head, not from an
   unreviewed working tree. Branch names are assigned on activation.
4. No M2 implementation branch merges to `master` merely because the coding LLM says it is done.
5. If the experiment is abandoned, the saved documentation-only `master` head remains intact.
   Branch deletion, reset, or history rewrite requires its own exact disposition.

## Required checkpoint bundle

Every return to Codex must include or leave reproducible in the checkout:

```text
Work order:
Branch:
Base commit:
Candidate head:
Changed paths:
Commits created:
RED evidence:
GREEN/focused evidence:
Full/static/governance evidence:
Known failures and NOT_RUN items:
Schema, database, broker, credential, or network activity performed:
Requested next action:
```

The candidate must be committed and the worktree clean unless the checkpoint explicitly asks for
help with an uncommitted failure. Test counts without commands, exact heads, and retained output do
not satisfy the bundle.

## Checkpoint classes

| Checkpoint | Local coding LLM may continue afterward? | Codex action |
| --- | --- | --- |
| `START` | Yes, inside the active order | Verify base, scope, inventory, and RED plan |
| `RED` | Yes, if the failures prove the intended missing behavior | Confirm tests can fail and do not weaken authority |
| `GREEN-CANDIDATE` | No further semantic expansion | Reproduce focused/static evidence and inspect scope |
| `HUMAN-GATE` | No | Present a concise decision, layman's meaning, and impact to Ameen |
| `BLOCKED` | No material workaround outside scope | Diagnose root cause and identify the smallest new authority needed |
| `REVIEW-CANDIDATE` | No changes except reviewed remediation | Produce or consume the exact review packet |
| `ACCEPTED` | Only the next separately activated order | Freeze head/evidence and establish successor base |

## Local coding autonomy

The coding LLM may investigate, run non-destructive checks, write RED tests, implement the exact
active specification, correct ordinary in-scope defects, and commit/push its own branch. It must
not ask Ameen to repeat authority already recorded in the active order.

It must stop for:

- SQL/DDL, schema creation, migration, or database execution without the M2-I2 human gate;
- credentials, outbound broker/network calls, orders, or configured database access;
- a public API, accepted ADR, dependency, safety invariant, or event-truth change;
- edits outside the exact active allowed paths;
- test/doc/ADR deletion, weakening, skip, xfail, broad suppression, or history rewrite;
- activation of the next work order or any merge to `master`.

## Evidence and review posture

- RED precedes implementation and must fail for the intended reason.
- Known-answer controls must be independently constructed, not computed by the production helper
  under test.
- Runtime and persistence slices use fresh temporary destinations only when explicitly authorized.
- `NOT_RUN`, `NOT_EVALUATED`, environmental limitations, and failed attempts remain visible.
- Codex may reject a checkpoint even when tests pass if the tests cannot fail, scope is broader than
  the work order, or the implementation creates a second semantic owner.
- The final M2 head requires independent acceptance and exact human merge authorization before it
  can affect `master`.
