# Lab 1: Basic Reverse Proxy Setup with Nginx
## Understanding Load Balancer Fundamentals Through Hands-on Implementation

### Lab Overview
Build a basic reverse proxy setup using Nginx to understand fundamental load balancing concepts. This lab introduces Layer 7 load balancing, health checks, and basic monitoring.

### Duration: 45 minutes

---

## Prerequisites

### Required Software
- Docker and Docker Compose
- curl or HTTPie for testing
- Text editor (VS Code, vim, etc.)

### Knowledge Requirements
- Basic understanding of HTTP protocol
- Familiarity with command line operations
- Basic Docker concepts

---

## Lab Architecture

```
Client (curl) → Nginx Load Balancer → Backend Services
                      |                     |
                      |                     ├── Web Server 1 (Port 8001)
                      |                     ├── Web Server 2 (Port 8002)
                      └─ (Port 80)          └── Web Server 3 (Port 8003)
```

---

## Step 1: Environment Setup

### 1.1 Create Lab Directory
```bash
mkdir -p ~/load-balancer-labs/lab01
cd ~/load-balancer-labs/lab01
```

### 1.2 Create Backend Application
Create a simple Python web application to serve as backend services:

```python
# app.py
from flask import Flask, request, jsonify
import os
import socket
import time

app = Flask(__name__)

SERVER_NAME = os.environ.get('SERVER_NAME', socket.gethostname())
PORT = os.environ.get('PORT', '8000')

@app.route('/')
def home():
    return jsonify({
        'server': SERVER_NAME,
        'port': PORT,
        'timestamp': time.time(),
        'client_ip': request.remote_addr,
        'user_agent': request.headers.get('User-Agent'),
        'path': request.path
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'server': SERVER_NAME,
        'timestamp': time.time()
    })

@app.route('/slow')
def slow():
    # Simulate slow response for testing
    time.sleep(2)
    return jsonify({
        'server': SERVER_NAME,
        'message': 'This was a slow response',
        'timestamp': time.time()
    })

@app.route('/error')
def error():
    # Simulate server error for testing
    return jsonify({'error': 'Simulated server error'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(PORT), debug=True)
```

### 1.3 Create Requirements File
```
# requirements.txt
Flask==2.3.3
```

### 1.4 Create Dockerfile for Backend
```dockerfile
# Dockerfile.backend
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .

EXPOSE 8000

CMD ["python", "app.py"]
```

---

## Step 2: Nginx Load Balancer Configuration

### 2.1 Basic Load Balancer Configuration
Create Nginx configuration for basic round-robin load balancing:

```nginx
# nginx.conf
events {
    worker_connections 1024;
}

http {
    # Upstream block defines the backend servers
    upstream backend_servers {
        server web1:8000;
        server web2:8000;
        server web3:8000;
    }
    
    # Basic logging
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;
    
    server {
        listen 80;
        server_name localhost;
        
        # Health check endpoint for load balancer itself
        location /nginx-health {
            access_log off;
            return 200 "nginx healthy\n";
            add_header Content-Type text/plain;
        }
        
        # Proxy all requests to backend
        location / {
            proxy_pass http://backend_servers;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Basic timeout settings
            proxy_connect_timeout 5s;
            proxy_send_timeout 10s;
            proxy_read_timeout 10s;
        }
        
        # Status endpoint showing nginx stats
        location /nginx-status {
            stub_status on;
            access_log off;
            allow 127.0.0.1;
            allow 172.16.0.0/12;  # Docker networks
            deny all;
        }
    }
}
```

### 2.2 Docker Compose Configuration
```yaml
# docker-compose.yml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./logs:/var/log/nginx
    depends_on:
      - web1
      - web2
      - web3
    networks:
      - loadbalancer_net

  web1:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      - SERVER_NAME=web1
      - PORT=8000
    networks:
      - loadbalancer_net

  web2:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      - SERVER_NAME=web2
      - PORT=8000
    networks:
      - loadbalancer_net

  web3:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      - SERVER_NAME=web3
      - PORT=8000
    networks:
      - loadbalancer_net

networks:
  loadbalancer_net:
    driver: bridge
```

---

## Step 3: Testing Basic Load Balancing

### 3.1 Start the Environment
```bash
# Create logs directory
mkdir logs

# Start all services
docker-compose up -d

# Verify all containers are running
docker-compose ps
```

### 3.2 Test Round-Robin Distribution
```bash
# Test multiple requests to see round-robin behavior
echo "Testing round-robin distribution:"
for i in {1..9}; do
  curl -s http://localhost/ | jq '.server'
done
```

Expected output should show requests distributed across web1, web2, and web3.

### 3.3 Test Health Endpoints
```bash
# Test nginx health
curl http://localhost/nginx-health

# Test backend health
curl http://localhost/health

# Check nginx status
curl http://localhost/nginx-status
```

### 3.4 Verify Headers
```bash
# Check forwarded headers
curl -H "X-Custom-Header: TestValue" http://localhost/ | jq '.'
```

---

## Step 4: Advanced Configuration

### 4.1 Add Health Checks and Failover
Update nginx.conf to include health checks:

```nginx
# nginx-advanced.conf
events {
    worker_connections 1024;
}

http {
    # Upstream with health checks and weights
    upstream backend_servers {
        server web1:8000 weight=3 max_fails=3 fail_timeout=30s;
        server web2:8000 weight=2 max_fails=3 fail_timeout=30s;
        server web3:8000 weight=1 max_fails=3 fail_timeout=30s;
    }
    
    # Enable response caching for better performance
    proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=my_cache:10m inactive=60m;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;
    
    server {
        listen 80;
        server_name localhost;
        
        location /nginx-health {
            access_log off;
            return 200 "nginx healthy\n";
            add_header Content-Type text/plain;
        }
        
        # API endpoints with rate limiting
        location /api/ {
            limit_req zone=api_limit burst=5 nodelay;
            proxy_pass http://backend_servers;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
        
        # Static content with caching
        location /static/ {
            proxy_cache my_cache;
            proxy_cache_valid 200 302 10m;
            proxy_cache_valid 404 1m;
            add_header X-Cache-Status $upstream_cache_status;
            
            proxy_pass http://backend_servers;
        }
        
        # Default location
        location / {
            # Add custom headers for tracking
            add_header X-Load-Balancer "nginx-lab";
            add_header X-Backend-Server $upstream_addr;
            
            proxy_pass http://backend_servers;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeout configurations
            proxy_connect_timeout 5s;
            proxy_send_timeout 10s;
            proxy_read_timeout 10s;
            
            # Retry configuration
            proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;
            proxy_next_upstream_tries 2;
        }
    }
}
```

### 4.2 Update Docker Compose for Advanced Features
```yaml
# docker-compose-advanced.yml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx-advanced.conf:/etc/nginx/nginx.conf:ro
      - ./logs:/var/log/nginx
      - nginx_cache:/var/cache/nginx
    depends_on:
      - web1
      - web2
      - web3
    networks:
      - loadbalancer_net

  web1:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      - SERVER_NAME=web1
      - PORT=8000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - loadbalancer_net

  web2:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      - SERVER_NAME=web2
      - PORT=8000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - loadbalancer_net

  web3:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      - SERVER_NAME=web3
      - PORT=8000
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - loadbalancer_net

  # Add monitoring container
  monitoring:
    image: nginx:alpine
    ports:
      - "8080:80"
    volumes:
      - ./monitoring.conf:/etc/nginx/nginx.conf:ro
      - ./logs:/var/log/nginx:ro
    networks:
      - loadbalancer_net

volumes:
  nginx_cache:

networks:
  loadbalancer_net:
    driver: bridge
```

---

## Step 5: Testing Failure Scenarios

### 5.1 Simulate Server Failure
```bash
# Stop one backend server
docker-compose stop web2

# Test that load balancer continues working
for i in {1..6}; do
  curl -s http://localhost/ | jq '.server'
done

# Start the server back up
docker-compose start web2
```

### 5.2 Test Rate Limiting
```bash
# Test rate limiting (if using advanced config)
for i in {1..15}; do
  curl -s -o /dev/null -w "%{http_code}\n" http://localhost/api/
  sleep 0.1
done
```

### 5.3 Test Error Handling
```bash
# Test error endpoint
curl http://localhost/error

# Test slow endpoint
time curl http://localhost/slow
```

---

## Step 6: Monitoring and Observability

### 6.1 Create Simple Monitoring Dashboard
```html
<!-- monitoring/index.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Load Balancer Monitoring</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .metric { margin: 10px 0; padding: 10px; background: #f0f0f0; }
        .healthy { background: #d4edda; }
        .unhealthy { background: #f8d7da; }
    </style>
</head>
<body>
    <h1>Load Balancer Status</h1>
    
    <div class="metric">
        <h2>Nginx Status</h2>
        <pre id="nginx-status"></pre>
    </div>
    
    <div class="metric">
        <h2>Backend Health</h2>
        <div id="backend-health"></div>
    </div>
    
    <script>
        // Simple JavaScript to fetch status
        async function updateStatus() {
            try {
                const response = await fetch('/nginx-status');
                const text = await response.text();
                document.getElementById('nginx-status').textContent = text;
            } catch (e) {
                document.getElementById('nginx-status').textContent = 'Error fetching status';
            }
        }
        
        updateStatus();
        setInterval(updateStatus, 5000);
    </script>
</body>
</html>
```

### 6.2 Log Analysis Script
```bash
#!/bin/bash
# analyze-logs.sh

echo "=== Nginx Access Log Analysis ==="
echo "Total requests:"
cat logs/access.log | wc -l

echo "Requests per backend server:"
grep -o 'upstream: [^,]*' logs/access.log | sort | uniq -c

echo "Response codes:"
awk '{print $9}' logs/access.log | sort | uniq -c

echo "Recent errors:"
grep -i error logs/error.log | tail -5
```

---

## Step 7: Performance Testing

### 7.1 Load Testing Script
```bash
#!/bin/bash
# load-test.sh

echo "Starting load test..."

# Install apache bench if not available
command -v ab >/dev/null 2>&1 || { echo "Installing apache2-utils..."; sudo apt-get install apache2-utils; }

# Basic load test
echo "=== Basic Load Test ==="
ab -n 1000 -c 10 http://localhost/

# Test with custom headers
echo "=== Custom Headers Test ==="
ab -n 500 -c 5 -H "X-Test-Client: LoadTest" http://localhost/

# Test slow endpoint
echo "=== Slow Endpoint Test ==="
ab -n 50 -c 2 http://localhost/slow

echo "Load test complete. Check logs/access.log for details."
```

### 7.2 Performance Analysis
```python
#!/usr/bin/env python3
# analyze-performance.py

import re
import statistics
from collections import defaultdict

def analyze_nginx_logs(log_file):
    response_times = []
    status_codes = defaultdict(int)
    backend_distribution = defaultdict(int)
    
    with open(log_file, 'r') as f:
        for line in f:
            # Parse nginx access log format
            # You may need to adjust the regex based on your log format
            match = re.search(r'(\d+\.\d+).*"(\d{3})".*upstream: ([^,]*)', line)
            if match:
                response_time, status_code, backend = match.groups()
                response_times.append(float(response_time))
                status_codes[status_code] += 1
                backend_distribution[backend] += 1
    
    print("=== Performance Analysis ===")
    print(f"Total requests: {len(response_times)}")
    print(f"Average response time: {statistics.mean(response_times):.3f}s")
    print(f"Median response time: {statistics.median(response_times):.3f}s")
    print(f"95th percentile: {sorted(response_times)[int(0.95 * len(response_times))]:.3f}s")
    
    print("\n=== Status Code Distribution ===")
    for code, count in status_codes.items():
        print(f"{code}: {count}")
    
    print("\n=== Backend Distribution ===")
    for backend, count in backend_distribution.items():
        print(f"{backend}: {count}")

if __name__ == "__main__":
    analyze_nginx_logs("logs/access.log")
```

---

## Step 8: Cleanup

### 8.1 Stop and Remove Containers
```bash
# Stop all services
docker-compose down

# Remove images (optional)
docker-compose down --rmi all

# Remove volumes (optional)
docker-compose down --volumes
```

### 8.2 Save Configuration for Future Use
```bash
# Archive the lab for reference
tar -czf lab01-nginx-loadbalancer.tar.gz .
```

---

## Lab Exercises

### Exercise 1: Configuration Modification
Modify the nginx configuration to:
1. Add a fourth backend server
2. Configure weighted round-robin with different weights
3. Add custom health check intervals

### Exercise 2: Advanced Routing
Implement path-based routing:
- Route `/api/*` requests to API servers
- Route `/static/*` requests to static file servers
- Route everything else to general application servers

### Exercise 3: Security Features
Add security features to your configuration:
1. Rate limiting for different paths
2. IP-based access control
3. Request size limits
4. Custom error pages

### Exercise 4: Monitoring Enhancement
Create a comprehensive monitoring setup:
1. Real-time dashboard showing server health
2. Log rotation and archival
3. Performance metrics collection
4. Alerting for failed servers

---

## Troubleshooting Guide

### Common Issues

#### 1. Connection Refused Errors
```bash
# Check if all containers are running
docker-compose ps

# Check logs
docker-compose logs nginx
docker-compose logs web1
```

#### 2. Load Balancing Not Working
```bash
# Verify nginx configuration
docker-compose exec nginx nginx -t

# Check upstream configuration
curl http://localhost/nginx-status
```

#### 3. High Response Times
```bash
# Monitor resource usage
docker stats

# Check application logs
docker-compose logs web1 | grep -i error
```

---

## Key Takeaways

1. **Layer 7 Load Balancing**: Understanding how application-layer routing works
2. **Health Checks**: Importance of monitoring backend server health
3. **Failover**: How load balancers handle server failures
4. **Configuration Management**: Best practices for maintaining load balancer configs
5. **Monitoring**: Essential metrics and logging for load balancer operations

---

## Next Steps

After completing this lab, you should be able to:
- Understand basic load balancer operation
- Configure Nginx for reverse proxy and load balancing
- Implement health checks and failover
- Monitor load balancer performance
- Troubleshoot common issues

Proceed to Lab 2 where you'll implement consistent hashing algorithms for more advanced load balancing scenarios.