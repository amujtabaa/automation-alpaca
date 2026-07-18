# Cloudflare MCP Setup — DNS Write for VPS Cutover

> **Note:** The runnable helper scripts referenced below (inventory, provision, db-migrate, cutover, env-import) describe a migration methodology. The original versions were specific to one environment and are NOT bundled in this template; implement them against your own Coolify API and infrastructure.

**Purpose:** Configure Claude Code to list and update Cloudflare DNS records via MCP tool calls, so Phase 5 cutover can flip A records across `example.com`, `example.com`, `example.com`, `example.com` without touching the Cloudflare dashboard.

**Approach:** `cloudflare-dns-mcp` npm package, stdio transport.

Rationale: Cloudflare's remote MCP at `mcp.cloudflare.com/mcp` requires interactive OAuth (Bearer token mode is broken in Claude Code as of April 2026 — Issue #95 in `cloudflare/mcp`). The `cloudflare-dns-mcp` package runs locally via `npx`, authenticates with an API token env var, exposes dedicated DNS CRUD tools, and works on Windows PowerShell without any OAuth dance or browser redirect.

---

## Prerequisites

- Node.js 18+ installed (`node --version`)
- Claude Code CLI installed
- Cloudflare account with zones: `example.com`, `example.com`, `example.com`, `example.com`

---

## Step 1 — Create the Cloudflare API Token

1. Go to: `https://dash.cloudflare.com/profile/api-tokens`
2. Click **Create Token**
3. Click **Use template** next to **Edit zone DNS**
4. Under **Zone Resources**, change "All zones" to **Specific zone**, then add each zone one at a time:
   - `example.com`
   - `example.com`
   - `example.com`
   - `example.com`
5. Under **Permissions**, verify these two rows are present (the template adds them):
   - Zone | DNS | **Edit**
   - Zone | Zone | **Read**
6. Leave **Client IP Address Filtering** blank (adding a filter here breaks the mcp-server token detection).
7. Click **Continue to summary** → **Create Token**
8. Copy the token immediately. It is shown once. Save it to `.env.migration` as:
   ```
   CLOUDFLARE_MCP_TOKEN=cf_YOUR_TOKEN_HERE
   ```
   `.env.migration` must be in `.gitignore`.

---

## Step 2 — Configure .mcp.json

Claude Code looks for project-level MCP config at `.mcp.json` in the project root. For user-level (available across all projects), use `%USERPROFILE%\.claude\settings.json` under `mcpServers`.

**Recommendation:** Use project-level `.mcp.json` in the `migration/` folder context, but since this token is personal and not team-shared, configure it at user level so the token never touches the committed repo.

### User-level config (recommended for this token)

Edit `C:\Users\<USER>\.claude\settings.json`. Add or merge this into the top-level `mcpServers` object:

```json
{
  "mcpServers": {
    "cloudflare-dns": {
      "command": "npx",
      "args": ["-y", "cloudflare-dns-mcp"],
      "env": {
        "CLOUDFLARE_API_TOKEN": "YOUR_TOKEN_HERE"
      }
    }
  }
}
```

Replace `YOUR_TOKEN_HERE` with the actual token value. Do not use `${ENV_VAR}` expansion here — Claude Code's user settings file is not committed and is the correct place for the literal value.

### Alternative: project-level .mcp.json (if you want it scoped to this repo)

Create `<your-project>\.mcp.json`:

```json
{
  "mcpServers": {
    "cloudflare-dns": {
      "command": "npx",
      "args": ["-y", "cloudflare-dns-mcp"],
      "env": {
        "CLOUDFLARE_API_TOKEN": "${CLOUDFLARE_MCP_TOKEN}"
      }
    }
  }
}
```

Then add `CLOUDFLARE_MCP_TOKEN` to your shell environment (PowerShell profile or Windows system env vars). Do not commit `.mcp.json` if it contains a literal token.

---

## Step 3 — Restart Claude Code

Close the current Claude Code session entirely and reopen it. On the first prompt after restart, Claude Code spawns MCP servers listed in config. You should see `cloudflare-dns` appear in the deferred tools list in the system reminder.

To verify without a prompt, run:

```powershell
claude mcp list
```

Expected output includes a `cloudflare-dns` entry with status connected.

---

## Step 4 — Verification Test

Once MCP is active, paste this into Claude Code:

```
List all Cloudflare zones on my account, then list all DNS records for example.com.
```

Claude will call `list_zones` (returns zone IDs and names for all 4 zones), then `list_dns_records` for `example.com`. Cross-check the record count against what you see in the Cloudflare dashboard under `example.com` → DNS → Records.

To verify the write path works before cutover day, run a test create-and-delete:

```
Create a DNS A record: name=example.com, content=127.0.0.1, proxied=false, ttl=60.
Then confirm it was created, then delete it.
```

If both succeed and the record appears then disappears in the dashboard, the MCP write path is confirmed.

---

## DNS Tool Reference

All tools are exposed via the `cloudflare-dns` MCP server. Claude calls these automatically when you describe the DNS operation in natural language.

### `list_zones`

Lists all zones (domains) associated with the API token's authorized accounts.

| Parameter | Type | Required | Notes                                  |
| --------- | ---- | -------- | -------------------------------------- |
| _(none)_  |      |          | Returns all zones the token can access |

Response includes: `id`, `name`, `status`, `paused`, `plan`.

---

### `list_dns_records`

Lists DNS records for a zone.

| Parameter     | Type    | Required               | Notes                                                |
| ------------- | ------- | ---------------------- | ---------------------------------------------------- |
| `zone_id`     | string  | Yes (or `domain_name`) | Zone ID from `list_zones`                            |
| `domain_name` | string  | Yes (or `zone_id`)     | e.g., `example.com`                                  |
| `type`        | string  | No                     | Filter by record type: A, AAAA, CNAME, MX, TXT, etc. |
| `name`        | string  | No                     | Filter by record name                                |
| `page`        | integer | No                     | Pagination                                           |
| `per_page`    | integer | No                     | Default 20, max 100                                  |

---

### `find_dns_records`

Looks up a specific record by name (useful before update to get `record_id`).

| Parameter                  | Type   | Required | Notes                                     |
| -------------------------- | ------ | -------- | ----------------------------------------- |
| `zone_id` or `domain_name` | string | Yes      |                                           |
| `record_name`              | string | Yes      | e.g., `example.com` or `example.com` |
| `type`                     | string | No       | Narrow to A, CNAME, etc.                  |

---

### `create_dns_record`

Creates a new DNS record.

| Parameter                  | Type    | Required | Notes                                                                 |
| -------------------------- | ------- | -------- | --------------------------------------------------------------------- |
| `zone_id` or `domain_name` | string  | Yes      |                                                                       |
| `type`                     | string  | Yes      | A, AAAA, CNAME, MX, TXT, etc.                                         |
| `name`                     | string  | Yes      | Full name e.g., `example.com` or `@` for root                    |
| `content`                  | string  | Yes      | IP address for A records                                              |
| `ttl`                      | integer | No       | 1 = auto, 60-86400 for explicit. Use 60 during cutover window         |
| `proxied`                  | boolean | No       | `true` = orange cloud (Cloudflare proxy on). Keep `true` for web apps |
| `priority`                 | integer | No       | MX records only                                                       |

---

### `update_dns_record`

Updates an existing DNS record. Use `find_dns_records` first to get `record_id`.

| Parameter   | Type    | Required | Notes                                         |
| ----------- | ------- | -------- | --------------------------------------------- |
| `zone_id`   | string  | Yes      |                                               |
| `record_id` | string  | Yes      | From `list_dns_records` or `find_dns_records` |
| `content`   | string  | No       | New IP for A record cutover                   |
| `ttl`       | integer | No       |                                               |
| `proxied`   | boolean | No       |                                               |
| `name`      | string  | No       |                                               |
| `type`      | string  | No       |                                               |

Only specified fields are updated (PATCH semantics).

---

### `delete_dns_record`

Deletes a DNS record permanently.

| Parameter   | Type   | Required | Notes |
| ----------- | ------ | -------- | ----- |
| `zone_id`   | string | Yes      |       |
| `record_id` | string | Yes      |       |

No confirmation prompt. The `cutover.mjs` rollback script re-creates deleted records if needed.

---

## Cutover Day Usage Pattern

The `04-cutover.mjs` script calls the MCP tools in sequence. For manual operation, the pattern is:

```
1. list_zones — confirm all 4 zones are visible
2. find_dns_records domain=example.com name=example.com type=A — get record_id + confirm current IP
3. update_dns_record zone_id=... record_id=... content=NEW_VPS_IP
4. list_dns_records domain=example.com type=A — verify updated content
5. Repeat steps 2-4 for each domain: example.com, example.com, example.com
6. Repeat for subdomains: example.com, example.com
```

Total domains to flip: 6 A records (see Phase 5 cutover plan).

---

## Rate Limits

Cloudflare's API rate limit for free/pro zones: **1,200 requests per 5 minutes** per API token. Each DNS update is 1 request; listing is 1 request. The entire cutover sequence (list + update + verify for 6 records) uses ~18-24 API calls. No rate limit risk.

---

## Troubleshooting

| Symptom                                     | Cause                                                                | Fix                                                                                           |
| ------------------------------------------- | -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `cloudflare-dns` not in deferred tools list | MCP server not loading                                               | Run `claude mcp list` to see status; check `settings.json` syntax with a JSON validator       |
| `Authentication error 10000`                | Token invalid or wrong scope                                         | Verify token in Cloudflare dashboard, confirm Zone DNS Edit + Zone Zone Read scopes           |
| `npx` not found                             | Node.js not on PATH                                                  | Run `node --version` in PowerShell; if missing, install Node.js 18+ and restart PowerShell    |
| `list_zones` returns empty                  | Token scoped to wrong zones or account                               | In Cloudflare dashboard, check token → edit → confirm all 4 zones listed under Zone Resources |
| `update_dns_record` returns 403             | Token has Read but not Edit on DNS                                   | Re-create token with Zone DNS Edit (not Read)                                                 |
| `record_id` not found                       | Querying wrong zone                                                  | Use `list_dns_records` with `domain_name` to dump all records, pick `id` from the result      |
| OAuth browser window opens                  | Using the remote `mcp.cloudflare.com` URL instead of the npx package | Remove any `url`-based entry for cloudflare from settings; use only the `command: npx` entry  |
| MCP server crashes on start                 | npx cache issue                                                      | Run `npx clear-npx-cache` or add `-y` flag to args if missing                                 |

---

## Alternatives Considered

**`mcp.cloudflare.com/mcp` (remote, OAuth):** Covers the entire Cloudflare API via Code Mode `search()`+`execute()` tools (~2,500 endpoints in 1k tokens). Excellent for general Cloudflare work. DNS writes work. However: requires interactive OAuth in a browser on first use, Bearer token auth is broken in Claude Code (Issue #95, opened April 2026), and the Code Mode tool interface requires writing JavaScript snippets rather than calling named DNS tools directly. Viable if OAuth issue is fixed before December.

**`dns-analytics.mcp.cloudflare.com`:** Read-only analytics. Cannot update records. Not suitable for cutover.

**`cloudflare/mcp-server-cloudflare` (old package):** Superseded by `cloudflare/mcp`. Contains a DNS analytics server but not a DNS write server.

---

## Pre-Cutover Ready Check

Run through this list before December cutover day:

- [ ] Node.js 18+ installed on the machine running Claude Code (`node --version`)
- [ ] API token created with Zone DNS Edit + Zone Zone Read scopes on all 4 zones
- [ ] Token saved in `settings.json` under `mcpServers.cloudflare-dns.env.CLOUDFLARE_API_TOKEN`
- [ ] `claude mcp list` shows `cloudflare-dns` as connected
- [ ] `list_zones` returns all 4 zones with correct names
- [ ] `list_dns_records` for `example.com` returns records matching the dashboard
- [ ] Test create + delete of `example.com` completed successfully (write path verified)
- [ ] Cloudflare TTLs on all 6 production A records set to 60s (Phase 0.3 — do 48h before cutover)
- [ ] `04-cutover.mjs` has zone IDs hardcoded or read from a config file (don't rely on name lookup during cutover)
- [ ] Rollback procedure tested: `04-cutover.mjs --rollback` with a mock receipt file

---

## Zone ID Reference

Captured <DATE> via `list_zones`. Zone IDs are stable, don't change.

| Domain             | Zone ID                            | Notes                                            |
| ------------------ | ---------------------------------- | ------------------------------------------------ |
| example.com        | `<CLOUDFLARE_ZONE_ID>` | Migrated from Hostinger <DATE> (17 records)  |
| example.com | `<CLOUDFLARE_ZONE_ID>` |                                                  |
| example.com          | `<CLOUDFLARE_ZONE_ID>` |                                                  |
| example.com      | `<CLOUDFLARE_ZONE_ID>` |                                                  |
| example.com        | `<CLOUDFLARE_ZONE_ID>` | example website (not in migration scope, FYI) |

All 5 zones use Cloudflare nameservers `<NS1>.ns.cloudflare.com` + `<NS2>.ns.cloudflare.com`.

Store zone IDs in `.env.migration` alongside the token, or hardcode into `04-cutover.mjs` to avoid name lookups during cutover.

---

## Library Note

This file is library-managed. After any edits, push from the library directory:

```bash
node sync.mjs --push
```
