# Master Strategy Document Template

**Purpose:** Output format for Phase 1 interview synthesis. Use this template to structure all extracted information.

---

## Template (Copy and Fill)

```markdown
# [Product Name] - Master Strategy Document

**Generated:** [Date]
**Version:** 1.0
**Status:** Draft / In Review / Approved

---

## 1. Executive Summary

### One-Liner
[Product Name] is a [product type] that helps [target customer] [achieve outcome] by [key mechanism].

### Key Highlights
- **Problem:** [One sentence problem statement]
- **Solution:** [One sentence solution]
- **Differentiator:** [What makes this unique]
- **Target Market:** [Who and how big]
- **Revenue Model:** [Pricing approach]
- **Launch Timeline:** [Target date]

### Viability Score
**Overall: [X]/100** (see Viability Scorecard)
- Market Potential: [X]/20
- Technical Feasibility: [X]/20
- Competition: [X]/15
- Revenue Potential: [X]/15
- Time to MVP: [X]/10
- Founder Fit: [X]/10
- Growth Potential: [X]/10

---

## 2. Product Overview

### Problem Statement
[Detailed description of the problem]

**Who experiences this problem:**
- [Customer segment 1]
- [Customer segment 2]

**Current solutions and their shortcomings:**
- [Solution A]: [Shortcoming]
- [Solution B]: [Shortcoming]

### Solution
[Detailed description of your solution]

**Core value proposition:**
[Statement: My product helps X do Y so they can Z]

### Key Innovation
[What you do differently and why it matters]

**Why competitors can't easily copy:**
- [Barrier 1]
- [Barrier 2]

### Product Type
- [ ] Pure SaaS (subscription software)
- [ ] Productized Service (human + software)
- [ ] Marketplace
- [ ] Developer Tool
- [ ] Information Product

### MVP Features (Priority Order)
1. **[Feature 1]** - [Why critical for MVP]
2. **[Feature 2]** - [Why critical for MVP]
3. **[Feature 3]** - [Why critical for MVP]
4. **[Feature 4]** - [Why critical for MVP]
5. **[Feature 5]** - [Why critical for MVP]

### v2 Features (Post-Launch)
- [Feature A]
- [Feature B]
- [Feature C]

---

## 3. Target Market Analysis

### Ideal Customer Profile

**Demographics/Firmographics:**
- Industry: [X]
- Company size: [X]
- Role/title: [X]
- Geography: [X]

**Psychographics:**
- Goals: [X]
- Frustrations: [X]
- Values: [X]

### Customer Personas

**Persona 1: [Name]**
- Background: [X]
- Current tools: [X]
- Pain points: [X]
- Buying behavior: [X]

**Persona 2: [Name]**
- Background: [X]
- Current tools: [X]
- Pain points: [X]
- Buying behavior: [X]

### Market Size

**TAM (Total Addressable Market):** $[X]
**SAM (Serviceable Addressable Market):** $[X]
**SOM (Serviceable Obtainable Market):** $[X] (realistic first-year target)

### Where They Hang Out
- **Communities:** [Reddit subs, Discord servers, Slack groups]
- **Social:** [Twitter, LinkedIn, specific influencers]
- **Content:** [Blogs, podcasts, YouTube channels]
- **Events:** [Conferences, meetups]

---

## 4. Revenue Model

### Pricing Strategy

**Model:** [Subscription / One-time / Usage-based / Freemium]

**Tier Structure:**

| Tier | Price | Target Customer | Key Features |
|------|-------|-----------------|--------------|
| [Free/Starter] | $[X]/mo | [Who] | [What they get] |
| [Growth] | $[X]/mo | [Who] | [What they get] |
| [Pro] | $[X]/mo | [Who] | [What they get] |
| [Enterprise] | $[X]/mo | [Who] | [What they get] |

**Annual discount:** [X]% (e.g., 2 months free)

### Revenue Targets

| Timeframe | MRR Target | Customer Count | ARPU |
|-----------|------------|----------------|------|
| Launch | $[X] | [X] | $[X] |
| 3 months | $[X] | [X] | $[X] |
| 6 months | $[X] | [X] | $[X] |
| 12 months | $[X] | [X] | $[X] |

### Unit Economics

- **Customer Acquisition Cost (CAC):** $[X] estimated
- **Lifetime Value (LTV):** $[X] estimated
- **LTV:CAC Ratio:** [X]:1 (target 3:1+)
- **Payback Period:** [X] months

### Payment Processing
**Provider:** Polar (default for indie SaaS)
- Processing fee: 4% + $0.40
- Payout timing: [Weekly/Monthly]

---

## 5. Technical Architecture Overview

### Tech Stack

**Frontend:**
- Framework: [Next.js 15 / etc.]
- UI Library: [Shadcn/Tailwind / etc.]
- State Management: [X]

**Backend:**
- Runtime: [Node.js / Bun / etc.]
- Database: [PostgreSQL / etc.]
- ORM: [Prisma / Drizzle / etc.]

**Infrastructure:**
- Hosting: VPS with [Coolify / Dokku]
- Database hosting: [Supabase / Railway / self-hosted]
- File storage: [S3 / R2]

**Third-Party Services:**
- Payments: Polar
- Email: [Resend / Postmark]
- Analytics: [PostHog / Plausible]
- AI: [OpenAI / Anthropic / etc.]

### External API Integrations

| Service | Purpose | Rate Limits | Cost |
|---------|---------|-------------|------|
| [API 1] | [Why] | [Limits] | $[X]/mo |
| [API 2] | [Why] | [Limits] | $[X]/mo |

### Data Architecture

**Core Entities:**
- [Entity 1]: [Description]
- [Entity 2]: [Description]
- [Entity 3]: [Description]

**Multi-tenancy:** [Yes/No - workspace-based isolation]

**Data Retention:** [Policy]

**Privacy Compliance:** [GDPR / CCPA / etc.]

### Background Processing

- [ ] Scheduled jobs needed (monitoring, reports, etc.)
- [ ] Async processing (queues, heavy computation)
- [ ] Real-time features (websockets, live updates)

**Job scheduler:** node-cron (VPS deployment)

### Scaling Projections

| Milestone | Users | Data Volume | Infra Cost |
|-----------|-------|-------------|------------|
| Launch | [X] | [X] | $[X]/mo |
| 6 months | [X] | [X] | $[X]/mo |
| 12 months | [X] | [X] | $[X]/mo |

---

## 6. Go-to-Market Strategy

### Launch Strategy

**Phase 1: Pre-Launch**
- [ ] Build waitlist/landing page
- [ ] Content seeding (blog posts, social)
- [ ] Community engagement
- [ ] Beta user recruitment

**Phase 2: Private Beta**
- [ ] [X] beta users
- [ ] Feedback collection
- [ ] Iterate on core features
- [ ] Build testimonials

**Phase 3: Public Launch**
- [ ] ProductHunt launch
- [ ] Community announcements
- [ ] Early-bird pricing
- [ ] PR/press outreach

### Acquisition Channels

**Primary Channels (focus here):**
1. [Channel 1] - [Why effective for this market]
2. [Channel 2] - [Why effective for this market]

**Secondary Channels (experiment later):**
- [Channel A]
- [Channel B]

### Content Strategy

**Blog Topics:**
- [Topic 1 - keyword target]
- [Topic 2 - keyword target]
- [Topic 3 - keyword target]

**Social Strategy:**
- Primary platform: [X]
- Posting frequency: [X]
- Content types: [X]

**Email Marketing:**
- Nurture sequence: [X emails]
- Newsletter frequency: [X]

### Existing Distribution

- Email list: [X] subscribers
- Twitter: [X] followers
- Other: [X]

---

## 7. Risk Assessment

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| [Risk 1] | [H/M/L] | [H/M/L] | [Strategy] |
| [Risk 2] | [H/M/L] | [H/M/L] | [Strategy] |

### Business Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| [Risk 1] | [H/M/L] | [H/M/L] | [Strategy] |
| [Risk 2] | [H/M/L] | [H/M/L] | [Strategy] |

### Market Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| [Risk 1] | [H/M/L] | [H/M/L] | [Strategy] |
| [Risk 2] | [H/M/L] | [H/M/L] | [Strategy] |

### Constraints

- **Budget:** $[X] for development, $[X]/mo for operations
- **Timeline:** [X] weeks to MVP
- **Geographic/Legal:** [Any restrictions]

---

## 8. Success Metrics

### North Star Metric
[Single metric that best captures value delivery]

### Key Performance Indicators

**Acquisition:**
- Signups per week: [target]
- Trial-to-paid conversion: [target %]
- CAC: [target $]

**Activation:**
- Time to first value: [target]
- Activation rate: [target %]

**Retention:**
- Day 7 retention: [target %]
- Day 30 retention: [target %]
- Monthly churn: [target %]

**Revenue:**
- MRR: [target $]
- ARPU: [target $]
- LTV: [target $]

**Referral:**
- NPS: [target]
- Referral rate: [target %]

---

## 9. Open Questions / Areas Needing Research

### Must Answer Before Development
1. [Question 1]
2. [Question 2]
3. [Question 3]

### Research During Development
1. [Question 1]
2. [Question 2]

### Validate Post-Launch
1. [Question 1]
2. [Question 2]

---

## 10. Competitive Landscape (Summary)

> **Note:** Full competitor analysis in Phase 2 documents

### Direct Competitors
- [Competitor 1]: [One-line description]
- [Competitor 2]: [One-line description]
- [Competitor 3]: [One-line description]

### Indirect Competitors
- [Solution A]: [How they solve it differently]
- [Solution B]: [How they solve it differently]

### Competitive Advantages
1. [Advantage 1]
2. [Advantage 2]
3. [Advantage 3]

---

## Next Steps

1. [ ] Complete Viability Scoring (Phase 1)
2. [ ] Conduct Competitor Analysis (Phase 2)
3. [ ] Select Starter Kit (Phase 3)
4. [ ] Run Transformation Analysis (Phase 4)
5. [ ] Create Expert Co-founder Project (Phase 5)

---

**Document Owner:** [Your name]
**Last Updated:** [Date]
```

---
