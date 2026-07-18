## Authentication

**Organization Access Token**:
- Generate from: Polar Dashboard → Organization Settings → Access Tokens
- Required scopes: `checkouts:write`, `customers:write`, `products:write`
- Usage: `Authorization: Bearer <token>`

**Example Token**:
```
Token: <YOUR_POLAR_ACCESS_TOKEN>
Scopes: checkouts:write, customers:write, products:write (or all scopes)
```

---

## Products & Pricing

### Example Migration Product

**Product ID**: `<YOUR_POLAR_PRODUCT_ID>`
**Price ID**: `<YOUR_POLAR_PRICE_ID>`
**Price**: $0 (FREE) - for customer migrations
**Checkout Link**: `<YOUR_POLAR_CHECKOUT_LINK>`

**Purpose**: One-time migration of existing customers from another platform
**Benefit Attached**: File Download or other benefits matching original product

---

## SDK Installation

### Node.js/TypeScript
```bash
pnpm add @polar-sh/sdk -w  # For pnpm workspaces
npm install @polar-sh/sdk  # For standard npm projects
```

### Python
```bash
pip install polar-sdk
```

---

## API Endpoints

### Base URLs
- Production: `https://api.polar.sh`
- Sandbox: `https://sandbox-api.polar.sh`

### Key Endpoints

#### 1. Create Checkout Session
```
POST /v1/checkouts
Authorization: Bearer <org_token>

Body:
{
  "products": ["<product_id>"],  // Array of product UUIDs
  "customer_email": "customer@example.com",
  "customer_name": "John Doe",
  "customer_billing_address": {
    "country": "US"
  },
  "success_url": "https://yoursite.com/success"
}

Response: {
  "id": "<checkout_id>",
  "client_secret": "<client_secret>",
  "status": "open",
  "url": "https://checkout.polar.sh/...",
  ...
}
```

**Note**: For price-specific checkouts, use `product_price_id` instead of `products`.

#### 2. Confirm Checkout Session (Client-Side)
```
POST /v1/checkouts/client/{client_secret}/confirm
Authorization: Bearer <org_token>

Body (for FREE products):
{
  "customer_name": "John Doe",
  "customer_email": "customer@example.com",
  "customer_billing_address": {
    "country": "US"
  }
}

Body (for PAID products):
{
  "confirmation_token_id": "<stripe_token>",  // Required!
  "customer_name": "John Doe",
  "customer_email": "customer@example.com",
  "customer_billing_address": {
    "country": "US"
  }
}

Response: {
  "id": "<checkout_id>",
  "status": "confirmed" | "succeeded",
  "customer_id": "<customer_id>",
  "customer_session_token": "<session_token>",
  ...
}
```

**CRITICAL**: For paid products, `confirmation_token_id` is **required**. For free products, it may be optional.

#### 3. Get Checkout Session
```
GET /v1/checkouts/{id}
Authorization: Bearer <org_token>

Response: Full checkout object with current status
```

---

## SDK Usage Examples

### Node.js/TypeScript

**CRITICAL DISCOVERY**: The SDK requires `products: [PRODUCT_ID]` (array of product IDs), NOT `productPriceId: "PRICE_ID"` for checkout creation.

```typescript
import { Polar } from "@polar-sh/sdk";

const polar = new Polar({
  accessToken: "polar_oat_..."
});

// ✅ CORRECT: Create checkout with products array
const checkout = await polar.checkouts.create({
  products: [PRODUCT_ID],  // Array of product IDs - THIS IS KEY!
  customerEmail: "customer@example.com",
  customerName: "John Doe",
  customerBillingAddress: {
    country: "US"
  },
  successUrl: "https://yoursite.com/success"
});

console.log(checkout.id);
console.log(checkout.clientSecret);

// Confirm checkout programmatically using raw fetch (SDK method not fully documented)
const response = await fetch(
  `https://api.polar.sh/v1/checkouts/client/${checkout.clientSecret}/confirm`,
  {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${POLAR_ACCESS_TOKEN}`
    },
    body: JSON.stringify({
      customer_name: customer.name,
      customer_email: customer.email,
      customer_billing_address: {
        country: customer.country
      }
    })
  }
);

const result = await response.json();
// Returns: { customer_id: "...", status: "confirmed", ... }
```

**Why Hybrid Approach?**
- SDK for checkout creation: Handles validation and type safety
- Raw fetch for confirmation: Full control over request/response, better documented endpoint behavior

### Python

```python
from polar_sdk import Polar

polar = Polar(access_token="polar_oat_...")

# Create checkout
checkout = polar.checkouts.create(
    product_price_id="price_id_here",
    customer_email="customer@example.com",
    customer_name="John Doe",
    customer_billing_address={"country": "US"},
    success_url="https://yoursite.com/success"
)

print(checkout.id)
print(checkout.client_secret)

# Confirm checkout
confirmed = polar.checkouts.client_confirm(
    client_secret=checkout.client_secret,
    customer_email="customer@example.com",
    customer_billing_address={"country": "US"}
)
```

---

## Benefits & Entitlements

### How Benefits Work

**Architecture**:
```
Product → Has Benefit(s) → Order Created → Benefit Grant Issued
```

**Benefits CANNOT be granted directly to customers**. They are always tied to products and automatically granted when an order is completed.

### Available Benefit Types

1. **License Keys**: Auto-generated, revocable activation keys
2. **File Downloads**: Up to 10GB with download tracking
3. **GitHub Access**: Repository invites and permissions
4. **Discord Access**: Role assignment and server invites
5. **Custom**: Webhooks for custom benefit logic

---
