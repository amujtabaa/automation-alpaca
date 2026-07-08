# Networking + DNS Reference (Route53 / CloudFront)

All commands assume the session preamble ran (`$env:AWS_PAGER = ""`, identity verified) and use `--profile <YOUR_PROFILE> --region <YOUR_REGION> --output json`. Abbreviated below as `<P/R>`.

## Hosted zones

| Operation         | Command                                                                                                   | Notes / Safety                            |
| ----------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| List hosted zones | `aws route53 list-hosted-zones <P/R> --output json --query 'HostedZones[*].[Name,Id,Config.PrivateZone]'` | Read; strip `/hostedzone/` prefix from Id |
| Zone ID by name   | `aws route53 list-hosted-zones <P/R> --query "HostedZones[?Name=='example.com.'].Id" --output text`       | Trailing dot significant                  |

## Reading records

| Operation         | Command                                                                                   | Notes / Safety       |
| ----------------- | ----------------------------------------------------------------------------------------- | -------------------- |
| List records      | `aws route53 list-resource-record-sets --hosted-zone-id <ZONE_ID> <P/R>`                  | Read; auto-paginates |
| Get change status | `aws route53 get-change --id <CHANGE_ID> <P/R> --output json --query 'ChangeInfo.Status'` | PENDING vs INSYNC    |

## Batch changes (always file://)

| Operation             | Command                                                                                                                | Notes / Safety                                      |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| Batch change (UPSERT) | `aws route53 change-resource-record-sets --hosted-zone-id <ZONE_ID> --change-batch file://$env:TEMP/change.json <P/R>` | Mutation; transactional all-or-none; always file:// |
| Wait INSYNC           | `aws route53 wait resource-record-sets-changed --id <CHANGE_ID> <P/R>`                                                 | Poll until INSYNC                                   |

Change-batch template (`file://`): `Comment` + `Changes[]` of `{Action: UPSERT|CREATE|DELETE, ResourceRecordSet: {Name (trailing dot), Type, TTL, ResourceRecords[]}}`.

- Prefer UPSERT: rerun-safe (create-or-replace), the natural idempotency primitive for DNS.
- GATE on DELETE: the request must byte-match the stored record (Name, Type, TTL, values); read it first with `list-resource-record-sets` or you get `InvalidChangeBatch`.

## CloudFront

| Operation                 | Command                                                                                                                                 | Notes / Safety                                         |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| List distributions        | `aws cloudfront list-distributions <P/R> --output json --query 'DistributionList.Items[*].[Id,DomainName,Origins.Items[0].DomainName]'` | Read                                                   |
| Get distribution          | `aws cloudfront get-distribution --id <DIST_ID> <P/R>`                                                                                  | Read                                                   |
| Invalidate paths          | `aws cloudfront create-invalidation --distribution-id <DIST_ID> --paths "/index.html" "/assets/*" <P/R>`                                | Mutation; first 1000 paths/month free                  |
| Invalidate all            | `... --paths "/*" <P/R>`                                                                                                                | GATE: full cache purge; appropriate after full deploys |
| Invalidate via batch file | `... --invalidation-batch file://$env:TEMP/inv.json <P/R>`                                                                              | CallerReference = idempotency                          |
| Wait invalidation         | `aws cloudfront wait invalidation-completed --distribution-id <DIST_ID> --id <INV_ID> <P/R>`                                            | 1-5 min typical                                        |

## IAM actions the profile needs per task

- Route53 read: `route53:ListHostedZones`, `route53:ListResourceRecordSets`, `route53:GetChange`
- Route53 write: + `route53:ChangeResourceRecordSets`
- CloudFront: `cloudfront:ListDistributions`, `cloudfront:GetDistribution`, `cloudfront:CreateInvalidation`, `cloudfront:GetInvalidation` (needed by the wait)
