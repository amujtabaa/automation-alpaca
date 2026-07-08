# Viability Scorecard - Weighted Matrix

**Purpose:** Score your idea's viability using 7 weighted factors. Aim for 70+ out of 100 before committing development time.

---

## Scoring Prompt (Copy to Claude Desktop)

```
Based on the Master Strategy Document we just created, score this idea using the following weighted viability matrix. For each factor, provide:
1. A score from 1-10 (see criteria below)
2. Brief justification for the score
3. Key risks or opportunities affecting this factor

Then calculate the weighted total and provide an overall assessment with recommendations.

SCORING MATRIX:

1. MARKET POTENTIAL (Weight: 20%)
   Score 1-10, multiply by 2

2. TECHNICAL FEASIBILITY (Weight: 20%)
   Score 1-10, multiply by 2

3. COMPETITIVE LANDSCAPE (Weight: 15%)
   Score 1-10, multiply by 1.5

4. REVENUE POTENTIAL (Weight: 15%)
   Score 1-10, multiply by 1.5

5. TIME TO MVP (Weight: 10%)
   Score 1-10, multiply by 1

6. FOUNDER FIT (Weight: 10%)
   Score 1-10, multiply by 1

7. GROWTH POTENTIAL (Weight: 10%)
   Score 1-10, multiply by 1

Total possible: 100 points

Provide the scorecard in a table format, then give overall recommendations based on the score.
```

---

## Factor 1: Market Potential (Weight: 20%)

**Question:** Is there a large, growing market with real pain and willingness to pay?

| Score | Criteria |
|-------|----------|
| 9-10 | Large market ($1B+), fast growing (20%+ YoY), clear pain point, proven willingness to pay |
| 7-8 | Medium market ($100M-1B), growing steadily, identifiable pain, customers spending on alternatives |
| 5-6 | Niche market ($10M-100M), stable or slow growth, pain exists but not urgent |
| 3-4 | Small market (<$10M), flat or declining, vague pain point, price sensitivity |
| 1-2 | Tiny/non-existent market, no clear pain, unwilling to pay |

**Key Indicators:**
- TAM/SAM/SOM calculations
- Existing spend on alternatives
- Market growth rate
- Customer acquisition difficulty

---

## Factor 2: Technical Feasibility (Weight: 20%)

**Question:** Can this be built with available technology, within budget, using AI-assisted development?

| Score | Criteria |
|-------|----------|
| 9-10 | Well-established tech stack, starter kit covers 80%+, all APIs available and reliable, simple architecture |
| 7-8 | Proven tech, starter kit covers 60-80%, APIs available with some complexity, moderate architecture |
| 5-6 | Some technical uncertainty, starter kit covers 40-60%, API limitations, complex architecture |
| 3-4 | Significant technical risk, heavy custom development, unreliable APIs, very complex architecture |
| 1-2 | Requires R&D/breakthrough technology, no existing solutions, extreme complexity |

**Key Indicators:**
- Starter kit coverage percentage
- API reliability and rate limits
- Data accuracy requirements
- Scaling complexity

---

## Factor 3: Competitive Landscape (Weight: 15%)

**Question:** Can you differentiate meaningfully and defend your position?

| Score | Criteria |
|-------|----------|
| 9-10 | Blue ocean (no direct competitors), or clear 10x improvement on key dimension |
| 7-8 | Few competitors, differentiation clear, some defensibility (data, network, expertise) |
| 5-6 | Moderate competition, differentiation exists but copyable, weak moat |
| 3-4 | Crowded market, hard to differentiate, no moat, competitor could crush you |
| 1-2 | Dominated by well-funded incumbents, commoditized, no path to differentiation |

**Key Indicators:**
- Number and strength of competitors
- Clarity of differentiation
- Defensibility of advantage
- Competitor response likelihood

---

## Factor 4: Revenue Potential (Weight: 15%)

**Question:** Can this reach meaningful recurring revenue ($10K+ MRR) within 12 months?

| Score | Criteria |
|-------|----------|
| 9-10 | High ARPU ($100+/mo), low churn (<3%), clear path to $50K+ MRR |
| 7-8 | Good ARPU ($50-100/mo), acceptable churn (3-5%), path to $20-50K MRR |
| 5-6 | Moderate ARPU ($20-50/mo), higher churn (5-8%), path to $10-20K MRR |
| 3-4 | Low ARPU (<$20/mo), high churn (8%+), difficult to reach $10K MRR |
| 1-2 | Cannot charge meaningful prices, no recurring revenue model, low LTV |

**Key Indicators:**
- Price points comparable to alternatives
- Unit economics (LTV:CAC)
- Churn expectations
- Upsell/expansion potential

---

## Factor 5: Time to MVP (Weight: 10%)

**Question:** Can you launch a valuable MVP within 4 weeks?

| Score | Criteria |
|-------|----------|
| 9-10 | 1-2 weeks to MVP, minimal features needed, starter kit handles most |
| 7-8 | 2-3 weeks to MVP, clear feature scope, starter kit helps significantly |
| 5-6 | 3-4 weeks to MVP, feature creep risk, some custom development |
| 3-4 | 4-6 weeks to MVP, complex features, significant custom development |
| 1-2 | 6+ weeks to MVP, scope unclear, heavy custom development |

**Key Indicators:**
- Feature scope clarity
- Starter kit applicability
- Technical complexity
- External dependencies

---

## Factor 6: Founder Fit (Weight: 10%)

**Question:** Do you have the skills, motivation, and context to build this?

| Score | Criteria |
|-------|----------|
| 9-10 | Deep domain expertise, personal pain point, existing audience, high motivation |
| 7-8 | Good domain knowledge, understand customer well, some audience, strong motivation |
| 5-6 | Learning the domain, theoretical understanding, no audience, moderate motivation |
| 3-4 | Unfamiliar domain, don't understand customer, no audience, motivation unclear |
| 1-2 | No relevant experience, no connection to problem, low motivation |

**Key Indicators:**
- Domain expertise
- Customer access
- Existing distribution
- Long-term interest in space

---

## Factor 7: Growth Potential (Weight: 10%)

**Question:** Can this grow beyond the founder through virality, SEO, or network effects?

| Score | Criteria |
|-------|----------|
| 9-10 | Built-in virality, strong network effects, SEO goldmine, scalable acquisition |
| 7-8 | Some viral mechanics, SEO opportunity, word-of-mouth potential |
| 5-6 | Limited viral potential, some SEO, growth requires ongoing effort |
| 3-4 | No viral mechanics, poor SEO fit, high-touch sales required |
| 1-2 | Anti-viral (private/sensitive), no organic growth path, founder-dependent |

**Key Indicators:**
- Viral coefficient potential
- SEO keyword opportunity
- Network effects
- Referral incentives

---

## Score Interpretation

| Total Score | Interpretation | Recommendation |
|-------------|----------------|----------------|
| **85-100** | Exceptional opportunity | Proceed immediately, move fast |
| **70-84** | Strong opportunity | Proceed with confidence |
| **55-69** | Moderate opportunity | Proceed with caution, address weak areas |
| **40-54** | Weak opportunity | Reconsider or pivot, significant risks |
| **Below 40** | Poor opportunity | Do not proceed, find different idea |

---

## Scorecard Template

```markdown
# Viability Scorecard: [Product Name]

**Date:** [Date]
**Overall Score:** [X]/100

## Factor Scores

| Factor | Raw Score (1-10) | Weight | Weighted Score | Justification |
|--------|------------------|--------|----------------|---------------|
| Market Potential | [X] | x2.0 | [X] | [Brief reason] |
| Technical Feasibility | [X] | x2.0 | [X] | [Brief reason] |
| Competitive Landscape | [X] | x1.5 | [X] | [Brief reason] |
| Revenue Potential | [X] | x1.5 | [X] | [Brief reason] |
| Time to MVP | [X] | x1.0 | [X] | [Brief reason] |
| Founder Fit | [X] | x1.0 | [X] | [Brief reason] |
| Growth Potential | [X] | x1.0 | [X] | [Brief reason] |
| **TOTAL** | - | - | **[X]/100** | - |

## Strengths (Highest Scores)
1. [Factor]: [Why it scored high]
2. [Factor]: [Why it scored high]

## Weaknesses (Lowest Scores)
1. [Factor]: [Why it scored low] → [Mitigation strategy]
2. [Factor]: [Why it scored low] → [Mitigation strategy]

## Overall Assessment

[2-3 paragraph assessment of the idea's viability, key risks, and recommendations]

## Go/No-Go Decision

- [ ] **GO** - Proceed to Phase 2 (Competitor Analysis)
- [ ] **CONDITIONAL GO** - Address [specific issues] first
- [ ] **NO-GO** - Pivot idea or find new opportunity

## Recommended Focus Areas

If proceeding, prioritize these during development:
1. [Area 1]
2. [Area 2]
3. [Area 3]
```

---

## Special Considerations for Developer/Growth Tools

Since you mentioned developer tools and growth/marketing tools are strong fits, here are bonus points to consider:

**Developer Tool Bonus Indicators:**
- Can you dogfood your own product?
- Will building it teach you valuable skills?
- Is the developer community accessible (Twitter, GitHub, Dev.to)?
- Are developers willing to pay for tools that save time?

**Growth Tool Bonus Indicators:**
- Is the indie hacker wave still growing?
- Can you participate in the community you're serving?
- Do you understand the pain from personal experience?
- Will this generate case studies and testimonials naturally?

---

## Next Steps

After scoring:

1. **Score 70+**: Proceed to Phase 2 - Competitor Analysis
2. **Score 55-69**: Consider pivoting weak areas, then proceed
3. **Score <55**: Revisit the idea or explore alternatives

---

## Optional: Multi-Factor Opportunity Scoring

If your product involves finding, scoring, or prioritizing opportunities (e.g., lead finding, content discovery, market research tools), define a weighted scoring system:

### Example: Opportunity Scoring Framework

```markdown
## Opportunity Score Calculation

| Factor | Weight | Description |
|--------|--------|-------------|
| Relevance | 40% | How well does it match target criteria? |
| Engagement | 30% | What's the activity level/interest? |
| Recency | 20% | How fresh is the opportunity? |
| Quality | 10% | What's the source quality/sentiment? |

### Scoring Thresholds
- **90-100:** High priority, immediate action
- **70-89:** Good opportunity, queue for action
- **50-69:** Monitor, may become actionable
- **Below 50:** Low priority, skip unless volume needed

### Decay Function
Older opportunities should score lower. Example:
- < 24 hours: 100% of recency score
- 1-7 days: 75% of recency score
- 7-30 days: 50% of recency score
- > 30 days: 25% of recency score
```

This framework helps when your product needs to surface the best opportunities from a large pool.

---
