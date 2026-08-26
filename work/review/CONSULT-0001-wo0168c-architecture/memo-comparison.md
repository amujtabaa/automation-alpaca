# WO-0168c — Comparison: Claude first-pass memo vs ChatGPT ADEG-1.1 memo

Author: Claude (Fable 5), disclosed second-pass reconciliation, 2026-08-26
Inputs: my frozen first-pass memo (unchanged) and `WO-0168c_ARCHITECTURE_DECISION_MEMO_v1.1.0_CONSOLIDATED.md` (read in full, 1,355 lines, after the first pass was finalized).

## Bottom line

The two memos agree on every fundamental: the diagnosis (the scanner is a hand-built partial Python interpreter chasing an open-ended claim that can never converge), the verdict (delete it, don't patch it), the threat model (protect against mistakes, not a hostile machine owner), the severity (governance/dev-speed harm, no trading or data harm), the settrace removal, and the shape of the stop rule (a blocker needs a reproducible counterexample against a frozen promise; new threat ideas become human decisions, not automatic blocks).

The divergence is almost entirely about **how much new machinery to build and where enforcement should live**. ChatGPT designs a new external execution platform (ADEG-1.1: an out-of-repo "doorman" with JSON record schemas, a state machine with counted attempt tickets, Git-object snapshotting, and a Docker-based no-network sandbox on Windows — roughly 1,200–2,050 lines of mandatory new code plus up to 3,000 lines of gate tests, plus Docker as a hard dependency). I keep enforcement in the two tiny runtime gates that already exist, add ~300–400 lines of boundary checks, restore normal pytest immediately, and fast-track the actual DDL review. In my own first-pass terms: ChatGPT chose my "Option D" machinery while declaring my "Option B" threat model; I chose Option B outright.

## Where we agree (no action needed to reconcile)

1. Root cause: one mis-bounded claim, not twelve independent bugs; REV-0105's findings are samples from an unbounded class.
2. The scanner, the cross-file re-export analysis, and all `sys.settrace` proof machinery must be **deleted**, preserved only as historical evidence. Neither memo permits "one more repair round."
3. Threat model: accidents and agent mistakes, in scope; deliberately evasive code and a malicious host owner, out of scope; a repository cannot defend against its own deliberate operator.
4. Deliberate-evasion concerns become explicit human decisions (my "threat-class proposal" = their "Architecture Change Request"), never silent P0s.
5. Review terminates via a frozen contract: closed invariant list, reproducible in-model counterexample required to block, hard size/runtime budgets so the replacement cannot regrow into a scanner.
6. A digest match is necessary but never sufficient; approval is a human act, not a value the code computes about itself.
7. Real-world severity: none of this touches trading behavior; the harm is review paralysis and development speed.

## The three real differences

### 1. Where enforcement lives: external mechanized doorman vs in-repo runtime gates plus process

**ChatGPT:** the authoritative gate must live *outside* the candidate worktree (EEP-1). It verifies an exact frozen manifest (commit, tree, every profile hash), materializes the approved tree from Git objects (ignoring the working directory), maps approval to fixed command IDs with counted attempt slots, launches inside a pinned no-network Docker container with a hard-capped disposable disk, and seals result evidence. Their core argument against a repo-only design: "the candidate would still define too much of its own approval and execution environment."

**Me:** the authoritative gate is the existing 39-line human-transcribed literal (`approved_schema_digest.py`) plus `install_schema`'s digest-refusal, with legibility as the defense — guard files so small that any tampering is glaring in a human-gated diff — and process (the WO/ledger discipline) binding identities.

**Why we differ:** we weighed the project's history differently. This project *did* suffer exactly the accident ChatGPT mechanizes away — the noncompliant tmp_path/`:memory:` runs against an unapproved candidate, and the self-approving digest (REV-0078). ChatGPT's design makes identity-substitution structurally impossible; mine relies on the literal gate plus discipline. Conversely, I weighed the machinery's cost: EEP-1 plus the Windows adapter is ~5–10× my footprint of new security-critical code that REV-0106 must then review — nineteen invariants, JSON parsers, a state machine, crash reconciliation, a Windows path-attack corpus. That is real treadmill risk moved one level up, mitigated but not eliminated by their budgets and stop rule. Their own §1.1 says "do not build a permanent hostile-code service," yet tamper-evident journals, forged-ticket tests, and an ADS/Unicode attack corpus are hostile-grade controls; strictly applying their own MUST-traces-to-TM-1 discipline would roughly halve their protocol.

**Layman's version:** we both agree the house only needs to keep out honest mistakes. I fitted two good door locks and kept the keys with the owner. They built a gatehouse with a guard, ID scanners, numbered visitor passes, and a disposable interview room — superb against impostors, but impostors were declared out of scope, and someone now has to inspect the gatehouse.

### 2. Does ordinary pytest come back now, or stay banned until after approval?

**ChatGPT:** "Before approval, no real-repository pytest command runs" — even collection-only, even with the held suites quarantined out of discovery. All testing stays frozen through their Stages 0–7 (build, review, approve).

**Me:** restore repo-wide pytest immediately with the four held suites excluded, because the ratified gate was "no changed-DDL install, no SQLite-bearing test run" — the ban on *importing* modules was later self-imposed inflation (the root `conftest.py` has imported the SQLite store on every pytest run in the repository's history; importing does no I/O), and the frozen suite is currently the project's single largest concrete harm.

**Why we differ:** we read the prohibition's authority differently. I traced the "no imports" rule to the REV-0101-era execution guard's own refusal and treated it as unratified scope creep to roll back; ChatGPT took the current prohibition text as a binding boundary to preserve and engineered around it. Notably this creates an internal tension in their memo: their invariant I-02 makes ordinary discovery *provably* unable to reach the held suites — and if I-02 holds, ordinary pytest is exactly as safe as they need, yet they ban it anyway.

**Layman's version:** the original rule was "don't run the four database tests." It quietly grew into "don't let Python even load the database library," which froze *all* testing. I say shrink the rule back to what you actually approved and turn the test suite back on today. They keep the grown rule and build a system so the four tests can eventually run under escort — while the other ~750 tests stay switched off in the meantime. Only you can say which rule you actually meant.

### 3. Size, dependencies, and time-to-done

**ChatGPT:** mandatory footprint up to ~450 SLOC in-repo + ~1,600 SLOC external + ~3,000 SLOC gate tests; requires Docker Desktop (or a separately reviewed Hyper-V profile) with an explicit rule that if Docker is unavailable the gate stays closed forever — no native fallback; protected NTFS control storage; a nine-stage migration; then REV-0106 reviews all of it.

**Me:** ~300–400 new lines, zero new infrastructure, nothing to install, review packet covers ~2 pages of policy plus those lines; the DDL review itself (the thing everything waits for) is promoted to the critical path.

**Why we differ:** partly genre — theirs is a normative protocol spec (MUST/SHOULD schemas ready for implementation), mine is a minimal-decision memo — and partly the handoff instruction I weighted heavily: "prefer the smallest adequate solution; do not presume Docker exists." They honored the Docker constraint by failing closed without it, which is legal but means the milestone's critical path now runs through installing and maintaining Docker Desktop on your workstation.

## Points where their memo is better than mine — I concede these

1. **The approval-literal lifecycle (their §7.5) — their strongest catch.** The current design says: after approval, edit `APPROVED_EXECUTION_DDL_SHA256` from `None` to the literal in an "unlock commit." But under exact-identity discipline that is circular: approval names commit X; transcribing the literal creates commit Y ≠ X; the approved thing never runs as approved. My memo carried that flow forward without spotting it. Their fix — set the *expected* digest before freeze/review (rename to `EXPECTED_EXECUTION_DDL_SHA256`), and let the human "run it now" authorization live outside the source — is cleaner and I would adopt it (or at minimum, make the approval explicitly name the post-unlock commit).
2. **Quarantine by relocation.** Moving the four held suites to a root outside `testpaths` makes accidental collection structurally impossible rather than config-dependent. Cheap, and better than my deselect/skip suggestion. Adopt.
3. **Counted attempts named in the approval.** Approval as "these exact commands, N attempts, this timeout" rather than an open-ended yes prevents a narrow approval drifting into standing permission — the exact failure mode of the earlier "conversational authorization" incident. Adopt as a written line in the approval/ledger record — without the ticket/journal machinery.
4. Extra identity anchors (WIP git blob ID, whole-`schema.py` hash) and the `.sql`-file DDL normalization SHOULD are both sensible touches I didn't include.

## Points where I'd push back on their memo

1. **Proportionality.** The asset is four tests writing disposable files in a paper-trading project with one operator, and the eventual production database also does not exist yet. Aerospace-grade attempt-slot semantics ("ambiguous launch consumes a ticket"), sealed result manifests, and a Windows path-attack corpus defend against adversaries their own threat table (§4) declares out of scope.
2. **The pytest ban** (difference 2 above) preserves the project's largest present harm and contradicts their own I-02.
3. **New review surface.** REV-0106 under their plan reviews ~2,000 lines of new security-critical code plus 19 invariants plus a container profile. Their stop rule is good, so it probably *does* converge — but at several more days of build-and-review before the first held test can run, versus roughly one day under mine.
4. **They did not verify the checkpoint** — their §1.3 says the anchors "describe the supplied state." I verified every anchor against the worktree by command (all matched). Minor, but it means their memo inherits the handoff's facts; mine tested them.

## Suggested merged path (if you want one)

- Adopt jointly agreed core: delete the scanner (human-gated — your approval), keep `approved_schema_digest.py` + digest-first `install_schema`, freeze the threat model and stop rule.
- Adopt from ChatGPT: the §7.5 expected-digest lifecycle fix; relocation of the four held suites out of discovery; approval records that name exact commit, commands, and attempt counts (as ledger text, not JSON schema machinery).
- Adopt from mine: restore repo-wide pytest now (relocation makes this even safer than my original deselection plan); the ~400-line lexical/AST boundary checks; no new infrastructure; schedule the actual DDL review as the critical path.
- Defer as optional: the container sandbox for the one approved run (worth it only if Docker is already on the machine and you want belt-and-suspenders); the full EEP-1 record/ticket apparatus (skip under TM-1).
- Combined footprint: ~500 lines plus a file move, no new dependencies, testing back on this week, and the gate opens when you review the DDL — not when a platform finishes being built.

## The decision that actually separates the memos

One question resolves nearly everything: **do you want residual trust to sit in process (small guards + your review of tiny diffs) or in mechanism (an external system that makes rule-breaking structurally impossible)?** Mechanism is objectively stronger against identity mistakes — this project has had one — and costs roughly 5–10× the build and review effort plus a Docker dependency. Process is dramatically cheaper and fully adequate *if* the threat really is accidents and you remain the only operator. That is your Decision A in their memo and my Decision 1 — the same fork, described from opposite sides.

*My first-pass memo remains frozen and unedited; this comparison is the disclosed addendum.*
