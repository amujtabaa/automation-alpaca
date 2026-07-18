# Domain 2: Payment Processing Deep Dive

**Focus:** Polar integration, subscription management, webhooks, tier enforcement

---

## Questions to Answer

### Current Implementation
- What payment provider does the kit use?
- Is there a payment abstraction layer?
- What methods need implementation?
- How are subscriptions stored?

### Polar Migration
- Can we swap providers cleanly?
- What events need webhook handlers?
- How do checkout flows work?
- Customer portal implementation?

---

## Files to Review

```
/lib/payments/
/app/api/webhooks/stripe/ or /polar/
/app/(marketing)/pricing/
/components/pricing/
Database tables: billing_*, subscriptions, etc.
```

---

## Polar Implementation Requirements

### SDK Installation
```bash
bun add @polar-sh/sdk
```

### Environment Variables
```bash
POLAR_ACCESS_TOKEN=
POLAR_WEBHOOK_SECRET=
POLAR_ORGANIZATION_ID=
POLAR_SERVER=sandbox # or production
```

### Core Methods to Implement

```typescript
// If there's a PaymentGateway abstract class:
class PolarGateway extends PaymentGateway {
  // Customer management
  createGatewayCustomer(email, metadata)

  // Checkout
  createGatewayCheckoutSession(customerId, priceId, successUrl, cancelUrl)

  // Subscriptions
  getGatewaySubscription(subscriptionId)
  cancelGatewaySubscription(subscriptionId)

  // Webhooks
  handleGatewayWebhook(payload, signature)
}
```

### Webhook Events to Handle

| Polar Event | Action |
|-------------|--------|
| `checkout.created` | Create pending subscription |
| `subscription.created` | Activate subscription |
| `subscription.updated` | Update tier/status |
| `subscription.canceled` | Mark as cancelled |
| `order.paid` | Record payment |

### Checkout Flow
```typescript
// 1. Create checkout session
const checkout = await polar.checkouts.create({
  productId: 'prod_xxx',
  successUrl: `${baseUrl}/success?session_id={CHECKOUT_ID}`,
  customerEmail: user.email,
});

// 2. Redirect to Polar
redirect(checkout.url);

// 3. Handle webhook on completion
// 4. Update database with subscription
```

---

## Tier Enforcement Pattern

```typescript
const TIER_LIMITS = {
  starter: { subreddits: 3, keywords: 10 },
  growth: { subreddits: 10, keywords: 50 },
  pro: { subreddits: 25, keywords: 150 },
  scale: { subreddits: 100, keywords: 500 },
};

function checkLimit(workspace, resource) {
  const tier = workspace.subscription_tier || 'starter';
  const limit = TIER_LIMITS[tier][resource];
  const current = workspace[`${resource}_count`];
  return current < limit;
}
```

---

## Output Checklist

- [ ] PolarGateway class (if abstract exists)
- [ ] Webhook handler endpoint
- [ ] Checkout flow UI updates
- [ ] Tier limits configuration
- [ ] Database schema for subscriptions
- [ ] Test scenarios list

---
