# CLOSE-OUT CHECKLIST — R6a gate (WO-0104a + WO-0140 + REV-0045)

- **Status:** QUEUED — pre-staged 2026-07-28 while Codex round-3 is in flight, on operator
  direction. **Executes only on an ACCEPT-class REV-0045 verdict.** Nothing here self-executes.
- **Why pre-staged:** the close-out has eleven moving parts across two work orders, one review
  packet, two state files, and the ledger. "Done but not dispositioned" is this repository's most
  repeated bookkeeping failure (AUDIT-0002 F001/F008/F009; WO-0116's whole sweep). A multi-part
  obligation held in an agent's memory is exactly what the ratified de-dicing principle says must
  be an artifact instead.
- **Integration map:** `work/review/AUDIT-0003-addendum-01.md` §W-3 (branch topology, silent-drop
  hazards). Read it before executing.

---

## 0. Preconditions (verify, do not assume)

```bash
git fetch origin codex/signal-r6a-rails-store master
git checkout codex/signal-r6a-rails-store && git pull
git status --short                      # must be empty
git rev-list --left-right --count origin/master...HEAD   # expect "0  <n>" — fast-forward
grep -m1 "^verdict:" work/review/REV-0045/result-addendum-03.md
```

- [ ] Working tree clean.
- [ ] Behind-count is **0** (a nonzero behind-count means re-merge master first; still expected
      conflict-free — zero file overlap was verified at `4fdf51b`).
- [ ] REV-0045 round-3 verdict is `ACCEPT` or `ACCEPT-WITH-CHANGES`.
- [ ] The round-3 result states a **pinned head SHA**, and that SHA covers the post-remediation
      gated-surface commits (ADR-014, ADR-015, CI gates, spec amendments). If it pins an older
      head, those merge on self-review only — **STOP and request an addendum covering them.**

**If the verdict is BLOCK:** do not execute this checklist and do not open a fourth remediation
round. Per the P-1 tripwire (`.ai-os/core/15`) and the operator pre-commitment of 2026-07-28, a
further BLOCK on the rail surface routes to the **WO-A/B/C kernel-consolidation program**
(AUDIT-0003 addendum-01 §5), not another patch cycle.

---

## 1. The atomic close-out commit

Everything in this section lands in **one commit**, per the repo close-out rule. CI fails a
completed work order parked in a live folder, so a partial close-out is a red build, not a
deferred chore.

### 1a. Reviewer-owned artifacts — do not edit

- [ ] Confirm no `work/review/REV-0044/**` or `REV-0045/result*.md` file is modified in this
      commit (`git diff --cached --name-only | grep result`). The implementer writes
      `disposition.md` only.

### 1b. REV-0045 disposition

- [ ] Create `work/review/REV-0045/disposition.md` — verdict received, per-finding resolution
      (P0-1..P0-5, P1-1..P1-3), the reviewed head SHA, and the evidence range
      `b48235e..<head>`. Cite the two external process audits as in-loop, non-gating.

### 1c. WO-0140 close-out

- [ ] `status: REVIEW` → `CLOSED` in `work/queue/WO-0140-r6a-truth-model-remediation.md`.
- [ ] Add the Completion-disposition block: `RESULT_SUMMARY_KEPT`, `PKL_UPDATED`,
      `ADR_CREATED` (ADR-014/ADR-015 both landed under this work).
- [ ] `git mv work/queue/WO-0140-*.md work/completed/`
- [ ] **Vocabulary note in the disposition:** WO-0140's ratified text names the pre-ADR-014
      identifiers (`poisoned_producers`, `PoisonedProducerMarker`). It is historical text and stays
      verbatim; cite ADR-014's mapping table so a future reader grepping its closed test-edit list
      does not conclude the ratified pins were dropped.

### 1d. WO-0104a close-out — **the orphan risk**

WO-0140's own close-out text is silent on its parent. WO-0104a is the work REV-0044 gated, and
its R-1/R-2 items are what this whole chain resolved. It is the item most likely to be left
"done but not dispositioned."

- [ ] `status: REVIEW` → `CLOSED` in `work/queue/WO-0104a-signal-rails-store-surface.md`.
- [ ] Completion disposition: `RESULT_SUMMARY_KEPT`, `PKL_UPDATED`.
- [ ] `git mv work/queue/WO-0104a-*.md work/completed/`
- [ ] Disposition text must cite **both** `REV-0044/result.md` **and**
      `REV-0044/result-addendum-01.md`.
- [ ] **Discharge or carry the addendum-01 caveat explicitly.** Addendum-01 records that R-1 was
      "not live against the operator's database" — downgraded from active data risk to *latent
      trap*, severity unchanged, still gating. State in the disposition whether the latent trap is
      now closed by the remediation, or carries forward as a named item. Do not let it pass silently.

### 1e. Ledger — **two** rows, real SHAs

```bash
git log --oneline --format='%h %s' b48235e..HEAD -- app/ | tail -20   # find implementation SHAs
```

- [ ] Append a row for **WO-0104a** and a row for **WO-0140**.
- [ ] `commit` field carries a **real hex SHA of the implementation commit** — for WO-0140 that is
      `807d38b` (the four-P0 remediation). **`"HEAD"` is now rejected** by `check_ledger.py` for
      rows dated after 2026-07-28 (P-6). Cite the work's commit, not the close-out commit — that
      avoids the chicken-and-egg and is what makes the row verifiable later.
- [ ] `status: CLOSED`; `disposition` from the valid vocabulary only; `date` ISO; `reason` states
      the verdict, the gating items resolved, and what carries forward.

### 1f. State files

- [ ] `git mv work/active/SIGNAL-R6aR-STATE.md work/completed/keep/`
- [ ] `git mv work/active/SIGNAL-R6a-STATE.md work/completed/keep/`
      (precedent: `SIGNAL-R5a-STATE.md`, `SIGNAL-R5b1-STATE.md`, `SIGNAL-R5b2-STATE.md`)
- [ ] Final evidence-log entry in the R6aR state file **before** moving it: the verdict, the
      reviewed head, and what carries to R6b.

### 1g. Knowledge refresh

- [ ] `pkl/architecture/signal-seat.md`: changelog entry + `last_verified` refresh.
- [ ] Any doc/ADR claim the verdict invalidates (close-out rule: the finishing commit refreshes
      what it falsifies).
- [ ] If round-3 raised non-blocking findings accepted as carry-forward, file them where R6b will
      see them — not only in the disposition.

### 1h. Verify before committing

```bash
source .venv/bin/activate
python .ai-os/scripts/check_ledger.py
python .ai-os/scripts/check_pkl.py pkl/
python .ai-os/scripts/check_work_order_disposition.py     # must not print WARNING
ruff check . && mypy app/ && lint-imports
python -m pytest -q tests/r2_conformance_oracle.py
python -m pytest --cov=app --cov-branch --basetemp <unique-os-temp>
```

- [ ] Hygiene ×3 pass; no WARNING from the disposition checker.
- [ ] Battery: read the **counts line and the coverage line**, never the exit code.
- [ ] `ruff format --check .` shows exactly the ten known base-debt files — an eleventh is a finding.

---

## 2. Merge to master

- [ ] `git checkout master && git pull && git merge --ff-only codex/signal-r6a-rails-store`
- [ ] Push; confirm CI green on master (the merge is a fast-forward, so CI on the branch head is
      the same tree — but confirm the run, do not infer it).

---

## 3. Post-merge

- [ ] Confirm `work/queue/` no longer holds WO-0104a or WO-0140.
- [ ] Confirm `work/active/` holds no retired R6a state file.
- [ ] Unblock check: R6b (WO-0104b) becomes eligible; **D-2a stays OFF** until R6 + R7 and the
      joint gate — the verdict does not change that.
- [ ] Record in the ledger reason (or the R6b kickoff) anything round-3 carried forward.

---

## Silent-drop watchlist (from AUDIT-0003 addendum-01 §W-3)

1. **REV-0044 addendum-01's operator-database caveat** — §1d.
2. **WO-0104a itself** — the parent, unmentioned by WO-0140's close-out text — §1d.
3. **Two ledger rows, not one** — §1e.
4. **Round-3's reviewed head vs the four post-remediation gated-surface commits** — §0.
5. **The vocabulary grep-miss** when verifying WO-0140's ratified pins — §1c.
