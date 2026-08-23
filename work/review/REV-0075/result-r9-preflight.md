# WO-0168a remaining-substrate preflight result

This is a findings-input review of the frozen remaining schema-v2 and
capability contract, not a source-candidate acceptance.

## P1 — Persisted-document, lifecycle, and checkpoint-parent contracts are not exact enough

Locations: frozen contract sections 5--6, especially lines 473, 499, 524, and
536; `records.py:111`, `:156`, and `:237`; `schema.py:238`.

Section 5 assigns kind octets to outcome, receipt, and outbox documents but
does not freeze their outer-array/member grammar or codecs. Section 6 names
six record/repository families but enumerates columns only for semantic keys;
it also leaves the technical-state transition owner and receipt/outcome linkage
open. `kernel_checkpoint` has separately unique application and version keys,
so the child parent binding must explicitly choose composite-FK support or an
equivalent constraint.

Impact: source/DDL implementation would invent canonical bytes, row
identities, terminal transitions, and checkpoint-parent integrity.

Smallest complete correction: add one compact sections-5--6 matrix that
freezes, for all six families, ordered record/SQL columns, stored-byte
semantics/digest, primary/unique/FK relationships, nullability, and the exact
durable-input state-transition owner. Specify a named composite parent index
and composite FK for `runtime_checkpoint_payload` instead of a new trigger.

## P1 — Runtime/setup capability coverage and test issuer are not mechanically defined

Locations: frozen contract section 7, especially lines 545, 550, 556, 562,
565, and 589; `repository.py:2800`.

The contract says a capability is required "where applicable" and for
"capital-relevant" writes, but it does not classify existing repository
mutators. It permits a named persistence test support module without naming it
or placing it in the exact test-path list.

Impact: implementation would decide which mutators need a runtime/setup token
and where test issuance is permitted, risking a bypass or blocking valid setup.

Smallest complete correction: add a section-7 capability matrix mapping every
repository mutator to `read-only`, `runtime`, or `setup`, and name the exact
support-module path plus its allowed importing test paths. Add that path to
section 8 only if it is not already named.

## Verdict

**ACCEPT-WITH-CHANGES** — P0=0, P1=2, P2=0.

The preflight is not clear for the remaining static source/DDL authoring until
the narrow contract amendment is independently accepted. No SQLite, database
creation, DDL installation, runtime, network, or broker code was run.
