export const meta = {
  name: 'rev0023-phase-a2-internal-review',
  description: 'Holistic internal adversarial review of the assembled W3 remediation+WO-0030 delta (f092ca7..HEAD) before external Codex Phase B — doc-17 lenses, R7-R11 right-sized',
  whenToUse: 'Before handing the W3 remediation delta to external cross-model review; draws blood internally first.',
  phases: [
    { title: 'Review', detail: '7 module-scoped adversarial finder lenses (tiered models)' },
    { title: 'Verify', detail: 'per-finding adversarial refuters (2 for P0/P1, 1 for P2/P3)' },
    { title: 'Synthesize', detail: 'dedup + rank + REV packet (opus)' },
  ],
}

// ---- shared context inlined into every agent (R5: subagents do NOT inherit CLAUDE.md) ----
const BASE = 'f092ca7'
const TIP = '3913605'
const PREAMBLE = `
You are an adversarial reviewer of a paper-first Alpaca trading platform (Spine v2 execution
architecture). Repo root is the current working directory; the working tree is CLEAN at the
review tip ${TIP}, so reading files gives you the exact code under review. The delta under review
is \`git diff ${BASE}..HEAD\` — the assembled W3 remediation (WO-0024..0028, WO-0029A) plus
WO-0031 (sell-side trail/bar integrity) and WO-0030 (interface lift). Review ONLY this delta and
its blast radius at the current tip (doc-17 R10 phase-relevance): do NOT re-audit pre-remediation
waves; historical incidents are calibration for WHERE bugs hide, never scan targets.

CHARTER: this is a REVIEW. Fix NOTHING, edit no source, weaken no test. Your job is to FIND
defects the green gate (ruff+mypy+pytest all pass at tip) does not catch — Phase A already found
two P0s that passed every gate. Report structured findings only.

SAFETY-CORE HYPOTHESES you are testing (a violation of ANY is at least P1; several are P0):
 H1  PAPER only; no live trading; kill switch blocks ALL new order intent (activation, resume,
     staging are new intent and must be refused while HALTED).
 H2  Submitted != filled; ONLY deduped fill events change position/remaining quantity
     (record_envelope_fill is the sole remaining_quantity writer; INV-5 exactly-once on dedupe_key).
 H3  Single writer: only the engine mutates order/fill/position/envelope state; SUBMITTED/ACCEPTED
     structurally cannot change quantity.
 H4  Reduce-only hard rail (INV-084): a staged envelope action may never increase a long position;
     enforced at write time against the live fill-derived position read under the SAME lock.
 H5  A ceiling-violated / breached envelope is NEVER silently COMPLETED (INV-085); overfill/negative
     facts are recorded + quarantined, never hidden.
 H6  Invalid market data (stale/NaN/negative/crossed/out-of-range) must NEVER drive sizing, stops,
     regime, or submission — the WHOLE active tape is screened, not just the latest row (INV-086 / SOL-F-003).
 H7  Lifetime monotonicity (INV-086 / SOL-F-002): the working stop never loosens across urgency
     epochs or intra-bucket rewrites over an envelope's lifetime (not merely within one call).
 H8  Ambiguous/timeout broker outcomes -> TIMEOUT_QUARANTINE, reconcile via deterministic
     client_order_id; NEVER blind-resubmit/blind-replace.
 H9  Supersession refuses while a live venue order is working, conserves remaining quantity, and
     sweeps the old mandate's staged CREATED orders atomically (INV-077).
 H10 Strict dual-store parity: InMemoryStateStore and SqliteStateStore accept/reject/event/err
     IDENTICALLY for every envelope operation.
 H11 Engine determinism: injected clock only (no bare datetime.now/time.time in engine logic), no
     unseeded randomness, deterministic ids/queues.
 H12 The D-3 "bounds checked twice": validate_action at plan time AND stage_envelope_action at write
     time. Disagreement classification (WO-0029A): deterministic rails (floor/ttl/session_phase/
     cooldown/budget/reduce_only) -> DEFECT (freeze + ENVELOPE_PLAN_DIVERGENCE); state-dependent
     rails (qty_ceiling, structural) -> benign STAGE_REFUSED_STALE (no freeze, replan next tick, and
     a refused_stale must NOT burn the tranche entitlement).

Key files (read what your lens needs):
 app/sellside/{policy,trails,bars,indicators,regime,types}.py  — pure sell-side policy + math
 app/store/core.py            — pure planners (plan_envelope_transition/_supersede/_fill/_stage)
 app/store/{memory,sqlite}.py — the two concrete stores (dual-store parity target)
 app/store/base.py            — StateStore ABC (WO-0030 interface lift)
 app/reconciliation.py        — redrive re-validation, staleness ceiling, inferred-fill bridge, executor
 app/monitoring.py            — tick drive, working-order predicate, fill bridge
 docs/adr/ADR-010-execution-envelope.md , docs/INVARIANTS.md (INV-077..086)

OUTPUT: return ONLY the structured object. Each finding needs a CONCRETE adversarial probe:
specific inputs / interleaving / call sequence -> the wrong output or violated invariant. A finding
with no concrete failing scenario is not a finding — put those in not_falsified instead. Rank
severity P0 (safety-core violation / silent wrong position or oversell / kill bypass), P1 (correctness
defect with a real trigger), P2 (mechanism gap / weak guard), P3 (nit / clarity). Also return
not_falsified: hypotheses you actively probed and could NOT break (so coverage is auditable).`

const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['findings', 'not_falsified', 'coverage_note'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['title', 'severity', 'module', 'location', 'mechanism', 'adversarial_probe', 'confidence'],
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: ['P0', 'P1', 'P2', 'P3'] },
          module: { type: 'string', description: 'file path or subsystem' },
          location: { type: 'string', description: 'file:line or function/symbol' },
          mechanism: { type: 'string', description: 'the defect: what the code does wrong and why' },
          adversarial_probe: { type: 'string', description: 'concrete inputs/interleaving/sequence -> wrong output or violated invariant' },
          invariant_violated: { type: 'string', description: 'H1..H12 / INV-xxx, or empty' },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
      },
    },
    not_falsified: { type: 'array', items: { type: 'string' } },
    coverage_note: { type: 'string', description: 'what you covered and any module you could not reach in budget' },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['verdict', 'reasoning', 'counter_probe'],
  properties: {
    verdict: { type: 'string', enum: ['CONFIRMED', 'REFUTED', 'UNCERTAIN'] },
    reasoning: { type: 'string', description: 'why the probe does or does not actually reproduce, tracing the real code path' },
    counter_probe: { type: 'string', description: 'the specific code fact / guard / call path that confirms or refutes' },
    corrected_severity: { type: 'string', enum: ['P0', 'P1', 'P2', 'P3', 'none'] },
  },
}

// ---- 7 module-scoped finder lenses (doc-17 five lenses, expanded per blast radius; R1/R7/R10) ----
const LENSES = [
  {
    key: 'pure-math',
    model: 'opus', effort: 'high',
    label: 'find:module-semantics(sellside+planners)',
    brief: `LENS = MODULE-SEMANTICS / PURE-MATH ATTACKER (doc-17 lens 5 — the lens that caught both SOL P0s).
Scope: app/sellside/policy.py, trails.py, bars.py, indicators.py, regime.py, and the PURE planners in
app/store/core.py (plan_envelope_transition, plan_supersede_envelope, plan_envelope_fill,
plan_stage_envelope_action, validate_action usage). Probe each public function DIRECTLY with tiny
hand-built adversarial inputs against its own docstring/contract — no assembled-stack scaffolding.
Attack especially (R2 invariant-frame over the OBSERVABLE SCOPE, R3 boundary-of-trust over EVERY ingress):
 - H7 lifetime monotonicity of the working stop: construct urgency-epoch sequences and intra-bucket
   rewrites where compute_working_stop / _urgency_at / the ratchet could still loosen the stop across
   the envelope lifetime (not just within one call). Check last_bar_open bucket exclusion and per-step
   urgency_at cannot be defeated by bar bucketing, gaps, or a re-aggregated tape.
 - H6 whole-tape screening: find any code path that lets a stale/NaN/negative/crossed/zero/huge print
   in HISTORY (not just the latest snapshot) reach ref-high / ATR / VWAP / regime / stop / sizing.
   _snapshot_invalid_reasons coverage vs every feature consumer.
 - the reported+upsizing probe (SOL-F-004 adjudication): can the participation ClampNote be dropped,
   or _rejected_probe_count mis-count (double-count / miss a terminal), or the doubling exceed remaining,
   or a probe be planned that a venue min-size would still reject with no upsize?
 - the tranche latch (DRIFT-SVD-2): can a refused_stale / non-WORKING action burn the tranche, or a real
   tranche submit be counted twice / zero times?
 - planner arithmetic: off-by-one on remaining_quantity, qty_ceiling, budget spend, cooldown math;
   float compares; a BreachSignal vs PlannedAction boundary that hides an oversell.
Report the tiny input that breaks the contract. This is the highest-value lens — be exhaustive.`,
  },
  {
    key: 'concurrency',
    model: 'opus', effort: 'high',
    label: 'find:interleaving(store+reconcile+tick)',
    brief: `LENS = INTERLEAVING / CONCURRENCY ATTACKER (doc-17 lens 2). Scope: the async envelope ops in
app/store/memory.py + sqlite.py (create/transition/supersede/record_envelope_fill/stage/approve),
app/reconciliation.py (redrive_staged_envelope_action, execute_envelope_action, _drive_staged_order,
_apply_inferred_fills), app/monitoring.py (_run_envelopes/_run_one_envelope, fill bridge).
FIRST build the await-point map for each op, THEN attack:
 - H1 kill-during-op: a set_kill_switch (HALTED) landing in any await window of activation / resume /
   stage — can a partial ORDERED intent / CREATED order / accounting event survive under HALTED? (the
   ENG-001 shape claim: no await between the HALTED check and the writes).
 - H2/H3 single-writer + exactly-once: can two ticks, or a tick racing reconciliation redrive, double-spend
   budget, double-stage, or apply a fill twice across a crash/restart (dedupe_key)? Is the budget spent
   exactly once when staging then redriving?
 - WO-0028 memory _atomic: does the in-memory _atomic() truly snapshot AND roll back _envelopes on an
   exception mid-op, or can a half-applied envelope mutation leak (TC-03)? Compare to sqlite _tx rollback.
 - H8 ambiguous outcome: on AmbiguousBrokerError does redrive/execute ALWAYS quarantine (never blind
   re-replace)? Is client_order_id deterministic (= order id)?
 - reduce-only (H4) and current_position read: is the live position re-read INSIDE the same lock/tx as the
   stage write, or is there a torn read across an await?
Report the concrete interleaving (ordered await/step sequence) that produces the bad durable state.`,
  },
  {
    key: 'spec',
    model: 'sonnet', effort: 'high',
    label: 'find:spec-attacker(ADR-010+INV)',
    brief: `LENS = SPEC-ATTACKER (doc-17 lens 1). Read docs/adr/ADR-010-execution-envelope.md and
docs/INVARIANTS.md (INV-077..086) clause by clause, and hunt decisions the code silently took that no
document records, or claims a document makes that the code does not honor. Scope the implementation in
app/store/core.py, memory.py, sqlite.py, reconciliation.py, transitions.py, models.py.
Specifically verify each remediation claim maps to code AND doc:
 - FROZEN->BREACHED edge (INV-085): overfill/ceiling-violation from ACTIVE or FROZEN -> BREACHED, and a
   ceiling-violated envelope is structurally unable to reach COMPLETED. Find any transition table gap.
 - stale-vs-defect split (H12/INV-082): the rail partition (deterministic -> DEFECT/freeze vs
   state-dependent qty_ceiling/structural -> STAGE_REFUSED_STALE). Is the partition in code identical to
   the doc? Any rail mis-filed (e.g. a deterministic rail treated as benign, hiding a real divergence)?
 - supersession (H9/INV-077): refuse-while-live + conserve-remaining + sweep-staged, all in doc and code.
 - working-order predicate (ADR-010 §5): live-derived, killed on FILLED/CANCELED/REJECTED terminals.
 - inferred-fill record-first (ADR-010 §6): the reconciliation bridge records before projecting.
Report each doc<->code divergence with the clause and the code location.`,
  },
  {
    key: 'parity',
    model: 'sonnet', effort: 'high',
    label: 'find:dual-store-parity',
    brief: `LENS = DUAL-STORE PARITY ATTACKER (house mandate H10). For EVERY envelope method changed in the
delta, diff the InMemoryStateStore (app/store/memory.py) behavior against SqliteStateStore
(app/store/sqlite.py) line-of-reasoning by line: create_envelope, get_envelope, list_envelopes,
transition_envelope, supersede_envelope, record_envelope_fill, stage_envelope_action,
approve_envelope_activation, plus the sweep helpers (_cancel_staged_envelope_orders_*), the
_envelope_action_context, and the reduce-only position read (_position_unlocked vs _position_locked).
Find any case where the two stores would: accept vs reject the same input differently; write events in a
different order or with different provenance; raise a different exception type; dedupe differently;
snapshot/rollback differently; or normalize symbols/enums differently. Also check list/filter validation
(require_status_enum) matches. Report the exact input where memory and sqlite diverge.`,
  },
  {
    key: 'mutation',
    model: 'sonnet', effort: 'high', isolation: 'worktree', agentType: 'general-purpose',
    label: 'find:test-critic+discovery-mutation',
    brief: `LENS = TEST-CRITIC / DISCOVERY-MUTATION SWEEP (doc-17 lens 3 + R4). You are in an ISOLATED
WORKTREE — mutate freely; the tree starts clean at the review tip. Your job: find DECORATIVE or VACUOUS
pins in the 20 changed test files, and unguarded load-bearing lines in the changed app modules.
Method (STRICT — follow R4 + the two recorded incidents):
 1. Pick load-bearing lines in the delta's app modules (sellside/policy.py, trails.py, store/core.py
    planners, reconciliation.py redrive, monitoring.py predicate, store/memory.py _atomic + reduce-only).
    Mutate ONE at a time (invert a comparison, drop a screening \`and\`, weaken a bound, no-op a freeze).
 2. Run the RELEVANT tests with EXPLICIT test ids or a -k that you VERIFY collects > 0 tests (the WO-0029A
    -k no-op incident: a 0-failure result from an empty selection is NOT a kill). Prefer:
       timeout 240 python -m pytest tests/test_<file>.py -q  (or specific ::test ids)
 3. A mutation that leaves all tests GREEN = a SURVIVOR = an unguarded module or a vacuous pin. Investigate:
    is the pin's assertion able to DISTINGUISH the mechanism's presence (the WO-0031 vacuous-pin lesson —
    e.g. a tape priced below the floor makes both arms return BreachSignal, so screening on/off compares
    equal)? Record each survivor as a finding (severity by what it leaves unguarded).
 4. Restore between mutations with \`git checkout -- <file>\` (worktree, committed code only). NEVER leave
    a mutation applied. Verify \`git status --porcelain\` is empty before finishing.
Budget ~30 tool calls; return partial at budget. Report survivors as findings; list mutations that were
correctly KILLED in coverage_note.`,
  },
  {
    key: 'completeness',
    model: 'sonnet', effort: 'high',
    label: 'find:completeness-critic',
    brief: `LENS = COMPLETENESS-CRITIC (doc-17 lens 4). Read the fable-done.md files under
work/completed/keep/WO-002*/ , WO-0029A, WO-0030, WO-0031, and the deferred log + open decisions in
work/active/W3-STATE.md. Attack claims-vs-omissions:
 - What did a close-out ASSERT that nothing actually verifies (a claim with no pin)?
 - What did the deferred log BURY that compounds into a live defect at tip? Specifically probe:
   (a) synthetic-fill envelope bridge bypass (reconciliation synthetic fills that skip record_envelope_fill —
       does that break H2 exactly-once or the remaining_quantity accounting?);
   (b) record_envelope_fill price=None poisoning position projection;
   (c) intent->ORDERED linkage gap (envelope fills not advancing SellIntent lifecycle);
   (d) models.py trail_distance docstring vs ATR-multiple semantics — any real consumer misled?
 - The WO-0030 test-guard deviation: independently judge whether widening the fill-mutator set to include
   record_envelope_fill is truly non-weakening, or whether it now lets a real fills-table mutator slip past.
Report each as a finding if it has a concrete failing scenario at tip; otherwise not_falsified.`,
  },
  {
    key: 'interface-lift',
    model: 'sonnet', effort: 'medium',
    label: 'find:wo0030-interface-behavior-preservation',
    brief: `LENS = INTERFACE-LIFT VERIFIER (WO-0030-specific, behavior-preservation). The lift declared the
envelope API on app/store/base.py StateStore and deleted four structural Protocols + every envelope-seam
cast. Verify it is TRULY behavior-preserving and that the new typing does not paper over a real mismatch:
 - Does each of the 8 ABC method signatures EXACTLY match BOTH concrete stores (memory + sqlite)? A
   defaulted/renamed/re-annotated param that silently differs is a finding (mypy checks overrides, but
   check the ABC defaults e.g. EventSource.BROKER_REST / EventAuthority.BROKER_AUTHORITATIVE match).
 - EnvelopeTransitionError relocated to base.py as ValueError subclass + re-exported from core.py: does
   every existing \`except EnvelopeTransitionError\` / \`from app.store.core import EnvelopeTransitionError\`
   still resolve and catch identically? Any caller catching it as StoreError (it is NOT one)?
 - The facade Protocols gained approve_envelope/cancel_envelope/list_envelopes: do the routes now call a
   REAL method on the concrete facade, and is any previously-cast call now reaching a differently-shaped
   method? Any runtime_checkable Protocol isinstance check affected by the new members?
 - TYPE_CHECKING import of PlannedAction/EnvelopeActionStageResult in base.py: any runtime path that needs
   them at runtime (e.g. get_type_hints, pydantic)?
Report concrete regressions; this lens is expected to be mostly not_falsified if the lift is clean.`,
  },
]

// ---------------------------------------------------------------------------------------------
phase('Review')
log(`internal adversarial review of ${BASE}..${TIP}: dispatching ${LENSES.length} finder lenses (tiered)`)
const rawResults = await parallel(
  LENSES.map((L) => () =>
    agent(PREAMBLE + '\n\n' + L.brief, {
      label: L.label,
      phase: 'Review',
      model: L.model,
      effort: L.effort,
      schema: FINDINGS_SCHEMA,
      ...(L.isolation ? { isolation: L.isolation } : {}),
      ...(L.agentType ? { agentType: L.agentType } : {}),
    }).then((r) => (r ? { ...r, _lens: L.key } : null)),
  ),
)

const lensReturns = rawResults.filter(Boolean)
const allFindings = lensReturns.flatMap((r) =>
  (r.findings || []).map((f, i) => ({ ...f, lens: r._lens, _id: `${r._lens}-${i}` })),
)
const notFalsified = lensReturns.flatMap((r) => (r.not_falsified || []).map((s) => `[${r._lens}] ${s}`))
log(`raw findings: ${allFindings.length} across ${lensReturns.length} lenses; verifying`)

// dedup by (module coarse + normalized mechanism prefix); keep highest severity (P0<P1<P2<P3)
const sevRank = { P0: 0, P1: 1, P2: 2, P3: 3 }
const norm = (s) => (s || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().slice(0, 60)
const dedup = new Map()
for (const f of allFindings) {
  const key = `${norm(f.module)}::${norm(f.mechanism)}`
  const prev = dedup.get(key)
  if (!prev || sevRank[f.severity] < sevRank[prev.severity]) dedup.set(key, f)
}
const deduped = [...dedup.values()].sort((a, b) => sevRank[a.severity] - sevRank[b.severity])
log(`deduped to ${deduped.length} findings; ${deduped.filter((f) => sevRank[f.severity] <= 1).length} are P0/P1 (2 refuters each)`)

phase('Verify')
const verifyOne = async (f) => {
  const refuters = sevRank[f.severity] <= 1 ? 2 : 1
  const refuterModel = f.severity === 'P0' ? 'opus' : 'sonnet'
  const prompt =
    PREAMBLE +
    `\n\nLENS = ADVERSARIAL REFUTER. A finder reported this finding. Your DEFAULT is to REFUTE it: trace the
REAL code path at tip and prove the probe does NOT actually reproduce (a guard exists, the path is
unreachable, the invariant already holds, or the severity is inflated). Only return CONFIRMED if you can
follow the probe through the actual code to the bad state. Read the cited files; do not trust the finder's
summary. If genuinely unsure after tracing, return UNCERTAIN with the residual risk.

FINDING (${f.severity}, lens=${f.lens}):
  title: ${f.title}
  module: ${f.module}   location: ${f.location}
  invariant: ${f.invariant_violated || '(none stated)'}
  mechanism: ${f.mechanism}
  adversarial_probe: ${f.adversarial_probe}`
  const votes = await parallel(
    Array.from({ length: refuters }, (_, k) => () =>
      agent(prompt, {
        label: `verify:${f.lens}#${f._id}(${k + 1}/${refuters})`,
        phase: 'Verify',
        model: refuterModel,
        effort: f.severity === 'P0' ? 'high' : 'medium',
        schema: VERDICT_SCHEMA,
      }),
    ),
  )
  const v = votes.filter(Boolean)
  // survives ONLY if NO refuter refuted it (doc-17 R6: P0/P1 survive only if neither refutes)
  const refuted = v.some((x) => x.verdict === 'REFUTED')
  const confirmed = v.some((x) => x.verdict === 'CONFIRMED')
  const status = refuted ? 'REFUTED' : confirmed ? 'CONFIRMED' : 'UNCERTAIN'
  return { ...f, verify: { status, votes: v } }
}
const verified = await parallel(deduped.map((f) => () => verifyOne(f)))
const survivors = verified.filter(Boolean).filter((f) => f.verify.status !== 'REFUTED')
const confirmed = survivors.filter((f) => f.verify.status === 'CONFIRMED')
log(`verified: ${confirmed.length} CONFIRMED, ${survivors.length - confirmed.length} UNCERTAIN, ${verified.length - survivors.length} refuted-out`)

phase('Synthesize')
const packet = await agent(
  PREAMBLE +
    `\n\nLENS = SYNTHESIS SEAT. Produce the REV-0023 Phase-A2 internal-review packet in MARKDOWN. You are given
the surviving (non-refuted) findings with their verify verdicts and the not-falsified list. Write:
 1. A one-paragraph verdict: does the assembled W3 remediation+WO-0030 delta draw blood internally, and is
    it ready for external Codex Phase B / the T5 merge, or are there must-fix items first?
 2. A ranked findings table (P0 first): id | severity | module | one-line mechanism | verify status |
    suggested pin (the strict-xfail the house pattern would add) | suggested remediation WO (if any).
    Mark CONFIRMED vs UNCERTAIN honestly. Do NOT invent findings; use only what is given.
 3. A "not falsified" section (coverage that held) so the review is auditable.
 4. A short "recommended next actions" list distinguishing: (a) items I (implementer seat) may pin+fix only
    with human approval because they touch human-gated surfaces, (b) items for the planning seat, (c) items
    that are genuinely clear for external Codex confirmation.
Be precise and terse. This packet goes to a human and then to an external reviewer.

SURVIVING FINDINGS (JSON):
${JSON.stringify(survivors, null, 1)}

NOT FALSIFIED (JSON):
${JSON.stringify(notFalsified, null, 1)}`,
  { label: 'synth:rev0023-phase-a2', phase: 'Synthesize', model: 'opus', effort: 'high' },
)

return {
  base: BASE,
  tip: TIP,
  lenses: LENSES.length,
  raw: allFindings.length,
  deduped: deduped.length,
  confirmed: confirmed.length,
  survivors: survivors.length,
  refuted_out: verified.length - survivors.length,
  packet,
  survivorFindings: survivors,
  notFalsified,
}
