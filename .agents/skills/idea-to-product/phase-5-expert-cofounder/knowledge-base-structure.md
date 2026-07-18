# Knowledge Base Structure for Expert Co-founder

**Purpose:** How to organize documents in your Claude Desktop project for optimal AI assistance.

---

## Recommended Document Organization

```
[Product Name] Expert Co-founder Project
│
├── CORE (Required)
│   ├── master-strategy.md           # Full product strategy
│   ├── viability-score.md           # Scoring and assessment
│   └── competitive-intelligence.md  # Market synthesis
│
├── ANALYSIS (Recommended)
│   ├── transformation-report.md     # Technical implementation plan
│   ├── market-positioning.md        # Positioning strategy
│   └── implementation-checklist.md  # Task breakdown
│
├── COMPETITORS (Optional)
│   ├── competitor-[name]-brief.md   # Individual analyses
│   ├── competitor-[name]-brief.md
│   └── ...
│
└── CONTEXT (As Needed)
    ├── api-[service]-guide.md       # Integration details
    ├── decision-[topic].md          # Key decisions and rationale
    └── user-research-notes.md       # Customer insights
```

---

## Document Priority by Use Case

### For Marketing & Content
**Essential:**
- Master Strategy (messaging, personas)
- Market Positioning (voice, differentiators)
- Competitive Intelligence (comparison points)

### For Product Decisions
**Essential:**
- Master Strategy (roadmap, priorities)
- Viability Score (constraints, risks)
- Transformation Report (technical context)

### For Technical Questions
**Essential:**
- Transformation Report (architecture, patterns)
- Implementation Checklist (task details)
- API Integration Guides (specific services)

---

## Document Preparation Guidelines

### Optimize for AI Consumption

**Do:**
- Use clear headers and structure
- Include summary sections at the top
- Keep formatting consistent
- Use bullet points for lists
- Include specific numbers and data

**Don't:**
- Include unnecessary images
- Have overly long paragraphs
- Use inconsistent formatting
- Leave ambiguous language

### Ideal Document Sections

Each document should have:
1. **Title and date**
2. **Executive summary** (2-3 sentences)
3. **Key takeaways** (bullet list)
4. **Main content** (well-structured)
5. **Action items / Next steps**

---

## Maximum Effectiveness Tips

### 1. Consolidate When Possible

Instead of 5 competitor briefs, create one consolidated competitive analysis with sections for each competitor. Less document switching = better AI performance.

### 2. Create Quick Reference Docs

For frequently accessed info, create a "Quick Reference" doc:
```markdown
# [Product] Quick Reference

## Positioning Statement
[One liner]

## Target Customer
[ICP]

## Key Differentiators
1. [Diff 1]
2. [Diff 2]
3. [Diff 3]

## Pricing
- Tier 1: $X - [Who]
- Tier 2: $X - [Who]
- Tier 3: $X - [Who]

## Competitors
- [Comp A]: [One-line weakness]
- [Comp B]: [One-line weakness]
- [Comp C]: [One-line weakness]
```

### 3. Update After Key Decisions

When you make a significant decision:
1. Update the relevant document
2. Add a "Decision Log" entry
3. Note the date and rationale

### 4. Remove Outdated Content

Old information confuses the AI. When something changes:
- Update or remove outdated docs
- Or clearly mark sections as "OUTDATED - [reason]"

---

## Document Templates for Project

### Quick Reference Template
```markdown
# [Product Name] Quick Reference

**Last Updated:** [Date]

## Core Product
[One paragraph description]

## Target Customer
**Primary:** [Description]
**Secondary:** [Description]

## Pricing
| Tier | Price | Target |
|------|-------|--------|
| [Name] | $X/mo | [Who] |

## Key Differentiators
1. **[Name]**: [Why it matters]
2. **[Name]**: [Why it matters]
3. **[Name]**: [Why it matters]

## Against Competitors
- vs [Comp A]: We're better because [reason]
- vs [Comp B]: We're better because [reason]

## Current Priorities
1. [Priority 1]
2. [Priority 2]
3. [Priority 3]

## Key Metrics to Hit
- [Metric 1]: [Target]
- [Metric 2]: [Target]
```

### Decision Log Template
```markdown
# [Product Name] Decision Log

## 2024-03-15: [Decision Title]
**Context:** [Why this came up]
**Options Considered:**
1. [Option A]: [Pros/cons]
2. [Option B]: [Pros/cons]
**Decision:** [What we chose]
**Rationale:** [Why]
**Impact:** [What changes]

## 2024-03-01: [Decision Title]
...
```

---

## Minimum Viable Knowledge Base

If you're short on time, these 3 documents are enough to start:

1. **Master Strategy** - Covers product, market, pricing, tech
2. **Competitive Intelligence** - Market context and positioning
3. **Quick Reference** - Fast access to key facts

You can always add more documents later as conversations reveal gaps.

---

## Testing Your Knowledge Base

After setup, test with these prompts:

**Test 1: Recall**
"What are our three main differentiators?"

**Test 2: Application**
"Based on our competitive analysis, how should we respond if [Competitor] drops their prices by 50%?"

**Test 3: Synthesis**
"Write a one-paragraph pitch for our product targeting [persona]."

If answers are off, check:
- Are documents properly uploaded?
- Is custom instructions set?
- Are documents clear and unambiguous?

---
