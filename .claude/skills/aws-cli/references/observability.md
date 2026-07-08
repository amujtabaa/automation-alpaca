# Observability Reference (CloudWatch Logs + Metrics)

All commands assume the session preamble ran (`$env:AWS_PAGER = ""`, identity verified) and use `--profile <YOUR_PROFILE> --region <YOUR_REGION> --output json`. Abbreviated below as `<P/R>`.

## Log group discovery

| Operation       | Command                                                                                                  | Notes / Safety |
| --------------- | -------------------------------------------------------------------------------------------------------- | -------------- |
| List log groups | `aws logs describe-log-groups <P/R> --output json --query 'logGroups[*].[logGroupName,retentionInDays]'` | Read           |

## Live tail (v2-exclusive)

| Operation        | Command                                                                    | Notes / Safety             |
| ---------------- | -------------------------------------------------------------------------- | -------------------------- |
| Tail live        | `aws logs tail /aws/lambda/<name> --follow <P/R>`                          | v2-exclusive; Ctrl+C exits |
| Tail with filter | `aws logs tail /aws/lambda/<name> --follow --filter-pattern "ERROR" <P/R>` | v2-exclusive               |

## Historical filter

| Operation         | Command                                                                                                                             | Notes / Safety             |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| Filter log events | `aws logs filter-log-events --log-group-name <group> --filter-pattern "REPORT" --start-time <epoch-ms> --end-time <epoch-ms> <P/R>` | Timestamps in MILLISECONDS |
| Filter with limit | `... --max-items 50 <P/R>`                                                                                                          | NextToken pagination       |

## Logs Insights

| Operation             | Command                                                                                                                                                                                                                                             | Notes / Safety                                         |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| Start Insights query  | `aws logs start-query --log-group-name <group> --start-time <epoch-s> --end-time <epoch-s> --query-string 'fields @timestamp, @message \| filter @message like /ERROR/ \| sort @timestamp desc \| limit 200' --query 'queryId' --output text <P/R>` | Timestamps in SECONDS (differs from filter-log-events) |
| Poll Insights results | `aws logs get-query-results --query-id <qid> <P/R>`                                                                                                                                                                                                 | Poll until status Complete                             |

## Metrics and alarms

| Operation             | Command                                                                                                                                                                                                           | Notes / Safety       |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------- |
| Get metric statistics | `aws cloudwatch get-metric-statistics --namespace AWS/Lambda --metric-name Errors --dimensions Name=FunctionName,Value=<name> --start-time <ISO8601Z> --end-time <ISO8601Z> --period 3600 --statistics Sum <P/R>` | ISO 8601 UTC strings |
| List alarms           | `aws cloudwatch describe-alarms <P/R> --output json --query 'MetricAlarms[*].[AlarmName,StateValue,MetricName]'`                                                                                                  | Read                 |

## Timestamp-unit trap (the #1 empty-result cause)

Three different timestamp formats live in this one domain:

- `logs filter-log-events`: epoch MILLISECONDS
- `logs start-query` (Insights): epoch SECONDS
- `cloudwatch get-metric-statistics`: ISO 8601 UTC strings

A unit mismatch yields EMPTY results with NO error. If a query returns nothing unexpectedly, check the timestamp unit before anything else.

Metric rounding: data points <15 days old round to the minute; 15-63 days to 5 minutes; >63 days to the hour.

## IAM actions the profile needs per task

- Logs read: `logs:DescribeLogGroups`, `logs:DescribeLogStreams`, `logs:GetLogEvents`, `logs:FilterLogEvents`
- Insights: + `logs:StartQuery`, `logs:GetQueryResults`
- Metrics/alarms: `cloudwatch:GetMetricStatistics`, `cloudwatch:DescribeAlarms`
