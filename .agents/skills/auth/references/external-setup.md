# External Setup: Google Console, SES, Maillayer, Deploy, Testing

The non-code half of the login stack, in execution order. Each step lists who can do it (agent with stored credentials vs user in a dashboard).

## 1. Google Cloud Console (user, one-time per app)

1. console.cloud.google.com -> APIs & Services -> Credentials -> Create OAuth client ID -> Web application.
2. Authorized redirect URIs, BOTH, exact paths:
   - `http://localhost:3000/api/auth/callback/google`
   - `https://YOURDOMAIN/api/auth/callback/google`
3. Copy client ID + secret into env (`AUTH_GOOGLE_ID/SECRET`). Same client serves dev and prod.
4. The popup flow needs NO extra console config (same redirect URI).

## 2. SES domain verification (agent, via aws-cli skill)

Follow `.claude/skills/aws-cli/references/ses-v2.md` end to end with your scoped AWS profile. Summary: `create-email-identity` -> 3 DKIM CNAMEs + MAIL FROM MX/TXT + DMARC TXT into your DNS provider (DNS-only, unproxied) -> poll `get-email-identity` until DKIM/MailFrom = SUCCESS (typically under a minute). Once the DOMAIN is verified, any address at it can send.

## 3. Maillayer transactional template (user in dashboard, agent guides)

Self-hosted open-source Maillayer (e.g. `https://mail.acme.com`). Gotchas discovered the hard way:

- **Transactional templates live under the brand's "Transactional" sidebar section, NOT "Templates"** (that's campaigns). Same-looking editors; the API only sees transactional ones.
- **The send API uses the TEMPLATE-level key** (`txn_...`, on the template's API tab), not the brand-level key (`br_...`, which is the contacts API).
- **The template must be PUBLISHED** (editor -> publish); the API returns 403 for drafts.
- **Turn click tracking OFF** (template -> Edit -> Tracking). Tracked links rewrite the magic link through a redirect, and mail scanners that prefetch links consume the one-time token. Turn open tracking off too (login emails don't need analytics).
- Brand sender email can be any address at the SES-verified domain.
- Rate limit: 100 emails/minute per brand, far above login traffic.

Template setup: subject `Sign in to Acme`, body = the HTML below (uses `{{url}}`, auto-detected as a variable on paste).

```html
<!doctype html>
<html>
  <body
    style="margin:0;padding:0;background-color:#faf9f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
  >
    <table
      role="presentation"
      width="100%"
      cellpadding="0"
      cellspacing="0"
      style="padding:40px 16px;"
    >
      <tr>
        <td align="center">
          <table
            role="presentation"
            width="100%"
            cellpadding="0"
            cellspacing="0"
            style="max-width:420px;background-color:#ffffff;border:1px solid #e8e6df;border-radius:12px;padding:32px;"
          >
            <tr>
              <td
                style="font-size:18px;font-weight:600;color:#1a1a1a;padding-bottom:12px;"
              >
                Sign in to Acme
              </td>
            </tr>
            <tr>
              <td
                style="font-size:14px;line-height:1.6;color:#555550;padding-bottom:24px;"
              >
                Click the button below to sign in. This link expires shortly and
                can only be used once.
              </td>
            </tr>
            <tr>
              <td align="center" style="padding-bottom:24px;">
                <a
                  href="{{url}}"
                  style="display:inline-block;background-color:#c4633e;color:#ffffff;font-size:14px;font-weight:500;text-decoration:none;padding:12px 28px;border-radius:8px;"
                >
                  Sign in
                </a>
              </td>
            </tr>
            <tr>
              <td
                style="font-size:12px;line-height:1.6;color:#8a877e;border-top:1px solid #e8e6df;padding-top:16px;"
              >
                If the button does not work, copy this link into your
                browser:<br />
                <a href="{{url}}" style="color:#c4633e;word-break:break-all;"
                  >{{url}}</a
                >
                <br /><br />
                If you did not request this email, you can safely ignore it.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
```

Adjust the button color (`#c4633e`) and background (`#faf9f5`) to the target brand.

Pre-deploy smoke test of the pipeline (agent):

```bash
curl -X POST "https://MAILLAYER_HOST/api/transactional/send" \
  -H "Content-Type: application/json" \
  -d '{"apiKey":"txn_...","to":"you@example.com","variables":{"url":"https://YOURDOMAIN/login?test=pipeline"}}'
# expect 200 {"success":true,"messageId":"..."}
```

## 4. Production env (agent, Coolify API)

Set runtime env vars `MAILLAYER_API_URL` + `MAILLAYER_API_KEY` (plus `BETTER_AUTH_URL`, `AUTH_GOOGLE_*`, `BETTER_AUTH_SECRET` if a new app). Coolify gotcha: POST `/applications/{uuid}/envs` creates, PATCH only updates existing (despite runbook claims of upsert), and the flag is `is_buildtime` (`is_build_time` returns 422). Redeploy after (env is read at runtime by the magic-link sender, but the code ships with the deploy).

## 5. End-to-end verification checklist (agent + user)

Run in order; each step isolates one seam:

1. **Dev, no email infra**: POST `localhost:3000/api/auth/sign-in/magic-link` `{email, callbackURL:"/dashboard"}` -> 200 + link printed in dev-server console.
2. **Dev, full loop**: GET the printed verify URL with `redirect:'manual'` -> 302 to /dashboard + `better-auth.session_token` cookie + `get-session` returns the user. Proves DB writes + account creation.
3. **Same-account check**: magic link with an email that already signed in via Google must land in the SAME user (accountLinking); verify `get-session` shows the existing user id/name.
4. **Popup flow** (browser, user): login page -> Continue with Google -> small popup -> lands on /dashboard with the original tab never leaving the site.
5. **Maillayer pipeline**: curl test from section 3 -> email arrives, button href points DIRECTLY at the target URL (no mail-host redirect = tracking is off).
6. **Production**: POST `https://YOURDOMAIN/api/auth/sign-in/magic-link` (Origin header = the domain) -> 200 `{"status":true}` -> real email -> click -> dashboard.
