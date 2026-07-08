# IAM + STS Reference (aws iam / aws sts)

All commands assume the session preamble ran (`$env:AWS_PAGER = ""`, identity verified) and use `--profile <YOUR_PROFILE> --region <YOUR_REGION> --output json`. Abbreviated below as `<P/R>`.

## Identity verification (mandatory preamble)

| Operation       | Command                                           | Notes / Safety                                               |
| --------------- | ------------------------------------------------- | ------------------------------------------------------------ |
| Verify identity | `aws sts get-caller-identity <P/R> --output json` | Mandatory preamble; works even when all else is AccessDenied |

## Reading current state

| Operation                   | Command                                                                                  | Notes / Safety |
| --------------------------- | ---------------------------------------------------------------------------------------- | -------------- |
| List users                  | `aws iam list-users <P/R> --output json --query 'Users[*].[UserName,UserId,CreateDate]'` | Read           |
| List roles                  | `aws iam list-roles <P/R> --output json --query 'Roles[*].[RoleName,Arn]'`               | Read           |
| Describe user               | `aws iam get-user --user-name <name> <P/R>`                                              | Read           |
| List attached user policies | `aws iam list-attached-user-policies --user-name <name> <P/R>`                           | Read           |
| List inline user policies   | `aws iam list-user-policies --user-name <name> <P/R>`                                    | Read           |
| List access keys            | `aws iam list-access-keys --user-name <name> <P/R>`                                      | Read           |

## Creating scoped users and keys

| Operation             | Command                                                                                       | Notes / Safety                                                       |
| --------------------- | --------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Create user           | `aws iam create-user --user-name <name> <P/R>`                                                | Mutation; create only, no keys yet                                   |
| Create access key     | `aws iam create-access-key --user-name <name> <P/R>`                                          | GATE: SecretAccessKey shown ONCE; store immediately; never log       |
| Deactivate access key | `aws iam update-access-key --user-name <name> --access-key-id <AKID> --status Inactive <P/R>` | Mutation; precursor to deletion                                      |
| Delete access key     | `aws iam delete-access-key --user-name <name> --access-key-id <AKID> <P/R>`                   | GATE: irreversible; deactivate first                                 |
| Delete user           | `aws iam delete-user --user-name <name> <P/R>`                                                | GATE: detach policies + delete keys + remove group memberships first |

## Managed and inline policies

| Operation             | Command                                                                                                                | Notes / Safety                        |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| Attach managed policy | `aws iam attach-user-policy --user-name <name> --policy-arn arn:aws:iam::aws:policy/AmazonSESFullAccess <P/R>`         | Mutation; confirm exact ARN           |
| Detach managed policy | `aws iam detach-user-policy --user-name <name> --policy-arn <arn> <P/R>`                                               | Mutation                              |
| Put inline policy     | `aws iam put-user-policy --user-name <name> --policy-name <polname> --policy-document file://$env:TEMP/pol.json <P/R>` | Mutation; file:// on Windows          |
| Get inline policy     | `aws iam get-user-policy --user-name <name> --policy-name <polname> <P/R>`                                             | Read                                  |
| Delete inline policy  | `aws iam delete-user-policy --user-name <name> --policy-name <polname> <P/R>`                                          | Mutation                              |
| Simulate policy       | `aws iam simulate-principal-policy --policy-source-arn <user-arn> --action-names s3:PutObject <P/R>`                   | Read; validates before mutating; free |

`simulate-principal-policy` before mutations is free and underused: it answers "would this action be allowed" without performing it.

## Assume-role and MFA sessions

| Operation               | Command                                                                                                                        | Notes / Safety                                     |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------- |
| STS session token (MFA) | `aws sts get-session-token --duration-seconds 3600 --serial-number arn:aws:iam::<acct>:mfa/<user> --token-code <123456> <P/R>` | Temp creds for MFA-required ops                    |
| Assume role (manual)    | `aws sts assume-role --role-arn arn:aws:iam::<acct>:role/<RoleName> --role-session-name session1 <P/R>`                        | Temp creds; --external-id where required           |
| Assume role (profile)   | `role_arn` + `source_profile` in `~/.aws/config`; then `--profile <role-profile>`                                              | Preferred; CLI auto-refreshes via ~/.aws/cli/cache |

## Safety notes

- One scoped IAM user per operational domain (SES-send, S3-deploy); never reuse or expand another app's key.
- `create-access-key` shows the secret once only; losing it means rotate, not recover.
- Credential resolution order (first wins): `--profile`/env vars, `~/.aws/credentials`, `~/.aws/config`, web identity, ECS creds, EC2 instance profile. Pin `--profile` on every call.

## IAM actions the profile needs per task

- Audit: `iam:ListUsers`, `iam:ListRoles`, `iam:GetUser`, `iam:ListAttachedUserPolicies`, `iam:ListUserPolicies`, `iam:GetUserPolicy`, `iam:ListAccessKeys`, `iam:SimulatePrincipalPolicy`
- User/key management: + `iam:CreateUser`, `iam:DeleteUser`, `iam:CreateAccessKey`, `iam:UpdateAccessKey`, `iam:DeleteAccessKey`
- Policy management: + `iam:AttachUserPolicy`, `iam:DetachUserPolicy`, `iam:PutUserPolicy`, `iam:DeleteUserPolicy`
- STS: `sts:GetCallerIdentity` (always allowed), `sts:GetSessionToken`; `sts:AssumeRole` is granted by the TARGET role's trust policy, not the caller's identity policy alone
