---
name: react
description: React and Next.js performance optimization best practices. Use when reviewing React components, optimizing performance, fixing waterfalls, reducing bundle size, or improving rendering efficiency. Contains 70 rules across 8 priority-ranked categories from Vercel Engineering.
---

# React Performance Best Practices

Comprehensive performance optimization guide for React and Next.js applications. Contains 70 rules across 8 categories, prioritized by impact.

**Source:** Adapted from [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills)

## When to Apply

Reference these guidelines when:

- Writing new React components or Next.js pages
- Implementing data fetching (client or server-side)
- Reviewing code for performance issues
- Refactoring existing React/Next.js code
- Optimizing bundle size or load times
- Improving Core Web Vitals (LCP, TTI, FID)

## Rule Categories by Priority

| Priority | Category                  | Impact      | Prefix       | Rules |
| -------- | ------------------------- | ----------- | ------------ | ----- |
| 1        | Eliminating Waterfalls    | CRITICAL    | `async-`     | 6     |
| 2        | Bundle Size Optimization  | CRITICAL    | `bundle-`    | 5     |
| 3        | Server-Side Performance   | HIGH        | `server-`    | 11    |
| 4        | Client-Side Data Fetching | MEDIUM-HIGH | `client-`    | 4     |
| 5        | Re-render Optimization    | MEDIUM      | `rerender-`  | 15    |
| 6        | Rendering Performance     | MEDIUM      | `rendering-` | 11    |
| 7        | JavaScript Performance    | LOW-MEDIUM  | `js-`        | 14    |
| 8        | Advanced Patterns         | LOW         | `advanced-`  | 4     |

## Quick Reference

### 1. Eliminating Waterfalls (CRITICAL)

Waterfalls are the #1 performance killer. Each sequential await adds full network latency.

| Rule                                 | Description                                    |
| ------------------------------------ | ---------------------------------------------- |
| `async-cheap-condition-before-await` | Check sync conditions before awaiting flags    |
| `async-defer-await`                  | Move await into branches where actually used   |
| `async-parallel`                     | Use Promise.all() for independent operations   |
| `async-dependencies`                 | Use better-all for partial dependencies        |
| `async-api-routes`                   | Start promises early, await late in API routes |
| `async-suspense-boundaries`          | Use Suspense to stream content                 |

### 2. Bundle Size Optimization (CRITICAL)

Reducing initial bundle size improves Time to Interactive and Largest Contentful Paint.

| Rule                       | Description                                 |
| -------------------------- | ------------------------------------------- |
| `bundle-barrel-imports`    | Import directly, avoid barrel files         |
| `bundle-dynamic-imports`   | Use next/dynamic for heavy components       |
| `bundle-defer-third-party` | Load analytics/logging after hydration      |
| `bundle-conditional`       | Load modules only when feature is activated |
| `bundle-preload`           | Preload on hover/focus for perceived speed  |

### 3. Server-Side Performance (HIGH)

Optimizing server-side rendering and data fetching eliminates server-side waterfalls.

| Rule                              | Description                                          |
| --------------------------------- | ---------------------------------------------------- |
| `server-auth-actions`             | Authenticate server actions like API routes          |
| `server-cache-react`              | Use React.cache() for per-request deduplication      |
| `server-cache-lru`                | Use LRU cache for cross-request caching              |
| `server-cache-components`         | Use 'use cache' directive with PPR (ClaudeFast-only) |
| `server-dedup-props`              | Avoid duplicate serialization in RSC props           |
| `server-hoist-static-io`          | Hoist static I/O (fonts, logos) to module level      |
| `server-no-shared-module-state`   | Avoid module-level mutable request state in RSC/SSR  |
| `server-serialization`            | Minimize data passed to client components            |
| `server-parallel-fetching`        | Restructure components to parallelize fetches        |
| `server-parallel-nested-fetching` | Chain nested fetches per item in Promise.all         |
| `server-after-nonblocking`        | Use after() for non-blocking operations              |

### 4. Client-Side Data Fetching (MEDIUM-HIGH)

Automatic deduplication and efficient data fetching patterns.

| Rule                             | Description                                 |
| -------------------------------- | ------------------------------------------- |
| `client-swr-dedup`               | Use SWR for automatic request deduplication |
| `client-event-listeners`         | Deduplicate global event listeners          |
| `client-passive-event-listeners` | Use passive listeners for scroll/touch      |
| `client-localstorage-schema`     | Schema for localStorage with versioning     |

### 5. Re-render Optimization (MEDIUM)

Reducing unnecessary re-renders minimizes wasted computation.

| Rule                                 | Description                                      |
| ------------------------------------ | ------------------------------------------------ |
| `rerender-defer-reads`               | Don't subscribe to state only used in callbacks  |
| `rerender-memo`                      | Extract expensive work into memoized components  |
| `rerender-memo-with-default-value`   | Hoist default non-primitive props to constants   |
| `rerender-dependencies`              | Use primitive dependencies in effects            |
| `rerender-derived-state`             | Subscribe to derived booleans, not raw values    |
| `rerender-derived-state-no-effect`   | Derive state during render, not in effects       |
| `rerender-functional-setstate`       | Use functional setState for stable callbacks     |
| `rerender-lazy-state-init`           | Pass function to useState for expensive values   |
| `rerender-simple-expression-in-memo` | Don't memo simple primitive expressions          |
| `rerender-split-combined-hooks`      | Split hooks with independent dependencies        |
| `rerender-move-effect-to-event`      | Put interaction logic in event handlers          |
| `rerender-transitions`               | Use startTransition for non-urgent updates       |
| `rerender-use-deferred-value`        | Defer expensive renders to keep input responsive |
| `rerender-use-ref-transient-values`  | Use refs for transient frequent values           |
| `rerender-no-inline-components`      | Don't define components inside components        |

### 6. Rendering Performance (MEDIUM)

Optimizing the rendering process reduces browser work.

| Rule                                   | Description                              |
| -------------------------------------- | ---------------------------------------- |
| `rendering-animate-svg-wrapper`        | Animate div wrapper, not SVG element     |
| `rendering-content-visibility`         | Use content-visibility for long lists    |
| `rendering-hoist-jsx`                  | Extract static JSX outside components    |
| `rendering-svg-precision`              | Reduce SVG coordinate precision          |
| `rendering-hydration-no-flicker`       | Use inline script for client-only data   |
| `rendering-hydration-suppress-warning` | Suppress expected hydration mismatches   |
| `rendering-activity`                   | Use Activity component for show/hide     |
| `rendering-conditional-render`         | Use ternary, not && for conditionals     |
| `rendering-usetransition-loading`      | Prefer useTransition for loading state   |
| `rendering-resource-hints`             | Use React DOM resource hints for preload |
| `rendering-script-defer-async`         | Use defer or async on script tags        |

### 7. JavaScript Performance (LOW-MEDIUM)

Micro-optimizations for hot paths can add up to meaningful improvements.

| Rule                        | Description                                    |
| --------------------------- | ---------------------------------------------- |
| `js-set-map-lookups`        | Use Set/Map for O(1) lookups                   |
| `js-batch-dom-css`          | Group CSS changes via classes or cssText       |
| `js-index-maps`             | Build Map for repeated lookups                 |
| `js-cache-property-access`  | Cache object properties in loops               |
| `js-cache-function-results` | Cache function results in module-level Map     |
| `js-cache-storage`          | Cache localStorage/sessionStorage reads        |
| `js-combine-iterations`     | Combine multiple filter/map into one loop      |
| `js-length-check-first`     | Check array length before expensive comparison |
| `js-early-exit`             | Return early from functions                    |
| `js-hoist-regexp`           | Hoist RegExp creation outside loops            |
| `js-min-max-loop`           | Use loop for min/max instead of sort           |
| `js-tosorted-immutable`     | Use toSorted() for immutability                |
| `js-flatmap-filter`         | Use flatMap to map and filter in one pass      |
| `js-request-idle-callback`  | Defer non-critical work to browser idle time   |

### 8. Advanced Patterns (LOW)

Advanced patterns for specific cases requiring careful implementation.

| Rule                          | Description                                     |
| ----------------------------- | ----------------------------------------------- |
| `advanced-effect-event-deps`  | Don't put useEffectEvent results in effect deps |
| `advanced-event-handler-refs` | Store event handlers in refs                    |
| `advanced-init-once`          | Initialize app once per app load, not per mount |
| `advanced-use-latest`         | useLatest for stable callback refs              |

## How to Use

Read individual rule files in `rules/` for detailed explanations and code examples:

```
rules/async-parallel.md       # Promise.all() for independent operations
rules/bundle-barrel-imports.md # Avoiding barrel file imports
rules/_sections.md            # Section metadata and descriptions
```

Each rule file contains:

- Brief explanation of why it matters
- Incorrect code example with explanation
- Correct code example with explanation
- Additional context and references

## File Structure

```
.Codex/skills/react/
├── SKILL.md          # This overview document
└── rules/
    ├── _sections.md  # Section definitions and priorities
    ├── _template.md  # Template for adding new rules
    ├── async-*.md    # Waterfall elimination rules (6)
    ├── bundle-*.md   # Bundle optimization rules (5)
    ├── server-*.md   # Server-side performance rules (11)
    ├── client-*.md   # Client-side data fetching rules (4)
    ├── rerender-*.md # Re-render optimization rules (15)
    ├── rendering-*.md# Rendering performance rules (11)
    ├── js-*.md       # JavaScript performance rules (14)
    └── advanced-*.md # Advanced pattern rules (4)
```

## React Compiler Note

If your project has React Compiler enabled, manual memoization with `memo()` and `useMemo()` is often unnecessary. The compiler handles these optimizations automatically.

## Upstream Sync Process

This skill is adapted from `vercel-labs/agent-skills` (the `react-best-practices` skill). Our structure differs from source: we use a flat `rules/` folder with our own `SKILL.md` index instead of their `AGENTS.md` compiled output. We also keep one extra rule (`server-cache-components`) not in the upstream.

### How to check for updates

```bash
# 1. List source rule files
gh api repos/vercel-labs/agent-skills/contents/skills/react-best-practices/rules \
  --jq '.[].name' | sort > /tmp/upstream-rules.txt

# 2. List our rule files
ls .Codex/skills/react/rules/*.md | xargs -I{} basename {} | sort > /tmp/local-rules.txt

# 3. Diff to find new/removed rules
diff /tmp/local-rules.txt /tmp/upstream-rules.txt
```

### How to pull a new rule

```bash
# Fetch a single rule file content
gh api -H "Accept: application/vnd.github.raw+json" \
  "repos/vercel-labs/agent-skills/contents/skills/react-best-practices/rules/<rule-name>.md"
```

Save the output to `rules/<rule-name>.md`, then update this SKILL.md:

1. Increment the rule count in the category table
2. Add a row in the matching Quick Reference section
3. Update the total in the description frontmatter

### How to check for content changes to existing rules

```bash
# Fetch upstream version and diff against local
gh api -H "Accept: application/vnd.github.raw+json" \
  "repos/vercel-labs/agent-skills/contents/skills/react-best-practices/rules/<rule-name>.md" \
  | diff - .Codex/skills/react/rules/<rule-name>.md
```

### Sync log

| Date       | Upstream rules | Our rules | Delta | Notes                                             |
| ---------- | -------------- | --------- | ----- | ------------------------------------------------- |
| 2025-01    | 48             | 48        | 0     | Initial adaptation from source                    |
| 2026-04-08 | 69             | 70        | +1    | Pulled 22 new rules; kept server-cache-components |

---

_Adapted from Vercel Engineering - January 2025. Last synced: April 2026._
