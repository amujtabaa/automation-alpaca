# WO-0168c convergence — blinded first-pass architecture memo

Author: Claude (Fable 5), first-pass blinded consultation
Date: 2026-08-26
Status: FIRST-PASS FINAL — preserved unchanged for later comparison. No post-REV-0105 decision memo, cross-model recommendation, or consultation output was read.
Verified checkpoint: HEAD `d0887585fdb479e83a74909e6d14f3375e0a0850`, tree `4e8676d3dbe8c9be306e0421789580d06d65224c`, frozen review candidate `fa260c77`, tree `8599f65b`, REV-0105 = BLOCK (P0=7, P1=5, P2=0), no REV-0106.

## Verdict in one paragraph

The review loop is not converging and will not converge, because the defect is in the assurance claim, not in the fixes. The scanner in `test_persistence_write_capability.py` implicitly claims "no Python code in these 49 files can reach SQLite or the approval token **by any route**." That is a universal claim about arbitrary Python, and sound static verification of it is impossible in principle; every "finite grammar" extension must leave escapes, and fresh adversarial reviewers will always find them. Meanwhile the protection that actually matters at runtime already exists and is tiny: the 39-line fail-closed human gate (`approved_schema_digest.py`, approval literal `None`) that every installing fixture calls **before** `sqlite3.connect`, plus `install_schema`'s digest-mismatch refusal before it executes anything. My recommendation is option (2)+(3) from the handoff: **stop repairing the scanner, delete its proof machinery (with your approval — test deletion is human-gated), keep the runtime gates, replace the static proof with two small structural checks (~300–400 lines total), and ratify a threat model plus a review stop rule so reviews can terminate.** None of the twelve REV-0105 findings affects real-world trading behavior, data integrity, or runtime reliability; the real damage today is development throughput, review time, and the fact that the whole pytest suite has been `NOT_RUN` since REV-0101.

---

## 1. Root diagnosis: mis-bounded claim, not diverging defects

Three independent lines of evidence say the findings are samples from an unbounded class, not a finite defect list being worked down.

**Theory.** "This file never acquires SQLite capability" is a non-trivial semantic property of programs in a language with `globals()`, `sys.modules`, `getattr`, `setattr`, closures, generators, and runtime import machinery. Deciding such properties statically for arbitrary code is impossible (this is Rice's theorem territory); a static checker can only be sound for a *restricted* language subset. Each WO amendment since REV-0082 is exactly that: a restriction grammar that grows to swallow the last counterexample. The grammar can never finish, because the reviewers are allowed to draw counterexamples from full Python while the grammar is finite by design.

**Empirics.** Twenty-seven review packets (REV-0079 → REV-0105) in roughly two days, all against the same test file. The P0 counts of the last three full reviews *rose*: REV-0103 P0=6, REV-0104 P0=5, REV-0105 P0=7. The work order's own circuit breaker fired at REV-0088 ("must not extend that evaluator with a fourth alias pattern") — and was followed by seven more replace-the-model-with-a-bigger-model rounds. The file is now 12,874 lines / 465KB with 98 top-level definitions; the primary scan took 122s at `fa260c7` and the current WIP did not finish in ~170s. Fix size, scan time, and finding count are all growing together. That is the signature of a claim that generates its own review surface.

**Self-reference.** REV-0105's P0-5, P0-6, P0-7, P1-4, and P1-5 are findings about the scanner's *own instrumentation* — the `sys.settrace` lifecycle, its counter typing, its callback identity. The machinery now produces proof obligations about itself, two levels removed from any database. That recursion has no floor.

There is also a category error worth naming plainly: the reviewers are testing the machinery against a **deliberately evasive author** — `globals()["TARGET"] = "sqlite3"`, `getattr(sys, "settrace")`, package-shadowing tricks. The declared threat is **accidental or agent-caused noncompliance**. Accidental code spells `import sqlite3`. Every finding since roughly REV-0082 requires code nobody writes by accident. The reviewers are behaving correctly *given the claim the machinery makes* — if you claim "no route exists," any demonstrated route is a legitimate P0 — and the REV-0105 request's "required review lenses" explicitly instructed them to hunt reflection and trace escapes. The claim and the request template must shrink; the reviewers were never the problem.

Finally, the causal origin matters for the cure. The chain was: a real DDL bug (the `RAISE(ABORT, ...)` `||` concatenations) → a real process defect (the gate was self-approving; runs happened before exact-identity approval; REV-0078's P0 was justified) → a correct fix (the human-transcribed `None` literal in `approved_schema_digest.py`) → then **precaution inflation**: the ratified prohibition ("no changed-DDL install, no SQLite-bearing test run") swelled into "no `sqlite3` import, no project-module import, in any process." Since the root `conftest.py` imports `app.store.sqlite` unconditionally, that inflated rule makes *every* pytest invocation in this repository illegal — which is why pytest has been `NOT_RUN` since REV-0101, which is why all assurance had to become static, which is what demanded an impossible static proof. The treadmill is the compensating mechanism for a prohibition stricter than the one you ratified.

## 2. Real-world severity, in plain language

**Trading/runtime correctness: no direct effect at all.** All twelve findings live in a test file. `execution_core` is not imported by the serving application anywhere — I verified that nothing outside `app/execution_core` itself references it (the FastAPI app, stores, facade, and cockpit never touch it). No order, fill, position, kill-switch, or risk behavior changes whether these findings are fixed or not.

**Data integrity: near-zero, and reversible.** The guarded asset is a checkpoint schema that has never been installed anywhere, in a paper-trading system with no live data on it. The worst *accidental* outcome the gate protects against is a scratch SQLite file being created with unapproved DDL — recoverable by deleting a file. The protections that operate at runtime are present and none of the findings defeats them at runtime: the fixtures refuse before a connection object exists while the approval literal is `None`, and `install_schema` refuses on digest mismatch before executing a single statement (verified at `schema.py:4776-4777`).

**Development/CI performance: this is where the real damage is.** Two-to-four-minute scans that are still growing; a 12,874-line test file every reviewer must re-derive; ten-plus hours of review labor; and — the largest concrete harm — **the entire pytest suite has not run since REV-0101**. The repository currently has *less* verification than it had before this machinery existed. That is a genuine reliability risk, and it is caused by the guard, not by the guarded code.

**Maintainability: severe.** The scanner is a bespoke abstract interpreter of Python maintained inside a test file. Every future touch of persistence tests drags it along.

**Governance assurance: paradoxically reduced.** An assurance mechanism that has returned BLOCK twenty-seven times in a row provides no assurance — the gate never opens, the milestone never closes, and the two genuinely strong protections (the 39-line gate and the digest refusal) are buried under machinery noise.

**Layman's translation of the twelve findings.** They all say versions of one thing: *a sufficiently creative Python program could fool the watchdog*. Swap a label through the module's name-map so the watchdog reads a stale value (P0-1); smuggle a capability out through a returned function or a copied dictionary (P0-2/P0-3); make a package shadow its protected child (P0-4); reach the tracing switch by an unlisted spelling, or flip it off mid-measurement (P0-5/P0-7); confuse two functions that share a name (P1-5); accept `True` where exactly `1` was meant (P1-4). None of them says the vault door is open. They say the CCTV system that watches people *approach* the vault has blind spots — and the people it would miss are deliberate sneaks, who are outside the threat model you stated.

## 3. Options

| | Guarantee | Limits | Complexity | Prerequisites | Likely review behavior |
|---|---|---|---|---|---|
| **A. Continue repairing the scanner** | None new; another "finite grammar" iteration | Unbounded counterexample space; suite still unrunnable | 12.9k lines and growing; scans >170s | None | Another BLOCK, with high confidence — the empirical trend and the theory both predict it |
| **B. Narrow the boundary: runtime gates + lexical/structural invariants** (recommended) | Accidents fail loudly at two runtime gates; boundary drift caught by a token check any human can verify in one read | Does not stop deliberate in-process evasion (nothing in-process does — 27 reviews demonstrated this for the scanner too) | ~300–400 lines total, <60s | None — stdlib + existing tools | Reviewable in minutes; terminates under the stop rule |
| **C. Contract change only (keep scanner, re-scope reviews)** | Stops the treadmill immediately | Leaves a 465KB liability to maintain and re-review at every touch; pytest still blocked | Unchanged | None | Terminates, but every future scanner edit reopens pain |
| **D. External isolation (subprocess/OS/CI sandbox)** | The only route that addresses a deliberately evasive author, because enforcement leaves the interpreter the author controls | Not required by the declared threat model; ongoing infra cost on a solo Windows box | Medium | Cannot presume Docker/Hyper-V/admin/CI — would need building | Strong, but reviewing sandbox config becomes the new surface |

There is also a complementary lever that is not an alternative but changes everything downstream: **actually holding the DDL review the gate is waiting for** (§9, decision 4). The entire pre-gate proof burden exists to police an interval whose end is in your hands.

Why not A: the last three rounds produced 6, 5, and 7 P0s; each remediation adds model surface that itself gets reviewed; the WO's circuit breaker already fired once and was overridden seven times. Continuing is not a neutral default — it has a measured failure record.

Why not C alone: it stops the bleeding but keeps the wound. The scanner still can't prove its own import graph runnable, so pytest stays dead, and its 12.9k lines remain the largest unreviewable artifact in a lane whose safety philosophy is legibility.

Why not D now: it defends against an adversary you have declared out of scope, at real cost. Record it as the documented escalation path if the threat model ever changes (e.g., unattended multi-agent fleets writing code under "make it pass" incentives).

## 4. Recommendation (option B + the contract half of C)

**Delete** (requires your explicit approval — test deletion is a human-gated surface; git history and the frozen commits preserve every byte as evidence):
- The two finite scanners (provenance + topology fixpoints), the embedded snippet corpus (~433 snippets), the `sys.settrace` line-count proof and its lifecycle grammar, and their controls — roughly 95% of `test_persistence_write_capability.py`.
- The uncommitted WIP in that file: do not finish it; do not commit it.

**Retain** (unchanged — these are the load-bearing parts and they are good):
- `tests/execution_core/approved_schema_digest.py` exactly as written. It is the single best artifact in this lane.
- The gate-before-connect pattern in all four held suites' installing fixtures.
- `install_schema`'s digest-refusal-first order, `SchemaDigestMismatchError`, and the EXPLAIN-plan boundedness assertions in the held SQLite suite (these already prove bounded reads at the database level — a stronger mechanism than counting executed Python lines with `settrace`, which is why dropping the trace proof loses almost nothing).
- The original WO-0168a controls at the top of the write-capability file (setup-issuer direction, the no-I/O `_Connection` stand-in, the anti-self-approval AST control from REV-0078 P0-1). These are bounded, decidable checks of specific spellings — the healthy kernel the scanner grew out of.
- The six import-linter contracts, ruff, mypy, the locked DDL/catalog/manifest identities in the review packets.

**Introduce** (~300–400 lines total, all stdlib):
1. **Lexical boundary check** (~150 lines): outside an explicit allowlist, no file in the 49-file corpus may contain the token `sqlite3`. Today the allowlist is exactly 11 files (2 app: `schema.py`, `repository.py`; 9 tests, dominated by the four held suites), each entry carrying a one-line justification. The property this buys is decidable and immune to accidental evasion *by construction*: code that never spells the module name cannot accidentally import it; code that builds the name from fragments is deliberate, hence out of model. Any human can verify the checker's correctness in one reading.
2. **Two first-statement AST checks**: (a) every installing fixture's first call is `require_approved_ddl_execution()` (before any `connect`); (b) `install_schema`'s first non-docstring action derives the digest and calls `_require_exact_approved_ddl_digest`. These pin exactly the two runtime gates, nothing else.
3. **Negative canaries** (the smallest failure-capability proof): a synthetic source with a disallowed `sqlite3` token is flagged; a fixture whose first statement is not the gate call is flagged; `require_approved_ddl_execution()` with the literal `None` raises; `install_schema` invoked with a one-hex-character-off digest raises before `execute` (provable with the existing no-I/O `_Connection` stand-in — no SQLite needed).
4. **A short ratified decision record** (WO amendment or mini-ADR, ~2 pages): the interim threat model (§5), the closed evidence corpus (§6), and the review stop rule (§7). This is the one piece that must pass a review packet — but it reviews two pages of policy plus ~400 lines of code, not 465KB.
5. **Re-scoped interim prohibition** (decision 3 below): pytest runs again with the four held suites deselected/skipped; module imports are legal; what stays forbidden is exactly what you ratified — changed-DDL install, held-suite execution, database/file creation in this lane.

**Explicitly out of scope**: sandboxes, Docker, CI hardening, signatures, hash-chained ledgers, any ambition to prove agents cannot be malicious, any change to engine/runtime behavior, and any further growth of static analysis — with an anti-metastasis rule: if the replacement boundary machinery ever exceeds ~2× its line budget, that is itself a stop-and-redecide trigger, not a fix-forward situation.

## 5. Threat model

**Protected against (the declared threat — accidents and non-evasive agent mistakes):**
- An agent or human runs a held suite too early → the fixture gate raises before a connection object or file exists.
- An agent writes a new execution_core test or module that touches SQLite directly → the token check fails in seconds, with a message pointing at the allowlist policy.
- The DDL is edited after approval → `install_schema` refuses on digest mismatch before executing anything.
- The self-approving-token regression returns → the retained AST control refuses the spelling.
- Cross-layer import drift → import-linter, as today.

**Not protected against (requires genuinely external enforcement, i.e. option D):**
- Deliberately evasive code — string-built imports, reflection chains, guard-namespace mutation. Nothing running inside the same interpreter stops this; the 27 reviews are the demonstration.
- An agent or human editing the guard files themselves. The mitigation is process, and it already exists: `approved_schema_digest.py`, the boundary test, and the allowlist stay on the human-gated diff list, and they are now small enough that any diff to them is glaring in review. **Legibility is the defense.** The current scanner inverts this — it is itself the largest unreviewable artifact in the lane.
- A malicious host owner. Out of scope by your statement, and unfixable by anything in this repository.

**Internal consistency of your framing:** it is consistent, with one honest wrinkle. An agent instructed to "make the review pass" can produce evasive-*looking* artifacts without malice — the gray zone between accident and attack. The correct response is not a stronger in-process scanner (the agent can edit the scanner too); it is keeping every guard small enough that a human reads the whole diff, and keeping guard paths human-gated. That is exactly the property the recommendation optimizes for.

## 6. Finite evidence: the closed acceptance corpus

- **Corpus (enumerated, closed):** the 49 `execution_core` Python files (18 app + 31 tests — count verified), the root `conftest.py`, and the new boundary/gate-pin test file. Nothing else is in scope for this claim.
- **Checks:** ruff, mypy, import-linter (as today); the token boundary check; the two first-statement AST pins; the four negative canaries; and the pure execution_core suites running under normal pytest again.
- **Bounds:** boundary + AST checks < 5 seconds; the full added corpus < 60 seconds; new code ≤ ~400 lines; the four held suites stay held until the gate opens.
- **The resulting finite claim:** "Accidental SQLite or DDL use inside the corpus is caught by token presence; approved-path execution is refused at two runtime gates unless Ameen's transcribed literal matches the exact DDL bytes." Every word of that is checkable by a human in one sitting, which is what makes review of it terminate.

## 7. Review stop rule

- A **P0/P1 may block** only with a concrete **in-model counterexample**: a reproducible demonstration that *non-evasive* code (spells `sqlite3`, uses public APIs normally) executes changed DDL, opens a connection, or runs a held suite without tripping a gate — or a mutation showing a guard/control cannot fail (not failure-capable).
- A concern that **requires deliberate evasion** (dynamic name construction, reflection to reach capability, mutating guard namespaces, editing guard files) is a **threat-class proposal**: recorded in the packet, routed to you as a scope decision, never a block — regardless of how severe it would be *if* the threat model included it.
- **Scope:** findings must land inside the closed corpus plus the guard files; anything else is out-of-packet.
- **Termination:** at most two rounds per packet; round 2 may only re-examine round-1 remediations, not open new classes. Absent an in-model counterexample, the verdict must be ACCEPT or ACCEPT-WITH-CHANGES with residual risks noted. "I can imagine a route" is not a finding.
- **Carve-out:** product-code safety findings (the CLAUDE.md invariants, INV-1…9) are never capped by this rule. The cap governs findings against assurance machinery only.
- **Template fix:** the review *request* must state the threat model and stop rule explicitly. REV-0105's request instructed reviewers to hunt reflection and trace escapes — the treadmill was written into the assignment, not chosen by the reviewers.

## 8. Feasibility

Everything recommended runs on the existing stock setup: Python stdlib (`pathlib`, `ast`, `hashlib`), pytest, ruff, mypy, import-linter — all already installed and green at `fa260c7`. **Required infrastructure: none.** No Docker, Hyper-V, CI changes, signatures, admin rights, or new services. Optional hardening, deliberately deferred to honor minimality: running the boundary check under `python -I` in a subprocess, and a ~15-line `sys.addaudithook` tripwire that fails the session if a `sqlite3.connect` audit event fires from this lane while the approval literal is `None` — a runtime observation rather than a static prediction, in keeping with the recommendation's philosophy, but still in-process and therefore optional, not load-bearing.

## 9. Decisions only you can make

1. **Ratify the narrowed assurance claim and stop rule** (§5–§7). *Layman: stop demanding the watchdog catch burglars you don't expect; demand that mistakes fail loudly.* Impact: reviews terminate; the treadmill ends. This is the decision this memo exists to put in front of you.
2. **Authorize deleting the scanner body** and replacing it per §4 (test deletion is human-gated). *Layman: remove the 13,000-line camera system that keeps failing its own inspection; keep the two door locks; add a smoke detector.* Impact: −12k lines, minutes-long reviews, and nothing is lost — git history keeps every byte as evidence.
3. **Re-scope the interim prohibition to what you actually ratified**: no changed-DDL install, no held-suite execution, no database creation — but module imports and normal pytest (held suites deselected) are legal again. *Layman: the ban meant "don't build the database"; it grew into "don't even say the word database"; shrink it back.* Impact: repo-wide verification returns — the single largest reliability win available today, because `conftest.py` has imported the SQLite store on every pytest run in this repo's history and importing was never the hazard.
4. **Schedule the actual DDL review.** The 178,755-byte DDL (SHA-256 `2636c727…`) is the thing the gate is waiting for; every hour of scanner work polices an interval only you can end. Decide whether to review it whole or in slices, then transcribe the approval literal into `approved_schema_digest.py` in a bounded unlock commit. Impact: unholds the four suites, dissolves most of the pre-gate proof burden, and unblocks WO-0169.
5. **Minor:** whether held suites appear as SKIPPED via a small module-level guard keyed on the `None` literal (my mild preference — visible in every run) or stay deselected via runner config (zero file changes). Low stakes either way.
6. **Housekeeping:** authorize pushing the branch — 23 commits exist only on this machine; ten-plus hours of evidence currently has no second copy.

## 10. Disproof pass against my own recommendation

- **Accidental transitive import that creates a DB at import time.** A corpus test could import a helper that connects on import without spelling `sqlite3` locally. Analysis: no module in this repo connects at import time; the seams make it unlikely; and the harm — a scratch file — is reversible. Cheap mitigation: include `app.store` / `SqliteStateStore` as additional boundary tokens for corpus files. **Residual: narrow, accepted.**
- **Allowlist rot.** Someone silences the boundary check by adding a file to the allowlist. That edit lands in a human-gated guard file whose whole diff fits on one screen. An agent that ignores the human-gate rule defeats *any* in-repo mechanism, including the current scanner (which it could also edit). **Residual: process-mitigated, accepted, and identical for every option.**
- **`install_schema` bypass** — code calls `executescript(SCHEMA_DDL)` directly. In-corpus that requires the `sqlite3` token or a connection object; while approval is `None` the only connection factories are gated fixtures that refuse before `connect`, so there is nothing to execute against. Post-gate, held suites run and are reviewed normally. **Sound within the model.**
- **Does the stop rule suppress a real danger?** A genuine in-model counterexample can always open a *new* packet; what it cannot do is block by imagination, and product-code invariant findings are exempt from the cap. **Held.**
- **Does deleting the trace proof lose real value?** Its purpose — bounded reads during checkpoint load — is covered better by the held suite's EXPLAIN-plan assertions, which check the database's actual access plans rather than counting Python lines. **Loss: negligible.**
- **The honest residual:** within its own threat model I could not break the two-runtime-gate design without either (a) writing deliberately evasive code or (b) editing a guard file — both explicitly out of model and both equally fatal to the current scanner approach. What this design cannot ever give you is a *proof* that no evasive route exists. Neither can the scanner; the difference is that this design stops paying for the attempt.

---

## Appendix — inspection and verification record

**Artifacts inspected (this worktree, HEAD `d088758`):**
- `AGENTS.md` (full); `CLAUDE.md` + `.claude/rules/repo-primer.md` (full, via project context injection)
- `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md` (full, 1,080 lines; SHA-256 verified `82d241ad…`)
- `work/review/REV-0105/request.md` (full; SHA-256 verified `4ab036b9…`) and `result.md` (full; SHA-256 verified `6a1146e8…`)
- `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md` (full, incl. amendments 1–6)
- `tests/execution_core/approved_schema_digest.py` (full)
- Held-suite guard regions: `test_persistence_schema.py` (1–80), `test_persistence_repository.py` (1–60), `test_persistence_directness.py` (1–60), `test_persistence_runtime_checkpoint_sqlite.py` (1–60)
- `tests/execution_core/test_persistence_write_capability.py` — first 130 lines plus structural counts only (98 top-level defs, 67 settrace/gettrace references, 229 `sqlite3` token occurrences), per the handoff's instruction not to re-review it exhaustively
- `app/execution_core/persistence/schema.py` — only the `_require_exact_approved_ddl_digest` / `install_schema` region (~4745–4783) via targeted search
- `pyproject.toml` (full), root `conftest.py` (full)

**Environment claims verified by command:** HEAD commit and tree; remote tip `51207c0d…` and 23-ahead count; single modified file in status; WIP file SHA-256 `2978d800…`, 465,566 bytes, 12,874 lines; `fa260c7` tree `8599f65b…`; all three listed artifact SHA-256s match; no `REV-0106` directory exists; exactly 49 Python files under `app/execution_core` + `tests/execution_core` (18+31); `execution_core` referenced nowhere in `app/` outside its own package; `sqlite3` token present in 2 app files and 9 test files of the corpus.

**Not verified:** I did not run pytest, any held suite, the scanners, or any project import; opened no database and executed no DDL (prohibited). I did not verify the DDL/catalog/manifest SHA-256s against file contents (took the locked values as recorded context). I did not read the REV-0079…REV-0104 packet bodies, `AUDIT-0001-quarantine-treadmill.md`, the `FINDING-*` files, ADR-020…022, or anything in Downloads (blinding + scope). I did not independently reproduce any REV-0105 finding (reviewer-reported, consistent with the code architecture I inspected). The four held suites' *full* bodies beyond their guard regions are unreviewed. Scan-time figures (122s/28s/104s/~170s/~270s) are author/handoff observations I did not re-measure. The claim that all installing fixtures gate-before-connect was directly verified in three of four held suites; for `test_persistence_runtime_checkpoint_sqlite.py` it rests on its import of the gated `test_persistence_repository` fixtures plus the WO/gate-doc record, not direct inspection of every fixture.
