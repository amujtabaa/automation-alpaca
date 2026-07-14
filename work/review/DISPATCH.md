# Cross-model review — staged-packet convention

The independent review lane (CLAUDE.md "Review"). Deliberately simple: **packets live in the repo,
Codex reads the request from GitHub, Codex pushes its result back.** No local CLI, no plugin, no
model/effort control from this side — you drive Codex and pick its model.

## The loop

1. **Claude stages the packet.** A review request lands at `work/review/REV-NNNN/request.md`
   (role, what changed, the numbered questions, verdict vocabulary, where-to-look), committed and
   **pushed** to the branch/PR under review.
2. **You point Codex at it — on the GitHub website.** Open `request.md` in the PR / on the branch
   and hand Codex that URL (or its raw view). Because it's already pushed, you don't fetch or pull
   in GitHub Desktop first — Codex reads the current pushed state directly.
3. **Codex reviews and pushes its result.** Codex writes `work/review/REV-NNNN/result.md` (findings
   + an explicit verdict token: ACCEPT | ACCEPT-WITH-CHANGES | BLOCK) and **pushes it to the repo**
   when done. Keeping this auto-push is the whole point — no file hand-carrying.
4. **Claude picks it up.** A background check-in (or the PR webhook) detects the pushed `result.md`,
   verifies it against the packet, scaffolds `disposition.md`, and reports the verdict to you.
5. **You disposition.** You read `result.md`, decide, and write/confirm `disposition.md`. Claude
   handles the gate effects + ledger entry from there. **Verdicts inform; only the human
   dispositions** (hard rule — see the REV-0022 rescind history for why).

## Conventions

- **Freezing:** while a branch is still under active fix, the packet's `commit_range` reads
  `SET-ON-DISPATCH` — Codex reviews whatever is pushed when you point it at the request; the result
  is understood to cover that state. Don't re-freeze the packet on every commit.
- **Model note (optional, useful):** if you can, have Codex record the model/version it used in
  `result.md`'s frontmatter — handy given the container/model-availability differences (e.g. Sol
  5.5 vs 5.6). Not a gate; just good provenance.
- **Applying fixes:** when Claude applies the returned findings and they touch defensive-security
  surfaces (auth/credentials/transport/rate-limit/quarantine), route that to the current Opus model
  per the repo-primer operator preference — Fable-family models false-positive their dual-use
  safeguard on that content.
