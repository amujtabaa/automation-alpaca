# SES v2 Reference (aws sesv2)

All commands assume the session preamble ran (`$env:AWS_PAGER = ""`, identity verified) and use `--profile <YOUR_PROFILE> --region <YOUR_REGION> --output json`. Abbreviated below as `<P/R>`.

## v1 vs v2: always sesv2

`aws ses` is the legacy v1 API; it lacks suppression lists, BYODKIM, MAIL FROM config, and modern deliverability controls. Every operation below uses `aws sesv2`.

| Operation     | Legacy (do not use)                 | Correct                                            |
| ------------- | ----------------------------------- | -------------------------------------------------- |
| Verify domain | `ses verify-domain-identity`        | `sesv2 create-email-identity`                      |
| DKIM          | `ses verify-domain-dkim`            | `sesv2 put-email-identity-dkim-signing-attributes` |
| MAIL FROM     | `ses set-identity-mail-from-domain` | `sesv2 put-email-identity-mail-from-attributes`    |
| Suppression   | not supported                       | `sesv2 *-suppressed-destination(s)`                |
| Quota         | `ses get-send-quota`                | `sesv2 get-account`                                |

## Account health

```powershell
# Sending enabled? Quota? Sandbox or production?
aws sesv2 get-account <P/R> --query '{Enabled:SendingEnabled, Prod:ProductionAccessEnabled, Max24h:SendQuota.Max24HourSend, Sent24h:SendQuota.SentLast24Hours}'
```

## Domain identity lifecycle (the standard new-domain flow)

```powershell
# 0. Read first: does the identity already exist?
aws sesv2 get-email-identity --email-identity example.com <P/R>
# -> NotFoundException means safe to create; anything else means STOP and inspect.

# 1. Create (Easy DKIM 2048 by default)
aws sesv2 create-email-identity --email-identity example.com <P/R>

# 2. Pull the 3 DKIM tokens
aws sesv2 get-email-identity --email-identity example.com <P/R> --query 'DkimAttributes.Tokens'
```

Each token becomes one DNS CNAME (Cloudflare on this setup, DNS-only/grey cloud, NOT proxied):

```
<TOKEN>._domainkey.example.com  CNAME  <TOKEN>.dkim.amazonses.com
```

```powershell
# 3. Custom MAIL FROM (best practice: SPF alignment for DMARC)
aws sesv2 put-email-identity-mail-from-attributes --email-identity example.com --mail-from-domain mail.example.com --behavior-on-mx-failure USE_DEFAULT_VALUE <P/R>
```

MAIL FROM needs two DNS records (also DNS-only):

```
mail.example.com  MX   10 feedback-smtp.<YOUR_REGION>.amazonses.com
mail.example.com  TXT  "v=spf1 include:amazonses.com ~all"
```

DMARC (on the root domain, start at monitor-only):

```
_dmarc.example.com  TXT  "v=DMARC1; p=none;"
```

```powershell
# 4. Poll verification (no waiter exists; DNS usually propagates in minutes)
aws sesv2 get-email-identity --email-identity example.com <P/R> --query '{Verified:VerifiedForSendingStatus, Dkim:DkimAttributes.Status}'
# Dkim goes PENDING -> SUCCESS. Cap polling (e.g. 10 tries x 60s) and report if still pending; worst case is 72h.
```

## Suppression list (bounces/complaints)

```powershell
aws sesv2 list-suppressed-destinations <P/R> --max-items 100
aws sesv2 get-suppressed-destination --email-address user@example.com <P/R>
aws sesv2 delete-suppressed-destination --email-address user@example.com <P/R>   # mutation gate applies
```

## Test send (verify end-to-end after setup)

```powershell
# Simple content needs no file://; anything with HTML body should use --cli-input-json file://
aws sesv2 send-email --from-email-address "noreply@example.com" --destination "ToAddresses=you@example.com" --content "Simple={Subject={Data=SES test},Body={Text={Data=It works}}}" <P/R>
```

## IAM actions the profile needs per task

- Read/audit: `ses:GetAccount`, `ses:GetEmailIdentity`, `ses:ListEmailIdentities`, `ses:ListSuppressedDestinations`
- Domain setup: + `ses:CreateEmailIdentity`, `ses:PutEmailIdentityDkimSigningAttributes`, `ses:PutEmailIdentityMailFromAttributes`
- Suppression management: + `ses:PutSuppressedDestination`, `ses:DeleteSuppressedDestination`
- Test sending: + `ses:SendEmail`

`AmazonSESFullAccess` covers all of the above. AccessDenied -> report the missing action; do not work around.
