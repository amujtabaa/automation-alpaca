# WO-0149 second Sol preflight disposition

Status: **AUTHOR-OWNED PROVENANCE RECORD — original reviewer result unchanged**

`REV-0051/result.md` is an independent `ACCEPT` of candidate SHA-256
`A85192BDC18455FBE7D6E2EA6178DBAA76ABB14608987EB7B8F9F61BB782DBEF`. It remains
unchanged and is not presented as a review of later candidate bytes.

A separate fresh GPT-5.6 Sol Extra High static rerun against that same candidate found four P1
specification gaps before activation:

1. Broad BUY refusal would also deny inherited target-derived BUY cancellation.
2. All-leg cancellation in one atomic transition conflicted with a one-next-leg cursor.
3. The allowlist omitted the WO-0149 completed destination and needed a narrow retained-WO-0148
   append-only exception.
4. The Fable task-start/gate grammar was incomplete.

No P0/P2 finding, implementation action, test execution, SQL/DDL, database work, network/broker
activity, Git mutation, or retained-evidence rewrite occurred in that rerun. The root corrections
were made only in the WO-0149 draft: preserve current-target BUY cancellation while sealing
exposure-increasing BUY work; atomically latch preemption then issue one target-derived cancellation
per current-leg cursor advance; add the completed destination and activation-only retention rule;
and restore canonical Fable fields.

The corrected candidate SHA-256 `8257907E9DC0772D8E419696FA8A0B7BFB8BA13BCCD4E464814314CF9B275D47`
received a new independent `REV-0052` static review. That review retained one P1 only: the draft
incorrectly demanded two same-hash preflights despite designating `REV-0052` as its one final
exact-candidate review. The final mechanical correction changes that condition to one final
independent exact-candidate preflight. Its post-correction SHA is recorded by the reviewer-owned
`REV-0052/result-addendum-01.md`; activation remains blocked until that addendum is `ACCEPT` with
P0=0/P1=0.
