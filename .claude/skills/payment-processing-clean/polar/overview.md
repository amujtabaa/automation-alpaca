# Polar.sh Integration Overview

Comprehensive knowledge base for Polar.sh payment processing, covering API integration, customer migration, and production-ready iframe checkout implementation.

---

## Documentation Files

| File | Purpose |
|------|---------|
| `api-reference.md` | Authentication, SDK, endpoints, benefits system |
| `customer-migration.md` | Migration strategies, common issues, testing |
| `iframe-checkout.md` | Iframe modal, CSP, preloading patterns |

---

## Quick Start

### API Integration
1. Load `api-reference.md`
2. Use `products: [PRODUCT_ID]` array (NOT `productPriceId`)
3. Hybrid approach: SDK for creation, raw fetch for confirmation

### Website Checkout
1. Load `iframe-checkout.md`
2. Single iframe pattern with CSS visibility toggle
3. Render via React Portal to document.body
4. Configure CSP with polar.sh, api.polar.sh, buy.polar.sh

### Customer Migration
1. Load `customer-migration.md`
2. Create FREE migration product ($0)
3. Programmatic checkout + confirmation
4. Archive migration product IMMEDIATELY after

---

## Platform Overview

Polar.sh is a Merchant of Record platform:

- **Products**: One-time & subscriptions
- **Benefits**: File downloads, license keys, GitHub access, Discord roles
- **Compliance**: Global tax handling
- **Checkout**: Sessions with Stripe integration

---

## Environment Variables

```bash
# API Authentication
POLAR_ACCESS_TOKEN=""              # Polar API access token
POLAR_ORGANIZATION_ID=""           # Polar org UUID
POLAR_WEBHOOK_SECRET=""            # Webhook signature verification

# Product IDs
POLAR_REGULAR_LISTING_ID=""        # Regular listing product
POLAR_FEATURED_LISTING_ID=""       # Featured listing product
POLAR_FEATURED_UPGRADE_ID=""       # Upgrade to featured
POLAR_LISTING_AD_ID=""             # Ad products...
POLAR_BANNER_AD_ID=""
POLAR_TOOLPAGE_AD_ID=""
POLAR_AD_BUNDLE_ID=""
```

---

## Key Patterns

### Dynamic Pricing (Ads)

Polar allows price override at checkout time:

```typescript
const checkout = await polar.checkouts.create({
  products: [PRODUCT_ID],
  prices: {
    [PRODUCT_ID]: [{
      amountType: "fixed",
      priceAmount: totalPriceInCents,  // Custom calculated amount
      priceCurrency: "usd"
    }]
  },
  metadata: { ads: JSON.stringify(selections) },
  successUrl: "/advertise/success?sessionId={CHECKOUT_ID}"
});
```

### Webhook Verification

```typescript
const signature = req.headers.get("webhook-signature");
const computedSignature = crypto
  .createHmac("sha256", webhookSecret)
  .update(body)
  .digest("hex");

if (signature !== computedSignature) {
  return new Response("Invalid signature", { status: 401 });
}
```

---

## Resources

- **Documentation**: https://polar.sh/docs
- **API Reference**: https://polar.sh/docs/api-reference
- **JavaScript SDK**: https://github.com/polarsource/polar-js
- **npm**: https://www.npmjs.com/package/@polar-sh/sdk
