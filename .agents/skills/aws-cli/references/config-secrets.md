# Config + Secrets Reference (SSM Parameter Store / Secrets Manager)

All commands assume the session preamble ran (`$env:AWS_PAGER = ""`, identity verified) and use `--profile <YOUR_PROFILE> --region <YOUR_REGION> --output json`. Abbreviated below as `<P/R>`.

## Decision matrix: which store

| Need                             | Use                    |
| -------------------------------- | ---------------------- |
| Config strings / feature flags   | SSM Standard (free)    |
| Rotating DB passwords / API keys | Secrets Manager (paid) |
| Cross-account access             | Secrets Manager        |
| Values over 4KB/8KB              | Secrets Manager (64KB) |
| Automatic rotation               | Secrets Manager        |
| High-frequency reads             | SSM                    |

## SSM Parameter Store

| Operation            | Command                                                                                               | Notes / Safety                                             |
| -------------------- | ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| SSM put String       | `aws ssm put-parameter --name "/myapp/prod/setting" --type String --value "myvalue" <P/R>`            | Mutation                                                   |
| SSM put SecureString | `aws ssm put-parameter --name "/myapp/prod/dbpassword" --type SecureString --value "secret123" <P/R>` | Mutation; AWS-managed KMS; --key-id alias/<key> for custom |
| SSM overwrite        | `... --overwrite <P/R>`                                                                               | Mutation; new version                                      |
| SSM get (decrypted)  | `aws ssm get-parameter --name "/myapp/prod/dbpassword" --with-decryption <P/R>`                       | Read; plaintext; never log                                 |
| SSM get value only   | `... --query 'Parameter.Value' --output text`                                                         | Pipe-friendly                                              |
| SSM get by path      | `aws ssm get-parameters-by-path --path "/myapp/prod/" --with-decryption --recursive <P/R>`            | Read                                                       |
| SSM delete           | `aws ssm delete-parameter --name "/myapp/prod/dbpassword" <P/R>`                                      | GATE: confirm exact name                                   |

## Secrets Manager

| Operation               | Command                                                                                                            | Notes / Safety                                           |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------- |
| SM create secret        | `aws secretsmanager create-secret --name "myapp/prod/db-creds" --secret-string file://$env:TEMP/secret.json <P/R>` | Mutation; inline JSON forbidden on PS5.1, always file:// |
| SM get value            | `aws secretsmanager get-secret-value --secret-id "myapp/prod/db-creds" <P/R>`                                      | Read; --query 'SecretString' --output text for piping    |
| SM list / describe      | `aws secretsmanager list-secrets <P/R>` / `describe-secret --secret-id <id> <P/R>`                                 | Read; describe shows metadata only                       |
| SM update               | `aws secretsmanager update-secret --secret-id <id> --secret-string file://$env:TEMP/newsecret.json <P/R>`          | Mutation                                                 |
| SM delete (recoverable) | `aws secretsmanager delete-secret --secret-id <id> <P/R>`                                                          | GATE: 30-day recovery window default                     |
| SM delete (immediate)   | `... --force-delete-without-recovery <P/R>`                                                                        | GATE: irreversible                                       |

## Cross-reference path

| Operation       | Command                                                                                              | Notes / Safety                |
| --------------- | ---------------------------------------------------------------------------------------------------- | ----------------------------- |
| SM via SSM path | `aws ssm get-parameter --name "/aws/reference/secretsmanager/<secret-name>" --with-decryption <P/R>` | Read; cross-service reference |

## Safety notes

- Decrypted values (`--with-decryption`, `get-secret-value`) are plaintext in tool output: never echo into logs, scripts, or files that could be committed (core rule 8 applies doubly here).
- Secret payloads always travel via `file://` temp files on PowerShell 5.1; delete the temp file after the call.

## IAM actions the profile needs per task

- SSM read: `ssm:GetParameter`, `ssm:GetParametersByPath` (+ `kms:Decrypt` for SecureString with a customer-managed key)
- SSM write: + `ssm:PutParameter`, `ssm:DeleteParameter`
- Secrets Manager read: `secretsmanager:GetSecretValue`, `secretsmanager:ListSecrets`, `secretsmanager:DescribeSecret`
- Secrets Manager write: + `secretsmanager:CreateSecret`, `secretsmanager:UpdateSecret`, `secretsmanager:DeleteSecret`
