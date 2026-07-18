# Unit Economics Template

**Purpose:** Calculate and validate the financial viability of your product before building.

---

## When to Use

Use this template to:
- Validate pricing covers costs
- Project profitability at scale
- Identify margin optimization opportunities
- Set realistic growth targets

---

## Unit Economics Document Template

```markdown
# Unit Economics: [Product Name]

**Date:** [Date]
**Model Type:** [SaaS / Productized Service / Hybrid]

---

## 1. Revenue per Unit

### Pricing Tiers

| Tier | Monthly | Annual | Target Segment |
|------|---------|--------|----------------|
| [Tier 1] | $[X] | $[X] | [Who] |
| [Tier 2] | $[X] | $[X] | [Who] |
| [Tier 3] | $[X] | $[X] | [Who] |

### Blended ARPU Projection

```
Expected tier distribution:
- Tier 1: [X]% of customers
- Tier 2: [X]% of customers
- Tier 3: [X]% of customers

Blended Monthly ARPU: $[X]
Blended Annual ARPU: $[X]
```

---

## 2. Cost per Unit

### Variable Costs (per customer/month)

| Cost Item | Amount | Notes |
|-----------|--------|-------|
| Infrastructure (hosting, DB) | $[X] | [Provider, details] |
| Third-party APIs | $[X] | [Services used] |
| Payment processing (2.9%+$0.30) | $[X] | [Based on ARPU] |
| Support time | $[X] | [Hours × rate] |
| Fulfillment (if productized) | $[X] | [Time × rate] |
| **Total Variable Cost** | **$[X]** | |

### Fixed Costs (monthly)

| Cost Item | Amount | Notes |
|-----------|--------|-------|
| Hosting baseline | $[X] | [Before per-customer costs] |
| SaaS tools | $[X] | [List: analytics, email, etc.] |
| Domain/SSL | $[X] | [Annualized monthly] |
| **Total Fixed Cost** | **$[X]** | |

---

## 3. Margin Analysis

### Per-Customer Margins

| Tier | Revenue | Variable Cost | Gross Margin | Margin % |
|------|---------|---------------|--------------|----------|
| [Tier 1] | $[X] | $[X] | $[X] | [X]% |
| [Tier 2] | $[X] | $[X] | $[X] | [X]% |
| [Tier 3] | $[X] | $[X] | $[X] | [X]% |

### Blended Gross Margin
- **Monthly:** $[X] per customer
- **Gross Margin %:** [X]%

### Target Benchmarks
- SaaS: 70-85% gross margin
- Productized service: 50-70% gross margin
- API/usage-based: 60-80% gross margin

---

## 4. Break-Even Analysis

### Monthly Break-Even

```
Fixed costs: $[X]/month
Gross margin per customer: $[X]
Break-even customers: [X]
```

### Time to Profitability

| Month | Customers | Revenue | Costs | Net |
|-------|-----------|---------|-------|-----|
| 1 | [X] | $[X] | $[X] | $[X] |
| 3 | [X] | $[X] | $[X] | $[X] |
| 6 | [X] | $[X] | $[X] | $[X] |
| 12 | [X] | $[X] | $[X] | $[X] |

---

## 5. Customer Lifetime Value (LTV)

### Churn Assumptions
- Monthly churn rate: [X]%
- Average customer lifetime: [X] months
- Calculation: 1 / churn rate

### LTV Calculation

```
Monthly ARPU: $[X]
Gross margin: [X]%
Average lifetime: [X] months

LTV = ARPU × Margin % × Lifetime
LTV = $[X] × [X]% × [X] = $[X]
```

### LTV by Tier

| Tier | ARPU | Lifetime | LTV |
|------|------|----------|-----|
| [Tier 1] | $[X] | [X] mo | $[X] |
| [Tier 2] | $[X] | [X] mo | $[X] |
| [Tier 3] | $[X] | [X] mo | $[X] |

---

## 6. Customer Acquisition Cost (CAC)

### Acquisition Channels

| Channel | Monthly Spend | Customers | CAC |
|---------|---------------|-----------|-----|
| Content/SEO | $[X] | [X] | $[X] |
| Paid ads | $[X] | [X] | $[X] |
| Communities | $[X] | [X] | $[X] |
| Referrals | $[X] | [X] | $[X] |
| **Blended** | **$[X]** | **[X]** | **$[X]** |

### LTV:CAC Ratio

```
LTV: $[X]
CAC: $[X]
LTV:CAC Ratio: [X]:1

Target: 3:1 or higher
```

### CAC Payback Period

```
CAC: $[X]
Monthly gross profit: $[X]
Payback: [X] months

Target: <12 months
```

---

## 7. Scaling Projections

### Revenue Scenarios

| Customers | MRR | ARR | Monthly Profit |
|-----------|-----|-----|----------------|
| 10 | $[X] | $[X] | $[X] |
| 50 | $[X] | $[X] | $[X] |
| 100 | $[X] | $[X] | $[X] |
| 500 | $[X] | $[X] | $[X] |
| 1000 | $[X] | $[X] | $[X] |

### Cost Scaling Notes
- Infrastructure: [Linear / Step-function / Economies of scale]
- Support: [When to hire, cost impact]
- API costs: [How they scale with usage]

---

## 8. Optimization Levers

### Revenue Optimization
1. **Increase ARPU:** [Strategy]
2. **Improve tier mix:** [Strategy]
3. **Annual upsells:** [Strategy]
4. **Expansion revenue:** [Strategy]

### Cost Optimization
1. **Infrastructure:** [Optimization opportunity]
2. **API costs:** [Caching, batching strategies]
3. **Support:** [Automation, self-serve]
4. **Fulfillment:** [Process improvements]

### Churn Reduction
1. **Onboarding:** [Improvement]
2. **Engagement:** [Improvement]
3. **Value delivery:** [Improvement]

---

## 9. Risk Factors

### Margin Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| API price increase | [X]% margin hit | [H/M/L] | [Strategy] |
| Infrastructure costs | [X]% margin hit | [H/M/L] | [Strategy] |
| Support burden | [X]% margin hit | [H/M/L] | [Strategy] |

### Revenue Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Higher churn | [X]% revenue | [H/M/L] | [Strategy] |
| Lower ARPU | [X]% revenue | [H/M/L] | [Strategy] |
| Slow acquisition | [X]% revenue | [H/M/L] | [Strategy] |

---

## 10. Decision Criteria

### Go/No-Go Thresholds

- [ ] Gross margin > 60%
- [ ] LTV:CAC > 3:1
- [ ] Payback < 12 months
- [ ] Break-even < [X] customers
- [ ] Path to $10K MRR within 12 months

### Pricing Validation

- [ ] Higher than cost + 50% margin
- [ ] Lower than competitor average
- [ ] Aligned with value delivered
- [ ] Room for discounts/promotions

---

## Summary

### Key Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Blended ARPU | $[X] | $[X]+ | [✅/⚠️/❌] |
| Gross Margin | [X]% | 60%+ | [✅/⚠️/❌] |
| LTV | $[X] | $[X]+ | [✅/⚠️/❌] |
| Target CAC | $[X] | <$[X] | [✅/⚠️/❌] |
| LTV:CAC | [X]:1 | 3:1+ | [✅/⚠️/❌] |
| Break-even | [X] customers | <[X] | [✅/⚠️/❌] |

### Recommendation

[Overall assessment of unit economics viability and key actions needed]

---

**Document Owner:** [Name]
**Last Updated:** [Date]
```

---

## Quick Unit Economics Calculator

For rapid validation, use this simplified calculation:

```
1. Target monthly price: $[X]
2. Variable cost per customer: $[X] (APIs, hosting, support)
3. Gross margin: Price - Cost = $[X] ([X]%)

4. Fixed costs: $[X]/month
5. Break-even: Fixed / Gross margin = [X] customers

6. Target MRR: $10,000
7. Customers needed: $10,000 / Price = [X]
8. Gross profit at target: [X] customers × $[X] margin = $[X]

Is this achievable in 12 months? [Yes/No]
```

---
