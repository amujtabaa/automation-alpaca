---
name: vps-deployment
description: "Application deployment workflows with Nginx reverse proxy, SSL certificates, and production configurations. Use when deploying apps, setting up reverse proxy, configuring SSL/HTTPS, or managing production deployments."
---

# VPS Deployment Guide

## Deployment Checklist

- [ ] Application built and tested
- [ ] Docker image ready
- [ ] Domain DNS configured
- [ ] Nginx reverse proxy set up
- [ ] SSL certificate obtained
- [ ] Firewall rules updated
- [ ] Monitoring configured

---

## 1. Nginx Installation & Setup

### Install Nginx

```bash
ssh root@server "apt update && apt install nginx -y"

# Start and enable
ssh root@server "systemctl enable nginx && systemctl start nginx"

# Verify
ssh root@server "systemctl status nginx"
ssh root@server "nginx -t"
```

### Basic Configuration

```bash
# Create site config
ssh root@server "cat > /etc/nginx/sites-available/myapp << 'EOF'
server {
    listen 80;
    server_name myapp.example.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOF"

# Enable site
ssh root@server "ln -sf /etc/nginx/sites-available/myapp /etc/nginx/sites-enabled/"

# Remove default
ssh root@server "rm -f /etc/nginx/sites-enabled/default"

# Test and reload
ssh root@server "nginx -t && systemctl reload nginx"
```

---

## 2. SSL with Let's Encrypt

### Install Certbot

```bash
ssh root@server "apt install certbot python3-certbot-nginx -y"
```

### Obtain Certificate

```bash
# Automatic (recommended)
ssh root@server "certbot --nginx -d myapp.example.com"

# Non-interactive
ssh root@server "certbot --nginx -d myapp.example.com --non-interactive --agree-tos -m you@example.com"
```

### Verify Auto-Renewal

```bash
# Test renewal
ssh root@server "certbot renew --dry-run"

# Check timer
ssh root@server "systemctl status certbot.timer"
```

### SSL-Enabled Nginx Config

```bash
ssh root@server "cat > /etc/nginx/sites-available/myapp << 'EOF'
server {
    listen 80;
    server_name myapp.example.com;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name myapp.example.com;

    ssl_certificate /etc/letsencrypt/live/myapp.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/myapp.example.com/privkey.pem;

    # SSL Security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF"

ssh root@server "nginx -t && systemctl reload nginx"
```

---

## 3. Docker Deployment Patterns

### Basic App Deployment

```yaml
# docker-compose.yml
version: "3.8"

services:
  app:
    image: myapp:latest
    container_name: myapp
    restart: unless-stopped
    ports:
      - "127.0.0.1:3000:3000" # Only localhost
    environment:
      - NODE_ENV=production
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### With Database

```yaml
version: "3.8"

services:
  app:
    image: myapp:latest
    container_name: myapp
    restart: unless-stopped
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      - DATABASE_URL=postgres://user:<PASSWORD>@<HOST>:<PORT>/<DB>
    depends_on:
      db:
        condition: service_healthy
    networks:
      - app-network

  db:
    image: postgres:15-alpine
    container_name: myapp-db
    restart: unless-stopped
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=myapp
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d myapp"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - app-network

networks:
  app-network:
    driver: bridge

volumes:
  postgres-data:
```

---

## 4. Nginx Proxy Manager (Alternative)

For simpler GUI-based management:

```yaml
# docker-compose.yml
version: "3.8"

services:
  npm:
    image: "jc21/nginx-proxy-manager:latest"
    container_name: nginx-proxy-manager
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "81:81" # Admin UI
    volumes:
      - ./data:/data
      - ./letsencrypt:/etc/letsencrypt
```

**Default login:** admin@example.com / changeme

---

## 5. Deployment Workflow

### Initial Deployment

```bash
# 1. Create app directory
ssh root@server "mkdir -p /opt/apps/myapp"

# 2. Copy docker-compose.yml
scp docker-compose.yml root@server:/opt/apps/myapp/

# 3. Copy environment file
scp .env.production root@server:/opt/apps/myapp/.env

# 4. Start application
ssh root@server "cd /opt/apps/myapp && docker compose up -d"

# 5. Check logs
ssh root@server "cd /opt/apps/myapp && docker compose logs -f"
```

### Update Deployment

```bash
# Pull latest and restart
ssh root@server "cd /opt/apps/myapp && docker compose pull && docker compose up -d"

# With zero-downtime (if using multiple replicas)
ssh root@server "cd /opt/apps/myapp && docker compose up -d --no-deps --scale app=2 && sleep 30 && docker compose up -d --no-deps --scale app=1"
```

### Rollback

```bash
# Stop current
ssh root@server "cd /opt/apps/myapp && docker compose down"

# Start previous version
ssh root@server "cd /opt/apps/myapp && docker compose up -d myapp:previous-tag"
```

---

## 6. Environment Variables

### Using .env File

```bash
# .env file on server
DATABASE_URL=postgres://user:<PASSWORD>@<HOST>:<PORT>/<DB>
SECRET_KEY=your-secret-key
NODE_ENV=production
```

### In Docker Compose

```yaml
services:
  app:
    env_file:
      - .env
    # Or inline
    environment:
      - NODE_ENV=production
```

---

## 7. Health Checks & Monitoring

### Basic Health Endpoint

```bash
# Test health endpoint
ssh root@server "curl -s http://localhost:3000/health"
```

### Simple Uptime Check Script

```bash
ssh root@server "cat > /opt/scripts/healthcheck.sh << 'EOF'
#!/bin/bash
if ! curl -sf http://localhost:3000/health > /dev/null; then
    echo \"App unhealthy, restarting...\"
    cd /opt/apps/myapp && docker compose restart app
fi
EOF"

ssh root@server "chmod +x /opt/scripts/healthcheck.sh"

# Add to crontab (every 5 minutes)
ssh root@server "(crontab -l 2>/dev/null; echo '*/5 * * * * /opt/scripts/healthcheck.sh') | crontab -"
```

---

## 8. Log Management

### View Logs

```bash
# Docker logs
ssh root@server "docker logs myapp --tail 100"
ssh root@server "docker logs myapp -f"

# Nginx access logs
ssh root@server "tail -f /var/log/nginx/access.log"

# Nginx error logs
ssh root@server "tail -f /var/log/nginx/error.log"
```

### Log Rotation

```bash
# Docker log rotation (daemon.json)
ssh root@server 'cat > /etc/docker/daemon.json << EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF'

ssh root@server "systemctl restart docker"
```

---

## 9. Backup Strategies

### Database Backup

```bash
# PostgreSQL backup
ssh root@server "docker exec myapp-db pg_dump -U user myapp > /backups/db_$(date +%Y%m%d).sql"

# Automated daily backup
ssh root@server "(crontab -l 2>/dev/null; echo '0 2 * * * docker exec myapp-db pg_dump -U user myapp > /backups/db_\$(date +\\%Y\\%m\\%d).sql') | crontab -"
```

### Volume Backup

```bash
# Backup Docker volume
ssh root@server "docker run --rm -v myapp_data:/data -v /backups:/backup alpine tar cvf /backup/data_$(date +%Y%m%d).tar /data"
```

---

## 10. Common Issues

### Port Already in Use

```bash
# Find process using port
ssh root@server "ss -tulpn | grep :3000"
ssh root@server "lsof -i :3000"
```

### Container Not Starting

```bash
# Check logs
ssh root@server "docker logs myapp"

# Check events
ssh root@server "docker events --since '1h'"
```

### Nginx 502 Bad Gateway

```bash
# Check if app is running
ssh root@server "curl -v http://localhost:3000"

# Check nginx config
ssh root@server "nginx -t"

# Check nginx error logs
ssh root@server "tail -20 /var/log/nginx/error.log"
```

---

## Sources

- [Nginx Reverse Proxy Setup](https://phoenixnap.com/kb/docker-nginx-reverse-proxy)
- [Docker Nginx Let's Encrypt](https://www.freecodecamp.org/news/docker-nginx-letsencrypt-easy-secure-reverse-proxy-40165ba3aee2/)
- [Nginx Proxy Manager](https://typevar.dev/articles/NginxProxyManager/nginx-proxy-manager)
- [VPS Docker Setup](https://dev.to/imzihad21/setting-up-a-vps-server-with-docker-nginx-proxy-manager-and-portainer-3hfk)
