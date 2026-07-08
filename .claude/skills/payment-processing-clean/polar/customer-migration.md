## Customer Migration Strategy

### Approach (Polar Support Recommended - VERIFIED WORKING ✅)

For migrating existing customers with paid products:

1. **Create FREE Migration Product**
   - Price: $0
   - Attach same benefits as original product
   - Mark as private/internal

2. **Programmatic Checkout Creation & Confirmation**
   ```typescript
   import { Polar } from "@polar-sh/sdk";

   const polar = new Polar({
     accessToken: process.env.POLAR_ACCESS_TOKEN!
   });

   const FREE_PRODUCT_ID = "<YOUR_MIGRATION_PRODUCT_ID>";

   for (const customer of customers) {
     // Step 1: Create checkout with products array (CRITICAL!)
     const checkout = await polar.checkouts.create({
       products: [FREE_PRODUCT_ID],  // Must be array, not productPriceId!
       customerEmail: customer.email,
       customerName: customer.name,
       customerBillingAddress: {
         country: customer.country,
       },
       successUrl: "https://yoursite.com/welcome",
     });

     // Step 2: Confirm checkout programmatically
     const response = await fetch(
       `https://api.polar.sh/v1/checkouts/client/${checkout.clientSecret}/confirm`,
       {
         method: "POST",
         headers: {
           "Content-Type": "application/json",
           "Authorization": `Bearer ${process.env.POLAR_ACCESS_TOKEN}`
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
     console.log(`✅ Migrated: ${customer.email} - Customer ID: ${result.customer_id}`);

     // Rate limiting: Wait between customers
     await new Promise(resolve => setTimeout(resolve, 600)); // 600ms delay
   }
   ```

3. **Archive Migration Product**
   - **IMMEDIATELY** after migration completes
   - Prevents abuse (free product with valuable benefits)
   - Does NOT revoke already-granted benefits
   - Customers retain access permanently

**Expected Migration Results**:
- Customers successfully migrated with confirmation emails
- File Download benefit immediately accessible
- Customer portal access working
- Rate: Stay well under Polar's 300 req/min limit (600ms delay recommended)

---

## Common Issues & Solutions

### ❌ Issue 1: SDK Validation Error - "products" field required

**Symptoms**:
```json
{
  "detail": [
    {
      "expected": "array",
      "code": "invalid_type",
      "path": ["products"]
    }
  ]
}
```

**Cause**: Using `productPriceId: "price_id"` instead of `products: [product_id]` array

**Solution** ✅:
```typescript
// ❌ WRONG:
const checkout = await polar.checkouts.create({
  productPriceId: "<YOUR_POLAR_PRICE_ID>",
  customerEmail: "customer@example.com",
  // ...
});

// ✅ CORRECT:
const checkout = await polar.checkouts.create({
  products: ["<YOUR_POLAR_PRODUCT_ID>"],  // Array of product IDs!
  customerEmail: "customer@example.com",
  // ...
});
```

**This was THE critical fix that made the entire migration work.**

---

### ❌ Issue 2: 404 on Checkout Confirmation

**Symptoms**:
- Checkouts created successfully
- Confirmation returns `404 ResourceNotFound`
- No customers appearing in Polar dashboard

**Cause**: Wrong confirmation endpoint URL

**Solution** ✅:
```typescript
// ❌ WRONG:
const response = await fetch(
  `https://api.polar.sh/v1/checkouts/custom/client/${clientSecret}/confirm`,
  // ...
);

// ✅ CORRECT:
const response = await fetch(
  `https://api.polar.sh/v1/checkouts/client/${clientSecret}/confirm`,
  // Removed "/custom" from path
  // ...
);
```

---

### ❌ Issue 3: No Customers/Orders Appearing in Dashboard

**Symptoms**:
- Checkouts created
- Status shows "open" or "undefined"
- No customers in dashboard after creation
- No orders visible

**Cause**: Checkouts not confirmed/completed

**Solution** ✅:
- Checkouts must be **confirmed** to create orders
- Orders create customer records
- Only **completed orders** grant benefits
- Free products auto-complete on confirmation (no payment required)
- Use the programmatic confirmation approach shown in Customer Migration Strategy

---

### ❌ Issue 4: CamelCase vs Snake_case Parameter Naming

**Symptoms**:
- SDK calls work, but raw API calls fail with validation errors
- Inconsistent behavior between SDK and fetch requests

**Cause**: SDK uses camelCase, API uses snake_case

**Solution** ✅:
```typescript
// SDK (camelCase):
const checkout = await polar.checkouts.create({
  customerEmail: "test@example.com",
  customerName: "John Doe",
  customerBillingAddress: { country: "US" }
});

// Raw API (snake_case):
const response = await fetch("https://api.polar.sh/v1/checkouts/client/{secret}/confirm", {
  body: JSON.stringify({
    customer_email: "test@example.com",
    customer_name: "John Doe",
    customer_billing_address: { country: "US" }
  })
});
```

**Best Practice**: Use SDK for creation (validation), raw fetch for confirmation (control)

---

## Testing Checklist

Before production migration:

- [ ] Create test checkout with test customer
- [ ] Verify checkout confirmation works
- [ ] Check customer appears in dashboard
- [ ] Verify order created successfully
- [ ] Confirm benefit was granted
- [ ] Test customer portal access
- [ ] Verify benefit is accessible

---

## Migration Context Template

### Source Platform
- **Customers**: Count your unique customers after deduplication
- **Product**: Your product name
- **Benefit**: What benefit to migrate (File Download, License Key, etc.)
- **Regions**: Collect customer country data for billing addresses

### Target: Polar.sh
- **Migration Product ID**: `<YOUR_MIGRATION_PRODUCT_ID>`
- **Migration Price ID**: `<YOUR_MIGRATION_PRICE_ID>`
- **Checkout Link**: `<YOUR_MIGRATION_CHECKOUT_LINK>`

### Handling Failed Migrations
- Some customers may fail due to invalid emails (domain doesn't exist)
- Track failed customers for manual outreach
- Request updated email addresses and retry individually

---

## Resources

- **Polar Documentation**: https://polar.sh/docs
- **API Reference**: https://polar.sh/docs/api-reference
- **Python SDK**: https://github.com/polarsource/polar-python
- **JavaScript SDK**: https://github.com/polarsource/polar-js
- **NPM Package**: https://www.npmjs.com/package/@polar-sh/sdk
- **PyPI Package**: https://pypi.org/project/polar-sdk/

---

## Migration Completion Checklist

**Migration Steps**:

1. [ ] Created migration product with free pricing ($0)
2. [ ] Attached appropriate benefit (File Download, License Key, etc.)
3. [ ] Used correct API implementation (`products` array, not `productPriceId`)
4. [ ] Used correct confirmation endpoint (no `/custom` in path)
5. [ ] Successfully migrated customers
6. [ ] Archived migration product immediately (prevents abuse)
7. [ ] Verified customer access in portal
8. [ ] Confirmed all customers received confirmation emails
9. [ ] Verified benefits are immediately accessible

**Track Your Migration**:
- Date Completed: ___
- Customers Migrated: ___/___
- Execution Time: ___

---

## Key Learnings & Best Practices

### Critical Discoveries

1. **Products vs ProductPriceId**:
   - SDK requires `products: [PRODUCT_ID]` array, NOT `productPriceId: "PRICE_ID"`
   - This was THE breakthrough that made everything work
   - Product IDs are UUIDs, not price IDs

2. **Confirmation Endpoint**:
   - Correct: `/v1/checkouts/client/{client_secret}/confirm`
   - Incorrect: `/v1/checkouts/custom/client/{client_secret}/confirm`
   - Must remove `/custom` from the path

3. **Free Product Behavior**:
   - No payment token required for $0 products
   - Auto-completes immediately on confirmation
   - `isPaymentRequired: false` and `isFreeProductPrice: true`
   - Benefits granted instantly upon confirmation

4. **SDK vs Raw API**:
   - SDK: camelCase parameters (`customerEmail`, `customerName`)
   - API: snake_case parameters (`customer_email`, `customer_name`)
   - Best practice: SDK for creation, raw fetch for confirmation

### Architecture Insights

- Benefits CANNOT be granted directly to customers
- Must flow through: Product → Order → Benefit Grant
- Archiving products doesn't revoke existing benefit grants
- Customer portal requires just email (no password setup)
- Organization Access Token needed for programmatic operations

### Performance & Rate Limiting

- Polar limit: 300 requests/minute
- Safe rate: 600ms delay between customers (100 req/min)
- For 41 customers: ~41 seconds total execution time
- Well under rate limits with room for error handling

### Migration Best Practices

1. **Always create FREE migration product** ($0 price)
2. **Test with 1-2 customers first** before production run
3. **Use sequential processing** with rate limiting (600ms)
4. **Verify in dashboard** before marking complete
5. **IMMEDIATELY archive migration product** after completion
6. **Document all credentials** in secure location (session files)
7. **Hybrid approach**: SDK + raw fetch gives best control

### What Worked Well

- Polar's developer experience and API design
- All-scopes access token for full exploration
- Free products for zero-friction migrations
- Immediate benefit grants (no delay)
- Customer confirmation emails automatic
- Customer portal access instant

### What to Avoid

- Don't use `productPriceId` parameter (use `products` array)
- Don't include `/custom` in confirmation endpoint
- Don't skip rate limiting (risk hitting API limits)
- Don't forget to archive migration product (security risk)
- Don't attempt direct benefit grants (use product flow)

---

