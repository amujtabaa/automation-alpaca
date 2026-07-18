# Dodo Payments Integration Overview

Comprehensive knowledge base for Dodo Payments as a Merchant of Record platform, covering API integration, checkout implementation, and production-ready patterns.

---

## Documentation Files

| File | Purpose |
|------|---------|
| `api-reference.md` | SDK, products API, checkout sessions, error handling |
| `checkout-implementation.md` | Sessions, overlay checkout, PWYW dynamic pricing |
| `webhook-handling.md` | Standard Webhooks, signature verification, events |
| `datafast-integration.md` | Revenue attribution with DataFast analytics |

---

## Quick Start

### Checkout Implementation
1. Load `checkout-implementation.md`
2. Use Checkout Sessions API (recommended)
3. For dynamic pricing: Create PWYW product, pass `amount` in cents
4. Configure `return_url` for success redirect

### Webhook Processing
1. Load `webhook-handling.md`
2. Use Standard Webhooks library (`standardwebhooks`)
3. Return 2xx immediately, process async
4. Implement idempotency using `webhook-id` header

### DataFast Attribution
1. Load `datafast-integration.md`
2. Capture `datafast_visitor_id` cookie in checkout metadata
3. Configure webhook transformation in Dodo dashboard

---

## Platform Overview

Dodo Payments is a Merchant of Record for digital businesses:

- **Global**: 190+ countries, 50+ currencies, 25+ payment methods
- **Compliance**: Taxes, fraud protection, billing handled
- **Developer-First**: TypeScript SDK, Standard Webhooks
- **Pricing**: ~4% + 40¢ per transaction (no monthly fees)

---

## Environment Variables

```bash
# API Authentication
DODO_PAYMENTS_API_KEY=""              # From Dashboard > Developer > API
DODO_PAYMENTS_WEBHOOK_KEY=""          # From Dashboard > Settings > Webhooks

# Environment Mode
DODO_PAYMENTS_MODE="test"             # "test" or "live"

# Product IDs
DODO_REGULAR_LISTING_ID=""            # Regular listing product
DODO_FEATURED_LISTING_ID=""           # Featured listing product
DODO_FEATURED_UPGRADE_ID=""           # Featured upgrade product
DODO_AD_BUNDLE_ID=""                  # PWYW product for dynamic ad pricing
```

---

## Key Differences from Polar

| Aspect | Polar | Dodo |
|--------|-------|------|
| **Dynamic Pricing** | `prices` override | PWYW product + `amount` |
| **Embedded Checkout** | Manual iframe | Overlay SDK |
| **Webhooks** | Custom HMAC | Standard Webhooks |
| **Product Cart** | `products: [id]` | `product_cart: [{product_id, quantity}]` |
| **Success Params** | `{CHECKOUT_ID}` | `?payment_id=xxx&status=xxx` |
| **Benefits** | Built-in | N/A |

---

## Implementation Checklist

### Setup
- [ ] Create Dodo Payments account
- [ ] Create products (fixed price + PWYW for ads)
- [ ] Generate API key
- [ ] Configure webhook endpoint

### Code
- [ ] Install: `bun add dodopayments dodopayments-checkout standardwebhooks`
- [ ] Create `services/dodo.ts` client
- [ ] Add env vars to `env.ts` schema
- [ ] Implement checkout server actions
- [ ] Create webhook handler route
- [ ] Build overlay checkout component (optional)

### Testing
- [ ] Checkout session creation
- [ ] Overlay checkout UX
- [ ] PWYW custom amounts
- [ ] Webhook signature verification
- [ ] Success page flow
- [ ] DataFast attribution

---

## Resources

- **Documentation**: https://docs.dodopayments.com
- **API Reference**: https://docs.dodopayments.com/api-reference
- **TypeScript SDK**: https://www.npmjs.com/package/dodopayments
- **Checkout SDK**: https://www.npmjs.com/package/dodopayments-checkout
- **GitHub**: https://github.com/dodopayments
