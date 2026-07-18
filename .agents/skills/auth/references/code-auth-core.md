# Auth Core: Server Config, Client, Email Sender, Schema

Battle-tested across production deployments. Carbon-copy these files, then apply the find/replace list. Code lives in a shared package (`packages/auth`, alias `@acme/auth`) in a monorepo; in a single-app repo put it in `src/lib/auth/` and adjust imports.

## Find/replace when porting

| Placeholder in this doc   | Replace with                                                                                              |
| ------------------------- | --------------------------------------------------------------------------------------------------------- |
| `https://acme.com`        | your production origin                                                                                    |
| `.acme.com`               | your cookie domain (only if subdomains share the session; otherwise DELETE the domain attribute entirely) |
| `@acme/auth` / `@acme/db` | your package aliases or local paths                                                                       |
| `Acme`                    | your product name                                                                                         |
| `/dashboard`              | your post-login destination                                                                               |

## 1. Server config (`packages/auth/src/index.ts`)

This config includes an OPTIONAL extension marked below (username/role/banned generated per user). Skip the marked blocks for a standard app.

```ts
import { betterAuth } from "better-auth";
import { prismaAdapter } from "better-auth/adapters/prisma";
import { magicLink } from "better-auth/plugins";
import { headers } from "next/headers";
import { cache } from "react";

import { db } from "@acme/db";

import { sendMagicLinkEmail } from "./email";

const isProduction = process.env.NODE_ENV === "production";
const isDevelopment = process.env.NODE_ENV === "development";

// Canonical production domain. The leading dot scopes the cookie to all
// subdomains under the apex (only needed if subdomains share the session).
const PRODUCTION_URL = "https://acme.com";
const COOKIE_DOMAIN = ".acme.com";

/**
 * Server-side base URL.
 * Priority: BETTER_AUTH_URL (runtime env) > localhost in dev > production URL.
 * Never derived from NEXT_PUBLIC_* (avoids build-time inlining of localhost).
 */
const getServerBaseUrl = (): string => {
  if (process.env.BETTER_AUTH_URL) return process.env.BETTER_AUTH_URL;
  if (isDevelopment) return "http://localhost:3000";
  return PRODUCTION_URL;
};

export const auth = betterAuth({
  database: prismaAdapter(db, { provider: "postgresql" }),
  baseURL: getServerBaseUrl(),
  secret: process.env.BETTER_AUTH_SECRET,
  trustedOrigins: [
    "http://localhost:3000",
    PRODUCTION_URL,
    ...(process.env.BETTER_AUTH_URL ? [process.env.BETTER_AUTH_URL] : []),
  ],

  // Sign-in surface is magic link + Google ONLY. No emailAndPassword block:
  // new users are created on first magic-link use or first Google sign-in,
  // and accountLinking below merges both methods into one account by email.
  plugins: [
    magicLink({
      sendMagicLink: async ({ email, url }) => {
        await sendMagicLinkEmail({ email, url });
      },
    }),
  ],

  socialProviders: {
    google: {
      clientId: process.env.AUTH_GOOGLE_ID ?? "",
      clientSecret: process.env.AUTH_GOOGLE_SECRET ?? "",
    },
  },

  // ── OPTIONAL (app-specific): per-user @username namespace ──────────────
  // user: {
  //   additionalFields: {
  //     username: { type: "string", required: false, input: false },
  //     role: { type: "string", required: false, input: false },
  //     banned: { type: "boolean", required: false, input: false },
  //   },
  // },
  // databaseHooks: {
  //   user: {
  //     create: {
  //       before: async (user) => {
  //         const username = await generateUniqueUsername({
  //           email: user.email,
  //           name: user.name,
  //         });
  //         return { data: { ...user, username } };
  //       },
  //     },
  //   },
  // },
  // ─────────────────────────────────────────────────────────────────────────

  account: {
    accountLinking: { enabled: true },
  },

  session: {
    freshAge: 0, // use the cached cookie immediately (no loading flash)
    cookieCache: { enabled: true },
  },

  advanced: {
    defaultCookieAttributes: {
      secure: isProduction, // HTTPS-only in prod; http localhost in dev
      httpOnly: true,
      sameSite: "lax", // required so OAuth redirect carries the cookie
      path: "/",
      // Subdomain-scoped only in production; host-only locally so dev works.
      // DELETE this line entirely if subdomains don't share the session.
      ...(isProduction ? { domain: COOKIE_DOMAIN } : {}),
    },
  },

  onAPIError: {
    onError: (error) => {
      console.error("[BetterAuth Error]:", error);
    },
  },
});

export type Session = typeof auth.$Infer.Session;

/** Cached per-request server session getter (cookie-based). */
export const getServerSession = cache(async () => {
  return auth.api.getSession({ headers: await headers() });
});
```

## 2. Client (`packages/auth/src/client.ts`)

```ts
"use client";

import { magicLinkClient } from "better-auth/client/plugins";
import { createAuthClient } from "better-auth/react";

const PRODUCTION_URL = "https://acme.com";

const getBaseUrl = (): string => {
  if (typeof window !== "undefined") return window.location.origin;
  // SSR fallback - not used for real auth calls (those run in the browser).
  return PRODUCTION_URL;
};

export const authClient = createAuthClient({
  baseURL: getBaseUrl(),
  plugins: [magicLinkClient()],
});

export const { useSession, signIn, signOut } = authClient;
```

`window.location.origin` (not `NEXT_PUBLIC_*`) is THE key decision: NEXT_PUBLIC vars are inlined at BUILD time, so a localhost build env permanently bakes localhost into prod bundles. Dynamic origin works identically on localhost and production.

## 3. Magic-link email sender (`packages/auth/src/email.ts`)

Sends through self-hosted Maillayer (open-source build). Contract verified against the source (`mddanishyusuf/maillayer-client`, `src/pages/api/transactional/send.js`).

```ts
// Magic-link email delivery.
//   POST {MAILLAYER_API_URL}/api/transactional/send
//   body { apiKey, to, variables } -> 200 { success, messageId }
// The apiKey is the TEMPLATE-level key (template's API tab), which selects the
// template, brand, sender, and SES credentials server-side. The template holds
// the email design with a {{url}} variable. Click tracking must be DISABLED on
// the template (tracked links would let scanners consume the one-time token).

const isDevelopment = process.env.NODE_ENV === "development";

type MaillayerConfig = {
  /** Base URL of the self-hosted instance, e.g. https://mail.example.com */
  apiUrl: string;
  /** TEMPLATE-level API key (template -> API tab), not the brand key. */
  apiKey: string;
};

function getMaillayerConfig(): MaillayerConfig | null {
  const apiUrl = process.env.MAILLAYER_API_URL;
  const apiKey = process.env.MAILLAYER_API_KEY;
  if (!apiUrl || !apiKey) return null;
  return { apiUrl: apiUrl.replace(/\/+$/, ""), apiKey };
}

/**
 * Send the BetterAuth magic-link email. Throws on delivery failure so the
 * magicLink plugin surfaces an error to the login form instead of pretending
 * the email went out. Maillayer's send is synchronous (200 = handed to SES).
 *
 * Dev with no Maillayer env vars: the link prints to the server console, so
 * local sign-in needs zero email infrastructure. Prod with missing env: hard
 * error (silence would strand users on the "check your inbox" screen).
 */
export async function sendMagicLinkEmail({
  email,
  url,
}: {
  email: string;
  url: string;
}): Promise<void> {
  const config = getMaillayerConfig();

  if (!config) {
    if (isDevelopment) {
      console.log(`\n[magic-link] Sign-in link for ${email}:\n${url}\n`);
      return;
    }
    throw new Error(
      "Email sending is not configured (MAILLAYER_API_URL / MAILLAYER_API_KEY missing).",
    );
  }

  const response = await fetch(`${config.apiUrl}/api/transactional/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      apiKey: config.apiKey,
      to: email,
      variables: { url },
    }),
  });

  const body = await response.text().catch(() => "");
  if (!response.ok) {
    console.error(
      `[magic-link] Maillayer delivery failed (${response.status}):`,
      body.slice(0, 300),
    );
    throw new Error("Failed to send the login email. Please try again.");
  }
}
```

## 4. API route handler (`apps/web/src/app/api/auth/[...all]/route.ts`)

```ts
// BetterAuth catch-all handler. Serves every /api/auth/* endpoint
// (callback/google, sign-in, sign-out, session, ...) from the auth config.
import { toNextJsHandler } from "better-auth/next-js";

import { auth } from "@acme/auth";

export const { GET, POST } = toNextJsHandler(auth);
```

## 5. Prisma models (BetterAuth core set)

```prisma
model User {
  id            String   @id @default(cuid())
  name          String?
  email         String   @unique
  emailVerified Boolean  @default(false)
  image         String?
  createdAt     DateTime @default(now())
  updatedAt     DateTime @updatedAt

  accounts Account[]
  sessions Session[]

  // OPTIONAL (app-specific): username String @unique, role, banned
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

## 6. Environment variables

```bash
# ── Dev (.env at repo root, loaded via dotenv -c) ──
DATABASE_URL="postgresql://user:pass@127.0.0.1:5432/app"
BETTER_AUTH_SECRET="dev-secret-32-chars-minimum"
BETTER_AUTH_URL="http://localhost:3000"
AUTH_GOOGLE_ID="...apps.googleusercontent.com"   # same client as prod
AUTH_GOOGLE_SECRET="GOCSPX-..."
# MAILLAYER_* unset in dev -> magic links print to the dev server console

# ── Production (deployment platform, runtime) ──
BETTER_AUTH_URL="https://acme.com"
AUTH_GOOGLE_ID / AUTH_GOOGLE_SECRET   # same values
MAILLAYER_API_URL="https://mail.acme.com"
MAILLAYER_API_KEY="txn_..."           # TEMPLATE-level key
```

Dependencies: `better-auth` (pin >=1.6.2 for advisories), `@prisma/client`. No email SDK needed (plain fetch to Maillayer).
