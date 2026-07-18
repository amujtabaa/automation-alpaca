# Infra-ops reusable scripts

Battle-tested helper scripts from the <DATE> VPS incident response. Each is idempotent (running twice = no-op) and parameterized for reuse across future Coolify installs / migrations / incident responses.

## Coolify deploy / migration

| Script                    | Purpose                                                                                                                                                                                                                                                                                                                                                                                                                    | Idempotent?                             |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| `fix-coolify-compose.py`  | Pin Coolify dashboard (port 8000) + Soketi (6001, 6002) to `127.0.0.1` in `/data/coolify/source/docker-compose.prod.yml`. Closes the public-dashboard attack surface from the <DATE> incident.                                                                                                                                                                                                                         | Yes                                     |
| `harden-new-vps.sh`       | Apply post-provisioning hardening to a fresh Ubuntu Lightsail/EC2 host: apt upgrade, UFW (22/80/443 only), SSH key-only + no root + MaxAuthTries 3, fail2ban with sshd jail, unattended-upgrades with 04:00 auto-reboot. **Run on a fresh VPS before Coolify install.**                                                                                                                                                    | Yes                                     |
| `setup-github-webhook.sh` | Wire a GitHub repo → Coolify webhook for `git push`-triggered auto-deploy. Run AFTER creating an app via `/applications/private-deploy-key` — that endpoint sets up clone access only, no push notifications. Resolves app UUID by name → reads per-app `manual_webhook_secret_github` from Coolify → creates the GitHub webhook → fires a test ping → reports `last_response: active:200` on success. See gotcha **G29**. | Yes (returns existing hook id on retry) |

## Incident response / forensics

| Script             | Purpose                                                                                                                                                                                                                                                                    | Idempotent?                               |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `forensic-dump.sh` | Read-only forensic snapshot of a Linux host: process tree, network state, persistence mechanisms, authorized_keys, kernel modules, recently modified files, package install log, bash history. Produces `/tmp/forensics-<ts>.tar.gz`. Use during active incident response. | Yes (creates timestamped output each run) |
| `db-dump.sh`       | Dump every Postgres + Mongo + Redis + persistent volume on a Coolify host into `/tmp/dbdumps-<ts>.tar.gz`. Use BEFORE stopping a compromised instance, so app data is preserved separately from poisoned OS state.                                                         | Yes                                       |

## Usage patterns

All scripts are designed to be uploaded to the target VPS and run there via SSH. Standard pattern:

```bash
# scp the script to the target, run it via SSH
scp -i <key> ./scripts/forensic-dump.sh ubuntu@<host>:/tmp/fd.sh
ssh -i <key> ubuntu@<host> "chmod +x /tmp/fd.sh && bash /tmp/fd.sh 2>&1 | tail -20"

# pull the resulting tarball back
scp -i <key> ubuntu@<host>:/tmp/forensics-*.tar.gz ~/Downloads/
```

## See also

- `../coolify-hardening.md` — security playbook these scripts enforce
- `../coolify-automation.md` — REST API patterns + when to use which script
- `../coolify-gotchas.md` — Coolify v4 quirks discovered while writing/using these
- `../coolify-migration-runbook.md` — generic per-app migration runbook that uses these
- Keep your own incident record where these scripts are used
