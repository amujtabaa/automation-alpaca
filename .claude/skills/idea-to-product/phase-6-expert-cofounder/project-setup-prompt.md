# Expert Co-founder Project Setup

**Purpose:** Create a Claude Desktop project with all your documents as a knowledge base, creating an expert "co-founder" for ongoing product decisions.

---

## What is an Expert Co-founder Project?

A Claude Desktop project where you upload all your strategy and analysis documents. This gives Claude:

- **Context retention** - Remembers your entire product strategy
- **Consistent advice** - Aligned with your documented decisions
- **Quick answers** - No need to re-explain your product

Use it for:
- Marketing copy and messaging
- Feature prioritization decisions
- Technical implementation questions
- Content creation (blog posts, social)
- User research interpretation
- Pricing discussions
- Competitor response strategies

---

## Project Setup Steps

### Step 1: Create New Project

1. Open Claude Desktop
2. Click "Projects" in sidebar
3. Click "New Project"
4. Name it: `[Product Name] - Expert Co-founder`

### Step 2: Set Project Instructions

Copy this into the project custom instructions:

```
You are an expert co-founder for [PRODUCT NAME], a [brief description].

You have deep knowledge of:
- Our product strategy and positioning
- Target market and customer personas
- Competitive landscape and differentiation
- Technical architecture and implementation
- Go-to-market approach

When helping me:
1. Reference our documented strategy when relevant
2. Maintain consistency with established decisions
3. Flag if a question contradicts our strategy
4. Think like a co-founder - challenge ideas constructively
5. Prioritize based on our viability scores and market analysis

Our key differentiators:
- [Differentiator 1]
- [Differentiator 2]
- [Differentiator 3]

Our target customer: [ICP description]

Our positioning: [Positioning statement]

Always consider:
- Revenue impact
- Time to implement
- Competitive response
- User experience
- Technical feasibility
```

### Step 3: Upload Documents

Upload these documents to the project (see `knowledge-base-structure.md` for organization):

**Required Documents:**
- [ ] Master Strategy Document
- [ ] Viability Scorecard
- [ ] Competitive Intelligence Synthesis
- [ ] Transformation Report

**Recommended Documents:**
- [ ] Individual Competitor Briefs
- [ ] Market Positioning Strategy
- [ ] Implementation Checklist

**Optional (if they exist):**
- [ ] API Integration Guides
- [ ] Decision Documents
- [ ] User Research Notes

---

## How to Use the Project

### Marketing & Content

**Generate homepage copy:**
```
Write homepage hero copy for [Product Name]. Use our positioning statement and key differentiators. Target our primary persona. Keep it concise and compelling.
```

**Create social posts:**
```
Write 5 Twitter posts announcing our launch. Reference our competitive advantages and target the indie hacker audience.
```

**Draft blog post outline:**
```
Create a blog post outline about [topic]. Align with our content strategy and target our SEO keywords.
```

### Product Decisions

**Feature prioritization:**
```
We're deciding between [Feature A] and [Feature B] for the next sprint. Based on our strategy and competitive positioning, which should we prioritize and why?
```

**Pricing changes:**
```
We're considering raising prices by 20%. Based on our competitive analysis and unit economics, what are the risks and how should we communicate this?
```

**New feature evaluation:**
```
A user requested [feature]. Should we build it? Consider our roadmap, differentiation strategy, and technical feasibility.
```

### Competitive Response

**Competitor launched a feature:**
```
[Competitor] just launched [feature]. Based on our competitive intelligence, how should we respond? Should we build something similar, differentiate further, or ignore?
```

**Positioning against specific competitor:**
```
I have a sales call with a prospect currently using [Competitor]. What key points should I make based on our positioning and their weaknesses?
```

### Technical Decisions

**Architecture questions:**
```
We need to decide between [Option A] and [Option B] for [component]. Based on our technical requirements and scaling projections, what's the better choice?
```

**Integration decisions:**
```
Should we integrate with [Service]? Consider our integration strategy, costs, and user benefit.
```

---

## Maintaining the Project

### When to Update Documents

- **After major decisions** - Update strategy doc with new direction
- **After user research** - Add insights to strategy
- **After competitor changes** - Update competitive intelligence
- **After pivots** - Revise positioning and differentiation

### Document Version Control

Name documents with dates:
- `master-strategy-v1.2-2024-03.md`
- `competitive-intelligence-2024-03.md`

Or use a simple changelog:
```markdown
## Document Updates

- 2024-03-15: Updated pricing tiers based on beta feedback
- 2024-03-01: Added new competitor [Name]
- 2024-02-15: Initial version
```

---

## Example Conversations

### Example 1: Content Creation

**You:** Write a ProductHunt launch description for [Product Name].

**Claude:** Based on our positioning as "[positioning statement]" and targeting [ICP], here's a PH description:

**Tagline:** [Short punchy tagline]

**Description:**
[Product Name] helps [target] [achieve outcome] without [pain point].

Unlike [competitors] that [weakness], we [differentiator].

Key features:
- [Feature 1] - [Benefit]
- [Feature 2] - [Benefit]
- [Feature 3] - [Benefit]

Built for [specific audience] who want [outcome].

### Example 2: Strategic Decision

**You:** Should we add a free tier?

**Claude:** Based on our strategy, I'd advise against a free tier right now. Here's why:

1. **Our competitive analysis** shows competitors with free tiers have high churn and struggle to convert
2. **Our unit economics** depend on $29+ entry pricing
3. **Our differentiation** is quality over price - free tier dilutes this

However, consider:
- 14-day free trial (already planned)
- Freemium with very limited features as lead gen

If you want to test demand, I'd suggest a waitlist with early-bird pricing instead.

---

## Troubleshooting

### Project not giving relevant answers

- Check documents are properly uploaded
- Verify project instructions are set
- Ask Claude to reference specific documents

### Answers contradicting strategy

- Update documents with latest decisions
- Clarify in custom instructions
- Explicitly reference which document to follow

### Running out of context

- Summarize less critical documents
- Focus on most relevant docs for conversation
- Split into multiple focused projects if needed

---
