# VPS Core Reference

Server credentials, SSH access patterns, and infrastructure quick reference.

> **TEMPLATE** - Replace example values with your own. Keep your customized copy private once it holds real credentials.
> Keep repository private.

---

## Servers Inventory

### Primary Server (<USER>-General) — current

| Setting      | Value                                                               |
| ------------ | ------------------------------------------------------------------- |
| **Provider** | AWS Lightsail                                                       |
| **Region**   | Frankfurt (eu-central-1a)                                           |
| **IP**       | <YOUR_SERVER_IP> (static: `<USER>-General-IP`, attached <DATE>) |
| **IPv6**     | <YOUR_SERVER_IPv6>                                                  |
| **Private**  | <YOUR_SERVER_IP>                                                    |
| **Username** | ubuntu                                                              |
| **OS**       | Ubuntu                                                              |
| **Specs**    | 8 GB RAM, 2 vCPUs, 160 GB SSD                                       |
| **Purpose**  | Coolify host — replacement for <SERVER_NAME> post-incident          |
| **Created**  | <DATE> (replacement after <SERVER_NAME> compromise)             |

**SSH Connection:**

```bash
ssh -i keys/<YOUR_SSH_KEY>.pem ubuntu@<YOUR_SERVER_IP>
```

**Prior ephemeral IPs (released):** `<YOUR_SERVER_IP>` (<DATE> → <DATE> stop/start). The <DATE> IP-loss incident — instance was stopped/started during a CPU thrash caused by Example CRM workers, ephemeral IPv4 changed, all 13 Cloudflare A records went stale → every public-facing app returned 000 for ~6 hours. Coolify dashboard kept working because cloudflared is outbound. Fix: attached static IP `<YOUR_SERVER_IP>` (free while attached to running instance), bulk-updated all 13 A records via Cloudflare API. **Never let this instance run without a static IP again.**

SSH key was regenerated in Lightsail (regional default keypair) before this instance was created — the key file in `keys/` is the fresh one (SHA256 `<SSH_KEY_FINGERPRINT>`), not the leaked pre-incident one.

**Status (<DATE>):** Provisioned + hardened + Coolify installed. SSH key-only, `PermitRootLogin prohibit-password` (key-only root needed for Coolify self-management), Fail2ban active with sshd jail, UFW restricted to 22/80/443 publicly + an additional rule allowing 22/tcp from the Coolify Docker bridge subnet (typically `10.0.1.0/24`) so Coolify can manage host Docker. Coolify v4.1.0 dashboard bound to `127.0.0.1:8000` (not public), exposed via Cloudflare Tunnel only. Apps not migrated yet — see `coolify-migration-runbook.md` for the per-app migration plan, Example App first.

**Phase 1 / 2 fixes encoded into this server's config** (do not roll these back without understanding Coolify's self-management pattern):

- `/root/.ssh/authorized_keys` contains the Coolify ed25519 pubkey `ssh-ed25519 <COOLIFY_PUBKEY> coolify`, required for Coolify container to SSH to host as root for Docker ops
- `/etc/ssh/sshd_config` has `PermitRootLogin prohibit-password` — key-only root login (no passwords)
- UFW has rule: `22/tcp ALLOW IN 10.0.1.0/24 # Coolify self-management SSH` — required so Coolify bridge can reach host SSH
- Coolify dashboard at `127.0.0.1:8000:8080`, Soketi realtime at `127.0.0.1:6001-6002`, pinned in `/data/coolify/source/docker-compose.prod.yml` via the patch in `scripts/fix-coolify-compose.py`

These three changes match the pattern that was on the old <SERVER_NAME> too (it was NOT the compromise vector — the npm supply chain was). Documented in detail in `your private incident notes`.

### Previous Server (<SERVER_NAME>) — DELETED <DATE>

| Setting       | Value                                                                                                                                                                                                                                                                    |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Status**    | **DELETED <DATE>** — instance + storage permanently removed from Lightsail account                                                                                                                                                                                   |
| **IP**        | <YOUR_SERVER_IP> (released)                                                                                                                                                                                                                                              |
| **Reason**    | Compromised via an unpatched remote-code-execution vulnerability in an app framework running in a container. Lesson: keep framework versions patched and treat any RCE advisory for your stack as urgent. Keep your own forensic root-cause notes in a private location. |
| **Retention** | Final cold-archive snapshot retained in Lightsail (forensic evidence preservation).                                                                                                                                                                                      |
| **Old key**   | Already invalid since the Lightsail regional default keypair was regenerated <DATE>.                                                                                                                                                                                 |

Full incident record at `your private incident notes`. Corrected root-cause record at `your private incident notes`.

### Coolify-Hosted Apps (7 live on <USER>-General as of <DATE>)

| App                   | URL         | Postgres / DB                                            | Migration outcome                                                                                                                                                                                                                                       |
| --------------------- | ----------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Example App**       | example.com | postgres:17-alpine (internal)                            | ✅ live <DATE>                                                                                                                                                                                                                                      |
| **Example App** | example.com | postgres:17-alpine (internal)                            | ✅ live <DATE> + 2 repo PRs upstream (ARG declarations, `--ignore-scripts`)                                                                                                                                                                         |
| **Maillayer**         | example.com | mongo:7 + redis:7.2-alpine (internal)                    | ✅ live <DATE> — **open-source repo version** (closed-source variant deferred)                                                                                                                                                                      |
| **example HQ**        | example.com | postgres:17-alpine (internal, `app_db` name preserved) | ✅ live <DATE> — repo renamed `<GITHUB_OWNER>/example-app` → `<GITHUB_OWNER>/example-HQ`; system-wide rename across .000 + repos                                                                                                                    |
| **example**           | example.com | none — fully stateless                                   | ✅ live <DATE> — fastest sprint (14 min wall clock)                                                                                                                                                                                                 |
| **example Website**   | example.com | none — fully static                                      | ✅ live <DATE> — **rebuilt from scratch** as 1:1 visual recreation of a reference app in Next.js 15 (patched) + Motion + Lenis + Tailwind v4                                                                                                                |
| **Example CRM**        | example.com | postgres:16 + redis (in compose stack)                   | ✅ deploying <DATE> — self-hosted twentyhq/twenty fork (`<GITHUB_OWNER>/Twenty`), Docker Compose build pack, project UUID `<RESOURCE_UUID>`, app UUID `<RESOURCE_UUID>`, deploy key id 7 (`example-deploy`). ENCRYPTION_KEY in 1Password. |

**All Postgres ports are internal-network-only** (`is_public: false`). Was a hardening miss on <SERVER_NAME>; fixed during migration.

**All 6 repos have `git push` → Coolify auto-deploy webhooks** wired (per G29 fix, retroactively applied to all repos).

---

## Coolify Dashboard

| Setting           | Value                                                                                                                                           |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **URL**           | https://example.com (via Cloudflare Tunnel — `coolify-user-general`, tunnel ID `<UUID>`, edge `fra03`)                                          |
| **Version**       | 4.1.0                                                                                                                                           |
| **Email**         | you@example.com                                                                                                                        |
| **Password**      | see `keys/coolify-credentials.env` (gitignored). 20+ char random in 1Password. Never commit. **2FA enabled (TOTP)**, backup codes in 1Password. |
| **API token**     | see `keys/coolify-credentials.env` `COOLIFY_NEW_TOKEN`. Scoped: root. Revoke after migration sprint completes.                                  |
| **Direct port**   | `127.0.0.1:8000` only on host. **Never** publicly bound — that was the architectural miss on <SERVER_NAME>.                                     |
| **Tunnel config** | `/etc/cloudflared/config.yml` on the VPS, single ingress rule `example.com → http://localhost:8000`. Realtime/Soketi tunnel not yet routed.     |

Migration-time API state captured in `your private incident notes` (gitignored):

- `COOLIFY_SERVER_UUID=<RESOURCE_UUID>` (localhost host server)
- `COOLIFY_DEFAULT_PROJECT_UUID=<RESOURCE_UUID>` (auto-created "My first project")

---

## SSH Quick Reference

### Connection Patterns

```bash
# Single command
ssh user@server "command"

# Multiple commands
ssh user@server "cmd1 && cmd2 && cmd3"

# Interactive (requires TTY)
ssh -t user@server "interactive-command"
```

### SSH Config (Local Machine)

Add to `~/.ssh/config` for easy access:

```
Host maillayer
    HostName <YOUR_SERVER_IP>
    User ubuntu
    IdentityFile ~/.ssh/<YOUR_SSH_KEY>.pem
```

Then connect with: `ssh maillayer`

---

## VPS Work Categories

| Category           | Examples                                         |
| ------------------ | ------------------------------------------------ |
| **Infrastructure** | Server setup, DNS, SSL/TLS, firewall, network    |
| **Deployments**    | App deploy, Docker, rolling updates, env vars    |
| **Security**       | SSH hardening, user management, fail2ban, audits |
| **Monitoring**     | Health checks, resources, logs, alerts           |

---

## Session-Based Workflow

For VPS work, use session files in `.claude/tasks/`:

1. **Create** `session-current.md` with planned tasks
2. **Document** each command before executing
3. **Capture** all outputs immediately
4. **Update** TodoWrite synchronously
5. **Commit** on completion with descriptive message
6. **Archive** to `session-XXX-description.md`

---

## Safety Protocols

### Before Any Operation

- Confirm target server
- Verify permissions
- Check current state
- Plan rollback if needed

### During Operations

- One command at a time
- Capture all outputs
- Verify each step

### After Operations

- Verify changes applied
- Check service health
- Review logs
- Update documentation

---

## Security Reminders

- Never store credentials in session files (reference this file instead)
- Never commit SSH keys (\*.pem files are gitignored)
- Use SSH keys, not passwords
- Sanitize logs before committing
- Follow principle of least privilege
