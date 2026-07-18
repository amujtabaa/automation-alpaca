# Blog Post Frontmatter Template

Copy this template when creating new blog posts.

## Required Fields

```yaml
---
menu: "Short Title"
title: "Claude Code Feature: Descriptive SEO Title"
description: "Your description (140 chars max, 'Claude Fast | ' auto-added)."
publishedAt: "YYYY-MM-DD"
---
```

## With Optional SEO Override

```yaml
---
menu: "Short Title"
title: "Claude Code Feature: Full H1 Title for Page"
seoTitle: "Custom Google Title (max 60 chars)"
description: "Your description (140 chars max, 'Claude Fast | ' auto-added)."
publishedAt: "YYYY-MM-DD"
---
```

---

## Field Reference

| Field         | Required | Max Length | Purpose                                        |
| ------------- | -------- | ---------- | ---------------------------------------------- |
| `menu`        | Yes      | ~30 chars  | Sidebar navigation (keep short)                |
| `title`       | Yes      | ~80 chars  | H1 on page + search title (if under 60 chars)  |
| `seoTitle`    | No       | 60 chars   | Use when title exceeds 60 chars for search     |
| `description` | Yes\*    | 140 chars  | Meta description ("Claude Fast \| " prepended) |
| `publishedAt` | Yes      | -          | Date in YYYY-MM-DD format                      |
| `icon`        | No       | -          | Sidebar icon (rarely used)                     |
| `index`       | No       | -          | Set true for category landing pages            |
| `mirror`      | No       | -          | Path to mirror content from                    |

\*Description is technically optional but should always be provided for SEO.

---

## SEO Title Logic

Priority order for what appears in Google/browser tab:

1. `seoTitle` (if present) - used exactly as written
2. `title` - used directly as meta title
3. `menu` with breadcrumbs - fallback (rarely happens)

**No site suffix is added.** You have the full 60 characters for seoTitle.

---

## Character Limit Guidelines

### Title Field (80 chars max)

- **Under 60 chars**: Safe for Google display
- **60-80 chars**: May truncate in search results
- **Over 80 chars**: Needs shortening

**IMPORTANT**: Always include "Claude Code" in the title for SEO context.

### Description (140 chars in frontmatter)

- **Under 120 chars**: Safe for all devices (becomes ~135 with prefix)
- **120-140 chars**: Displays on desktop, may truncate on mobile
- **Over 140 chars**: Will be truncated by Google

**Note**: "Claude Fast | " (15 chars) is auto-prepended, so 140 chars becomes ~155 total.

---

## Examples

### Standard Blog Post

```yaml
---
menu: "Task Management"
title: "Claude Code Task Management: Native Multi-Session Coordination"
description: "Anthropic's native task system with dependencies, blockers, and CLAUDE_CODE_TASK_LIST_ID for multi-session sync."
publishedAt: "2026-01-23"
---
```

- Sidebar shows: "Task Management"
- Google title: "Claude Code Task Management: Native Multi-Session Coordination"
- Google description: "Claude Fast | Anthropic's native task system..." (auto-prefixed)

### With SEO Override

```yaml
---
menu: "Hooks"
title: "Complete Guide to Claude Code Hooks: Automate Your AI Workflow"
seoTitle: "Claude Code Hooks Guide 2026: Automation Tutorial"
description: "Master Claude Code hooks for automated workflows. Pre/post hooks, permission control, and task enforcement."
publishedAt: "2026-01-26"
---
```

- Sidebar shows: "Hooks"
- H1 on page: "Complete Guide to Claude Code Hooks: Automate Your AI Workflow"
- Google title: "Claude Code Hooks Guide 2026: Automation Tutorial" (49 chars)
- Google description: "Claude Fast | Master Claude Code hooks..." (auto-prefixed)

### Category Index Page

```yaml
---
menu: "Mechanics"
title: "Claude Code Mechanics: Deep Dive into How It Works"
description: "Understand Claude Code internals: context management, skill loading, agent coordination."
publishedAt: "2025-08-23"
index: true
---
```

---

## Common Mistakes

1. **Description too long**: Keep under 140 chars (prefix adds 15 more)
2. **Missing "Claude Code"**: Title should contain "Claude Code" for SEO
3. **Wrong date format**: Use YYYY-MM-DD exactly
4. **Missing publishedAt**: Always include for article schema
5. **Using removed fields**: Don't use `author`, `tags`, `readingTime`, `modifiedAt`

---

## Validation Checklist

Before publishing, verify:

- [ ] `menu` is short enough for sidebar (~30 chars)
- [ ] `title` includes "Claude Code" and is under 80 chars
- [ ] `seoTitle` (if used) is under 60 chars
- [ ] `description` is under 140 chars (prefix auto-added)
- [ ] `publishedAt` is valid YYYY-MM-DD date
- [ ] No unused fields (author, tags, readingTime, modifiedAt)
