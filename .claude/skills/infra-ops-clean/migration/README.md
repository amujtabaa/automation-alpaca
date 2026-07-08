# Coolify VPS Migration Plan — December 2026

> **Note:** The runnable helper scripts referenced below (inventory, provision, db-migrate, cutover, env-import) describe a migration methodology. The original versions were specific to one environment and are NOT bundled in this template; implement them against your own Coolify API and infrastructure.

**Strategy:** Option C — Coolify-managed migration with parallel VPS soak and Cloudflare MCP cutover.
**Target window:** December 2026 (start prep October-November 2026).
**Source:** AWS Lightsail Frankfurt (`<YOUR_SERVER_IP>`, Ubuntu 24.04.3 LTS, Coolify 4.0.0-beta.459).
**Destination:** TBD (AWS Lightsail clone, Hetzner CCX33, or equivalent — final choice deferred to Phase 2).

This document is the master runbook. Scripts referenced live in `./scripts/`. Discovered state from the May 2026 exploratory probe is captured in `## Current State Snapshot` and drives the per-service migration manifest in `## Per-Service Migration Manifest`.

---

## Progress Log

### <DATE> — Cloudflare MCP + example.com unification

Pre-Phase 0 work, completed early to remove cutover-day friction:

- [x] Cloudflare DNS MCP installed at project level (`.mcp.json` → `cloudflare-dns` server, npm package `cloudflare-dns-mcp`)
- [x] Cloudflare API token created, scoped to all zones, saved to `.env` at repo root (was `.env.example` until <DATE>; rotate after December cutover)
- [x] MCP verified working — `list_zones`, `list_dns_records`, `create_dns_record` all return successfully
- [x] **example.com migrated from Hostinger to Cloudflare** — was on Hostinger parking nameservers, now on Cloudflare. Auto-import captured 10/17 records; the other 7 (1 A + 6 DKIM CNAMEs) added manually via MCP. All 17 verified character-for-character against Hostinger source. Zone status: `active` (nameserver swap propagated <DATE>)
- [x] All 5 production zones now Cloudflare-managed and MCP-accessible: `example.com`, `example.com`, `example.com`, `example.com`, plus `example.com` (in scope but not a migration target)
- [x] Lightsail automatic snapshots enabled — rolling 7-day VPS-level backup floor, fully covered by AWS credits through end of year
- [x] Migration methodology documented (inventory, provision, db-migrate, cutover steps). Runnable scripts are environment-specific and NOT bundled in this template.

**Impact:** Cutover-day surface is now uniform — all 6 production A records (example.com, example.com, example.com, example.com, example.com, example.com) can be flipped via a single `04-cutover.mjs` run against one Cloudflare account. No Hostinger touchpoint required during December.

### Next: dormant until October 2026

The plan resumes with the Phase 0 prep checklist (`scripts/00-prep-checklist.md`). Highest-priority items when work resumes:

1. Configure Coolify scheduled S3 backups (still empty — only Lightsail snapshots cover us right now)
2. Resolve Maillayer orphan duplicate in Coolify
3. Practice run on $5 test VPS
4. Choose destination provider (Lightsail clone vs Hetzner)

---

## Why Option C (and not A)

**Option C — Fresh Coolify + redeploy from Git + DB dumps:** cleanest end state, provider-agnostic, exposes any tech debt, every artifact is AI-readable/scriptable. Higher up-front work, lower long-term tax. **This is the chosen path.**

**Option A — Lightsail snapshot → restore:** captured here only as the **emergency fallback**. If the parallel soak reveals fundamental issues with C, snapshot the old Lightsail, restore as new instance, attach static IP, flip Cloudflare. ~30 min recovery if needed. Constraints: AWS-only, perpetuates current Docker/Coolify state warts, no cleanup opportunity.

**Decision rule:** proceed with C. Only invoke A if the Phase 4 soak surfaces a blocker that can't be resolved in <48h.

---

## Current State Snapshot

Captured <DATE> via read-only SSH probe.

### Host

| Property  | Value                                                                                        |
| --------- | -------------------------------------------------------------------------------------------- |
| Provider  | AWS Lightsail (Frankfurt, `eu-central-1a`)                                                   |
| IP        | `<YOUR_SERVER_IP>`                                                                              |
| OS        | Ubuntu 24.04.3 LTS (kernel 6.14, AWS-tuned)                                                  |
| Specs     | 8 vCPUs, 32 GB RAM, 640 GB SSD                                                               |
| Uptime    | 170 days                                                                                     |
| Load avg  | 5.48 / 5.70 / 5.44 (moderate, near vCPU count — watch for capacity headroom on target)       |
| Disk used | **27 GB of 640 GB (5%)** — massively over-provisioned, can downsize target                   |
| Swap      | **None configured** — add 4 GB swap on target                                                |
| Timezone  | UTC                                                                                          |
| Firewall  | UFW active. Open: 22, 80, 443, 8000 (Coolify), 6001-6002 (realtime), 5432 (Postgres public) |
| Fail2ban  | Active, sshd jail only                                                                       |

### Coolify

| Component      | Version                   |
| -------------- | ------------------------- |
| Coolify        | 4.0.0 (channel: beta-459) |
| Helper         | 1.0.13                    |
| Realtime       | 1.0.13                    |
| Sentinel       | 0.0.21                    |
| Traefik        | 3.6.11                    |
| Docker         | 27.0.3                    |
| Docker Compose | v2.40.3                   |

**Critical finding:** `/data/coolify/backups/` is empty. **No scheduled database backups configured.** This must be remediated in Phase 0 before any migration work begins.

**Routing:** Coolify uses Traefik via the file provider; routes are written into Traefik dynamic config from Coolify's internal Postgres at deploy time. Container labels do **not** carry route info — the Coolify DB (`coolify-db`) is the source of truth.

### Apps (7 detected)

Queried from `coolify-db` `applications` table:

| Container ID               | App Name                                   | Domain               | Repository                      | Branch |
| -------------------------- | ------------------------------------------ | -------------------- | ------------------------------- | ------ |
| `<RESOURCE_UUID>` | Maillayer (docker-image variant)           | example.com     | coollabsio/coolify (image)      | main   |
| `<RESOURCE_UUID>` | Maillayer (git variant — likely stale)     | example.com     | <GITHUB_OWNER>/maillayer       | main   |
| `<RESOURCE_UUID>` | example Website                            | example.com          | <GITHUB_OWNER>/example-website | main   |
| `<RESOURCE_UUID>` | Example App                          | example.com   | <GITHUB_OWNER>/example  | main   |
| `<RESOURCE_UUID>` | Example App                                  | example.com            | <GITHUB_OWNER>/Example App       | main   |
| `<RESOURCE_UUID>` | example HQ (renamed from App <DATE>) | example.com | <GITHUB_OWNER>/example-HQ      | main   |
| `<RESOURCE_UUID>` | example                              | example.com        | <GITHUB_OWNER>/example   | main   |

**Cleanup opportunity:** Two Maillayer entries pointing at the same FQDN. Resolve before migration — confirm which is active, delete the orphan in Coolify, push the change before inventory.

### Databases (5 standalone)

| Container ID               | Engine                     | Public Port | Schema/DB                                                                              | Used By           |
| -------------------------- | -------------------------- | ----------- | -------------------------------------------------------------------------------------- | ----------------- |
| `<RESOURCE_UUID>` | Postgres 17-alpine         | Not exposed | `app_db` (DB name kept post-rename — see example HQ row)                             | example HQ        |
| `<RESOURCE_UUID>` | Postgres (Coolify-managed) | 5432       | `postgres` DB (12 tables: Account, Ad, Tool, Category, Report, User, etc.)             | Example App |
| `<RESOURCE_UUID>` | Postgres (Coolify-managed) | 5433       | `postgres` DB (9 tables: ApiKey, Purchase, UsageLog, indexing_projects, indexing_urls) | Example App         |
| `<RESOURCE_UUID>` | MongoDB 7                  | Not exposed | (auth-protected, contents TBD via API)                                                 | Maillayer         |
| `<RESOURCE_UUID>` | Redis 7.2                  | Not exposed | (cache, ephemeral)                                                                     | Maillayer         |

### Volumes (10)

- 3x `postgres-data-*` (one per Postgres)
- 2x `mongodb-*` (db + configdb)
- 1x `redis-data-*`
- 1x `<UUID_PREFIX>...-maillayer-data` (Maillayer file storage — likely email attachments)
- `coolify-db`, `coolify-redis` (Coolify internal state)
- 1x unnamed sha256 volume (investigate before migration)

Total volume size: ~920 MB. Combined with images (~16 GB), full data footprint is **~17 GB**. Migration data transfer is trivial.

### Networks

- `coolify` (bridge) — shared cross-app network
- `<RESOURCE_UUID>` (bridge) — orphan from stale Maillayer
- Standard `bridge`, `host`, `none`

### Mongo/Redis on Maillayer

Maillayer uses Mongo for primary store + Redis for queue/cache. Credentials live in app env vars (extract via Coolify API in Phase 1).

---

## Phase 0 — Preparation (October-November 2026)

Two months of runway. Do these in order. Each is independently valuable even if the migration is delayed.

### 0.1 Fix the backup gap (CRITICAL — week 1)

**Status (<DATE>): Lightsail automatic snapshots ENABLED.** Rolling 7-day full-VPS snapshot now in place. This materially reduces Phase 0 urgency — even before Coolify-level backups are configured, a 24h-old full-disk snapshot exists at any moment. Snapshots cost ~$1.35/snapshot/month at 27 GB used (~$9.45/month for full 7-day rotation), fully covered by AWS credits through end of year. Plan to migrate the most recent snapshot to S3 Glacier Deep Archive (~$0.03/month) after the December cutover.

Still TODO for app-level granularity:

1. Provision an S3 bucket (or Backblaze B2 — cheaper) for Coolify backups.
2. In Coolify dashboard → each database resource → **Backups** → configure:
   - S3-compatible destination
   - Daily schedule (e.g., `0 3 * * *` UTC)
   - Retention: 14 daily + 4 weekly
3. Trigger a manual backup on each, verify file appears in S3.
4. Test restore on a throwaway DB to confirm the loop works.

Coolify-level backups become the primary data migration vehicle in Phase 3 (the Lightsail snapshot is the disaster-recovery floor; Coolify backups are the per-DB scalpel).

### 0.2 Resolve Maillayer duplicate

Two Maillayer Coolify app entries point at `example.com`. Identify the active one (likely `<UUID_PREFIX>...` since it's the docker-image variant and was last rebuilt May 6), delete the orphan via Coolify UI, verify example.com still resolves.

### 0.3 Lower Cloudflare TTLs

For all 5 domains (`example.com`, `example.com`, `example.com`, `example.com`, `example.com`, `example.com`):

- Set TTL on all A records to **60 seconds**.
- Do this **48 hours before** the planned cutover, not earlier (Cloudflare caches DNS aggressively at the edge, but downstream resolvers honor TTL).
- Records remain proxied (orange cloud) — TTL affects only upstream resolvers behind Cloudflare's CDN.

### 0.4 Generate Coolify API tokens

- Old VPS: `http://<YOUR_SERVER_IP>:8000` → **Profile → API Tokens** → create token with `read` scope (inventory only). Save to `.env.migration` as `COOLIFY_OLD_TOKEN`.
- New VPS: same flow once provisioned, save as `COOLIFY_NEW_TOKEN`.
- Both tokens never leave `.env.migration` (gitignored).

### 0.5 Cloudflare MCP server setup

See `## Cloudflare MCP Configuration` below. Test the connection by listing zones before cutover day.

### 0.6 Document a "VPS bill of materials"

Run `scripts/01-inventory.mjs` against the old VPS to produce `migration-inventory.json`. Manually review for completeness. Anything the script misses gets a manual entry in `migration-inventory-manual.json` (e.g., DNS records pointing at the VPS that aren't tied to a Coolify app).

### 0.7 Practice run

Two weeks before the real migration, spin up a $5 test VPS, install Coolify, run the full pipeline against **one non-critical app** (example Website is a good candidate — static-ish, no critical DB). Time each step. Catch failure modes. Iterate the scripts.

---

## Phase 1 — Inventory (December, Day 1)

**Goal:** Produce a single JSON file (`migration-inventory.json`) that fully describes the source VPS state. AI-readable. Reviewable. The migration's source of truth.

**Script:** `scripts/01-inventory.mjs`

### What it captures (per app)

- UUID, name, FQDN
- Git repo + branch + build pack (nixpacks / dockerfile / docker-image)
- Environment variables (decrypted values, via API)
- Domains (primary + any aliases)
- Custom build commands
- Health check config
- Volumes mounted (host paths)
- Linked databases/services

### What it captures (per database)

- UUID, name, engine, version
- Connection credentials
- Volume name + size on disk
- Linked apps (consumers)
- Backup schedule + S3 destination
- Latest backup timestamp

### What it captures (host-level)

- Coolify version (must match on target)
- Traefik version
- Open UFW ports
- Custom Traefik dynamic config files (`/data/coolify/proxy/dynamic/`)
- Any one-click services in `/data/coolify/services/` (currently empty per probe)

### Manual review gate

Before Phase 2, **stop**. Open `migration-inventory.json`, read it end-to-end, confirm every domain and env var is captured. Fix gaps in `migration-inventory-manual.json`. Commit both files to a private branch.

---

## Phase 2 — Provision New VPS (December, Days 2-3)

### 2.1 Decide on destination

Decision deferred to this point because the inventory will reveal actual resource needs (current usage is only ~12 GB RAM, ~27 GB disk, well under the Lightsail allotment).

| Option             | Cost/mo | Specs                           | Notes                                                            |
| ------------------ | ------- | ------------------------------- | ---------------------------------------------------------------- |
| AWS Lightsail 16GB | ~$80    | 4 vCPU, 16 GB, 320 GB           | Same provider, simpler ops, can use Option A as fallback         |
| Hetzner CCX33      | ~€30    | 8 vCPU dedicated, 32 GB, 240 GB | 60% savings, dedicated CPU (no neighbor contention), Falkenstein |
| Hetzner CCX23      | ~€18    | 4 vCPU dedicated, 16 GB, 160 GB | If usage stays at current ~12 GB                                 |

Pick based on Phase 1 inventory + a week of monitoring `htop`/`free -h` snapshots.

### 2.2 Provision

- Ubuntu 24.04 LTS (must match source major version)
- 4 GB swap file
- Same UFW rules as source (port list captured in inventory)
- SSH key-only auth, fail2ban
- Install Docker (matching v27.x to minimize compat risk)

### 2.3 Install Coolify

```bash
# Pin to the exact version running on source (beta-459)
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash -s 4.0.0-beta.459
```

Why pin: Coolify's internal schema may differ across versions. Provisioning with the same version means the API contracts match. Upgrade the new instance to latest only **after** migration is complete and stable.

### 2.4 Generate target API token, save to `.env.migration`.

### 2.5 Run provisioner

**Script:** `scripts/02-provision.mjs`

Reads `migration-inventory.json`, recreates on the target Coolify:

1. GitHub App authorization (manual one-time — Coolify must be re-authorized on the new host because GitHub App installations are tied to a hostname).
2. For each app: create application via API, set env vars, configure domains using **placeholder hostnames** (`<app>-example.com` or `<app>.example.com`), wire up databases.
3. For each database: create standalone resource, capture new connection string for app env vars.

Important: domains use **placeholder hostnames** at this point. Real production DNS still points at the old VPS. The new VPS gets its own subdomain set so each app is testable end-to-end without affecting users.

### 2.6 Add placeholder DNS

For each of the 6 production domains, add a parallel A record:

| Production           | Placeholder              |
| -------------------- | ------------------------ |
| example.com     | example.com     |
| example.com          | example.com          |
| example.com   | example.com   |
| example.com            | example.com            |
| example.com | example.com |
| example.com        | example.com        |

All point at the new VPS IP. Proxied through Cloudflare. SSL auto-issued by Let's Encrypt on new Coolify.

These get created via Cloudflare MCP at this stage (test the MCP path before cutover relies on it). See `scripts/04-cutover.mjs` `--placeholders` mode.

---

## Phase 3 — Data Migration (December, Day 4)

**Goal:** Restore every database and persistent volume from old VPS into new VPS.

**Script:** `scripts/03-db-migrate.sh`

### 3.1 Postgres dumps

For each of the 3 Postgres databases:

```bash
# On source VPS
sudo docker exec <RESOURCE_UUID> \
  pg_dump -U postgres -Fc app_db > app_db.dump

# Stream over SSH to target VPS, restore into new Coolify-managed Postgres
scp -i ~/.ssh/key app_db.dump ubuntu@NEW_IP:/tmp/
ssh ubuntu@NEW_IP "sudo docker cp /tmp/app_db.dump <NEW_PG_CONTAINER>:/tmp/ && \
  sudo docker exec <NEW_PG_CONTAINER> pg_restore -U postgres -d app_db --clean --if-exists /tmp/app_db.dump"
```

Repeat for `<UUID_PREFIX>...` (exampleapp2) and `<UUID_PREFIX>...` (Example App). Use the format-custom (`-Fc`) dump for fast parallel restore (`pg_restore -j 4`).

### 3.2 MongoDB dump

```bash
sudo docker exec <RESOURCE_UUID> \
  mongodump --username root --password $MAILLAYER_MONGO_PASS \
  --authenticationDatabase admin --archive > maillayer-mongo.archive

# Restore on target
sudo docker exec -i <NEW_MONGO_CONTAINER> \
  mongorestore --username root --password $NEW_MONGO_PASS \
  --authenticationDatabase admin --archive < maillayer-mongo.archive
```

### 3.3 Redis snapshot (optional)

Maillayer's Redis is cache/queue — likely ephemeral. Confirm with code review before deciding to migrate or let it rebuild empty.

### 3.4 Persistent volumes

For `<UUID_PREFIX>...-maillayer-data` (file attachments):

```bash
# On source
sudo tar -C /var/lib/docker/volumes/<UUID_PREFIX>...-maillayer-data/_data -czf maillayer-files.tgz .

# Transfer + restore
scp maillayer-files.tgz ubuntu@NEW_IP:/tmp/
ssh ubuntu@NEW_IP "sudo tar -xzf /tmp/maillayer-files.tgz -C /var/lib/docker/volumes/<NEW_VOLUME>/_data/"
```

### 3.5 Trigger first deploy

For each app on the new Coolify: trigger a deploy via API. Coolify pulls from GitHub fresh, builds, starts containers. Verify each comes up healthy.

### 3.6 Smoke test each app at its placeholder URL

Browse `https://example.com`, log in, send a test email. Browse `https://example.com`, verify tools list loads (matches 12-table schema). Etc.

---

## Phase 4 — Parallel Soak (December, Days 5-N)

Both VPSs running. Both healthy. Real users still on old VPS.

**You decide how long the soak lasts.** Recommended minimum: **7 days**. Comfortable: **14 days**. If anything in the inventory was uncertain (e.g., Redis data, build env quirks), longer.

### Soak activities

- Daily: run synthetic tests against each `*-new.*` URL (login, primary user flow, write operation, read operation).
- Compare logs old vs new (`docker logs <container> --since 24h` on each).
- Watch resource usage on new VPS — confirms target sizing was right.
- Send copies of any production webhooks/integrations to the new URLs (Maillayer SMTP test, Example App API key test against `https://example.com`).

### Pre-cutover sync

The day before cutover:

1. Re-run Phase 3 dumps to capture deltas (any writes since the initial migration day).
2. Restore deltas into new VPS Postgres/Mongo (use `--clean --if-exists` semantics to overwrite cleanly).
3. Confirm placeholder URLs still work post-delta-sync.
4. Generate the **cutover DNS plan** as a JSON file (input to `04-cutover.mjs`):

```json
{
  "zone_id": "abc123...",
  "records": [
    { "name": "example.com", "type": "A", "new_content": "NEW_IP" },
    { "name": "example.com", "type": "A", "new_content": "NEW_IP" },
    { "name": "example.com", "type": "A", "new_content": "NEW_IP" },
    { "name": "example.com", "type": "A", "new_content": "NEW_IP" },
    { "name": "example.com", "type": "A", "new_content": "NEW_IP" },
    { "name": "example.com", "type": "A", "new_content": "NEW_IP" }
  ]
}
```

---

## Phase 5 — Cutover via Cloudflare MCP (December, Cutover Day)

### 5.1 Pre-flight

- All synthetic tests green on new VPS.
- Latest DB sync ran <2 hours ago.
- Cloudflare TTL on all records confirmed at 60s.
- Take a Lightsail snapshot of the OLD VPS right now — this is the Option A rollback artifact.

### 5.2 Stop writes on old VPS (optional but cleaner)

For maximum data consistency: put old apps into read-only mode or stop them. For most use cases, the small delta between final dump and DNS propagation is acceptable.

**Recommended:** stop old containers for the apps with active writes (Maillayer especially) for ~10 min during cutover. example Website (static-ish) can run continuously.

### 5.3 Run cutover script

**Script:** `scripts/04-cutover.mjs`

Talks to Cloudflare via MCP. Operations:

1. For each record in cutover plan: read current value (sanity check), update to new IP.
2. Verify each update by re-reading the record.
3. Poll `dig +short` against `<YOUR_SERVER_IP>` until propagation observed.
4. Emit a `cutover-receipt.json` with timestamps and pre/post values.

Expected total wall time: 2-5 minutes (TTL is 60s, Cloudflare's edge cache flushes quickly).

### 5.4 Monitor

For the next 30 minutes:

- Watch logs on new VPS for incoming traffic.
- Watch Cloudflare Analytics for any 5xx spike.
- Hit each production URL from a clean network (mobile data, VPN) to catch DNS cache issues.

### 5.5 Rollback procedure (if needed)

`scripts/04-cutover.mjs --rollback cutover-receipt.json` — re-runs the receipt in reverse, restoring old IP on all records. Same 2-5 min wall time. Have this command ready in a terminal during cutover.

---

## Phase 6 — Decommission (December → January)

### 6.1 Keep old VPS running for **30 days** minimum after cutover

Cost is negligible compared to recovery cost if a regression surfaces.

### 6.2 During the 30 days

- All new writes go to new VPS.
- Old VPS becomes a frozen historical record.
- If a regression appears: flip DNS back via `--rollback`, re-sync any new-VPS writes back to old, investigate.

### 6.3 At 30 days

- Final Lightsail snapshot of old VPS (cold archive, ~$0.05/GB/month).
- Delete the old Lightsail instance.
- Remove placeholder DNS records (`*-new.*`).
- Update `vps-core.md` with new IP, new container names, new dashboard URL.
- Archive this folder to `_migration-archive/2026-12/`.

---

## Per-Service Migration Manifest

Each row is one item to migrate. Reviewed during Phase 1 inventory.

### Apps

| App                | Container UUID | Domain               | Migration approach                                  | DB dependency                       | Volume?                        |
| ------------------ | -------------- | -------------------- | --------------------------------------------------- | ----------------------------------- | ------------------------------ |
| Maillayer          | `<UUID_PREFIX>...`     | example.com     | Docker image redeploy + Mongo restore + volume sync | Mongo `<UUID_PREFIX>...`, Redis `<UUID_PREFIX>...`  | Yes (`<UUID_PREFIX>...-maillayer-data`) |
| example Website    | `<UUID_PREFIX>...`     | example.com          | Git redeploy, stateless                             | None                                | None                           |
| Example App  | `<UUID_PREFIX>...`     | example.com   | Git redeploy + Postgres restore                     | Postgres `<UUID_PREFIX>...` (12 tables)     | None                           |
| Example App          | `<UUID_PREFIX>...`     | example.com            | Git redeploy + Postgres restore                     | Postgres `<UUID_PREFIX>...` (9 tables)      | None                           |
| example HQ         | `<UUID_PREFIX>...`     | example.com | Git redeploy + Postgres restore                     | Postgres `<UUID_PREFIX>...` (app_db kept) | None                           |
| example      | `<UUID_PREFIX>...`     | example.com        | Git redeploy, **verify DB dependency in Phase 1**   | TBD                                 | TBD                            |
| Maillayer (orphan) | `<UUID_PREFIX>...`     | example.com     | **DELETE in Phase 0.2**                             | —                                   | —                              |

### Databases

| Container                    | Engine      | Migration method                                      | Risk                                         |
| ---------------------------- | ----------- | ----------------------------------------------------- | -------------------------------------------- |
| `<UUID_PREFIX>...` (app_db)        | Postgres 17 | `pg_dump -Fc` → `pg_restore`                          | Low — well-tested pattern                    |
| `<UUID_PREFIX>...` (exampleapp2)         | Postgres    | Same                                                  | Low                                          |
| `<UUID_PREFIX>...` (Example App)       | Postgres    | Same                                                  | Low                                          |
| `<UUID_PREFIX>...` (Maillayer Mongo) | MongoDB 7   | `mongodump --archive` → `mongorestore`                | Medium — auth quirks, verify with smoke test |
| `<UUID_PREFIX>...` (Maillayer Redis) | Redis 7.2   | **Re-evaluate:** rebuild empty vs `BGSAVE` + RDB copy | Low (likely ephemeral)                       |

---

## Cloudflare MCP Configuration

We're using Cloudflare's official MCP path (Option 1 from the strategy convo).

### Option A: Remote Cloudflare MCP (recommended for simplicity)

Cloudflare hosts a fleet of remote MCP servers. The relevant one for DNS work:

- **Server name:** `cloudflare-dns-analytics` (analytics-focused, read access)
- **Server name:** Self-hosted `mcp-server-cloudflare` (npm: `@cloudflare/mcp-server-cloudflare`) for **DNS record CRUD**.

For migration cutover, the **write capability** comes from the self-hosted variant (the official Cloudflare-hosted analytics MCP doesn't currently expose DNS write — verify at migration time).

### Setup

Add to project's `.mcp.json` (or `~/.mcp.json` for global):

```json
{
  "mcpServers": {
    "cloudflare": {
      "command": "npx",
      "args": ["-y", "@cloudflare/mcp-server-cloudflare", "run", "ACCOUNT_ID"],
      "env": {
        "CLOUDFLARE_API_TOKEN": "..."
      }
    }
  }
}
```

**API token scope:** create a custom token in Cloudflare dashboard → My Profile → API Tokens with:

- Zone → DNS → Edit
- Zone → Zone → Read
- Restrict to specific zones (example.com, example.com, example.com, example.com)

This token is the only credential the migration needs from Cloudflare. Store in `.env.migration`, never commit.

### Tools available via the MCP

The Cloudflare MCP exposes tool calls like:

- `dns_records_list(zone_id)`
- `dns_records_create(zone_id, type, name, content, proxied)`
- `dns_records_update(zone_id, record_id, content)`
- `dns_records_delete(zone_id, record_id)`
- `zones_list()`

Claude invokes these directly during cutover via tool use — no manual `curl` required.

### Pre-cutover MCP test (Phase 0.5)

Before relying on the MCP for cutover, prove it works:

1. Configure `.mcp.json` with the token.
2. Restart Claude Code, confirm Cloudflare tools appear in the deferred tools list.
3. Run a no-op: list zones, list DNS records for one zone, verify output matches Cloudflare dashboard.
4. **Add and delete a test record** (e.g., `example.com → 127.0.0.1`) to confirm write path works.

If the MCP can't write DNS (e.g., scope mismatch, token issue), fall back to the direct Cloudflare API path documented in `cloudflare-setup.md` — same end result, slightly more script.

---

## Scripts

These describe the migration steps. Only `00-prep-checklist.md` is bundled in this template; the runnable `.mjs`/`.sh` scripts below are environment-specific - implement them against your own Coolify API. A real implementation should never modify state without an explicit `--apply` flag.

| Script                 | Phase | Purpose                                                        |
| ---------------------- | ----- | -------------------------------------------------------------- |
| `00-prep-checklist.md` | 0     | Human checklist for prep phase                                 |
| `01-inventory.mjs`     | 1     | Old Coolify API → `migration-inventory.json`                   |
| `02-provision.mjs`     | 2     | `migration-inventory.json` → new Coolify (apps, envs, domains) |
| `03-db-migrate.sh`     | 3     | pg_dump / mongodump / volume tar → restore on target           |
| `04-cutover.mjs`       | 5     | Cloudflare MCP DNS swap (with `--rollback`)                    |

Each script writes a receipt file (`*-receipt.json`) so the next phase has structured input and the whole pipeline is replayable.

---

## Risk Register

| Risk                                            | Likelihood | Impact | Mitigation                                                                     |
| ----------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------ |
| Coolify API doesn't expose all env vars cleanly | Medium     | High   | Fallback: `docker inspect <container>` reads runtime env, merge into inventory |
| Mongo restore auth quirks                       | Medium     | High   | Tested in Phase 0.7 practice run                                               |
| Cloudflare TTL caching delays propagation       | Low        | Medium | Lower TTL 48h ahead in 0.3; monitor `dig`                                      |
| GitHub App re-auth blocks deploy                | Low        | High   | Done early in Phase 2.5, before any data work                                  |
| SSL issuance rate-limited on new domains        | Low        | Medium | Use staging Let's Encrypt for soak; switch to prod on cutover                  |
| Resource undersized on new VPS                  | Low        | Medium | Sized from Phase 1 inventory + a week of htop snapshots                        |
| Maillayer file volume not transferred           | Medium     | High   | Explicit checklist item in Phase 3.4                                           |
| Coolify version drift breaks restore            | Low        | High   | Pin to exact source version in Phase 2.3                                       |

---

## Success Criteria

Migration is "done" when **all** of these hold:

- [ ] All 6 production domains resolve to new VPS IP.
- [ ] Every app health-checks green on new Coolify dashboard.
- [ ] DB row counts match between old and new (sampled per major table).
- [ ] Synthetic test suite passes against production URLs (login, primary write, primary read per app).
- [ ] Maillayer can send + receive a test email.
- [ ] SSL valid on every domain.
- [ ] Cloudflare Analytics shows traffic landing on new VPS, zero traffic on old VPS for 24h.
- [ ] `vps-core.md` updated with new server details.
- [ ] Backup schedule active on new VPS, first successful S3 upload verified.
- [ ] Old VPS snapshot taken and stored cold.

---

## Cross-Cutting AWS Dependencies (not on the VPS, but tied to the migration)

The Coolify VPS is one piece. Two other AWS resources are tied to the apps and need a decision before December:

| Resource                | Purpose (likely)                                      | Migration implication                                                                                                                                                                         |
| ----------------------- | ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **AWS S3 bucket(s)**    | File storage (Maillayer attachments? backups? media?) | Staying on AWS → no change. Leaving AWS → migrate to Backblaze B2, R2, or Hetzner Object Storage. Bucket name + IAM creds live in app env vars; new VPS just needs same creds.                |
| **AWS SES**             | Transactional email sending (Maillayer SMTP relay)    | Staying on AWS → no change, sending domain + DKIM records stay put. Leaving AWS → migrate to Postmark, Resend, Brevo, or SES from a different account. DKIM/SPF/DMARC re-validation required. |
| **Lightsail snapshots** | Full-VPS rolling backup (enabled <DATE>)          | Covered by AWS credits through end of year. Post-migration, archive final snapshot to Glacier Deep Archive (~$0.03/mo).                                                                       |

**AWS credit coverage confirmed (<DATE>):** Lightsail, S3, SES, and Glacier Deep Archive are all on the active AWS credit list. All migration-related AWS spend through Dec 2026 is offset by credits.

**Action item (defer to Phase 1):** During inventory, capture which apps reference S3 buckets / SES creds in their env vars. Document bucket names, IAM key IDs, SES sending domain. Doesn't change cutover plan, just adds rows to the per-service manifest.

**Action item (defer if leaving AWS):** If the destination is non-AWS, a parallel migration plan for S3 + SES becomes a Phase 0 dependency. Both are doable in days, not weeks, but need their own runbooks.

---

## Open Questions (resolve before December)

1. **Destination provider** — AWS Lightsail clone, Hetzner CCX33, or other? Decision in Phase 2.1.
2. **example DB dependency** — does it share a DB with another app, have its own DB, or is it stateless? Confirm via Phase 1 inventory.
3. **Mongo credentials** — fetch from Maillayer env vars during Phase 1.
4. **Static IP on new VPS** — Lightsail requires explicit static IP attachment. Hetzner IPs are static by default.
5. **`example.com` MX records** — confirm whether Cloudflare hosts MX or if upstream provider does. MX migration is separate from A record cutover.

---

## Library Note

This folder is library-managed (`migration/`). After any edits during the migration:

```bash
# From library directory
node sync.mjs --push
```

Run this **before** the next library pull to avoid clobbering migration-day edits.
