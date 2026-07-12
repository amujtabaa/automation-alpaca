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
  { key: 'working-order-predicate', prompt: `The working-order predicate is LIVE-derived (app.sellside.policy._live_working_order_id; FILLED/CANCELED/REJECTED terminals kill liveness). The OLD baseline predicate ('any submit event EVER' -> force REPRICE) was a bug (REV-0022 F4). Check sol_policy's SUBMIT-vs-REPRICE selection: if it reproduces the monotone predicate, every Sol second leg gets refused_stale at our seam - P1. Trace their code AND run a two-leg scenario through it if feasible.` },
  { key: 'reduce-only-seam', prompt: `The store now gates SELL qty against live position (INV-084) and write-time qty violations refuse as 'refused_stale'. Check whether Sol's tests assert venue submission in scenarios our seam now refuses, and whether their sizing can emit qty > remaining.` },
  { key: 'stale-vs-defect', prompt: `Write-time rejections are now split: qty_ceiling/structural refuse benignly (refused_stale, no freeze); floor/ttl/phase/cooldown/budget + reduce_only freeze with ENVELOPE_PLAN_DIVERGENCE (WO-0029A). Check Sol's docs/tests for assumptions about divergence-freeze behavior that the amendment changed.` },
]
const drift = await parallel(DRIFT_ROWS.map(row => () =>
  agent(`${COMMON}\nLENS: DRIFT ROW '${row.key}'. Sol coded against a pre-remediation baseline.
${row.prompt}\nRead the relevant app/ code at CURRENT tip to ground the comparison. Findings
need file:line on BOTH sides (sol_policy.py and app/).`,
    { label: `drift:${row.key}`, phase: 'Drift', schema: FINDINGS })))

phase('Adversarial')
const adv = await parallel([
  () => agent(`${COMMON}\nLENS: MUTATION-CRITIC on THEIR tests. Copy ${ROOT} to a scratch dir,
mutate the COPY only: (a) delete/neuter their ratchet or monotonicity mechanism, (b) neuter
their fade/hold trigger, (c) break one hard-rail check. Run THEIR suite against each mutant
(one at a time). A survivor = their suite is decorative on that mechanism (P1/P2 finding, the
repo's TC-01 lesson). Paste each mutant diff + suite tail. Restore nothing in the real tree —
you never touched it (verify + state 'git status --porcelain' is clean for ${ROOT}).`,
    { label: 'adv:mutation', schema: FINDINGS }),
  () => agent(`${COMMON}\nLENS: OUR TAPES vs THEIR POLICY. Adapt the repo's regime tapes
(tests/test_wo0021_regime_tapes.py walk/envelope helpers, the WO-0028 ATR-expansion-collapse
tape, tests/test_wo0020_envelope_tick.py crash_tape) to drive sol_policy.decide in a scratch
script. Assert: every exit above floor, sized within remaining, ratchet never loosens, no
action out of allowed phases/TTL (validate_action must pass on every PlannedAction they emit).
Any rail-violating or malformed action is P0/P1. Paste the script path + decisive output.`,
    { label: 'adv:tapes', schema: FINDINGS }),
  () => agent(`${COMMON}\nLENS: STRUCTURAL-HOLD ATTACK. Their headline territory is the
structural-hold mechanism (FINDING-W3-lase-pullback-structural-hold: hold a pull-to-VWAP on
low-vol grinds WITHOUT violating rails). Build the adversarial tapes: (1) grind-then-orderly-
pullback (must HOLD: this is the P2 finding's scenario - if they hold it, that is a HELD entry
of high value), (2) grind-then-true-breakdown through the floor (must EXIT above floor - a hold
below floor or missed stop is P0), (3) chop designed to whipsaw their hold trigger. Paste
outputs. Compare against our incumbent compute_working_stop on the same tapes for the memo.`,
    { label: 'adv:structural-hold', schema: FINDINGS }),
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
const verified = await parallel(deduped.map(f => () =>
  parallel([
    () => agent(`${COMMON}\nADVERSARIALLY REFUTE this finding about the Sol drop: [${f.severity}] ${f.claim}
(evidence claimed: ${f.evidence.slice(0, 500)}). Reproduce it yourself from scratch. Default to
refuted=true if you cannot reproduce it or the evidence does not support the severity.`,
      { label: `verify:${f.id}:a`, phase: 'Verify', schema: VERDICT }),
    () => agent(`${COMMON}\nSECOND INDEPENDENT REFUTER, different angle (read the code path the
finding names rather than re-running the reproducer): [${f.severity}] ${f.claim}. refuted=true
unless the code genuinely shows it.`,
      { label: `verify:${f.id}:b`, phase: 'Verify', schema: VERDICT }),
  ]).then(vs => ({ ...f, confirmed: vs.filter(Boolean).filter(v => !v.refuted).length >= 1, verdicts: vs }))
))

phase('Synthesize')
const confirmed = verified.filter(Boolean).filter(f => f.confirmed)
const heldAll = [...conf, ...drift, ...adv].filter(Boolean).flatMap(r => r.held)
const memo = await agent(`${COMMON}\nSYNTHESIZE the crosswise review. CONFIRMED findings:
${JSON.stringify(confirmed.map(f => ({ id: f.id, sev: f.severity, claim: f.claim })), null, 1)}
HELD (not falsified): ${JSON.stringify(heldAll, null, 1)}
Produce (as your final text, markdown): (1) verdict per INTAKE-CHECKLIST section; (2) the
consolidation recommendation split: merge-now candidates (contract-conformant, rail-safe,
mutation-hardened) vs W4-bake-off items (empirical mechanism-quality claims); (3) the W4
harness spec addendum (exact shared scenario set incl. the structural-hold tapes, five-metric
scorer, no-peeking rule); (4) the drift-remediation list Sol's operator needs (what to rebase
onto the remediated contract). Do not soften findings.`,
  { label: 'synthesize', effort: 'high' })

return {
  confirmed,
  held: heldAll,
  memo,
  counts: { raw: allFindings.length, deduped: deduped.length, confirmed: confirmed.length },
}
