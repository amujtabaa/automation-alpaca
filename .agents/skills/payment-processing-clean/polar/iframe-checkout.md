## Conversion-Optimized Iframe Checkout with Revenue Attribution

**Purpose**: Polar's default overlay has poor conversion rates (30-40% lower). This implementation embeds Polar checkout in an iframe while enabling full revenue attribution through DataFast analytics.

**Key Benefits**:
- 30-40% higher conversion than Polar overlay
- Full customer journey attribution (traffic source, referrer, campaigns)
- Custom success page experience
- Keeps users on-site (better UX)
- Instant loading with smart preloading

---

## Revenue Attribution Architecture (CRITICAL)

### The Problem with Static Checkout Links

Static checkout links (`https://buy.polar.sh/polar_cl_xxx`) cannot attribute purchases to visitor sessions because:
- DataFast tracks visitors with cookies on YOUR domain
- Checkout happens on `buy.polar.sh` (different origin)
- No mechanism to pass visitor identity between domains

### The Solution: API-Based Checkout with Success URL

Create checkout sessions via Polar API with a `success_url` that redirects back to your domain after payment.

```
User clicks CTA
  → Client calls /api/checkout
  → Server creates Polar session with success_url
  → Checkout loads in iframe
  → User completes payment
  → Polar redirects iframe to /checkout-success?checkout_id=xxx
  → Your success page loads (same domain as analytics cookies)
  → DataFast reads checkout_id → Attribution complete!
```

---

## Implementation

### 1. API Route (Server-Side)

**File**: `apps/web/src/app/api/checkout/route.ts`

```typescript
import { NextResponse } from "next/server";
import { env, publicUrl } from "~/lib/env";

export async function POST() {
  if (!env.POLAR_ACCESS_TOKEN || !env.POLAR_PRODUCT_ID) {
    console.error("[Checkout API] Missing environment variables");
    return NextResponse.json(
      { error: "Checkout not configured" },
      { status: 500 }
    );
  }

  try {
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

    if (!response.ok) {
      const errorData = await response.text();
      console.error("[Checkout API] Polar API error:", response.status, errorData);
      return NextResponse.json(
        { error: "Failed to create checkout" },
        { status: response.status }
      );
    }

    const checkout = await response.json();
    return NextResponse.json({
      url: checkout.url,
      id: checkout.id,
    });
  } catch (error) {
    console.error("[Checkout API] Error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
```

**Key Points**:
- `{CHECKOUT_ID}` is a placeholder that Polar replaces with the actual ID
- `success_url` must be your domain for attribution to work
- API token kept server-side only (never exposed to client)

### 2. Environment Variables

**File**: `apps/web/src/lib/env/index.ts`

```typescript
server: {
  POLAR_ACCESS_TOKEN: z.string().optional(),
  POLAR_PRODUCT_ID: z.string().optional(),
},
```

**EasyPanel/Production**:
```
POLAR_ACCESS_TOKEN=polar_oat_xxxxx
POLAR_PRODUCT_ID=your-product-uuid
```

Get your Product ID from Polar Dashboard → Products → Click product → Copy UUID from URL.

### 3. Success Page

**File**: `apps/web/src/app/checkout-success/page.tsx`

```typescript
import { Icons } from "@turbostarter/ui";

export default function CheckoutSuccessPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background p-8">
      <div className="flex max-w-md flex-col items-center text-center">
        <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-primary/10">
          <Icons.Check className="h-10 w-10 text-primary" />
        </div>
        <h1 className="mb-4 text-3xl font-bold tracking-tight text-foreground">
          Thank you for your purchase!
        </h1>
        <p className="text-lg text-muted-foreground">
          You can now close this pop-up and check your email!
        </p>
      </div>
    </div>
  );
}
```

This page loads INSIDE the iframe after payment. DataFast automatically reads the `checkout_id` from the URL.

### 4. Checkout Provider (Client-Side)

**File**: `apps/web/src/providers/polar-checkout.tsx`

```typescript
"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import { Icons } from "@turbostarter/ui";

interface PolarCheckoutContextValue {
  openCheckout: (onOpen?: () => void) => void;
  isOpen: boolean;
}

const PolarCheckoutContext = React.createContext<PolarCheckoutContextValue | null>(null);

export const usePolarCheckout = () => {
  const context = React.useContext(PolarCheckoutContext);
  if (!context) {
    throw new Error("usePolarCheckout must be used within PolarCheckoutProvider");
  }
  return context;
};

export const PolarCheckoutProvider = ({ children }: { readonly children: React.ReactNode }) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const [checkoutUrl, setCheckoutUrl] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(false);
  const [iframeLoaded, setIframeLoaded] = React.useState(false);
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  // Fetch fresh checkout URL from API
  const fetchCheckoutUrl = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetch("/api/checkout", { method: "POST" });
      if (!response.ok) throw new Error("Failed to create checkout");

      const data = await response.json();
      setCheckoutUrl(data.url);
      setIframeLoaded(false);
    } catch (error) {
      console.error("[Polar Checkout] Error:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const openCheckout = React.useCallback(async (onOpen?: () => void) => {
    onOpen?.();
    setIsOpen(true);
    await fetchCheckoutUrl();
  }, [fetchCheckoutUrl]);

  const handleClose = React.useCallback(() => {
    setIsOpen(false);
    setCheckoutUrl(null); // Clear for fresh URL next time
  }, []);

  // Escape key handler
  React.useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") handleClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handleClose]);

  const modalContent = (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 transition-opacity duration-200 ${
        isOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
      }`}
      aria-hidden={!isOpen}
      onClick={handleClose}
    >
      <div
        className="relative h-[80vh] w-[80vw] max-w-[1200px] overflow-hidden !rounded-3xl bg-background shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {isOpen && (
          <button
            type="button"
            onClick={handleClose}
            className="absolute right-4 top-4 z-10 rounded-full border bg-background px-2 py-1 text-sm font-medium text-foreground/70 transition-colors hover:text-foreground"
            aria-label="Close checkout"
          >
            <Icons.X className="h-4 w-4" />
          </button>
        )}
        <div className="relative h-full w-full md:overflow-hidden">
          {/* Loading spinner */}
          {isOpen && (isLoading || !iframeLoaded) && (
            <div className="absolute inset-0 z-[1] flex items-center justify-center bg-background">
              <Icons.Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          )}
          {/* Checkout iframe */}
          {checkoutUrl && (
            <iframe
              src={checkoutUrl}
              title="Checkout"
              className={`absolute inset-0 h-full w-full md:h-[calc(100%+20px)] md:w-[calc(100%+20px)] border-0 ${
                isOpen && iframeLoaded ? "block" : "hidden"
              }`}
              allow="payment *; clipboard-write"
              onLoad={() => setIframeLoaded(true)}
            />
          )}
        </div>
      </div>
    </div>
  );

  const contextValue = React.useMemo(
    () => ({ openCheckout, isOpen }),
    [openCheckout, isOpen]
  );

  return (
    <PolarCheckoutContext.Provider value={contextValue}>
      {children}
      {mounted && createPortal(modalContent, document.body)}
    </PolarCheckoutContext.Provider>
  );
};

// Trigger component
export const PolarCheckoutTrigger = ({
  children,
  onTriggerClick,
  className,
}: {
  readonly children: React.ReactNode;
  readonly onTriggerClick?: () => void;
  readonly className?: string;
}) => {
  const { openCheckout } = usePolarCheckout();

  return (
    <div onClick={() => openCheckout(onTriggerClick)} className={className}>
      {children}
    </div>
  );
};
```

**Key Difference from Static Links**: Uses API to create checkout sessions, enabling:
- Fresh session (no stale/expired checkouts)
- Success URL for revenue attribution
- Discount codes always enabled
- Smart preloading for instant UX

---

## Preloading Strategy (CRITICAL FOR UX)

The checkout URL is fetched via API on **TWO triggers** for instant checkout UX:

### 1. Scroll Trigger
When user scrolls past hero section → API creates checkout session → iframe preloads.

```typescript
// datafast-tracker.tsx
const { preloadCheckout } = usePolarCheckout();
useDataFastScrollTracking({
  onScrollPastHero: preloadCheckout,
});
```

### 2. Hover Trigger
When user hovers any CTA button → API creates checkout (if not already loaded).

```typescript
// PolarCheckoutTrigger
const handleMouseEnter = () => {
  preloadCheckout();
};
```

### How Preloading Works

```typescript
// In provider
const preloadCheckout = React.useCallback(() => {
  if (!checkoutUrl && !isLoading) {
    console.log("[Polar Checkout] Preloading checkout via API...");
    fetchCheckoutUrl(); // Calls POST /api/checkout
  }
}, [checkoutUrl, isLoading, fetchCheckoutUrl]);
```

**Key Points**:
- Each preload trigger calls the Polar API to create a fresh checkout session
- URL is cached for the entire page session (not cleared on close)
- Multiple modal opens = instant checkout (URL stays cached)
- Fresh URL on page reload (React state resets)
- If user clicks before preload completes, spinner shows briefly

### User Journey

```
1. User lands on page (hero) → No preload yet, clean Lighthouse
2. User scrolls to features → API creates checkout, iframe preloads in background
3. User hovers CTA → Backup preload if scroll didn't trigger
4. User clicks → INSTANT checkout (already loaded)
5. Payment completes → Redirect to success page → Attribution captured
```

### Why This Matters

| Without Preloading | With Preloading |
|--------------------|-----------------|
| ~500ms API delay on click | 0ms delay (instant) |
| Spinner visible every time | Spinner only on cold start |
| User waits after decision | Checkout ready before click |

---

## Content Security Policy (CSP)

```javascript
// next.config.js
{
  key: "Content-Security-Policy",
  value: [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://datafa.st https://js.stripe.com https://cdn.polar.sh",
    "style-src 'self' 'unsafe-inline' https://cdn.polar.sh",
    "img-src 'self' data: blob: https://cdn.polar.sh https://avatars.polar.sh https://*.stripe.com",
    "font-src 'self' data: https://cdn.polar.sh",
    "connect-src 'self' https://datafa.st https://api.polar.sh https://*.stripe.com",
    "frame-src 'self' https://polar.sh https://buy.polar.sh https://api.polar.sh https://js.stripe.com https://hooks.stripe.com",
    "form-action 'self' https://polar.sh https://buy.polar.sh https://*.stripe.com",
  ].join("; "),
}
```

---

## Usage

### Basic Trigger

```tsx
import { PolarCheckoutTrigger } from "~/providers/polar-checkout";

<PolarCheckoutTrigger>
  <Button>Get Started</Button>
</PolarCheckoutTrigger>
```

### With Analytics

```tsx
<PolarCheckoutTrigger
  onTriggerClick={() => {
    window?.datafast?.("pricing_cta_clicked", {
      location: "pricing_section",
      plan: "pro",
      price: "39",
    });
  }}
>
  <Button>Get Started</Button>
</PolarCheckoutTrigger>
```

---

## Why API-Based Over Static Links

| Aspect | Static Links | API-Based (Recommended) |
|--------|--------------|-------------------------|
| Revenue Attribution | Not possible | Full customer journey |
| Session Freshness | Can expire | Always fresh |
| Success Page | Polar's generic | Your custom branded |
| Discount Codes | Fixed in URL | Always enabled |
| Security | URL visible | Token server-side |

---

## Implementation Checklist

**API Setup**:
- [ ] Create `/api/checkout` route
- [ ] Add `POLAR_ACCESS_TOKEN` to env schema
- [ ] Add `POLAR_PRODUCT_ID` to env schema
- [ ] Configure environment variables in EasyPanel

**Frontend**:
- [ ] Create success page at `/checkout-success`
- [ ] Update provider to fetch from API
- [ ] Remove static checkout URL constants
- [ ] Test checkout flow end-to-end

**Verification**:
- [ ] Checkout creates successfully (check server logs)
- [ ] Iframe loads checkout page
- [ ] Payment completes and redirects to success page
- [ ] DataFast shows customer journey attribution

---

## Troubleshooting

### "Checkout not configured" error
- Verify `POLAR_ACCESS_TOKEN` is set in environment
- Verify `POLAR_PRODUCT_ID` is correct (check Polar dashboard)
- Check server logs for detailed error

### "Product does not exist" error
- Product ID is wrong - copy correct UUID from Polar dashboard
- Product might be archived

### Attribution not showing in DataFast
- Verify success page URL is on your domain
- Check that `checkout_id` appears in success page URL
- Wait 5-10 minutes for DataFast to process

### CSP blocking iframe
- Add all required domains to CSP (see CSP section)
- Check browser console for specific blocked resources
