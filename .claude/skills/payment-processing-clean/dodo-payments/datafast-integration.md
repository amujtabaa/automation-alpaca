# DataFast Revenue Attribution with Dodo Payments

## Overview

DataFast is a revenue-first analytics platform that integrates with Dodo Payments to attribute revenue to marketing channels. This enables identifying which traffic sources (organic, paid ads, referrals) drive actual paying customers, not just visitors.

**Why This Matters**: Standard analytics show traffic → DataFast shows traffic that converts to revenue.

---

## How It Works

```
User visits site → DataFast sets visitor cookie
       ↓
User browses → DataFast tracks page/scroll/click events
       ↓
User clicks checkout → Visitor ID captured in payment metadata
       ↓
Payment succeeds → Dodo webhook fires
       ↓
Webhook transformation → Sends payment + visitor ID to DataFast
       ↓
DataFast dashboard → Shows revenue attributed to traffic source
```

---

## Implementation Steps

### Step 1: Ensure DataFast Tracking is Active

The DataFast tracking script must be installed on your site. This creates the `datafast_visitor_id` cookie.

**Verify in browser**:
```javascript
// Check cookie exists
document.cookie.includes('datafast_visitor_id') // true
```

See `analytics` skill for full DataFast setup instructions.

---

### Step 2: Capture Visitor ID in Checkout

When creating a checkout session, extract the DataFast visitor ID from cookies and store in metadata:

**Server Action (Next.js App Router)**:
```typescript
"use server";

import { cookies } from "next/headers";
import DodoPayments from "dodopayments";
import { env } from "~/env";

const dodo = new DodoPayments({
  bearerToken: env.DODO_PAYMENTS_API_KEY,
  environment: env.DODO_PAYMENTS_MODE === "test" ? "test_mode" : "live_mode",
});

export async function createCheckoutWithAttribution(productId: string) {
  // Get DataFast visitor ID from cookie
  const cookieStore = cookies();
  const datafastVisitorId = cookieStore.get("datafast_visitor_id")?.value;

  const session = await dodo.checkoutSessions.create({
    product_cart: [{ product_id: productId, quantity: 1 }],
    return_url: `${env.NEXT_PUBLIC_SITE_URL}/checkout/success`,
    metadata: {
      // Include visitor ID for revenue attribution
      datafast_visitor_id: datafastVisitorId || "",
      // Other metadata...
    },
  });

  return {
    url: session.checkout_url,
    sessionId: session.session_id,
  };
}
```

**Key Points**:
- Capture visitor ID server-side via `cookies()` API
- Store in `metadata.datafast_visitor_id`
- Handle missing cookie gracefully (empty string)

---

### Step 3: Configure Dodo Webhook Integration

Dodo Payments has built-in DataFast integration through webhook transformations.

**Dashboard Setup**:
1. Navigate to Dodo Dashboard → Settings → Webhooks
2. Click "Add Endpoint"
3. Select **DataFast** from the integration dropdown
4. Enter your DataFast API Key (from DataFast dashboard → Website Settings → API)
5. Configure the transformation code (see below)
6. Test with sample payload
7. Activate the webhook

---

### Step 4: Webhook Transformation Code

The transformation forwards payment data to DataFast when a visitor ID exists:

```javascript
function handler(webhook) {
  // Only process successful payments
  if (webhook.eventType === "payment.succeeded") {
    const payment = webhook.payload.data;

    // Only send to DataFast if we have a visitor ID
    if (payment.metadata?.datafast_visitor_id) {
      // Set DataFast API endpoint
      webhook.url = "https://datafa.st/api/v1/payments";

      // Transform payload for DataFast API
      webhook.payload = {
        amount: payment.total_amount / 100, // Convert cents to dollars
        currency: payment.currency,
        transaction_id: payment.payment_id,
        datafast_visitor_id: payment.metadata.datafast_visitor_id,
      };

      return webhook;
    } else {
      // No visitor ID - skip DataFast (payment still processed normally)
      return null;
    }
  }

  // Non-payment events pass through unchanged
  return webhook;
}
```

---

## Currency Handling

DataFast expects amounts in standard currency units (e.g., dollars, euros).

**Standard Currencies** (USD, EUR, GBP, etc.):
```javascript
amount: payment.total_amount / 100 // $29.00 = 2900 cents / 100
```

**Zero-Decimal Currencies** (JPY, KRW, VND, etc.):
```javascript
// For these currencies, DON'T divide by 100
const zeroDecimalCurrencies = ["JPY", "KRW", "CLP", "VND", "UGX", "MGA"];

const amount = zeroDecimalCurrencies.includes(payment.currency)
  ? payment.total_amount
  : payment.total_amount / 100;
```

---

## Subscription Revenue Attribution

For recurring payments, include subscription context:

```javascript
function handler(webhook) {
  if (webhook.eventType === "payment.succeeded") {
    const payment = webhook.payload.data;

    if (payment.metadata?.datafast_visitor_id) {
      webhook.url = "https://datafa.st/api/v1/payments";
      webhook.payload = {
        amount: payment.total_amount / 100,
        currency: payment.currency,
        transaction_id: payment.payment_id,
        datafast_visitor_id: payment.metadata.datafast_visitor_id,
        // Optional: subscription context
        subscription_id: payment.subscription_id || null,
        is_recurring: !!payment.subscription_id,
      };
      return webhook;
    }
    return null;
  }
  return webhook;
}
```

---

## Testing the Integration

### 1. Verify Cookie Capture

```javascript
// Browser console on your site
console.log(document.cookie.includes('datafast_visitor_id'));
// Should be: true
```

### 2. Verify Metadata in Checkout

After creating a checkout, check the Dodo dashboard:
- Go to Payments → Click a test payment
- Check `metadata` field contains `datafast_visitor_id`

### 3. Test Webhook Transformation

Use Dodo's webhook testing feature:
- Go to Webhooks → Your DataFast endpoint → Logs
- Click "Send Test" with sample payment.succeeded event
- Verify 200 response from DataFast

### 4. Verify in DataFast Dashboard

After successful test payment:
- Go to DataFast dashboard → Payments tab
- New payment should appear with traffic source attribution

---

## Troubleshooting

### Payments Not Appearing in DataFast

| Issue | Solution |
|-------|----------|
| Missing visitor ID | Check DataFast script is installed; verify cookie exists |
| Metadata empty | Ensure `cookies()` is called server-side, not client |
| Webhook not firing | Check Dodo webhook logs for errors |
| Transformation error | Validate JSON structure matches DataFast API |
| Wrong amount | Check currency decimal handling |

### Attribution Not Working

| Issue | Solution |
|-------|----------|
| All "Direct" traffic | DataFast script may be blocked; check proxy setup |
| Visitor ID mismatch | Ensure same visitor ID from browse to purchase |
| Cookie expiration | DataFast cookies last 2 years by default |

### Webhook Errors

Check Dodo Dashboard → Webhooks → Logs:
- **401 Unauthorized**: Invalid DataFast API key
- **400 Bad Request**: Malformed payload (check transformation)
- **500 Server Error**: DataFast service issue (retry)

---

## Complete Integration Example

**Server Action**:
```typescript
// server/actions/checkout.ts
"use server";

import { cookies } from "next/headers";
import DodoPayments from "dodopayments";
import { env } from "~/env";

const dodo = new DodoPayments({
  bearerToken: env.DODO_PAYMENTS_API_KEY,
  environment: env.DODO_PAYMENTS_MODE === "test" ? "test_mode" : "live_mode",
});

export async function createProductCheckout(
  productId: string,
  metadata?: Record<string, string>
) {
  const cookieStore = cookies();
  const datafastVisitorId = cookieStore.get("datafast_visitor_id")?.value;

  const session = await dodo.checkoutSessions.create({
    product_cart: [{ product_id: productId, quantity: 1 }],
    return_url: `${env.NEXT_PUBLIC_SITE_URL}/checkout/success`,
    allow_discount_code: true,
    metadata: {
      ...metadata,
      datafast_visitor_id: datafastVisitorId || "",
    },
  });

  return {
    url: session.checkout_url,
    sessionId: session.session_id,
  };
}
```

**Webhook Transformation** (in Dodo Dashboard):
```javascript
function handler(webhook) {
  if (webhook.eventType === "payment.succeeded") {
    const payment = webhook.payload.data;
    if (payment.metadata?.datafast_visitor_id) {
      webhook.url = "https://datafa.st/api/v1/payments";
      webhook.payload = {
        amount: payment.total_amount / 100,
        currency: payment.currency,
        transaction_id: payment.payment_id,
        datafast_visitor_id: payment.metadata.datafast_visitor_id,
      };
      return webhook;
    }
    return null;
  }
  return webhook;
}
```

---

## Best Practices

1. **Capture Early**: Get visitor ID at checkout creation, not payment completion
2. **Handle Missing IDs**: Gracefully handle cases where cookie doesn't exist
3. **Test Mode**: Use Dodo test mode for integration testing
4. **Monitor Logs**: Regularly check Dodo webhook logs for failures
5. **Idempotent API**: DataFast's Payment API safely handles retry attempts

---

## Related Documentation

- **DataFast Setup**: Load `analytics` skill for full tracking implementation
- **Dodo Checkout**: See `checkout-implementation.md` for session creation
- **Dodo Webhooks**: See `webhook-handling.md` for webhook setup
