---
name: infra-ops
description: Comprehensive infrastructure operations: VPS management, SSH, Docker, Coolify PaaS, Nginx deployments, SSL certificates, security hardening, email infrastructure, and cloud service setup. Use for server administration, deployments, DevOps, and production operations.
---

# Infrastructure Operations (infra-ops)

**TEMPLATE VERSION** - This skill ships with placeholders (`<YOUR_SERVER_IP>`, `example.com`, `<RESOURCE_UUID>`, `<PASSWORD>`, `<HOST>`, `<GITHUB_OWNER>`, etc.) in place of real infrastructure. Replace them with your own values before use. See "Getting Started" below.

Master skill for all infrastructure, deployment, and operations work. Use progressive disclosure - load only the files needed for your current task.

---

## Getting Started

This is a **template-based skill**. Before using in production, customize it for your infrastructure:

1. **Server access** (`vps-core.md`) - replace `<YOUR_SERVER_IP>` placeholders, SSH users, and Coolify dashboard URLs with your instances.
2. **Cloud credentials** - set your AWS S3 bucket/region/keys (`aws-s3.md`), Cloudflare API token and zone IDs (`cloudflare-setup.md`), and Google OAuth client (`google-oauth.md`).
3. **Resource IDs** - replace every `<RESOURCE_UUID>` / `<RESOURCE_ID>` / `<UUID>` with your real Coolify app/database UUIDs, and every `<PASSWORD>`/`<HOST>` in connection strings.
4. **SSH keys** - place your private keys in `keys/` (gitignored) and update references; ensure 600 permissions.
5. **Never commit** real `.env` files, PEM keys, or credentials to version control.

---

## Quick Reference: Which File to Load

### By Task Type

| Task                                  | Load These Files                                 |
| ------------------------------------- | ------------------------------------------------ |
| **SSH to server / server reference**  | `vps-core.md`                                    |
| **New server setup**                  | `vps-security.md` → `vps-security-setup.md`      |
| **Security hardening**                | `vps-security.md` → `vps-security-protection.md` |
| **Server maintenance / emergency**    | `vps-security-operations.md`                     |
| **Install/manage Docker**             | `vps-docker.md`                                  |
| **Deploy with Nginx + SSL**           | `vps-deployment.md`                              |
| **Deploy with Coolify (overview)**    | `coolify.md`                                     |
| **Coolify hardening (post-incident)** | `coolify-hardening.md`                           |
| **Coolify API automation**            | `coolify-automation.md`                          |
| **Coolify v4 gotchas / known quirks** | `coolify-gotchas.md`                             |
| **Per-app Coolify migration**         | `coolify-migration-runbook.md`                   |
| **Reusable infra scripts**            | `scripts/README.md`                              |
| **VPS-to-VPS migration**              | `migration/README.md`                            |
| **Next.js Docker deployment**         | `docker-deployment-guide.md`                     |
| **Generic Docker patterns**           | `docker-deployment-patterns.md`                  |
| **Email system setup**                | `email-infrastructure.md`                        |
| **Maillayer contacts API**            | `email-maillayer-contacts-api.md`                |
| **Cloudflare DNS/CDN**                | `cloudflare-setup.md`                            |
| **Google OAuth setup**                | `google-oauth.md`                                |
| **AWS S3 setup**                      | `aws-s3.md`                                      |
| **Database migrations**               | `database-migrations.md`                         |

---

## File Index

### VPS Core & Security

| File                         | Purpose                                             | Contains Credentials? |
| ---------------------------- | --------------------------------------------------- | --------------------- |
| `vps-core.md`                | Server inventory, SSH access, Coolify dashboard     | Template - customize  |
| `vps-security.md`            | Security philosophy, checklist, module overview     | No                    |
| `vps-security-setup.md`      | Initial setup, SSH hardening, auto-updates          | No                    |
| `vps-security-protection.md` | UFW firewall, Fail2ban, Cloudflare protection       | No                    |
| `vps-security-operations.md` | Maintenance, hardening script, emergency procedures | No                    |

### Docker & Deployment

| File                                | Purpose                                                                                             |
| ----------------------------------- | --------------------------------------------------------------------------------------------------- |
| `vps-docker.md`                     | Docker installation, compose, container management                                                  |
| `vps-deployment.md`                 | Nginx reverse proxy, SSL/Let's Encrypt, production configs                                          |
| `coolify.md`                        | Coolify PaaS overview: apps, databases, domains, troubleshooting                                    |
| `coolify-hardening.md`              | Hardening playbook (dashboard private, DBs internal, supply-chain checks)                           |
| `coolify-automation.md`             | REST API patterns + reusable scripts for programmatic provisioning                                  |
| `coolify-gotchas.md`                | Undocumented Coolify v4 quirks - read before any migration sprint                                   |
| `coolify-migration-runbook.md`      | Per-app migration template - copy and adapt for each app                                            |
| `scripts/README.md`                 | Index of reusable scripts (fix-coolify-compose.py, harden-new-vps.sh, forensic-dump.sh, db-dump.sh) |
| `migration/README.md`               | VPS-to-VPS migration plan (inventory, provision, cutover)                                           |
| `migration/cloudflare-mcp-setup.md` | Cloudflare MCP setup for DNS CRUD via Codex tool calls                                             |
| `docker-deployment-guide.md`        | Next.js 16 + Tailwind v4 + Prisma → Docker/Coolify                                                  |
| `docker-deployment-patterns.md`     | Generic Docker patterns for monorepos                                                               |

### Email Infrastructure

| File                              | Purpose                                         | Contains Credentials? |
| --------------------------------- | ----------------------------------------------- | --------------------- |
| `email-infrastructure.md`         | Architecture overview, stack comparison         | No                    |
| `email-maillayer-contacts-api.md` | Maillayer contacts API usage (subscribe, lists) | No                    |

### External Services

| File                     | Purpose                                    |
| ------------------------ | ------------------------------------------ |
| `cloudflare-setup.md`    | DNS, CDN, SSL, security & performance      |
| `google-oauth.md`        | OAuth setup for user authentication        |
| `aws-s3.md`              | S3 bucket setup for file storage           |
| `database-migrations.md` | Prisma migrations, production DB workflows |

### Skill Customization

| File               | Purpose                                                                                                                           |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| `CUSTOM-AGENTS.md` | Example AGENTS.md additions for infra work (session workflow, SSH conventions); copy relevant parts into your project's AGENTS.md |

### Keys (Subfolder)

| File                      | Purpose                                                           |
| ------------------------- | ----------------------------------------------------------------- |
| `keys/<YOUR_SSH_KEY>.pem` | SSH private key (e.g., AWS Lightsail). Gitignored - never commit. |

---

## Progressive Disclosure Guide

### Scenario: "Deploy a Next.js app to VPS"

**Load order:**

1. `vps-core.md` - Get server access info
2. `coolify.md` - If using Coolify
3. `docker-deployment-guide.md` - Next.js specific Docker setup
4. `cloudflare-setup.md` - DNS and CDN configuration

### Scenario: "Secure a new VPS"

**Load order:**

1. `vps-security.md` - Overview and checklist
2. `vps-security-setup.md` - SSH hardening, user creation
3. `vps-security-protection.md` - Firewall, Fail2ban

### Scenario: "Set up email system"

**Load order:**

1. `email-infrastructure.md` - Architecture overview
2. `email-maillayer-contacts-api.md` - Contacts API for list management

### Scenario: "Troubleshoot Coolify deployment"

**Load order:**

1. `coolify.md` - Full troubleshooting section
2. `vps-core.md` - SSH access to investigate

---

## Environment Variables Quick Reference

### CDN & DNS (Cloudflare)

```env
# No env vars - configuration in Cloudflare dashboard
```

### Authentication (Google OAuth)

```env
AUTH_GOOGLE_ID=your-client-id.apps.googleusercontent.com
AUTH_GOOGLE_SECRET=GOCSPX-your-secret
```

### File Storage (AWS S3)

```env
S3_BUCKET=your-bucket-name
S3_REGION=eu-central-1
S3_ACCESS_KEY=AKIA...
S3_SECRET_ACCESS_KEY=your-secret-key
S3_ENDPOINT=https://s3.eu-central-1.amazonaws.com
S3_PUBLIC_URL=https://your-bucket-name.s3.eu-central-1.amazonaws.com
```

### Database

```env
DATABASE_URL=postgresql://user:<PASSWORD>@<HOST>:<PORT>/<DB>
```

---

## Command Patterns

All VPS commands use SSH pattern:

```bash
# Single command
ssh user@server "command"

# Multiple commands
ssh user@server "cmd1 && cmd2 && cmd3"

# Interactive (requires TTY)
ssh -t user@server "interactive-command"
```

For server credentials and connection details, load `vps-core.md`.

---

## Session Workflow

For significant infrastructure work:

1. Create `.Codex/tasks/session-current.md`
2. Document planned tasks
3. Execute via SSH, capturing outputs
4. Update TodoWrite synchronously
5. Commit on completion
6. Archive to `session-XXX-description.md`

---

## Security Notes

- **Template files**: Files marked "Template - customize" contain placeholders that must be replaced with your actual infrastructure values before use.
- **Credentials**: Once customized, several files will hold sensitive data (AWS keys, passwords, server IPs). Keep your copy private.
- **SSH Keys**: Store in the `keys/` subfolder, which must be gitignored.
- **Never commit**: Raw passwords, API keys, or PEM files outside designated, gitignored locations.
- **Production readiness**: Do not use any file in production until all placeholders are replaced and tested.
