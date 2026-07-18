# API Integration Planning Template

**Purpose:** Comprehensive planning for third-party API integrations in your product.

---

## When to Use

Use this template when your product relies on external APIs:
- Data sources (Reddit, Twitter, etc.)
- Enrichment services (DataForSEO, Clearbit)
- AI services (OpenAI, Anthropic)
- Specialized services (payment, email, analytics)

---

## API Integration Document Template

```markdown
# API Integration: [Service Name]

**Integration Priority:** P0/P1/P2
**Estimated Effort:** [X] hours

---

## 1. Service Overview

**What it does:** [Brief description]
**Why we need it:** [Business justification]
**Alternative considered:** [Other options and why not chosen]

---

## 2. API Details

### Authentication
- **Type:** API Key / OAuth / Bearer Token
- **Environment Variables:**
  - `SERVICE_API_KEY` - Main API key
  - `SERVICE_SECRET` - Webhook secret (if applicable)

### Base Configuration
```typescript
const config = {
  baseUrl: 'https://api.service.com/v1',
  apiKey: process.env.SERVICE_API_KEY,
  timeout: 30000, // ms
};
```

### Endpoints We'll Use

| Endpoint | Method | Purpose | Rate Limit |
|----------|--------|---------|------------|
| `/data` | GET | Fetch data | 100/min |
| `/search` | POST | Search query | 50/min |
| `/webhook` | POST | Receive events | N/A |

---

## 3. Rate Limits & Quotas

### Rate Limits
- **Requests:** [X] per [minute/hour/day]
- **Concurrent:** [X] simultaneous requests
- **Burst:** [X] in short window

### Quotas
- **Daily:** [X] requests
- **Monthly:** [X] requests
- **Data volume:** [X] MB/records

### Our Expected Usage
| Customers | Daily Requests | Monthly Requests |
|-----------|----------------|------------------|
| 10 | [X] | [X] |
| 100 | [X] | [X] |
| 1000 | [X] | [X] |

### Rate Limit Strategy
```typescript
// Implementation approach
class RateLimiter {
  // Track requests per window
  // Queue overflow requests
  // Implement backoff on 429
}
```

---

## 4. Pricing & Costs

### Pricing Model
- **Type:** Free tier / Pay-as-you-go / Subscription
- **Pricing:** $[X] per [request/record/month]

### Cost Projections

| Customers | Monthly Usage | Monthly Cost |
|-----------|---------------|--------------|
| 10 | [X] | $[X] |
| 100 | [X] | $[X] |
| 1000 | [X] | $[X] |

### Cost Control Measures
1. **Caching:** Cache results for [X] days
2. **Batching:** Combine requests where possible
3. **Filtering:** Only call for high-value items
4. **Budget alerts:** Alert at $[X]/month

---

## 5. Data & Caching

### Data We Receive
```typescript
interface ServiceResponse {
  id: string;
  data: {
    // Response structure
  };
  metadata: {
    // Metadata fields
  };
}
```

### Caching Strategy
- **Cache duration:** [X] hours/days
- **Cache key pattern:** `service:[resource]:[id]`
- **Storage:** Database / Redis / In-memory

### Data Retention
- **Keep in cache:** [Duration]
- **Keep in database:** [Duration]
- **Compliance:** [GDPR/CCPA considerations]

---

## 6. Error Handling

### Expected Errors

| Code | Meaning | Action |
|------|---------|--------|
| 400 | Bad request | Log, fix code |
| 401 | Auth failed | Alert, check keys |
| 403 | Forbidden | Check permissions |
| 404 | Not found | Skip, log |
| 429 | Rate limited | Wait, retry |
| 500 | Server error | Retry with backoff |
| 503 | Unavailable | Retry with backoff |

### Retry Strategy
```typescript
const retryConfig = {
  maxRetries: 3,
  initialDelay: 1000, // ms
  maxDelay: 30000, // ms
  backoffMultiplier: 2,
  retryableStatuses: [429, 500, 502, 503, 504],
};
```

### Fallback Behavior
- **Graceful degradation:** [What happens if API is down]
- **User communication:** [How to inform users]
- **Monitoring:** [How to detect issues]

---

## 7. Implementation Plan

### Phase 1: Basic Integration
- [ ] Set up API client class
- [ ] Implement auth
- [ ] Basic request/response handling
- [ ] Error handling

### Phase 2: Production Hardening
- [ ] Rate limiting
- [ ] Caching layer
- [ ] Retry logic
- [ ] Logging/monitoring

### Phase 3: Optimization
- [ ] Cost tracking
- [ ] Performance optimization
- [ ] Batch processing

### Files to Create
- `/lib/integrations/[service]/client.ts` - API client
- `/lib/integrations/[service]/types.ts` - TypeScript types
- `/lib/integrations/[service]/cache.ts` - Caching layer

---

## 8. Testing

### Test Scenarios
- [ ] Successful request
- [ ] Auth failure
- [ ] Rate limit hit
- [ ] Timeout
- [ ] Invalid response
- [ ] Service unavailable

### Test Endpoint
```typescript
// /api/dev/test-[service]/route.ts
// For manual testing during development
```

### Sandbox/Testing Environment
- **Sandbox URL:** [URL if available]
- **Test credentials:** [How to get]
- **Test data:** [What's available]

---

## 9. Monitoring & Alerting

### Metrics to Track
- Request count (success/failure)
- Response times
- Error rates by type
- Cost accumulation
- Rate limit proximity

### Alerts
- [ ] Error rate > [X]%
- [ ] Monthly cost > $[X]
- [ ] P99 latency > [X]ms
- [ ] Approaching rate limit

---

## 10. Documentation & Resources

- **API Docs:** [URL]
- **SDK/Library:** [Package name]
- **Support:** [Contact info]
- **Status Page:** [URL]
- **Changelog:** [URL]

---

## Checklist

- [ ] API account created
- [ ] Credentials in env
- [ ] Client class implemented
- [ ] Rate limiting in place
- [ ] Caching implemented
- [ ] Error handling complete
- [ ] Cost tracking added
- [ ] Tests written
- [ ] Monitoring set up
- [ ] Documentation complete
```

---
