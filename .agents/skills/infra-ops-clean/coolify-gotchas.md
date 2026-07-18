---
name: coolify-gotchas
description: "Undocumented Coolify v4 quirks, failure-to-fix mappings, and 'I wish I'd known' findings from real migrations. Read before any Coolify provisioning or migration sprint."
---

# Coolify v4 Gotchas

Every entry here cost real time to discover. Read this top-to-bottom before starting a migration and you'll save hours.

Each gotcha has:

- **Symptom** — what you'll see
- **Cause** — what's actually going on
- **Fix** — how to resolve
- **Prevention** — what to do differently next time

Source: <DATE> Example App migration sprint. Coolify version: 4.1.0.

---

## G1. The API is disabled by default

**Symptom:** Profile → API Tokens page says "API is disabled" and the Create button is greyed out.

**Cause:** Coolify v4.1 ships with API access OFF as a security default.

**Fix:** Settings → Advanced → toggle **Allow API Access** → Save. (In some versions: Settings → Configuration → API Access.) Then create the token.

**Prevention:** Always do this immediately after first admin login, before generating any tokens. Add it to your install checklist.

---

## G2. Dashboard binds to `0.0.0.0:8000` by default

**Symptom:** Right after install, the Coolify login page is reachable at `http://<VPS_IP>:8000` from anywhere on the internet.

**Cause:** The install script's `docker-compose.prod.yml` uses `"${APP_PORT:-8000}:8080"` — default Docker binding interface is `0.0.0.0`.

**Fix:** Patch `docker-compose.prod.yml` to change three port bindings to `127.0.0.1:...` (dashboard 8000, Soketi 6001, Soketi metrics 6002). Use `scripts/fix-coolify-compose.py` — it's idempotent.

**Prevention:** Add Cloudflare Tunnel BEFORE you ever start advertising the install. The `vps-core.md` should reference Cloudflare Tunnel as the access path, never the public IP. See `coolify-hardening.md` for the full procedure.

---

## G3. Setting `APP_PORT=127.0.0.1:8000` in `.env` doesn't work

**Symptom:** You try to use Coolify's env var as the simple fix path. Container fails to start with `invalid start port '127.0.0.1:8000': invalid syntax`.

**Cause:** Docker Compose parses the value `${APP_PORT:-8000}` and expects an integer host port. The colon-containing form breaks the parser.

**Fix:** Edit `docker-compose.prod.yml` directly — there's no env-only path.

**Prevention:** Don't try to be clever with Compose substitution to add an interface prefix. The interface always goes BEFORE the host port in the binding spec, not inside the variable.

---

## G4. Coolify needs root SSH back to the host

**Symptom:** Coolify setup wizard's "Register This Machine as a server" step fails with `ssh: connect to host host.docker.internal port 22: Connection refused` or `Permission denied (publickey)`.

**Cause:** Coolify runs in a Docker container. To manage the host's Docker daemon (start/stop containers, build images, etc.), it SSHs into the host AS ROOT, using its own self-generated ed25519 key. The hardened sshd_config from `vps-security-setup.md` (`PermitRootLogin no` + empty `/root/.ssh/authorized_keys`) blocks this.

**Fix (three sub-issues, in order):**

1. **Add Coolify's pubkey to `/root/.ssh/authorized_keys`** (Coolify shows the pubkey in the wizard, OR fetch via `sudo cat /data/coolify/ssh/keys/you@example.com` or whatever the install creates).

2. **Change `PermitRootLogin no` → `PermitRootLogin prohibit-password`** in `/etc/ssh/sshd_config`. Still no password-based root login; only the specific Coolify ed25519 key works.

3. **Allow UFW from the Coolify Docker bridge** to port 22:

   ```bash
   COOLIFY_SUBNET=$(sudo docker network inspect coolify --format '{{(index .IPAM.Config 0).Subnet}}')
   sudo ufw allow from "$COOLIFY_SUBNET" to any port 22 proto tcp comment 'Coolify self-management SSH'
   ```

4. **Unban the Coolify IP from Fail2ban** (it'll have auto-banned itself during the above failures):
   ```bash
   sudo fail2ban-client set sshd unbanip 10.0.1.5
   ```

**Prevention:** Document these three relaxations in your hardening playbook BEFORE you install Coolify. Don't assume `vps-security-setup.md`'s defaults are Coolify-compatible. Full incident chronology with copy-pasteable commands: `your private incident notes`.

---

## G5. The Coolify ed25519 SSH "heartbeat" is NOT an attacker

**Symptom:** `w` on the host shows multiple `root` SSH sessions from an internal Docker bridge IP (e.g., `10.0.1.5`), going back months. Auth log shows tens of thousands of `Accepted publickey for root from 10.0.1.5` entries.

**Cause:** Coolify's container holds a persistent SSH connection to the host for management ops, plus opens new connections every few seconds for individual Docker commands. Each connection rapidly opens and closes. Over weeks of uptime, you accumulate zombie sshd PIDs from those connections (the parent dies, the zombie sshd waits to be reaped).

**Fix:** Nothing — this is normal Coolify operation. Verify it's legitimate by checking the SSH key fingerprint matches Coolify's ed25519 key (`/root/.ssh/authorized_keys` has it labeled `coolify`). Real attacker SSH would show external IPs, NOT bridge subnet IPs.

**Prevention:** During incident response, **always check `ip-addr.txt` and `docker network inspect` BEFORE assuming bridge-subnet SSH is an attacker**. The <DATE> incident response misread these for ~30 minutes as "active attacker root sessions for 5 months". They weren't. The actual compromise was a containerized npm payload in one specific app.

---

## G6. Lightsail's firewall is separate from UFW (port 443 trap)

**Symptom:** UFW allows 443/tcp. `sudo ss -tlnp | grep :443` shows it bound to `0.0.0.0:443`. `curl https://localhost` from inside the VPS works (HTTP 200). But `curl https://<VPS_IP>` from outside times out, and Cloudflare-proxied requests return HTTP 522.

**Cause:** Lightsail has an instance-level firewall (network ACL) separate from the OS-level UFW. By default it opens 22 + 80 only. **443 must be added manually in the console.**

**Fix:** Lightsail console → instance → **Networking** tab → IPv4 Firewall → Add rule → Application: **HTTPS** (TCP 443, source: Anywhere). Repeat for IPv6.

**Prevention:** Add this as a checklist item in your "new Lightsail instance" runbook. Note: AWS Lightsail differs from EC2 here — EC2 security groups don't have this default.

---

## G7. Bulk env import is `PATCH`, not `POST`

**Symptom:** `POST /applications/{uuid}/envs/bulk` returns HTTP 404 "Not found".

**Cause:** Coolify v4.1 routes the bulk endpoint as PATCH only.

**Fix:** Use `PATCH /applications/{uuid}/envs/bulk` with body `{data: [{key, value, is_preview, is_buildtime, is_runtime, is_literal}, ...]}`.

**Prevention:** The naming is misleading — "bulk" sounds like POST (create many). Mentally remap it: think "PATCH the bulk env set".

---

## G8. Field is `is_buildtime`, not `is_build_time`

**Symptom:** Single env POST/PATCH returns `{"message":"Validation failed.","errors":{"is_build_time":["This field is not allowed."]}}`.

**Cause:** The field name is `is_buildtime` (no underscore between "build" and "time"). Everything else on the resource uses snake_case (`is_preview`, `is_literal`, `is_runtime`), so muscle memory predicts the wrong one.

**Fix:** Use `is_buildtime` exactly. Don't trust your instinct — copy from a GET response.

**Prevention:** Any time you're writing fields against a Coolify v4 API, GET the resource once and copy field names from the response. Same gotcha applies to other casing quirks: `is_runtime` not `is_run_time`, but `created_at` IS snake_case. Be paranoid.

---

## G9. Bulk env import creates production AND preview entries

**Symptom:** You import 25 vars, then GET `/envs` and see 50 entries — every key duplicated.

**Cause:** Each PATCH `/envs/bulk` call creates **two** entries per key: one with `is_preview: false` (production deploy uses this) and one with `is_preview: true` (preview deploy uses this). By design — Coolify v4 maintains separate env scopes for production vs preview deploys.

**Fix:** Don't dedupe. The "duplicates" are correct. If you don't use preview deploys, the preview entries are harmless ballast.

**Prevention:** When updating a single env by key, **update BOTH copies** (call PATCH `/envs` twice, with `is_preview: false` then `is_preview: true`). Otherwise production and preview drift over time.

---

## G10. Cancel deployment returns HTTP 500 but still works

**Symptom:** `POST /deployments/{uuid}/cancel` returns:

```json
{ "message": "Failed to cancel deployment: Undefined variable $application" }
```

with HTTP 500.

**Cause:** Coolify v4.1 server-side PHP bug in the cancel handler's error path. The cancellation itself executes correctly server-side before the bug triggers.

**Fix:** Verify post-call by GET'ing the deployment — status should be `cancelled-by-user`. If it isn't (rare), force-kill the build container directly:

```bash
ssh ubuntu@<vps> "sudo docker kill <deployment_uuid>"
```

The build container's name is exactly the deployment UUID.

**Prevention:** Don't trust HTTP status alone — verify with a follow-up GET. Worth filing as a Coolify bug if not already known.

---

## G11. Postgres dump major version must match container image

**Symptom:** `pg_restore` returns `error: unsupported version (1.16) in file header` (or similar).

**Cause:** A dump from `pg_dump` v17 cannot restore into a Postgres v15 container. PostgreSQL dump format versions are tied to the major version of `pg_dump` that created them; restoration is forward-compatible but not backward.

**Fix:** Recreate the Coolify Postgres resource with the matching major version. Delete the wrong-version DB resource (`DELETE /databases/{uuid}`), then re-create with `image: "postgres:17-alpine"` instead of `postgres:15-alpine`.

**Prevention:** When inventorying the source VPS, **inspect the dump file header first**:

```bash
head -c 200 mydump.dump | strings | head -5
# Look for: "Dumped by pg_dump version 17.7" or similar
```

Or query the source DB's `SELECT version()` before dumping. Match the target Coolify image to that major version exactly. **Never rely on the migration plan or old vps-core.md** — those tend to lag the actual installed version after auto-upgrades.

---

## G12. Build pack detection — check the repo, not the env

**Symptom:** Build fails with `UndefinedVar: Usage of undefined variable '$NIXPACKS_PATH'`. You created the app with `build_pack: "nixpacks"`.

**Cause:** Coolify v4.1 Nixpacks integration doesn't auto-inject `NIXPACKS_PATH` reliably. More importantly: the build pack you should have used was `dockerfile`, because the repo has its own custom Dockerfile.

**Fix:** PATCH the app to switch:

```bash
curl -sS -X PATCH "$COOLIFY_API_BASE/applications/$APP_UUID" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"build_pack":"dockerfile","dockerfile_location":"/Dockerfile","base_directory":"/"}'
```

**Prevention:** Always `gh repo clone` the source repo to `/tmp/audit/` and check `ls Dockerfile nixpacks.toml docker-compose.yml` BEFORE creating the Coolify app. Don't infer build pack from old runtime env (NIXPACKS\_\*) — old vars are STALE STATE that can survive a build-pack switch.

---

## G13. `DATABASE_URL` must be `is_buildtime: true` for Prisma + Next.js + Better Auth

**Symptom:** Build succeeds through pnpm install + prisma generate, then fails during `next build` page data collection with `Error: Database connection not available. Check DATABASE_URL environment variable.`

**Cause:** Next.js's `next build` collects page data for each route, which instantiates API route handlers. Better Auth / NextAuth / Auth.js handlers initialize at module load and read DATABASE_URL from `process.env`. If DATABASE_URL isn't a Docker build ARG (i.e., not `is_buildtime: true`), the handler instantiation fails.

If the Dockerfile also does `prisma db push` at build time, same requirement — Prisma needs DATABASE_URL during build to apply schema migrations.

**Fix:** PATCH the env to add buildtime:

```bash
curl -sS -X PATCH "$COOLIFY_API_BASE/applications/$APP_UUID/envs" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -d '{"key":"DATABASE_URL","value":"...","is_preview":false,"is_buildtime":true,"is_runtime":true,"is_literal":true}'
# Repeat with is_preview: true for the preview env (see G9)
```

**Prevention:** Mark these as build-time by default for any Next.js + Prisma + Better Auth app:

- `DATABASE_URL`
- `BETTER_AUTH_SECRET` (or `NEXTAUTH_SECRET` / `AUTH_SECRET`)
- `AUTH_GOOGLE_ID` + `AUTH_GOOGLE_SECRET` (Better Auth eagerly validates providers)
- All `NEXT_PUBLIC_*` (always — Next.js embeds them in the client bundle)

A safer default policy: **mark every secret your app uses as both `is_buildtime: true` AND `is_runtime: true`** unless you have a specific reason not to. The downside is that build cache invalidates more often when secrets change; the upside is no surprise failures.

The Coolify-injected `NIXPACKS_NODE_VERSION` and `PHP_*` system envs stay as `is_buildtime`-only — leave those alone.

---

## G14. `BETTER_AUTH_SECRET` must be build-time for static page generation

**Symptom:** Build proceeds past DATABASE_URL stage, then fails with:

```
[Error [BetterAuthError]: You are using the default secret. Please set `BETTER_AUTH_SECRET` in your environment variables or pass `secret` in your auth config.]
```

**Cause:** Same root cause as G13 — page data collection during `next build` instantiates the Better Auth handler at module load. Better Auth's init code throws if `BETTER_AUTH_SECRET` is missing or falls back to a known default value.

**Fix:** Mark `BETTER_AUTH_SECRET` as `is_buildtime: true` (and `is_runtime: true`).

**Prevention:** See G13 — for any Next.js + Better Auth app, treat all auth secrets as build-time by default.

---

## G15. Dockerfile must declare `ARG <NAME>` for build-time envs to land

**Symptom:** You marked an env as `is_buildtime: true` in Coolify. Build still fails because the variable is "undefined" inside the Dockerfile.

**Cause:** Coolify v4.1 passes build-time envs as `--build-arg <NAME>=<value>` to `docker build`. But Docker only makes those values accessible inside the Dockerfile via `ARG <NAME>` declarations. Without the explicit ARG, Docker drops the value silently.

**Fix:** Add `ARG <NAME>` to the Dockerfile, BEFORE the stage that uses it:

```dockerfile
FROM base AS builder

# Declare all build-time secrets here
ARG DATABASE_URL
ARG BETTER_AUTH_SECRET
ARG AUTH_GOOGLE_ID
ARG AUTH_GOOGLE_SECRET

# Now they're accessible:
RUN echo "Building with DATABASE_URL=$DATABASE_URL"
```

You don't need to ENV them — `ARG` is enough during the build stage. If you also want them at container runtime, that's `is_runtime: true` in Coolify (Coolify injects them into `process.env` of the running container directly, no Dockerfile change needed).

**Prevention:** For any private app that uses Prisma or Better Auth: add a comment block of ARGs at the top of the builder stage in the Dockerfile. Pre-emptively declares everything that might need to be build-time. Doesn't hurt to have extras.

---

## G16. Cloudflare proxy + Let's Encrypt — HTTP-01 challenge works through proxy

**Symptom:** You set up a Cloudflare-proxied A record (orange cloud) for your app. You worry Coolify's Traefik can't get a Let's Encrypt cert via HTTP-01 ACME challenge because Cloudflare intercepts the request.

**Cause:** Worry was unfounded — Cloudflare DOES allow ACME challenges through to origin by default (their `/.well-known/acme-challenge/*` path is special-cased).

**Fix:** Nothing — just make sure port 80 is open at both UFW + Lightsail firewall levels. ACME redirects to HTTPS will follow correctly.

**Prevention:** If you want stronger guarantees (e.g., for clients on Cloudflare Enterprise with strict rules), switch to DNS-01 ACME challenge with Cloudflare API. But for default Cloudflare proxy setups, HTTP-01 just works.

**Caveat:** This works because port 443 is open. If 443 is closed at Lightsail level (G6), HTTP-01 fails because the redirect lands on a dead port. Always check G6 first.

---

## G17. Traefik returns 200 from localhost but 522 from Cloudflare

**Symptom:** Coolify says the app is running healthy. `curl https://localhost` from inside the VPS returns 200. Cloudflare-proxied request returns HTTP 522 (origin connection timeout). Direct `curl https://<VPS_IP>` from outside also times out.

**Cause:** 99% of the time, this is G6 (Lightsail firewall doesn't open 443). The remaining 1%: rate limiting or DDoS protection actively blocking.

**Fix:** Check G6 first.

**Prevention:** Add `curl --max-time 5 https://<VPS_IP>` from your own machine to the post-install verification checklist, BEFORE any DNS swap.

---

## G18. App container hostname is the application UUID with a suffix

**Symptom:** Looking at `docker ps`, you see container names like `<RESOURCE_UUID>-<DEPLOY_SUFFIX>`. The first 32 chars match the app UUID; the suffix is generated.

**Cause:** Coolify uses a deterministic naming pattern: `<app_uuid>-<random_suffix>`. The suffix changes on each deploy. Same for build containers (`<deployment_uuid>` exactly — no suffix).

**Fix:** Look up app containers by prefix:

```bash
sudo docker ps --format '{{.ID}} {{.Names}}' | grep "^[^ ]* $APP_UUID"
```

Or via Coolify API: GET `/applications/{uuid}` returns the current running container.

**Prevention:** Don't hard-code container names. Use the UUID prefix as a lookup.

---

## G19. Internal DB hostname is the DB container UUID

**Symptom:** You restore a Example App dump, then update the app's `DATABASE_URL` to point at the new Postgres. You try to use a "friendly" hostname like `example-postgres` — connection fails.

**Cause:** Coolify v4.1 creates DB resources with the container UUID AS the network alias on the `coolify` bridge. The "name" you give the resource in the Coolify UI is just a label — the actual DNS entry inside the network is the UUID.

**Fix:** Use the `internal_db_url` returned by the CREATE response — that's the canonical hostname. Format: `postgres://user:<PASSWORD>@<HOST>:<PORT>/<DB>`. The `<db_uuid>` is what the container resolves to on the coolify bridge.

**Prevention:** Always capture `internal_db_url` from the DB create response into your migration `.env.migration` state file. Reference it via env interpolation in subsequent calls.

---

## G20. Coolify auto-redeploys on certain PATCH operations

**Symptom:** You update an env via PATCH. Coolify silently triggers a new deploy. You didn't ask for one.

**Cause:** Some Coolify v4.1 env operations are flagged as "requires redeploy" and trigger an automatic deployment. Not consistent — depends on whether the env is marked `is_buildtime` and whether it's a fresh create vs an update.

**Fix:** Watch for this — check `/deployments/applications/{uuid}` periodically during config changes. If a stuck or unwanted deployment appears, cancel via G10's pattern.

**Prevention:** Batch env changes BEFORE the first deploy. Use bulk import (PATCH `/envs/bulk`) instead of per-key PATCHes if doing many at once. After the app is stable in production, individual env changes have less consequence.

---

## G21. The "queued" status can mean "no slot available" — check concurrent_builds

**Symptom:** New deploy stays at status `queued` for tens of minutes, never moves to `in_progress`.

**Cause:** Coolify server settings cap concurrent builds (default 2). If 2 deployments are stuck in_progress (often because a build container is hanging), new deploys queue indefinitely.

**Fix:** GET `/deployments/applications/{uuid}` — if you see in_progress deployments older than the typical build time (8-10 min for a Next.js monorepo), force-kill them (G10).

**Prevention:** Always check for stuck in_progress deployments before triggering a new one. Add a `concurrent_builds: 4` setting via `PATCH /servers/{uuid}/settings` if you regularly do parallel multi-app migrations.

---

## G22. The `ApiKey` table schema (for Example App / Better Auth) has no `enabled` column

**Symptom:** A query like `SELECT key FROM "ApiKey" WHERE enabled = true` fails with `column "enabled" does not exist`.

**Cause:** Better Auth's default ApiKey schema is `{ id, key, userId, createdAt, lastUsed }`. There's no boolean enabled flag — keys are valid until deleted.

**Fix:** Drop the `enabled` predicate. To filter active keys, use `lastUsed IS NOT NULL` (used at least once) or `createdAt > now() - interval '90 days'` (recently created).

**Prevention:** When writing audit/validation queries for any app's DB, ALWAYS `\d "TableName"` first to see the actual schema. Don't assume column names — Better Auth, NextAuth, Lucia, etc., all have slightly different schemas.

---

## G23. GitHub deploy keys CANNOT be reused across repositories

**Symptom:** `gh api -X POST repos/<owner>/<other-repo>/keys` with a public key that's already on another repo returns:

```json
{
  "message": "Validation Failed",
  "errors": [
    {
      "resource": "PublicKey",
      "code": "custom",
      "field": "key",
      "message": "key is already in use"
    }
  ],
  "status": "422"
}
```

**Cause:** GitHub enforces global uniqueness on deploy-key public keys across the entire account. The same public key cannot be added as a deploy key to two repos simultaneously. This contradicts the "Workflow B — shared deploy key across N repos" pattern in `coolify-automation.md`, which is incorrect as written.

**Fix:** Generate a fresh ed25519 keypair per repo, register the private half in Coolify as a new entry under Security → Private Keys, add the public half to the target repo, then reference the new `private_key_uuid` when creating the Coolify app.

```bash
ssh-keygen -t ed25519 -f /tmp/coolify-<repo>-deploy -N "" -C "coolify-<repo>-$(date +%Y-%m)"
# 1. POST private to Coolify /security/keys → capture uuid
# 2. POST public to repos/<owner>/<repo>/keys with read_only=true
# 3. shred /tmp/coolify-<repo>-deploy*
```

**Prevention:** Plan per-repo deploy keys upfront. Don't try to share. The overhead is one extra keypair per app (Coolify stores them encrypted at rest, GitHub stores only the public half).

---

## G24. `NODE_ENV=production` as build-time ARG silently breaks npm devDependencies install

**Symptom:** Build fails in the deps stage with `./node_modules/.bin/prisma: not found` (or any other dev-only tool the Dockerfile expects post-install). The previous build worked; the only change was flipping more envs to `is_buildtime: true`.

**Cause:** `NODE_ENV=production` was marked as a build-time env in Coolify. Coolify injects build-time envs as `--build-arg NODE_ENV=production` to `docker build`, which exposes them as build-time env vars. When `RUN npm install` runs with `NODE_ENV=production` in its environment, npm respects it and skips `devDependencies`. Tools like Prisma (often in devDependencies) never get installed, so any postinstall hook or subsequent `prisma generate` call fails with "not found".

**Fix:** Mark `NODE_ENV` as `is_buildtime: false` (runtime-only). The runtime container still gets `NODE_ENV=production` injected by Coolify, but the build environment no longer has it, so `npm install` installs both dependencies and devDependencies.

```bash
curl -sS -X PATCH "$COOLIFY_API_BASE/applications/$APP/envs" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"key":"NODE_ENV","value":"production","is_preview":false,"is_buildtime":false,"is_runtime":true,"is_literal":true}'
# Repeat with is_preview: true
```

Alternative fix (Dockerfile-side): use `npm install --include=dev` or `npm ci --include=dev` to force devDependency install regardless of `NODE_ENV`.

**Prevention:** When bulk-flipping envs to buildtime, EXCLUDE `NODE_ENV` (and `NPM_CONFIG_PRODUCTION`, `YARN_PRODUCTION`, etc. — any flag npm/yarn/pnpm interpret as "skip devDeps"). Discovered during the Example App migration after a wholesale "mark everything buildtime" pass. Hit on Coolify v4.1 + npm 10.9.

---

## G25. Coolify auto-injects build-time ARGs at the top of the Dockerfile (invalidates layer cache)

**Symptom:** Marking envs as `is_buildtime: true` invalidates Docker's deps layer cache. Subsequent builds re-run `RUN npm install` from scratch even though `package.json` and `package-lock.json` haven't changed. Combined with G24 and Prisma postinstall hooks, this surfaces flaky bin-symlink races.

**Cause:** Coolify v4.1 prepends a block of global `ARG <NAME>` declarations to the top of the Dockerfile (before the first `FROM`) for every env flagged `is_buildtime: true`. Docker BuildKit hashes the Dockerfile content as part of the layer cache key — any change to those ARGs (adding/removing envs, changing buildtime flags) invalidates ALL subsequent layers.

**Fix:** Two options:

1. **Stabilize the buildtime env set** before relying on cache. Flip all needed envs to buildtime once, then leave them alone. Subsequent rebuilds will hit cache normally.
2. **Make the deps RUN robust to fresh execution.** Use `npm install --ignore-scripts` and run postinstall steps (like `prisma generate`) explicitly after, so the install doesn't depend on bin symlink timing.

**Prevention:** Plan the buildtime env list once during initial provisioning. Don't toggle is_buildtime mid-migration. Also note: the auto-injected ARGs at the top of the Dockerfile are GLOBAL ARGs — they apply BEFORE any `FROM`, which means they need to be re-declared inside each stage's `ARG NAME` to actually be used by `RUN` commands in that stage. The ARGs you declare yourself inside the builder stage are the ones that matter for builds.

---

## G26. Coolify API's DB `status` field lags actual container state by 30-60s

**Symptom:** Right after creating a Postgres (or Mongo / Redis) resource via `POST /databases/postgresql` with `instant_deploy: true`, polling `GET /databases/{uuid}` returns `status: "exited:unhealthy"` even though `docker ps` on the VPS shows the container as `Up (healthy)`. Polling continues to show the stale status for 30-60 seconds before the API catches up.

**Cause:** Coolify v4.1's status field is populated from a background reconciler, not from live `docker inspect` calls. The initial pre-start status (`exited:unhealthy`, the placeholder before the container is launched) persists in the API response until the next reconcile tick lands.

**Fix:** Don't trust the API status during the first minute after creation. Verify directly on the host:

```bash
ssh ubuntu@<vps> "sudo docker ps --format '{{.Names}}\t{{.Status}}' | grep <db_uuid>"
# Expect: <db_uuid>  Up X seconds (healthy)
```

If `docker ps` shows the container is up and healthy, proceed with restore/connection operations. Re-poll the Coolify API status only if you specifically need a programmatic confirmation; usually you don't.

**Prevention:** In migration scripts, treat the post-create wait as "verify via host docker, not via Coolify API". Or skip the wait entirely if you'll do the DB restore next (the restore will fail loudly if the container actually isn't up). Discovered during the Example App migration — burned ~10 seconds of confusion and one unnecessary diagnostic SSH before the pattern became clear.

---

## G27. `mongorestore --drop` rewrites `admin.system.users` and invalidates Coolify's generated DB password

**Symptom:** Immediately after `mongorestore --drop --archive=...` succeeds (documents restored, exit code 0), any subsequent `mongosh -u root -p <coolify-generated-password>` connection fails with `MongoServerError: Authentication failed.` — even though the same password was used to issue the restore command moments earlier. The Coolify-injected `MONGODB_URI` env var (which the app uses) is now broken.

**Cause:** Mongo's authentication data lives in the `admin.system.users` collection. When the source dump includes the `admin` database (any typical `mongodump --archive` of the whole instance does), `mongorestore --drop` drops `admin.system.users` and re-inserts the source instance's user records. The fresh Coolify-generated `root` user is wiped; the OLD VPS's `root` user (with its OLD password hash) takes over. The new Mongo container is now authenticated against the source instance's credentials, not Coolify's.

**Fix (preferred):** Read the OLD password from the source `.env` / `paste-ready/*.env` file (it's in the `MONGODB_URI` value) and PATCH Coolify's stored `MONGODB_URI` to use the OLD password against the NEW Mongo container's UUID hostname:

```bash
OLD_PASS='<from old .env>'
NEW_URI="mongodb://user:<PASSWORD>@<HOST>:<PORT>/<DB>"
for IS_PREV in false true; do
  curl -sS -X PATCH "$COOLIFY_API_BASE/applications/$APP_UUID/envs" \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d "{\"key\":\"MONGODB_URI\",\"value\":\"$NEW_URI\",\"is_preview\":$IS_PREV,\"is_buildtime\":false,\"is_runtime\":true,\"is_literal\":true}"
done
```

**Fix (alternative, more invasive):** Restore everything EXCEPT the admin database (`--nsExclude='admin.*'`), so Coolify's fresh root user survives. Trade-off: any source-side admin-DB metadata (custom roles, etc.) is lost — but for most Maillayer-style apps that store data in app-specific collections, this is harmless.

**Prevention:** When migrating a Mongo-backed app, anticipate the admin-DB overwrite as part of the standard restore flow. Capture the source MongoDB password from the source env BEFORE provisioning the new Coolify Mongo resource, so you have it ready to PATCH `MONGODB_URI` immediately post-restore. Note: this is a Mongo-specific gotcha; the Postgres equivalent (G11) is about dump-version mismatch, NOT credential overwrite — `pg_restore --data-only` doesn't touch `pg_catalog.pg_authid` so the Coolify-generated postgres password survives.

Discovered during the Maillayer migration (<DATE>).

---

## G28. First-deploy git clone via Coolify's deploy-key path is bandwidth-throttled from this Lightsail region

**Symptom:** First deploy of a fresh repo sits in the git-clone step for 20-30 minutes before `next build` even starts. Inspecting the build container shows the `tmp_pack_*` file growing at ~16-20 KB/sec. Subsequent deploys (with Docker layer cache warm) are normal (~3 min).

**Cause:** GitHub throttles SSH-based git protocol transfers asymmetrically by source IP / connection reputation. The new Lightsail VPS at `<YOUR_SERVER_IP>` (eu-central-1) consistently hits this throttle when cloning via Coolify's deploy-key SSH path. Even shallow clones (`--depth=1`) suffer because the pack file is still tens of MB. Same VPS, same deploy-key pattern as the Example App / exampleapp2 migrations — those just happened to have smaller repos so the cost was hidden under 10 minutes total.

**Fix:** None during the build itself — just budget extra wall-clock time for the FIRST deploy of any repo larger than ~10 MB shallow-clone. Subsequent deploys reuse Docker layers + source tree and are normal speed.

**Workaround if intolerable:** Switch the app's git source from "Deploy key (SSH)" to "GitHub App (HTTPS)" — HTTPS clones from GitHub are not throttled the same way. Requires registering a Coolify GitHub App and installing it on the source repo. Worth it only if you'll be doing repeated initial deploys of large repos; one-off migration sprints just wait it out.

**Prevention:** When budgeting wall-clock for a migration plan, estimate first-deploy clone time as `(local .git size MB) ÷ 0.02 MB/s` for this VPS region. Maillayer's 35 MB `.git` → ~29 min predicted, ~28 min actual. Discovered during the Maillayer migration (<DATE>).

---

## G29. Private-deploy-key apps don't auto-deploy on `git push` — webhook setup is a separate manual step

**Symptom:** You push commits to `main` and Coolify doesn't redeploy. No log entry, no queued deployment, nothing in `GET /deployments/applications/{uuid}`. The repo is reachable from Coolify (the deploy itself works when triggered manually via the dashboard or `POST /deploy`), so the deploy-key auth is healthy — it's just that nothing TOLD Coolify a push happened.

**Cause:** The `/applications/private-deploy-key` endpoint only sets up the **pull half** of the relationship: Coolify has SSH read access to clone the repo. There's no inverse push-notification path — GitHub has no idea Coolify exists. Auto-deploy needs a separate GitHub-side webhook configured on the repo, pointing at Coolify's webhook endpoint, with the per-app secret.

This is the difference between the **deploy-key** flow and the **GitHub App** flow. A GitHub App installation handles both clone access AND push webhooks in one setup; deploy keys are clone-only. When you choose `private-deploy-key` for simplicity (one keypair per repo, no GitHub App registration overhead), you owe yourself the manual webhook step.

**Fix:** Add a GitHub webhook to each repo:

- **URL**: `https://coolify.<your-host>/webhooks/source/github/events/manual` (single URL for all apps)
- **Content-Type**: `application/json`
- **Secret**: the per-app `manual_webhook_secret_github` value from `GET /applications/{uuid}` — Coolify auto-generates this when you create the app, but doesn't surface it anywhere obvious. Each app has its OWN secret, and Coolify uses HMAC validation to route incoming requests to the correct app.
- **Events**: just `push` is enough
- **Active**: yes

Use `scripts/setup-github-webhook.sh <app-name> <owner>/<repo>` — it does all of the above + fires a test ping to verify. Idempotent.

Verify post-setup: the response on `GET repos/<owner>/<repo>/hooks` should show `last_response: {status: "active", code: 200}` after a test ping. Any other code means the secret is wrong, the URL is unreachable, or Coolify isn't routing properly.

**Prevention:** Add to your migration runbook as Phase 1.6 (after app creation, before first deploy). Every `private-deploy-key` app needs this. The Coolify dashboard shows the webhook URL + secret per-app under the app's General/Webhook settings, but only AFTER you click into the app — easy to miss during programmatic provisioning.

Discovered during the example HQ migration follow-up (<DATE>), retroactively applied to all four already-migrated apps.

---

## See also

- `coolify-hardening.md` — security playbook (do this before opening to the internet)
- `coolify-automation.md` — API reference + curl/Node patterns
- `coolify.md` — general overview
- `your private incident notes` — the chronological "what we did, what failed, why" for the Example App run
