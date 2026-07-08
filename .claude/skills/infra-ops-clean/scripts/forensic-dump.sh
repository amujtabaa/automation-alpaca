#!/bin/bash
# Forensic data collection template: read-only snapshot of a Linux host during incident response
# Read-only collection - does not modify system state
# All commands wrapped in `|| true` so a failure on one item never aborts the dump.

set +e
TS=$(date +%Y%m%d-%H%M%S)
WORK=/tmp/forensics-$TS
mkdir -p "$WORK"

echo "[*] Collecting live state..."

# --- Live state (volatile, gone on reboot) ---
ps auxfww > "$WORK/ps-tree.txt" 2>&1 || true
ps -eo pid,ppid,user,etime,start_time,stat,cmd --sort=start_time > "$WORK/ps-by-starttime.txt" 2>&1 || true
ss -tunap > "$WORK/sockets-all.txt" 2>&1 || true
ss -tlnp > "$WORK/sockets-listening.txt" 2>&1 || true
ss -tunap state established > "$WORK/sockets-established.txt" 2>&1 || true
who -a > "$WORK/who.txt" 2>&1 || true
w > "$WORK/w.txt" 2>&1 || true
last -200 > "$WORK/last.txt" 2>&1 || true
lastb -50 2>/dev/null > "$WORK/lastb.txt" || true
uptime > "$WORK/uptime.txt" 2>&1 || true
free -h > "$WORK/free.txt" 2>&1 || true
df -h > "$WORK/df.txt" 2>&1 || true
mount > "$WORK/mount.txt" 2>&1 || true

# --- Network: interfaces, routes, firewall, tunnels ---
ip addr show > "$WORK/ip-addr.txt" 2>&1 || true
ip route show table all > "$WORK/ip-route-all.txt" 2>&1 || true
ip -d link show > "$WORK/ip-link-detailed.txt" 2>&1 || true
ip rule show > "$WORK/ip-rule.txt" 2>&1 || true
ip xfrm state > "$WORK/ip-xfrm-state.txt" 2>&1 || true
ip xfrm policy > "$WORK/ip-xfrm-policy.txt" 2>&1 || true

# Privileged - best effort, will fail silently if NOPASSWD not set
sudo -n iptables-save > "$WORK/iptables-save.txt" 2>&1 || true
sudo -n ip6tables-save > "$WORK/ip6tables-save.txt" 2>&1 || true
sudo -n nft list ruleset > "$WORK/nftables.txt" 2>&1 || true
sudo -n wg show > "$WORK/wireguard.txt" 2>&1 || true
sudo -n ls -la /etc/wireguard/ > "$WORK/wireguard-config-list.txt" 2>&1 || true
which tailscale > "$WORK/tailscale-which.txt" 2>&1 || true
sudo -n tailscale status > "$WORK/tailscale-status.txt" 2>&1 || true
sudo -n cat /proc/net/wireguard 2>/dev/null > "$WORK/proc-wireguard.txt" || true

# --- Kernel state ---
sudo -n lsmod > "$WORK/lsmod.txt" 2>&1 || true
uname -a > "$WORK/uname.txt" 2>&1 || true
sudo -n dmesg | tail -200 > "$WORK/dmesg-tail.txt" 2>&1 || true

# --- Auth & sessions ---
sudo -n cat /etc/passwd > "$WORK/passwd.txt" 2>&1 || cp /etc/passwd "$WORK/passwd.txt" 2>/dev/null || true
sudo -n cat /etc/shadow > "$WORK/shadow.txt" 2>&1 || true
sudo -n cat /etc/group > "$WORK/group.txt" 2>&1 || cp /etc/group "$WORK/group.txt" 2>/dev/null || true
sudo -n cat /etc/sudoers > "$WORK/sudoers.txt" 2>&1 || true
sudo -n ls -laR /etc/sudoers.d > "$WORK/sudoers-d.txt" 2>&1 || true
sudo -n cat /etc/ssh/sshd_config > "$WORK/sshd_config.txt" 2>&1 || true
sudo -n ls -la /etc/ssh/sshd_config.d/ > "$WORK/sshd_config_d.txt" 2>&1 || true

# --- SSH keys (the holy grail) ---
sudo -n find / -name "authorized_keys" -type f -exec ls -la {} \; -exec echo "--- CONTENT ---" \; -exec cat {} \; -exec echo "" \; 2>/dev/null > "$WORK/all-authorized-keys.txt" || true
cat /home/ubuntu/.ssh/authorized_keys 2>/dev/null > "$WORK/ubuntu-authorized-keys.txt" || true
sudo -n cat /root/.ssh/authorized_keys 2>/dev/null > "$WORK/root-authorized-keys.txt" || true

# --- Persistence mechanisms ---
crontab -l > "$WORK/crontab-ubuntu.txt" 2>&1 || true
sudo -n crontab -u root -l > "$WORK/crontab-root.txt" 2>&1 || true
sudo -n bash -c 'for u in $(cut -d: -f1 /etc/passwd); do echo "=== $u ==="; crontab -u "$u" -l 2>/dev/null; done' > "$WORK/crontab-all-users.txt" 2>&1 || true
sudo -n ls -laR /etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/cron.weekly /etc/cron.monthly /var/spool/cron > "$WORK/cron-all.txt" 2>&1 || true
sudo -n cat /etc/crontab > "$WORK/etc-crontab.txt" 2>&1 || true

systemctl list-timers --all --no-pager > "$WORK/systemd-timers.txt" 2>&1 || true
systemctl list-units --type=service --state=running --no-pager > "$WORK/systemd-services-running.txt" 2>&1 || true
sudo -n ls -la /etc/systemd/system /usr/lib/systemd/system /etc/systemd/user > "$WORK/systemd-units-listing.txt" 2>&1 || true
sudo -n find /etc/systemd /lib/systemd -name "*.service" -mtime -180 -ls > "$WORK/systemd-recent-services.txt" 2>&1 || true

# Classic persistence files
sudo -n cat /etc/rc.local > "$WORK/rc.local.txt" 2>&1 || true
sudo -n cat /etc/ld.so.preload > "$WORK/ld.so.preload.txt" 2>&1 || true
sudo -n ls -la /etc/profile.d/ > "$WORK/profile.d-listing.txt" 2>&1 || true
sudo -n cat /root/.bashrc /root/.bash_profile /root/.profile > "$WORK/root-shell-rc.txt" 2>&1 || true
sudo -n cat /home/ubuntu/.bashrc /home/ubuntu/.bash_profile /home/ubuntu/.profile > "$WORK/ubuntu-shell-rc.txt" 2>&1 || true
sudo -n find /etc/pam.d -type f -exec md5sum {} \; > "$WORK/pam.d-md5.txt" 2>&1 || true

# --- Common malware drop locations ---
ls -laR /tmp 2>&1 > "$WORK/tmp-listing.txt" || true
ls -laR /var/tmp 2>&1 > "$WORK/var-tmp-listing.txt" || true
ls -laR /dev/shm 2>&1 > "$WORK/dev-shm-listing.txt" || true
sudo -n ls -laR /opt > "$WORK/opt-listing.txt" 2>&1 || true
sudo -n ls -laR /usr/local/bin /usr/local/sbin > "$WORK/usr-local-bin-listing.txt" 2>&1 || true
sudo -n ls -la /root > "$WORK/root-home-listing.txt" 2>&1 || true
ls -la /home > "$WORK/home-listing.txt" 2>&1 || true

# --- Shell history ---
sudo -n cat /root/.bash_history > "$WORK/root-bash-history.txt" 2>&1 || true
cat /home/ubuntu/.bash_history > "$WORK/ubuntu-bash-history.txt" 2>&1 || true
sudo -n find /home /root -name ".bash_history" -ls 2>/dev/null > "$WORK/all-bash-history-listing.txt" || true
sudo -n find /home /root -name ".*_history" -exec ls -la {} \; -exec echo "--- $f ---" \; -exec cat {} \; 2>/dev/null > "$WORK/all-shell-histories.txt" || true

# --- Logs ---
sudo -n cp /var/log/auth.log "$WORK/auth.log" 2>/dev/null || true
sudo -n ls -la /var/log/auth.log* > "$WORK/auth-log-listing.txt" 2>&1 || true
sudo -n grep -E "Accepted|sudo:|Failed password|invalid|root" /var/log/auth.log 2>/dev/null > "$WORK/auth-interesting.txt" || true
sudo -n journalctl -u ssh --since "YYYY-MM-DD" --no-pager 2>/dev/null > "$WORK/journalctl-ssh.txt" || true
sudo -n journalctl --since "YYYY-MM-DD" --until "YYYY-MM-DD" --no-pager 2>/dev/null > "$WORK/journalctl-around-incident.txt" || true

# --- Recently modified files (catch dropped binaries / modified configs) ---
sudo -n find /etc /usr/local /opt /var/spool /root /home -type f -mtime -30 -ls 2>/dev/null > "$WORK/files-modified-30d.txt" || true
sudo -n find /bin /sbin /usr/bin /usr/sbin -type f -mtime -180 -ls 2>/dev/null > "$WORK/system-binaries-modified-180d.txt" || true
sudo -n find / -type f -mtime -1 -not -path "/proc/*" -not -path "/sys/*" -not -path "/var/lib/docker/*" -not -path "/var/log/*" -not -path "/tmp/forensics-*" -ls 2>/dev/null > "$WORK/files-modified-1d.txt" || true

# --- Package state ---
dpkg -l > "$WORK/dpkg-l.txt" 2>&1 || true
sudo -n grep " install " /var/log/dpkg.log 2>/dev/null > "$WORK/dpkg-installs.txt" || true
sudo -n grep " install " /var/log/dpkg.log.1 2>/dev/null >> "$WORK/dpkg-installs.txt" || true
which wg tailscale ncat socat a cryptominer masscan nmap > "$WORK/suspicious-tools.txt" 2>&1 || true

# --- Docker ---
docker ps -a > "$WORK/docker-ps-a.txt" 2>&1 || sudo -n docker ps -a > "$WORK/docker-ps-a.txt" 2>&1 || true
docker images > "$WORK/docker-images.txt" 2>&1 || sudo -n docker images > "$WORK/docker-images.txt" 2>&1 || true
docker volume ls > "$WORK/docker-volumes.txt" 2>&1 || sudo -n docker volume ls > "$WORK/docker-volumes.txt" 2>&1 || true
docker network ls > "$WORK/docker-networks.txt" 2>&1 || sudo -n docker network ls > "$WORK/docker-networks.txt" 2>&1 || true

# --- Attacker process deep-dive (PIDs of attacker root sessions) ---
# Find PIDs of any sshd process owned by root with parent sshd (the live root sessions)
sudo -n bash -c 'for pid in $(ps -eo pid,user,cmd | grep "sshd: root" | grep -v grep | awk "{print \$1}"); do echo "=== PID $pid ==="; ls -la /proc/$pid/exe /proc/$pid/cwd 2>/dev/null; echo "--- cmdline:"; tr "\0" " " < /proc/$pid/cmdline 2>/dev/null; echo ""; echo "--- env:"; tr "\0" "\n" < /proc/$pid/environ 2>/dev/null | head -20; echo "--- open files (top 20):"; ls -la /proc/$pid/fd/ 2>/dev/null | head -25; echo ""; done' > "$WORK/attacker-process-deep-dive.txt" 2>&1 || true

# --- Tar it up ---
echo "[*] Compressing..."
cd /tmp
tar czf "forensics-$TS.tar.gz" "forensics-$TS/" 2>&1
rm -rf "forensics-$TS/"
ls -la "/tmp/forensics-$TS.tar.gz"
echo ""
echo "DONE: /tmp/forensics-$TS.tar.gz"
