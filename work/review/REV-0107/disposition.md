---
type: Review Disposition
rev_id: REV-0107
work_order_id: WO-0168d
status: RESOLVED
verdict_received: BLOCK
date: 2026-08-27
recorded_by: Codex implementation seat
---

# REV-0107 round-one disposition

## Result accepted unchanged

The reviewer-owned `result.md` is preserved unchanged at SHA-256
`680f11e0a5460eabb37163120c3b70737172d8ecd79561a8d789d3dee7b58c12`. Its verdict is
BLOCK with P0=0/P1=1/P2=0 against implementation candidate
`5cf52a846dcd34aaf6cae2d0f1338014ceabd536`, tree
`68e2fb928f04732bdb03eaf996df8a3bdab2d177`.

The P1 is valid. A normal assignment such as `Connection = sqlite3.Connection` followed by a
name call could add a second opener while the structural controls remained green. A production
`from sqlite3.dbapi2 import Connection` import also escaped the exact-module check. No such bypass
exists in the checked-in candidate, but the named failure-capable control did not meet its contract.

## Root remediation

The remediation does not add dataflow, provenance, or arbitrary-Python analysis. The finite AST
rule now rejects every executable, non-annotation attribute named `Connection`; therefore an
ordinary local alias is rejected at the assignment that obtains the constructor, before call
tracking is relevant. Deferred function/variable annotations remain permitted. SQLite module and
submodule imports share one exact prefix rule, and dangerous `connect`/`Connection` imports from
`sqlite3` or `sqlite3.*` are rejected. The helper exactness check applies the same executable-
reference rule to prevent any second opener in its own module.

Canaries cover a direct constructor, a local constructor alias plus name call, a
`sqlite3.dbapi2` direct import, and a second helper-module alias opener. The focused no-I/O boundary
suite passes 15 tests. Boundary plus gate is exactly 400 nonblank/noncomment lines. The application
installer correction remains unchanged and the human authorization flag remains False.

The exact remediation identity and full static/no-I/O evidence belong in `request-r2.md` after the
candidate is committed. Round two must independently reproduce the round-one mutant and return
zero open P0/P1. No held suite, database, DDL, migration, unlock, or later work is authorized.

## Round-two result and successor route

The reviewer-owned `result-r2.md` is preserved unchanged at SHA-256
`714a88cb269a0cba10c72458c9b233f6e8e73b952253bf45564b4634785e782d`. It returned BLOCK with
P0=0/P1=1/P2=0. It confirmed all round-one alias/submodule forms were rejected and found one valid
remaining spelling: `from sqlite3 import *` or `from sqlite3.dbapi2 import *` supplies the public
constructor while the import check examined only explicitly named imports.

REV-0107 has exhausted two rounds and remains a blocking historical packet. The finite root fix is
to classify wildcard imports as dangerous for the already-bounded `sqlite3`/`sqlite3.*` family in
both structural checks, with real-source canaries. No name dataflow, reflection, or general Python
model is added. The exact successor routes to fresh packet REV-0108; the DDL gate remains closed.
