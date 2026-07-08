# Phase 1: Idea Extraction Interview Framework

**Purpose:** Extract comprehensive information about your product idea through structured questions to build a Master Strategy Document.

**Duration:** 30-60 minutes
**Output:** Master Strategy Document (use `strategy-document-template.md`)

---

## How to Use This Framework

1. Copy the **Interview Prompt** below into Claude Desktop
2. Answer each question as Claude asks them
3. Request the **Strategy Document** at the end using the template
4. Run **Viability Scoring** using `viability-scorecard.md`

---

## Interview Prompt (Copy to Claude Desktop)

```
You are a product strategy consultant helping me develop a new online SaaS/digital product idea. Your goal is to extract comprehensive information through an interview process, then synthesize it into a Master Strategy Document.

INTERVIEW PROCESS:
1. Ask questions one at a time (or in small related groups)
2. Wait for my response before proceeding
3. Probe deeper when answers are vague or incomplete
4. Note gaps or inconsistencies for later clarification
5. After all questions, produce the Master Strategy Document

QUESTION CATEGORIES:
- Core Concept (5 questions)
- Target Market (4 questions)
- Revenue Model (4 questions)
- Technical Requirements (5 questions)
- Go-to-Market (4 questions)
- Risks & Constraints (3 questions)

Begin with Core Concept questions. After each category, summarize what you've learned before moving to the next.

At the end, produce a comprehensive Master Strategy Document following this structure:
1. Executive Summary
2. Product Overview
3. Target Market Analysis
4. Revenue Model
5. Technical Architecture Overview
6. Go-to-Market Strategy
7. Risk Assessment
8. Success Metrics
9. Open Questions / Areas Needing Research

Start the interview now.
```

---

## Core Questions (25 Total)

### Core Concept (5 Questions)

1. **What problem does your product solve?**
   - Be specific about the pain point
   - Who experiences this pain?
   - How are they solving it today?

2. **What is your product's core value proposition?**
   - One sentence: "My product helps [target] do [action] so they can [benefit]"
   - What makes this valuable enough to pay for?

3. **What is your key innovation or differentiator?**
   - What do you do better/different than alternatives?
   - Why can't competitors easily copy this?

4. **What type of product is this?**
   - Pure SaaS (subscription)
   - Productized service (human + software)
   - Marketplace
   - Tool/utility
   - Information product with automation

5. **What is your product name and positioning statement?**
   - Working name (can be placeholder)
   - Category: "[Product] is a [category] that [key benefit]"

---

### Target Market (4 Questions)

6. **Who is your ideal customer?**
   - Demographics (if B2C) or firmographics (if B2B)
   - Job title / role
   - Company size / stage
   - Geographic focus

7. **What is their current behavior?**
   - How do they solve this problem today?
   - What tools do they currently use?
   - How much do they spend on alternatives?

8. **What triggers them to seek a solution?**
   - Pain event or growth stage
   - Seasonal patterns
   - External pressures

9. **Where do they hang out online?**
   - Communities (Reddit, Discord, Slack)
   - Social platforms
   - Content they consume
   - Events they attend

---

### Revenue Model (4 Questions)

10. **What is your pricing model?**
    - Subscription tiers (monthly/annual)
    - One-time purchase
    - Usage-based
    - Freemium vs free trial

11. **What are your target price points?**
    - Entry tier price
    - Most popular tier (expected)
    - Enterprise/high tier
    - Reasoning for these prices

12. **What are the tier differentiators?**
    - Usage limits (seats, API calls, storage)
    - Feature gates
    - Support levels
    - Add-on services

13. **What is your revenue target?**
    - 6-month MRR goal
    - 12-month MRR goal
    - Customer count targets
    - Average Revenue Per User (ARPU) estimate

---

### Technical Requirements (5 Questions)

14. **What core features are required for MVP?**
    - List 3-5 must-have features
    - What can be deferred to v2?

15. **What external APIs or services will you integrate?**
    - Data sources
    - Payment processing (default: Polar)
    - Email/notifications
    - AI/ML services
    - Analytics

16. **What are your data requirements?**
    - User data to store
    - Content/media handling
    - Data retention needs
    - Privacy considerations (GDPR, etc.)

17. **Do you need background processing?**
    - Scheduled jobs (monitoring, reports)
    - Async processing (queues)
    - Real-time features (websockets)

18. **What are your scaling expectations?**
    - Users at launch
    - Users at 6 months
    - Users at 12 months
    - Traffic patterns (steady vs spiky)

---

### Go-to-Market (4 Questions)

19. **What is your launch strategy?**
    - Beta/waitlist approach
    - ProductHunt launch
    - Community seeding
    - Content marketing

20. **What are your primary acquisition channels?**
    - Organic (SEO, content)
    - Paid (ads, sponsorships)
    - Community (Reddit, Twitter, forums)
    - Partnerships/affiliates

21. **What is your content strategy?**
    - Blog topics
    - Social presence
    - Email marketing
    - Educational content

22. **Do you have existing audience or distribution?**
    - Email list size
    - Social following
    - Community presence
    - Existing products with user base

---

### Risks & Constraints (3 Questions)

23. **What are your biggest technical risks?**
    - API dependencies
    - Scaling challenges
    - Data accuracy requirements
    - Third-party reliability

24. **What are your business constraints?**
    - Budget for development
    - Budget for ongoing costs (APIs, hosting)
    - Time to launch
    - Geographic/legal restrictions

25. **What keeps you up at night about this idea?**
    - Market timing concerns
    - Competition fears
    - Execution worries
    - Personal commitment level

---

## Optional Deep-Dive Questions

Use these when core answers need expansion:

### Product Deep-Dive

- Walk me through the user journey from signup to first value moment
- What does "success" look like for your users?
- What would make users recommend your product to others?
- How will users know your product is working?

### Market Deep-Dive

- Name 3 specific people (real or persona) who would buy this
- What objections would they have during the sales process?
- How price sensitive is this market?
- What's the buying process (impulse vs considered)?

### Technical Deep-Dive

- Draw out the data model (main entities and relationships)
- What's the most technically complex feature?
- What security requirements exist (auth, encryption, compliance)?
- Do you need multi-tenancy (workspaces/teams)?

### Business Model Deep-Dive

- What's your Customer Acquisition Cost (CAC) estimate?
- What's the expected Lifetime Value (LTV)?
- How long until a customer pays back their CAC?
- What are your unit economics at 100 customers?

### Competitive Deep-Dive

- Who would you lose deals to and why?
- What would make someone switch from a competitor to you?
- Are there indirect competitors solving this differently?
- What's the competitive moat you're building?

---

## Interview Completion Checklist

Before generating the Strategy Document, verify:

- [ ] Clear problem statement articulated
- [ ] Target customer specifically defined
- [ ] Pricing model with actual numbers
- [ ] MVP features prioritized (not everything)
- [ ] Technical requirements scoped
- [ ] Launch strategy outlined
- [ ] Key risks identified
- [ ] Revenue targets set

---

## Next Steps

1. Generate **Master Strategy Document** using `strategy-document-template.md`
2. Run **Viability Scoring** using `viability-scorecard.md`
3. Proceed to **Phase 2: Competitor Analysis** with `competitor-brief-template.md`

---
