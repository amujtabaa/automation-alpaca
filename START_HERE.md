# START HERE — Architecture reset

The current target authority is the accepted architecture-reset ADR set:

- [`docs/adr/ARCH-RESET-2026-07-RATIFICATION.md`](docs/adr/ARCH-RESET-2026-07-RATIFICATION.md)
- [`docs/adr/ADR-020-current-state-execution-kernel.md`](docs/adr/ADR-020-current-state-execution-kernel.md)
- [`docs/adr/ADR-021-position-protection-liquidity-execution.md`](docs/adr/ADR-021-position-protection-liquidity-execution.md)
- [`docs/adr/ADR-022-reset-beta-scope-cutover-governance.md`](docs/adr/ADR-022-reset-beta-scope-cutover-governance.md)
- [`work/queue/ARCH-RESET-2026-07/README.md`](work/queue/ARCH-RESET-2026-07/README.md)

The current Spine v2 implementation and the W3/R6 campaign material are frozen evidence. Nothing
in this index activates `RESET-WO-01`, implementation, schema/database work, broker access, or
trading activity.

## Frozen historical W3 instructions

The text below is retained only as provenance and is not current authorization.

**Human:** place this folder's contents at the repo root of `automation-alpaca` (checked out on
the current dev tip), open a fresh Claude Code session (Fable 5, effort per your plan: high
baseline, xhigh for WO-0019 and WO-0022 Phase A), and paste the full contents of
`work/queue/W3-KICKOFF-PROMPT.md` as the first message. That prompt is the session's standing
authorization and contains everything else.

**Claude Code session reading this file without the kickoff pasted:** do not start work from this
file. Read `work/queue/W3-KICKOFF-PROMPT.md` in full, confirm with the human that it constitutes
your authorization for this session, then follow it exactly (its human-checkpoint list is
binding).

Contents of this drop:
- `docs/adr/ADR-010-execution-envelope.md` — the wave's authoritative design (Proposed)
- `work/queue/W3-README.md` — sequencing + branch/worktree strategy
- `work/queue/W3-KICKOFF-PROMPT.md` — the session bootstrap + operating agreement
- `work/queue/WO-0016..0022` — the work orders (0018 = the LASE algorithm itself)
- `work/review/W3-codex-review-prompt.md` — Phase B independent review prompt (pin SHA before use)
- `pkl/architecture/sellside-research-notes.md` — distilled exit/entry mechanism research
- `work/queue/W4-SEED-NOTES.md` — buy-side + replay-harness seeds (NOT authorized in W3)
