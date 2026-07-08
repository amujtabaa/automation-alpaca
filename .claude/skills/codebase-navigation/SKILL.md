---
name: codebase-navigation
description: Codebase structure and efficient navigation tips
---

# Directory Structure

## 🏗️ Claude Fast Framework Organization

```
.claude/
├── agents/                                     # Sub-agent configurations (12 specialists)
│   ├── backend-engineer.md                     # Server actions, APIs, database operations
│   ├── code-simplifier.md                      # Code simplification, refactoring, maintainability
│   ├── content-writer.md                       # Content creation: documentation, blogs, technical writing
│   ├── debugger-detective.md                   # Bug investigation, root cause analysis
│   ├── deep-researcher.md                      # External research, evidence-based decisions
│   ├── frontend-specialist.md                  # React, UI, components, responsive design
│   ├── master-orchestrator.md                  # Strategic coordination, session planning
│   ├── performance-optimizer.md                # Core Web Vitals, optimization strategies
│   ├── quality-engineer.md                     # Testing, QA automation, quality assurance
│   ├── security-auditor.md                     # Security reviews, compliance, vulnerability assessment
│   ├── session-librarian.md                    # Git commits, session completion, archival
│   └── supabase-specialist.md                  # Database, RLS, real-time, Edge Functions
│
├── tasks/                                      # Session-based task management
│   ├── session-template.md                     # Session file template
│   ├── session-current.md                      # Active session (if any)
│   └── archive/                                # Completed sessions
│
└── skills/                                     # Lazy-loaded skills (invoke via Skill tool)
    ├── git-commits/
    ├── session-management/
    ├── sub-agent-invocation/
    └── codebase-navigation/                    # This skill
```

## 📁 Root Configuration

```
/CLAUDE.md                   # Central AI configuration - auto-loaded base
```

## 📋 Session File Management

Session files serve as the single source of truth for development work:

- **session-template.md**: Template for creating new sessions
- **session-current.md**: Active session with ongoing work
- **session-[number].md**: Archived completed sessions

Each session file contains:

- User request and success criteria
- Task breakdown with TodoWrite synchronization
- Agent work sections and progress updates
- Research findings and architectural decisions
- Quality gates and validation checkpoints

## 🎯 Agent Specializations

### Core Development

- **Frontend**: React, UI/UX, components
- **Backend**: APIs, server actions, middleware
- **Database**: Supabase, RLS, migrations

### Quality & Performance

- **Security**: Vulnerability assessment, compliance
- **Quality**: Testing strategies, QA automation
- **Performance**: Optimization, Core Web Vitals
- **Code Simplifier**: Refactoring, clarity, maintainability

### Specialized Operations

- **Debugging**: Root cause analysis, issue investigation
- **Research**: External documentation, best practices
- **Content**: Marketing copy, blog posts, documentation

### Orchestration

- **Master Orchestrator**: Session planning and strategic analysis
- **Session Librarian**: Git commits, session archival, and completion

---

This structure supports the session-based workflow where all task and development management happens through session files in `.claude/tasks/`.
