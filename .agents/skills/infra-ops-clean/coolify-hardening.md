---
name: coolify-hardening
description: "Hardened Coolify v4 setup with private dashboard, internal-only databases, and supply-chain-aware deploys. Use when installing Coolify or auditing an existing install for the configuration mistakes that caused the <DATE> incident."
---

# Coolify Hardening Playbook

Battle-tested security configuration for Coolify v4 on Ubuntu Lightsail/EC2/Hetzner.
Every item below maps to a real-world failure mode: an npm supply-chain compromise that led to a host-root cryptominer and an L7 DDoS bot. Treat it as an illustrative scenario for your own hardening.

Keep your own incident record as you apply these steps.

---

## TL;DR — the 10 rules

| #   | Rule                                                                                     | Why                                                                                                                              |
| --- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **Dashboard bound to `127.0.0.1:8000`, exposed only via Cloudflare Tunnel**              | Old VPS had `0.0.0.0:8000` (login page reachable from internet). Independent attack surface that we still can't prove was clean. |
| 2   | **No database has `is_public: true` — internal Docker network only**                     | Old VPS exposed Postgres on 5432/5433 to public internet. Brute-forceable.                                                     |
| 3   | **Coolify admin password in 1Password, never in committed files**                        | Old `vps-core.md` had credentials in plaintext.                                                              |
| 4   | **App containers get explicit CPU + memory limits** (`limits_memory`, `limits_cpus`)     | Old VPS had no per-app limits → malware in one container consumed the whole 32GB box.                                            |
| 5   | **Every database has S3 backup configured at creation time** (daily, 14d + 4w retention) | Old VPS had zero DB backups. No clean-restore option during incident.                                                            |
| 6   | **2FA enabled on Coolify admin account** (TOTP)                                          | Old account had password-only.                                                                                                   |
| 7   | **API tokens scoped to sprint, revoked at end**                                          | Old account had no tokens — no audit trail of admin actions.                                                                     |
| 8   | **Lightsail alarms: CPU > 80% sustained 1h + network-out > 2x baseline**                 | Old VPS gave 8 days of L7 DDoS before AWS reported it.                                                                           |
| 9   | **Lightsail automatic snapshots from day 1**                                             | Old VPS only got automatic snapshots 8 days before incident.                                                                     |
| 10  | **Per-repo `pnpm audit` in CI + lockfile review on every PR**                            | Root cause was a malicious npm dep.                                                                                              |

---

## 1. Pin Coolify dashboard to localhost (security rule #1)

Coolify v4.1's install script binds the dashboard to `0.0.0.0:8000`. This is the **single most important fix** from the incident.

### Why the simple `.env` override doesn't work

You might think setting `APP_PORT=127.0.0.1:8000` in `/data/coolify/source/.env` would do it (the compose uses `${APP_PORT:-8000}:8080`). It doesn't — Docker compose validates the host port as an integer and rejects the colon-containing value with `invalid start port: invalid syntax`.

### What actually works

Edit `/data/coolify/source/docker-compose.prod.yml` directly. Three lines need changing:

```yaml
# Before                                After
- "${APP_PORT:-8000}:8080"        →    - "127.0.0.1:${APP_PORT:-8000}:8080"
- "${SOKETI_PORT:-6001}:6001"     →    - "127.0.0.1:${SOKETI_PORT:-6001}:6001"
- "6002:6002"                     →    - "127.0.0.1:6002:6002"
```

Use the Python helper at `scripts/fix-coolify-compose.py` — it's idempotent (running twice is a no-op).

Then recreate the containers:

```bash
sudo bash -c 'cd /data/coolify/source && \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate coolify soketi'
```

Verify with `sudo ss -tlnp | grep -E ':8000|:6001|:6002'` — all three should be `127.0.0.1:...`, not `0.0.0.0:...`.

### Verify externally unreachable

From your local machine (not the VPS):

```bash
curl -sS --max-time 5 -o /dev/null -w '%{http_code}\n' http://<VPS_IP>:8000
# Expected: timeout (curl exit 28) or connection refused. NOT 200.
```

---

## 2. Cloudflare Tunnel for private dashboard access

Once the dashboard is `127.0.0.1`-bound, you need a way to reach it. Cloudflare Tunnel gives you:

- HTTPS at the edge (Cloudflare-issued cert, you don't need Let's Encrypt for the dashboard)
- Origin IP hidden
- No public port 8000 anywhere

### Setup (~10 min total)

```bash
# Install cloudflared
curl -fsSL -o /tmp/cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i /tmp/cloudflared.deb

# Authenticate (INTERACTIVE — prints a URL, you click it in browser, select zone)
cloudflared tunnel login
# Writes ~/.cloudflared/cert.pem

# Create tunnel + auto-add DNS record using cert.pem
cloudflared tunnel create coolify-<host-name>
cloudflared tunnel route dns coolify-<host-name> coolify.<your-domain>

# Move credentials to /etc/cloudflared so the systemd service can read them
sudo mkdir -p /etc/cloudflared
sudo cp ~/.cloudflared/*.json /etc/cloudflared/

# Write config
sudo tee /etc/cloudflared/config.yml <<EOF
tunnel: coolify-<host-name>
credentials-file: /etc/cloudflared/$(ls ~/.cloudflared/*.json | xargs basename)

ingress:
  - hostname: coolify.<your-domain>
    service: http://localhost:8000
    originRequest:
      noTLSVerify: true
  - service: http_status:404
EOF

# Install as systemd service
sudo cloudflared --config /etc/cloudflared/config.yml service install
sudo systemctl enable --now cloudflared
```

Verify:

```bash
curl -I https://coolify.<your-domain>/  # 302 → /login = Coolify alive
curl --max-time 5 http://<VPS_IP>:8000/  # timeout = direct path closed
```

### Optional: add Cloudflare Access policy

For higher security, gate the dashboard behind a Cloudflare Access policy (SSO via Google, GitHub, or email PIN). Zero Trust → Access → Applications → Add → self-hosted, hostname = `coolify.<your-domain>`, identity provider = your choice. The dashboard then requires Access auth on top of Coolify's own login.

---

## 3. Databases stay internal (security rule #2)

Coolify's "Make Public" toggle on database resources is the Postgres exposure trap. **Never enable it.**

Always create databases via API with `is_public: false`:

```bash
curl -sS -X POST "$COOLIFY_API_BASE/databases/postgresql" \
  -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "server_uuid": "...",
    "project_uuid": "...",
    "environment_name": "production",
    "name": "myapp-postgres",
    "image": "postgres:17-alpine",
    "is_public": false,
    "instant_deploy": true
  }'
```

When apps need access, they reach the DB by the **internal Coolify Docker network**, using the container UUID as hostname. Coolify returns the connection string in the create response:

```
postgres://user:<PASSWORD>@<HOST>:<PORT>/<DB>
```

This URL only works **inside** the `coolify` Docker network. From outside the box, the port isn't bound. That's the point.

---

## 4. Resource limits per app (security rule #4)

Always set explicit limits in the application config. Without them, a compromised container can eat the whole host (as happened on <SERVER_NAME> — the malware in example-website's container had no caps, so it pinned all 8 vCPUs at 40% sustainable for 8 days of L7 DDoS).

API parameters:

```json
{
  "limits_memory": "2g", // hard cap on RAM
  "limits_cpus": "1.5" // hard cap on CPU shares (1.5 = 1.5 cores)
}
```

Right-size based on actual usage. Typical for a Next.js SaaS handling a few hundred users: `2g` memory, `1.5` cpus. Larger Mongo / queue workers: `4g`, `2.0`.

You can also add `limits_memory_swap`, `limits_memory_reservation`, `limits_cpu_shares` for finer control — but `limits_memory` + `limits_cpus` cover 95% of cases.

---

## 5. S3 backups configured at DB creation time (security rule #5)

Coolify supports daily S3 backups per database, but they're OFF by default. Configure during creation, not "later". The old VPS had "configure backups in Phase 0" as a December migration item that was never reached — so the incident had no clean DB to restore from.

### One-time setup

1. **Create an S3 bucket** (or Backblaze B2 / R2). Recommended: `<your-name>-coolify-backups-<year>`. Block all public access. Lifecycle rule: transition to Glacier Deep Archive after 90 days.
2. **Create a dedicated IAM user** with `s3:PutObject` + `s3:GetObject` + `s3:ListBucket` scoped to that bucket only.
3. **Add the S3 destination in Coolify**: Sources & Destinations → S3 Storages → New. Fill in endpoint (`https://s3.<region>.amazonaws.com`), bucket, access key, secret. Click Validate.

### Per database

After creating each DB resource, configure its Backups tab:

- Schedule: daily at low-traffic hour (e.g. `0 3 * * *` UTC)
- Retention: 14 daily + 4 weekly
- Destination: the S3 storage above
- Trigger a manual backup once → confirm the file appears in S3 → restore-test on a throwaway DB

If you skip this and your box is compromised, **the dumps inside the box are also compromised** — no clean restore.

---

## 6. Coolify self-management SSH requirements (DON'T over-harden)

Coolify v4 runs as a Docker container. It manages the host's Docker daemon by **SSHing from inside its container TO the host as `root`**, using its own self-generated ed25519 key. This pattern is unfamiliar to people who hardened the host first, then installed Coolify second — which is the right order security-wise, but creates 3 specific friction points.

The hardening from `vps-security-setup.md` (specifically `PermitRootLogin no`, UFW deny-by-default, Fail2ban) MUST be relaxed in narrow specific ways. Don't roll these back:

| Setting                                  | Hardened default       | Coolify-compatible value                                                                   | Why this is still safe                                                                            |
| ---------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `/etc/ssh/sshd_config` `PermitRootLogin` | `no`                   | **`prohibit-password`**                                                                    | Root login only via SSH key, never password. Brute force still hits Fail2ban.                     |
| `/root/.ssh/authorized_keys`             | empty                  | **One** ed25519 line from Coolify (`ssh-ed25519 ... coolify`)                              | Only Coolify's own container holds the matching private key.                                      |
| UFW rules for SSH                        | `22/tcp` from anywhere | Add: `22/tcp from <coolify-bridge-subnet>`                                                 | Only the Coolify Docker bridge can reach 22 internally; public 22 is unchanged.                   |
| Fail2ban during initial setup            | active                 | active — but unban the Coolify bridge IP once: `fail2ban-client set sshd unbanip 10.0.1.5` | Fail2ban will dynamic-ban Coolify after 3 failed attempts during the above setup. One-time unban. |

After Coolify runs successfully, the ed25519 heartbeat from `10.0.1.x:22` (the Coolify container) accumulates over time — 8 stale zombie sshd processes per quarter is normal. **DO NOT mistake them for attacker sessions.** See `your private incident notes` for why this initially looked like an active compromise (it wasn't).

Find the Coolify bridge subnet dynamically:

```bash
COOLIFY_SUBNET=$(sudo docker network inspect coolify --format '{{(index .IPAM.Config 0).Subnet}}')
sudo ufw allow from "$COOLIFY_SUBNET" to any port 22 proto tcp comment 'Coolify self-management SSH'
```

The full chronology of these 3 fixes is in `your private incident notes`.

---

## 7. Lightsail-specific firewall (NOT just UFW)

**Easy-to-miss gotcha**: Lightsail has a network-level firewall **separate from** UFW on the host. Lightsail opens only **22 + 80** by default. **443 must be added manually before HTTPS works.**

Symptoms when 443 is missing:

- `curl https://yourdomain.com` from outside times out
- Cloudflare returns HTTP 522 (origin connection timeout)
- Coolify's Traefik can't complete Let's Encrypt HTTP-01 ACME challenges
- `curl https://localhost:443` from inside the VPS works fine (UFW + Traefik both happy)
- `sudo ss -tlnp | grep :443` shows it bound — making it seem like a working setup

The fix is in the Lightsail console (no API path from within the box unless you mount AWS creds, which is exactly what you don't want):

1. Lightsail console → instance → **Networking** tab
2. IPv4 Firewall → Add rule → Application: **HTTPS** (TCP 443, source: Anywhere)
3. Repeat for IPv6 Firewall
4. Save

Document the fact that this was done in `vps-core.md`. It's a one-time setup but the kind of thing that bites you 6 months later when you provision instance #2 and forget.

---

## 8. Monitoring alarms

Set in Lightsail console (no Coolify equivalent — these are infra-level):

- **CPU**: ≥ 80% sustained for 60 min, evaluate 1 of 1 datapoints → email
- **Network out**: ≥ 5 GB/hr (or 2x your normal baseline — observe a few days first) → email
- **Disk usage** (if available): ≥ 80%

Why these specific thresholds: the <SERVER_NAME> incident had CPU pinned at 40% (the plan's "sustainable" threshold — the attacker was calibrating against AWS' burst throttling) and outbound traffic at ~5x normal. The thresholds above would have caught it.

For more sensitive setups, add a Cloudflare WAF rate-limit rule on suspicious paths (`/wp-login.php`, `/.env`, `/admin`) that emails on first hit.

---

## 9. 2FA + API tokens

After first admin login:

1. **Profile → Two-Factor Authentication → Enable** (TOTP via 1Password / Authy / Aegis). Store backup codes in 1Password.
2. **API tokens are scoped per migration sprint, never long-lived.** Profile → API Tokens → Create. Name like `migration-2026-05`. Scope: root for the migration, then revoke.
3. Don't reuse tokens across sprints — each gets its own audit trail.
4. Keep the token in a gitignored `~/.coolify-migration.env` or `.env.migration` file on your local machine, never committed.

---

## 10. Supply chain hygiene

Root cause of the <DATE> incident: a malicious npm dependency in the example Website's `package.json`. The dep ran on `npm start` and decoded base64 payloads to launch a cryptominer + a malware process (the L7 DDoS bot).

Three controls per repo:

| Control               | What                                                                                              | When           |
| --------------------- | ------------------------------------------------------------------------------------------------- | -------------- |
| Lockfile review       | Every PR that touches `package.json` / `pnpm-lock.yaml` / `yarn.lock` gets manually-reviewed diff | PR review time |
| `pnpm audit` CI check | `.github/workflows/audit.yml` runs `pnpm audit --audit-level=moderate` on every PR                | Pre-merge      |
| Container caps        | Already covered by rule #4 — explicit memory + CPU limits per app                                 | Coolify config |

These don't prevent a supply-chain compromise but they (a) make it harder to ship one accidentally, (b) limit the blast radius once it runs.

---

## Verification checklist (per new install)

Run through this before declaring a Coolify install "production":

- [ ] `sudo ss -tlnp | grep 8000` → `127.0.0.1:8000` only, no `0.0.0.0`
- [ ] `sudo ss -tlnp | grep -E ':6001|:6002'` → both `127.0.0.1`
- [ ] `curl --max-time 5 http://<VPS_IP>:8000/` from outside → timeout/refused
- [ ] `https://coolify.<your-domain>/` → 302 to /login (via Cloudflare Tunnel)
- [ ] `sudo systemctl is-active cloudflared` → `active`
- [ ] Coolify admin password is from password manager, length ≥ 20, never committed
- [ ] 2FA enabled, backup codes saved
- [ ] No databases have `is_public: true` (check via API: every DB returns `is_public: false`)
- [ ] Every running app has `limits_memory` and `limits_cpus` set (PATCH if missing)
- [ ] S3 destination configured in Coolify
- [ ] Each DB has a daily backup schedule with retention rules
- [ ] First S3 backup uploaded and verifiable
- [ ] Lightsail firewall rules include 443 (IPv4 + IPv6)
- [ ] Lightsail CPU + network-out alarms set
- [ ] Lightsail automatic snapshots enabled
- [ ] `.gitattributes` and `.gitignore` cover any credentials files in the repo
- [ ] CI: `pnpm audit` enforcement on every PR for every deployed app

---

## See also

- `coolify-automation.md` — API patterns for programmatic management
- `coolify-gotchas.md` — undocumented Coolify v4 quirks discovered the hard way
- `coolify.md` — general overview + install
- `vps-security-setup.md` — host-level hardening (do this first)
- `vps-core.md` — your specific servers
- `your private incident notes` — full incident record this playbook is derived from
