# Dodo Payments Webhook Handling

## Overview

Dodo Payments uses the **Standard Webhooks** specification for webhook delivery and verification. This ensures compatibility with standard webhook libraries and industry best practices.

---

## Webhook Setup

### Dashboard Configuration

1. Navigate to Dodo Dashboard → Settings → Webhooks
2. Click "Add Webhook"
3. Enter your endpoint URL (e.g., `https://yoursite.com/api/dodo/webhooks`)
4. Select events to subscribe to
5. Copy the **Webhook Secret Key** for verification

### Environment Variable

```bash
DODO_PAYMENTS_WEBHOOK_KEY="whsec_xxx..."
```

---

## Webhook Events

### Payment Events

| Event | Description |
|-------|-------------|
| `payment.succeeded` | One-time payment completed successfully |
| `payment.failed` | Payment attempt failed |

### Subscription Events

| Event | Description |
|-------|-------------|
| `subscription.created` | New subscription created |
| `subscription.renewed` | Subscription successfully renewed |
| `subscription.updated` | Subscription modified |
| `subscription.canceled` | Subscription canceled |

### Other Events

| Event | Description |
|-------|-------------|
| `refund.created` | Refund issued |
| `dispute.created` | Dispute/chargeback initiated |
| `license_key.created` | License key generated |

---

## Webhook Payload Structure

```json
{
  "business_id": "biz_xxx",
  "type": "payment.succeeded",
  "timestamp": "2025-01-15T10:30:00Z",
  "data": {
    "payment_id": "pay_xxx",
    "customer": {
      "customer_id": "cus_xxx",
      "email": "customer@example.com",
      "name": "John Doe"
    },
    "total_amount": 2900,
    "currency": "USD",
    "status": "succeeded",
    "metadata": {
      "tool_slug": "my-tool",
      "product_type": "featured"
    },
    "product_cart": [
      {
        "product_id": "prod_xxx",
        "quantity": 1,
        "amount": 2900
      }
    ]
  }
}
```

**Note**: For subscription renewals, `payment.succeeded` includes `subscription_id` instead of `product_id`.

---

## Webhook Headers

Every webhook request includes these headers:

| Header | Description |
|--------|-------------|
| `webhook-id` | Unique identifier for idempotency |
| `webhook-signature` | HMAC signature for verification |
| `webhook-timestamp` | Unix timestamp (seconds) of dispatch |

---

## Signature Verification

### Using Standard Webhooks Library (Recommended)

```typescript
// app/api/dodo/webhooks/route.ts
import { Webhook } from "standardwebhooks";
import { headers } from "next/headers";
import { env } from "~/env";

const webhook = new Webhook(env.DODO_PAYMENTS_WEBHOOK_KEY);

export async function POST(request: Request) {
  const headersList = headers();
  const rawBody = await request.text();

  const webhookHeaders = {
    "webhook-id": headersList.get("webhook-id") || "",
    "webhook-signature": headersList.get("webhook-signature") || "",
    "webhook-timestamp": headersList.get("webhook-timestamp") || "",
  };

  try {
    // Verify signature - throws if invalid
    webhook.verify(rawBody, webhookHeaders);
  } catch (error) {
    console.error("Webhook signature verification failed:", error);
    return new Response("Invalid signature", { status: 401 });
  }

  const payload = JSON.parse(rawBody);

  // Process the event
  await processWebhookEvent(payload);

  return new Response("OK", { status: 200 });
}
```

### Manual Verification

```typescript
import crypto from "crypto";

function verifyWebhookSignature(
  rawBody: string,
  signature: string,
  timestamp: string,
  secret: string
): boolean {
  const signedContent = `${webhookId}.${timestamp}.${rawBody}`;
  const expectedSignature = crypto
    .createHmac("sha256", secret)
    .update(signedContent)
    .digest("base64");

  // Signature format: "v1,<base64-signature>"
  const providedSignature = signature.split(",")[1];

  return crypto.timingSafeEqual(
    Buffer.from(expectedSignature),
    Buffer.from(providedSignature)
  );
}
```

---

## Event Processing

### Complete Handler Implementation

```typescript
// app/api/dodo/webhooks/route.ts
import { Webhook } from "standardwebhooks";
import { headers } from "next/headers";
import { revalidateTag } from "next/cache";
import { prisma } from "~/server/db";
import { env } from "~/env";

const webhook = new Webhook(env.DODO_PAYMENTS_WEBHOOK_KEY);

interface DodoWebhookPayload {
  business_id: string;
  type: string;
  timestamp: string;
  data: {
    payment_id?: string;
    subscription_id?: string;
    customer: {
      customer_id: string;
      email: string;
      name: string;
    };
    total_amount: number;
    currency: string;
    status: string;
    metadata?: Record<string, string>;
    product_cart?: Array<{
      product_id: string;
      quantity: number;
      amount: number;
    }>;
  };
}

export async function POST(request: Request) {
  const headersList = headers();
  const rawBody = await request.text();

  const webhookHeaders = {
    "webhook-id": headersList.get("webhook-id") || "",
    "webhook-signature": headersList.get("webhook-signature") || "",
    "webhook-timestamp": headersList.get("webhook-timestamp") || "",
  };

  try {
    webhook.verify(rawBody, webhookHeaders);
  } catch (error) {
    console.error("[Dodo Webhook] Invalid signature:", error);
    return new Response("Invalid signature", { status: 401 });
  }

  const payload: DodoWebhookPayload = JSON.parse(rawBody);
  console.log(`[Dodo Webhook] Event: ${payload.type}`);

  try {
    switch (payload.type) {
      case "payment.succeeded":
        await handlePaymentSucceeded(payload);
        break;

      case "subscription.created":
        await handleSubscriptionCreated(payload);
        break;

      case "subscription.canceled":
        await handleSubscriptionCanceled(payload);
        break;

      case "refund.created":
        await handleRefundCreated(payload);
        break;

      default:
        console.log(`[Dodo Webhook] Unhandled event: ${payload.type}`);
    }
  } catch (error) {
    console.error(`[Dodo Webhook] Processing error:`, error);
    // Return 200 to prevent retries for processing errors
    // Log the error for manual review
  }

  return new Response("OK", { status: 200 });
}

async function handlePaymentSucceeded(payload: DodoWebhookPayload) {
  const { metadata } = payload.data;

  // Tool listing purchase
  if (metadata?.tool_slug) {
    const toolSlug = metadata.tool_slug;
    const productType = metadata.product_type;

    if (productType === "featured" || productType === "upgrade") {
      await prisma.tool.update({
        where: { slug: toolSlug },
        data: { isFeatured: true },
      });

      revalidateTag("tools");
      revalidateTag(`tool-${toolSlug}`);

      console.log(`[Dodo Webhook] Updated tool ${toolSlug} to featured`);

      // Send notification emails
      // await notifySubmitterOfPremiumTool(tool);
      // await notifyAdminOfPremiumTool(tool);
    }
  }

  // Ad purchase (ads created in success page form, not here)
  if (metadata?.ads) {
    console.log(`[Dodo Webhook] Ad purchase logged: ${payload.data.payment_id}`);
    // Ad record creation happens in success page form submission
    // This webhook is just for logging/verification
  }
}

async function handleSubscriptionCreated(payload: DodoWebhookPayload) {
  // Handle subscription creation if needed
  console.log(`[Dodo Webhook] Subscription created: ${payload.data.subscription_id}`);
}

async function handleSubscriptionCanceled(payload: DodoWebhookPayload) {
  // Handle subscription cancellation
  console.log(`[Dodo Webhook] Subscription canceled: ${payload.data.subscription_id}`);
}

async function handleRefundCreated(payload: DodoWebhookPayload) {
  // Handle refund if needed
  console.log(`[Dodo Webhook] Refund created for: ${payload.data.payment_id}`);
}
```

---

## Retry Logic

Dodo automatically retries failed webhook deliveries:

| Attempt | Delay | Cumulative Time |
|---------|-------|-----------------|
| 1 | Immediate | 0 |
| 2 | 5 seconds | 5s |
| 3 | 5 minutes | 5m 5s |
| 4 | 30 minutes | 35m 5s |
| 5 | 2 hours | 2h 35m |
| 6 | 5 hours | 7h 35m |
| 7 | 10 hours | 17h 35m |
| 8 | 10 hours | 27h 35m |

**Maximum**: 8 retry attempts

---

## Idempotency

Use the `webhook-id` header to prevent duplicate processing:

```typescript
// Store processed webhook IDs (use Redis/DB in production)
const processedWebhooks = new Set<string>();

export async function POST(request: Request) {
  const webhookId = headers().get("webhook-id");

  // Check for duplicate
  if (webhookId && processedWebhooks.has(webhookId)) {
    console.log(`[Dodo Webhook] Duplicate ignored: ${webhookId}`);
    return new Response("Already processed", { status: 200 });
  }

  // ... process webhook ...

  // Mark as processed
  if (webhookId) {
    processedWebhooks.add(webhookId);
  }

  return new Response("OK", { status: 200 });
}
```

**Production Pattern**: Store `webhook-id` in database with TTL of 48 hours.

---

## Best Practices

1. **Return 2xx Immediately**: Process async to avoid timeouts
2. **Implement Idempotency**: Handle duplicate deliveries gracefully
3. **Use HTTPS**: Required for production endpoints
4. **Verify Signatures**: Always validate before processing
5. **Log Everything**: Store raw payloads for debugging
6. **Handle Gracefully**: Return 200 even on processing errors to prevent retries
7. **Set Up Monitoring**: Configure email alerts for delivery failures

---

## Testing Webhooks

### Local Development

Use a tunnel service like ngrok:

```bash
ngrok http 3000
# Copy the HTTPS URL → Configure in Dodo dashboard
```

### Test Mode

Dodo's test mode sends webhooks for test payments. Use `test.dodopayments.com` API in development.

### Manual Retry

Failed webhooks can be retried from the Dodo Dashboard → Webhooks → Logs tab.

---

## Comparison with Polar Webhooks

| Aspect | Polar | Dodo |
|--------|-------|------|
| Specification | Custom | Standard Webhooks |
| Verification | Manual HMAC SHA256 | Library or manual |
| Signature Header | `webhook-signature` | `webhook-signature` |
| Timestamp Header | N/A | `webhook-timestamp` |
| ID Header | N/A | `webhook-id` |
| Retry Attempts | Unknown | 8 |
| Event Format | `order.created`, etc. | `payment.succeeded`, etc. |
| Library Support | Manual | standardwebhooks npm |

---

## Troubleshooting

### "Invalid signature" Error
- Verify `DODO_PAYMENTS_WEBHOOK_KEY` matches dashboard secret
- Ensure raw body is not modified before verification
- Check for character encoding issues

### Webhooks Not Arriving
- Verify endpoint URL is publicly accessible
- Check Dodo dashboard webhook logs for errors
- Ensure endpoint returns 2xx status

### Duplicate Events
- Implement idempotency using `webhook-id`
- Check retry logs in Dodo dashboard

### Out-of-Order Events
- Design handlers to work regardless of event order
- Use timestamps to track latest state
