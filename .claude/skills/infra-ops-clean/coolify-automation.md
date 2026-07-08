---
name: coolify-automation
description: "Programmatic Coolify v4 management via REST API. Use when migrating apps, bulk-importing env vars, or driving deploys from scripts. Replaces ~80% of dashboard clicking with curl + Node."
---

# Coolify v4 API Automation

> **Note:** The runnable helper scripts referenced here (e.g. env-import, cutover) describe a methodology. The original versions were specific to one environment and are NOT bundled in this template; implement them against your own Coolify API and infrastructure.

The Coolify v4 REST API can drive almost everything in the dashboard. This document is the field-tested reference for the patterns that worked during the <DATE> Example App migration — including the endpoints, the field-name gotchas, and the curl + Node helpers.

If you're starting fresh, read this top-to-bottom — total time to provision an app + database + envs + deploy is ~10 API calls + one rebuild wait, doable in under 30 minutes per app once the deploy key is in place.

---

## Setup

### Credentials file

Store credentials in `keys/coolify-credentials.env` (gitignored via a folder-level `.gitignore` that excludes everything except itself):

```bash
COOLIFY_API_BASE='https://coolify.<your-domain>/api/v1'
COOLIFY_NEW_TOKEN='<YOUR_SECRET>'     # Laravel Sanctum format — MUST be quoted (`|` is bash pipe)
COOLIFY_ADMIN_EMAIL='you@example.com'
COOLIFY_ADMIN_PASSWORD='...'              # required by some flows; otherwise stays for record
```

**Critical:** the token format is `<id>|<secret>`. The `|` is the field separator and a bash pipe character — **always single-quote when sourcing**. Without quotes, bash interprets it as a pipeline.

Source pattern:

```bash
set -a && source keys/coolify-credentials.env && set +a
```

### Migration state file

Per sprint, capture discovered UUIDs into `.claude/tasks/<sprint-name>/.env.migration` (gitignored). Example structure after the Example App run:

```bash
COOLIFY_SERVER_UUID='<RESOURCE_UUID>'
COOLIFY_MIGRATION_PROJECT_UUID='<RESOURCE_UUID>'
COOLIFY_GIT_DEPLOY_KEY_UUID='<RESOURCE_UUID>'
COOLIFY_example_DB_UUID='<RESOURCE_UUID>'
COOLIFY_example_DB_URL='postgres://user:<PASSWORD>@<HOST>:<PORT>/<DB>'
COOLIFY_example_APP_UUID='<RESOURCE_UUID>'
```

---

## API enabled by default? No.

**Coolify v4 ships with the API DISABLED.** Before creating any token, the user must flip the toggle:

- Dashboard → Settings → Advanced → **Allow API Access** → Save

Then Profile → Keys & Tokens → API Tokens → Create. The "Create Token" button is greyed out until the global toggle is on.

This catches you on a fresh install — the migration plan said "create a token" without noting the prereq, costing ~10 minutes of confusion.

---

## Endpoint reference (the actually-used set)

Base path: `https://coolify.<your-domain>/api/v1`
Auth: `Authorization: Bearer <token>` on every request.

| Method | Path                                                | Use                                                                                                                                                                                                                                                                         |
| ------ | --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GET    | `/teams/current`                                    | Sanity-check the token works. Returns `{id, name, ...}`.                                                                                                                                                                                                                    |
| GET    | `/servers`                                          | List managed servers. We use the auto-registered `localhost`. Capture `uuid` (32 chars).                                                                                                                                                                                    |
| GET    | `/security/keys`                                    | List private keys (deploy keys, host keys).                                                                                                                                                                                                                                 |
| POST   | `/security/keys`                                    | Register a private key (for git operations). Body: `{name, description, private_key}` (full OpenSSH private key text).                                                                                                                                                      |
| GET    | `/projects`                                         | List projects.                                                                                                                                                                                                                                                              |
| POST   | `/projects`                                         | Create a project. Body: `{name, description}`. Returns `{uuid}`. Coolify auto-creates a `production` environment under it.                                                                                                                                                  |
| GET    | `/projects/{uuid}`                                  | Get project + its environments list.                                                                                                                                                                                                                                        |
| PATCH  | `/projects/{uuid}`                                  | Rename / update description. Body: `{name?, description?}`.                                                                                                                                                                                                                 |
| POST   | `/databases/postgresql`                             | Create Postgres. Body must include `server_uuid`, `project_uuid`, `environment_name`, `name`, `image`, `is_public: false`. Returns `{uuid, internal_db_url}`. **Match the source dump's PG major version** — see gotchas.                                                   |
| POST   | `/databases/mongodb` / `/redis`                     | Same shape, different engines.                                                                                                                                                                                                                                              |
| GET    | `/databases/{uuid}`                                 | Full DB details.                                                                                                                                                                                                                                                            |
| DELETE | `/databases/{uuid}`                                 | Queue DB deletion.                                                                                                                                                                                                                                                          |
| POST   | `/applications/public`                              | Create app from a public Git URL.                                                                                                                                                                                                                                           |
| POST   | `/applications/private-deploy-key`                  | Create app from a private repo using a stored deploy key. Body must include `private_key_uuid` and an SSH-format `git_repository` (e.g. `you@example.com:owner/repo.git`).                                                                                                  |
| POST   | `/applications/private-github-app`                  | Create app via Coolify-installed GitHub App. Use only if you've set up the GitHub App flow.                                                                                                                                                                                 |
| GET    | `/applications/{uuid}`                              | Full app details.                                                                                                                                                                                                                                                           |
| PATCH  | `/applications/{uuid}`                              | Update app config (build_pack, domains, limits, ports_exposes, base_directory, dockerfile_location).                                                                                                                                                                        |
| POST   | `/applications/{uuid}/start` / `/stop` / `/restart` | Lifecycle ops.                                                                                                                                                                                                                                                              |
| GET    | `/applications/{uuid}/envs`                         | List environment variables.                                                                                                                                                                                                                                                 |
| POST   | `/applications/{uuid}/envs`                         | Create a single env.                                                                                                                                                                                                                                                        |
| PATCH  | `/applications/{uuid}/envs`                         | **Upsert single env by key.** Body must use `is_buildtime` (no underscore) — `is_build_time` returns 422.                                                                                                                                                                   |
| PATCH  | `/applications/{uuid}/envs/bulk`                    | **Bulk upsert.** Body: `{data: [{key, value, is_preview, is_buildtime, is_runtime, is_literal}, ...]}`. **POST returns 404 — must be PATCH.** Creates a production-scoped (is_preview=false) AND a preview-scoped (is_preview=true) entry per call by design — see gotchas. |
| DELETE | `/applications/{uuid}/envs/{env_uuid}`              | Delete a single env.                                                                                                                                                                                                                                                        |
| POST   | `/deploy?uuid={app_uuid}`                           | Trigger a deploy. Optional `&force=true` to skip cache. Returns `{deployments: [{deployment_uuid, ...}]}`.                                                                                                                                                                  |
| GET    | `/deployments/applications/{app_uuid}`              | All deployments for an app, with statuses.                                                                                                                                                                                                                                  |
| GET    | `/deployments/{deploy_uuid}`                        | Full deployment record including `logs` (JSON string of log entries).                                                                                                                                                                                                       |
| POST   | `/deployments/{deploy_uuid}/cancel`                 | Cancel deployment. **Returns HTTP 500 with "Undefined variable $application" but actually works server-side.** See gotchas.                                                                                                                                                 |

---

## Helper script: bulk env import

The most repeated operation is "load a `.env` file into an app's environment variables". Implement an env-import helper (not bundled in this template) — it:

- Parses a paste-ready `.env` file (`KEY=VALUE`, one per line, comments skipped)
- Auto-flags `NEXT_PUBLIC_*` / `NUXT_PUBLIC_*` / `VITE_*` / `PUBLIC_*` as `is_buildtime: true`
- Accepts `--override KEY=VALUE` for per-call substitutions (typical: new `DATABASE_URL`, new `NEXT_PUBLIC_SITE_URL`)
- POSTs as a single PATCH `/envs/bulk` call

Usage:

```bash
node scripts/env-import.mjs \
  --app "$COOLIFY_APP_UUID" \
  --file ~/Downloads/.../paste-ready/example.env \
  --override "DATABASE_URL=postgres://user:<PASSWORD>@<HOST>:<PORT>/<DB>" \
  --override "NEXT_PUBLIC_SITE_URL=https://app.example.com"
```

The script expects `COOLIFY_API_BASE` and `COOLIFY_NEW_TOKEN` in env. Source the credentials file first.

---

## Common workflows

### Workflow A — fresh app from a private GitHub repo

```bash
# Prereq: a registered private key (the read-only deploy key shared by all apps)
# Generated once, registered in /security/keys, public half added to each repo via gh CLI

# 1. Create project
PROJECT_UUID=$(curl -sS -X POST "$COOLIFY_API_BASE/projects" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "My App", "description": "..."}' | jq -r .uuid)

# 2. Create Postgres (internal-only)
DB_RESP=$(curl -sS -X POST "$COOLIFY_API_BASE/databases/postgresql" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"server_uuid\": \"$COOLIFY_SERVER_UUID\",
    \"project_uuid\": \"$PROJECT_UUID\",
    \"environment_name\": \"production\",
    \"name\": \"myapp-postgres\",
    \"image\": \"postgres:17-alpine\",
    \"is_public\": false,
    \"instant_deploy\": true
  }")
DB_UUID=$(echo "$DB_RESP" | jq -r .uuid)
DB_URL=$(echo "$DB_RESP" | jq -r .internal_db_url)

# 3. Create app
APP_UUID=$(curl -sS -X POST "$COOLIFY_API_BASE/applications/private-deploy-key" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"project_uuid\": \"$PROJECT_UUID\",
    \"server_uuid\": \"$COOLIFY_SERVER_UUID\",
    \"environment_name\": \"production\",
    \"private_key_uuid\": \"$COOLIFY_GIT_DEPLOY_KEY_UUID\",
    \"git_repository\": \"you@example.com:owner/repo.git\",
    \"git_branch\": \"main\",
    \"build_pack\": \"dockerfile\",
    \"ports_exposes\": \"3000\",
    \"domains\": \"https://app-new.example.com\",
    \"name\": \"myapp\",
    \"limits_memory\": \"2g\",
    \"limits_cpus\": \"1.5\",
    \"instant_deploy\": false
  }" | jq -r .uuid)

# 4. Bulk-import envs (with DATABASE_URL override + sane placeholder NEXT_PUBLIC_SITE_URL)
node env-import.mjs \
  --app "$APP_UUID" \
  --file paste-ready/myapp.env \
  --override "DATABASE_URL=$DB_URL" \
  --override "NEXT_PUBLIC_SITE_URL=https://app-new.example.com"

# 5. Restore DB from dump
scp ~/Downloads/myapp.dump ubuntu@<vps>:/tmp/
ssh ubuntu@<vps> "
  PG=\$(sudo docker ps --format '{{.ID}} {{.Names}}' | grep $DB_UUID | awk '{print \$1}')
  sudo docker cp /tmp/myapp.dump \$PG:/tmp/myapp.dump
  sudo docker exec \$PG pg_restore -U postgres -d postgres --clean --if-exists -j 4 /tmp/myapp.dump
"

# 6. Trigger deploy
DEPLOY_UUID=$(curl -sS -X POST "$COOLIFY_API_BASE/deploy?uuid=$APP_UUID" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" | jq -r '.deployments[0].deployment_uuid')

# 7. Watch
while true; do
  STATUS=$(curl -sS -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
    "$COOLIFY_API_BASE/deployments/$DEPLOY_UUID" | jq -r .status)
  echo "$STATUS"
  case "$STATUS" in finished|failed|cancelled|cancelled-by-user) break;; esac
  sleep 12
done
```

### Workflow B — dedicated deploy key per repo

> **WARNING — this workflow used to say "shared deploy key across N repos".** That doesn't work. GitHub enforces global uniqueness on deploy-key public keys across an account — the same key cannot be attached to two repos. See **gotcha G23** in `coolify-gotchas.md`. The Coolify side does support referencing one stored key from multiple apps; it's only the GitHub side that rejects reuse. So the only path is one keypair per repo.

For each app you migrate, generate a fresh ed25519 keypair, register the private half in Coolify, add the public half to the repo, and shred the local copies.

```bash
REPO=<GITHUB_OWNER>/example
APP_SLUG=exampleapp2  # short tag for naming

# 1. Generate ephemeral keypair locally
ssh-keygen -t ed25519 -f /tmp/coolify-${APP_SLUG}-deploy -N "" \
  -C "coolify-${APP_SLUG}-$(date +%Y-%m)"

# 2. Register the PRIVATE half in Coolify (stored encrypted at rest)
PAYLOAD=$(node -e "
const fs = require('fs');
const pk = fs.readFileSync('$(cygpath -w /tmp/coolify-${APP_SLUG}-deploy | tr '\\\\' '/')', 'utf8');
process.stdout.write(JSON.stringify({
  name: '${APP_SLUG}-deploy-$(date +%Y-%m)',
  description: 'Read-only deploy key for ${REPO}',
  private_key: pk
}));
")
KEY_UUID=$(curl -sS -X POST "$COOLIFY_API_BASE/security/keys" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" | jq -r .uuid)
echo "Coolify key UUID: $KEY_UUID"

# 3. Add the PUBLIC half as a read-only deploy key on the repo
PUBKEY=$(cat /tmp/coolify-${APP_SLUG}-deploy.pub)
gh api -X POST "repos/$REPO/keys" \
  -f title="coolify-${APP_SLUG}-$(date +%Y-%m)" \
  -f key="$PUBKEY" \
  -F read_only=true

# 4. CRITICAL: shred the local keypair (it's now in Coolify + GitHub only)
shred -u /tmp/coolify-${APP_SLUG}-deploy /tmp/coolify-${APP_SLUG}-deploy.pub
```

You'll end up with one Coolify private-key entry and one GitHub deploy key per app, and reference the corresponding `private_key_uuid` in each `/applications/private-deploy-key` body. The overhead is real but small — the original "share one key" intuition is the wrong shortcut.

### Workflow C — env var update only (no rebuild)

Useful for non-build-time secrets. Example: rotated Polar webhook secret.

```bash
curl -sS -X PATCH "$COOLIFY_API_BASE/applications/$APP_UUID/envs" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "POLAR_WEBHOOK_SECRET",
    "value": "polar_whs_NEW_VALUE",
    "is_preview": false,
    "is_buildtime": false,
    "is_runtime": true,
    "is_literal": true
  }'
```

Note: this updates the PRODUCTION env. To update preview too, send the same call with `is_preview: true`. Coolify v4 maintains separate copies — see gotchas.

After the PATCH, the running container does NOT automatically pick up the new value. Either:

- Trigger a redeploy (`POST /deploy?uuid=...`), or
- Restart the container (`POST /applications/{uuid}/restart`)

Restart is faster (~10s) but only works for runtime-only changes. For build-time vars, you must redeploy.

### Workflow D — clean wipe of env vars (when bulk-import dupes)

If a bulk import duplicated or you want to start fresh:

```bash
ENVS=$(curl -sS -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  "$COOLIFY_API_BASE/applications/$APP_UUID/envs")
echo "$ENVS" | jq -r '.[].uuid' | while read uuid; do
  curl -sS -X DELETE "$COOLIFY_API_BASE/applications/$APP_UUID/envs/$uuid" \
    -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" > /dev/null
done
```

Coolify will re-inject buildpack-managed vars (like `NIXPACKS_NODE_VERSION` for Nixpacks builds) automatically. Don't delete those; you'll just get them back.

### Workflow E — DNS swap via Cloudflare API (cutover day)

The migration plan's `04-cutover.mjs` uses the Cloudflare MCP. If that's not available, direct API:

```bash
CF_TOKEN=$(grep CLOUDFLARE_MCP_TOKEN .env.example | sed 's/.*="//;s/"$//')

# Find zone
ZONE_ID=$(curl -sS -H "Authorization: Bearer $CF_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones?name=example.com" | jq -r .result[0].id)

# Find current A record (capture for rollback!)
curl -sS -H "Authorization: Bearer $CF_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?name=example.com&type=A" \
  | jq '.result[] | {id, content, proxied, ttl}'

# PATCH to new IP (don't DELETE+CREATE — keeps record ID stable, rollback easier)
curl -sS -X PATCH \
  "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID" \
  -H "Authorization: Bearer $CF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "A",
    "name": "example.com",
    "content": "NEW_IP",
    "ttl": 1,
    "proxied": true
  }'

# Verify externally
for i in 1 2 3; do
  curl -sS --max-time 12 -o /dev/null -w "$i: %{http_code} %{time_total}s\n" \
    https://example.com/
  sleep 3
done
```

Always `PATCH` (not DELETE+CREATE) — keeps the record ID stable for rollback. If something breaks, run the same PATCH with the old IP.

### Workflow F — wire GitHub auto-deploy webhook (post app-creation, gotcha G29)

`/applications/private-deploy-key` apps don't auto-deploy on `git push` until you add a GitHub-side webhook pointing at Coolify. Without this, your only deploy paths are the dashboard or `POST /deploy`. This workflow closes that gap.

```bash
scripts/setup-github-webhook.sh <app-name> <owner>/<repo>
```

The script handles the full flow: resolve app UUID by name → read the per-app `manual_webhook_secret_github` from `GET /applications/{uuid}` → `gh api -X POST repos/{owner}/{repo}/hooks` to create the webhook → fire a test ping → report whether Coolify replied 200. Idempotent (returns the existing hook id if you've already added it).

Manual version, if you'd rather see the wire-up:

```bash
APP_UUID="..."
REPO="<GITHUB_OWNER>/myapp"

SECRET=$(curl -sS -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  "$COOLIFY_API_BASE/applications/$APP_UUID" | \
  jq -r .manual_webhook_secret_github)

WEBHOOK_URL="${COOLIFY_API_BASE%/api/v1}/webhooks/source/github/events/manual"

gh api -X POST "repos/$REPO/hooks" \
  -f name=web \
  -F active=true \
  -f "events[]=push" \
  -F "config[url]=$WEBHOOK_URL" \
  -F "config[content_type]=json" \
  -F "config[secret]=$SECRET"
```

**Routing model**: ONE webhook URL serves all apps on a Coolify instance. Coolify uses HMAC validation (per-app `manual_webhook_secret_github`) to figure out WHICH app's deploy to trigger. So every app's hook points at the same `/webhooks/source/github/events/manual` URL — only the secret differs.

After setup, verify:

```bash
gh api repos/$REPO/hooks --jq '.[] | select(.config.url | test("coolify")) | "\(.id) \(.last_response.code)"'
# Expect: <id> 200
```

If the response code is anything other than 200 (e.g. 401 = secret mismatch, 404 = wrong URL path, 500 = Coolify internal), the webhook is registered but won't actually trigger deploys. See coolify-gotchas.md G29 for the diagnosis pattern.

---

## Field-name gotchas

### `is_buildtime`, not `is_build_time`

Validation rejects the with-underscore form:

```json
{
  "message": "Validation failed.",
  "errors": { "is_build_time": ["This field is not allowed."] }
}
```

Coolify's own API responses use `is_buildtime` (without the underscore). The discrepancy comes from `is_build_time` being a name people INSTINCTIVELY type because every other field on the resource follows snake_case (`is_preview`, `is_literal`, `is_runtime`). **Don't trust your instinct — copy from a GET response.**

### `is_runtime` matters

When you create an env, you can mark it `is_buildtime`, `is_runtime`, both, or neither. Coolify treats them independently:

- **`is_buildtime: true`** → passed as Docker build ARG (if the Dockerfile declares `ARG <NAME>`)
- **`is_runtime: true`** → injected into the container's process env at start
- **Both true** → both behaviours
- **Neither** → the env exists in Coolify's DB but doesn't reach the container. Useful for "remembered" values.

Default to `is_runtime: true` for everything. Add `is_buildtime: true` for:

- `NEXT_PUBLIC_*` / `NUXT_PUBLIC_*` / `VITE_*` / any framework-embedded client var
- `DATABASE_URL` if your app uses Prisma `db push` during build, or if Better Auth / NextAuth / Auth.js initializes at build time
- `BETTER_AUTH_SECRET` (and similar auth secrets) — Better Auth refuses to init with default secret during page data collection
- Anything an `ARG` in the Dockerfile declares

### Production AND preview entries — by design

Every PATCH `/envs/bulk` call creates **two** entries per key: one with `is_preview: false` (production deploy uses this) and one with `is_preview: true` (preview deploy uses this). 25 keys in → 50 entries out.

This is **not a duplication bug** — Coolify v4 maintains parallel env scopes for prod vs preview. Don't try to dedupe. If you don't care about preview, the entries are harmless; previews just won't deploy because there's no preview branch configured.

When you PATCH a single env by key, you have to do it twice — once with `is_preview: false`, once with `is_preview: true` — or the production and preview values drift.

### Sanctum token format

Tokens look like `1|abcdef123...`. The leading number is the token ID; the pipe is the separator. Always single-quote in shell contexts. `Authorization: Bearer 1|abcdef123` works fine in HTTP (curl handles the literal pipe in the value), but `source` of an unquoted env file breaks bash.

---

## Build pack discovery

Don't assume — check the repo before creating the app.

| If repo has...                          | Use `build_pack:`                                                                 |
| --------------------------------------- | --------------------------------------------------------------------------------- |
| A root `Dockerfile`                     | `"dockerfile"` (set `dockerfile_location: "/Dockerfile"` + `base_directory: "/"`) |
| A `nixpacks.toml`                       | `"nixpacks"`                                                                      |
| A `docker-compose.yml`                  | `"dockercompose"` (different endpoint: `/applications/dockercompose-empty`)       |
| Plain JS/TS/Go without any of the above | `"nixpacks"` (Coolify auto-detects)                                               |

**The Example App migration burned ~15 minutes** because the old VPS env vars contained `NIXPACKS_*` keys, so I assumed nixpacks. Reality: the user had ADDED a custom Dockerfile mid-2026 ("Optimize Dockerfile with dep caching and Next.js BuildKit cache mount"). The presence of `NIXPACKS_*` in the runtime env was stale state from a pre-Dockerfile deploy.

**Always check the repo's current state:**

```bash
gh repo clone owner/repo /tmp/audit
ls /tmp/audit/{Dockerfile,nixpacks.toml,docker-compose.yml,docker-compose.yaml} 2>/dev/null
```

If you used the wrong build pack, switching is one PATCH:

```bash
curl -sS -X PATCH "$COOLIFY_API_BASE/applications/$APP_UUID" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"build_pack":"dockerfile","dockerfile_location":"/Dockerfile","base_directory":"/"}'
```

But you lose the wait time on the prior failed build.

---

## Watching a deploy

Coolify doesn't expose a streaming-log endpoint. The pattern that works:

```bash
DEPLOY_UUID=$(curl -sS -X POST "$COOLIFY_API_BASE/deploy?uuid=$APP_UUID&force=true" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  | jq -r '.deployments[0].deployment_uuid')

# Poll every 12 seconds — that's roughly the rate at which build output meaningfully changes
for i in $(seq 1 90); do
  STATUS=$(curl -sS -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
    "$COOLIFY_API_BASE/deployments/$DEPLOY_UUID" | jq -r .status)
  printf "[%2d] %s\n" "$i" "$STATUS"
  case "$STATUS" in
    finished|failed|cancelled|cancelled-by-user|error) break ;;
  esac
  sleep 12
done

# On failure, fetch the JSON logs and grep stderr:
curl -sS -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  "$COOLIFY_API_BASE/deployments/$DEPLOY_UUID" \
  | jq -r '.logs | fromjson | .[] | select(.type=="stderr") | .output' \
  | tail -30
```

Typical first-build durations on a 2-vCPU / 8GB Lightsail instance for a Next.js monorepo with Prisma:

- pnpm install: 3-4 minutes
- Prisma generate + db push: 30-60 seconds
- `next build` with static page generation: 4-5 minutes
- Docker image layering + healthcheck: ~30 seconds
- **Total: 8-10 minutes**

Subsequent builds with Docker layer cache hit: 4-6 minutes.

---

## Cancelling a stuck deployment

The cancel endpoint has a Coolify v4.1 server-side bug: it raises an "Undefined variable $application" PHP error and returns HTTP 500. **But the cancel still takes effect** — the deployment record goes to `cancelled-by-user` status.

If that's not enough (rare — maybe the build container ignores the cancel signal), force-kill the build container directly:

```bash
ssh ubuntu@<vps> "sudo docker kill $DEPLOY_UUID"
```

The build container's name is exactly the deployment UUID. Killing it terminates the build immediately. Coolify cleans up the partial image.

---

## Rate limiting

Coolify v4.1 doesn't enforce strict rate limits on the API for authenticated requests, but **don't loop without a sleep** — the Horizon queue (Laravel) has 1-second internal heartbeats and aggressive polling can starve other jobs. The 12-second poll cadence above is comfortable.

---

## See also

- `coolify-hardening.md` — the security configuration that should be in place before this automation runs
- `coolify-gotchas.md` — every undocumented quirk we hit during the Example App migration
- `coolify.md` — general overview + install
- env-import helper — implement your own (not bundled; see note at top)
- `scripts/fix-coolify-compose.py` — the dashboard-pin patch
- Coolify API reference (web): https://coolify.io/docs/api-reference/
