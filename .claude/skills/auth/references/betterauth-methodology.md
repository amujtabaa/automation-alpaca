# BetterAuth Methodology (Deep Reference)

The deep methodology reference for the auth skill: full code snippets, CSP configuration, cookie internals, Prisma schema, and the environment variable reference. The carbon-copy implementation guide in SKILL.md routes here for exhaustive detail.

Comprehensive guide for implementing BetterAuth with Next.js App Router, including critical pitfalls and battle-tested solutions.

## Critical Warning: NEXT*PUBLIC*\* Build-Time Inlining

**THE BUG**: `NEXT_PUBLIC_*` environment variables are inlined at BUILD time, not runtime. If your build environment has `NEXT_PUBLIC_SITE_URL=http://localhost:3000`, that value is permanently baked into your production bundle.

**SYMPTOMS**:

- OAuth redirects to localhost in production
- "Failed to fetch" errors on login
- Session cookies not being set
- Google OAuth showing "redirect_uri_mismatch"

**THE FIX**: Never use `NEXT_PUBLIC_*` for auth URLs. Use dynamic detection instead.

---

## Architecture Overview

```
apps/web/src/
  lib/
    auth.ts           # Server-side BetterAuth config
    auth-client.ts    # Client-side auth hooks (useSession, signIn, signOut)
    env/index.ts      # Environment/URL handling
  app/
    api/auth/[...all]/route.ts  # BetterAuth API handler
    (home)/auth/login/page.tsx  # Login page
  components/auth/
    login.tsx         # Login form container
    login-button.tsx  # OAuth button component
    login-form.tsx    # Magic link form
    user-menu.tsx     # Avatar dropdown
  hooks/
    use-auth-callback-url.ts    # Callback URL logic
packages/db/
  prisma/schema.prisma          # User, Session, Account models
```

---

## The Dynamic URL Pattern (Production-Safe)

### Client-Side: Use window.location.origin

```typescript
// lib/auth-client.ts
"use client";

import { magicLinkClient } from "better-auth/client/plugins";
import { createAuthClient } from "better-auth/react";

// Get the base URL dynamically at runtime
// This avoids NEXT_PUBLIC_* build-time inlining issues
const getBaseUrl = (): string => {
  // In the browser, use the actual origin (works for localhost AND production)
  if (typeof window !== "undefined") {
    return window.location.origin;
  }
  // SSR fallback - this won't be used for actual auth calls
  return "https://your-production-domain.com";
};

export const authClient = createAuthClient({
  baseURL: getBaseUrl(),
  plugins: [magicLinkClient()],
});

export const { useSession, signIn, signOut } = authClient;
```

### Server-Side: Use Runtime Environment Variables

```typescript
// lib/auth.ts
import { betterAuth } from "better-auth";
import { magicLink } from "better-auth/plugins";
import { prismaAdapter } from "better-auth/adapters/prisma";
import { headers } from "next/headers";
import { cache } from "react";
import { db } from "@your-org/db/client";

const isProduction = process.env.NODE_ENV === "production";
const isDevelopment = process.env.NODE_ENV === "development";

// Server-side base URL
// Priority: BETTER_AUTH_URL env var > localhost in dev > production URL
const getServerBaseUrl = (): string => {
  // If explicitly set, use it (runtime env var, not build-time)
  if (process.env.BETTER_AUTH_URL) {
    return process.env.BETTER_AUTH_URL;
  }
  // In development (next dev), use localhost
  if (isDevelopment) {
    return "http://localhost:3000";
  }
  // Production fallback - hardcoded to avoid build-time issues
  return "https://your-production-domain.com";
};

const serverBaseUrl = getServerBaseUrl();

export const auth = betterAuth({
  database: prismaAdapter(db, {
    provider: "postgresql",
  }),
  baseURL: serverBaseUrl,
  trustedOrigins: [
    "http://localhost:3000",
    "https://your-production-domain.com",
  ],
  socialProviders: {
    google: {
      clientId: process.env.AUTH_GOOGLE_ID!,
      clientSecret: process.env.AUTH_GOOGLE_SECRET!,
    },
  },
  plugins: [
    magicLink({
      sendMagicLink: async ({ email, token, url }) => {
        // TODO: Implement email sending with Resend
        console.log(`Magic link for ${email}: ${url}`);
      },
    }),
  ],
  account: {
    accountLinking: {
      enabled: true,
    },
  },
  session: {
    freshAge: 0, // Use cached cookie immediately, no network request
    cookieCache: {
      enabled: true,
    },
  },
  advanced: {
    // Explicit cookie configuration for production
    defaultCookieAttributes: {
      secure: isProduction, // Only send cookies over HTTPS in production
      httpOnly: true,
      sameSite: "lax", // Required for OAuth redirects
      path: "/",
    },
  },
});

export type Session = typeof auth.$Infer.Session;

// Server-side session getter (cached per request)
export const getServerSession = cache(async () => {
  return auth.api.getSession({
    headers: await headers(),
  });
});
```

---

## Cookie Configuration Deep Dive

### Why These Settings Matter

```typescript
advanced: {
  defaultCookieAttributes: {
    secure: isProduction,  // HTTPS only in production
    httpOnly: true,        // Prevent XSS access to cookies
    sameSite: "lax",       // CRITICAL for OAuth redirects
    path: "/",             // Cookie available on all routes
  },
},
```

**sameSite: "lax"** is required because:

- OAuth involves redirects from Google back to your app
- `sameSite: "strict"` blocks cookies on cross-origin redirects
- `sameSite: "lax"` allows cookies on safe navigation (GET requests from links)

**secure: isProduction** because:

- In development, you use `http://localhost:3000`
- In production, you must use HTTPS
- Setting `secure: true` in dev breaks cookies

---

## CSP Configuration for Google OAuth

Your `next.config.js` must allow Google OAuth domains:

```javascript
async headers() {
  const isDev = process.env.NODE_ENV === "development";

  return [
    {
      source: "/:path*",
      headers: [
        ...(isDev
          ? []
          : [
              {
                key: "Content-Security-Policy",
                value: [
                  "default-src 'self'",
                  // Scripts: include Google accounts
                  "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://accounts.google.com",
                  // Styles: Google account styling
                  "style-src 'self' 'unsafe-inline' https://accounts.google.com",
                  // Images: Google profile pictures
                  "img-src 'self' data: blob: https://*.googleusercontent.com https://lh3.googleusercontent.com",
                  // API connections: OAuth endpoints
                  "connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com https://www.googleapis.com",
                  // Frames: OAuth popups
                  "frame-src 'self' https://accounts.google.com",
                  // Form submissions: OAuth
                  "form-action 'self' https://accounts.google.com",
                ].join("; "),
              },
            ]),
      ],
    },
  ];
}
```

**Required Google OAuth Domains:**

- `accounts.google.com` - OAuth consent screen
- `oauth2.googleapis.com` - Token exchange
- `www.googleapis.com` - User info API
- `lh3.googleusercontent.com` - Profile pictures

---

## Google Cloud Console Setup

### 1. Create OAuth 2.0 Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (or create new)
3. Navigate to APIs & Services > Credentials
4. Click "Create Credentials" > "OAuth client ID"
5. Application type: "Web application"

### 2. Configure Authorized Redirect URIs

Add BOTH for development and production:

```
http://localhost:3000/api/auth/callback/google
https://your-production-domain.com/api/auth/callback/google
```

**Common Mistake**: Forgetting to add the production URL before deploying.

### 3. Configure OAuth Consent Screen

1. Go to OAuth consent screen
2. User type: External (unless Google Workspace)
3. App name, support email, developer email
4. Scopes: `email`, `profile`, `openid`
5. Test users: Add your email during development

### 4. Environment Variables

```bash
# .env.local (development)
AUTH_GOOGLE_ID=your-client-id.apps.googleusercontent.com
AUTH_GOOGLE_SECRET=your-client-secret

# Production (set in deployment platform)
AUTH_GOOGLE_ID=same-client-id
AUTH_GOOGLE_SECRET=same-client-secret
BETTER_AUTH_URL=https://your-production-domain.com
```

---

## API Route Handler

```typescript
// app/api/auth/[...all]/route.ts
import { toNextJsHandler } from "better-auth/next-js";
import { auth } from "~/lib/auth";

export const { GET, POST } = toNextJsHandler(auth);
```

This single file handles all auth endpoints:

- `/api/auth/callback/google` - OAuth callback
- `/api/auth/sign-in` - Magic link sign in
- `/api/auth/sign-out` - Sign out
- `/api/auth/session` - Get session

---

## Client Components

### Login Button (OAuth Trigger)

```typescript
// components/auth/login-button.tsx
"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useAuthCallbackUrl } from "~/hooks/use-auth-callback-url";
import { signIn } from "~/lib/auth-client";

type LoginButtonProps = {
  provider: "google" | "github";
};

export const LoginButton = ({ provider }: LoginButtonProps) => {
  const [isPending, setIsPending] = useState(false);
  const callbackURL = useAuthCallbackUrl();

  const handleSignIn = () => {
    signIn.social({
      provider,
      callbackURL,
      fetchOptions: {
        onRequest: () => setIsPending(true),
        onError: ({ error }) => {
          setIsPending(false);
          toast.error(error.message || "Failed to sign in");
        },
      },
    });
  };

  return (
    <button onClick={handleSignIn} disabled={isPending}>
      Continue with {provider}
    </button>
  );
};
```

### Callback URL Hook

```typescript
// hooks/use-auth-callback-url.ts
"use client";

import { usePathname, useSearchParams } from "next/navigation";

export const useAuthCallbackUrl = () => {
  const searchParams = useSearchParams();
  const pathname = usePathname();

  // Priority: ?next param > current path (unless on auth page) > home
  const callbackURL =
    searchParams.get("next") || (pathname.startsWith("/auth") ? "/" : pathname);

  return callbackURL;
};
```

### Session Display (User Menu)

```typescript
// components/auth/user-menu.tsx
"use client";

import { useSession, signOut } from "~/lib/auth-client";

export const UserMenu = () => {
  const { data: session, isPending } = useSession();

  if (isPending || !session?.user) {
    return <a href="/auth/login">Sign in</a>;
  }

  return (
    <div>
      <img src={session.user.image} alt={session.user.name} />
      <span>{session.user.name}</span>
      <button onClick={() => signOut()}>Logout</button>
    </div>
  );
};
```

---

## Database Schema (Prisma)

BetterAuth requires these tables:

```prisma
model User {
  id            String    @id @default(cuid())
  name          String
  email         String    @unique
  emailVerified Boolean   @default(false)
  image         String?
  role          String    @default("user")
  banned        Boolean?  @default(false)
  banReason     String?
  banExpires    DateTime?
  createdAt     DateTime  @default(now())
  updatedAt     DateTime  @updatedAt

  accounts Account[]
  sessions Session[]
}

model Session {
  id             String   @id @default(cuid())
  token          String   @unique
  expiresAt      DateTime
  ipAddress      String?
  userAgent      String?
  impersonatedBy String?
  createdAt      DateTime @default(now())
  updatedAt      DateTime @updatedAt

  user   User   @relation(fields: [userId], references: [id], onDelete: Cascade)
  userId String

  @@index([userId])
}

model Account {
  id                    String    @id @default(cuid())
  accountId             String
  providerId            String
  accessToken           String?
  refreshToken          String?
  idToken               String?
  accessTokenExpiresAt  DateTime?
  refreshTokenExpiresAt DateTime?
  scope                 String?
  password              String?
  createdAt             DateTime  @default(now())
  updatedAt             DateTime  @updatedAt

  user   User   @relation(fields: [userId], references: [id], onDelete: Cascade)
  userId String

  @@index([userId])
}

model Verification {
  id         String   @id @default(cuid())
  identifier String
  value      String
  expiresAt  DateTime
  createdAt  DateTime @default(now())
  updatedAt  DateTime @updatedAt
}
```

---

## Troubleshooting Checklist

### OAuth Not Working in Production

1. **Check redirect_uri**

   - Open browser DevTools > Network tab
   - Look for the OAuth request to Google
   - Check the `redirect_uri` parameter
   - If it shows `localhost`, you have the build-time inlining issue

2. **Verify environment variables**

   - `BETTER_AUTH_URL` set in production (NOT `NEXT_PUBLIC_*`)
   - `AUTH_GOOGLE_ID` and `AUTH_GOOGLE_SECRET` set correctly
   - Rebuild after changing env vars

3. **Check Google Cloud Console**
   - Production redirect URI added
   - OAuth consent screen configured
   - App not in "Testing" mode if public access needed

### Session Not Persisting

1. **Cookie configuration**

   - `sameSite: "lax"` for OAuth redirects
   - `secure: true` only in production
   - Domain matches your app domain

2. **Session settings**
   ```typescript
   session: {
     freshAge: 0, // Eliminates loading flash
     cookieCache: { enabled: true },
   }
   ```

### "Failed to Fetch" Errors

1. **CSP blocking requests**

   - Check browser console for CSP violations
   - Add Google OAuth domains to CSP

2. **CORS issues**

   - `trustedOrigins` must include your domain
   - Both localhost and production domains

3. **Network issues**
   - Check if `/api/auth/session` responds
   - Verify BetterAuth handler is set up

### Loading Flash on Session Check

Set `freshAge: 0` to use cached cookie immediately:

```typescript
session: {
  freshAge: 0,
  cookieCache: { enabled: true },
}
```

### `internal_server_error` After OAuth Callback

**IMPORTANT**: Auth failures often stem from **database schema mismatches**, not auth configuration.

**Symptoms**:

- OAuth completes at Google but redirects to `/?error=internal_server_error`
- Login worked before but stopped after a deployment
- Works locally but fails in production

**Common Causes**:

1. **Missing database columns**

   - New fields added to User model but not synced to production DB
   - Example: Adding `tier` field locally, pushing code, but production DB lacks the column
   - BetterAuth tries to INSERT/UPDATE with the new field and fails

2. **Schema drift between environments**

   - Local migrations run but production never updated
   - Prisma client expects columns that don't exist

3. **Migration scripts not running**
   - Dockerfile doesn't run `prisma db push` or `prisma migrate deploy`
   - Migration fails silently due to missing dependencies (e.g., `dotenv` in production)

**Diagnosis**:

```sql
-- Check if expected columns exist
SELECT column_name FROM information_schema.columns WHERE table_name = 'User';
```

**Fixes**:

1. **Ensure migrations run on deploy** - Add to startup script:

   ```bash
   npx prisma db push --skip-generate
   ```

2. **Check prisma.config.ts** - Remove dev dependencies like `dotenv`:

   ```typescript
   // BAD - dotenv is devDependency, not in production
   import "dotenv/config";

   // GOOD - DATABASE_URL already in environment
   import { defineConfig } from "prisma/config";
   ```

3. **Manual fix** - SSH to server and add missing columns:
   ```bash
   sudo docker exec POSTGRES_CONTAINER psql -U postgres -d postgres -c \
     "ALTER TABLE \"User\" ADD COLUMN IF NOT EXISTS \"tier\" TEXT DEFAULT 'free'"
   ```

**Prevention**: Always run `prisma db push` as part of container startup to keep schema in sync.

---

## Environment Variables Reference

### Development (.env.local)

```bash
# Database
DATABASE_URL="postgresql://user:pass@127.0.0.1:5432/mydb"

# Auth
BETTER_AUTH_SECRET="your-32-char-minimum-secret"
# Note: No NEXT_PUBLIC_SITE_URL needed - uses dynamic detection

# Google OAuth
AUTH_GOOGLE_ID="your-client-id.apps.googleusercontent.com"
AUTH_GOOGLE_SECRET="your-client-secret"
```

### Production

```bash
# Database
DATABASE_URL="postgresql://..."

# Auth
BETTER_AUTH_SECRET="production-secret-different-from-dev"
BETTER_AUTH_URL="https://your-production-domain.com"

# Google OAuth (same credentials work for both)
AUTH_GOOGLE_ID="your-client-id.apps.googleusercontent.com"
AUTH_GOOGLE_SECRET="your-client-secret"
```

### Key Differences

| Variable           | Development                 | Production                  |
| ------------------ | --------------------------- | --------------------------- |
| DATABASE_URL       | localhost PostgreSQL        | Production database         |
| BETTER_AUTH_SECRET | Dev secret                  | Production secret           |
| BETTER_AUTH_URL    | Not needed (uses localhost) | Required: production domain |
| AUTH*GOOGLE*\*     | Same for both               | Same for both               |

---

## Quick Reference: The Fix Summary

**Problem**: `NEXT_PUBLIC_SITE_URL` baked in at build time causes localhost to leak into production.

**Solution**:

1. **Client-side**: Use `window.location.origin` for dynamic URL detection
2. **Server-side**: Use `BETTER_AUTH_URL` (runtime env, not `NEXT_PUBLIC_*`)
3. **Hardcode production URL** as fallback for safety
4. **trustedOrigins**: Include both localhost and production
5. **Cookie config**: `sameSite: "lax"`, `secure: isProduction`
6. **CSP**: Allow Google OAuth domains

**Never rely on `NEXT_PUBLIC_*` for auth URLs.**
