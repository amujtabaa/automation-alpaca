# Running a review packet locally — dispatch runbook

Three paths, all ending in the same place: `work/review/REV-NNNN/result.md` with a **model/effort
attestation** in its frontmatter (protocol rule 2026-07-14: no attestation, no gate clearance),
committed and pushed so any session's check-in picks it up.

## Path A — one-liner via your local Claude Code (recommended)

Prereqs (once): pull the branch/master containing `.claude/settings.json`'s plugin config, open
Claude Code in the repo (the `codex@openai-codex` plugin auto-installs — accept the trust prompt),
and have the Codex CLI signed in with your ChatGPT account (`npm i -g @openai/codex && codex login`
— **plan billing, not API credits**).

Then, in any session:

> dispatch REV-0024 at high effort

The `dispatch-review` skill (`.claude/skills/dispatch-review/`) tells Claude exactly what that
means: freeze the SHA, run Codex against the packet with the requested effort, enforce the
attestation, write `result.md`, commit, push, and scaffold the disposition for you. Saying
**"ultra"** additionally layers a Claude-side adversarial critic panel over Codex's findings.

## Path B — direct script (no Claude in the loop)

```bash
scripts/dispatch_review.sh REV-0024            # default: high effort, CLI-default model
scripts/dispatch_review.sh REV-0024 xhigh      # explicit effort (falls back to high if unsupported)
scripts/dispatch_review.sh REV-0024 high gpt-5.2-codex   # explicit model too
```

The script runs `codex exec` read-only with the packet as the prompt, tees the raw output to
`work/review/REV-NNNN/result-raw.md`, and prints the finishing steps (finalize as `result.md`
with the attestation frontmatter, commit, push). If a `codex` flag has drifted in a newer CLI,
`codex --help` is authoritative — the script's flags are current as of codex-plugin-cc's release.

## Path C — manual Codex app (what you've been doing), minus the file hunt

1. Open the repo in Codex; paste the contents of `work/review/REV-NNNN/DISPATCH-PROMPT.md`
   (pre-generated per packet; it points Codex at `request.md` and demands the verdict token +
   attestation). Pick the model/effort in the app — the attestation records your choice.
2. Have Codex (or you) save its output as `work/review/REV-NNNN/result.md`.
3. **Commit and push it immediately** — that's the whole fix for the file hunt: a push is how
   every other session finds out. Any branch works; `codex/rev-NNNN` by convention.

## After any path

- You read `result.md`, write `disposition.md` (verdict received + your decision), and the
  dispatching/next session handles gate effects + the ledger entry per the close-out rule.
- A result **without** the model/effort/environment attestation is advisory only.
