#!/bin/bash
# Hardening template for a new Lightsail / EC2 / Hetzner VPS
# Run as ubuntu user with NOPASSWD sudo.
set -e

echo "============================================================"
echo "VPS HARDENING - <USER>-General (<YOUR_SERVER_IP>)"
echo "Started: $(date -u)"
echo "============================================================"
echo ""

echo "[1/7] apt update + upgrade..."
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get -y upgrade -qq

echo ""
echo "[2/7] Install security packages..."
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ufw fail2ban unattended-upgrades apt-listchanges

echo ""
echo "[3/7] Configure UFW (default deny in, allow 22/80/443)..."
sudo ufw --force reset >/dev/null
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp comment 'SSH'
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw allow 443/tcp comment 'HTTPS'
sudo ufw --force enable
echo "UFW status:"
sudo ufw status verbose

echo ""
echo "[4/7] Harden SSH (key-only, no root login, MaxAuthTries 3)..."
sudo cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak
sudo sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^#*MaxAuthTries.*/MaxAuthTries 3/' /etc/ssh/sshd_config
sudo sed -i 's/^#*PermitEmptyPasswords.*/PermitEmptyPasswords no/' /etc/ssh/sshd_config
sudo sed -i 's/^#*X11Forwarding.*/X11Forwarding no/' /etc/ssh/sshd_config
# Also handle cloud-init's /etc/ssh/sshd_config.d/ overrides which Ubuntu 24.04 uses
if [ -f /etc/ssh/sshd_config.d/50-cloud-init.conf ]; then
  sudo sed -i 's/^PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config.d/50-cloud-init.conf
fi
# Validate before restart
if sudo sshd -t; then
  sudo systemctl restart ssh
  echo "SSH config validated and ssh restarted."
else
  echo "SSH config INVALID - restoring backup, not restarting."
  sudo cp /etc/ssh/sshd_config.bak /etc/ssh/sshd_config
  exit 1
fi
echo "Active SSH directives:"
sudo grep -E '^(PermitRootLogin|PasswordAuthentication|MaxAuthTries|PermitEmptyPasswords|X11Forwarding)' /etc/ssh/sshd_config

echo ""
echo "[5/7] Configure Fail2ban..."
sudo tee /etc/fail2ban/jail.local >/dev/null <<'EOF'
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5
banaction = ufw
backend = systemd
ignoreip = 127.0.0.1/8 ::1

[sshd]
enabled = true
port = ssh
filter = sshd
maxretry = 3
bantime = 1h
EOF
sudo systemctl enable fail2ban
sudo systemctl restart fail2ban
sleep 2
echo "Fail2ban status:"
sudo fail2ban-client status sshd

echo ""
echo "[6/7] Configure unattended-upgrades..."
sudo tee /etc/apt/apt.conf.d/20auto-upgrades >/dev/null <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
sudo tee /etc/apt/apt.conf.d/52unattended-upgrades-local >/dev/null <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
EOF
sudo systemctl enable unattended-upgrades
sudo systemctl restart unattended-upgrades

echo ""
echo "[7/7] Verify final state..."
echo ""
echo "--- Listening ports (should be 22 + 80 + 443 + DNS only) ---"
sudo ss -tlnp | grep LISTEN
echo ""
echo "--- UFW ---"
sudo ufw status numbered
echo ""
echo "--- SSH key-only enforced ---"
sudo grep -E '^(PermitRootLogin|PasswordAuthentication|MaxAuthTries)' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null
echo ""
echo "--- Fail2ban active ---"
sudo systemctl is-active fail2ban
echo ""
echo "--- Unattended-upgrades active ---"
sudo systemctl is-active unattended-upgrades
echo ""
echo "============================================================"
echo "HARDENING COMPLETE - $(date -u)"
echo "============================================================"
echo ""
echo "Next steps (not done by this script):"
echo "  - Install Coolify with PRIVATE dashboard (Cloudflare Tunnel or restrict-to-home-IP)"
echo "  - Enable Lightsail automatic snapshots from the AWS console"
echo "  - Add a deploy/ops user if you want one separate from 'ubuntu' (optional)"
