# Cost Reference (Cost Explorer + Budgets)

All commands assume the session preamble ran (`$env:AWS_PAGER = ""`, identity verified) and use `--profile <YOUR_PROFILE> --region <YOUR_REGION> --output json`. Abbreviated below as `<P/R>`.

EXCEPTION to region pinning: Cost Explorer (`ce`) is a global service; ALWAYS pass `--region us-east-1` for `ce` calls regardless of your primary region.

## Cost and usage

| Operation           | Command                                                                                                                                                                              | Notes / Safety                    |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------- |
| Monthly by service  | `aws ce get-cost-and-usage --time-period Start=<YYYY-MM-01>,End=<YYYY-MM-01> --granularity MONTHLY --metrics BlendedCost --group-by Type=DIMENSION,Key=SERVICE <P/R> --no-cli-pager` | $0.01 per call; use sparingly     |
| Daily current month | `... --granularity DAILY --metrics UnblendedCost <P/R>`                                                                                                                              | Anomaly spotting                  |
| Filter one service  | `... --filter file://$env:TEMP/cefilter.json <P/R>`                                                                                                                                  | Inline JSON breaks PS5.1; file:// |

## Budgets

| Operation       | Command                                                                                                                                                                | Notes / Safety                                                                        |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| List budgets    | `aws budgets describe-budgets --account-id <ACCOUNT_ID> <P/R>`                                                                                                         | account-id mandatory, NOT inferred; get via `sts get-caller-identity --query Account` |
| Describe budget | `aws budgets describe-budget --account-id <ACCOUNT_ID> --budget-name <name> <P/R>`                                                                                     | Read                                                                                  |
| Create budget   | `aws budgets create-budget --account-id <ACCOUNT_ID> --budget file://$env:TEMP/budget.json --notifications-with-subscribers file://$env:TEMP/notifications.json <P/R>` | Mutation; names unique per account; no `:`/`\`/`/action/`                             |

## API pricing note

The Cost Explorer API is NOT free: $0.01 per call. Console reads are free. Batch your questions into one grouped query rather than many small calls, and never poll `ce` in a loop.
