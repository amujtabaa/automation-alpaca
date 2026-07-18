# AWS CLI v2 on Windows / PowerShell 5.1

The failure modes in this file are all documented CLI bugs or shell quirks (aws-cli issues #6487, #1326, #3994). Follow these patterns exactly.

## Pager (the #1 hang)

CLI v2 routes ALL output through `more` on Windows by default, so a non-interactive session hangs forever waiting for a keypress.

```powershell
$env:AWS_PAGER = ""      # once per session, OR
aws ... --no-cli-pager    # per command
```

## JSON arguments: file:// or nothing

PowerShell 5.1 + CommandLineToArgvW double-parse inline JSON; quotes get stripped or mangled unpredictably. NEVER pass inline JSON. Write a temp file:

```powershell
@'
{ "EmailIdentity": "example.com" }
'@ | Set-Content -Path "$env:TEMP\payload.json" -Encoding utf8

aws sesv2 create-email-identity --cli-input-json "file://$env:TEMP/payload.json" --profile <YOUR_PROFILE> --region <YOUR_REGION>
```

Rules:

- `file://` paths use FORWARD slashes even on Windows (`file://C:/Users/...`); backslashes throw "file not found".
- `Set-Content -Encoding utf8` (PS 5.1 default is UTF-16 LE, which the CLI cannot read). If text blobs misbehave, also set `$env:AWS_CLI_FILE_ENCODING = "UTF-8"`.
- Simple scalar params (a domain, an email) are fine inline with single quotes: `--email-identity 'example.com'`.
- Shorthand syntax (`Key=Value,Key2=Value2`) is fine for flat structures; switch to file:// the moment nesting appears.

## Line continuation and chaining

- Multi-line commands use the backtick `` ` ``, not `\`.
- No `&&` / `||` in PS 5.1: use `cmd1; if ($LASTEXITCODE -eq 0) { cmd2 }`.
- Prefer one AWS call per tool invocation so each exit code is observed.

## Exit codes and errors

```powershell
aws sesv2 get-email-identity --email-identity example.com --profile <YOUR_PROFILE> --region <YOUR_REGION> --output json
if ($LASTEXITCODE -ne 0) { throw "aws failed: $LASTEXITCODE" }
```

- Check `$LASTEXITCODE`, not `$?` (native exe).
- 0 success | 1 API error (AccessDenied, NotFound, validation) | 2 CLI usage/parse error | 252-254 v2 internals.
- Do NOT redirect stderr (`2>&1`) on native exes in PS 5.1; it wraps lines in ErrorRecords and corrupts `$?`. Stderr is captured by the tool harness anyway.
- Diagnosis: add `--debug` and read the request/response dump.

## Parsing output (no jq on this box)

```powershell
# PowerShell-native
$acct = aws sesv2 get-account --profile <YOUR_PROFILE> --region <YOUR_REGION> --output json | ConvertFrom-Json
$acct.SendQuota.Max24HourSend

# Or push filtering into the CLI itself (preferred, less to parse)
aws sesv2 get-account --profile <YOUR_PROFILE> --region <YOUR_REGION> --output json --query 'SendQuota.Max24HourSend'

# Complex transforms: node -e (jq is not installed)
aws ... --output json | node -e "const d=JSON.parse(require('fs').readFileSync(0)); console.log(d.something)"
```

`ConvertFrom-Json` returns PSCustomObject (no `-AsHashtable` in 5.1).

## Polling loops (no watch/xargs)

```powershell
$tries = 0
do {
  Start-Sleep -Seconds 60
  $status = aws sesv2 get-email-identity --email-identity example.com --profile <YOUR_PROFILE> --region <YOUR_REGION> --output json --query 'DkimAttributes.Status'
  $tries++
} while ($status -match 'PENDING' -and $tries -lt 10)
```

Always cap attempts; report PENDING-after-cap rather than looping forever.
