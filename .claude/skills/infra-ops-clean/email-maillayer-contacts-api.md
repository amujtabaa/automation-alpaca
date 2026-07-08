---
name: maillayer-contacts-api
description: "Maillayer Contacts API for managing email contacts programmatically. Use when adding subscribers, updating contact info, syncing customer data, or building forms that add contacts to Maillayer lists."
---

# Maillayer Contacts API Reference

> **TEMPLATE** - Replace example values with your own. Keep your customized copy private once it holds real credentials.
> Do NOT expose in client-side code. Use server-side only.

---

## Overview

Maillayer provides a public API for managing contacts in your email lists. This enables:

- Adding new subscribers from forms/checkout flows
- Updating existing contact information
- Syncing customer data from external systems
- Building custom signup flows

**Instance URL**: `https://example.com`
**Brand ID**: `<RESOURCE_ID>`
**Contact List ID**: `<RESOURCE_ID>`
**List Name**: Example Customers

---

## Credentials

### API Configuration

| Setting                  | Value                                     |
| ------------------------ | ----------------------------------------- |
| **API Key**              | `<MAILLAYER_CONTACTS_API_KEY>`            |
| **Base URL**             | `https://example.com/api/public/contacts` |
| **Environment Variable** | `MAILLAYER_CONTACTS_API_KEY`              |

### Current List Stats (example numbers)

| Metric         | Count |
| -------------- | ----- |
| Total Contacts | 1,250 |
| Active         | 1,180 |
| Unsubscribed   | 55    |
| Bounced        | 12    |
| Complained     | 3     |

---

## API Endpoints

### Add Contact

**POST** `https://example.com/api/public/contacts/{API_KEY}`

Adds a new contact to the list. If contact exists and "Allow duplicate submissions" is disabled, only custom fields are updated.

#### Request

```bash
curl -X POST "https://example.com/api/public/contacts/<MAILLAYER_CONTACTS_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "firstName": "John",
    "lastName": "Doe",
    "phone": "+1234567890",
    "customFields": {
      "company": "Acme Inc",
      "plan": "premium",
      "source": "website"
    }
  }'
```

#### Request Body

| Field          | Type   | Required | Description                     |
| -------------- | ------ | -------- | ------------------------------- |
| `email`        | string | **Yes**  | Contact email address           |
| `firstName`    | string | No       | First name                      |
| `lastName`     | string | No       | Last name                       |
| `phone`        | string | No       | Phone number (E.164 format)     |
| `customFields` | object | No       | Key-value pairs for custom data |

#### Response (201 Created)

```json
{
  "success": true,
  "message": "Contact added successfully",
  "contactId": "<RESOURCE_ID>"
}
```

---

### Update Contact

**PUT** `https://example.com/api/public/contacts/{API_KEY}/update`

Updates an existing contact. Email is used to identify the contact.

#### Request

```bash
curl -X PUT "https://example.com/api/public/contacts/<MAILLAYER_CONTACTS_API_KEY>/update" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "firstName": "John",
    "lastName": "Smith",
    "phone": "+1234567890",
    "tags": ["customer", "vip"],
    "customFields": {
      "company": "New Company",
      "plan": "enterprise"
    }
  }'
```

#### Request Body

| Field          | Type   | Required | Description                     |
| -------------- | ------ | -------- | ------------------------------- |
| `email`        | string | **Yes**  | Contact email (identifier)      |
| `firstName`    | string | No       | Update first name               |
| `lastName`     | string | No       | Update last name                |
| `phone`        | string | No       | Update phone                    |
| `tags`         | array  | No       | **Replaces** existing tags      |
| `customFields` | object | No       | **Merges** with existing fields |

#### Response (200 OK)

```json
{
  "success": true,
  "message": "Contact updated successfully",
  "contactId": "<RESOURCE_ID>",
  "updatedFields": ["firstName", "tags", "customFields"]
}
```

---

## Error Responses

| Status | Meaning                                             |
| ------ | --------------------------------------------------- |
| `400`  | Invalid email or missing required fields            |
| `403`  | Domain not allowed (if domain restrictions enabled) |
| `404`  | Invalid API key or contact not found (update only)  |

---

## Implementation Examples

### TypeScript (Server Action)

```typescript
// lib/maillayer.ts
const MAILLAYER_API_KEY = process.env.MAILLAYER_CONTACTS_API_KEY;
const MAILLAYER_BASE_URL = "https://example.com/api/public/contacts";

interface ContactData {
  email: string;
  firstName?: string;
  lastName?: string;
  phone?: string;
  customFields?: Record<string, string>;
}

interface ContactUpdateData extends ContactData {
  tags?: string[];
}

interface MaillayerResponse {
  success: boolean;
  message: string;
  contactId: string;
  updatedFields?: string[];
}

export async function addContact(
  data: ContactData,
): Promise<MaillayerResponse> {
  const response = await fetch(`${MAILLAYER_BASE_URL}/${MAILLAYER_API_KEY}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to add contact: ${error}`);
  }

  return response.json();
}

export async function updateContact(
  data: ContactUpdateData,
): Promise<MaillayerResponse> {
  const response = await fetch(
    `${MAILLAYER_BASE_URL}/${MAILLAYER_API_KEY}/update`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to update contact: ${error}`);
  }

  return response.json();
}
```

### Next.js Server Action

```typescript
// app/actions/newsletter.ts
"use server";

import { addContact } from "@/lib/maillayer";

export async function subscribeToNewsletter(formData: FormData) {
  const email = formData.get("email") as string;
  const firstName = formData.get("firstName") as string | undefined;

  try {
    const result = await addContact({
      email,
      firstName,
      customFields: {
        source: "newsletter_form",
        subscribed_at: new Date().toISOString(),
      },
    });

    return { success: true, contactId: result.contactId };
  } catch (error) {
    console.error("Newsletter subscription failed:", error);
    return { success: false, error: "Failed to subscribe" };
  }
}
```

### Post-Purchase Integration

```typescript
// After successful Polar checkout
async function onCheckoutComplete(checkout: PolarCheckout) {
  await addContact({
    email: checkout.customer.email,
    firstName: checkout.customer.name?.split(" ")[0],
    lastName: checkout.customer.name?.split(" ").slice(1).join(" "),
    customFields: {
      product: checkout.product.name,
      purchase_date: new Date().toISOString(),
      order_id: checkout.id,
      plan: checkout.product.metadata?.plan || "standard",
    },
  });
}
```

### Vanilla JavaScript (Client-side)

> **Warning**: Only use client-side if domain restrictions are configured in Maillayer settings.

```javascript
// Add a contact from a form
async function subscribeContact(email, firstName) {
  const response = await fetch(
    "https://example.com/api/public/contacts/<MAILLAYER_CONTACTS_API_KEY>",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        firstName,
        customFields: { source: "website" },
      }),
    },
  );

  const data = await response.json();
  console.log(data);
}
```

---

## Configuration Options

### Domain Restrictions

In Maillayer dashboard, you can restrict API access to specific domains:

- **Current Setting**: All domains allowed (empty list)
- **Recommendation**: Add `example.com` if using client-side integration

### Duplicate Handling

- **Allow duplicate submissions**: If disabled, duplicate emails update custom fields only
- **Current Setting**: Disabled (updates only)

### Redirect URL

Optional redirect URL returned in API response for client-side form handling:

- **Current Setting**: Not configured
- **Use Case**: Post-form submission redirects

---

## Use Cases for Example

### 1. Post-Purchase Customer Sync

Add customers to mailing list after Polar checkout:

```typescript
// In webhook handler or checkout success callback
await addContact({
  email: customer.email,
  firstName: customer.name,
  customFields: {
    product: "Complete Kit", // or 'Code Kit', 'Growth Kit'
    purchase_date: new Date().toISOString(),
    polar_customer_id: customer.id,
  },
});
```

### 2. Newsletter Signup

```typescript
// Newsletter form submission
await addContact({
  email: formData.email,
  customFields: {
    source: "blog_sidebar",
    interests: formData.interests.join(","),
  },
});
```

### 3. Lead Magnet Downloads

```typescript
// After lead magnet form submission
await addContact({
  email: formData.email,
  firstName: formData.firstName,
  customFields: {
    lead_magnet: "claude-code-cheatsheet",
    download_date: new Date().toISOString(),
  },
});
```

### 4. Customer Upgrade Tracking

```typescript
// When customer upgrades plan
await updateContact({
  email: customer.email,
  tags: ["customer", "upgraded"],
  customFields: {
    previous_plan: "Code Kit",
    current_plan: "Complete Kit",
    upgrade_date: new Date().toISOString(),
  },
});
```

---

## Recommended Custom Fields for Example

| Field               | Description                  | Example Value                            |
| ------------------- | ---------------------------- | ---------------------------------------- |
| `product`           | Product purchased            | `Code Kit`, `Growth Kit`, `Complete Kit` |
| `purchase_date`     | ISO timestamp of purchase    | `2025-01-23T10:30:00Z`                   |
| `source`            | Where they signed up         | `checkout`, `newsletter`, `lead_magnet`  |
| `polar_customer_id` | Polar customer ID            | `cust_xxxxx`                             |
| `order_id`          | Polar order ID               | `ord_xxxxx`                              |
| `lead_magnet`       | Which lead magnet downloaded | `claude-code-cheatsheet`                 |
| `interests`         | Comma-separated interests    | `claude-code,mcp,automation`             |

---

## Dashboard Access

| Resource               | URL                                                               |
| ---------------------- | ----------------------------------------------------------------- |
| Maillayer Dashboard    | `https://example.com`                                             |
| Example Brand          | `https://example.com/brands/<RESOURCE_ID>`                        |
| Example Customers List | `https://example.com/brands/<RESOURCE_ID>/contacts/<RESOURCE_ID>` |

---

## Security Notes

1. **Never expose API key in client-side code** without domain restrictions
2. **Use environment variables** for all API keys
3. **Server-side preferred** for all contact operations
4. **Rate limiting**: Maillayer has built-in rate limiting; respect 429 responses

---

## Related Documentation

- [Email Infrastructure](./email-infrastructure.md) - Architecture overview

---

**Last Updated**: January 2025
