# Dodo Payments API Reference

## Authentication

**API Key**:
- Generate from: Dodo Dashboard → Developer → API section
- Format: Bearer token authentication
- Environment variable: `DODO_PAYMENTS_API_KEY`

**Usage**:
```typescript
Authorization: Bearer <api_key>
```

---

## SDK Installation

### TypeScript/Node.js
```bash
# Main SDK
npm install dodopayments
# or
bun add dodopayments

# Checkout overlay SDK (optional, for embedded checkout)
npm install dodopayments-checkout
```

### Python
```bash
pip install dodopayments
```

### Other Languages
SDKs available for: Go, PHP (beta), Ruby, Java, Kotlin, C# (beta)

---

## SDK Initialization

### TypeScript

```typescript
import DodoPayments from 'dodopayments';

const dodo = new DodoPayments({
  bearerToken: process.env.DODO_PAYMENTS_API_KEY!,
  environment: 'test_mode', // 'test_mode' or 'live_mode' (default)
});
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `bearerToken` | string | - | API key (required) |
| `environment` | string | `'live_mode'` | `'test_mode'` for development |
| `maxRetries` | number | 2 | Automatic retry count |
| `timeout` | number | 60000 | Request timeout (ms) |
| `logLevel` | string | `'warn'` | `'debug'` \| `'info'` \| `'warn'` \| `'error'` \| `'off'` |

---

## API Base URLs

| Environment | URL |
|-------------|-----|
| **Production** | `https://live.dodopayments.com` |
| **Test/Sandbox** | `https://test.dodopayments.com` |

---

## Products API

### List Products

```typescript
// With auto-pagination
for await (const product of dodo.products.list()) {
  console.log(product.product_id, product.name, product.price);
}

// With filters
const products = dodo.products.list({
  page_size: 50,
  archived: false,
  recurring: false, // one-time products only
});
```

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `page_size` | int | Items per page (default: 10, max: 100) |
| `page_number` | int | Page number (default: 0) |
| `archived` | bool | Filter archived products |
| `recurring` | bool | `true` = subscriptions, `false` = one-time |
| `brand_id` | string | Filter by brand |

**Response Fields**:
```typescript
interface Product {
  product_id: string;
  business_id: string;
  name: string;
  description: string;
  price: number;           // In cents
  currency: string;
  image: string;
  is_recurring: boolean;
  tax_category: string;
  tax_inclusive: boolean;
  metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
}
```

---

## Checkout Sessions API

### Create Checkout Session

```typescript
const session = await dodo.checkoutSessions.create({
  product_cart: [
    { product_id: 'prod_123abc', quantity: 1 }
  ],
  customer: {
    email: 'customer@example.com',
    name: 'John Doe',
  },
  return_url: 'https://yoursite.com/checkout/success',
});

console.log(session.session_id);
console.log(session.checkout_url);
// Redirect customer to session.checkout_url
```

**Request Parameters**:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `product_cart` | Yes | Array of `{product_id, quantity, amount?}` |
| `return_url` | Yes | Post-payment redirect URL |
| `customer` | No | `{email, name, phone_number}` |
| `customer_id` | No | Existing customer ID |
| `billing_address` | No | `{street, city, state, country, zipcode}` |
| `metadata` | No | Custom key-value pairs |
| `discount_code` | No | Pre-applied discount code |
| `confirm` | No | `true` = finalize immediately (15min validity) |
| `allow_discount_code` | No | Show discount input (default: true) |
| `force_3ds` | No | Override 3DS behavior |
| `allowed_payment_method_types` | No | Array of methods |

**Response**:
```typescript
interface CheckoutSessionResponse {
  session_id: string;
  checkout_url: string;
}
```

### Retrieve Checkout Session

```typescript
const session = await dodo.checkoutSessions.retrieve('cks_xxx');
console.log(session.status); // 'open', 'succeeded', 'expired'
```

---

## Payments API

### Create Payment (Dynamic Link)

```typescript
const payment = await dodo.payments.create({
  payment_link: true, // Required for shareable link
  product_cart: [
    { product_id: 'prod_123', quantity: 1 }
  ],
  customer: {
    email: 'customer@example.com',
    name: 'John Doe',
  },
  billing: {
    city: 'San Francisco',
    country: 'US',
    state: 'CA',
    street: '123 Main St',
    zipcode: 94102,
  },
});

console.log(payment.payment_url);
```

### List Payments

```typescript
for await (const payment of dodo.payments.list()) {
  console.log(payment.payment_id, payment.status, payment.total_amount);
}
```

---

## Error Handling

```typescript
import DodoPayments, {
  APIError,
  BadRequestError,
  AuthenticationError,
  PermissionDeniedError,
  NotFoundError,
  UnprocessableEntityError,
  RateLimitError,
  InternalServerError,
} from 'dodopayments';

try {
  const session = await dodo.checkoutSessions.create({...});
} catch (err) {
  if (err instanceof BadRequestError) {
    // 400 - Invalid request parameters
    console.error('Bad request:', err.message);
  } else if (err instanceof AuthenticationError) {
    // 401 - Invalid API key
    console.error('Auth failed:', err.message);
  } else if (err instanceof NotFoundError) {
    // 404 - Resource not found (e.g., invalid product_id)
    console.error('Not found:', err.message);
  } else if (err instanceof RateLimitError) {
    // 429 - Too many requests
    console.error('Rate limited, retry after:', err.headers?.['retry-after']);
  } else if (err instanceof APIError) {
    // Generic API error
    console.error('API error:', err.status, err.message);
  }
}
```

**Error Codes**:
| Status | Error Class | Common Causes |
|--------|-------------|---------------|
| 400 | `BadRequestError` | Invalid parameters |
| 401 | `AuthenticationError` | Invalid/missing API key |
| 403 | `PermissionDeniedError` | Insufficient permissions |
| 404 | `NotFoundError` | Invalid product_id, session not found |
| 422 | `UnprocessableEntityError` | Validation failed |
| 429 | `RateLimitError` | Rate limit exceeded |
| 5xx | `InternalServerError` | Dodo server issue |

---

## TypeScript Types

```typescript
import DodoPayments, {
  CheckoutSessionCreateParams,
  CheckoutSessionResponse,
  PaymentCreateParams,
  Product,
} from 'dodopayments';

// Fully typed parameters
const params: CheckoutSessionCreateParams = {
  product_cart: [{ product_id: 'prod_123', quantity: 1 }],
  return_url: 'https://example.com/success',
  metadata: { source: 'web_app' },
};

// Typed response
const session: CheckoutSessionResponse = await dodo.checkoutSessions.create(params);
```

---

## Raw Response Access

```typescript
// Get headers and raw response
const { data, response } = await dodo.checkoutSessions
  .create({...})
  .withResponse();

console.log(response.headers.get('x-request-id'));
console.log(data.checkout_url);
```

---

## Comparison with Polar.sh SDK

| Aspect | Polar SDK | Dodo SDK |
|--------|-----------|----------|
| Package | `@polar-sh/sdk` | `dodopayments` |
| Init | `new Polar({ accessToken })` | `new DodoPayments({ bearerToken })` |
| Env toggle | No built-in (use sandbox URL) | `environment: 'test_mode'` |
| Checkout | `polar.checkouts.create()` | `dodo.checkoutSessions.create()` |
| Products array | `products: [id]` | `product_cart: [{product_id, quantity}]` |
| Dynamic price | `prices: { [id]: [{amountType, priceAmount}] }` | PWYW product with `amount` field |
| Confirmation | Manual via `/confirm` endpoint | Auto-confirm with `confirm: true` |

---

## Best Practices

1. **Environment Variables**: Never commit API keys; use `.env` files
2. **Test Mode**: Always develop with `environment: 'test_mode'`
3. **Error Handling**: Wrap all API calls in try/catch
4. **Rate Limiting**: SDK auto-retries, but implement backoff for bulk operations
5. **Logging**: Enable `logLevel: 'debug'` during development
6. **Type Safety**: Use TypeScript types for compile-time validation
