---
name: idea-to-product
description: "Complete idea-to-product workflow for online SaaS businesses: idea extraction, competitor analysis, GTM strategy, starter kit transformation, and expert co-founder creation. Supports fresh ideas or mid-process entry points."
---

# Idea-to-Product Development System

**Purpose:** Formalized workflow for developing online SaaS/digital product ideas from initial concept through implementation-ready documentation, optimized for AI-assisted development using starter kits.

**Target Use Cases:**
- SaaS applications (subscription-based)
- Growth and marketing tools
- Developer tools and utilities
- Information products with automation
- Semi-automated services (productized services)

---

## When to Use This Skill

Invoke this skill when:
- Starting with a new product idea that needs validation and development planning
- Already have strategy documents but need competitor analysis
- Need to define go-to-market strategy and target segments
- Have complete research and need starter kit transformation analysis
- Want to create an expert co-founder project from existing documentation
- Need viability scoring for an idea before committing development time

---

## Workflow Overview

```
Phase 1: Idea Extraction (Claude Desktop)
    ↓
Phase 2: Competitor Analysis (Claude Desktop)
    ↓
Phase 3: GTM Strategy (Claude Desktop)
    ↓
Phase 4: Starter Kit Selection (Claude Desktop/Code)
    ↓
Phase 5: Transformation Analysis (Claude Code)
    ↓
Phase 6: Expert Co-founder Creation (Claude Desktop)
```

**Total Timeline:** 3-5 hours for complete workflow (varies by idea complexity)

---

## Entry Points

### Starting Fresh (No Documents)
**Start at:** Phase 1 - Idea Extraction
**Files to load:** `phase-1-idea-extraction/interview-framework.md`

### Have Strategy Document, Need Competitor Analysis
**Start at:** Phase 2 - Competitor Analysis
**Files to load:** `phase-2-competitor-analysis/competitor-brief-template.md`

### Have Competitors Analyzed, Need GTM Strategy
**Start at:** Phase 3 - GTM Strategy
**Files to load:** `phase-3-gtm-strategy/gtm-playbook.md`

### Have Research, Need Starter Kit Analysis
**Start at:** Phase 4 - Starter Kit Selection
**Files to load:** `phase-4-starter-kit-selection/requirements-mapping.md`

### Have Everything, Need Implementation Plan
**Start at:** Phase 5 - Transformation Analysis
**Files to load:** `phase-5-transformation-analysis/master-prompt-template.md`

### Need to Create Expert Co-founder Project
**Start at:** Phase 6 - Expert Co-founder Creation
**Files to load:** `phase-6-expert-cofounder/project-setup-prompt.md`

---

## Phase Summary

### Phase 1: Idea Extraction (30-60 minutes)
**Location:** Claude Desktop
**Output:** Master Strategy Document

Interview-driven extraction of your product idea covering:
- Core value proposition and target market
- Revenue model and pricing strategy
- Technical requirements and constraints
- Go-to-market approach
- Viability scoring with weighted matrix

**Key Files:**
- `interview-framework.md` - 25 core questions + optional deep-dives
- `strategy-document-template.md` - Output format for master strategy
- `viability-scorecard.md` - Weighted scoring matrix (7 factors)

### Phase 2: Competitor Analysis (30-60 minutes)
**Location:** Claude Desktop
**Output:** 2-5 Competitor Briefs + Competitive Intelligence Synthesis

Deep research on direct competitors covering:
- Feature comparison and pricing
- Strengths and weaknesses
- Market positioning
- How to win against each competitor

**Key Files:**
- `competitor-brief-template.md` - Individual competitor analysis
- `competitive-intelligence.md` - Synthesis across all competitors + How to Win playbooks
- `market-positioning.md` - Your differentiation strategy

### Phase 3: GTM Strategy (30-45 minutes)
**Location:** Claude Desktop
**Output:** GTM Playbook + Target Segments

Comprehensive go-to-market planning covering:
- Launch phases (Beta → Soft → Full)
- Channel strategy and tactics
- Target customer segments with personas
- Success metrics by phase
- Risk assessment

**Key Files:**
- `gtm-playbook.md` - Complete launch strategy and channel tactics
- `target-segments.md` - Detailed customer personas with messaging

### Phase 4: Starter Kit Selection (15-30 minutes)
**Location:** Claude Desktop or Code
**Output:** Selected Starter Kit + Requirements Mapping

Match your idea requirements to available starter kits:
- Feature coverage analysis
- Gap identification
- Modification scope estimation

**Key Files:**
- `requirements-mapping.md` - Match needs to kit capabilities
- `kit-evaluation-criteria.md` - Scoring rubric for selection

### Phase 5: Transformation Analysis (60-90 minutes)
**Location:** Claude Code
**Output:** Comprehensive Transformation Report + Implementation Plan

7-domain deep analysis of starter kit transformation:
1. Authentication & Multi-tenancy
2. Payment Processing (Polar)
3. Database Architecture
4. Background Jobs
5. UI Components
6. Integrations
7. Gap Synthesis

**Key Files:**
- `master-prompt-template.md` - Complete analysis prompt
- `domain-*.md` - Individual domain deep-dive prompts

### Phase 6: Expert Co-founder Creation (15-30 minutes)
**Location:** Claude Desktop
**Output:** Claude Desktop Project as Expert Co-founder

Create a project with all documents as knowledge base:
- Project configuration
- Document organization
- Use case examples

**Key Files:**
- `project-setup-prompt.md` - How to create the project
- `knowledge-base-structure.md` - Document organization guide

---

## Best Practices (Baked In)

### Payment Processing: Polar
- Industry standard for indie SaaS
- Better terms than Stripe for small creators
- Supports subscriptions, one-time, and usage-based billing
- All templates assume Polar integration

### Hosting: VPS (Coolify/Dokku)
- Becoming standard for cost-effective deployment
- Better control than serverless for always-on features
- Templates assume VPS deployment with Docker
- Background jobs use node-cron (not Edge Functions)

### Development Approach: AI-Assisted
- Heavy reliance on Claude Code for implementation
- Starter kit as foundation (not from scratch)
- Clear documentation enables effective AI delegation
- Atomic tasks suitable for AI execution

---

## Document Naming Conventions

All output documents should follow this naming pattern:

```
[project-slug]/
├── strategy/
│   ├── master-strategy.md
│   └── viability-score.md
├── competitors/
│   ├── competitor-[name]-brief.md
│   └── competitive-intelligence.md
├── analysis/
│   ├── transformation-report.md
│   ├── domain-[name]-analysis.md
│   └── implementation-checklist.md
└── context/
    ├── api-[service]-guide.md
    └── decision-[topic].md
```

---

## Quick Navigation

| Task | Phase | File to Load |
|------|-------|--------------|
| New idea validation | 1 | `interview-framework.md` |
| Score idea viability | 1 | `viability-scorecard.md` |
| Analyze competitor | 2 | `competitor-brief-template.md` |
| Synthesize competition | 2 | `competitive-intelligence.md` |
| How to win positioning | 2 | `competitive-intelligence.md` (How to Win section) |
| GTM launch strategy | 3 | `gtm-playbook.md` |
| Target customer personas | 3 | `target-segments.md` |
| Select starter kit | 4 | `requirements-mapping.md` |
| Full transformation analysis | 5 | `master-prompt-template.md` |
| Auth/multitenancy deep-dive | 5 | `domain-1-auth-multitenancy.md` |
| Payment integration | 5 | `domain-2-payments.md` |
| Database design | 5 | `domain-3-database.md` |
| Background jobs | 5 | `domain-4-background-jobs.md` |
| UI components | 5 | `domain-5-ui-components.md` |
| Third-party integrations | 5 | `domain-6-integrations.md` |
| Gap analysis | 5 | `domain-7-gap-synthesis.md` |
| Create expert project | 6 | `project-setup-prompt.md` |
| API integration planning | Support | `api-integration-template.md` |
| Capacity/hiring planning | Support | `capacity-planning.md` |
| Pricing strategy | Support | `monetization-models.md` |
| Unit economics | Support | `unit-economics-template.md` |
| Risk assessment | Support | `risk-assessment-template.md` |
| Success metrics | Support | `success-metrics-template.md` |
| Architecture decisions | Support | `architecture-decision-template.md` |

---

## Success Criteria

A completed workflow produces:

1. **Master Strategy Document** - Complete business and technical overview
2. **Viability Score** - Weighted assessment (aim for 70+ out of 100)
3. **Competitor Briefs** - 2-5 detailed analyses with How to Win playbooks
4. **Competitive Intelligence** - Synthesis with differentiation strategy
5. **GTM Playbook** - Launch strategy with channel tactics and phased approach
6. **Target Segments** - Detailed customer personas with messaging
7. **Risk Assessment** - Categorized risks with mitigation strategies
8. **Success Metrics** - Phase-by-phase KPIs and milestones
9. **Transformation Report** - Implementation-ready technical plan
10. **Implementation Checklist** - Atomic tasks for development
11. **Expert Co-founder Project** - Claude Desktop project for ongoing support

---

## Version Information

**Last Updated:** 2025-11-22
**Workflow Version:** 2.0

**v2.0 Changes:**
- Added Phase 3: GTM Strategy (gtm-playbook.md, target-segments.md)
- Renumbered phases 3-5 to 4-6
- Enhanced competitive-intelligence.md with "How to Win" format
- Added supporting templates: risk-assessment, success-metrics, architecture-decision
- Increased total deliverables from 7 to 11

---
