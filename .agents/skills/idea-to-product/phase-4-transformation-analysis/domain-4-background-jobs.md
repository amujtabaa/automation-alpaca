# Domain 4: Background Jobs Deep Dive

**Focus:** Scheduled tasks, job processing, monitoring (using node-cron for VPS)

---

## Questions to Answer

### Current Implementation
- Does the kit have background job support?
- What patterns are used (cron, queue, etc.)?
- How are long-running tasks handled?

### Our Requirements
- What jobs need to run?
- Frequency of each job?
- Error handling approach?
- Scaling considerations?

---

## Files to Review

```
/lib/jobs/ or /lib/cron/
/app/api/cron/ (if API-based)
Any queue implementations
```

---

## VPS Job Pattern (node-cron)

### Installation
```bash
bun add node-cron
```

### Job Setup
```typescript
// lib/jobs/scheduler.ts
import cron from 'node-cron';
import { checkReddit } from './check-reddit';
import { sendDigests } from './send-digests';

export function initializeScheduler() {
  // Run every 5 minutes
  cron.schedule('*/5 * * * *', async () => {
    console.log('[CRON] Starting Reddit check...');
    try {
      await checkReddit();
      console.log('[CRON] Reddit check complete');
    } catch (error) {
      console.error('[CRON] Reddit check failed:', error);
    }
  });

  // Run daily at 9am
  cron.schedule('0 9 * * *', async () => {
    await sendDigests();
  });

  console.log('[CRON] Scheduler initialized');
}
```

### Initialize in App
```typescript
// app/layout.tsx or lib/init.ts
import { initializeScheduler } from '@/lib/jobs/scheduler';

// Only run on server, not during build
if (process.env.NODE_ENV === 'production' && typeof window === 'undefined') {
  initializeScheduler();
}
```

---

## Job Implementation Pattern

```typescript
// lib/jobs/check-reddit.ts
import { db } from '@/lib/database';
import { redditClient } from '@/lib/reddit/client';

export async function checkReddit() {
  // 1. Get all active workspaces
  const workspaces = await db.workspace.findMany({
    where: { monitoring_enabled: true },
    include: { subreddits: true, keywords: true },
  });

  // 2. Process each workspace
  for (const workspace of workspaces) {
    try {
      await processWorkspace(workspace);
    } catch (error) {
      console.error(`Error processing workspace ${workspace.id}:`, error);
      // Continue with other workspaces
    }
  }
}

async function processWorkspace(workspace) {
  // 3. Check rate limits
  // 4. Fetch from external APIs
  // 5. Store results
  // 6. Send notifications if needed
}
```

---

## Rate Limiting Pattern

```typescript
// lib/jobs/rate-limiter.ts
class RateLimiter {
  private timestamps: number[] = [];
  private readonly limit: number;
  private readonly windowMs: number;

  constructor(limit: number, windowMs: number) {
    this.limit = limit;
    this.windowMs = windowMs;
  }

  async waitIfNeeded(): Promise<void> {
    const now = Date.now();
    this.timestamps = this.timestamps.filter(t => now - t < this.windowMs);

    if (this.timestamps.length >= this.limit) {
      const oldestInWindow = this.timestamps[0];
      const waitTime = this.windowMs - (now - oldestInWindow);
      await new Promise(resolve => setTimeout(resolve, waitTime));
    }

    this.timestamps.push(Date.now());
  }
}

// 100 requests per minute
export const apiRateLimiter = new RateLimiter(100, 60000);
```

---

## Error Handling & Monitoring

```typescript
// lib/jobs/utils.ts
export async function withJobLogging(
  jobName: string,
  fn: () => Promise<void>
) {
  const startTime = Date.now();
  console.log(`[JOB:${jobName}] Starting...`);

  try {
    await fn();
    const duration = Date.now() - startTime;
    console.log(`[JOB:${jobName}] Completed in ${duration}ms`);
  } catch (error) {
    const duration = Date.now() - startTime;
    console.error(`[JOB:${jobName}] Failed after ${duration}ms:`, error);

    // Optionally send alert
    // await sendSlackAlert(`Job ${jobName} failed: ${error.message}`);

    throw error;
  }
}
```

---

## Output Checklist

- [ ] Job scheduler setup
- [ ] Individual job functions
- [ ] Rate limiting implementation
- [ ] Error handling
- [ ] Logging/monitoring
- [ ] Test endpoints for manual triggers

---
