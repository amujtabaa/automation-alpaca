# Dodo Payments Checkout Implementation

## Checkout Methods Overview

Dodo Payments offers four checkout integration methods, ranked by recommendation:

1. **Checkout Sessions** (Recommended) - API-based, most flexible
2. **Overlay Checkout** - Embedded in-page experience
3. **Static Payment Links** - No-code, simple URL sharing
4. **Dynamic Payment Links** - API-created shareable links

---

## 1. Checkout Sessions (Recommended)

### Basic Implementation

**Server Action (Next.js)**:
```typescript
"use server";

import DodoPayments from "dodopayments";
import { env } from "~/env";

const dodo = new DodoPayments({
  bearerToken: env.DODO_PAYMENTS_API_KEY,
  environment: env.DODO_PAYMENTS_MODE === "test" ? "test_mode" : "live_mode",
});

export async function createDodoCheckout(productId: string, metadata?: Record<string, string>) {
  const session = await dodo.checkoutSessions.create({
    product_cart: [{ product_id: productId, quantity: 1 }],
    return_url: `${env.NEXT_PUBLIC_SITE_URL}/checkout/success`,
    metadata: metadata,
    allow_discount_code: true,
  });

  return {
    url: session.checkout_url,
    sessionId: session.session_id,
  };
}
```

**Client Usage**:
```typescript
"use client";

import { createDodoCheckout } from "~/server/actions/checkout";

export function BuyButton({ productId }: { productId: string }) {
  const [isLoading, setIsLoading] = useState(false);

  const handleClick = async () => {
    setIsLoading(true);
    try {
      const { url } = await createDodoCheckout(productId, { source: "buy_button" });
      window.location.href = url; // Redirect to Dodo checkout
    } catch (error) {
      console.error("Checkout failed:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <button onClick={handleClick} disabled={isLoading}>
      {isLoading ? "Loading..." : "Buy Now"}
    </button>
  );
}
```

### With Customer Pre-fill

```typescript
const session = await dodo.checkoutSessions.create({
  product_cart: [{ product_id: productId, quantity: 1 }],
  customer: {
    email: "customer@example.com",
    name: "John Doe",
  },
  billing_address: {
    country: "US",
    // city, state, street, zipcode optional
  },
  return_url: `${env.NEXT_PUBLIC_SITE_URL}/checkout/success`,
});
```

### Session Validity

- **Default**: 24 hours
- **With `confirm: true`**: 15 minutes (requires full billing address)

---

## 2. Overlay Checkout (Embedded Experience)

### Installation

```bash
npm install dodopayments-checkout
# or
bun add dodopayments-checkout
```

### React Provider Pattern

**Provider Component**:
```typescript
"use client";

import { DodoPayments, CheckoutEvent } from "dodopayments-checkout";
import * as React from "react";
import { createPortal } from "react-dom";

interface DodoCheckoutContextValue {
  openCheckout: (checkoutUrl: string) => void;
  closeCheckout: () => void;
  isOpen: boolean;
}

const DodoCheckoutContext = React.createContext<DodoCheckoutContextValue | null>(null);

export const useDodoCheckout = () => {
  const context = React.useContext(DodoCheckoutContext);
  if (!context) {
    throw new Error("useDodoCheckout must be used within DodoCheckoutProvider");
  }
  return context;
};

export function DodoCheckoutProvider({ children }: { children: React.ReactNode }) {
  const [isOpen, setIsOpen] = React.useState(false);
  const [initialized, setInitialized] = React.useState(false);

  React.useEffect(() => {
    if (!initialized) {
      DodoPayments.Initialize({
        mode: process.env.NEXT_PUBLIC_DODO_MODE === "test" ? "test" : "live",
        onEvent: (event: CheckoutEvent) => {
          console.log("Checkout event:", event.event_type);

          switch (event.event_type) {
            case "checkout.opened":
              setIsOpen(true);
              break;
            case "checkout.closed":
              setIsOpen(false);
              break;
            case "checkout.error":
              console.error("Checkout error:", event.data?.message);
              setIsOpen(false);
              break;
            case "checkout.redirect":
              // Handle redirect - Dodo will redirect to return_url
              break;
          }
        },
      });
      setInitialized(true);
    }
  }, [initialized]);

  const openCheckout = React.useCallback((checkoutUrl: string) => {
    DodoPayments.Checkout.open({ checkoutUrl });
  }, []);

  const closeCheckout = React.useCallback(() => {
    DodoPayments.Checkout.close();
    setIsOpen(false);
  }, []);

  return (
    <DodoCheckoutContext.Provider value={{ openCheckout, closeCheckout, isOpen }}>
      {children}
    </DodoCheckoutContext.Provider>
  );
}
```

**Usage with Server Action**:
```typescript
"use client";

import { useDodoCheckout } from "~/providers/dodo-checkout";
import { createDodoCheckout } from "~/server/actions/checkout";

export function BuyButton({ productId }: { productId: string }) {
  const { openCheckout } = useDodoCheckout();
  const [isLoading, setIsLoading] = useState(false);

  const handleClick = async () => {
    setIsLoading(true);
    try {
      const { url } = await createDodoCheckout(productId);
      openCheckout(url); // Opens overlay instead of redirect
    } catch (error) {
      console.error("Checkout failed:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <button onClick={handleClick} disabled={isLoading}>
      Buy Now
    </button>
  );
}
```

### Overlay Checkout Events

| Event | Description |
|-------|-------------|
| `checkout.opened` | Overlay displayed |
| `checkout.payment_page_opened` | Payment form rendered |
| `checkout.customer_details_submitted` | Customer info captured |
| `checkout.closed` | Overlay dismissed |
| `checkout.redirect` | Redirecting to return_url |
| `checkout.error` | Error occurred |

**Note**: Apple Pay is NOT supported in overlay checkout mode.

---

## 3. Dynamic Pricing with Pay What You Want (PWYW)

For dynamic pricing (like our advertisement checkout), use PWYW products:

### Setup

1. Create a PWYW product in Dodo dashboard:
   - Set product type: One-time
   - Enable "Pay What You Want"
   - Set minimum price (e.g., $0.50)
   - Set suggested price (optional)

2. Pass custom amount at checkout:

```typescript
export async function createAdCheckout(
  productId: string,
  amountInCents: number,
  metadata: Record<string, string>
) {
  const session = await dodo.checkoutSessions.create({
    product_cart: [
      {
        product_id: productId,
        quantity: 1,
        amount: amountInCents, // Custom amount for PWYW products
      }
    ],
    return_url: `${env.NEXT_PUBLIC_SITE_URL}/advertise/success?session_id={SESSION_ID}`,
    metadata: metadata,
  });

  return {
    url: session.checkout_url,
    sessionId: session.session_id,
  };
}
```

### Volume Discount Pattern (Matching Polar Implementation)

```typescript
export async function createAdCheckout(selections: AdSelection[]) {
  // Calculate total price with volume discount
  const basePrice = 2.50; // Cheapest ad type price
  const totalValue = selections.reduce((sum, s) => sum + s.price * s.duration, 0);
  const equivalentDays = Math.round(totalValue / basePrice);
  const discountPercentage = Math.min(Math.max(equivalentDays - 1, 0), 30);
  const discountedTotal = totalValue * (1 - discountPercentage / 100);
  const totalCents = Math.round(discountedTotal * 100);

  const session = await dodo.checkoutSessions.create({
    product_cart: [
      {
        product_id: env.DODO_AD_BUNDLE_ID!, // PWYW product
        quantity: 1,
        amount: totalCents,
      }
    ],
    return_url: `${env.NEXT_PUBLIC_SITE_URL}/advertise/success?session_id={SESSION_ID}`,
    metadata: {
      ads: JSON.stringify(selections),
      discount_percent: String(discountPercentage),
    },
  });

  return session;
}
```

---

## 4. Success Page & Return URL

### Return URL Format

After payment, Dodo redirects to your `return_url` with query parameters:

```
https://yoursite.com/checkout/success?payment_id=pay_xxx&status=succeeded
```

**Available Parameters**:
- `payment_id` - Unique payment identifier
- `status` - Payment status (`succeeded`, `failed`, etc.)

### Success Page Implementation

```typescript
// app/checkout/success/page.tsx
import { redirect } from "next/navigation";
import DodoPayments from "dodopayments";

const dodo = new DodoPayments({
  bearerToken: process.env.DODO_PAYMENTS_API_KEY!,
  environment: process.env.DODO_PAYMENTS_MODE === "test" ? "test_mode" : "live_mode",
});

export default async function SuccessPage({
  searchParams,
}: {
  searchParams: { payment_id?: string; status?: string };
}) {
  const { payment_id, status } = searchParams;

  if (!payment_id || status !== "succeeded") {
    redirect("/checkout/failed");
  }

  // Optionally fetch payment details
  // const payment = await dodo.payments.retrieve(payment_id);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center">
      <h1>Thank you for your purchase!</h1>
      <p>Payment ID: {payment_id}</p>
      <p>Check your email for confirmation.</p>
    </div>
  );
}
```

### For Ads: Form Submission on Success

```typescript
// app/advertise/success/page.tsx
export default async function AdSuccessPage({
  searchParams,
}: {
  searchParams: { session_id?: string; payment_id?: string };
}) {
  const sessionId = searchParams.session_id || searchParams.payment_id;

  if (!sessionId) {
    redirect("/advertise");
  }

  // Fetch checkout/payment to get metadata
  const payment = await dodo.payments.retrieve(sessionId);
  const adSelections = JSON.parse(payment.metadata?.ads || "[]");

  return (
    <div>
      <h1>Complete Your Ad Details</h1>
      <AdDetailsForm
        sessionId={sessionId}
        selections={adSelections}
      />
    </div>
  );
}
```

---

## 5. Metadata Handling

### Passing Metadata

```typescript
const session = await dodo.checkoutSessions.create({
  product_cart: [...],
  return_url: "...",
  metadata: {
    tool_slug: "my-tool",
    source: "submit_page",
    product_type: "featured",
  },
});
```

### Retrieving Metadata (Webhook or Success Page)

Metadata is available in:
- Webhook payloads: `payload.data.metadata`
- Payment retrieval: `payment.metadata`
- Checkout session retrieval: `session.metadata`

---

## 6. CSP Configuration

For overlay checkout to work, add these CSP headers:

```javascript
// next.config.js
const cspHeader = `
  default-src 'self';
  script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net;
  style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
  frame-src 'self' https://checkout.dodopayments.com https://test.checkout.dodopayments.com;
  connect-src 'self' https://live.dodopayments.com https://test.dodopayments.com https://*.stripe.com;
  img-src 'self' data: blob: https://*.stripe.com;
`;
```

**Required Domains**:
| Purpose | Domain |
|---------|--------|
| Checkout iframe | `checkout.dodopayments.com`, `test.checkout.dodopayments.com` |
| Overlay SDK | `cdn.jsdelivr.net` |
| API calls | `live.dodopayments.com`, `test.dodopayments.com` |
| Payment processing | `*.stripe.com` |

---

## 7. UI Customization

### Checkout Session Customization

```typescript
const session = await dodo.checkoutSessions.create({
  product_cart: [...],
  return_url: "...",
  customization: {
    theme: "dark", // "light", "dark", or "system"
    show_order_details: true,
    force_language: "en", // Language code
  },
  allow_currency_selection: true,
  allow_discount_code: true,
  allowed_payment_method_types: ["credit", "debit", "apple_pay", "google_pay"],
});
```

---

## 8. Comparison with Polar Iframe Checkout

| Aspect | Polar Iframe | Dodo Overlay |
|--------|--------------|--------------|
| Implementation | Manual iframe + Portal | SDK-provided overlay |
| Preloading | Custom CSS toggle pattern | Not built-in |
| Events | Cross-frame messaging (manual) | Built-in event callbacks |
| Close handling | Custom backdrop + ESC | Built-in `Checkout.close()` |
| Loading state | Custom spinner | SDK handles internally |
| Mobile support | Manual responsive | SDK handles |
| Apple Pay | Supported | NOT supported in overlay |

---

## Implementation Checklist

### Fixed-Price Products (Tool Listings)
- [ ] Create products in Dodo dashboard
- [ ] Store product IDs in env vars
- [ ] Implement `createDodoCheckout` server action
- [ ] Add checkout button/trigger to UI
- [ ] Create success page with payment verification
- [ ] Set up webhook handler for order.created

### Dynamic-Price Products (Advertisements)
- [ ] Create PWYW product in Dodo dashboard
- [ ] Set minimum price (e.g., $0.50)
- [ ] Implement `createAdCheckout` with calculated amount
- [ ] Pass ad selections as metadata
- [ ] Create success page with form for ad details
- [ ] Process metadata in webhook to create Ad records

### Overlay Checkout (Optional)
- [ ] Install `dodopayments-checkout` package
- [ ] Create `DodoCheckoutProvider`
- [ ] Add CSP headers for checkout domains
- [ ] Update buttons to use `openCheckout()` instead of redirect
- [ ] Test all event handlers
