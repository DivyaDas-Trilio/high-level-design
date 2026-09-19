# Lab 3: DevOps Pipeline for Load Balancer Deployment
## Build Complete CI/CD Pipeline with Infrastructure as Code

### Lab Overview
Create a production-ready DevOps pipeline that automates load balancer infrastructure provisioning, configuration management, and deployment using modern DevOps practices. This lab demonstrates enterprise-level automation for staff/principal engineers.

### Duration: 120 minutes

---

## Prerequisites

### Required Tools
- **Docker & Docker Compose**: For local development and testing
- **Terraform**: Infrastructure as Code provisioning
- **Ansible**: Configuration management
- **Git**: Version control
- **AWS CLI**: Cloud resource management (or equivalent cloud provider)
- **kubectl & Helm**: Kubernetes management
- **GitLab or GitHub**: CI/CD platform

### Knowledge Requirements
- Basic understanding of Git workflows
- Familiarity with cloud platforms (AWS/GCP/Azure)
- Understanding of containerization concepts
- Basic knowledge of YAML and HCL syntax

---

## Lab Architecture

```
Developer → Git Repository → CI/CD Pipeline → Infrastructure Deployment
    ↓             ↓              ↓                     ↓
Code Changes → Automated Tests → Infrastructure → Load Balancer Config
                    ↓              Provisioning           ↓
                Validation          (Terraform)     Configuration Management
                Security Scan           ↓              (Ansible)
                    ↓              Cloud Resources         ↓
                Approval Gate           ↓           Automated Deployment
                    ↓         Load Balancers + Monitoring
                Production Deploy       ↓
                                Health Checks
                                Rollback Capability
```

---

## Step 1: Project Setup and Structure

### 1.1 Create Lab Directory Structure
```bash
mkdir -p ~/devops-load-balancer-lab
cd ~/devops-load-balancer-lab

# Create comprehensive project structure
mkdir -p {terraform/{modules,environments/{dev,staging,prod}},ansible/{playbooks,roles,inventory},helm/{charts,values},scripts,tests/{unit,integration,performance},docs,.gitlab-ci,.github/workflows}

# Initialize Git repository
git init
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

### 1.2 Create Project Configuration Files
```yaml
# .gitlab-ci.yml
stages:
  - validate
  - test
  - security
  - deploy-dev
  - integration-test
  - deploy-staging
  - deploy-production

variables:
  TERRAFORM_VERSION: "1.5.0"
  ANSIBLE_VERSION: "2.15"
  KUBECTL_VERSION: "1.27.0"
  HELM_VERSION: "3.12.0"

include:
  - template: Security/SAST.gitlab-ci.yml
  - template: Security/Secret-Detection.gitlab-ci.yml

# Validation jobs
validate:terraform:
  stage: validate
  image: hashicorp/terraform:$TERRAFORM_VERSION
  script:
    - find terraform/ -name "*.tf" -exec terraform fmt -check {} \;
    - cd terraform/environments/dev && terraform init -backend=false && terraform validate

validate:ansible:
  stage: validate
  image: ansible/ansible-runner:latest
  script:
    - ansible-lint ansible/playbooks/
    - ansible-playbook ansible/playbooks/site.yml --syntax-check

validate:helm:
  stage: validate
  image: alpine/helm:$HELM_VERSION
  script:
    - helm lint helm/charts/load-balancer/
    - helm template test helm/charts/load-balancer/ --values helm/values/dev.yaml

# Security scanning
security:config:
  stage: security
  image: aquasec/trivy:latest
  script:
    - trivy config --exit-code 1 --severity HIGH,CRITICAL terraform/
    - trivy config --exit-code 1 --severity HIGH,CRITICAL ansible/
  allow_failure: false

# Deployment jobs
deploy:dev:
  stage: deploy-dev
  environment: development
  script:
    - ./scripts/deploy.sh dev
  only:
    - develop

deploy:staging:
  stage: deploy-staging
  environment: staging
  script:
    - ./scripts/deploy.sh staging
  when: manual
  only:
    - develop

deploy:production:
  stage: deploy-production
  environment: production
  script:
    - ./scripts/deploy.sh prod
  when: manual
  only:
    - main
```

```bash
#!/bin/bash
# scripts/deploy.sh
set -e

ENVIRONMENT=$1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -z "$ENVIRONMENT" ]; then
    echo "Usage: $0 <environment>"
    echo "Environments: dev, staging, prod"
    exit 1
fi

echo "=== Deploying Load Balancer Infrastructure to $ENVIRONMENT ==="

# Source environment-specific variables
source "$PROJECT_ROOT/.env.$ENVIRONMENT"

# Step 1: Provision infrastructure with Terraform
echo "🏗️  Provisioning infrastructure..."
cd "$PROJECT_ROOT/terraform/environments/$ENVIRONMENT"

terraform init
terraform plan -out=tfplan -var-file="terraform.tfvars"
terraform apply -auto-approve tfplan

# Get outputs for next steps
LOAD_BALANCER_IPS=$(terraform output -json load_balancer_ips | jq -r '.[]')
echo "Load Balancer IPs: $LOAD_BALANCER_IPS"

# Step 2: Configure servers with Ansible
echo "⚙️  Configuring load balancer servers..."
cd "$PROJECT_ROOT/ansible"

# Generate dynamic inventory
cat > inventory/dynamic_$ENVIRONMENT.ini << EOF
[load_balancers]
EOF

echo "$LOAD_BALANCER_IPS" | while read ip; do
    echo "lb-$ENVIRONMENT-$(echo $ip | tr '.' '-') ansible_host=$ip" >> inventory/dynamic_$ENVIRONMENT.ini
done

cat >> inventory/dynamic_$ENVIRONMENT.ini << EOF

[load_balancers:vars]
environment=$ENVIRONMENT
ansible_user=ubuntu
ansible_ssh_private_key_file=~/.ssh/id_rsa
EOF

# Run Ansible playbook
ansible-playbook -i inventory/dynamic_$ENVIRONMENT.ini playbooks/site.yml \
    --extra-vars "environment=$ENVIRONMENT" \
    --check --diff

echo "Ansible dry run completed. Running actual deployment..."
ansible-playbook -i inventory/dynamic_$ENVIRONMENT.ini playbooks/site.yml \
    --extra-vars "environment=$ENVIRONMENT"

# Step 3: Deploy to Kubernetes (if applicable)
if [ "$ENVIRONMENT" != "dev" ]; then
    echo "🚀 Deploying to Kubernetes..."
    cd "$PROJECT_ROOT/helm"
    
    # Update kubeconfig
    aws eks update-kubeconfig --region $AWS_REGION --name $ENVIRONMENT-cluster
    
    # Deploy with Helm
    helm upgrade --install load-balancer-$ENVIRONMENT charts/load-balancer/ \
        --namespace load-balancer-$ENVIRONMENT \
        --create-namespace \
        --values values/$ENVIRONMENT.yaml \
        --wait --timeout=300s
fi

# Step 4: Run health checks
echo "🔍 Running health checks..."
cd "$PROJECT_ROOT"
python3 scripts/health_check.py --environment $ENVIRONMENT

# Step 5: Run smoke tests
echo "🧪 Running smoke tests..."
python3 tests/integration/smoke_tests.py --environment $ENVIRONMENT

echo "🎉 Deployment to $ENVIRONMENT completed successfully!"
```

---

## Step 2: Terraform Infrastructure Modules

### 2.1 Create Terraform Modules
```hcl
# terraform/modules/load-balancer/main.tf
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Variables
variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where load balancer will be deployed"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for load balancer"
  type        = list(string)
}

variable "instance_type" {
  description = "Instance type for load balancer servers"
  type        = string
  default     = "t3.medium"
}

variable "min_size" {
  description = "Minimum number of load balancer instances"
  type        = number
  default     = 2
}

variable "max_size" {
  description = "Maximum number of load balancer instances"
  type        = number
  default     = 6
}

variable "desired_capacity" {
  description = "Desired number of load balancer instances"
  type        = number
  default     = 3
}

# Data sources
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Security Groups
resource "aws_security_group" "load_balancer" {
  name_prefix = "${var.environment}-lb-sg"
  vpc_id      = var.vpc_id

  # HTTP access
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP access"
  }

  # HTTPS access
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS access"
  }

  # SSH access
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
    description = "SSH access from VPC"
  }

  # HAProxy stats
  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
    description = "HAProxy statistics"
  }

  # Health check from ALB
  ingress {
    from_port   = 8081
    to_port     = 8081
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
    description = "Health check endpoint"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name        = "${var.environment}-lb-sg"
    Environment = var.environment
  }
}

# Launch Template
resource "aws_launch_template" "load_balancer" {
  name_prefix   = "${var.environment}-lb-template"
  image_id      = data.aws_ami.ubuntu.id
  instance_type = var.instance_type

  vpc_security_group_ids = [aws_security_group.load_balancer.id]

  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    environment = var.environment
  }))

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name        = "${var.environment}-lb"
      Environment = var.environment
      Role        = "load-balancer"
    }
  }

  block_device_mappings {
    device_name = "/dev/sda1"
    ebs {
      volume_size           = 20
      volume_type          = "gp3"
      encrypted            = true
      delete_on_termination = true
    }
  }

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }
}

# Auto Scaling Group
resource "aws_autoscaling_group" "load_balancer" {
  name                = "${var.environment}-lb-asg"
  vpc_zone_identifier = var.subnet_ids
  target_group_arns   = [aws_lb_target_group.load_balancer.arn]
  health_check_type   = "ELB"
  health_check_grace_period = 300

  min_size         = var.min_size
  max_size         = var.max_size
  desired_capacity = var.desired_capacity

  launch_template {
    id      = aws_launch_template.load_balancer.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "${var.environment}-lb-asg"
    propagate_at_launch = false
  }

  tag {
    key                 = "Environment"
    value               = var.environment
    propagate_at_launch = true
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
    }
  }
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${var.environment}-main-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets           = var.subnet_ids

  enable_deletion_protection = var.environment == "prod"

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.bucket
    prefix  = "alb"
    enabled = true
  }

  tags = {
    Environment = var.environment
  }
}

# ALB Security Group
resource "aws_security_group" "alb" {
  name_prefix = "${var.environment}-alb-sg"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Environment = var.environment
  }
}

# Target Group
resource "aws_lb_target_group" "load_balancer" {
  name     = "${var.environment}-lb-tg"
  port     = 80
  protocol = "HTTP"
  vpc_id   = var.vpc_id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
    port                = "8081"
    protocol            = "HTTP"
  }

  tags = {
    Environment = var.environment
  }
}

# ALB Listener
resource "aws_lb_listener" "web" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.load_balancer.arn
  }
}

# S3 Bucket for ALB Logs
resource "aws_s3_bucket" "alb_logs" {
  bucket = "${var.environment}-${random_string.bucket_suffix.result}-alb-logs"
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    id     = "log_retention"
    status = "Enabled"

    expiration {
      days = 30
    }
  }
}

resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

# Outputs
output "load_balancer_ips" {
  description = "Private IPs of load balancer instances"
  value       = data.aws_instances.load_balancer.private_ips
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Zone ID of the Application Load Balancer"
  value       = aws_lb.main.zone_id
}

data "aws_instances" "load_balancer" {
  instance_tags = {
    Role = "load-balancer"
    Environment = var.environment
  }

  depends_on = [aws_autoscaling_group.load_balancer]
}
```

```bash
# terraform/modules/load-balancer/user_data.sh
#!/bin/bash
set -e

# Update system
apt-get update -y
apt-get upgrade -y

# Install required packages
apt-get install -y \
    nginx \
    haproxy \
    python3 \
    python3-pip \
    awscli \
    cloudwatch-agent \
    htop \
    curl \
    jq

# Configure basic Nginx for health checks
cat > /etc/nginx/sites-available/health << 'EOF'
server {
    listen 8081;
    server_name _;
    
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    location /nginx-status {
        stub_status on;
        access_log off;
        allow 127.0.0.1;
        allow 10.0.0.0/8;
        deny all;
    }
}
EOF

ln -sf /etc/nginx/sites-available/health /etc/nginx/sites-enabled/health
rm -f /etc/nginx/sites-enabled/default

# Start services
systemctl enable nginx haproxy
systemctl start nginx

# Install CloudWatch agent configuration
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << EOF
{
    "metrics": {
        "namespace": "LoadBalancer/${environment}",
        "metrics_collected": {
            "cpu": {
                "measurement": [
                    "cpu_usage_idle",
                    "cpu_usage_iowait",
                    "cpu_usage_user",
                    "cpu_usage_system"
                ],
                "metrics_collection_interval": 60
            },
            "disk": {
                "measurement": [
                    "used_percent"
                ],
                "metrics_collection_interval": 60,
                "resources": [
                    "*"
                ]
            },
            "diskio": {
                "measurement": [
                    "io_time"
                ],
                "metrics_collection_interval": 60,
                "resources": [
                    "*"
                ]
            },
            "mem": {
                "measurement": [
                    "mem_used_percent"
                ],
                "metrics_collection_interval": 60
            },
            "netstat": {
                "measurement": [
                    "tcp_established",
                    "tcp_time_wait"
                ],
                "metrics_collection_interval": 60
            },
            "swap": {
                "measurement": [
                    "swap_used_percent"
                ],
                "metrics_collection_interval": 60
            }
        }
    },
    "logs": {
        "logs_collected": {
            "files": {
                "collect_list": [
                    {
                        "file_path": "/var/log/nginx/access.log",
                        "log_group_name": "/aws/ec2/nginx/${environment}",
                        "log_stream_name": "{instance_id}/access.log"
                    },
                    {
                        "file_path": "/var/log/nginx/error.log",
                        "log_group_name": "/aws/ec2/nginx/${environment}",
                        "log_stream_name": "{instance_id}/error.log"
                    },
                    {
                        "file_path": "/var/log/haproxy.log",
                        "log_group_name": "/aws/ec2/haproxy/${environment}",
                        "log_stream_name": "{instance_id}/haproxy.log"
                    }
                ]
            }
        }
    }
}
EOF

systemctl enable amazon-cloudwatch-agent
systemctl start amazon-cloudwatch-agent

echo "Load balancer server initialization completed"
```

### 2.2 Environment-specific Configurations
```hcl
# terraform/environments/dev/main.tf
terraform {
  required_version = ">= 1.0"
  
  backend "s3" {
    bucket = "your-terraform-state-bucket"
    key    = "load-balancer/dev/terraform.tfstate"
    region = "us-west-2"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Environment = "dev"
      Project     = "load-balancer"
      ManagedBy   = "terraform"
    }
  }
}

module "load_balancer" {
  source = "../../modules/load-balancer"
  
  environment      = "dev"
  vpc_id          = var.vpc_id
  subnet_ids      = var.subnet_ids
  instance_type   = "t3.small"
  min_size        = 1
  max_size        = 3
  desired_capacity = 2
}

output "load_balancer_ips" {
  description = "Load balancer instance IPs"
  value       = module.load_balancer.load_balancer_ips
}

output "alb_dns_name" {
  description = "ALB DNS name"
  value       = module.load_balancer.alb_dns_name
}
```

```hcl
# terraform/environments/dev/variables.tf
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-west-2"
}

variable "vpc_id" {
  description = "VPC ID for load balancer deployment"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs for load balancer"
  type        = list(string)
}
```

```hcl
# terraform/environments/dev/terraform.tfvars
aws_region = "us-west-2"
vpc_id     = "vpc-12345678"  # Replace with your VPC ID
subnet_ids = ["subnet-12345678", "subnet-87654321"]  # Replace with your subnet IDs
```

---

## Step 3: Ansible Configuration Management

### 3.1 Create Ansible Playbook Structure
```yaml
# ansible/playbooks/site.yml
---
- name: Configure Load Balancer Servers
  hosts: load_balancers
  become: yes
  gather_facts: yes
  
  roles:
    - common
    - nginx
    - haproxy
    - monitoring
    - security

  post_tasks:
    - name: Verify load balancer health
      uri:
        url: "http://{{ ansible_default_ipv4.address }}:8081/health"
      register: health_check
      retries: 3
      delay: 10

    - name: Display health check result
      debug:
        msg: "Health check passed: {{ health_check.status == 200 }}"
```

```yaml
# ansible/roles/nginx/tasks/main.yml
---
- name: Install Nginx
  package:
    name: nginx
    state: present

- name: Create Nginx configuration directory
  file:
    path: /etc/nginx/conf.d
    state: directory
    mode: '0755'

- name: Template main Nginx configuration
  template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
    backup: yes
    mode: '0644'
  notify: restart nginx

- name: Template site configuration
  template:
    src: load-balancer-site.conf.j2
    dest: /etc/nginx/sites-available/load-balancer
    mode: '0644'
  notify: restart nginx

- name: Enable load balancer site
  file:
    src: /etc/nginx/sites-available/load-balancer
    dest: /etc/nginx/sites-enabled/load-balancer
    state: link
  notify: restart nginx

- name: Remove default site
  file:
    path: /etc/nginx/sites-enabled/default
    state: absent
  notify: restart nginx

- name: Configure log rotation
  template:
    src: nginx-logrotate.j2
    dest: /etc/logrotate.d/nginx
    mode: '0644'

- name: Ensure Nginx is running and enabled
  systemd:
    name: nginx
    state: started
    enabled: yes
    daemon_reload: yes

- name: Test Nginx configuration
  command: nginx -t
  changed_when: false
```

```yaml
# ansible/roles/haproxy/tasks/main.yml
---
- name: Install HAProxy
  package:
    name: haproxy
    state: present

- name: Template HAProxy configuration
  template:
    src: haproxy.cfg.j2
    dest: /etc/haproxy/haproxy.cfg
    backup: yes
    mode: '0644'
  notify: restart haproxy

- name: Configure HAProxy stats socket
  file:
    path: /var/run/haproxy
    state: directory
    owner: haproxy
    group: haproxy
    mode: '0755'

- name: Configure rsyslog for HAProxy
  template:
    src: 49-haproxy.conf.j2
    dest: /etc/rsyslog.d/49-haproxy.conf
    mode: '0644'
  notify: restart rsyslog

- name: Ensure HAProxy is running and enabled
  systemd:
    name: haproxy
    state: started
    enabled: yes

- name: Test HAProxy configuration
  command: haproxy -f /etc/haproxy/haproxy.cfg -c
  changed_when: false
```

### 3.2 Ansible Templates
```jinja2
# ansible/roles/nginx/templates/nginx.conf.j2
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
    use epoll;
    multi_accept on;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

    access_log /var/log/nginx/access.log main;

    # Performance
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    client_max_body_size 10m;

    # Security
    server_tokens off;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Include site configurations
    include /etc/nginx/sites-enabled/*;
}
```

```jinja2
# ansible/roles/nginx/templates/load-balancer-site.conf.j2
# Upstream backend servers
upstream backend_servers {
    least_conn;
    {% for backend in backend_servers %}
    server {{ backend }} max_fails=3 fail_timeout=30s;
    {% endfor %}
    keepalive 32;
}

# Main server block
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name {{ ansible_fqdn }} {{ ansible_default_ipv4.address }};

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

    location / {
        proxy_pass http://backend_servers;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Timeouts
        proxy_connect_timeout 5s;
        proxy_send_timeout 10s;
        proxy_read_timeout 10s;
        proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;
    }

    location /api/ {
        limit_req zone=api burst=5 nodelay;
        proxy_pass http://backend_servers;
        # Same proxy settings as above
    }
}

# Health check server block
server {
    listen 8081;
    server_name _;

    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }

    location /nginx-status {
        stub_status on;
        access_log off;
        allow 127.0.0.1;
        allow 10.0.0.0/8;
        deny all;
    }
}
```

---

## Step 4: Testing Framework

### 4.1 Create Testing Scripts
```python
# tests/integration/test_load_balancer.py
import pytest
import requests
import time
import concurrent.futures
from urllib.parse import urljoin

class TestLoadBalancer:
    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.timeout = 10

    def test_health_endpoint(self):
        """Test that health endpoint returns 200"""
        response = self.session.get(urljoin(self.base_url, '/health'))
        assert response.status_code == 200
        assert 'healthy' in response.text

    def test_load_distribution(self):
        """Test that load is distributed across backend servers"""
        servers_hit = set()
        
        for _ in range(20):
            response = self.session.get(self.base_url)
            if response.status_code == 200:
                # Extract server identifier from response
                # This assumes backend returns server info
                server_id = response.headers.get('X-Server-ID')
                if server_id:
                    servers_hit.add(server_id)
        
        # Should hit multiple servers
        assert len(servers_hit) > 1, f"Only hit {len(servers_hit)} servers"

    def test_failover_behavior(self):
        """Test failover when a backend server is down"""
        # This test requires coordination with infrastructure
        # to simulate server failure
        initial_response = self.session.get(self.base_url)
        assert initial_response.status_code == 200
        
        # Note: In real test, you would:
        # 1. Stop one backend server
        # 2. Verify requests still succeed
        # 3. Restart server
        # 4. Verify it's back in rotation

    def test_concurrent_requests(self):
        """Test load balancer under concurrent load"""
        def make_request():
            try:
                response = self.session.get(self.base_url)
                return response.status_code
            except Exception as e:
                return str(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [future.result() for future in futures]
        
        success_count = sum(1 for result in results if result == 200)
        success_rate = success_count / len(results)
        
        assert success_rate > 0.95, f"Success rate: {success_rate:.2%}"

    def test_ssl_redirect(self):
        """Test HTTP to HTTPS redirect if SSL is configured"""
        try:
            response = self.session.get(
                self.base_url.replace('https://', 'http://'),
                allow_redirects=False
            )
            if response.status_code in [301, 302]:
                assert 'https://' in response.headers.get('Location', '')
        except requests.exceptions.SSLError:
            # Expected if HTTPS is enforced
            pass

if __name__ == "__main__":
    import sys
    
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost"
    
    tester = TestLoadBalancer(base_url)
    
    print("Running load balancer integration tests...")
    
    try:
        tester.test_health_endpoint()
        print("✅ Health endpoint test passed")
    except Exception as e:
        print(f"❌ Health endpoint test failed: {e}")
    
    try:
        tester.test_concurrent_requests()
        print("✅ Concurrent requests test passed")
    except Exception as e:
        print(f"❌ Concurrent requests test failed: {e}")
    
    print("Integration tests completed")
```

```python
# scripts/health_check.py
#!/usr/bin/env python3
import argparse
import requests
import sys
import time
from urllib.parse import urljoin

class HealthChecker:
    def __init__(self, base_url, timeout=10):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.timeout = timeout

    def check_health_endpoint(self):
        """Check the /health endpoint"""
        try:
            response = self.session.get(urljoin(self.base_url, '/health'))
            return {
                'endpoint': '/health',
                'status': 'pass' if response.status_code == 200 else 'fail',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'details': response.text[:100] if response.text else None
            }
        except Exception as e:
            return {
                'endpoint': '/health',
                'status': 'fail',
                'error': str(e)
            }

    def check_main_endpoint(self):
        """Check the main application endpoint"""
        try:
            response = self.session.get(self.base_url)
            return {
                'endpoint': '/',
                'status': 'pass' if response.status_code == 200 else 'fail',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'headers': dict(response.headers)
            }
        except Exception as e:
            return {
                'endpoint': '/',
                'status': 'fail',
                'error': str(e)
            }

    def check_ssl_configuration(self):
        """Check SSL configuration if HTTPS is used"""
        if not self.base_url.startswith('https://'):
            return {'endpoint': 'SSL', 'status': 'skip', 'reason': 'HTTP only'}
        
        try:
            response = self.session.get(self.base_url)
            return {
                'endpoint': 'SSL',
                'status': 'pass',
                'cipher': getattr(response.raw.connection.sock, 'cipher', None),
                'version': getattr(response.raw.connection.sock, 'version', None)
            }
        except Exception as e:
            return {
                'endpoint': 'SSL',
                'status': 'fail',
                'error': str(e)
            }

    def run_comprehensive_check(self):
        """Run all health checks"""
        checks = [
            self.check_health_endpoint(),
            self.check_main_endpoint(),
            self.check_ssl_configuration()
        ]
        
        overall_status = 'pass' if all(
            check.get('status') in ['pass', 'skip'] for check in checks
        ) else 'fail'
        
        return {
            'overall_status': overall_status,
            'timestamp': time.time(),
            'checks': checks
        }

def main():
    parser = argparse.ArgumentParser(description='Load balancer health checker')
    parser.add_argument('--environment', required=True, help='Environment name')
    parser.add_argument('--url', help='Base URL to check')
    parser.add_argument('--timeout', type=int, default=10, help='Request timeout')
    
    args = parser.parse_args()
    
    # Determine URL based on environment if not provided
    if not args.url:
        env_urls = {
            'dev': 'http://dev-lb.example.com',
            'staging': 'https://staging-lb.example.com',
            'prod': 'https://lb.example.com'
        }
        args.url = env_urls.get(args.environment, 'http://localhost')
    
    checker = HealthChecker(args.url, args.timeout)
    
    print(f"🔍 Running health checks for {args.environment} environment")
    print(f"🌐 Target URL: {args.url}")
    print()
    
    results = checker.run_comprehensive_check()
    
    for check in results['checks']:
        status_icon = "✅" if check['status'] == 'pass' else "❌" if check['status'] == 'fail' else "⏭️"
        print(f"{status_icon} {check['endpoint']}: {check['status']}")
        
        if 'status_code' in check:
            print(f"   Status Code: {check['status_code']}")
        if 'response_time' in check:
            print(f"   Response Time: {check['response_time']:.3f}s")
        if 'error' in check:
            print(f"   Error: {check['error']}")
        print()
    
    print(f"🎯 Overall Status: {results['overall_status']}")
    
    sys.exit(0 if results['overall_status'] == 'pass' else 1)

if __name__ == "__main__":
    main()
```

---

## Step 5: Running the Complete Pipeline

### 5.1 Execute the Pipeline
```bash
# 1. Initialize the project
git add .
git commit -m "Initial load balancer DevOps pipeline setup"

# 2. Create environment files
cat > .env.dev << EOF
AWS_REGION=us-west-2
ENVIRONMENT=dev
BACKEND_SERVERS=["web1:8080", "web2:8080"]
EOF

# 3. Run Terraform deployment
cd terraform/environments/dev
terraform init
terraform plan -var-file="terraform.tfvars"
terraform apply

# 4. Run Ansible configuration
cd ../../../ansible
ansible-playbook -i inventory/dev.ini playbooks/site.yml

# 5. Run tests
cd ..
python3 tests/integration/test_load_balancer.py http://$(terraform output -raw alb_dns_name)

# 6. Run health checks
python3 scripts/health_check.py --environment dev
```

### 5.2 Monitor and Validate
```bash
# Check deployment status
kubectl get pods -n load-balancer-dev
kubectl get ingress -n load-balancer-dev

# Monitor logs
kubectl logs -f -l app=load-balancer -n load-balancer-dev

# Run performance test
cd tests/performance
k6 run load-test.js
```

---

## Lab Exercises

### Exercise 1: Pipeline Enhancement
**Objective**: Add additional stages to the CI/CD pipeline

**Tasks**:
1. Add security scanning with SAST tools
2. Implement automated rollback on deployment failure
3. Add Slack/Teams notifications for deployment status
4. Create branch-specific deployment environments

### Exercise 2: Multi-Environment Management
**Objective**: Extend the pipeline to support multiple environments

**Tasks**:
1. Create production-specific configurations
2. Implement environment promotion workflow
3. Add manual approval gates for production
4. Create environment-specific monitoring

### Exercise 3: Advanced Testing
**Objective**: Enhance the testing framework

**Tasks**:
1. Add chaos engineering tests
2. Implement end-to-end user journey tests
3. Create performance regression testing
4. Add security penetration tests

### Exercise 4: Disaster Recovery
**Objective**: Implement disaster recovery procedures

**Tasks**:
1. Create automated backup procedures
2. Implement cross-region failover
3. Create disaster recovery runbooks
4. Test full system recovery procedures

---

## Assessment Criteria

### Technical Implementation (40%)
- [ ] **Infrastructure as Code**: Complete Terraform modules with best practices
- [ ] **Configuration Management**: Functional Ansible playbooks
- [ ] **Pipeline Automation**: Working CI/CD pipeline with all stages
- [ ] **Testing Integration**: Comprehensive test suite

### DevOps Best Practices (30%)
- [ ] **Security**: Proper secret management and security scanning
- [ ] **Documentation**: Clear documentation and runbooks
- [ ] **Monitoring**: Comprehensive monitoring and alerting
- [ ] **Rollback Capability**: Safe deployment and rollback procedures

### Operational Excellence (30%)
- [ ] **Automation**: High degree of automation
- [ ] **Reliability**: Robust error handling and recovery
- [ ] **Scalability**: Support for multi-environment deployment
- [ ] **Maintainability**: Clean, maintainable code and configurations

---

## Troubleshooting Guide

### Common Issues

#### Terraform State Lock
```bash
# If terraform state is locked
terraform force-unlock <LOCK_ID>
```

#### Ansible Connection Issues
```bash
# Test connectivity
ansible all -i inventory/dev.ini -m ping

# Check SSH configuration
ssh -i ~/.ssh/id_rsa ubuntu@<server-ip>
```

#### CI/CD Pipeline Failures
```bash
# Check GitLab CI logs
gitlab-runner logs

# Debug specific job
gitlab-ci-multi-runner exec docker validate:terraform
```

---

## Key Takeaways

1. **Infrastructure as Code** enables consistent, repeatable deployments
2. **CI/CD pipelines** provide automated testing and safe deployment practices
3. **Configuration Management** ensures consistent server configurations
4. **Comprehensive Testing** catches issues before production
5. **Monitoring and Health Checks** enable proactive issue detection
6. **Automated Rollback** provides safety net for failed deployments

This lab provides hands-on experience with enterprise-level DevOps practices essential for managing load balancer infrastructure at scale, directly applicable to staff and principal engineer responsibilities.