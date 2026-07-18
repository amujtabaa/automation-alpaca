# Requirements Mapping for Starter Kit Selection

**Purpose:** Match your product requirements to available starter kits to identify the best foundation.

---

## Mapping Prompt (Copy to Claude Desktop or Code)

```
Based on my Master Strategy Document and technical requirements, help me select the best starter kit from my available options.

For each starter kit, analyze:
1. Feature coverage percentage (how much of what I need is already built)
2. Gap identification (what I'll need to add)
3. Modification scope (complexity of changes needed)
4. Stack compatibility (does it use my preferred stack)
5. Overall fit score

My requirements from the Strategy Document:
[Paste technical requirements section]

Available starter kits:
[List your starter kits with brief descriptions]

Produce a requirements mapping table and recommendation.
```

---

## Requirements Checklist

Before evaluating starter kits, confirm you need these categories:

### Authentication & Authorization
- [ ] User registration/login
- [ ] Social login (Google, GitHub, etc.)
- [ ] Magic link authentication
- [ ] Password reset flow
- [ ] Email verification
- [ ] Role-based access control
- [ ] Admin vs user roles
- [ ] Multi-tenancy/workspaces
- [ ] Team invitations
- [ ] API authentication

### Payment Processing
- [ ] Subscription billing (Polar)
- [ ] One-time payments
- [ ] Usage-based billing
- [ ] Multiple pricing tiers
- [ ] Checkout flow
- [ ] Customer portal
- [ ] Webhook handling
- [ ] Invoice generation
- [ ] Refund processing
- [ ] Annual vs monthly billing

### Database & Data
- [ ] PostgreSQL support
- [ ] ORM (Prisma/Drizzle)
- [ ] Migration system
- [ ] Type safety
- [ ] Row Level Security
- [ ] Seeding/fixtures
- [ ] Backup strategy

### Background Processing
- [ ] Scheduled jobs (cron)
- [ ] Queue processing
- [ ] Long-running tasks
- [ ] Email sending
- [ ] Webhook processing

### UI/UX
- [ ] Component library
- [ ] Responsive design
- [ ] Dark mode
- [ ] Dashboard layout
- [ ] Data tables
- [ ] Forms with validation
- [ ] Modals/dialogs
- [ ] Toast notifications
- [ ] Loading states

### Content & Media
- [ ] File uploads
- [ ] Image processing
- [ ] S3/R2 storage
- [ ] MDX/blog system
- [ ] Rich text editor

### Email
- [ ] Transactional emails
- [ ] Email templates
- [ ] Email preview
- [ ] Newsletter/marketing

### Analytics & Monitoring
- [ ] Product analytics
- [ ] Error tracking
- [ ] User behavior
- [ ] Custom events

### SEO & Marketing
- [ ] Meta tags
- [ ] Sitemap
- [ ] OpenGraph images
- [ ] robots.txt
- [ ] Structured data

### DevOps & Deployment
- [ ] VPS deployment ready
- [ ] Docker support
- [ ] Environment management
- [ ] CI/CD pipeline
- [ ] Logging

---

## Requirements Mapping Template

```markdown
# Starter Kit Requirements Mapping

**Product:** [Product Name]
**Date:** [Date]

---

## Requirements Summary

**Total Requirements:** [X]
**Critical Requirements:** [X]
**Nice-to-Have:** [X]

---

## Starter Kit Evaluation

### [Starter Kit 1 Name]

**Stack:** [Next.js X, React X, etc.]
**Last Updated:** [Date]
**Documentation:** [Quality rating]

#### Coverage Analysis

| Category | Requirements | Covered | Gap | Notes |
|----------|--------------|---------|-----|-------|
| Auth | [X] | [X] | [X] | [Details] |
| Payments | [X] | [X] | [X] | [Details] |
| Database | [X] | [X] | [X] | [Details] |
| Background Jobs | [X] | [X] | [X] | [Details] |
| UI/UX | [X] | [X] | [X] | [Details] |
| Content | [X] | [X] | [X] | [Details] |
| Email | [X] | [X] | [X] | [Details] |
| Analytics | [X] | [X] | [X] | [Details] |
| SEO | [X] | [X] | [X] | [Details] |
| DevOps | [X] | [X] | [X] | [Details] |
| **TOTAL** | **[X]** | **[X]** | **[X]** | **[X]%** |

#### Strengths
- [Strength 1]
- [Strength 2]

#### Gaps to Fill
- [Gap 1]: [Estimated effort]
- [Gap 2]: [Estimated effort]

#### Fit Score: [X]/10

---

### [Starter Kit 2 Name]

[Same structure as above]

---

### [Starter Kit 3 Name]

[Same structure as above]

---

## Comparison Matrix

| Criteria | [Kit 1] | [Kit 2] | [Kit 3] |
|----------|---------|---------|---------|
| Coverage % | [X]% | [X]% | [X]% |
| Gap effort (hours) | [X]h | [X]h | [X]h |
| Stack match | [X]/10 | [X]/10 | [X]/10 |
| Documentation | [X]/10 | [X]/10 | [X]/10 |
| Community/support | [X]/10 | [X]/10 | [X]/10 |
| Recent updates | [X]/10 | [X]/10 | [X]/10 |
| **Overall Score** | **[X]/60** | **[X]/60** | **[X]/60** |

---

## Recommendation

**Selected Starter Kit:** [Name]

### Why This Kit

**Primary reasons:**
1. [Reason 1]
2. [Reason 2]
3. [Reason 3]

**Trade-offs accepted:**
- [Trade-off 1]: [Why acceptable]
- [Trade-off 2]: [Why acceptable]

### Implementation Strategy

**Immediate use (no changes):**
- [Feature 1]
- [Feature 2]

**Minor modifications:**
- [Feature 3]: [What to change]
- [Feature 4]: [What to change]

**Build from scratch:**
- [Feature 5]: [Estimated hours]
- [Feature 6]: [Estimated hours]

**Remove/ignore:**
- [Unnecessary feature 1]
- [Unnecessary feature 2]

### Time Estimate

- **Setup and familiarization:** [X] hours
- **Core modifications:** [X] hours
- **Gap filling:** [X] hours
- **Testing and polish:** [X] hours
- **Total:** [X] hours

---

## Next Steps

1. [ ] Clone selected starter kit
2. [ ] Review documentation thoroughly
3. [ ] Set up development environment
4. [ ] Proceed to Phase 4: Transformation Analysis

---

**Analysis by:** [Your name]
**Last Updated:** [Date]
```

---

## Common Starter Kit Evaluation Criteria

### Stack Compatibility Points

| Factor | Points | Criteria |
|--------|--------|----------|
| Framework match | +3 | Uses your preferred framework (Next.js, etc.) |
| Database match | +2 | Uses your preferred DB (PostgreSQL) |
| ORM match | +2 | Uses your preferred ORM (Prisma) |
| UI library match | +1 | Uses your preferred UI (Tailwind, Shadcn) |
| Runtime match | +1 | Uses your preferred runtime (Bun, Node) |
| Payment provider | +3 | Supports Polar or easy to swap |
| Deployment model | +2 | Supports VPS deployment |

### Red Flags

- ❌ Last updated >6 months ago
- ❌ No TypeScript support
- ❌ Locked to specific deployment (Vercel-only)
- ❌ No documentation
- ❌ Abandoned/archived repository
- ❌ Complex monorepo when not needed
- ❌ Over-engineered for simple use case

---
