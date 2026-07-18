# Domain 6: Third-Party Integrations Deep Dive

**Focus:** External APIs, SDKs, rate limiting, caching, error handling

---

## Questions to Answer

### Existing Integrations
- What APIs are already integrated?
- What patterns are used?
- How is auth handled?

### New Integrations Needed
- What APIs to integrate?
- Rate limits and costs?
- Caching strategy?
- Fallback behavior?

---

## Files to Review

```
/lib/integrations/ or /lib/services/
/lib/[service-name]/
.env.example (for API keys)
```

---

## Integration Client Pattern

```typescript
// lib/integrations/example-api/client.ts
import { RateLimiter } from '@/lib/utils/rate-limiter';

const API_BASE = 'https://api.example.com/v1';
const rateLimiter = new RateLimiter(100, 60000); // 100/min

export class ExampleApiClient {
  private apiKey: string;

  constructor() {
    this.apiKey = process.env.EXAMPLE_API_KEY!;
    if (!this.apiKey) {
      throw new Error('EXAMPLE_API_KEY not configured');
    }
  }

  async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    await rateLimiter.waitIfNeeded();

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API error ${response.status}: ${error}`);
    }

    return response.json();
  }

  // Specific methods
  async getData(params: Params) {
    return this.request('/data', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }
}

export const exampleApi = new ExampleApiClient();
```

---

## Caching Pattern

```typescript
// lib/integrations/example-api/cached-client.ts
import { db } from '@/lib/database';
import { exampleApi } from './client';

const CACHE_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

export async function getDataWithCache(key: string, params: Params) {
  // 1. Check cache
  const cached = await db.apiCache.findUnique({
    where: { key },
  });

  if (cached && cached.expires_at > new Date()) {
    return cached.value;
  }

  // 2. Fetch from API
  const data = await exampleApi.getData(params);

  // 3. Store in cache
  await db.apiCache.upsert({
    where: { key },
    create: {
      key,
      value: data,
      expires_at: new Date(Date.now() + CACHE_TTL_MS),
    },
    update: {
      value: data,
      expires_at: new Date(Date.now() + CACHE_TTL_MS),
    },
  });

  return data;
}
```

---

## Cost Control Pattern

```typescript
// lib/integrations/paid-api/budget.ts

const MONTHLY_BUDGET = 100; // $100/month
const COST_PER_REQUEST = 0.01; // $0.01 per request

export async function checkBudget(): Promise<boolean> {
  const startOfMonth = new Date();
  startOfMonth.setDate(1);
  startOfMonth.setHours(0, 0, 0, 0);

  const usage = await db.apiUsage.aggregate({
    where: {
      service: 'paid-api',
      created_at: { gte: startOfMonth },
    },
    _sum: { cost: true },
  });

  const spent = usage._sum.cost || 0;
  return spent < MONTHLY_BUDGET;
}

export async function recordUsage(requestCount: number) {
  await db.apiUsage.create({
    data: {
      service: 'paid-api',
      request_count: requestCount,
      cost: requestCount * COST_PER_REQUEST,
    },
  });
}
```

---

## Integration Documentation Template

For each integration, document:

```markdown
### [Service Name] Integration

**Purpose:** [What it's used for]

**API Documentation:** [URL]

**Environment Variables:**
- `SERVICE_API_KEY` - API key from dashboard
- `SERVICE_SECRET` - Webhook secret (if applicable)

**Rate Limits:**
- [X] requests per [minute/day]
- [Cost per request if paid]

**Caching Strategy:**
- Cache duration: [X] days
- Cache key pattern: `[service]:[resource]:[id]`

**Error Handling:**
- 429 (Rate Limited): Wait and retry
- 5xx: Retry with exponential backoff
- 4xx: Log and skip

**Cost Estimate:**
- At 100 customers: $[X]/month
- At 1000 customers: $[X]/month
```

---

## Output Checklist

- [ ] Client class for each API
- [ ] Rate limiting
- [ ] Caching layer
- [ ] Error handling
- [ ] Cost tracking (if paid)
- [ ] Environment variables list
- [ ] Integration tests

---
