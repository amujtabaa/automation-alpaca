# Delivery process

## Development model

Use Codex and Claude as interchangeable implementation/planning resources, but never let the same
context be builder and gate-clearing reviewer for a safety milestone.

| Seat | Receives | Produces | Cannot do |
|---|---|---|---|
| Planning | Accepted ADRs, current milestone, exact code anchors | One bounded work order and assumption ledger | Implement it in the same context |
| Implementation | One work order and named context files | Tests, minimal code, evidence, result | Expand scope or change accepted semantics |
| Independent review | Spec/invariants, clean diff, tests; no builder rationale | Findings with reproduction/proof | Fix code or inherit builder conclusions |
| Disposition | Findings and accepted spec | Accept/fix/dispute record | Quietly edit reviewer-owned result |

Codex may be the builder and Claude the reviewer, or the reverse. Model brand matters less than
fresh framing and distinct ownership.

## Clarification policy

The implementation seat continues without a human question when all are true:

- the choice is reversible;
- it does not widen broker, money, credential, schema, live-mode, or deletion authority;
- the accepted ADR/domain spec gives a conservative answer;
- the smallest solution satisfies the work order;
- the decision is recorded in the result.

Resolution order:

1. Accepted ADR/invariant.
2. Work-order requirement.
3. Domain specification.
4. Existing executable behavior explicitly marked for preservation.
5. Simplest fail-safe choice inside allowed paths.

Stop and batch a question only when:

- two accepted authorities conflict;
- the change would widen financial authority or use real credentials/money;
- an exact broker fact cannot be established from a sandbox or primary source;
- the authorized schema/field vocabulary cannot express the required state;
- the only fix crosses forbidden paths or deletes protected evidence.

Questions are accumulated into one milestone decision packet. Do not stop for naming, formatting,
test organization, or a reversible internal representation choice.

## Work-order shape

Every work order contains:

- one sentence goal;
- exact context files;
- allowed and forbidden paths;
- one semantic center;
- state/invariant deltas;
- required examples and generated properties;
- mutation or fault-injection proof;
- exact commands;
- explicit non-goals;
- stop conditions;
- expected disposition.

The builder does not read the whole historical campaign. It reads the accepted reset ADRs, the
specific work order, relevant source, and relevant tests.

## Stop-loss rules

The current campaign repeatedly improved a complex design after each new P0. The reset uses these
limits:

1. **Design stop-loss:** one fresh-context pre-build refutation, one revision, then a focused
   recheck of changed claims. If a P0 remains in the same mechanism, choose a simpler mechanism or
   split the work; do not begin a third broad rewrite of the same work order.
2. **Build stop-loss:** if post-build review finds either two P0s, or three P1s with a common
   ownership root, freeze implementation and return to the reference model/ADR.
3. **Patch stop-loss:** a second defect in the same lifecycle edge cannot be fixed with another
   path-local guard. Move the transition into the kernel or redesign the artifact.
4. **Size stop-loss:** if a work order needs more than one new durable concept or crosses fast
   path, persistence, broker, and UI together, split it before coding.
5. **Review stop-loss:** review comments must supply a reproduction or a code-anchored
   unreachability obligation. Narrative unease is converted into a test question or closed.
6. **Optional-feature stop-loss:** any optional subsystem that complicates startup/protection is
   disabled and deferred, not made tolerant through more state.

These rules reduce correlated rework; they do not waive independent review.

## Testing pyramid

1. Pure example tests for named transitions.
2. Hypothesis rule-based model tests for lifecycle classes.
3. Mutation proof for each capital-safety invariant.
4. SQLite transaction/crash tests.
5. Deterministic broker simulator fault histories.
6. Adapter conformance against Alpaca Paper.
7. Performance/queue-age benchmarks.
8. Attended and unattended paper soak.

Test count and branch coverage are secondary indicators. The primary evidence is invariant
closure across generated histories and real broker boundary behavior.

## Review protocol

Before reading code, an independent reviewer pre-registers:

- state owners;
- allowed lifecycle edges;
- fill/quantity invariant;
- order-attempt ownership;
- ambiguity behavior;
- crash boundaries;
- startup/process-ownership fencing;
- broker gap-recovery coverage and outbound rate ownership;
- optional-subsystem isolation;
- performance complexity class.

The reviewer then attempts executable counterexamples and mutations. Milestone review is
consolidated; tiny implementation work orders use local review until they compose into a
human-gated behavior.

## Concurrency

Parallelize only independent work:

- domain documentation and adapter research;
- pure kernel property tests and simulator fixtures after interfaces freeze;
- cockpit read projection after the query contract freezes.

Never parallelize two writers against:

- reducer semantics;
- schema;
- broker effect lifecycle;
- protection state machine;
- startup/process ownership or broker request budgets;
- the same accepted ADR.

One branch owns each semantic center.

## Freelancer decision

Do not hire a broad Upwork developer now. AI-led implementation is realistic because the reset
removes the largest ambiguity and uses small deterministic modules.

Consider a human only for a fixed deliverable such as:

- a 5–10 hour review of an Alpaca/Webull adapter and its rate/reconnect behavior;
- a production operations/security review;
- a targeted Python/SQLite performance profile;
- a broker-specific issue that survives a minimal reproduction.

Use a capped milestone, repository access limited to the relevant branch, no live credentials,
and acceptance tests written before engagement. Do not outsource architecture ownership.

## Documentation discipline

- Accepted durable decisions live in ADRs/PKL, not raw work orders.
- Work results retain only evidence and durable failures.
- Shrunk traces are code fixtures.
- Old campaign documents remain archived evidence, not default context.
- No claim is “verified” without a pasted command result, primary source, or executable anchor.
