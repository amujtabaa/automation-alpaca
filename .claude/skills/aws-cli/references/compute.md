# Compute Reference (Lambda / ECR / ECS, light EC2)

All commands assume the session preamble ran (`$env:AWS_PAGER = ""`, identity verified) and use `--profile <YOUR_PROFILE> --region <YOUR_REGION> --output json`. Abbreviated below as `<P/R>`.

## Lambda: deploy, update, publish, config

| Operation                | Command                                                                                                     | Notes / Safety                                          |
| ------------------------ | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| List functions           | `aws lambda list-functions <P/R> --output json --query 'Functions[*].[FunctionName,Runtime,LastModified]'`  | Read                                                    |
| Get function config      | `aws lambda get-function-configuration --function-name <name> <P/R>`                                        | Read                                                    |
| Update code (zip)        | `aws lambda update-function-code --function-name <name> --zip-file fileb://<func>.zip <P/R>`                | Mutation; fileb:// (binary) not file://                 |
| Update + publish version | `aws lambda update-function-code --function-name <name> --zip-file fileb://<func>.zip --publish <P/R>`      | Mutation; immutable version                             |
| Wait function-updated    | `aws lambda wait function-updated --function-name <name> <P/R>`                                             | 5s x 60 = 5 min window; exit 255 on timeout             |
| Update env vars          | `aws lambda update-function-configuration --function-name <name> --environment "Variables={KEY=val}" <P/R>` | GATE: replaces ENTIRE env map; read first, merge, write |

The env-vars gate is the classic Lambda foot-gun: `--environment` is a full replacement, not a merge. Read the current map with `get-function-configuration`, merge locally, then write the complete map back.

## Lambda: invoke and log capture

| Operation          | Command                                                                                                                        | Notes / Safety                |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------ | ----------------------------- |
| Invoke sync        | `aws lambda invoke --function-name <name> --payload '{}' out.json <P/R>`                                                       | Use fileb:// payload on PS5.1 |
| Invoke + tail logs | `aws lambda invoke --function-name <name> --log-type Tail --query 'LogResult' --output text out.json <P/R>` then base64-decode | Up to 4KB tail                |
| Tail logs live     | `aws logs tail /aws/lambda/<name> --follow <P/R>`                                                                              | v2-exclusive                  |

## ECR: repo, auth, push

| Operation           | Command                                                                                                                  | Notes / Safety                  |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------ | ------------------------------- |
| Create ECR repo     | `aws ecr create-repository --repository-name <name> <P/R> --output json --query 'repository.repositoryUri'`              | Mutation; AlreadyExists is safe |
| Docker login to ECR | `aws ecr get-login-password <P/R> \| docker login --username AWS --password-stdin <acct>.dkr.ecr.<region>.amazonaws.com` | get-login removed in v2         |
| List ECR images     | `aws ecr list-images --repository-name <name> <P/R>`                                                                     | Read                            |

## ECS: list, describe, update, wait

| Operation                  | Command                                                                                   | Notes / Safety                                              |
| -------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| List ECS clusters/services | `aws ecs list-clusters <P/R>` / `aws ecs list-services --cluster <cluster> <P/R>`         | Read                                                        |
| Describe ECS service       | `aws ecs describe-services --cluster <cluster> --services <svc> <P/R>`                    | Read; desired/running/pending                               |
| Force new deployment       | `aws ecs update-service --cluster <cluster> --service <svc> --force-new-deployment <P/R>` | Mutation                                                    |
| Wait services-stable       | `aws ecs wait services-stable --cluster <cluster> --services <svc> <P/R>`                 | Exit 255 on timeout; raise --max-attempts for slow services |

## EC2: describe + the --dry-run pattern

| Operation              | Command                                                                                                                         | Notes / Safety                                                             |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| EC2 describe instances | `aws ec2 describe-instances <P/R> --output json --query 'Reservations[*].Instances[*].[InstanceId,State.Name,PublicIpAddress]'` | Read                                                                       |
| EC2 dry-run check      | `aws ec2 start-instances --instance-ids i-<id> --dry-run <P/R>`                                                                 | DryRunOperation = allowed; UnauthorizedOperation = denied; no action taken |

EC2 fleet management is out of scope here; keep EC2 usage read-only plus the `--dry-run` permission probe. RDS likewise: `describe-*` only.

## DynamoDB footnote

v2 ships high-level `aws ddb put/select`. Low-level `get-item`/`scan`/`query` need `file://` for expression values on Windows. `scan` is a full-table read; prefer `query` with `--key-condition-expression`.

## IAM actions the profile needs per service

- Lambda read: `lambda:ListFunctions`, `lambda:GetFunctionConfiguration`
- Lambda deploy/run: + `lambda:UpdateFunctionCode`, `lambda:UpdateFunctionConfiguration`, `lambda:PublishVersion`, `lambda:InvokeFunction`
- ECR: `ecr:GetAuthorizationToken`, `ecr:CreateRepository`, `ecr:ListImages`; docker push additionally needs `ecr:BatchCheckLayerAvailability`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`, `ecr:PutImage`
- ECS: `ecs:ListClusters`, `ecs:ListServices`, `ecs:DescribeServices`, `ecs:UpdateService`
- EC2: `ec2:DescribeInstances`, `ec2:StartInstances` (for the dry-run probe)
