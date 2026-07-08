---
name: aws-cli
description: AWS CLI v2 operating rules for AI-assisted infra work (Windows 11 / PowerShell 5.1). Credential verification, profile/region pinning, output parsing, pagination, safe-mutation gates, waiters, idempotency. Per-domain references cover SES v2 email infrastructure, S3, IAM/STS, Lambda/ECR/ECS, CloudWatch Logs and metrics, SSM Parameter Store and Secrets Manager, Route53/CloudFront, Cost Explorer and Budgets, plus PowerShell quoting/encoding pitfalls.
---

# AWS CLI v2 (AI-Assisted Operations)

Operating manual for driving the AWS CLI consistently and without errors. AWS is critical infrastructure: a wrong call can break email sending or leak access. Follow every rule; they exist because each one is a documented failure mode.

## Account Setup (conventions)

Establish these conventions once for the target environment, then pin them on every call. Two placeholder slots are used throughout this skill:

| Slot             | Meaning                                                                               |
| ---------------- | ------------------------------------------------------------------------------------- |
| `<YOUR_PROFILE>` | A named profile in `~/.aws/credentials` mapped to a scoped IAM user for AI work       |
| `<YOUR_REGION>`  | The region your resources live in; always pass it explicitly, never rely on a default |

Conventions:

- **CLI**: AWS CLI v2 (`aws` on PATH; on Windows, install via winget).
- **Shell**: PowerShell 5.1 (backtick continuation, `$LASTEXITCODE`, no jq, no `xargs`). See `references/powershell-windows.md`.
- **Profile**: use a dedicated, narrowly scoped IAM user for AI-driven work, not a personal admin key.
- **Region**: pin one primary region and pass it on every call.
- **Other apps' keys**: never reuse or modify another application's send-only IAM key (e.g. an email app's dedicated SES credential); operate only through `<YOUR_PROFILE>`.

> example: a scoped IAM user profile named `ai-ops` pinned to `eu-central-1` (where its SES resources live).

## Session Preamble (run before anything else)

```powershell
$env:AWS_PAGER = ""          # CLI v2 pipes output to `more` by default -> hangs non-interactive sessions
aws sts get-caller-identity --profile <YOUR_PROFILE> --region <YOUR_REGION> --output json
```

Identity check is mandatory: confirms account, user, and live credentials in one cheap call. Wrong/expired profile fails here instead of mid-task.

Credential hygiene: leaked `AWS_*` env vars override the intended profile. Verify the returned ARN matches expectations; if it does not, list the strays with `Get-ChildItem Env: | Where-Object { $_.Name -like 'AWS_*' }` and `Remove-Item` them before proceeding.

## Core Rules

1. **Pin profile + region on every call**: `--profile <YOUR_PROFILE> --region <YOUR_REGION>`. Never rely on ambient defaults. If using env vars instead (`$env:AWS_PROFILE`), set once at block start and do not mix with `--profile` mid-session (`--profile` wins).
2. **`--output json` always**, plus `--query '<JMESPath>'` to extract just what you need. `--output text` only when feeding another command. Never `table` in automation. Parse JSON with `ConvertFrom-Json` or `node -e` (no jq on this box).
3. **Read before write.** Run the matching `get-*`/`list-*`/`describe-*` first, confirm a change is actually needed, then mutate. For EC2-class commands supporting it, `--dry-run` first. `s3 sync` gets a `--dryrun` pass before any `--delete`. Route53 DELETE requires reading the exact stored record first (any field mismatch returns `InvalidChangeBatch`).
4. **Mutation gate** (borrowed from aws-cost-audit-skill): mutate only when (a) current state confirmed by a read, (b) action is reversible or explicitly approved, (c) permissions verified (dry-run or prior identical call), (d) for destructive/irreversible actions the user has confirmed in this session.
5. **Check `$LASTEXITCODE` (not `$?`) after every call.** 0 = success; 1 = API error (denied/not found/invalid); 2 = CLI usage error. Stop the chain on non-zero. `ThrottlingException` -> retry with exponential backoff; `ExpiredToken` -> re-auth, never retry as-is. Waiter exit 255 = polling window exceeded, NOT necessarily failure: read the resource state before retrying. Default windows: lambda function-updated 5 min, ec2 snapshot 10 min, rds snapshot 30 min; extend with `--max-attempts`.
6. **Pagination**: CLI v2 auto-paginates by default (fetches ALL pages silently). For bounded reads use `--max-items N`, resume with `--starting-token`. Never mix `--page-size` and `--max-items` with conflicting values (causes missing/duplicate items).
7. **Complex JSON arguments go through `file://`**, never inline JSON in PowerShell 5.1 (CommandLineToArgvW double-escaping mangles it). Write payload with `Set-Content -Encoding utf8`, reference as `file://$env:TEMP/payload.json` with FORWARD slashes. Details: `references/powershell-windows.md`.
8. **No secrets in commands or files that could be committed.** Credentials live only in `~/.aws/credentials`. Never echo keys; never hardcode account IDs/ARNs in skill docs or scripts that land in a repo.
9. **No sleep-polling when a waiter exists** (`aws <svc> wait <condition>`). SES identity verification has no waiter: poll `get-email-identity` with a capped loop (DNS-dependent; usually minutes, up to 72h worst case).
10. **Long-running or risky work**: prefer one command per tool call over long `;`-chained one-liners, so each exit code is observed.
11. **Timestamp units differ per API**: `logs filter-log-events` = epoch MILLISECONDS; `logs start-query` (Insights) = epoch SECONDS; `cloudwatch get-metric-statistics` = ISO 8601 UTC strings. Mismatches yield empty results with NO error.
12. **CLI v2 breaking changes**: auto-pager is ON by default (set `$env:AWS_PAGER = ""` first, or `--no-cli-pager`); binary I/O is base64 by default (`fileb://` for zips/binary, `file://` for JSON); v2 does NOT fetch http(s):// parameter URLs (download to temp + `file://`); `cloudformation deploy` exits 0 on an empty changeset (v1 exited 1); `ecr get-login` is removed (use `get-login-password`); `--max-items` alone is the safe pagination pattern (a mismatched `--page-size` causes missing/duplicate items); `AWS_REGION` overrides `AWS_DEFAULT_REGION`, but pin `--region` per call anyway.
13. **Idempotency tokens**: pass deterministic `--client-request-token` / `--client-token` / CallerReference where supported (cloudfront create-invalidation, sts assume-role `--external-id`, Route53 via UPSERT) so retries return the existing result instead of duplicating work.

## Decision Tree

- SES / email domains / DKIM / MAIL FROM / suppression / quotas -> load `references/ses-v2.md` (use `aws sesv2`, NEVER legacy `aws ses`)
- S3 buckets / objects / sync / presigned URLs / bucket policy / static hosting -> load `references/s3.md`
- IAM users / access keys / policies / assume-role / identity checks -> load `references/iam-sts.md`
- Lambda deploy/invoke, ECR push, ECS deploys, EC2 reads, DynamoDB -> load `references/compute.md`
- CloudWatch logs (tail/filter/Insights), metrics, alarms -> load `references/observability.md`
- SSM Parameter Store / Secrets Manager (config + secrets) -> load `references/config-secrets.md`
- Route53 records / hosted zones / CloudFront invalidations -> load `references/networking-dns.md`
- Cost Explorer / Budgets / bill surprises -> load `references/cost.md` (ce is global: `--region us-east-1`)
- Any JSON payload, quoting error, weird "file not found" on file:// -> load `references/powershell-windows.md`
- New service not covered here -> `aws <service> help`, then read-only exploration first; consider whether the official AWS Agent Toolkit MCP server fits better (enterprise audit/approval gates; note it has NO SES coverage, CLI is the only SES path)
- IAM permission denied -> the scoped profile user is intentionally limited; report the missing action to the user rather than seeking workarounds

## References

- `references/ses-v2.md`: full SES v2 command set: identities, DKIM tokens -> DNS CNAMEs, MAIL FROM, DMARC, suppression list, send quotas
- `references/s3.md`: bucket/object lifecycle, sync + --delete danger, presigned URLs, bucket policy, static hosting, multipart tuning
- `references/iam-sts.md`: identity verification, scoped users/keys, managed/inline policies, policy simulation, assume-role, MFA sessions
- `references/compute.md`: Lambda deploy/invoke/waiters, ECR auth/push, ECS deploys, EC2 reads + --dry-run, DynamoDB footnote
- `references/observability.md`: log group discovery, live tail, filter-log-events, Logs Insights, metric statistics, alarms, timestamp traps
- `references/config-secrets.md`: SSM vs Secrets Manager decision matrix, put/get/delete flows, cross-reference path
- `references/networking-dns.md`: hosted zones, batch record changes via file://, INSYNC waits, CloudFront invalidations
- `references/cost.md`: get-cost-and-usage, budgets, API pricing note (calls cost $0.01)
- `references/powershell-windows.md`: PowerShell 5.1 quoting, file:// rules, encoding, exit codes, JSON parsing patterns
