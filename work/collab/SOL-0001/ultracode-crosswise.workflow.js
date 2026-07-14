export const meta = {
  name: 'sol-0001-crosswise-review',
  description: 'Ultracode crosswise review of Sol/Codex SOL-0001 deliverables: conformance, drift, adversarial, verify, synthesize',
  whenToUse: 'Run when work/collab/SOL-0001/impl/{sol_policy.py,test_sol_policy.py,sol_conformance_plugin.py} + MANIFEST.md exist in the working tree. Ameen invoked ultracode for SOL-related work (2026-07-12).',
  phases: [
    { title: 'Conformance', detail: 'signature/purity, their suite on our toolchain, plugin inspection, manifest-vs-reality' },
    { title: 'Drift', detail: 'one agent per post-baseline contract change (WO-0024..0027)' },
    { title: 'Adversarial', detail: 'mutation-critic on their tests; our tapes vs their policy; structural-hold attack' },
    { title: 'Verify', detail: 'independent refuters per finding' },
    { title: 'Synthesize', detail: 'consolidation memo + W4 bake-off spec inputs' },
  ],
}

const ROOT = 'work/collab/SOL-0001/impl'
const CHECKLIST = 'work/collab/SOL-0001/INTAKE-CHECKLIST.md'

const FINDINGS = {
  type: 'object',
  required: ['findings', 'held'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'severity', 'claim', 'evidence'],
        properties: {
          id: { type: 'string' },
          severity: { enum: ['P0', 'P1', 'P2', 'P3'] },
          claim: { type: 'string' },
          file_line: { type: 'string' },
          evidence: { type: 'string', description: 'pasted decisive output' },
        },
      },
    },
    held: { type: 'array', items: { type: 'string' }, description: 'claims attacked and NOT falsified, with how' },
  },
}

const VERDICT = {
  type: 'object',
  required: ['refuted', 'reason'],
  properties: { refuted: { type: 'boolean' }, reason: { type: 'string' }, evidence: { type: 'string' } },
}

const COMMON = `You are reviewing a RIVAL implementation delivered by another model (GPT Sol via
Codex) into ${ROOT}/ of repo /home/user/automation-alpaca. Read ${CHECKLIST} FIRST — it is the
review contract. Evidence discipline: every claim needs fresh pasted command output from THIS
container (pinned toolchain: ruff 0.15.20 / mypy 2.2.0 / pytest 9.1.1). You may run their code
and tests; you may temporarily copy files into a scratch dir; you MUST NOT modify anything
under app/, tests/, or ${ROOT}/ (verify 'git status --porcelain' clean at your end and say so).
The frozen contract: decide(envelope, snapshots, *, now, history) returning app.sellside.types
variants; purity (no wall clock / RNG / IO at decision time). Do not trust their MANIFEST —
verify it. Your final message is raw data for the orchestrator, not prose for a human.`

phase('Conformance')
const conf = await parallel([
  () => agent(`${COMMON}\nLENS: SIGNATURE + PURITY. Read every line of ${ROOT}/sol_policy.py.
Check: exact frozen signature; no input mutation; return taxonomy; grep + trace every time/RNG/
IO source (datetime.now, time.time, utcnow at decide-time, random, open, network). Check import
surface: only the allowed contract modules. Report violations as findings with file:line.`,
    { label: 'conf:purity', schema: FINDINGS }),
  () => agent(`${COMMON}\nLENS: THEIR SUITE ON OUR TOOLCHAIN. Run their tests
(pytest ${ROOT}/test_sol_policy.py -q, adapt paths/imports if their layout needs sys.path help —
document exactly what you did). Paste the tail. Any failure, error, warning-as-error, or
collection problem is a finding. Also count their tests and note any skipped/xfail.`,
    { label: 'conf:suite', schema: FINDINGS }),
  () => agent(`${COMMON}\nLENS: CONFORMANCE PLUGIN. Read ${ROOT}/sol_conformance_plugin.py in
FULL before executing anything. Determine what it does (adapter? pytest plugin? monkeypatch?).
If it persistently monkeypatches app/ modules, that is a P1 finding. If safe, run whatever
conformance flow it defines and paste results. If unsafe, do NOT run it — report why.`,
    { label: 'conf:plugin', schema: FINDINGS }),
  () => agent(`${COMMON}\nLENS: MANIFEST vs REALITY. Read ${ROOT}/../MANIFEST.md (and any memo/
tape-catalog files in the drop). For every checkable claim (what baseline SHA, what runs, what
was 'removed as unimplemented'), verify against the actual code. Unverifiable or false claims
are findings. Extract: the baseline SHA they coded against (needed by the Drift phase) — put it
in a finding-or-held entry explicitly labelled BASELINE.`,
    { label: 'conf:manifest', schema: FINDINGS }),
])

phase('Drift')
const DRIFT_ROWS = [
  { key: 'validate-action-rails', prompt: `validate_action gained ttl + session_phase hard rails and callers thread an injected now (WO-0024). Check: does sol_policy call the SHARED app.sellside.policy.validate_action for its plan-time D-3 half, or fork/reimplement it? A fork missing ttl/phase is a P1 finding; a fork at all is P2.` },
  { key: 'working-order-predicate', prompt: `The working-order predicate is LIVE-derived (app.sellside.policy._live_working_order_id; FILLED/CANCELED/REJECTED terminals kill liveness). The OLD baseline predicate ('any submit event EVER' -> force REPRICE) was a bug (REV-0023 F4). Check sol_policy's SUBMIT-vs-REPRICE selection: if it reproduces the monotone predicate, every Sol second leg gets refused_stale at our seam - P1. Trace their code AND run a two-leg scenario through it if feasible.` },
  { key: 'reduce-only-seam', prompt: `The store now gates SELL qty against live position (INV-084) and write-time qty violations refuse as 'refused_stale'. Check whether Sol's tests assert venue submission in scenarios our seam now refuses, and whether their sizing can emit qty > remaining.` },
  { key: 'stale-vs-defect', prompt: `Write-time rejections are now split: qty_ceiling/structural refuse benignly (refused_stale, no freeze); floor/ttl/phase/cooldown/budget + reduce_only freeze with ENVELOPE_PLAN_DIVERGENCE (WO-0029A). Check Sol's docs/tests for assumptions about divergence-freeze behavior that the amendment changed.` },
]
const drift = await parallel(DRIFT_ROWS.map(row => () =>
  agent(`${COMMON}\nLENS: DRIFT ROW '${row.key}'. Sol coded against a pre-remediation baseline.
${row.prompt}\nRead the relevant app/ code at CURRENT tip to ground the comparison. Findings
need file:line on BOTH sides (sol_policy.py and app/).`,
    { label: `drift:${row.key}`, phase: 'Drift', schema: FINDINGS })))

phase('Adversarial')
// Right-sized 2026-07-12 (Ameen): this container caps workflow concurrency at
// ~2 agents, so breadth must come from CHEAP TIERED agents with hard budgets,
// not from a wide fan-out of session-model heavyweights. Conformance/Drift
// prompts above are byte-identical to the first run so resume returns them
// from cache.
const GUARD = `BUDGET GUARDS (hard): at most ~30 tool calls; prefix every test-suite run with
'timeout 240'; if a command would exceed that, kill it and record the timing as a finding.
If you hit the budget, STOP and return what you have marked partial=true in a held entry.
Scope: review ONLY the Sol drop vs the CURRENT tip contract — do not re-audit incumbent
history, past waves, or anything the intake checklist does not name.`

const adv = await parallel([
  () => agent(`${COMMON}\n${GUARD}\nLENS: MUTATION-CRITIC on THEIR tests. Copy ${ROOT} to a
scratch dir; make THREE mutants of the COPY, one at a time: (a) neuter their ratchet/
monotonicity mechanism, (b) neuter their fade/hold trigger, (c) break one hard-rail check.
Run THEIR suite per mutant ('timeout 240 pytest <scratch>/test_sol_policy.py -q -x'). A
survivor = decorative suite on that mechanism (P1/P2, the TC-01 lesson). Paste each mutant
diff line + suite tail. Never touch the real tree.`,
    { label: 'adv:mutation', schema: FINDINGS, model: 'sonnet', effort: 'medium' }),
  () => agent(`${COMMON}\n${GUARD}\nLENS: OUR TAPES vs THEIR POLICY. ONE scratch script that
drives sol_policy.decide over exactly THREE tapes: the WO-0020 crash_tape (stop exit), the
WO-0028 ATR-expansion-collapse shape (ratchet), and one thin/gappy tape of your design. For
every PlannedAction they emit assert: app.sellside.policy.validate_action passes, limit >=
floor, 0 < qty <= remaining. Any violation is P0/P1 with the pasted action. Do not build more
tapes than these three.`,
    { label: 'adv:tapes', schema: FINDINGS, model: 'sonnet', effort: 'medium' }),
  () => agent(`${COMMON}\n${GUARD}\nLENS: STRUCTURAL-HOLD ATTACK (their headline mechanism —
the one lens worth a strong model). THREE tapes only: (1) low-vol grind then orderly
pull-to-VWAP — holding it is the prize (record as held-of-high-value if they do), (2) grind
then TRUE breakdown through the floor — any hold below floor or missed stop is P0, (3) chop
built to whipsaw their hold trigger. Compare against incumbent compute_working_stop on the
same tapes (one table). Paste decisive outputs.`,
    { label: 'adv:structural-hold', schema: FINDINGS, model: 'opus', effort: 'medium' }),
])

phase('Verify')
const allFindings = [...conf, ...drift, ...adv].filter(Boolean).flatMap(r => r.findings)
log(`raw findings: ${allFindings.length}`)
const seen = new Set()
const deduped = allFindings.filter(f => {
  const k = `${f.severity}|${f.claim.slice(0, 80)}`
  if (seen.has(k)) return false
  seen.add(k)
  return true
})
// Tiered verification: P0/P1 get two INDEPENDENT cheap refuters and survive
// only if NEITHER refutes (a false P0 against a rival's work poisons the
// collaboration); P2/P3 get one refuter. All sonnet — refutation is targeted
// reproduction, not open-ended judgment.
const p01 = deduped.filter(f => f.severity === 'P0' || f.severity === 'P1')
const rest = deduped.filter(f => f.severity !== 'P0' && f.severity !== 'P1')
log(`verifying: ${p01.length} P0/P1 (2 refuters), ${rest.length} P2/P3 (1 refuter)`)
const refute = (f, angle) => agent(
  `${COMMON}\nBUDGET: <=15 tool calls. ADVERSARIALLY REFUTE (${angle}): [${f.severity}] ${f.claim}
Evidence claimed: ${String(f.evidence).slice(0, 400)}
${angle === 'reproduce' ? 'Reproduce it yourself from scratch; refuted=true if you cannot.' :
  'Read the exact code path the finding names; refuted=true unless the code genuinely shows it.'}`,
  { label: `verify:${f.id}:${angle[0]}`, phase: 'Verify', schema: VERDICT, model: 'sonnet', effort: 'medium' })
const verifiedP01 = await parallel(p01.map(f => () =>
  parallel([() => refute(f, 'reproduce'), () => refute(f, 'code-read')])
    .then(vs => ({ ...f, confirmed: vs.filter(Boolean).every(v => !v.refuted), verdicts: vs }))))
const verifiedRest = await parallel(rest.map(f => () =>
  refute(f, 'code-read').then(v => ({ ...f, confirmed: v ? !v.refuted : false }))))
const verified = [...verifiedP01, ...verifiedRest]

phase('Synthesize')
const confirmed = verified.filter(Boolean).filter(f => f.confirmed)
const heldAll = [...conf, ...drift, ...adv].filter(Boolean).flatMap(r => r.held)
const memo = await agent(`${COMMON}\nSYNTHESIZE the crosswise review. CONFIRMED findings:
${JSON.stringify(confirmed.map(f => ({ id: f.id, sev: f.severity, claim: f.claim })), null, 1)}
HELD (not falsified): ${JSON.stringify(heldAll, null, 1)}
Produce (markdown): (1) verdict per INTAKE-CHECKLIST section; (2) consolidation split:
merge-now candidates vs W4-bake-off items; (3) W4 harness spec addendum (shared scenario set
incl. structural-hold tapes, five metrics, no-peeking); (4) drift-remediation list for Sol's
operator. Do not soften findings.`,
  { label: 'synthesize', model: 'opus', effort: 'high' })

return {
  confirmed,
  held: heldAll,
  memo,
  counts: { raw: allFindings.length, deduped: deduped.length, confirmed: confirmed.length },
}
