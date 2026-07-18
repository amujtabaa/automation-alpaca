# Master Transformation Analysis Prompt

**Purpose:** Complete prompt for analyzing a starter kit and producing an implementation-ready transformation report. Run in Claude Code.

---

## Master Prompt (Copy to Claude Code)

```
You are Claude Code performing a comprehensive transformation analysis. Your task is to analyze [STARTER KIT NAME] and produce a complete implementation plan for transforming it into [PRODUCT NAME].

---

## CONTEXT DOCUMENTS

You have been provided with:
1. Master Strategy Document (product requirements, pricing, technical needs)
2. Competitive Intelligence (market positioning, differentiation)
3. Selected Starter Kit repository (the codebase to transform)

---

## YOUR MISSION

Analyze the starter kit repository comprehensively and produce a transformation report covering 7 domains:

1. **Authentication & Multi-tenancy** - User management, workspaces, RLS
2. **Payment Processing** - Polar integration (migrate from Stripe if needed)
3. **Database Architecture** - Schema design, migrations, types
4. **Background Jobs** - Scheduled tasks, queues, monitoring
5. **UI Components** - Dashboard, forms, data display
6. **Integrations** - Third-party APIs, external services
7. **Gap Synthesis** - Custom features specific to this product

---

## ANALYSIS PROCESS

### Phase 1: Documentation Review (30 minutes)

1. Read ALL markdown files in the repository's `/docs` folder (or equivalent)
2. Map existing feature set
3. Document conventions:
   - Project structure and file organization
   - Naming conventions
   - Database query patterns
   - Server/Client component split
   - API route structure

**Output:** Summary of what the starter kit provides out-of-the-box

---

### Phase 2: Domain Analysis (60 minutes)

For each of the 7 domains, analyze:

1. **What exists:** Current implementation in the starter kit
2. **What we need:** Requirements from the Strategy Document
3. **Gap:** Delta between existing and needed
4. **Implementation:** Specific files to create/modify
5. **Effort:** Hours estimate

---

### Phase 3: Integration Planning (20 minutes)

Identify exactly WHERE in the codebase to add new features:
- File paths for new code
- Existing files to modify
- Integration points between systems
- Data flow architecture

---

### Phase 4: Implementation Checklist (20 minutes)

Break down all work into atomic tasks:
- Priority (P0 = MVP critical, P1 = Launch, P2 = Post-launch)
- Estimated hours
- Dependencies
- Risk level

---

## TRANSFORMATION REPORT STRUCTURE

Your final output should follow this structure:

```markdown
# [Starter Kit] → [Product]: Transformation Report

## Executive Summary
- Feasibility assessment
- Timeline overview (weeks)
- Total effort (hours)
- Key challenges
- Confidence level

## Part 1: Starter Kit Analysis
### 1.1 What the Kit Provides
### 1.2 Key Implementation Patterns
### 1.3 Code Organization

## Part 2: Domain Analyses
### Domain 1: Authentication & Multi-tenancy
### Domain 2: Payment Processing (Polar)
### Domain 3: Database Architecture
### Domain 4: Background Jobs
### Domain 5: UI Components
### Domain 6: Integrations
### Domain 7: Gap Synthesis (Product-Specific)

## Part 3: Gap Analysis Summary
- Feature comparison table
- Total new development needed
- Biggest gaps (highest effort)

## Part 4: Implementation Plan
### 4.1 File Structure (new files to create)
### 4.2 Implementation Checklist
### 4.3 Dependency Graph
### 4.4 Critical Path

## Part 5: Development Roadmap
### Week 1: [Focus area]
### Week 2: [Focus area]
### Week 3: [Focus area]

## Part 6: Risk Assessment
### Technical Risks
### Timeline Risks
### Dependency Risks

## Part 7: Recommendations
### Immediate Actions
### Technical Debt to Avoid
### Future Enhancements

## Conclusion
- Go/no-go recommendation
- Success criteria
- Next steps
```

---

## DOMAIN ANALYSIS GUIDELINES

For each domain, provide:

### What Exists
```typescript
// Show actual code patterns from the starter kit
// Reference specific file paths
```

### What We Need
- [ ] Requirement 1
- [ ] Requirement 2
- [ ] Requirement 3

### Gap Analysis

| Feature | Starter Kit Has | We Need | Action |
|---------|-----------------|---------|--------|
| [Feature] | ✅/❌/🔶 | [Requirement] | [Build/Modify/Use] |

### Implementation Details

**Files to create:**
- `/path/to/file.ts` - [Description]

**Files to modify:**
- `/path/to/existing.ts` - [What to change]

**Code examples:**
```typescript
// Provide actual TypeScript code following starter kit patterns
```

### Effort Estimate
- [Task 1]: [X] hours
- [Task 2]: [X] hours
- **Domain Total:** [X] hours

---

## QUALITY STANDARDS

### Be Specific
- Use actual file paths from the starter kit
- Show real code patterns, not pseudocode
- Include proper TypeScript types

### Be Thorough
- Consider edge cases
- Plan for scaling
- Include error handling

### Be Realistic
- Add 20% buffer to estimates
- Note dependencies and blockers
- Flag areas needing research

### Follow Best Practices
- Payment processing: Polar (not Stripe)
- Hosting: VPS-ready (node-cron for jobs, not Edge Functions)
- Security: RLS policies, input validation, auth checks

---

## SUCCESS CRITERIA

Your analysis is successful if:

✅ A developer can read the report and know exactly what to build
✅ Every integration point is identified with file paths
✅ Polar migration has complete implementation spec (if applicable)
✅ Timeline is realistic with appropriate buffers
✅ Code examples follow starter kit conventions
✅ Risks are identified with mitigation strategies
✅ No major architectural questions remain

---

## BEGIN ANALYSIS

Start with Phase 1: Documentation Review. After completing all phases, compile the comprehensive Transformation Report.
```

---

## Using Domain Deep-Dive Files

For complex domains, load the specific deep-dive file to get detailed prompts:

- `domain-1-auth-multitenancy.md` - Authentication patterns
- `domain-2-payments.md` - Polar integration specifics
- `domain-3-database.md` - Schema design patterns
- `domain-4-background-jobs.md` - Job scheduling patterns
- `domain-5-ui-components.md` - Dashboard components
- `domain-6-integrations.md` - Third-party API patterns
- `domain-7-gap-synthesis.md` - Product-specific features

---
