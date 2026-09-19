# Load Balancer Command Cheatsheet
## Quick Reference for HAProxy & Nginx Operations

### 🚀 Emergency Quick Commands

```bash
# IMMEDIATE HEALTH CHECK
systemctl status nginx haproxy
curl -I http://localhost/
netstat -tlnp | grep -E ":80|:443"

# GRACEFUL RELOAD (ZERO DOWNTIME)
sudo systemctl reload nginx
sudo systemctl reload haproxy

# CONFIGURATION TEST (BEFORE RELOAD)
sudo nginx -t && sudo haproxy -c -f /etc/haproxy/haproxy.cfg
```

---

## 🔧 HAProxy Quick Commands

### Essential Operations
| Operation | Command |
|-----------|---------|
| **Test Config** | `haproxy -f /etc/haproxy/haproxy.cfg -c` |
| **Graceful Reload** | `systemctl reload haproxy` |
| **Stats Socket** | `echo "show info" \| socat stdio /var/run/haproxy/admin.sock` |
| **Disable Server** | `echo "disable server backend/server1" \| socat stdio /var/run/haproxy/admin.sock` |
| **Enable Server** | `echo "enable server backend/server1" \| socat stdio /var/run/haproxy/admin.sock` |

### Stats Socket Commands
```bash
# Server Management
echo "show stat" | socat stdio /var/run/haproxy/admin.sock
echo "show servers state" | socat stdio /var/run/haproxy/admin.sock
echo "set weight backend/server1 50" | socat stdio /var/run/haproxy/admin.sock

# Information
echo "show info" | socat stdio /var/run/haproxy/admin.sock
echo "show backend" | socat stdio /var/run/haproxy/admin.sock
echo "show frontend" | socat stdio /var/run/haproxy/admin.sock
```

---

## 📊 Nginx Quick Commands

### Essential Operations
| Operation | Command |
|-----------|---------|
| **Test Config** | `nginx -t` |
| **Graceful Reload** | `nginx -s reload` |
| **Show Config** | `nginx -T` |
| **Status Check** | `curl http://localhost/nginx_status` |
| **Process Info** | `ps aux \| grep nginx` |

### Signals
```bash
# Graceful operations
nginx -s reload    # Reload config
nginx -s quit      # Graceful shutdown
nginx -s stop      # Fast shutdown
nginx -s reopen    # Reopen logs
```

---

## 🔍 Monitoring One-Liners

### Traffic Monitoring
```bash
# Real-time requests (Nginx)
tail -f /var/log/nginx/access.log | awk '{print $1, $7, $9}'

# Error monitoring (HAProxy)
tail -f /var/log/haproxy.log | grep -E "(5[0-9]{2}|4[0-9]{2})"

# Connection count
watch -n 1 'netstat -an | grep :80 | wc -l'
```

### Performance Monitoring
```bash
# Quick load check
uptime && ps aux | grep -E "(nginx|haproxy)" | grep -v grep

# Memory usage
ps aux | grep -E "(nginx|haproxy)" | awk '{sum+=$6} END {print "Memory: " sum " KB"}'

# Connection status
ss -tuln | grep -E ":80|:443|:8080"
```

---

## 🧪 Testing Commands

### Connectivity Tests
```bash
# Backend connectivity
nc -zv backend1 8080
curl -I http://backend1:8080/health

# Load balancer response
curl -I http://localhost/
curl -w "%{http_code} %{time_total}\n" -o /dev/null -s http://localhost/
```

### Load Testing
```bash
# Quick load test
ab -n 100 -c 10 http://localhost/
curl -s http://localhost/ | grep -o "server[0-9]*" | sort | uniq -c

# Sustained testing
for i in {1..10}; do curl -s http://localhost/ | grep server; sleep 1; done
```

---

## 🚨 Troubleshooting Commands

### Common Issues
```bash
# Check if service is running
systemctl status nginx haproxy
pgrep -f nginx && echo "Nginx running" || echo "Nginx not running"

# Port conflicts
netstat -tlnp | grep -E ":80|:443"
lsof -i :80,443

# Configuration errors
nginx -t 2>&1 | head -5
haproxy -c -f /etc/haproxy/haproxy.cfg 2>&1 | head -5
```

### Log Analysis
```bash
# Last 50 errors
tail -50 /var/log/nginx/error.log
journalctl -u haproxy --no-pager -n 50

# Status code distribution
awk '{print $9}' /var/log/nginx/access.log | sort | uniq -c
grep "HTTP/1.1" /var/log/haproxy.log | awk '{print $10}' | sort | uniq -c
```

---

## ⚡ Performance Commands

### Resource Usage
```bash
# CPU usage
top -p $(pgrep -f nginx | tr '\n' ',' | sed 's/,$//')
ps -C haproxy -o pid,pcpu,pmem,cmd

# File descriptors
ls /proc/$(cat /var/run/nginx.pid)/fd | wc -l
echo "show info" | socat stdio /var/run/haproxy/admin.sock | grep -i conn
```

### Network Performance
```bash
# Connection states
netstat -an | awk '/tcp/ {print $6}' | sort | uniq -c
ss -s  # Socket statistics summary

# Bandwidth usage
iftop -i eth0 -n -P  # Network interface monitoring
```

---

## 🔒 Security Commands

### SSL/TLS Testing
```bash
# Certificate check
openssl s_client -connect localhost:443 -servername example.com
openssl x509 -in /etc/ssl/certs/example.com.crt -dates -noout

# SSL configuration test
testssl.sh https://localhost
nmap --script ssl-enum-ciphers -p 443 localhost
```

### Security Monitoring
```bash
# Rate limiting check
grep -E "(limit_req|rate limit)" /var/log/nginx/error.log | tail -10
echo "show table" | socat stdio /var/run/haproxy/admin.sock

# DDoS monitoring
awk '{print $1}' /var/log/nginx/access.log | sort | uniq -c | sort -nr | head -10
```

---

## 🔄 Configuration Management

### Backup & Restore
```bash
# Backup configurations
cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%Y%m%d)
cp /etc/haproxy/haproxy.cfg /etc/haproxy/haproxy.cfg.backup.$(date +%Y%m%d)

# Compare configurations
diff /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup
```

### Deployment Commands
```bash
# Safe deployment process
nginx -t && systemctl reload nginx || echo "Deployment failed"
haproxy -c -f /etc/haproxy/haproxy.cfg && systemctl reload haproxy || echo "Deployment failed"

# Rollback
cp /etc/nginx/nginx.conf.backup /etc/nginx/nginx.conf && systemctl reload nginx
```

---

## 🐛 Debug Mode

### Enable Debug Logging
```bash
# Nginx debug (compile with --with-debug)
nginx -s stop
nginx -g "error_log /var/log/nginx/debug.log debug;"

# HAProxy debug
haproxy -f /etc/haproxy/haproxy.cfg -db  # Foreground debug mode
```

### Process Monitoring
```bash
# Trace system calls
strace -p $(pgrep nginx | head -1) -e trace=network
strace -p $(pgrep haproxy) -e trace=network

# Monitor file access
lsof -p $(pgrep nginx | head -1)
ls -la /proc/$(pgrep haproxy)/fd
```

---

## 📞 Emergency Response

### Service Recovery
```bash
# Force restart services
systemctl restart nginx haproxy
pkill -9 nginx && systemctl start nginx  # Force kill and restart

# Bypass load balancer (emergency)
iptables -t nat -A OUTPUT -p tcp --dport 80 -j DNAT --to-destination backend1:8080
```

### Health Check Script
```bash
#!/bin/bash
# emergency-check.sh
echo "=== EMERGENCY HEALTH CHECK ==="
echo "Time: $(date)"
systemctl is-active nginx haproxy
curl -I -m 5 http://localhost/ 2>/dev/null | head -1
echo "Active connections: $(netstat -an | grep :80 | wc -l)"
echo "Load: $(uptime | awk '{print $10, $11, $12}')"
```

---

## 📋 Monitoring Aliases

Add these to your `.bashrc` or `.profile`:

```bash
# Load balancer aliases
alias lb-status='systemctl status nginx haproxy'
alias lb-reload='nginx -t && haproxy -c -f /etc/haproxy/haproxy.cfg && systemctl reload nginx haproxy'
alias lb-test='curl -I http://localhost/ && curl -I https://localhost/'
alias lb-logs='tail -f /var/log/nginx/access.log /var/log/haproxy.log'
alias lb-errors='tail -f /var/log/nginx/error.log | grep -E "(error|warn)"'
alias lb-connections='watch -n 1 "netstat -an | grep -E \":80|:443\" | wc -l"'
```

---

**💡 Pro Tip**: Save this cheatsheet to your server as `/usr/local/bin/lb-cheat` and make it executable for quick reference!

```bash
sudo wget -O /usr/local/bin/lb-cheat https://raw.githubusercontent.com/your-repo/COMMAND_CHEATSHEET.md
sudo chmod +x /usr/local/bin/lb-cheat
```