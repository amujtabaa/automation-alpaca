# Codex kickoff — WO-0168d hybrid gate simplification (2026-08-26)

You are the implementation seat for `WO-0168d`. The treadmill is over: Ameen ratified deleting
the static scanner and replacing it with the minimal hybrid. Do not extend, repair, or re-derive
any provenance/topology/trace model — that entire approach is superseded by ratified decision.

## Read order (complete; nothing else is required context)

1. `AGENTS.md`; `CLAUDE.md` safety core.
2. `work/active/WO-0168d-m2-i3-5-hybrid-gate-simplification.md` — the authoritative scope,
   authority, budgets, review contract, and done-when. Treat it as binding.
3. `work/review/CONSULT-0001-wo0168c-architecture/memo-comparison.md` — why each piece exists.
4. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md` Amendment 7 — gate truth.
5. `.ai-os/core/20_ASSURANCE_PROPORTIONALITY.md` and doc 15's review protocol — the scoped
   project-policy correction that REV-0106 reviews independently.
6. `tests/execution_core/approved_schema_digest.py` — the file you will rename constants in.

Do NOT load: the WO-0168c amendment chain (evidence only), REV-0079…REV-0105 packet bodies, or
the deleted scanner internals beyond the kernel you are retaining. They are context bombs.

## Execution notes

- Repository checkout `G:\dev-hdd\automation-alpaca`, branch `codex/m2-wo0168d-hybrid-r1`, based
  exactly on planning head `81c65a09fbdd3d67a4a46ccd1d22f3c9b395353a`, tree
  `7dfed0cb0dd68add1ca36704766ccfd7a65bff61`. The abandoned scanner WIP remains untouched in the
  old `automation-alpaca-worktrees/codex-m2-wo0168c` checkout. Do not reset, clean, or edit that
  old worktree.
- Order of work: Scope 2 (relocation) → 1 (scanner reduction) → 4 (gate lifecycle) → 3
  (boundary layer, red-first with the canaries) → 5 (CODEOWNERS) → 6 (ADR-023) → 7 (verify).
- Fable discipline applies: red-first for every new control, pasted fresh evidence, FIX blocks
  with root cause. The interim prohibition re-scope in WO-0168d §"Ratified prohibition re-scope"
  is your execution guard now — repo-wide pytest excluding `tests_gated/` is authorized.
- Respect the budgets: ≤400 new SLOC, <60 s boundary runtime, ≥500-SLOC meta-code proposals
  escalate to Ameen instead of being built. If you feel the pull to model Python semantics,
  stop — that is the superseded approach.
- Open `work/review/REV-0106/request.md` when frozen. Its implementation lens uses ADR-023's
  bounded threat model; its governance lens judges Core 20 under `AGENTS.md` and doc 15 without
  letting Core 20 constrain findings about itself. Close-out ships only after zero open P0/P1.

## Hard limits (unchanged)

No `tests_gated/` execution, changed-DDL install/execution, database or `:memory:` creation in
this lane, migration, runtime composition, credentials, network, broker calls, orders, promotion,
or merge to master. Gate-day unlock is Ameen's separate act after his DDL intent review.
