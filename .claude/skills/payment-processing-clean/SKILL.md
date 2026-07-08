---
name: payment-processing
description: Comprehensive payment processor integration knowledge base covering Polar.sh and Dodo Payments. Use when implementing checkout flows, migrating between processors, configuring webhooks, handling dynamic pricing, or troubleshooting payment issues.
---

> **TEMPLATE VERSION**: This skill contains placeholder values (e.g., `<YOUR_POLAR_ACCESS_TOKEN>`, `<YOUR_POLAR_PRODUCT_ID>`). Replace all `<YOUR_*>` placeholders with your actual credentials before use. Never commit real credentials to version control.

# Payment Processing Skill

Central knowledge base for all payment processor integrations. Load specific documentation files based on which provider and task you're working on.

---

## Directory Structure

```
payment-processing/
├── SKILL.md                           # This file - overview & routing
│
├── polar/                             # Polar.sh (Current provider)
│   ├── overview.md                    # Platform overview, env vars, quick start
│   ├── api-reference.md               # SDK, endpoints, benefits system
│   ├── customer-migration.md          # Migration patterns, common issues
│   └── iframe-checkout.md             # Iframe modal, CSP, preloading
│
└── dodo-payments/                     # Dodo Payments (Migration target)
    ├── overview.md                    # Platform overview, env vars, comparison
    ├── api-reference.md               # SDK, products API, error handling
    ├── checkout-implementation.md     # Sessions, overlay, PWYW dynamic pricing
    ├── webhook-handling.md            # Standard Webhooks, signature verification
    └── datafast-integration.md        # Revenue attribution setup
```

---

## Provider Comparison

| Feature | Polar.sh | Dodo Payments |
|---------|----------|---------------|
| **Type** | Merchant of Record | Merchant of Record |
| **Coverage** | Global | 190+ countries, 50+ currencies |
| **Fees** | ~4% + fees | ~4% + 40¢ |
| **SDK** | `@polar-sh/sdk` | `dodopayments` |
| **Embedded Checkout** | Manual iframe | Overlay SDK |
| **Dynamic Pricing** | `prices` object override | PWYW product + `amount` |
| **Webhooks** | Custom HMAC SHA256 | Standard Webhooks spec |
| **Benefits System** | Built-in (files, licenses) | N/A |
| **DataFast Integration** | Manual | Built-in webhook transform |

---

## Provider Strengths

### Polar.sh
- **Benefits/Entitlements**: Built-in file downloads, license keys, GitHub access
- **Price Override**: Can override any product's price at checkout time
- **Simpler SDK**: Fewer configuration options, faster setup
- **Best for**: Products with digital deliverables, simple checkout flows

### Dodo Payments
- **Global Coverage**: More payment methods, currencies, localized checkout
- **Overlay Checkout**: SDK-provided embedded experience with events
- **Standard Webhooks**: Industry-standard verification, library support
- **DataFast Built-in**: Native revenue attribution integration
- **Best for**: Global audience, complex checkout requirements

---

## Loading Documentation

### For Polar.sh Work

```
# Quick start / overview
Read: .claude/skills/payment-processing/polar/overview.md

# API and SDK usage
Read: .claude/skills/payment-processing/polar/api-reference.md

# Customer migration
Read: .claude/skills/payment-processing/polar/customer-migration.md

# Iframe checkout implementation
Read: .claude/skills/payment-processing/polar/iframe-checkout.md
```

### For Dodo Payments Work

```
# Quick start / overview
Read: .claude/skills/payment-processing/dodo-payments/overview.md

# API and SDK usage
Read: .claude/skills/payment-processing/dodo-payments/api-reference.md

# Checkout implementation (sessions, overlay, PWYW)
Read: .claude/skills/payment-processing/dodo-payments/checkout-implementation.md

# Webhook handling
Read: .claude/skills/payment-processing/dodo-payments/webhook-handling.md

# DataFast revenue attribution
Read: .claude/skills/payment-processing/dodo-payments/datafast-integration.md
```

---

## Project Integration Points

### Tool Listing Purchases
- Regular Listing ($9)
- Featured Listing ($29)
- Featured Upgrade ($20)
- **Flow**: Fixed-price checkout → Webhook updates `tool.isFeatured`

### Advertisement Purchases
- Listing Ad, Banner Ad, Tool Page Ad
- **Flow**: Dynamic pricing → Multi-product checkout → Success page form
- **Polar**: Uses `prices` override for custom amount
- **Dodo**: Uses PWYW product with `amount` in cents

### Key Implementation Files
| Purpose | File |
|---------|------|
| SDK Client | `services/polar.ts` or `services/dodo.ts` |
| Product Checkout | `server/web/products/actions.ts` |
| Ad Checkout | `server/web/ads/actions.ts` |
| Webhook Handler | `app/api/[provider]/webhooks/route.ts` |
| Checkout Modal | `components/web/[provider]-checkout-modal.tsx` |

---

## When to Load This Skill

- Implementing payment checkout flows
- Adding/modifying products or pricing
- Setting up or debugging webhooks
- Migrating between payment processors
- Configuring CSP for embedded checkout
- Implementing dynamic/calculated pricing
- Setting up revenue attribution (DataFast)
