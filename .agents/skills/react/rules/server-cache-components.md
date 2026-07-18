---
title: Next.js Cache Components with Partial Prerendering
impact: HIGH
impactDescription: enables component-level caching with PPR for optimal static/dynamic composition
tags: server, cache, nextjs, ppr, use-cache, cacheLife, cacheTag, partial-prerendering
---

## Next.js Cache Components with Partial Prerendering

**Impact: HIGH (component-level caching replaces segment-level configuration)**

When `cacheComponents: true` is enabled in `next.config`, Next.js shifts from segment-level caching to compositional, component-level caching using the `'use cache'` directive. This replaces deprecated patterns like `export const revalidate`.

### Architecture Pattern

Pages combine three layers:

- **Static shell** -- rendered at build time, sent immediately
- **Cached content** -- included in static shell with revalidation rules
- **Dynamic streams** -- fetched at request time via Suspense

### Caching Decision Tree

When authoring server components, ask sequentially:

1. Does it perform I/O?
2. Does it depend on request context (cookies, headers, searchParams)?
3. Can the data be cached across all users?

If cacheable across users, use `'use cache'`. If request-dependent, wrap in `<Suspense>`.

### Core APIs

**`'use cache'` directive** -- marks code as cacheable at file, component, or function level. All cached functions must be `async`.

**`cacheLife()`** -- controls cache duration with predefined profiles:

| Profile     | Use Case                   |
| ----------- | -------------------------- |
| `'default'` | Framework default          |
| `'seconds'` | Near-real-time data        |
| `'minutes'` | Frequently updated content |
| `'hours'`   | Standard content           |
| `'days'`    | Stable content             |
| `'weeks'`   | Rarely changing data       |
| `'max'`     | Immutable content          |

Custom config: `cacheLife({ stale: 60, revalidate: 3600, expire: 86400 })`

**`cacheTag()`** -- applies semantic tags for targeted invalidation. Multiple tags per component supported.

**`updateTag()`** -- immediate invalidation for read-your-own-writes after mutations.

**`revalidateTag()`** -- background revalidation, serves stale content while refreshing.

### Usage

**Incorrect (deprecated segment-level caching):**

```typescript
// page.tsx
export const revalidate = 3600 // deprecated with cacheComponents

export default async function Page() {
  const data = await fetchData()
  return <div>{data.title}</div>
}
```

**Correct (component-level caching):**

```typescript
// page.tsx
import { Suspense } from 'react'

export default function Page() {
  return (
    <div>
      <StaticHeader />
      <CachedContent />
      <Suspense fallback={<Loading />}>
        <DynamicUserSection />
      </Suspense>
    </div>
  )
}

async function CachedContent() {
  'use cache'
  cacheLife('hours')
  cacheTag('content', 'homepage')

  const data = await fetchData()
  return <section>{data.title}</section>
}
```

### Invalidation After Mutations

```typescript
'use server'

import { updateTag, revalidateTag } from 'next/cache'

export async function updatePost(id: string, content: string) {
  await db.posts.update({ where: { id }, data: { content } })

  // Immediate invalidation (read-your-own-writes)
  updateTag(`post-${id}`)

  // Background revalidation (stale-while-revalidate)
  revalidateTag('posts-list')
}
```

### Parameter Permutations and Subshells

When using `generateStaticParams()`, Next.js renders ALL permutations to create reusable subshells:

```typescript
// Providing [{ category: 'jackets', slug: 'bomber' }] generates:
// - Full route: /products/jackets/bomber
// - Category subshell: /products/jackets/[slug] (reusable for any jacket)
// - Fallback: /products/[category]/[slug]
```

**Critical**: Must provide at least one parameter. Empty arrays cause build errors.

### Common Build Errors

| Error | Fix |
| ----- | --- |
| "Accessing cookies/headers outside Suspense boundary" | Wrap dynamic components in `<Suspense fallback={...}>` |
| "Accessing uncached data outside Suspense" | Add `'use cache'` or wrap in Suspense |
| "Cannot access cookies inside 'use cache'" | Extract request data outside the cache boundary |

### Proactive Rules

When `cacheComponents: true` is detected:

- **Data fetching**: Ask "Can this be cached?" If yes, add `'use cache'`
- **Server actions**: Always call `updateTag()` or `revalidateTag()` after mutations
- **Page composition**: Structure as static shell + cached + dynamic streams
- **Code review**: Flag missing cache directives, deprecated segment exports

Reference: [Next.js Caching Documentation](https://nextjs.org/docs/app/building-your-application/caching)
