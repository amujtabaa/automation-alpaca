# Repository Primer

<!--
  QUICK START: Minimum viable primer - fill in "What This Repo Is", "Tech Stack",
  and "Build Commands". Expand from there as you learn what context Claude needs most.
-->

<!--
  This file tells Claude about YOUR repository. Fill in each section below with
  your project's specifics. Delete sections that don't apply. The more accurate
  and detailed this file is, the better Claude will understand your codebase and
  make correct decisions without asking unnecessary questions.
-->

## Operator working preferences

Durable preference from the repo owner (Ameen) on how to run multi-step work — captured at his request:

- **Drive autonomously; minimize stops.** Prefer running through the task list end-to-end over a
  start-stop, one-approval-per-step cadence. Don't pause to ask when the request, the code, or a
  sensible default already answers the question.
- **Work concurrently where it's safe.** Let read-only synthesis and independent fixes progress in
  parallel (e.g. background analysis workflows while foreground code changes land), sequencing only
  what would otherwise cause a harmful file/state conflict.
- **Isolate ambiguity instead of blocking on it.** When one thread genuinely needs a human decision,
  set it aside and keep the other threads moving; **batch** the human-only decisions and surface them
  together rather than halting the whole effort for each one.
- **Route defensive-security work to the current Opus model** (adopted 2026-07-14). Large parts of
  this repo are defensive security by nature — authentication/credential boundaries, transport/TLS/
  proxy config, rate-limit / flood / DoS rails, quarantine and kill-switch internals, and the
  exploit-*prevention* tests that prove them. The prose for this work is dense with attack-shaped
  language ("bypass the proxy", "expose the key", "flood the log") even though every sentence
  describes what to **prevent**. On **Fable-family models this reliably false-positives the dual-use
  safeguard and blocks generation mid-task** (observed 2026-07-14: the ADR-009 A-1 transport
  amendment was blocked and had to be completed on Opus 4.8). Convention:
  - Do this class of work — **and the fixes that respond to review findings on it** — on the **most
    current Opus model** (Opus 4.8 as of 2026-07-14). This is a **friction fix, not a safety
    relaxation**: every model is bound by the identical `CLAUDE.md` safety core, the same human-gated
    surfaces, and the same review gates. Routing changes only *which agent writes the defensive
    documentation/code*, never *what controls apply* — nothing here is a way to get past a gate,
    only past a content-filter false-positive on defensive material.
  - **Recognize the class before generating.** Trigger surfaces: auth/credentials/secrets/keys,
    TLS/transport/proxy/network-boundary, rate-limit/backpressure/quarantine/DoS, kill-switch/flatten
    internals, and any test whose job is to *demonstrate an attack is refused*. If you are on a
    Fable-family model and about to enter this class, **STOP and recommend the `/model` switch to the
    current Opus first** — do not push into the safeguard and lose partial work to a mid-task block.
    (Work orders on these surfaces carry a `recommended_model` note; honor it at activation.)
- **Hard limit:** this preference governs *velocity and structure only*. It never overrides the
  `CLAUDE.md` safety core, the invariants, or the human-gated surfaces — those still stop and wait for
  explicit human approval, always. Autonomy means fewer needless pauses, not auto-approving gated actions.

## What This Repo Is

<!-- REPLACE: 1-3 sentences describing what this project does, who it serves, and its primary purpose. -->

<!-- Examples (delete these and write your own):
  - "A B2B SaaS dashboard for fleet management companies to track vehicles, drivers, and maintenance schedules."
  - "An open-source CLI tool that generates TypeScript types from OpenAPI specifications."
  - "An e-commerce storefront with a React frontend, Node.js API, and PostgreSQL database."
-->

## Product / Feature Structure

<!-- REPLACE: Describe the main products, features, or modules in your application. Delete this section if not applicable. -->

<!-- Example format (delete and replace with your own):

| Feature / Module | Route / Entry Point | Description                              |
| ---------------- | ------------------- | ---------------------------------------- |
| **Dashboard**    | `/dashboard`        | Main analytics view for logged-in users  |
| **Public API**   | `/api/v2/`          | REST API consumed by mobile apps         |
| **Admin Panel**  | `/admin`            | Internal tool for support team           |

-->

## Tech Stack

### Core Framework

<!-- REPLACE: List your primary frameworks, language, and runtime. -->

<!-- Examples (delete and replace):
- **Next.js 15** with App Router
- **Python 3.12** with FastAPI
- **Go 1.22** with Chi router
- **TypeScript** strict mode
- **pnpm** / **npm** / **yarn** / **cargo** / **poetry** (your package manager)
-->

### Project Structure

<!-- REPLACE: Show your folder layout. Adjust for monorepo or single-app as needed. -->

<!-- Example for a monorepo (delete and replace):
```
apps/
  web/              # Next.js frontend
  api/              # Express API server
packages/
  shared/           # Shared types and utilities
  ui/               # Component library
  db/               # Database schema and migrations
```
-->

<!-- Example for a single app (delete and replace):
```
src/
  app/              # Route handlers / pages
  components/       # Reusable UI components
  lib/              # Business logic and utilities
  db/               # Database models and migrations
  tests/            # Test files
```
-->

### Database

<!-- REPLACE: List your database(s), ORM, and migration tool. Delete if no database. -->

<!-- Examples (delete and replace):
- **PostgreSQL 16** via Supabase
- **Prisma** ORM with migrations in `prisma/migrations/`
- **Redis** for session cache and job queues
-->

### Authentication

<!-- REPLACE: Describe your auth system. Delete if no auth. -->

<!-- Examples (delete and replace):
- **NextAuth.js** with GitHub and Google OAuth providers
- **Clerk** for user management and session handling
- **Custom JWT** - tokens issued by `/api/auth/login`, verified via middleware
-->

### Payments / Billing

<!-- REPLACE: Describe your payment integration. Delete if no payments. -->

<!-- Examples (delete and replace):
- **Stripe** for subscriptions, webhooks at `/api/webhooks/stripe`
- **LemonSqueezy** for one-time purchases
-->

### Analytics / Monitoring

<!-- REPLACE: List analytics and monitoring tools. Delete if none. -->

<!-- Examples (delete and replace):
- **PostHog** for product analytics
- **Sentry** for error tracking (DSN in env vars)
- **Vercel Analytics** for web vitals
-->

### Styling

<!-- REPLACE: Describe your styling approach. Delete if not a frontend project. -->

<!-- Examples (delete and replace):
- **Tailwind CSS 4** with custom design tokens in `tailwind.config.ts`
- **shadcn/ui** components in `src/components/ui/`
- **CSS Modules** with PostCSS
-->

### Key Architectural Decisions

<!-- REPLACE: Document any non-obvious patterns or deviations from framework defaults that Claude needs to know about. These are the things that would trip up someone new to the codebase. Delete if none. -->

<!-- Examples (delete and replace):
- "All API routes use a shared middleware chain defined in `src/middleware/chain.ts` - never create raw route handlers"
- "Navigation is driven by `config/nav.ts`, not by filesystem routing - update that file when adding pages"
- "We use barrel exports (`index.ts`) in every module - always export new files through the barrel"
-->

## Important Paths

<!-- REPLACE: List the files and directories Claude will need to reference most often. Focus on config files, entry points, and anything non-obvious. -->

| Path | Purpose |
| ---- | ------- |

<!-- Examples (delete and replace):
| `src/app/layout.tsx`         | Root layout with providers and global styles  |
| `src/lib/db/schema.ts`      | Database schema (Drizzle / Prisma)             |
| `src/middleware.ts`          | Auth and routing middleware                    |
| `.env.example`              | Template for required environment variables     |
| `docker-compose.yml`        | Local development services (DB, Redis, etc.)   |
-->

## Build Commands

<!-- REPLACE: List the commands needed to develop, build, test, and deploy. -->

```bash
# Examples (delete and replace with your actual commands):

# Development
npm run dev               # Start dev server
npm run db:migrate        # Run database migrations
npm run db:seed           # Seed database with test data

# Testing
npm run test              # Run unit tests
npm run test:e2e          # Run end-to-end tests
npm run lint              # Lint and type-check

# Production
npm run build             # Production build
npm run start             # Start production server

# Utilities
npm run generate          # Generate types from schema
npm run db:studio         # Open database GUI
```

## Environment Variables

<!-- REPLACE: List environment variables grouped by importance. Never put actual secret values here - just the variable names and descriptions. -->

**Required for build:**

<!-- Examples (delete and replace):
- `DATABASE_URL` - PostgreSQL connection string
- `NEXTAUTH_SECRET` - Session encryption key
- `NEXTAUTH_URL` - Canonical app URL (e.g., http://localhost:3000)
-->

**Required for full functionality:**

<!-- Examples (delete and replace):
- `STRIPE_SECRET_KEY` - Stripe API key for server-side operations
- `STRIPE_WEBHOOK_SECRET` - Webhook signature verification
- `RESEND_API_KEY` - Transactional email sending
- `SENTRY_DSN` - Error reporting endpoint
-->

**Optional:**

<!-- Examples (delete and replace):
- `ANALYTICS_ID` - PostHog project ID (analytics disabled if missing)
- `LOG_LEVEL` - Defaults to "info" in production, "debug" in development
-->

## Common Gotchas

<!-- REPLACE: List the things that regularly trip people up in this codebase. These save Claude (and your future self) hours of debugging. -->

<!-- Examples (delete and replace):
1. **Env vars require restart** - Next.js caches env vars at build time. After changing `.env.local`, restart the dev server.
2. **Migration order matters** - Always run `db:migrate` before `db:seed`. Seeds depend on the latest schema.
3. **Port conflicts** - The API runs on :3001 and the frontend on :3000. Docker Compose maps Redis to :6380 (not default 6379) to avoid conflicts.
4. **Generated files** - Files in `src/generated/` are auto-created by `npm run generate`. Never edit them directly.
5. **Import aliases** - Use `@/` for `src/` imports. Absolute paths break in the test runner.
-->

## Workflows

<!-- REPLACE: Describe any recurring development workflows or team conventions. -->

<!-- Examples (delete and replace):
1. Feature branches follow `feature/<ticket-id>-<short-description>` naming
2. PRs require passing CI checks and one approval before merge
3. Database changes always need a migration file, never manual schema edits
4. New API endpoints require corresponding integration tests in `tests/api/`
-->

## Notes

<!-- REPLACE: Any additional context that doesn't fit above. Delete if nothing to add. -->

<!-- Examples (delete and replace):
1. The staging environment uses a separate database - never point local dev at staging.
2. We vendor the `@internal/legacy-sdk` package because upstream is unmaintained. Source is in `packages/legacy-sdk/`.
3. The `/health` endpoint is called by the load balancer every 10 seconds - keep it fast and side-effect-free.
-->
