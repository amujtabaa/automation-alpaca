# REV-0116 R2 root correction — cold serving cutover

Date: 2026-08-29

Status: **AUTHOR-DISCOVERED PREDECESSOR CONFLICT — corrected contract pending fresh review**

The first hydration RED disproved one R1 clause before a serving decoder was implemented. The
accepted WO-0168c predecessor says both that existing history-shaped behavior commitments are not
claimed reproducible from bounded checkpoint bytes and that WO-0169 must perform a bounded
behavioral-commitment cutover. R1 nevertheless required byte-identical reconstruction of existing
serving owners and their commitments. An execution snapshot, for example, retains historical
seen-fact map commitments while the checkpoint and current proof deliberately retain only bounded
current facts. Recreating that map would require forbidden history replay; defaulting it empty
while pretending its old commitment survived would be a digest-only authority bypass.

The root correction keeps the loaded checkpoint inert. Owner-private constructors rebuild only
the complete bounded current/active/unresolved semantic state from authenticated payload rows plus
fresh direct proof. Omitted audit/history state remains omitted and future targeted operations use
the already-accepted operation-keyed proof boundary. Before any adapter work, one private UOW
transaction atomically persists a normalized compact-owner successor checkpoint and cold market
invalidation. Only that committed and reread successor may become the serving context. A
post-cutover source refusal returns no context; retry reloads the committed successor.

This adds no DDL, table, public operation, alternate engine, replay store, generic decoder,
configured database, adapter, or M3 scope. The previously committed startup/lock/recovery value
and capability contracts do not attempt hydration and remain compatible with this correction.
