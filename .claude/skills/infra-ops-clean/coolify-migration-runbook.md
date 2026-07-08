# First Migration Sprint — Foundation + Example App

> **Note:** The runnable helper scripts referenced below (inventory, provision, db-migrate, cutover, env-import) describe a migration methodology. The original versions were specific to one environment and are NOT bundled in this template; implement them against your own Coolify API and infrastructure.

**Sprint scope:** Install + harden Coolify on the new VPS (`<USER>-General` / `<YOUR_SERVER_IP>`) and migrate Example App (example.com) as the first app.
**Why bundled:** the foundation work only happens once but blocks every per-app migration after this, so Example App rides on the back of the same sprint. Subsequent apps (exampleapp2, example HQ — renamed from App on <DATE>, Maillayer) reuse Phases 3-7 of this runbook with their own paste files.
**Driver model:** Claude drives via SSH + Coolify REST API + Cloudflare DNS MCP. User does ~30-45 min of focused work spread over the wall clock (account setup, smoke tests, decision points).

---

## Security playbook — applied throughout this sprint

Every item below ties to a specific failure mode from the <DATE> → <DATE> incident on the old VPS. Verifications listed at the phase they're applied.

| #   | Failure on old VPS                                                                                           | New-VPS rule                                                                                                                                                         | Phase applied                                               |
| --- | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| 1   | Coolify dashboard publicly bound on `0.0.0.0:8000` (HTTP login page reachable from internet)                 | Dashboard bound to `127.0.0.1:8000`, exposed only via Cloudflare Tunnel to `example.com` (Cloudflare-signed HTTPS, optional Access policy for SSO/IP gating) | Phase 1.4-1.5                                               |
| 2   | Postgres ports `5432` and `5433` were `0.0.0.0`-bound                                                      | Every Coolify-managed DB stays on internal Docker networks. **Never enable "Make public" in Coolify DB settings.**                                                   | Phase 4.2 (DB create)                                       |
| 3   | Coolify admin password committed to library-managed `vps-core.md` as plaintext                               | Strong admin password stored in 1Password, never committed. `vps-core.md` says "see vault" only.                                                                     | Phase 2.1                                                   |
| 4   | App containers ran as root inside container → npm payload had host-equivalent caps inside the container      | Where Dockerfiles allow: `USER node`. For Nixpacks-built apps: apply Coolify resource limits (CPU + memory caps) to contain blast radius                             | Phase 4.3 + Appendix B                                      |
| 5   | No S3 backups configured for any DB → no clean-restore option mid-incident                                   | S3 backups configured at DB-creation time for every DB. Daily schedule, 14 daily + 4 weekly retention.                                                               | Phase 4.2                                                   |
| 6   | npm supply chain unaudited → root cause of incident                                                          | Per-repo GitHub Action: `pnpm audit --audit-level moderate` on every PR; require lockfile diff review for any new dep                                                | Tracked in Phase 8 (post-cutover); not blocking this sprint |
| 7   | No anomaly detection on outbound traffic; AWS T&S report was the only signal after 8 days of abuse           | Lightsail alarms: CPU > 80% sustained 1h, "Data transfer out" > 2x baseline. Email to you@example.com                                                       | Phase 1.7                                                   |
| 8   | No 2FA on Coolify admin account                                                                              | TOTP enabled in Coolify after first login                                                                                                                            | Phase 2.2                                                   |
| 9   | API tokens not used (would have given an audit trail of admin actions); the only credential was the password | Migration API token scoped + revoked after sprint complete                                                                                                           | Phase 2.3, Phase 7.5                                        |
| 10  | No Lightsail automatic snapshots until 8 days before incident                                                | Enable automatic snapshots on Day 1 + a manual one after sprint completes                                                                                            | Phase 1.8                                                   |

---

## Phase 0 — Preflight (Claude, ~2 min)

### 0.1 Generate the bulk-paste env files

For each app, filter the captured runtime env down to just the user-set variables (strip `PATH`, `COOLIFY_*`, `NIXPACKS_*`, base image stuff). Output one paste-ready `.env` per app at `~/Downloads/incident-<DATE>-dumps/paste-ready/<app>.env`.

Done during this phase; reference files live at:

- `paste-ready/example.env`
- `paste-ready/exampleapp2.env`
- `paste-ready/example-app.env`
- `paste-ready/maillayer.env`
- `paste-ready/example.env`

### 0.2 Pick the Coolify subdomain

Going with **`example.com`** (admin/personal domain — apex unchanged).

### 0.3 Confirm Cloudflare API token has Tunnel scope

The existing token (created <DATE>, per the migration plan progress log) has DNS Edit + Zone Read. We need `Tunnel:Edit` added for programmatic tunnel creation, OR I'll authenticate `cloudflared` once interactively in Phase 1 (browser flow, you click a URL once). Default to the interactive flow — simpler, no token-scope change needed.

---

## Phase 1 — Install + harden Coolify on the new VPS (Claude via SSH, ~30 min including waits)

All steps below run as `ubuntu` (NOPASSWD sudo) over SSH from my Bash tool. I'll show you each block before running anything destructive.

### 1.1 Pre-flight check

```bash
ssh -i ~/keys/<YOUR_SSH_KEY>.pem ubuntu@<YOUR_SERVER_IP> \
  "df -h / && free -h && docker --version 2>/dev/null || echo 'docker not yet installed'"
```

Expected: ≥150GB free on /, 8GB RAM, docker not yet installed.

### 1.2 Install Coolify (latest stable, NOT pinned to old version)

Old VPS ran 4.0.0-beta.459 — pinning was relevant when we planned to migrate Coolify's internal state. We're not — we're recreating apps from scratch via API. Latest stable is fine, gets us out of beta.

```bash
ssh ubuntu@<YOUR_SERVER_IP> "curl -fsSL https://cdn.coollabs.io/coolify/install.sh | sudo bash"
```

Wait ~5-10 min. Installer outputs the dashboard URL at the end. **We will not use this public URL** — Phase 1.4 below replaces it with a private one.

### 1.3 Pin Coolify dashboard to localhost only (security playbook #1)

Edit Coolify's docker-compose to bind dashboard to `127.0.0.1:8000` instead of `0.0.0.0:8000`. This is the single most important security fix from the incident.

```bash
ssh ubuntu@<YOUR_SERVER_IP> "sudo sed -i 's|^      - \"8000:|      - \"127.0.0.1:8000:|' /data/coolify/source/docker-compose.yml && sudo grep -E '8000:|6001:|6002:' /data/coolify/source/docker-compose.yml"
```

Verify the output shows `127.0.0.1:8000:` not `0.0.0.0:8000:`. Then restart Coolify:

```bash
ssh ubuntu@<YOUR_SERVER_IP> "cd /data/coolify/source && sudo docker compose up -d --force-recreate coolify"
```

Confirm dashboard is no longer publicly reachable:

```bash
# From your local machine:
curl -sS --max-time 5 -o /dev/null -w '%{http_code}\n' http://<YOUR_SERVER_IP>:8000
# Expected: timeout or connection refused (NOT 200)
```

### 1.4 Set up Cloudflare Tunnel for private dashboard access

Install `cloudflared`:

```bash
ssh ubuntu@<YOUR_SERVER_IP> "curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb && sudo dpkg -i cloudflared.deb && cloudflared --version"
```

Authenticate (interactive — **this is the one user step in Phase 1**):

```bash
ssh -t ubuntu@<YOUR_SERVER_IP> "cloudflared tunnel login"
```

This prints a URL. Open it in your browser, select `example.com` zone, authorize. The cert is written to `~/.cloudflared/cert.pem` on the VPS.

Create the tunnel + config:

```bash
ssh ubuntu@<YOUR_SERVER_IP> "cloudflared tunnel create coolify-user-general && sudo mkdir -p /etc/cloudflared && sudo cp /home/ubuntu/.cloudflared/*.json /etc/cloudflared/"

ssh ubuntu@<YOUR_SERVER_IP> "sudo tee /etc/cloudflared/config.yml >/dev/null <<'EOF'
tunnel: coolify-user-general
credentials-file: /etc/cloudflared/$(ls /etc/cloudflared/*.json | xargs basename)

ingress:
  - hostname: example.com
    service: http://localhost:8000
  - service: http_status:404
EOF"
```

### 1.5 DNS record via Cloudflare MCP

I create the CNAME record pointing `example.com` → `<tunnel-id>.cfargotunnel.com` via the Cloudflare DNS MCP (already configured per migration plan).

### 1.6 Install cloudflared as a systemd service

```bash
ssh ubuntu@<YOUR_SERVER_IP> "sudo cloudflared service install && sudo systemctl enable --now cloudflared && sudo systemctl status cloudflared --no-pager"
```

Tunnel comes up. Test from your laptop browser: `https://example.com` should load Coolify's initial-setup page.

### 1.6.5 **OPEN PORT 443 IN LIGHTSAIL CONSOLE** (manual one-time, easy to miss)

Lightsail's instance-level firewall (network ACL, separate from UFW on the host) opens only **22 + 80** by default. **443 must be added manually before any HTTPS traffic can reach the box.** Without this, Cloudflare-proxied A records will return HTTP 522 (origin connection timeout), and Coolify's Let's Encrypt HTTP-01 challenges will fail.

Steps:

1. Lightsail console → instance <USER>-General → **Networking** tab
2. Under **IPv4 Firewall** → **Add rule** → Application: **HTTPS** (port 443, TCP, source: Anywhere)
3. Repeat for **IPv6 Firewall** if you want IPv6 traffic
4. Save

Verify from your local machine:

```bash
curl -sS --max-time 5 -o /dev/null -w '%{http_code}\n' -H 'Host: <any-domain-pointing-at-vps>' https://<YOUR_SERVER_IP>/ -k
# Expect HTTP 200/301/302/404 — anything BUT timeout means 443 is reachable
```

This is a one-time setup per Lightsail instance. Document in `vps-core.md` once done.

### 1.7 Lightsail monitoring alarms (security playbook #7)

Done by you in Lightsail console (no API path for alarm CRUD from outside AWS without a separate IAM key, and we deliberately don't have AWS API creds on this VPS):

- Instance → Metrics → CPU utilization → Add alarm: ≥ 80%, evaluation period 60 min, datapoints to alarm 1 / 1. Notify you@example.com
- Instance → Metrics → Network out → Add alarm: ≥ 5 GB / hr (set the threshold based on your normal baseline; 5 GB/hr is roughly 2x typical for Coolify hosts your size). Notify same email.

### 1.8 Lightsail automatic snapshots (security playbook #10)

Done by you in Lightsail console:

- Instance → Snapshots → Automatic snapshots → Enable. Daily, retain 7.
- Cost: ~$0.05/GB/month × ~20-40 GB once Coolify runs = trivial, covered by AWS credits.

### 1.9 Foundation done — verification checklist

- [ ] `curl http://<YOUR_SERVER_IP>:8000` from outside the box returns connection refused/timeout
- [ ] `https://example.com` loads the Coolify setup page
- [ ] `sudo ss -tlnp | grep 8000` on the VPS shows `127.0.0.1:8000` only, no `0.0.0.0:8000`
- [ ] `sudo systemctl is-active cloudflared` → `active`
- [ ] Lightsail CPU + Network-out alarms exist
- [ ] Lightsail automatic snapshots enabled

---

## Phase 2 — Coolify account setup (User, ~5 min)

### 2.1 First-time admin account

At `https://example.com`:

- Create your admin account. Email: `you@example.com`. **Password: <YOUR_SECRET> a fresh 20+ char random string in 1Password. Do NOT reuse any previously-exposed password.**

### 2.2 Enable 2FA (security playbook #8)

Profile → Two-Factor Authentication → Enable. Scan QR code in your authenticator app. Save the backup codes in 1Password.

### 2.3 Generate API token (security playbook #9)

Profile → API Tokens → Create token. Name: `migration-2026-05`. Scope: full (we'll revoke it after the sprint completes).

Copy the token, paste into a local file (gitignored):

```bash
echo "COOLIFY_NEW_TOKEN=<COOLIFY_TOKEN>" > ~/.coolify-migration.env
chmod 600 ~/.coolify-migration.env
```

Tell me the token is ready (don't paste it in chat; I'll read the file from disk).

### 2.4 Add Lightsail server in Coolify

Servers → Add Server → "this server" (the install already auto-registered localhost). Verify it's listed and healthy. Should be automatic.

### 2.5 Add S3 destination for backups (security playbook #5)

Storages → New S3 Storage → "AWS S3" with:

- Endpoint: `https://s3.eu-central-1.amazonaws.com`
- Region: `eu-central-1`
- Bucket: create a new one or reuse — `your-coolify-backups` works
- Access key + Secret: from a new IAM user with **just** that bucket's read/write permission

Click "Validate" — Coolify confirms write access.

---

## Phase 3 — Pre-migration audit (Claude + User, ~15 min)

### 3.1 Audit Example App repo for malicious commits

Claude runs:

```bash
gh repo clone <GITHUB_OWNER>/Example App /tmp/Example App-audit
cd /tmp/Example App-audit
git log --since="<DATE>" --until="<DATE>" --all --pretty=format:"%h %ai %an %s"
git log --all --diff-filter=A --since="<DATE>" -- 'package.json' 'pnpm-lock.yaml' 'yarn.lock'
git log --all -p --since="<DATE>" -- package.json pnpm-lock.yaml | head -200
```

I summarise findings. **You confirm every commit in the window is yours.** Watch for:

- Unknown dep additions
- Suspiciously old version pins
- Typosquats (`next-build-utils`, `next-helper-dev`, etc.)

Also check GitHub:

- Settings → Deploy keys → revoke any present
- Settings → Webhooks → note any pointing at old IP `<YOUR_SERVER_IP>`

### 3.2 Audit Postgres dump for tampering

```bash
cd ~/Downloads/incident-<DATE>-dumps
tar xzf dbdumps-<TIMESTAMP>.tar.gz
cd dbdumps-<TIMESTAMP>

cat example.roles.txt
# Look for any role other than 'postgres' / Coolify-managed users

less example.schema.sql
# Scan for: unfamiliar tables, suspicious functions, triggers, extensions

pg_restore --list example.dump | head -40
# Confirm familiar tables: ApiKey, Purchase, UsageLog, indexing_projects, indexing_urls
```

Post-restore audit query (run in Phase 5.3):

```sql
SELECT id, email, "createdAt", role
FROM "User"
WHERE "createdAt" BETWEEN '<DATE>' AND '<DATE>'
ORDER BY "createdAt" DESC;
```

Expected: only legitimate signups in that window. Anything you don't recognise gets flagged before deploy.

---

## Phase 4 — API-driven Example App provisioning (Claude via Coolify API, ~10 min)

All steps below are scripted against `https://example.com/api/v1/*` using the token from Phase 2.3. I'll show the request bodies before firing them.

### 4.1 Create project

```bash
curl -sS -X POST "https://example.com/api/v1/projects" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Migration-2026-05", "description": "Incident-driven migration from <SERVER_NAME>"}'
```

Captures `project_uuid` for downstream calls.

### 4.2 Create Postgres 15 resource (security playbook #2 + #5)

```bash
curl -sS -X POST "https://example.com/api/v1/databases/postgresql" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "example-postgres",
    "project_uuid": "<from 4.1>",
    "server_uuid": "<from /servers>",
    "image": "postgres:15-alpine",
    "is_public": false,
    "postgres_user": "postgres",
    "postgres_db": "postgres",
    "instant_deploy": true
  }'
```

**Critical:** `is_public: false`. This is the explicit fix for the old VPS exposing 5433 publicly.

After creation, configure S3 backups via API (or UI fallback): daily schedule, 14 daily + 4 weekly retention, target the S3 storage from Phase 2.5.

Captures `database_uuid` + internal connection string.

### 4.3 Create Example App application (security playbook #4)

```bash
curl -sS -X POST "https://example.com/api/v1/applications/public" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_uuid": "<from 4.1>",
    "server_uuid": "<from /servers>",
    "git_repository": "https://github.com/<GITHUB_OWNER>/Example App",
    "git_branch": "main",
    "build_pack": "nixpacks",
    "ports_exposes": "3000",
    "domains": "https://example.com",
    "name": "example",
    "description": "Example App migrated from <SERVER_NAME>",
    "limits_memory": "2g",
    "limits_cpus": "1.5"
  }'
```

Note `limits_memory` + `limits_cpus`: caps blast radius per app even if a future supply-chain attack lands. The old VPS had no per-app limits — the malware could consume the whole 32GB box.

Captures `application_uuid`.

### 4.4 Bulk-import env vars (the previously tedious part — now one API call)

```bash
# Build the JSON payload from the paste-ready file:
node -e "
const fs = require('fs');
const lines = fs.readFileSync('${HOME}/Downloads/incident-<DATE>-dumps/paste-ready/example.env', 'utf8').trim().split('\n');
const env = lines.map(l => {
  const eq = l.indexOf('=');
  return { key: l.slice(0, eq), value: l.slice(eq+1), is_preview: false, is_build_time: false, is_literal: true };
});
console.log(JSON.stringify({ data: env }));
" > /tmp/example-env.json

curl -sS -X POST "https://example.com/api/v1/applications/<application_uuid>/envs/bulk" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -H "Content-Type: application/json" \
  --data @/tmp/example-env.json
```

This pastes all ~24 user-set env vars in a single call. Coolify validates and stores them encrypted at rest.

### 4.5 Update env values that reference old infra

Two env vars need new values:

- `DATABASE_URL` → use the internal connection string from Phase 4.2 (Coolify hostname + new password). I'll update via single-env PATCH:
  ```bash
  curl -sS -X PATCH "https://example.com/api/v1/applications/<application_uuid>/envs" \
    -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"key": "DATABASE_URL", "value": "<new-internal-connection-string>"}'
  ```
- `NEXT_PUBLIC_SITE_URL` → set to `https://example.com` temporarily for the smoke-test phase. We swap to `https://example.com` at Phase 7.

### 4.6 Wire GitHub → Coolify push webhook (gotcha G29 — easy to skip)

The `/applications/private-deploy-key` endpoint only sets up clone access; GitHub has no push-notification path to Coolify by default. Without this step, `git push` won't trigger redeploys — your only way to deploy will be the dashboard button or manual `POST /deploy` calls. Don't ship a Coolify app without this.

```bash
scripts/setup-github-webhook.sh example <GITHUB_OWNER>/Example App
```

The script: resolves the app UUID by name → reads `manual_webhook_secret_github` from Coolify → creates the webhook on the repo → fires a test ping → reports `last_response: active:200` if everything's wired. Idempotent (returns the existing hook id if you've already added it).

Verify post-step:

```bash
gh api repos/<GITHUB_OWNER>/Example App/hooks --jq '.[] | "\(.id) \(.config.url) \(.last_response.code)"'
# Expect: <id> https://coolify.<host>/webhooks/source/github/events/manual 200
```

After this, push to the configured branch will trigger Coolify deploys automatically. See coolify-gotchas.md G29 for the full diagnosis pattern if a hook doesn't fire correctly.

---

## Phase 5 — Restore Example App DB (Claude via SSH, ~5 min)

### 5.1 Copy dump to new VPS

```bash
scp -i ~/keys/<YOUR_SSH_KEY>.pem \
  ~/Downloads/incident-<DATE>-dumps/dbdumps-<TIMESTAMP>/example.dump \
  ubuntu@<YOUR_SERVER_IP>:/tmp/
```

### 5.2 Restore into the new Coolify-managed Postgres

```bash
ssh ubuntu@<YOUR_SERVER_IP> "
  NEW_PG=\$(sudo docker ps --format '{{.ID}} {{.Names}}' | grep example-postgres | awk '{print \$1}');
  sudo docker cp /tmp/example.dump \$NEW_PG:/tmp/example.dump;
  sudo docker exec \$NEW_PG pg_restore -U postgres -d postgres --clean --if-exists -j 4 /tmp/example.dump;
  sudo docker exec \$NEW_PG psql -U postgres -d postgres -c '\dt'
"
```

### 5.3 Run the tampering audit query (from Phase 3.2)

```bash
ssh ubuntu@<YOUR_SERVER_IP> "
  NEW_PG=\$(sudo docker ps --format '{{.ID}} {{.Names}}' | grep example-postgres | awk '{print \$1}');
  sudo docker exec \$NEW_PG psql -U postgres -d postgres -c \"
    SELECT id, email, \\\"createdAt\\\", role
    FROM \\\"User\\\"
    WHERE \\\"createdAt\\\" BETWEEN '<DATE>' AND '<DATE>'
    ORDER BY \\\"createdAt\\\" DESC;
  \"
"
```

I'll show the output. **You confirm every row is a legitimate signup.** If anything looks injected, we halt and decide.

---

## Phase 6 — Deploy + smoke test (Claude triggers, User verifies, ~15 min)

### 6.1 Trigger deploy via API

```bash
curl -sS -X POST "https://example.com/api/v1/deploy?uuid=<application_uuid>" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN"
```

I tail the deployment logs via:

```bash
curl -sS "https://example.com/api/v1/applications/<application_uuid>/logs" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN"
```

Build takes 3-10 minutes. I'll show the tail.

### 6.2 You smoke-test at `https://example.com`

- [ ] Page loads, no errors
- [ ] Google OAuth login works (**confirm `https://example.com/api/auth/callback/google` is whitelisted in Google Cloud Console first**)
- [ ] One of your accounts can log in
- [ ] Pricing page renders Polar product IDs correctly
- [ ] Trigger one indexing job end-to-end (DataForSEO + Ralfy paths)
- [ ] Trigger a Resend email (password reset works)

If anything fails → fix in env / code → I redeploy via API → repeat. **Do not proceed to cutover until all six pass.**

---

## Phase 7 — DNS cutover (Claude via Cloudflare MCP, ~5 min)

### 7.1 Pre-flight

- [ ] All 6 Phase 6 smoke tests green
- [ ] Cloudflare A record TTL for `example.com` confirmed at 60s (lower 30 min ahead if not)
- [ ] Your laptop has terminal open + Coolify dashboard visible to react if anything misfires

### 7.2 Add production domain to the Coolify app via API

```bash
curl -sS -X PATCH "https://example.com/api/v1/applications/<application_uuid>" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"domains": "https://example.com,https://example.com"}'
```

Coolify auto-issues Let's Encrypt cert for `example.com` (~30s after DNS resolves).

### 7.3 Update `NEXT_PUBLIC_SITE_URL` env to production domain

```bash
curl -sS -X PATCH "https://example.com/api/v1/applications/<application_uuid>/envs" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -d '{"key": "NEXT_PUBLIC_SITE_URL", "value": "https://example.com"}'
```

Trigger a redeploy via Phase 6.1.

### 7.4 Swap DNS via Cloudflare MCP

I call:

- `list_dns_records` for zone `example.com`
- `update_dns_record` on the apex A record → new value `<YOUR_SERVER_IP>`, proxied (orange cloud)
- Verify by re-reading the record

Within 60s, traffic lands on new VPS. I'll watch Coolify logs for inbound requests from real users.

### 7.5 Revoke the migration API token (security playbook #9)

After all 4 apps are migrated (end of last app sprint), Coolify Profile → API Tokens → revoke `migration-2026-05`. Generate a smaller-scope read-only token for me to use for future ops on the box.

---

## Phase 8 — Post-cutover wiring (User + Claude, ~10 min)

### 8.1 Polar webhook secret rotation

Polar dashboard → Webhooks → the example.com endpoint → regenerate signing secret.
Update Coolify app env via API:

```bash
curl -sS -X PATCH "https://example.com/api/v1/applications/<application_uuid>/envs" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -d '{"key": "POLAR_WEBHOOK_SECRET", "value": "<new-secret>"}'
```

I trigger a redeploy. You send a test webhook from Polar dashboard; verify app log accepts it.

### 8.2 Google OAuth: remove old redirect URI (housekeeping)

console.cloud.google.com → APIs & Services → Credentials → the Example App OAuth client → remove any redirect URI pointing at the old IP / placeholder if still listed.

### 8.3 IP allowlists at third parties

- Algolia: if any IP allowlist on the index, swap old `<YOUR_SERVER_IP>` → new `<YOUR_SERVER_IP>`
- DataForSEO + Ralfy: same check, swap if found

### 8.4 Supply-chain hygiene baseline (security playbook #6 — tracked, not blocking)

Add to Example App repo: `.github/workflows/audit.yml` that runs `pnpm audit --audit-level=moderate` on every PR. Block merges on findings. (Separate sprint — track in main session file.)

---

## Phase 9 — Customer comms (conditional, User, 5 min if needed)

If anyone messaged about the outage:

> Subject: Example App — service restored after planned infrastructure migration
>
> Hi — quick update. Last night we performed an infrastructure migration to a new hardened host as part of an incident response. Service is restored, your data is intact, and your sessions were reset as a security precaution. Just log in again. Let me know if anything seems off.

Don't volunteer the npm-dep root cause unless asked. If asked: be straight — malicious dependency in an unrelated application affected the shared host, Example App code/data clean, credentials rotated where the malware had any reachability.

---

## Sprint done criteria

- [ ] `example.com` resolves to `<YOUR_SERVER_IP>` (verify from clean network)
- [ ] HTTPS valid via Coolify-issued Let's Encrypt
- [ ] Google OAuth login works
- [ ] Indexing job runs end-to-end
- [ ] Polar test webhook delivered + accepted with rotated secret
- [ ] Resend email sends + receives
- [ ] Postgres audit query showed no injected users
- [ ] All 10 security playbook items verified per their phase
- [ ] Lightsail snapshot taken of the new VPS in its post-sprint state
- [ ] Sprint notes appended to `session-current.md`

---

## Appendix A — Subsequent app sprints

For Example App → example HQ (renamed from App <DATE>) → Maillayer, **only Phases 3-8 repeat** (audit, provision, restore, deploy, cutover, post-wiring). Phases 1-2 are foundation work, already done.

Per-app substitutions:

| App               | Repo                                | Container ID old           | DB type                       | Paste file                  |
| ----------------- | ----------------------------------- | -------------------------- | ----------------------------- | --------------------------- |
| Example App | `<GITHUB_OWNER>/example`    | `<RESOURCE_UUID>` | Postgres                      | `paste-ready/exampleapp2.env`   |
| example HQ        | `<GITHUB_OWNER>/example-HQ`        | `<RESOURCE_UUID>` | Postgres (`app_db` kept)    | `paste-ready/example-app.env`     |
| Maillayer         | (image variant, see migration plan) | `<RESOURCE_UUID>` | MongoDB + Redis + file volume | `paste-ready/maillayer.env` |

example Website: **do not redeploy** until the malicious npm dep is identified and purged from `package.json` / lockfile. Separate audit sprint.

example: deferred — confirm DB dependency from Phase 1 inventory first.

---

## Appendix D — Per-app pre-flight additions (discovered during exampleapp2 migration)

The Example App worked example above misses three classes of pre-flight check that surface on later apps. Add these for every subsequent migration BEFORE triggering the first deploy.

### D.1 Dockerfile ARG audit (gotcha G15 + G25)

```bash
gh repo clone <owner>/<repo> /tmp/<app>-audit
grep -nE '^ARG ' /tmp/<app>-audit/Dockerfile
```

**Interpret the count:**

- **Zero ARGs** + the app uses Resend / Better Auth / Prisma / any SDK that constructs clients at module load: build WILL fail at `next build` page-data-collection unless you add ARGs. Commit them BEFORE first deploy, not after.
  - Standard list to add for Next.js + Prisma + Better Auth: every env Coolify will pass as build-time. Easiest is one ARG per imported env var, declared at the top of the builder stage.
- **`ARG DATABASE_URL` only**: matches the Example App pattern. Mark DATABASE_URL + BETTER_AUTH_SECRET buildtime in Coolify. Likely sufficient.
- **Many ARGs**: probably fine; mark matching envs buildtime per existing declarations.

The fix commit looks like the one pushed to example as `<COMMIT_SHA>` — see `your private incident notes` for the exact diff.

### D.2 `NODE_ENV` must be runtime-only (gotcha G24)

`env-import.mjs` writes `NODE_ENV` as a normal var. If you then bulk-flip everything to `is_buildtime: true` (tempting because of G13/G14), `NODE_ENV=production` becomes a build arg, npm strips devDependencies during install, and any dev-time tool (Prisma CLI is the common one) is missing from the build → failure.

Always patch `NODE_ENV` back to `is_buildtime: false` after a bulk flip:

```bash
for IS_PREV in false true; do
  curl -sS -X PATCH "$COOLIFY_API_BASE/applications/$APP/envs" \
    -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"key\":\"NODE_ENV\",\"value\":\"production\",\"is_preview\":$IS_PREV,\"is_buildtime\":false,\"is_runtime\":true,\"is_literal\":true}"
done
```

The latest version of `env-import.mjs` enforces this automatically via a `NEVER_BUILDTIME_KEYS` guard — but verify after import in case the user-supplied env file specifies otherwise.

### D.3 npm install postinstall resilience (Prisma in particular)

If the repo's `package.json` has a `postinstall` script that runs `./node_modules/.bin/<tool>`, the deps stage may race against npm bin-symlink creation when Coolify's global ARG injection forces a fresh `npm install` (no cache). Symptom: `./node_modules/.bin/prisma: not found` even on a clean repo.

The fix in the Dockerfile (committed to exampleapp2 as `<COMMIT_SHA>`):

```dockerfile
RUN npm install --legacy-peer-deps --ignore-scripts \
    && npm install <native-modules> --legacy-peer-deps --save-optional --ignore-scripts \
    && ./node_modules/.bin/prisma generate --no-hints
```

`--ignore-scripts` skips lifecycle hooks during install; the explicit `prisma generate` runs after the symlinks are guaranteed to exist.

### D.4 Coolify API DB-status reporting lag (gotcha G26)

Right after creating a Postgres resource via `POST /databases/postgresql` with `instant_deploy: true`, the API's `status` field may show `exited:unhealthy` for 30-60 seconds while the container is actually `Up (healthy)` on the host. Don't panic — verify with `docker ps` on the VPS before tearing down and recreating. Wait 60s and re-poll the API.

---

## Appendix B — Coolify hardening cheatsheet (will become `coolify-hardening.md`)

| Setting                  | Default (bad)                                 | Hardened (this sprint)                                                 |
| ------------------------ | --------------------------------------------- | ---------------------------------------------------------------------- |
| Dashboard binding        | `0.0.0.0:8000`                                | `127.0.0.1:8000` only, accessed via Cloudflare Tunnel                  |
| Dashboard auth           | Password only                                 | Password + TOTP 2FA                                                    |
| Database public exposure | UI offers "Make public" toggle, very tempting | `is_public: false` always; access via SSH tunnel or in-cluster only    |
| App resource limits      | Unset = container can eat the whole host      | `limits_memory` + `limits_cpus` per app, matched to actual usage       |
| DB backups               | Off                                           | Daily S3 backups, 14d + 4w retention                                   |
| API tokens               | Often left active forever                     | Created per sprint, revoked at end                                     |
| Coolify version          | Once installed, often left to drift           | Coolify auto-updates via its own scheduled service; check monthly      |
| SSL on dashboard         | HTTP by default if you bind to 0.0.0.0:8000   | HTTPS via Cloudflare Tunnel (Cloudflare-signed cert, edge termination) |
| Audit log                | Off by default                                | Enable in Coolify Settings if available in your version                |

---

## Appendix C — Coolify API reference (will become `coolify-automation.md`)

Base URL: `https://example.com/api/v1`
Auth: `Authorization: Bearer <token>`

Key endpoints used in this runbook:

| Method | Path                               | Purpose                                                      |
| ------ | ---------------------------------- | ------------------------------------------------------------ |
| POST   | `/projects`                        | Create a project                                             |
| GET    | `/servers`                         | List managed servers (we use the auto-registered localhost)  |
| POST   | `/databases/postgresql`            | Create a Postgres resource                                   |
| POST   | `/databases/mongodb`               | Create a Mongo resource                                      |
| POST   | `/databases/redis`                 | Create a Redis resource                                      |
| POST   | `/applications/public`             | Create app from public Git repo                              |
| POST   | `/applications/private-github-app` | Create app via GitHub App auth (preferred for private repos) |
| POST   | `/applications/{uuid}/envs/bulk`   | Bulk env import                                              |
| PATCH  | `/applications/{uuid}/envs`        | Update single env var                                        |
| PATCH  | `/applications/{uuid}`             | Update app config (domains, limits, etc.)                    |
| POST   | `/deploy?uuid={uuid}`              | Trigger deploy                                               |
| GET    | `/applications/{uuid}/logs`        | Stream build/runtime logs                                    |
| GET    | `/teams/current`                   | Sanity check token works                                     |

Full docs: https://coolify.io/docs/api-reference/

---

**Sprint ready. Phase 0 about to execute.**
