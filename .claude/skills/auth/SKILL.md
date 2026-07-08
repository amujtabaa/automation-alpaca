---
name: auth
description: Carbon-copy login system for new Next.js sites - BetterAuth magic link (email-only, via self-hosted Maillayer + SES) plus Google OAuth in a popup, session-aware avatar menu, accounts auto-created on first sign-in. Battle-tested across production deployments, 2026. Load references/ for verbatim implementation files and external setup. Also covers debugging login problems, OAuth redirect issues, session/cookie config.
---

# Auth: The Standard Login Stack (Carbon-Copy)

The complete, production-proven login system to drop into any new Next.js site. This is a battle-tested implementation: magic link + popup Google, no passwords. Copy verbatim first, rebrand after (per the porting standard).

## What the user gets

- `/login`: one email field ("Send me a magic link") + "Continue with Google". No password, no separate register page (`/register` redirects to `/login`; accounts auto-create on first sign-in).
- Google opens in a small centered POPUP, so the user never leaves the site; falls back to full-page redirect if blocked.
- Magic link emails sent from the product's own domain via self-hosted Maillayer -> Amazon SES (zero vendor cost, DKIM-signed). In dev with no email env, links print to the server console.
- Header shows a Sign-in button that becomes the user's Google avatar; clicking opens name/email + Dashboard + Log out.
- Same email via Google AND magic link = same account (accountLinking).

## Stack

BetterAuth (>=1.6.2) + Prisma/Postgres + Next.js App Router + shadcn. Email: Maillayer (self-hosted) -> SES.

## References (load per task)

| File                                   | Contents                                                                                                                                                         |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `references/code-auth-core.md`         | Server config, client, Maillayer email sender, route handler, Prisma models, env vars, find/replace list                                                         |
| `references/code-login-ui.md`          | All pages + components verbatim: layout, login, magic-link form, popup Google button, popup-complete bridge, verify, register redirect, UserMenu + header wiring |
| `references/external-setup.md`         | Google Console, SES/DNS (via aws-cli skill), Maillayer template gotchas + email HTML, Coolify env, end-to-end test checklist                                     |
| `references/betterauth-methodology.md` | Deep methodology: full code snippets, CSP config, cookie internals, Prisma schema, complete env reference                                                        |

## Porting order (new site)

1. Prisma models (User/Session/Account/Verification) -> `db push`.
2. Auth core: server config + client + email.ts + route handler (code-auth-core.md). Apply find/replace list.
3. UI: the seven files in code-login-ui.md. Point every signup CTA at `/login`.
4. Wire `<UserMenu />` into the site's REAL header. Verify which header component the layout actually imports; don't assume.
5. External: Google Console redirect URIs; SES domain (aws-cli skill); Maillayer template (template-level `txn_` key, published, click tracking OFF).
6. Env: dev needs only DATABASE*URL/BETTER_AUTH_SECRET/AUTH_GOOGLE*\* (magic links print to console). Prod adds BETTER_AUTH_URL + MAILLAYER_API_URL/KEY.
7. Run the 6-step verification checklist in external-setup.md before calling it done.

## Key decisions (do not regress these)

1. **Never `NEXT_PUBLIC_*` for auth URLs.** They inline at BUILD time; a localhost build bakes localhost into prod. Client uses `window.location.origin`; server uses runtime `BETTER_AUTH_URL` with localhost/prod fallbacks.
2. **`sameSite: "lax"`** because strict blocks the OAuth redirect cookie. `secure` only in production (true in dev breaks http localhost).
3. **Magic link + Google only, no emailAndPassword** because one credential-less surface, accounts auto-create, account-linking merges methods by email.
4. **Popup OAuth requires no COOP headers** (they sever `window.opener`) and the popup must be opened SYNCHRONOUSLY in the click handler (blockers), with the OAuth URL assigned after `signIn.social({ disableRedirect: true })` returns it.
5. **Click tracking OFF on the magic-link email template** because scanners prefetch tracked links and burn one-time tokens.
6. **Email failures must THROW** from sendMagicLink so the form shows an error instead of a fake "check your inbox".
7. **Dev console fallback** for the magic link, so local sign-in needs zero email infra.

## Troubleshooting (field-tested)

- **Login button does nothing, no error**: missing `AUTH_GOOGLE_*`/DATABASE_URL in the env the dev server actually loaded; or the dev server predates the env change. Next reads env at process start, so restart it. Check the network tab: POST `/api/auth/sign-in/social` 500.
- **OAuth redirects to localhost in production**: the NEXT_PUBLIC inlining bug (decision 1).
- **`redirect_uri_mismatch`**: console entry must be the exact path `/api/auth/callback/google`, not just the origin.
- **`internal_server_error` after Google consent**: usually DATABASE schema drift, not auth config. A User column the code expects is missing in that environment. Diagnose with `SELECT column_name FROM information_schema.columns WHERE table_name = 'User'`.
- **Magic link 200 but no email**: in dev that's by design (console). In prod check MAILLAYER*\* env, template is PUBLISHED, and the key is the template-level `txn*`key, not the brand`br\_` key.
- **Blog/marketing pages break after CSP edits for OAuth**: needed domains are `accounts.google.com` (script/frame/form-action/connect), `oauth2.googleapis.com` + `www.googleapis.com` (connect), `*.googleusercontent.com` (img, avatars).
- **Session not visible in header after popup login**: the opener tab must `router.refresh()` on the completion message (already in the button code); cookies set in the popup apply origin-wide.
- **White screen after killing/restarting the dev server**: corrupted `.next`. Delete it and restart; hard-refresh the browser tab.
