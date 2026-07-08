# Architecture Decision Record (ADR) Template

**Purpose:** Document key technical and architectural decisions with context, options considered, and rationale for future reference.

---

## ADR Prompt (Copy to Claude Desktop)

```
Help me document an Architecture Decision Record for [decision topic]. Include:

1. Context and problem statement
2. Decision drivers (requirements, constraints)
3. Options considered (with pros/cons)
4. Decision outcome and rationale
5. Consequences (positive, negative, risks)
6. Implementation notes

Follow the standard ADR format. Be specific about trade-offs and why we chose this approach over alternatives.
```

---

## ADR Template

```markdown
# ADR-[Number]: [Title of Decision]

**Status:** [Proposed | Accepted | Deprecated | Superseded]
**Date:** [Date]
**Deciders:** [Names]
**Technical Area:** [Backend | Frontend | Infrastructure | Database | Integration | Security]

---

## Context

### Problem Statement
[What problem are we trying to solve? Why is this decision needed now?]

### Background
[Relevant context, constraints, and prior decisions that inform this choice]

### Decision Drivers
- [Driver 1]: [Explanation]
- [Driver 2]: [Explanation]
- [Driver 3]: [Explanation]

### Requirements
**Must have:**
- [Requirement 1]
- [Requirement 2]

**Should have:**
- [Requirement 1]
- [Requirement 2]

**Nice to have:**
- [Requirement 1]

---

## Options Considered

### Option 1: [Name]

**Description:**
[Brief explanation of this approach]

**Pros:**
- [Pro 1]
- [Pro 2]
- [Pro 3]

**Cons:**
- [Con 1]
- [Con 2]

**Cost/Effort:** [Low | Medium | High]
**Risk:** [Low | Medium | High]

### Option 2: [Name]

**Description:**
[Brief explanation of this approach]

**Pros:**
- [Pro 1]
- [Pro 2]

**Cons:**
- [Con 1]
- [Con 2]
- [Con 3]

**Cost/Effort:** [Low | Medium | High]
**Risk:** [Low | Medium | High]

### Option 3: [Name]

**Description:**
[Brief explanation of this approach]

**Pros:**
- [Pro 1]
- [Pro 2]

**Cons:**
- [Con 1]
- [Con 2]

**Cost/Effort:** [Low | Medium | High]
**Risk:** [Low | Medium | High]

---

## Decision

### Chosen Option
**[Option Name]**

### Rationale
[Explain why this option was selected over others. Reference decision drivers and how this option best satisfies them.]

Key factors:
1. [Factor 1]: [Why this option is best for this factor]
2. [Factor 2]: [Why this option is best for this factor]
3. [Factor 3]: [Why this option is best for this factor]

### Trade-offs Accepted
- [Trade-off 1]: [Why it's acceptable]
- [Trade-off 2]: [Why it's acceptable]

---

## Consequences

### Positive
- [Positive outcome 1]
- [Positive outcome 2]
- [Positive outcome 3]

### Negative
- [Negative outcome 1]
- [Negative outcome 2]

### Risks
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| [Risk 1] | [L/M/H] | [L/M/H] | [Strategy] |
| [Risk 2] | [L/M/H] | [L/M/H] | [Strategy] |

### Future Implications
- [What this means for future decisions]
- [What becomes easier/harder]

---

## Implementation

### Approach
[How we will implement this decision]

### Dependencies
- [Dependency 1]
- [Dependency 2]

### Timeline
- [Phase 1]: [Timeframe]
- [Phase 2]: [Timeframe]

### Success Criteria
- [Criterion 1]
- [Criterion 2]

### Rollback Plan
[How to reverse this decision if it doesn't work out]

---

## Related Decisions
- ADR-[X]: [Related decision]
- ADR-[Y]: [Related decision]

---

## Review & Updates

### Review Schedule
[When to review if this decision is still valid]

### Superseded By
[If deprecated, link to new ADR]

---

**Author:** [Name]
**Reviewers:** [Names]
**Last Updated:** [Date]
```

---

## Common ADR Topics

### Infrastructure
- Hosting provider choice
- Serverless vs VPS
- Database selection
- Caching strategy
- CDN selection

### Backend
- Framework/language choice
- API architecture (REST vs GraphQL)
- Background job system
- Authentication approach
- Error handling strategy

### Frontend
- Framework choice
- State management
- Styling approach
- Build tooling
- Testing strategy

### Integrations
- Payment processor
- Email service
- Analytics platform
- Third-party APIs
- Monitoring tools

### Security
- Authentication method
- Authorization model
- Data encryption
- API security
- Compliance approach

---

## ADR Index Template

Track all decisions in a central index:

```markdown
# Architecture Decision Records Index

| ADR | Title | Status | Date | Area |
|-----|-------|--------|------|------|
| 001 | [Database Selection] | Accepted | [Date] | Database |
| 002 | [Auth Provider] | Accepted | [Date] | Security |
| 003 | [Hosting Platform] | Accepted | [Date] | Infrastructure |
| 004 | [Payment Processor] | Accepted | [Date] | Integration |
| 005 | [Background Jobs] | Accepted | [Date] | Backend |
```

---

## Quick Decision Template

For simpler decisions that don't need full ADR:

```markdown
## Decision: [Title]

**Date:** [Date]
**Decided:** [Option chosen]

**Why:**
[2-3 sentence rationale]

**Alternatives considered:**
- [Option 2]: [Why not]
- [Option 3]: [Why not]

**Revisit if:**
[Conditions that would trigger reconsideration]
```

---
