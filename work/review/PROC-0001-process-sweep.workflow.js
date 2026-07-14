export const meta = {
  name: 'proc-0001-process-sweep',
  description: 'Sweeping review of the TDD process, review processes, and working practices — find where the next SOL-F-002 hides',
  whenToUse: 'Ameen 2026-07-12: "conduct a sweeping review to improve our test-driven development processes, review processes, and other areas". Launch after the SOL-0001 crosswise workflow completes.',
  phases: [
    { title: 'Audit', detail: 'six lenses over process docs + their actual practice in the repo record' },
    { title: 'Verify', detail: 'refute each proposed improvement against the repo record' },
    { title: 'Synthesize', detail: 'ranked, evidenced improvement plan' },
  ],
}

const COMMON = `You are auditing the WORKING PRACTICES of repo /home/user/automation-alpaca —
not hunting code bugs. The question is always: where would the NEXT miss come from, and what
process change would have caught the LAST ones earlier? Ground truth for "the last ones":
(a) REV-0023 Phase A found 8 finding-clusters that seven prior work orders' discipline missed
(work/review/REV-0023/phase-a.md); (b) the SOL-0001 crosswise intake found 2 P0s that even
Phase A's four critics missed (work/collab/SOL-0001/incumbent-findings-triage.md +
findings.md); (c) the incident log inside work/completed/keep/*/fable-done.md files (git-
checkout wiping uncommitted work TWICE; a mutation-check that reported KILLED-0-failures
because a -k selector matched nothing; a WO closed with "full gate green" that was ruff-red at
the tip). Read what you cite. Evidence = file paths + quotes from THIS repo, not general
software wisdom. Propose few, sharp changes — a process doc nobody can hold in their head is
itself a process failure. Your final message is raw data for the orchestrator.`

const PROPOSALS = {
  type: 'object',
  required: ['proposals', 'held'],
  properties: {
    proposals: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'target', 'problem_evidence', 'change', 'cost'],
        properties: {
          id: { type: 'string' },
          target: { type: 'string', description: 'which doc/process artifact changes' },
          problem_evidence: { type: 'string', description: 'the repo-record miss this would have prevented, with paths/quotes' },
          change: { type: 'string', description: 'the exact change, small enough to apply' },
          cost: { enum: ['trivial', 'moderate', 'heavy'] },
        },
      },
    },
    held: { type: 'array', items: { type: 'string' }, description: 'practices audited and found GOOD as-is, with why' },
  },
}

const VERDICT = {
  type: 'object',
  required: ['refuted', 'reason'],
  properties: { refuted: { type: 'boolean' }, reason: { type: 'string' } },
}

phase('Audit')
const LENSES = [
  { key: 'tdd-evidence', prompt: `LENS: TDD + EVIDENCE DISCIPLINE. Read .ai-os/templates/fable-core-v3.md (incl. the v3.1 amendment), .claude/skills/fable/SKILL.md, and 5+ fable-done.md files under work/completed/keep/. Compare the protocol to its PRACTICE: where did RED-first actually get skipped or degraded to mutation-RED? Where did "fresh pasted evidence" degrade (the summary-line-suppressed container, the -k selector no-op)? Is the evidence: block format actually used? Propose changes that make violations STRUCTURALLY visible rather than exhortations.` },
  { key: 'review-lenses', prompt: `LENS: REVIEW ARCHITECTURE. Read .ai-os/core/15_CROSS_MODEL_REVIEW.md, 16_CROSS_MODEL_BUILD.md, 17_INTERNAL_ADVERSARIAL_REVIEW.md (just adopted — critique it too), work/review/REV-0023/phase-a.md, and the SOL-0001 triage. The known residual: even with R1-R6, what class of defect STILL gets through? (e.g. cross-module emergent behavior, performance, config/deployment, the cockpit UI, docs drift). Is there a cheap standing lens for each? Which of R1-R6 will be skipped in practice because they're expensive, and what's the minimum-viable version?` },
  { key: 'invariants-registry', prompt: `LENS: THE INVARIANTS REGISTRY AS AN ORACLE. Read docs/INVARIANTS.md end to end. Audit: which registered invariants have NO pinning test listed or a stale one? Which use vague scope words ("never", "always") without naming the observable scope? Sample 5 invariants and check their pinned-by tests exist and still assert the statement. Is the registry actually used by reviews (grep work/review for INV- references) or is it write-only? Propose registry hygiene rules with evidence.` },
  { key: 'workorder-lifecycle', prompt: `LENS: WORK-ORDER LIFECYCLE + LEDGER. Read .ai-os/templates/work-order.md, work/ledger.jsonl (all entries), the work/queue and work/completed trees. Audit: branch-hygiene slips recorded (WO-0020, 0024, 0025, 0027 ran on the integration branch — why did the process not prevent recurrence after the first note?); allowed_paths drafting errors (WO-0026 had to amend at execution start); WIP-commit-before-mutation practice (adopted mid-wave after a wipe incident — is it written anywhere?). Propose the smallest checklist/template changes that would have prevented each recorded slip.` },
  { key: 'session-continuity', prompt: `LENS: SESSION CONTINUITY + STATE ARTIFACTS. Read work/active/W3-STATE.md history (git log -p -- work/active/W3-STATE.md | head -400), .ai-os/core/13_SESSION_LENGTH_AND_CONTEXT_HYGIENE.md. The state file went stale mid-wave once (REV-0023 CC-07). Audit: what does the state file capture vs what post-compaction work actually needed? Are deferred-log items structurally guaranteed to surface in the next WO's gate, or do they rely on memory? Propose the minimal structure change (not more prose) that makes deferrals and incidents flow forward automatically.` },
  { key: 'toolchain-env', prompt: `LENS: TOOLCHAIN + ENVIRONMENT REPRODUCIBILITY. Read constraints.txt, requirements.txt, .importlinter, pyproject/CI config if present, and the W3-STATE toolchain notes (shim shadowing; Python 3.11 container vs 3.12 authoritative; pytest summary line suppressed; weekend wall clock breaking phase-dependent tests until clocks were pinned). Each of these cost real debugging time. Propose: what belongs in a session-start preflight script (checked into the repo) that asserts the environment before any gate run is trusted, and what test-suite conventions (e.g. the fixed Wednesday clock) should be codified where new tests will actually see them (conftest? a testing-model doc?).` },
]
const audits = await parallel(LENSES.map(l => () =>
  agent(`${COMMON}\n${l.prompt}`, { label: `audit:${l.key}`, schema: PROPOSALS })))

phase('Verify')
const all = audits.filter(Boolean).flatMap(a => a.proposals)
log(`raw proposals: ${all.length}`)
const verified = await parallel(all.map(p => () =>
  agent(`${COMMON}\nADVERSARIALLY REFUTE this process proposal: target=${p.target}; change=${p.change}; claimed evidence=${p.problem_evidence.slice(0, 400)}. Refute if: the cited miss would NOT actually have been prevented; the change duplicates an existing rule (cite it); the ongoing cost exceeds the miss it prevents; or the evidence misreads the repo record (check the cited files). Default refuted=true when in doubt — process bloat is itself a failure mode this repo names.`,
    { label: `verify:${p.id}`, phase: 'Verify', schema: VERDICT })
    .then(v => ({ ...p, confirmed: v ? !v.refuted : false }))))

phase('Synthesize')
const confirmed = verified.filter(Boolean).filter(p => p.confirmed)
const heldAll = audits.filter(Boolean).flatMap(a => a.held)
const memo = await agent(`${COMMON}\nSYNTHESIZE the process sweep into a ranked improvement
plan. CONFIRMED proposals: ${JSON.stringify(confirmed, null, 1)}\nPractices audited and HELD
good: ${JSON.stringify(heldAll, null, 1)}\nProduce markdown: (1) top changes ranked by
(misses-prevented / ongoing-cost), each with its repo-record evidence and the EXACT edit;
(2) a "do not add" list — refuted/bloat proposals worth recording so they aren't re-proposed;
(3) which changes need Ameen's gate (template/OS changes) vs which the implementation seat can
apply under standing discipline. Keep the whole plan holdable in one head.`,
  { label: 'synthesize', effort: 'high' })

return { confirmed_count: confirmed.length, held: heldAll, memo }
