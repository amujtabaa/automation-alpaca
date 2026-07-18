# Risk Assessment Template

**Purpose:** Systematically identify, assess, and plan mitigation for project risks across market, technical, competitive, and operational dimensions.

---

## Risk Assessment Prompt (Copy to Claude Desktop)

```
Based on our Master Strategy Document, Competitive Intelligence, and Technical Architecture, help me create a comprehensive Risk Assessment. Categorize risks as:

1. Critical (blocking/existential)
2. High (significant impact)
3. Medium (manageable)
4. Low (acceptable)

For each risk, provide:
- Description and trigger conditions
- Probability (1-5)
- Impact (1-5)
- Risk score (P × I)
- Specific mitigation strategies
- Contingency plans

Focus on risks specific to this product and market, not generic startup risks.
```

---

## Risk Assessment Template

```markdown
# Risk Assessment: [Product Name]

**Date:** [Date]
**Version:** [X]
**Risk Owner:** [Your name]
**Next Review:** [Date]

---

## Risk Summary

| Risk Level | Count | Top Concerns |
|------------|-------|--------------|
| 🔴 Critical | [X] | [Brief list] |
| 🟠 High | [X] | [Brief list] |
| 🟡 Medium | [X] | [Brief list] |
| 🟢 Low | [X] | [Brief list] |

**Overall Risk Profile:** [Conservative/Moderate/Aggressive]

---

## Risk Matrix

```
        │ LOW IMPACT │ MED IMPACT │ HIGH IMPACT
────────┼────────────┼────────────┼────────────
HIGH    │   Medium   │    High    │  Critical
PROB    │            │            │
────────┼────────────┼────────────┼────────────
MED     │    Low     │   Medium   │    High
PROB    │            │            │
────────┼────────────┼────────────┼────────────
LOW     │    Low     │    Low     │   Medium
PROB    │            │            │
```

---

## 1. Critical Risks (Must Address Immediately)

### Risk C1: [Risk Name]

**Category:** [Market/Technical/Competitive/Regulatory/Operational]

**Description:**
[Detailed description of the risk and what could trigger it]

**Risk Assessment:**
- Probability: [1-5] - [Low/Medium/High]
- Impact: [1-5] - [Low/Medium/High]
- Risk Score: [P × I]
- Timeline: [When this could occur]

**Why It's Critical:**
[Explain why this is blocking or existential]

**Trigger Indicators:**
- [Early warning sign 1]
- [Early warning sign 2]

**Mitigation Strategy:**

| Action | Owner | Deadline | Status |
|--------|-------|----------|--------|
| [Action 1] | [Name] | [Date] | [ ] |
| [Action 2] | [Name] | [Date] | [ ] |
| [Action 3] | [Name] | [Date] | [ ] |

**Contingency Plan:**
If mitigation fails: [What we do instead]

**Residual Risk:** [Risk level after mitigation]

---

### Risk C2: [Risk Name]

[Same structure]

---

## 2. High Risks (Monitor Closely)

### Risk H1: [Risk Name]

**Category:** [Market/Technical/Competitive/Regulatory/Operational]

**Description:**
[Detailed description]

**Risk Assessment:**
- Probability: [1-5]
- Impact: [1-5]
- Risk Score: [P × I]

**Mitigation Strategy:**

| Action | Owner | Deadline | Status |
|--------|-------|----------|--------|
| [Action 1] | [Name] | [Date] | [ ] |
| [Action 2] | [Name] | [Date] | [ ] |

**Contingency Plan:**
[Backup approach]

---

### Risk H2: [Risk Name]

[Same structure]

---

## 3. Medium Risks (Have Plan Ready)

### Risk M1: [Risk Name]

**Category:** [Category]

**Description:**
[Brief description]

**Risk Assessment:**
- Probability: [1-5]
- Impact: [1-5]
- Risk Score: [P × I]

**Mitigation:**
[Key actions]

---

### Risk M2: [Risk Name]

[Same structure]

---

## 4. Low Risks (Acceptable)

### Risk L1: [Risk Name]

**Description:** [Brief]
**Probability:** [1-5] | **Impact:** [1-5]
**Why Acceptable:** [Reasoning]

---

## Risk Categories Detail

### Market Risks

| ID | Risk | P | I | Score | Mitigation |
|----|------|---|---|-------|------------|
| MR1 | [Market doesn't exist] | [X] | [X] | [X] | [Strategy] |
| MR2 | [Market too small] | [X] | [X] | [X] | [Strategy] |
| MR3 | [Timing wrong] | [X] | [X] | [X] | [Strategy] |
| MR4 | [Customer won't pay] | [X] | [X] | [X] | [Strategy] |

### Technical Risks

| ID | Risk | P | I | Score | Mitigation |
|----|------|---|---|-------|------------|
| TR1 | [API access denied] | [X] | [X] | [X] | [Strategy] |
| TR2 | [Scaling issues] | [X] | [X] | [X] | [Strategy] |
| TR3 | [Security breach] | [X] | [X] | [X] | [Strategy] |
| TR4 | [Technical debt] | [X] | [X] | [X] | [Strategy] |

### Competitive Risks

| ID | Risk | P | I | Score | Mitigation |
|----|------|---|---|-------|------------|
| CR1 | [Incumbent responds] | [X] | [X] | [X] | [Strategy] |
| CR2 | [New entrant] | [X] | [X] | [X] | [Strategy] |
| CR3 | [Price war] | [X] | [X] | [X] | [Strategy] |
| CR4 | [Feature copied] | [X] | [X] | [X] | [Strategy] |

### Operational Risks

| ID | Risk | P | I | Score | Mitigation |
|----|------|---|---|-------|------------|
| OR1 | [Founder burnout] | [X] | [X] | [X] | [Strategy] |
| OR2 | [Cash flow] | [X] | [X] | [X] | [Strategy] |
| OR3 | [Key dependency] | [X] | [X] | [X] | [Strategy] |
| OR4 | [Support overload] | [X] | [X] | [X] | [Strategy] |

### Regulatory/Legal Risks

| ID | Risk | P | I | Score | Mitigation |
|----|------|---|---|-------|------------|
| RR1 | [Platform ToS change] | [X] | [X] | [X] | [Strategy] |
| RR2 | [Data privacy] | [X] | [X] | [X] | [Strategy] |
| RR3 | [IP issues] | [X] | [X] | [X] | [Strategy] |

---

## Competitive Response Scenarios

### Scenario 1: [Competitor] Adds Your Key Feature

**Probability:** [X]%
**Timeline:** [When this could happen]

**Impact Assessment:**
- [Impact on differentiation]
- [Impact on customers]
- [Impact on growth]

**Response Plan:**
1. [Immediate action]
2. [Short-term response]
3. [Long-term strategy]

### Scenario 2: New Well-Funded Competitor Enters

**Probability:** [X]%
**Timeline:** [When this could happen]

**Impact Assessment:**
[Details]

**Response Plan:**
1. [Immediate action]
2. [Short-term response]
3. [Long-term strategy]

### Scenario 3: Price War Initiated

**Probability:** [X]%
**Timeline:** [When this could happen]

**Impact Assessment:**
[Details]

**Response Plan:**
1. [Immediate action]
2. [Short-term response]
3. [Long-term strategy]

---

## Risk Monitoring Plan

### Weekly Monitoring

| Risk | Metric to Track | Warning Threshold | Action if Triggered |
|------|-----------------|-------------------|---------------------|
| [Risk 1] | [Metric] | [Threshold] | [Action] |
| [Risk 2] | [Metric] | [Threshold] | [Action] |

### Monthly Review

- [ ] Review all risk scores
- [ ] Update probabilities based on new information
- [ ] Add new risks identified
- [ ] Close resolved risks
- [ ] Update mitigation progress

### Quarterly Assessment

- [ ] Full risk reassessment
- [ ] Competitive landscape review
- [ ] Technical risk audit
- [ ] Update contingency plans

---

## Risk Response Protocols

### If Critical Risk Materializes

1. **Immediate (Hour 1):**
   - [Action 1]
   - [Action 2]

2. **Short-term (Day 1):**
   - [Action 1]
   - [Action 2]

3. **Recovery (Week 1):**
   - [Action 1]
   - [Action 2]

### Communication Plan

**Internal:**
- [Who to notify]
- [How to communicate]

**External (if customer-facing):**
- [Customer communication]
- [Public statement if needed]

---

## Key Takeaways

### Top 3 Risks to Address Now
1. [Risk and immediate action]
2. [Risk and immediate action]
3. [Risk and immediate action]

### Acceptable Risks
[Risks we're choosing to accept and why]

### Risk Appetite Statement
[Our overall approach to risk in this venture]

---

**Assessment Author:** [Your name]
**Last Updated:** [Date]
**Next Review:** [Date]
```

---

## Quick Risk Checklist

Use this for rapid risk identification:

```markdown
## Quick Risk Scan

### Market
- [ ] Is this a proven market?
- [ ] Are people paying for solutions?
- [ ] Is the market growing?
- [ ] Can we reach customers affordably?

### Technical
- [ ] Do we have API/platform access?
- [ ] Can we build the MVP in time?
- [ ] Will it scale?
- [ ] Are there security concerns?

### Competitive
- [ ] Who's the biggest threat?
- [ ] Can they copy us quickly?
- [ ] Do we have defensible advantages?
- [ ] What if a big player enters?

### Operational
- [ ] Do we have runway?
- [ ] Can we support customers?
- [ ] What are our dependencies?
- [ ] What about burnout?

### Regulatory
- [ ] Platform ToS compliant?
- [ ] Data privacy handled?
- [ ] Any IP concerns?
```

---
