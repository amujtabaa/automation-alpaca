# WO-0151 exact-head GitHub Actions run #741 outcome

## Exact external evidence

- Branch: `codex/arch-reset-2026-07-r1`.
- Exact candidate SHA: `a2b84abc1914517cf591f27fb88f0b20b2a47ef7`.
- GitHub Actions push run: #741, ID `31185454392`.
- Python 3.11 job: ID `92888729393`.
- Python 3.12 job: ID `92888729623`.

Each job completed its functional/static work on that exact SHA: setup, Ruff,
Mypy, import boundaries, contamination checks, AI Project OS checks, the R2
conformance gate, and the full repository test suite. Each reported **5,934
passed, 11 skipped, 1 xfailed**. Neither job is an overall CI success: the
unchanged combined line/branch coverage ratchet failed at **91.34%** against a
required **93%**.

## Admissibility and current use

Run #741 is positive exact-head evidence for the listed functional and static
gates and negative evidence for the coverage gate. It is not used to claim
WO-0151 effective `CLOSED`, M1 complete, or unconditional WO-0152 activation.
It supersedes only the prior statement that E2's external result was still
pending. The paired E2/E3 exact-head Python 3.11/3.12 closeout must pass the
same unchanged 93% gate before either work order becomes effectively closed.

No prohibited local R2 fixture, database, SQL/DDL, broker, credential,
runtime, or network result is relied upon by this record.

