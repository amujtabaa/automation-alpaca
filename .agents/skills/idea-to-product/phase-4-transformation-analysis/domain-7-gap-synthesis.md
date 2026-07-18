# Domain 7: Gap Synthesis Deep Dive

**Focus:** Product-specific features not covered by standard domains

---

## Purpose

This domain covers everything unique to YOUR product that doesn't fit neatly into the other 6 domains:

- Custom business logic
- Unique workflows
- Product-specific algorithms
- Special UI requirements
- Novel integrations

---

## Questions to Answer

### Core Product Logic
- What's the main algorithm/logic?
- What makes this product unique?
- What are the edge cases?

### Custom Workflows
- What user workflows are product-specific?
- What admin workflows?
- What automated workflows?

### Special Requirements
- Any compliance/legal needs?
- Unique data processing?
- Special security requirements?

---

## Gap Identification Process

### Step 1: List All Product Features
From your Strategy Document, list every feature:
1. [Feature 1]
2. [Feature 2]
3. [Feature 3]
...

### Step 2: Categorize Each Feature

| Feature | Domain | Status |
|---------|--------|--------|
| User login | Auth | ✅ Covered |
| Subscription billing | Payments | ✅ Covered |
| [Custom feature] | **Gap** | ❌ New |
| [Custom feature] | **Gap** | ❌ New |

### Step 3: Detail Each Gap

For each feature marked as Gap:

```markdown
### [Feature Name]

**Description:** [What it does]

**Why it's needed:** [Business value]

**Implementation complexity:** [Low/Medium/High]

**Dependencies:** [What must exist first]

**Implementation approach:**
- [Step 1]
- [Step 2]
- [Step 3]

**Estimated effort:** [X] hours

**Code location:**
- `/path/to/file.ts` - [Description]
```

---

## Common Gap Categories

### Custom Algorithms
- Scoring/ranking systems
- Matching algorithms
- Recommendation engines
- Custom search logic

### Business Logic
- Tier limit enforcement
- Usage tracking
- Custom pricing rules
- Workflow automation

### Specialized UI
- Custom dashboards
- Unique visualizations
- Interactive elements
- Custom forms

### Admin Features
- Content moderation
- User management beyond basics
- Analytics/reporting
- Operations tools

### Integration Orchestration
- Multi-API workflows
- Data enrichment pipelines
- Cross-system sync

---

## Implementation Priority Template

```markdown
## Gap Features Priority List

### P0 - Must Have for MVP
1. **[Feature]** - [X] hours
   - Required for core value proposition
2. **[Feature]** - [X] hours
   - Users can't accomplish main task without this

### P1 - Must Have for Launch
1. **[Feature]** - [X] hours
   - Needed for complete user experience
2. **[Feature]** - [X] hours
   - Differentiator from competitors

### P2 - Nice to Have
1. **[Feature]** - [X] hours
   - Enhances experience but not critical
2. **[Feature]** - [X] hours
   - Can launch without, add in v2

### Total Gap Effort
- P0: [X] hours
- P1: [X] hours
- P2: [X] hours
- **Total: [X] hours**
```

---

## Example: Product-Specific Feature

```typescript
// Example: Opportunity Scoring Algorithm

// lib/scoring/opportunity-score.ts
export function calculateOpportunityScore(opportunity: Opportunity): number {
  const weights = {
    traffic_value: 0.3,
    engagement: 0.25,
    relevance: 0.25,
    recency: 0.2,
  };

  // Normalize traffic value (0-100)
  const trafficScore = Math.min(100, opportunity.traffic_value / 10);

  // Engagement score from upvotes + comments
  const engagementScore = Math.min(100,
    (opportunity.upvotes * 2) + (opportunity.comments * 5)
  );

  // Relevance from keyword matching
  const relevanceScore = opportunity.keyword_match_score;

  // Recency - newer is better
  const hoursOld = (Date.now() - opportunity.created_at.getTime()) / 3600000;
  const recencyScore = Math.max(0, 100 - (hoursOld * 2));

  return Math.round(
    (trafficScore * weights.traffic_value) +
    (engagementScore * weights.engagement) +
    (relevanceScore * weights.relevance) +
    (recencyScore * weights.recency)
  );
}
```

---

## Output Checklist

- [ ] Complete list of gap features
- [ ] Priority ranking (P0/P1/P2)
- [ ] Implementation approach for each
- [ ] Effort estimates
- [ ] Dependencies mapped
- [ ] Code examples for complex logic

---
