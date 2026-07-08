# Monetization Models Reference

**Purpose:** Framework for choosing and designing your product's pricing and revenue model.

---

## Common SaaS Pricing Models

### 1. Flat-Rate Subscription
**One price, all features**

```
$49/month - Everything included
```

**Best for:**
- Simple products
- Clear value proposition
- Early-stage validation

**Pros:** Easy to understand, simple to implement
**Cons:** No room for growth, leaves money on table

---

### 2. Tiered Subscription
**Multiple plans at different price points**

```
Starter: $29/mo - Basic features
Growth: $79/mo - More features + limits
Pro: $199/mo - All features + higher limits
```

**Best for:**
- Products with varying use cases
- Different customer segments
- Upsell potential

**Pros:** Captures more value, clear upgrade path
**Cons:** Complexity, decision paralysis risk

---

### 3. Usage-Based
**Pay for what you use**

```
$0.01 per API call
$5 per 1,000 records
```

**Best for:**
- APIs and infrastructure
- Variable usage patterns
- Developer tools

**Pros:** Fair, scales with value, low barrier
**Cons:** Unpredictable revenue, billing complexity

---

### 4. Hybrid (Subscription + Usage)
**Base subscription + usage fees**

```
$49/mo base + $0.01 per additional call over 10,000
```

**Best for:**
- Products with baseline + variable usage
- Predictable revenue with upside

**Pros:** Predictable base + upside, fair scaling
**Cons:** Complex to explain and implement

---

### 5. Freemium
**Free tier with paid upgrades**

```
Free: Limited features
Pro: $29/mo - Full features
```

**Best for:**
- Network effects
- Viral products
- Long sales cycles

**Pros:** Lower barrier, viral potential
**Cons:** Support burden, conversion challenges

---

### 6. Per-Seat
**Price per user**

```
$10/user/month
```

**Best for:**
- Collaboration tools
- Team-based products

**Pros:** Scales with adoption, clear value
**Cons:** Limits adoption, seat-pooling issues

---

## Pricing Strategy Framework

### Step 1: Understand Value

**Value Metric Questions:**
- What unit of value does customer get?
- How does more usage = more value?
- What do they pay for alternatives?

**Common Value Metrics:**
- Users/seats
- Projects/workspaces
- API calls/records
- Features unlocked
- Storage
- Results/outcomes

---

### Step 2: Segment Customers

| Segment | Size | Budget | Needs | Sensitivity |
|---------|------|--------|-------|-------------|
| Hobbyist | Large | $0-29 | Basic | High |
| Pro Individual | Medium | $29-99 | Full | Medium |
| Small Team | Medium | $99-299 | + Collab | Medium |
| Business | Small | $299+ | + Support | Low |

---

### Step 3: Design Tiers

### Tier Design Template

```markdown
## Tier: [Name]
**Price:** $[X]/month ($[X]/year)
**Target:** [Who this is for]
**Psychology:** [Why they buy this tier]

### Limits
- [Value metric 1]: [Limit]
- [Value metric 2]: [Limit]
- [Value metric 3]: [Limit]

### Features
- [Feature 1]: ✅
- [Feature 2]: ✅
- [Feature 3]: ❌

### Why Not Lower Tier
[What they need that lower tier doesn't have]

### Why Not Higher Tier
[What they don't need from higher tier]
```

---

### Step 4: Set Prices

**Pricing Anchors:**
- Competitor prices (be aware but don't copy)
- Value delivered (10x rule: price = 1/10 of value)
- Cost + margin (minimum viable price)
- Round numbers (psychological pricing)

**Pricing Psychology:**
- $29 not $30 (left-digit effect)
- 3 tiers (middle bias)
- Annual discount 15-20% (2-3 months free)
- Enterprise "Contact us" (anchor high)

---

## SaaS Pricing Benchmarks

### B2C / Prosumer
- Entry: $9-29/mo
- Mid: $29-99/mo
- Pro: $99-199/mo

### B2B SMB
- Entry: $29-49/mo
- Mid: $99-199/mo
- Pro: $299-499/mo

### B2B Mid-Market
- Entry: $99-299/mo
- Mid: $499-999/mo
- Pro: $999-2999/mo

### Developer Tools
- Entry: Free or $9-29/mo
- Mid: $49-99/mo
- Pro: $199-499/mo

---

## Monetization Decision Matrix

| Factor | → Tiered | → Usage | → Freemium |
|--------|----------|---------|------------|
| Predictable usage | ✅ | ❌ | ✅ |
| Variable usage | ❌ | ✅ | ❌ |
| High switching cost | ✅ | ❌ | ❌ |
| Low switching cost | ❌ | ❌ | ✅ |
| Strong network effects | ❌ | ❌ | ✅ |
| Clear segments | ✅ | ❌ | ❌ |
| API/infrastructure | ❌ | ✅ | ❌ |
| Long sales cycle | ❌ | ❌ | ✅ |

---

## Pricing Page Best Practices

### Structure
1. **Hero:** One clear statement of value
2. **Tiers:** 3 plans (highlight middle)
3. **Comparison:** Feature table
4. **FAQ:** Common objections
5. **CTA:** Clear next step

### Effective Elements
- Annual/monthly toggle (show annual first)
- "Most popular" badge on middle tier
- Feature comparison table
- Social proof near CTAs
- Money-back guarantee
- "Talk to us" for enterprise

---

## Pricing Experiments to Run

### Pre-Launch
1. **Survey willingness to pay**
   - "How much would you pay for [benefit]?"
   - Price sensitivity meter

2. **Landing page tests**
   - Different price points
   - Different tier structures

### Post-Launch
1. **A/B test prices** (10-20% increments)
2. **Test annual discounts** (2 vs 3 months free)
3. **Test tier limits** (more/less generous)
4. **Test feature bundling**

---

## Revenue Optimization

### Expansion Revenue
- Usage upgrades (hit limits)
- Seat expansion (add team)
- Feature upsells (add-ons)
- Tier upgrades (growth)

### Retention
- Annual plans (lower churn)
- Usage-based stickiness
- Data lock-in
- Workflow integration

### Metrics to Track
- MRR / ARR
- ARPU (average revenue per user)
- Net revenue retention
- Expansion MRR
- Churn rate by tier

---

## Pricing Template for Strategy Document

```markdown
## Pricing Strategy

### Model
[Subscription / Usage / Hybrid]

### Value Metric
[What we charge for]

### Tiers

| Tier | Monthly | Annual | Target | Key Limits |
|------|---------|--------|--------|------------|
| [Name] | $[X] | $[X] | [Who] | [Limits] |
| [Name] | $[X] | $[X] | [Who] | [Limits] |
| [Name] | $[X] | $[X] | [Who] | [Limits] |

### Rationale
[Why these prices and tiers]

### Competitive Position
[How we compare to market]

### Future Considerations
- [What might change]
- [Experiments to run]
```

---
