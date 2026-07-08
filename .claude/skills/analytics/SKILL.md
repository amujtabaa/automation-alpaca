---
name: analytics
description: Analytics Documentation and Best Practices. To be used when working with Datafa.st, Piqo, Umami, or other Analytics Tools.
---

# Analytics Integration (DataFast, Piqo & Umami)

This skill documents implementation patterns for the three analytics platforms used in production:

- **DataFast** — client-side custom-event tracking with revenue attribution (Stripe / Polar / LemonSqueezy native). Best for funnel/CRO and channel attribution.
- **Piqo** — zero-config click tracking. Reads the W3C accessible name of every clicked button/link, no instrumentation needed. Best for "what did users click on this page" without per-element wiring.
- **Umami** — privacy-focused pageview analytics with a robust server-side API. Best for dashboard queries and historical pageview analysis.

The three are complementary: DataFast covers custom events and conversion goals you wire manually, Piqo automatically catches everything else (clicks you never thought to instrument), and Umami handles pageview rollups.

## Related Files

- **[tracking-setup.md](./tracking-setup.md)** - GA4, GTM, event naming conventions, UTM strategy, and general tracking implementation guidance

---

## DataFast (Client-Side Event Tracking)

### Overview

**Context7 Library ID**: `/websites/datafa_st`
**Documentation**: https://datafa.st/docs

DataFast tracks user actions, scroll events, and revenue attribution. It's optimized for identifying which marketing channels drive conversions.

### Script Installation

Add to your root layout (`app/layout.tsx`):

```tsx
// Queue script in <head> - ensures events capture before main script loads
<script
  id="datafast-queue"
  dangerouslySetInnerHTML={{
    __html: `
      window.datafast = window.datafast || function() {
        window.datafast.q = window.datafast.q || [];
        window.datafast.q.push(arguments);
      };
    `,
  }}
/>

// Main tracking script at end of <body>
<Script
  strategy="afterInteractive"
  data-website-id="your_website_id"
  data-domain="yourdomain.com"
  src="/js/script.js"
/>
```

**Proxy Required**: Use Next.js rewrites to proxy `/js/script.js` → `datafa.st/js/script.js`. See "DataFast Next.js Proxy Setup" section below.

### Three Tracking Methods

#### Method 1: JavaScript (Recommended for Complex Events)

```typescript
// TypeScript declaration
declare global {
  interface Window {
    datafast?: (goal: string, params?: Record<string, string>) => void;
  }
}

// Simple event
window?.datafast?.("signup");

// Event with parameters
window?.datafast?.("pricing_cta_clicked", {
  location: "pricing_section",
  plan: "pro",
  price: "39",
  discount: "launch_offer",
});
```

#### Method 2: HTML Data Attributes (Simplest)

```html
<!-- Simple -->
<button data-fast-goal="initiate_checkout">Buy Now</button>

<!-- With parameters (kebab-case → snake_case) -->
<button
  data-fast-goal="initiate_checkout"
  data-fast-goal-product-id="prod_123"
  data-fast-goal-price="49"
>
  Buy Now
</button>
```

#### Method 3: Server-Side API (Most Reliable)

Best for critical conversions. Requires API key from Website Settings → API tab.

### Goal Naming Rules

- **Goal names**: lowercase, numbers, underscores `_`, hyphens `-`, max 64 characters
- **Parameter names**: same rules, max 64 characters
- **Parameter values**: any string, max 255 characters
- **Max parameters**: 10 per event

### Scroll Tracking Pattern

Use Intersection Observer for section visibility tracking. The hook supports an optional callback for triggering actions (like iframe preloading) when user scrolls past the hero section.

```typescript
// lib/hooks/use-datafast-scroll-tracking.tsx
"use client";

import { useEffect, useRef } from "react";

interface ScrollTrackingSection {
  id: string;
  goalName: string;
}

const SECTIONS: ScrollTrackingSection[] = [
  { id: "hero", goalName: "section_hero_viewed" },
  { id: "features", goalName: "section_features_viewed" },
  { id: "pricing", goalName: "section_pricing_viewed" },
];

interface UseDataFastScrollTrackingOptions {
  onScrollPastHero?: () => void; // Callback when user scrolls past hero
}

export function useDataFastScrollTracking(
  options?: UseDataFastScrollTrackingOptions,
) {
  const trackedSections = useRef<Set<string>>(new Set());
  const hasTriggeredScrollPastHero = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && entry.intersectionRatio >= 0.3) {
            const section = SECTIONS.find((s) => s.id === entry.target.id);

            if (section && !trackedSections.current.has(section.id)) {
              trackedSections.current.add(section.id);

              window?.datafast?.(section.goalName, {
                section_id: section.id,
                timestamp: new Date().toISOString(),
                scroll_depth: Math.round(
                  (window.scrollY / document.documentElement.scrollHeight) *
                    100,
                ).toString(),
              });

              // Trigger callback when user scrolls past hero (reaches any other section)
              if (
                section.id !== "hero" &&
                !hasTriggeredScrollPastHero.current &&
                options?.onScrollPastHero
              ) {
                hasTriggeredScrollPastHero.current = true;
                options.onScrollPastHero();
              }
            }
          }
        });
      },
      { threshold: 0.3 },
    );

    SECTIONS.forEach((section) => {
      const element = document.getElementById(section.id);
      if (element) observer.observe(element);
    });

    return () => observer.disconnect();
  }, []);
}
```

### Using Scroll Tracking for Iframe Preloading

The `onScrollPastHero` callback is ideal for preloading heavy iframes (like checkout modals) before the user reaches CTAs:

```tsx
// components/datafast-tracker.tsx
"use client";

import { useDataFastScrollTracking } from "~/lib/hooks/use-datafast-scroll-tracking";
import { usePolarCheckout } from "~/providers/polar-checkout";

export function DataFastTracker() {
  const { preloadCheckout } = usePolarCheckout();

  // Preload checkout iframe when user scrolls past hero
  useDataFastScrollTracking({
    onScrollPastHero: preloadCheckout,
  });

  return null;
}
```

**Why This Works**:

- User scrolls from hero → features → checkout preloads in background
- By the time user reaches pricing section, checkout is ready
- No Lighthouse impact (scroll events don't trigger during audits)

### Click Tracking Pattern

Use JavaScript handlers for reliable tracking:

```tsx
"use client";

declare global {
  interface Window {
    datafast?: (goal: string, params?: Record<string, string>) => void;
  }
}

export function CTAButton() {
  const handleClick = () => {
    window?.datafast?.("cta_clicked", {
      location: "header",
      plan: "pro",
    });
  };

  return (
    <button
      onClick={handleClick}
      data-fast-goal="cta_clicked"
      data-fast-goal-location="header"
    >
      Get Started
    </button>
  );
}
```

### Client Component Architecture

- **Landing pages**: Server components for SEO
- **Tracker components**: Client component wrappers for event handling
- **Pattern**: Wrap tracking hooks in dedicated client components

```tsx
// components/datafast-tracker.tsx
"use client";

import { useDataFastScrollTracking } from "~/lib/hooks/use-datafast-scroll-tracking";

export function DataFastTracker() {
  useDataFastScrollTracking();
  return null;
}

// In server component page
import { DataFastTracker } from "~/components/datafast-tracker";

export default function LandingPage() {
  return (
    <>
      <DataFastTracker />
      {/* page content */}
    </>
  );
}
```

### Billing Considerations

Custom goals count toward monthly usage. Current implementation tracks:

- Navigation events (reusable per session)
- CTA click events (per conversion attempt)
- Section scroll events (once per session)

### Testing & Debugging

```javascript
// In browser console - verify DataFast is loaded
console.log(typeof window.datafast); // "function"
console.log(window.datafast.q); // array if events queued

// Intercept events for debugging
const originalDatafast = window.datafast;
window.datafast = function (...args) {
  console.log("DataFast Event:", { goal: args[0], params: args[1] || {} });
  return originalDatafast?.apply(this, args);
};
```

### Common Issues

**Events not firing:**

1. Check browser console for errors
2. Verify script loaded (check Network tab)
3. Check ad blockers
4. Ensure components are client components
5. Verify `window.datafast` exists before calling

**Build errors with "use client":**

- Separate tracker logic into dedicated client components
- Keep pages as server components for static generation

---

## Piqo (Zero-Config W3C Click Tracking)

### Overview

Piqo captures every click on `<button>`, `<a>`, `[role="button"]`, and similar interactive elements automatically — no per-element wiring. It derives the event name from the W3C accessible-name algorithm:

1. `aria-label` on the element (highest priority — overrides everything else)
2. `aria-labelledby` reference
3. Visible text content (concatenated, including `sr-only` spans)
4. `alt` attribute (for `<img>`)
5. `title` attribute

**Implication**: every interactive element in your app is already being tracked. The question is whether the captured name is useful (a verb-first sentence) or garbage (`Star`, `Pricing`, `v2.0.0`, raw URLs, button text concatenated with sr-only spans).

### How Piqo resolves the clicked element

Piqo walks up the DOM from the click target via `closest('button, a, [role="button"]')` to find the nearest interactive parent, then reads that element's accessible name.

**Verified in production (2026-05-20)**: when an outer `<div onClick>` wraps an inner `<Button>`, Piqo reads the inner Button's `aria-label` — not the outer div's. This means:

- ✅ Wrapper components like `PolarCheckoutTrigger` (`<div onClick>{<Button aria-label="..." />}</div>`) work fine — put the label on the Button.
- ⚠️ If your `<div onClick>` has no interactive child (just plain text/divs), Piqo will fall back to whatever string the div's accessible-name walk produces (often a mash of inner text). Add `aria-label` directly on the div in that case.

### The Naming Convention (locked)

**Format**: `{Action verb} {Object} {Scope/Location}`

- Verb first: `Open`, `Close`, `Switch`, `View`, `Toggle`, `Dismiss`, `Select`, `Visit`, `Jump to`. Dashboards read like sentences.
- Object: the thing being acted on (`Code Kit checkout`, `Shopify Kit popup`, `FAQ`).
- Scope: page region or component context (`hero`, `pricing section`, `Shopify header`). Omit when verb+object is already unambiguous.

**Rules:**

- Don't repeat the page name — Piqo already records the URL.
- Don't use bare nouns (`Star`, `Pricing`, `Blog`). They appear contextless across pages.
- Keep names ≤ ~45 characters — dashboards truncate.

**Examples (production):**

```tsx
aria-label="Open purchase menu (header)"
aria-label="Close Polar checkout"
aria-label="Dismiss Shopify Kit popup"
aria-label="View Code Kit README"
aria-label="Jump to Shopify Kit pricing (hero)"
```

### Dynamic state-dependent labels

State labels interpolate at render time. They're captured per-state in Piqo automatically.

```tsx
aria-label={`Switch to ${activeKit === "code" ? "Growth" : "Code"} Kit (hero)`}
aria-label={`View ${activeKit === "code" ? "Code Kit" : "Growth Kit"} README`}
aria-label={`Toggle FAQ: ${item.question}`}
aria-label={`${open ? "Close" : "Open"} mobile menu`}
```

### Decorative children pattern

Multiple icon/SVG children inside one clickable parent (e.g., 5 star icons in a rating row) will each emit a click event if they have their own accessible name. This produces 5× event spam per click.

**Bad** — emits 5 `Star` events per row click:

```tsx
{
  stars.map(() => <Icons.Star aria-label="Star" />);
}
```

**Good** — emits zero from children; parent row carries the name:

```tsx
<div aria-label={`Rated ${rating} stars`}>
  {stars.map(() => (
    <Icons.Star aria-hidden="true" />
  ))}
</div>
```

**Caveat**: if the parent `<div>` isn't itself interactive (no `onClick`, not inside an `<a>`/`<button>`), Piqo won't fire any event when the row is clicked — the parent aria-label is dead weight for analytics (but still useful for screen readers). Use this pattern only when the parent or an ancestor is interactive.

### Shadcn / Radix primitives with hardcoded close labels

The shadcn `Sheet`, `Dialog`, and similar primitives bake in a built-in close button with `<span className="sr-only">Close</span>`. Every consumer of these primitives emits the same bare `Close` event — no scope, no context.

**Fix**: extend the primitive's `Content` props with an optional `closeLabel?: string` and forward it onto both `aria-label` and the inner `sr-only` span:

```tsx
interface SheetContentProps extends React.ComponentPropsWithoutRef<typeof SheetPrimitive.Content> {
  closeLabel?: string;
}

const SheetContent = React.forwardRef<...>(({ closeLabel = "Close", children, ...props }, ref) => (
  ...
  <SheetPrimitive.Close aria-label={closeLabel} className="...">
    <X className="h-4 w-4" aria-hidden="true" />
    <span className="sr-only">{closeLabel}</span>
  </SheetPrimitive.Close>
  ...
));
```

Then each caller passes a scoped label:

```tsx
<SheetContent closeLabel={`Close ${title} README`}>...
<SheetContent closeLabel="Close changelog popup">...
<SheetContent closeLabel="Close Shopify Kit README">...
```

The default `"Close"` preserves backwards compatibility for unscoped Sheets.

### Outbound link event framing

Piqo categorizes clicks on external `<a>` links under a **separate** event type called `Outbound Link: Click`, with the aria-label appearing as a `label` parameter (e.g. `label=Visit x.com`). This is not a bug — it's Piqo's built-in segmentation. The aria-label is still captured correctly; just expect outbound clicks to be filtered/grouped separately from your custom events in the dashboard.

### sr-only span concatenation gotcha

`<span className="sr-only">` text is part of the accessible name. If a link has both visible text AND an sr-only span, Piqo concatenates them — often without spaces.

**Bug seen in production**:

```tsx
<TurboLink href="/">
  <ClaudeFastLogo withText /> {/* renders "Claude Fast" */}
  <span className="sr-only">home</span> {/* concatenated → "Claude Fasthome" */}
</TurboLink>
```

**Fix**: add `aria-label` (which overrides all other sources per W3C spec), then remove the redundant `sr-only` span:

```tsx
<TurboLink href="/" aria-label="Go to homepage (header)">
  <ClaudeFastLogo withText />
</TurboLink>
```

### Decision pattern: no wrapper component for visually-hidden labels

We considered a `<VisuallyHidden>` wrapper component for this work. Rejected: every case was solved with `aria-label` + (optional) `aria-hidden`. Keeping the JSX surface area minimal reduces a11y regression risk and keeps audits diff-able.

### Installation

Piqo is installed as a single script tag, similar to DataFast. Add `piqo.com` (or your Piqo proxy host) to the CSP `connect-src` and `script-src` directives.

### Production case study

Full inventory of one site's aria-label refactor (67 interactive elements across 27 files, with naming-convention rationale, post-deploy verification, and gap-patches): see `.claude/tasks/aria-label-piqo-audit.md` in the ClaudeFast repo. It documents the locked convention, decision log, and verified outcomes across DataFast + Piqo dashboards.

---

## Umami (Server-Side Analytics API)

### Environment Variables

```env
# Server-side (for API calls)
UMAMI_API_KEY="your-api-key"
UMAMI_WEBSITE_ID="your-website-id"

# Client-side (for tracking script)
NEXT_PUBLIC_UMAMI_WEBSITE_ID="your-website-id"
NEXT_PUBLIC_UMAMI_DOMAINS="yourdomain.com"
NEXT_PUBLIC_UMAMI_URL="/_proxy/umami"
```

Get from Umami dashboard:

- API Key: Settings → API Keys → Create
- Website ID: Settings → Websites → Click website → Copy UUID

**Important**:

- `NEXT_PUBLIC_UMAMI_DOMAINS` prevents tracking on localhost/preview deployments
- `NEXT_PUBLIC_UMAMI_URL` should point to your proxy (e.g., `/_proxy/umami`) for ad-blocker bypass, or directly to Umami (e.g., `https://cloud.umami.is`)

### Service Layer Pattern

```typescript
// services/umami.ts
import wretch from "wretch";
import { env } from "~/env";

// CRITICAL: Pass full path to preserve auth header
// DO NOT use .url() chaining - it loses the Bearer token
export const getUmamiApi = (path: string) => {
  return wretch(`https://api.umami.is/v1${path}`)
    .auth(`Bearer ${env.UMAMI_API_KEY}`)
    .headers({ "Content-Type": "application/json" });
};
```

**Critical Pattern**: Always pass the complete path including query params to `getUmamiApi()`. Using `.url()` after creating the wretch instance will lose the auth header.

### API Usage

```typescript
import { getUmamiApi } from "~/services/umami";

// Correct - path includes all query params
const { data, error } = await tryCatch(
  getUmamiApi(
    `/websites/${env.UMAMI_WEBSITE_ID}/pageviews?startAt=${startAt}&endAt=${endAt}&unit=day`,
  )
    .get()
    .json<UmamiPageviewsResponse>(),
);

// WRONG - DO NOT DO THIS (loses auth header)
// getUmamiApi().url(`/websites/...`).get()
```

### API Endpoints

#### Get Page Stats

```typescript
type UmamiStatsResponse = {
  pageviews: { value: number; prev: number };
  visitors: { value: number; prev: number };
  visits: { value: number; prev: number };
  bounces: { value: number; prev: number };
  totaltime: { value: number; prev: number };
};

const stats = await getUmamiApi(
  `/websites/${websiteId}/stats?startAt=${startAt}&endAt=${endAt}&url=${encodeURIComponent(page)}`,
)
  .get()
  .json<UmamiStatsResponse>();
```

#### Get Pageviews Over Time

```typescript
type UmamiPageviewsResponse = {
  pageviews: { x: string; y: number }[]; // x = date, y = count
  sessions: { x: string; y: number }[];
};

const data = await getUmamiApi(
  `/websites/${websiteId}/pageviews?startAt=${startAt}&endAt=${endAt}&unit=day`,
)
  .get()
  .json<UmamiPageviewsResponse>();
```

### Date Range Parameters

- `startAt`: Unix timestamp in milliseconds
- `endAt`: Unix timestamp in milliseconds
- `unit`: `hour`, `day`, `week`, `month`, `year`

```typescript
const days = 30;
const endAt = Date.now();
const startAt = endAt - days * 24 * 60 * 60 * 1000;
```

### Proxy Configuration (Recommended)

Add to `next.config.ts` to bypass ad-blockers (~15-30% more accurate data):

```typescript
async rewrites() {
  return [
    // Umami proxy (bypasses ad-blockers)
    {
      source: "/_proxy/umami/:path*",
      destination: "https://cloud.umami.is/:path*",
    },
  ]
}
```

Then set `NEXT_PUBLIC_UMAMI_URL="/_proxy/umami"` in your `.env` file.

For self-hosted Umami, change the destination to your analytics server (e.g., `https://analytics.yourdomain.com/:path*`).

### Tracking Script

```tsx
import Script from "next/script";
import { env } from "~/env";

<Script
  defer
  data-website-id={env.NEXT_PUBLIC_UMAMI_WEBSITE_ID}
  data-domains={env.NEXT_PUBLIC_UMAMI_DOMAINS}
  src={`${env.NEXT_PUBLIC_UMAMI_URL}/script.js`}
/>;
```

**Key attributes**:

- `data-domains`: Comma-separated list of domains to track (prevents localhost/preview tracking)
- `data-website-id`: Your Umami website UUID
- `src`: Points to proxy for ad-blocker bypass

### Error Handling Pattern

```typescript
const { data, error } = await tryCatch(
  getUmamiApi(`/path`).get().json<ResponseType>(),
);

if (error) {
  console.error("Analytics error:", error);
  return { results: [], totalVisitors: 0, averageVisitors: 0 };
}
```

### Cache Invalidation

```typescript
import { revalidateTag } from "next/cache";

// In server actions
revalidateTag("analytics");
```

### Common Issues

**"No API key specified" Error**

- Cause: Using `.url()` chaining loses auth header
- Fix: Pass complete path to `getUmamiApi(path)` directly

**Data not updating**

- Cause: Aggressive caching
- Fix: Use `revalidateTag()` or shorter cache life

### Free Tier Limits

- 10,000 events/month
- Unlimited websites
- 6 month data retention

For higher limits, consider self-hosting Umami.

---

## When to Use Each Platform

| Use Case                                    | Platform          | Reason                                                                                 |
| ------------------------------------------- | ----------------- | -------------------------------------------------------------------------------------- |
| Revenue attribution                         | DataFast          | Native Stripe/Polar/LemonSqueezy integration                                           |
| Custom events with params (clicks, scrolls) | DataFast          | Programmatic firing with rich param shapes                                             |
| Funnel / conversion goal tracking           | DataFast          | Goals + predictions trained on event volume                                            |
| Marketing channel attribution               | DataFast          | UTM + referrer attribution to conversion                                               |
| "What did users click on this page?"        | Piqo              | Zero-config — captures every interactive element automatically                         |
| Accessibility-derived event names           | Piqo              | Uses W3C accessible-name algorithm; aria-label tuning shapes the entire event taxonomy |
| Validating a UX refactor                    | Piqo              | Compare event names + volume before/after — no instrumentation work                    |
| Server-side analytics queries               | Umami             | Robust authenticated API for dashboards                                                |
| Dashboard/admin analytics                   | Umami             | Better for data visualization                                                          |
| Privacy-focused pageviews                   | Umami or DataFast | Both are privacy-focused                                                               |

**Defense-in-depth pattern (recommended)**: run DataFast for instrumented goals + Piqo as the safety net. Piqo will catch clicks you never thought to instrument; DataFast carries the param-rich events you care about for funnel analysis.

---

## Implementation Checklist

### DataFast Setup

- [ ] Add queue script to `<head>`
- [ ] Add main tracking script (proxied)
- [ ] Create TypeScript declarations
- [ ] Implement scroll tracking hook
- [ ] Add click handlers to CTAs
- [ ] Test with browser console debugging
- [ ] Audit for double-tracking (don't use both `window.datafast()` JS call AND `data-fast-goal` attr on the same element)
- [ ] Normalize param shape for events that fire from multiple surfaces (see "Cross-surface param normalization" pitfall)

### Piqo Setup

- [ ] Add Piqo script tag
- [ ] Add Piqo host to CSP `connect-src` and `script-src`
- [ ] Audit all interactive elements: `<button>`, `<a>`, `[role="button"]`, `<div onClick>` — apply the `{verb} {object} {scope}` aria-label convention
- [ ] Mark decorative children (icons inside clickable parents) `aria-hidden="true"`
- [ ] Extend Sheet/Dialog/Drawer primitives with a `closeLabel` prop instead of letting the hardcoded "Close" sr-only span leak through
- [ ] Audit `sr-only` spans for concatenation gotchas (visible text + sr-only with no space = `Claude Fasthome`-style merges)
- [ ] Post-deploy verification: 24-48h after going live, compare top-volume events in dashboard against expected names. Investigate any bare nouns that persist.

### Umami Setup

- [ ] Set environment variables (including DOMAINS and URL)
- [ ] Configure proxy rewrites in next.config.ts
- [ ] Create service layer with auth pattern
- [ ] Implement API calls with error handling
- [ ] Add tracking script with data-domains
- [ ] Set up cache invalidation
- [ ] Test ad-blocker bypass with proxy

---

## Code Locations (ClaudeFast)

```
/apps/web/
├── src/
│   ├── app/
│   │   └── layout.tsx                              # DataFast queue + tracking scripts + Piqo script
│   ├── components/
│   │   ├── common/layout/header/
│   │   │   ├── header.tsx                          # Header logo aria-label
│   │   │   ├── purchase-dropdown.tsx               # purchase_click event (desktop header)
│   │   │   ├── controls.tsx                        # Header CTA tracking
│   │   │   └── nav/
│   │   │       ├── nav.tsx                         # Desktop nav tracking
│   │   │       └── mobile-nav.tsx                  # Mobile nav + purchase_click (mobile_menu surface)
│   │   ├── common/readme-panel.tsx                 # Sheet w/ closeLabel for scoped close events
│   │   └── home/
│   │       ├── hero/hero.tsx                       # hero_mobile_cta_clicked event
│   │       ├── datafast-tracker.tsx                # Client wrapper for scroll tracking
│   │       ├── changelog-popup.tsx                 # Sheet w/ closeLabel
│   │       └── pricing/pricing.tsx                 # Pricing CTA tracking
│   ├── app/shopify/
│   │   ├── shopify-header.tsx                      # purchase_click event (shopify_header surface)
│   │   └── shopify-everything.tsx                  # Sheet w/ closeLabel for Shopify Kit README
│   ├── lib/
│   │   └── hooks/
│   │       └── use-datafast-scroll-tracking.tsx    # Scroll tracking hook
│   └── services/
│       └── umami.ts                                # Umami API service
└── /packages/ui/src/components/web/
    └── sheet.tsx                                   # Sheet primitive — closeLabel prop on SheetContent
```

**Reference inventory**: `.claude/tasks/aria-label-piqo-audit.md` — exhaustive table of every interactive element (67 elements across 27 files), its accessible-name source, the applied label, and post-deploy verification status.

---

## DataFast Next.js Proxy Setup (Required)

DataFast requires proxy setup to bypass ad-blockers. Use Next.js rewrites (recommended by DataFast docs).

### next.config.js Rewrites

Add to your `next.config.js`:

```javascript
module.exports = {
  async rewrites() {
    return [
      {
        source: "/js/script.js",
        destination: "https://datafa.st/js/script.js",
      },
      {
        source: "/api/events",
        destination: "https://datafa.st/api/events",
      },
    ];
  },
};
```

### Script Tag Implementation

Add to your root layout:

```tsx
import Script from "next/script";

<Script
  strategy="afterInteractive"
  data-website-id="your_website_id"
  data-domain="yourdomain.com"
  src="/js/script.js"
/>;
```

**Note**: Next.js automatically handles IP forwarding with rewrites.

### Why Proxy is Required

- Bypasses ad-blockers (~30% more accurate data)
- Keeps analytics running when third-party scripts are blocked
- Official DataFast recommendation: https://datafa.st/docs/nextjs-proxy

### Alternative: Nginx Proxy (for VPS/EasyPanel)

If using Nginx (EasyPanel, VPS), add to your config:

```nginx
location /js/script.js {
    proxy_pass https://datafa.st/js/script.js;
    proxy_set_header Host datafa.st;
    proxy_cache_valid 200 1y;
    add_header Cache-Control "public, max-age=31536000";
}

location /api/events {
    proxy_pass https://datafa.st/api/events;
    proxy_set_header Host datafa.st;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_method POST;
    proxy_pass_request_body on;
}
```

---

## DataFast + Polar Revenue Attribution (CRITICAL)

When using Polar checkout in an iframe, DataFast cannot attribute purchases to visitor sessions by default because the checkout happens on a different domain (`buy.polar.sh`). This section documents the best practice solution.

### The Problem

| What Works                               | What Doesn't Work                                       |
| ---------------------------------------- | ------------------------------------------------------- |
| DataFast shows purchase in revenue graph | Customer journey attribution (traffic source, referrer) |
| Purchase amount tracked                  | Which campaign drove the sale                           |
| Transaction recorded                     | Which page the customer came from                       |

### The Solution: API-Based Checkout with Success URL

Create checkout sessions via Polar API with a `success_url` that redirects back to your domain after payment.

**Architecture**:

```
User clicks CTA
  → /api/checkout creates Polar session with success_url
  → Checkout loads in iframe
  → User pays
  → Polar redirects iframe to /checkout-success?checkout_id=xxx
  → Your domain loads (same cookies as DataFast)
  → DataFast reads checkout_id → Full attribution!
```

### Implementation

**1. API Route** (`/api/checkout`):

```typescript
const response = await fetch("https://api.polar.sh/v1/checkouts/", {
  method: "POST",
  headers: {
    Authorization: `Bearer ${env.POLAR_ACCESS_TOKEN}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    products: [env.POLAR_PRODUCT_ID],
    success_url: `${publicUrl}/checkout-success?checkout_id={CHECKOUT_ID}`,
    allow_discount_codes: true,
  }),
});
```

**2. Success Page** (`/checkout-success`):

- Simple thank-you page that loads in iframe after payment
- DataFast automatically reads `checkout_id` from URL
- No additional code needed - just having the page on your domain is enough

**3. Environment Variables**:

```
POLAR_ACCESS_TOKEN=polar_oat_xxxxx
POLAR_PRODUCT_ID=your-product-uuid
```

### Why This Works

- `{CHECKOUT_ID}` is replaced by Polar with the actual checkout ID
- After payment, iframe redirects to YOUR domain with the checkout_id
- DataFast matches this to the visitor's existing session/cookies
- Full customer journey attribution restored

### Key Points

- Success page MUST be on your domain (not Polar's)
- `checkout_id` in URL is how DataFast matches the purchase
- API approach also provides fresh checkout sessions (no stale URLs)
- See `polar-integration` skill for full implementation code

---

## Best Practices: Analytics-Driven Preloading

Scroll tracking events trigger API-based checkout preloading for instant UX without impacting Lighthouse scores.

### Smart Preloading Triggers

| Trigger    | When                           | Action                                       |
| ---------- | ------------------------------ | -------------------------------------------- |
| **Scroll** | User scrolls past hero section | API creates checkout, iframe preloads        |
| **Hover**  | User hovers CTA button         | API creates checkout (if not already loaded) |

### Implementation

```typescript
// datafast-tracker.tsx
const { preloadCheckout } = usePolarCheckout();

useDataFastScrollTracking({
  onScrollPastHero: preloadCheckout, // Calls Polar API to create checkout
});
```

The `preloadCheckout` function calls the `/api/checkout` endpoint which creates a Polar checkout session with the attribution-enabled `success_url`.

### User Journey

```
1. User lands on page (hero) → No preload yet, clean Lighthouse
2. User scrolls to features → API creates checkout, iframe preloads in background
3. User hovers CTA → Backup preload if scroll didn't trigger
4. User clicks CTA → INSTANT checkout (already loaded)
5. Payment completes → Redirect to success page
6. DataFast captures checkout_id → Full attribution
```

### Key Points

- Each preload trigger calls the Polar API (not just toggling iframe visibility)
- The checkout URL is cached for the entire page session (not cleared on close)
- Multiple modal opens = instant checkout (URL stays cached)
- Fresh URL on page reload (React state resets)
- This combines instant UX with revenue attribution
- Lighthouse scores stay high (no auto-preload on page load)

---

## Common Pitfalls & Lessons Learned

Production gotchas observed in real dashboards. Each one is a class of bug, not a one-off — check for the pattern across your codebase before shipping.

### 1. DataFast double-tracking via attr + JS on the same element

**Symptom**: every nav click fires twice in DataFast — once with a `device` param, once without. Volume looks roughly 2× what it should be; any goal targeting the event-without-`device` will undercount.

**Cause**: developer added `window.datafast?.("nav_blog", {...})` inside the click handler AND left `data-fast-goal="nav_blog"` on the same `<a>` element. DataFast fires both paths.

**Fix**: pick one source per element. The JS call is usually richer (lets you compute `device`, derived state, etc.), so keep that and remove the attribute. Verify in dashboard: pre-fix sessions show paired duplicate events at the same timestamp; post-fix sessions show single events.

**How to find offenders**:

```bash
rg "data-fast-goal" apps/web/src    # cross-reference with JS-fired goals
```

### 2. Stale hardcoded params

**Symptom**: an event consistently carries a param value that doesn't match any current product/plan/state — e.g. `plan: "pro"` when your plans are now `codekit`/`growthkit`/etc.

**Cause**: leftover from a previous setup. The event was instrumented under an older pricing model, the model changed, and nobody re-checked the params.

**Fix**: audit every `window.datafast(...)` call site quarterly. Drop params that no longer map to any current state. If a param needs to track current state, make it dynamic (`kit: activeKit`), not hardcoded.

### 3. Cross-surface event-name reuse with inconsistent param shape

**Symptom**: one event name (`purchase_click`) fires from three places with three different param shapes — different value formats (`"Code Kit"` vs `"codekit"`), different fields present (some have `price`, some don't). In the dashboard, the same product appears as multiple values, fragmenting aggregations.

**Cause**: same event name was instrumented independently at each call site. No shared schema.

**Fix**: when the same event fires from N surfaces, define a canonical schema once and normalize all firing sites to it:

```ts
purchase_click {
  product: string   // canonical: display name ("Code Kit")
  price:   string   // numeric string
  device:  "desktop" | "mobile"
  surface: string   // NEW dimension: which entry point ("header", "mobile_menu", "shopify_header")
}
```

The `surface` dimension is a free CRO win — it lets you answer "which entry point drives the most checkout opens?" without manual joins.

### 4. Bare-noun aria-labels (Piqo dashboard noise)

**Symptom**: top Piqo events are `Pricing`, `Blog`, `Star`, `v2.0.0`, `With Claude Fast`. No verb, no scope, often colliding across pages.

**Cause**: aria-labels (or visible button text) used the object name only. Piqo reads the accessible name verbatim.

**Fix**: rewrite to `{verb} {object} {scope}` — `Open Pricing from header`, `Comparison tab: with Claude Fast`, `Rated 5 stars`. See the Piqo section above for the locked convention.

### 5. Decorative icon spam (`Star` × 5 per click)

**Symptom**: a single click on a rating row emits 5 `Star` events because each star icon had its own `aria-label="Star"`.

**Fix**: `aria-hidden="true"` on every decorative child; put one aria-label on an interactive parent (if one exists). If no interactive parent, accept that the row won't fire any event (the parent aria-label is dead weight for analytics, but keep it for screen readers).

### 6. sr-only span concatenation

**Symptom**: an event name like `Claude Fasthome` appears (visible text "Claude Fast" + sr-only "home" merged with no space).

**Cause**: `<a><LogoImage /><span className="sr-only">home</span></a>` — Piqo concatenates child text content.

**Fix**: add `aria-label` on the parent (W3C spec: aria-label overrides all other accessible-name sources), then remove the now-redundant sr-only span.

### 7. Shadcn/Radix primitives with built-in `Close` sr-only spans

**Symptom**: every Sheet/Dialog close button fires the same bare `Close` event with no scope, across multiple surfaces.

**Cause**: the primitive (`SheetContent`, `DialogContent`) bakes in `<SheetPrimitive.Close><span className="sr-only">Close</span></SheetPrimitive.Close>`. Every consumer inherits this verbatim.

**Fix**: extend the primitive's content props with an optional `closeLabel` prop, default to `"Close"` for backwards compatibility:

```tsx
interface SheetContentProps {
  closeLabel?: string;
  // ...other props
}

// inside SheetContent:
<SheetPrimitive.Close aria-label={closeLabel}>
  <X aria-hidden="true" />
  <span className="sr-only">{closeLabel}</span>
</SheetPrimitive.Close>;
```

Then every caller passes a scoped label: `closeLabel="Close Code Kit README"`, `closeLabel="Close changelog popup"`.

### 8. Wrapper components & accessible-name walk

**Symptom**: a `<div onClick>` wrapping a `<Button>` — you don't know whether Piqo reads the div's name or the Button's name.

**Verified behavior (2026-05-20)**: Piqo walks up via `closest('button, a, [role="button"]')` from the click target, then reads the resolved element's accessible name. So an inner `<Button aria-label="..." />` wins — Piqo finds the Button and reads its label. The outer div's name is irrelevant unless the div is itself the matched interactive element.

**Implication**: put aria-label on the inner Button. No need to refactor wrapper components like `PolarCheckoutTrigger` to propagate the label upward.

**Caveat**: if your `<div onClick>` has no `<button>`/`<a>` child, the `closest()` walk falls through to the div itself, and Piqo derives the name from the div's text content (often a mash). In that case, add `aria-label` directly on the div.

### 9. Outbound link events are categorized separately

**Symptom**: you don't see your `Visit twitter.com` aria-label in Piqo's "Custom Events" view.

**Cause**: Piqo segments external `<a>` clicks into a separate `Outbound Link: Click` event type, with your aria-label appearing as a `label` parameter (e.g. `label=Visit x.com`).

**Fix**: not a bug — look in the Outbound Links section of the dashboard, not Custom Events. The aria-label is still being captured correctly.

### 10. Verification can be impossible from analytics alone

**Symptom**: you can't tell from a 24h dashboard pull whether checkout-button labels are firing correctly because no one happened to click checkout.

**Fix**: create an authenticated test session, click through every CTA variant yourself, then read the per-visitor event timeline in the dashboard. Closes the verification gap without waiting for organic clicks. (Piqo + DataFast both expose per-visitor event timelines.)

### 11. Historical data persists under old names

**Symptom**: after renaming a goal from `hero_cta_clicked` to `growth_hero_cta_clicked`, the new goal has zero data and the old goal still exists in dashboards.

**Fix**: this is by design — analytics platforms don't backfill renames. Past events stay under their original name. Either filter by deploy timestamp forward, or keep a manual mapping for cross-period analysis. Mention this explicitly when renaming established goals.
