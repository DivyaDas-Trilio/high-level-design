# Module 4: DevOps & Deployment Strategies
## Production Load Balancer Deployment, CI/CD, and Infrastructure as Code

### Learning Objectives
- Design CI/CD pipelines for load balancer deployments
- Implement Infrastructure as Code for scalable load balancer infrastructure
- Master blue-green and canary deployment patterns using load balancers
- Build automated testing frameworks for load balancer configurations
- Integrate load balancers with container orchestration and service mesh

---

## 4.1 Infrastructure as Code (IaC)

### 4.1.1 Terraform for Load Balancer Infrastructure

```hcl
# terraform/main.tf - Complete Load Balancer Infrastructure
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket = "company-terraform-state"
    key    = "load-balancer/terraform.tfstate"
    region = "us-west-2"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Environment   = var.environment
      Project      = "load-balancer"
      ManagedBy    = "terraform"
      CostCenter   = var.cost_center
    }
  }
}

# Variables
variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

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

variable "backend_instance_ids" {
  description = "Backend EC2 instance IDs"
  type        = list(string)
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${var.environment}-app-lb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets           = var.subnet_ids

  enable_deletion_protection = var.environment == "prod" ? true : false

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.bucket
    prefix  = "alb"
    enabled = true
  }

  tags = {
    Name = "${var.environment}-app-lb"
  }
}

# Network Load Balancer for high-performance Layer 4
resource "aws_lb" "network" {
  name               = "${var.environment}-network-lb"
  internal           = false
  load_balancer_type = "network"
  subnets           = var.subnet_ids

  enable_cross_zone_load_balancing = true

  tags = {
    Name = "${var.environment}-network-lb"
  }
}

# Target Groups
resource "aws_lb_target_group" "web" {
  name     = "${var.environment}-web-tg"
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
    port                = "traffic-port"
    protocol            = "HTTP"
  }

  tags = {
    Name = "${var.environment}-web-tg"
  }
}

resource "aws_lb_target_group" "api" {
  name     = "${var.environment}-api-tg"
  port     = 8080
  protocol = "HTTP"
  vpc_id   = var.vpc_id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/api/health"
    matcher             = "200"
    port                = "traffic-port"
    protocol            = "HTTP"
  }

  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400  # 24 hours
    enabled         = true
  }

  tags = {
    Name = "${var.environment}-api-tg"
  }
}

# Target Group Attachments
resource "aws_lb_target_group_attachment" "web" {
  count            = length(var.backend_instance_ids)
  target_group_arn = aws_lb_target_group.web.arn
  target_id        = var.backend_instance_ids[count.index]
  port             = 80
}

resource "aws_lb_target_group_attachment" "api" {
  count            = length(var.backend_instance_ids)
  target_group_arn = aws_lb_target_group.api.arn
  target_id        = var.backend_instance_ids[count.index]
  port             = 8080
}

# Listeners
resource "aws_lb_listener" "web" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = aws_acm_certificate.main.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

resource "aws_lb_listener" "redirect" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# Listener Rules for Path-based Routing
resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.web.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }
}

# SSL Certificate
resource "aws_acm_certificate" "main" {
  domain_name       = "*.${var.domain_name}"
  validation_method = "DNS"

  subject_alternative_names = [
    var.domain_name
  ]

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${var.environment}-certificate"
  }
}

# Security Group for ALB
resource "aws_security_group" "alb" {
  name        = "${var.environment}-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP"
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  tags = {
    Name = "${var.environment}-alb-sg"
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
      days = 90
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

# Auto Scaling Integration
resource "aws_autoscaling_attachment" "web" {
  autoscaling_group_name = var.autoscaling_group_name
  lb_target_group_arn   = aws_lb_target_group.web.arn
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "high_response_time" {
  alarm_name          = "${var.environment}-alb-high-response-time"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = "60"
  statistic           = "Average"
  threshold           = "1"  # 1 second
  alarm_description   = "This metric monitors ALB response time"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }

  tags = {
    Name = "${var.environment}-high-response-time-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "${var.environment}-alb-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "HTTPCode_ELB_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "This metric monitors ALB 5xx errors"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    LoadBalancer = aws_lb.main.arn_suffix
  }

  tags = {
    Name = "${var.environment}-high-error-rate-alarm"
  }
}

# SNS Topic for Alerts
resource "aws_sns_topic" "alerts" {
  name = "${var.environment}-alb-alerts"

  tags = {
    Name = "${var.environment}-alb-alerts"
  }
}

# Outputs
output "alb_dns_name" {
  description = "DNS name of the load balancer"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Zone ID of the load balancer"
  value       = aws_lb.main.zone_id
}

output "target_group_arns" {
  description = "ARNs of the target groups"
  value = {
    web = aws_lb_target_group.web.arn
    api = aws_lb_target_group.api.arn
  }
}
```

### 4.1.2 Helm Charts for Kubernetes Load Balancers

```yaml
# helm/load-balancer/Chart.yaml
apiVersion: v2
name: load-balancer
description: Production-ready load balancer for Kubernetes
type: application
version: 0.1.0
appVersion: "2.4"

dependencies:
  - name: ingress-nginx
    version: "4.7.1"
    repository: "https://kubernetes.github.io/ingress-nginx"
    condition: nginx.enabled
```

```yaml
# helm/load-balancer/values.yaml
# Global configuration
global:
  environment: production
  domain: example.com
  monitoring:
    enabled: true
    namespace: monitoring

# Nginx Ingress Controller
nginx:
  enabled: true
  controller:
    replicaCount: 3
    
    config:
      enable-real-ip: "true"
      proxy-protocol: "true"
      use-forwarded-headers: "true"
      compute-full-forwarded-for: "true"
      log-format-escape-json: "true"
      log-format-upstream: >-
        {"timestamp":"$time_iso8601","requestID":"$req_id","proxyUpstreamName":"$proxy_upstream_name","proxyAlternativeUpstreamName":"$proxy_alternative_upstream_name","upstreamStatus":"$upstream_status","upstreamAddr":"$upstream_addr","httpRequest":{"requestMethod":"$request_method","requestUrl":"$host$request_uri","status":$status,"requestSize":"$request_length","responseSize":"$upstream_response_length","userAgent":"$http_user_agent","remoteIp":"$remote_addr","referer":"$http_referer","latency":"$upstream_response_time s","protocol":"$server_protocol"}}
    
    resources:
      requests:
        cpu: 500m
        memory: 512Mi
      limits:
        cpu: 1000m
        memory: 1Gi
    
    autoscaling:
      enabled: true
      minReplicas: 3
      maxReplicas: 10
      targetCPUUtilizationPercentage: 70
      targetMemoryUtilizationPercentage: 80
    
    service:
      type: LoadBalancer
      annotations:
        service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
        service.beta.kubernetes.io/aws-load-balancer-backend-protocol: "tcp"
        service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"
    
    metrics:
      enabled: true
      service:
        annotations:
          prometheus.io/scrape: "true"
          prometheus.io/port: "10254"
    
    podDisruptionBudget:
      enabled: true
      minAvailable: 2

# HAProxy (alternative option)
haproxy:
  enabled: false
  image:
    repository: haproxy
    tag: "2.4-alpine"
    pullPolicy: IfNotPresent
  
  replicaCount: 3
  
  config: |
    global
        daemon
        maxconn 4096
        log stdout local0 info
        
    defaults
        mode http
        timeout connect 5000ms
        timeout client 50000ms
        timeout server 50000ms
        option httplog
        option dontlognull
        
    frontend web_frontend
        bind *:80
        bind *:443 ssl crt /etc/ssl/certs/tls.crt
        redirect scheme https if !{ ssl_fc }
        use_backend api_backend if { path_beg /api/ }
        default_backend web_backend
        
    backend web_backend
        balance roundrobin
        option httpchk GET /health
        {{- range $i, $backend := .Values.backends.web }}
        server web{{ $i }} {{ $backend.host }}:{{ $backend.port }} check
        {{- end }}
        
    backend api_backend
        balance leastconn
        option httpchk GET /api/health
        {{- range $i, $backend := .Values.backends.api }}
        server api{{ $i }} {{ $backend.host }}:{{ $backend.port }} check
        {{- end }}

# SSL/TLS Configuration
tls:
  enabled: true
  secretName: load-balancer-tls
  issuer:
    name: letsencrypt-prod
    kind: ClusterIssuer

# Backend services configuration
backends:
  web:
    - host: web-service-1
      port: 80
    - host: web-service-2
      port: 80
  api:
    - host: api-service-1
      port: 8080
    - host: api-service-2
      port: 8080

# Monitoring and observability
monitoring:
  prometheus:
    enabled: true
    scrapeInterval: 30s
  
  grafana:
    enabled: true
    dashboards:
      enabled: true
  
  jaeger:
    enabled: true
    sampling: 0.1

# Network policies
networkPolicy:
  enabled: true
  ingress:
    - from:
      - namespaceSelector:
          matchLabels:
            name: monitoring
  egress:
    - to:
      - namespaceSelector:
          matchLabels:
            name: backend

# Pod security
podSecurityPolicy:
  enabled: true
securityContext:
  runAsNonRoot: true
  runAsUser: 65534
  fsGroup: 65534
```

```yaml
# helm/load-balancer/templates/ingress.yaml
{{- if .Values.nginx.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "load-balancer.fullname" . }}-ingress
  namespace: {{ .Release.Namespace }}
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "5"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "60"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
    nginx.ingress.kubernetes.io/proxy-next-upstream: "error timeout invalid_header http_502 http_503 http_504"
    {{- if .Values.monitoring.enabled }}
    nginx.ingress.kubernetes.io/enable-opentracing: "true"
    {{- end }}
    {{- if .Values.tls.enabled }}
    cert-manager.io/cluster-issuer: {{ .Values.tls.issuer.name }}
    {{- end }}
spec:
  {{- if .Values.tls.enabled }}
  tls:
  - hosts:
    - {{ .Values.global.domain }}
    - www.{{ .Values.global.domain }}
    - api.{{ .Values.global.domain }}
    secretName: {{ .Values.tls.secretName }}
  {{- end }}
  rules:
  - host: {{ .Values.global.domain }}
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 8080
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80
  - host: api.{{ .Values.global.domain }}
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 8080
{{- end }}
```

---

## 4.2 CI/CD Pipeline Integration

### 4.2.1 GitLab CI/CD Pipeline

```yaml
# .gitlab-ci.yml
stages:
  - validate
  - test
  - security
  - deploy-staging
  - integration-tests
  - deploy-production
  - post-deploy

variables:
  TERRAFORM_VERSION: "1.5.0"
  KUBECTL_VERSION: "1.27.0"
  HELM_VERSION: "3.12.0"
  DOCKER_DRIVER: overlay2
  DOCKER_TLS_CERTDIR: "/certs"

# Validation stage
validate-terraform:
  stage: validate
  image: hashicorp/terraform:$TERRAFORM_VERSION
  script:
    - cd terraform/environments/$ENVIRONMENT
    - terraform init -backend=false
    - terraform validate
    - terraform fmt -check
  artifacts:
    reports:
      junit: terraform-validation-report.xml

validate-helm:
  stage: validate
  image: alpine/helm:$HELM_VERSION
  script:
    - helm lint helm/load-balancer/
    - helm template test helm/load-balancer/ --values helm/load-balancer/values-staging.yaml
  artifacts:
    paths:
      - helm-lint-results.txt

validate-configs:
  stage: validate
  image: nginx:alpine
  script:
    - nginx -t -c configs/nginx/nginx.conf
    - |
      if command -v haproxy &> /dev/null; then
        haproxy -f configs/haproxy/haproxy.cfg -c
      fi
  artifacts:
    reports:
      junit: config-validation-report.xml

# Testing stage
unit-tests:
  stage: test
  image: python:3.9
  script:
    - pip install -r tests/requirements.txt
    - python -m pytest tests/unit/ -v --junitxml=unit-tests.xml
  artifacts:
    reports:
      junit: unit-tests.xml
    paths:
      - tests/unit/coverage/

load-balancer-simulation:
  stage: test
  image: python:3.9
  services:
    - docker:dind
  script:
    - pip install docker-compose
    - docker-compose -f tests/docker-compose.test.yml up -d
    - sleep 30  # Wait for services to start
    - python tests/integration/test_load_balancer.py
    - docker-compose -f tests/docker-compose.test.yml down
  artifacts:
    reports:
      junit: simulation-tests.xml

# Security scanning
security-scan:
  stage: security
  image: aquasec/trivy:latest
  script:
    - trivy config terraform/
    - trivy config helm/
    - trivy config configs/
  artifacts:
    reports:
      junit: security-scan.xml
  allow_failure: true

# Staging deployment
deploy-staging:
  stage: deploy-staging
  image: alpine:latest
  environment:
    name: staging
    url: https://staging.example.com
  before_script:
    - apk add --no-cache curl aws-cli
    - curl -LO "https://dl.k8s.io/release/v$KUBECTL_VERSION/bin/linux/amd64/kubectl"
    - curl -LO "https://get.helm.sh/helm-v$HELM_VERSION-linux-amd64.tar.gz"
    - tar -zxvf helm-v$HELM_VERSION-linux-amd64.tar.gz
    - mv linux-amd64/helm /usr/local/bin/helm
    - chmod +x kubectl && mv kubectl /usr/local/bin/
  script:
    # Deploy infrastructure with Terraform
    - cd terraform/environments/staging
    - terraform init
    - terraform plan -out=tfplan
    - terraform apply -auto-approve tfplan
    
    # Deploy Kubernetes resources
    - kubectl config use-context staging-cluster
    - helm upgrade --install load-balancer ../../helm/load-balancer/ 
        --namespace load-balancer 
        --create-namespace 
        --values ../../helm/load-balancer/values-staging.yaml
        --wait --timeout=300s
    
    # Verify deployment
    - kubectl get pods -n load-balancer
    - kubectl get ingress -n load-balancer
  artifacts:
    paths:
      - terraform/environments/staging/tfplan
    expire_in: 1 day
  only:
    - develop
    - merge_requests

# Integration testing
integration-tests:
  stage: integration-tests
  image: python:3.9
  environment:
    name: staging
  script:
    - pip install -r tests/requirements.txt
    - python -m pytest tests/integration/ 
        --base-url=https://staging.example.com 
        --junitxml=integration-tests.xml
  artifacts:
    reports:
      junit: integration-tests.xml
  dependencies:
    - deploy-staging

# Performance testing
performance-tests:
  stage: integration-tests
  image: grafana/k6:latest
  environment:
    name: staging
  script:
    - k6 run tests/performance/load-test.js
      --env BASE_URL=https://staging.example.com
  artifacts:
    paths:
      - k6-results.json
  dependencies:
    - deploy-staging

# Production deployment
deploy-production:
  stage: deploy-production
  image: alpine:latest
  environment:
    name: production
    url: https://example.com
  before_script:
    - apk add --no-cache curl aws-cli
    - curl -LO "https://dl.k8s.io/release/v$KUBECTL_VERSION/bin/linux/amd64/kubectl"
    - curl -LO "https://get.helm.sh/helm-v$HELM_VERSION-linux-amd64.tar.gz"
    - tar -zxvf helm-v$HELM_VERSION-linux-amd64.tar.gz
    - mv linux-amd64/helm /usr/local/bin/helm
    - chmod +x kubectl && mv kubectl /usr/local/bin/
  script:
    # Production deployment with approval
    - echo "Deploying to production..."
    - cd terraform/environments/production
    - terraform init
    - terraform plan -out=tfplan
    - terraform apply -auto-approve tfplan
    
    # Blue-green deployment
    - ./scripts/blue-green-deploy.sh
  when: manual
  only:
    - main

# Post-deployment verification
post-deploy-verification:
  stage: post-deploy
  image: python:3.9
  script:
    - pip install requests
    - python scripts/health-check.py --environment=$CI_ENVIRONMENT_NAME
    - python scripts/smoke-tests.py --environment=$CI_ENVIRONMENT_NAME
  artifacts:
    reports:
      junit: post-deploy-tests.xml

# Rollback job (manual)
rollback:
  stage: deploy-production
  image: alpine:latest
  script:
    - ./scripts/rollback.sh $CI_ENVIRONMENT_NAME
  when: manual
  only:
    - main
```

### 4.2.2 GitHub Actions Workflow

```yaml
# .github/workflows/load-balancer-deploy.yml
name: Load Balancer Deployment

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  TERRAFORM_VERSION: 1.5.0
  KUBECTL_VERSION: 1.27.0
  HELM_VERSION: 3.12.0

jobs:
  validate:
    name: Validate Configuration
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Setup Terraform
      uses: hashicorp/setup-terraform@v2
      with:
        terraform_version: ${{ env.TERRAFORM_VERSION }}

    - name: Terraform Format Check
      run: terraform fmt -check -recursive terraform/

    - name: Terraform Validate
      run: |
        cd terraform/environments/staging
        terraform init -backend=false
        terraform validate

    - name: Setup Helm
      uses: azure/setup-helm@v3
      with:
        version: ${{ env.HELM_VERSION }}

    - name: Helm Lint
      run: |
        helm lint helm/load-balancer/
        helm template test helm/load-balancer/ \
          --values helm/load-balancer/values-staging.yaml

    - name: Config Validation
      run: |
        # Validate Nginx config
        docker run --rm -v $PWD/configs/nginx:/etc/nginx:ro nginx:alpine nginx -t
        
        # Validate HAProxy config
        docker run --rm -v $PWD/configs/haproxy:/usr/local/etc/haproxy:ro haproxy:alpine haproxy -f /usr/local/etc/haproxy/haproxy.cfg -c

  test:
    name: Run Tests
    runs-on: ubuntu-latest
    needs: validate
    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r tests/requirements.txt

    - name: Run unit tests
      run: |
        python -m pytest tests/unit/ -v --junitxml=unit-tests.xml

    - name: Load balancer simulation test
      run: |
        docker-compose -f tests/docker-compose.test.yml up -d
        sleep 30
        python tests/integration/test_load_balancer.py
        docker-compose -f tests/docker-compose.test.yml down

  security:
    name: Security Scanning
    runs-on: ubuntu-latest
    needs: validate
    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        scan-type: 'config'
        scan-ref: '.'
        format: 'sarif'
        output: 'trivy-results.sarif'

    - name: Upload Trivy scan results
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: 'trivy-results.sarif'

  deploy-staging:
    name: Deploy to Staging
    runs-on: ubuntu-latest
    needs: [test, security]
    if: github.ref == 'refs/heads/develop'
    environment: staging
    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: us-west-2

    - name: Setup Terraform
      uses: hashicorp/setup-terraform@v2
      with:
        terraform_version: ${{ env.TERRAFORM_VERSION }}

    - name: Terraform Init and Apply
      working-directory: terraform/environments/staging
      run: |
        terraform init
        terraform plan -out=tfplan
        terraform apply -auto-approve tfplan

    - name: Setup kubectl
      uses: azure/setup-kubectl@v3
      with:
        version: ${{ env.KUBECTL_VERSION }}

    - name: Setup Helm
      uses: azure/setup-helm@v3
      with:
        version: ${{ env.HELM_VERSION }}

    - name: Deploy to Kubernetes
      run: |
        aws eks update-kubeconfig --region us-west-2 --name staging-cluster
        helm upgrade --install load-balancer helm/load-balancer/ \
          --namespace load-balancer \
          --create-namespace \
          --values helm/load-balancer/values-staging.yaml \
          --wait --timeout=300s

    - name: Verify deployment
      run: |
        kubectl get pods -n load-balancer
        kubectl get ingress -n load-balancer
        # Wait for load balancer to be ready
        kubectl wait --for=condition=Ready pod -l app=load-balancer -n load-balancer --timeout=300s

  integration-test:
    name: Integration Tests
    runs-on: ubuntu-latest
    needs: deploy-staging
    if: github.ref == 'refs/heads/develop'
    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Run integration tests
      run: |
        pip install -r tests/requirements.txt
        python -m pytest tests/integration/ \
          --base-url=https://staging.example.com \
          --junitxml=integration-tests.xml

    - name: Performance tests with k6
      uses: grafana/k6-action@v0.3.0
      with:
        filename: tests/performance/load-test.js
      env:
        BASE_URL: https://staging.example.com

  deploy-production:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: integration-test
    if: github.ref == 'refs/heads/main'
    environment: production
    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: us-west-2

    - name: Blue-Green Deployment
      run: |
        ./scripts/blue-green-deploy.sh production

    - name: Post-deployment verification
      run: |
        python scripts/health-check.py --environment=production
        python scripts/smoke-tests.py --environment=production
```

---

## 4.3 Deployment Patterns

### 4.3.1 Blue-Green Deployment

```bash
#!/bin/bash
# scripts/blue-green-deploy.sh
# Blue-Green deployment script for load balancer

set -e

ENVIRONMENT=$1
NAMESPACE="load-balancer"
TIMEOUT=300

if [ -z "$ENVIRONMENT" ]; then
    echo "Usage: $0 <environment>"
    exit 1
fi

echo "=== Starting Blue-Green Deployment for $ENVIRONMENT ==="

# Determine current active deployment
CURRENT_ACTIVE=$(kubectl get ingress -n $NAMESPACE -o jsonpath='{.items[0].metadata.annotations.deployment\.active}' 2>/dev/null || echo "blue")

if [ "$CURRENT_ACTIVE" = "blue" ]; then
    NEW_ACTIVE="green"
    OLD_ACTIVE="blue"
else
    NEW_ACTIVE="blue" 
    OLD_ACTIVE="green"
fi

echo "Current active deployment: $OLD_ACTIVE"
echo "Deploying to: $NEW_ACTIVE"

# Deploy new version to inactive environment
echo "=== Deploying new version to $NEW_ACTIVE environment ==="
helm upgrade --install load-balancer-$NEW_ACTIVE helm/load-balancer/ \
    --namespace $NAMESPACE \
    --create-namespace \
    --values helm/load-balancer/values-${ENVIRONMENT}.yaml \
    --set nameOverride=load-balancer-$NEW_ACTIVE \
    --set image.tag=$CI_COMMIT_SHA \
    --wait --timeout=${TIMEOUT}s

# Health check on new deployment
echo "=== Running health checks on $NEW_ACTIVE deployment ==="
NEW_SERVICE_URL="http://load-balancer-$NEW_ACTIVE.$NAMESPACE.svc.cluster.local"

for i in {1..30}; do
    if curl -f -s $NEW_SERVICE_URL/health > /dev/null; then
        echo "✅ Health check passed"
        break
    fi
    echo "⏳ Waiting for health check... ($i/30)"
    sleep 10
done

# Run comprehensive tests on new deployment
echo "=== Running integration tests on $NEW_ACTIVE deployment ==="
python tests/integration/blue_green_tests.py --service-url=$NEW_SERVICE_URL

# Switch traffic to new deployment
echo "=== Switching traffic to $NEW_ACTIVE deployment ==="
kubectl patch ingress load-balancer-ingress -n $NAMESPACE -p '{
    "metadata": {
        "annotations": {
            "deployment.active": "'$NEW_ACTIVE'"
        }
    },
    "spec": {
        "rules": [{
            "host": "example.com",
            "http": {
                "paths": [{
                    "path": "/",
                    "pathType": "Prefix",
                    "backend": {
                        "service": {
                            "name": "load-balancer-'$NEW_ACTIVE'",
                            "port": {
                                "number": 80
                            }
                        }
                    }
                }]
            }
        }]
    }
}'

# Monitor traffic switch
echo "=== Monitoring traffic switch ==="
sleep 30

# Validate production traffic
echo "=== Validating production traffic ==="
for i in {1..10}; do
    RESPONSE=$(curl -s -w "%{http_code}" https://example.com/health -o /dev/null)
    if [ "$RESPONSE" != "200" ]; then
        echo "❌ Health check failed with status: $RESPONSE"
        echo "🔄 Rolling back to $OLD_ACTIVE"
        
        # Rollback
        kubectl patch ingress load-balancer-ingress -n $NAMESPACE -p '{
            "spec": {
                "rules": [{
                    "host": "example.com", 
                    "http": {
                        "paths": [{
                            "path": "/",
                            "pathType": "Prefix",
                            "backend": {
                                "service": {
                                    "name": "load-balancer-'$OLD_ACTIVE'",
                                    "port": {
                                        "number": 80
                                    }
                                }
                            }
                        }]
                    }
                }]
            }
        }'
        exit 1
    fi
    echo "✅ Health check $i/10 passed"
done

# Cleanup old deployment
echo "=== Cleaning up $OLD_ACTIVE deployment ==="
sleep 60  # Wait before cleanup to ensure stability
helm uninstall load-balancer-$OLD_ACTIVE -n $NAMESPACE

echo "🎉 Blue-Green deployment completed successfully!"
echo "New active deployment: $NEW_ACTIVE"
```

### 4.3.2 Canary Deployment

```yaml
# canary-deployment/canary-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: load-balancer-canary
  namespace: load-balancer
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "10"  # 10% traffic
    nginx.ingress.kubernetes.io/canary-by-header: "X-Canary"
    nginx.ingress.kubernetes.io/canary-by-header-value: "always"
spec:
  rules:
  - host: example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: load-balancer-canary
            port:
              number: 80
```

```bash
#!/bin/bash
# scripts/canary-deploy.sh
# Canary deployment script with gradual traffic increase

set -e

ENVIRONMENT=$1
NAMESPACE="load-balancer"
CANARY_PERCENTAGES=(5 10 25 50 100)
MONITOR_DURATION=300  # 5 minutes between increases

echo "=== Starting Canary Deployment for $ENVIRONMENT ==="

# Deploy canary version
echo "=== Deploying canary version ==="
helm upgrade --install load-balancer-canary helm/load-balancer/ \
    --namespace $NAMESPACE \
    --values helm/load-balancer/values-${ENVIRONMENT}.yaml \
    --set nameOverride=load-balancer-canary \
    --set image.tag=$CI_COMMIT_SHA \
    --wait --timeout=300s

# Function to update canary weight
update_canary_weight() {
    local weight=$1
    echo "=== Setting canary weight to $weight% ==="
    
    kubectl patch ingress load-balancer-canary -n $NAMESPACE -p '{
        "metadata": {
            "annotations": {
                "nginx.ingress.kubernetes.io/canary-weight": "'$weight'"
            }
        }
    }'
}

# Function to monitor metrics
monitor_canary_metrics() {
    local weight=$1
    echo "=== Monitoring canary metrics at $weight% traffic ==="
    
    python scripts/canary_monitor.py \
        --weight=$weight \
        --duration=$MONITOR_DURATION \
        --error-threshold=1 \
        --latency-threshold=500
    
    return $?
}

# Gradual traffic increase
for percentage in "${CANARY_PERCENTAGES[@]}"; do
    update_canary_weight $percentage
    
    if [ $percentage -lt 100 ]; then
        echo "⏳ Monitoring for $MONITOR_DURATION seconds..."
        
        if ! monitor_canary_metrics $percentage; then
            echo "❌ Canary metrics failed at $percentage% - rolling back"
            kubectl delete ingress load-balancer-canary -n $NAMESPACE
            helm uninstall load-balancer-canary -n $NAMESPACE
            exit 1
        fi
        
        echo "✅ Canary metrics passed at $percentage%"
    fi
done

# Promote canary to main
echo "=== Promoting canary to main deployment ==="
helm upgrade load-balancer helm/load-balancer/ \
    --namespace $NAMESPACE \
    --values helm/load-balancer/values-${ENVIRONMENT}.yaml \
    --set image.tag=$CI_COMMIT_SHA \
    --wait --timeout=300s

# Cleanup canary
kubectl delete ingress load-balancer-canary -n $NAMESPACE
helm uninstall load-balancer-canary -n $NAMESPACE

echo "🎉 Canary deployment completed successfully!"
```

```python
# scripts/canary_monitor.py
import argparse
import time
import requests
from prometheus_api_client import PrometheusConnect
import sys

class CanaryMonitor:
    def __init__(self, prometheus_url="http://prometheus:9090"):
        self.prometheus = PrometheusConnect(url=prometheus_url)
    
    def check_error_rate(self, duration_minutes=5, threshold_percent=1):
        """Check error rate for canary deployment"""
        query = f'''
        sum(rate(nginx_ingress_controller_requests_total{{
            ingress="load-balancer-canary",
            status=~"5.."
        }}[{duration_minutes}m])) /
        sum(rate(nginx_ingress_controller_requests_total{{
            ingress="load-balancer-canary"
        }}[{duration_minutes}m])) * 100
        '''
        
        result = self.prometheus.custom_query(query)
        if result:
            error_rate = float(result[0]['value'][1])
            print(f"📊 Canary error rate: {error_rate:.2f}%")
            return error_rate <= threshold_percent
        return True
    
    def check_latency(self, duration_minutes=5, threshold_ms=500):
        """Check average response time for canary"""
        query = f'''
        histogram_quantile(0.95,
            sum(rate(nginx_ingress_controller_request_duration_seconds_bucket{{
                ingress="load-balancer-canary"
            }}[{duration_minutes}m])) by (le)
        ) * 1000
        '''
        
        result = self.prometheus.custom_query(query)
        if result:
            latency = float(result[0]['value'][1])
            print(f"📊 Canary 95th percentile latency: {latency:.2f}ms")
            return latency <= threshold_ms
        return True
    
    def check_success_rate(self, duration_minutes=5, threshold_percent=99):
        """Check overall success rate"""
        query = f'''
        sum(rate(nginx_ingress_controller_requests_total{{
            ingress="load-balancer-canary",
            status=~"2..|3.."
        }}[{duration_minutes}m])) /
        sum(rate(nginx_ingress_controller_requests_total{{
            ingress="load-balancer-canary"
        }}[{duration_minutes}m])) * 100
        '''
        
        result = self.prometheus.custom_query(query)
        if result:
            success_rate = float(result[0]['value'][1])
            print(f"📊 Canary success rate: {success_rate:.2f}%")
            return success_rate >= threshold_percent
        return True

def main():
    parser = argparse.ArgumentParser(description='Monitor canary deployment')
    parser.add_argument('--weight', type=int, required=True, help='Canary weight percentage')
    parser.add_argument('--duration', type=int, default=300, help='Monitor duration in seconds')
    parser.add_argument('--error-threshold', type=float, default=1, help='Error rate threshold')
    parser.add_argument('--latency-threshold', type=float, default=500, help='Latency threshold in ms')
    
    args = parser.parse_args()
    
    monitor = CanaryMonitor()
    
    print(f"🔍 Monitoring canary deployment at {args.weight}% for {args.duration} seconds")
    
    # Monitor for specified duration
    start_time = time.time()
    checks_passed = 0
    total_checks = 0
    
    while (time.time() - start_time) < args.duration:
        total_checks += 1
        
        # Check all metrics
        error_rate_ok = monitor.check_error_rate(threshold_percent=args.error_threshold)
        latency_ok = monitor.check_latency(threshold_ms=args.latency_threshold)
        success_rate_ok = monitor.check_success_rate()
        
        if error_rate_ok and latency_ok and success_rate_ok:
            checks_passed += 1
            print("✅ All metrics passed")
        else:
            print("❌ Some metrics failed")
            # Immediate failure if metrics are bad
            if not error_rate_ok or not success_rate_ok:
                print("💥 Critical metrics failed - aborting canary")
                sys.exit(1)
        
        time.sleep(30)  # Check every 30 seconds
    
    # Final assessment
    success_rate = (checks_passed / total_checks) * 100
    print(f"📈 Overall check success rate: {success_rate:.1f}%")
    
    if success_rate >= 80:  # 80% of checks must pass
        print("🎉 Canary monitoring completed successfully")
        sys.exit(0)
    else:
        print("❌ Canary monitoring failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## 4.4 Configuration Management

### 4.4.1 Ansible Playbooks

```yaml
# ansible/load-balancer.yml
---
- name: Deploy and Configure Load Balancers
  hosts: load_balancers
  become: yes
  vars:
    nginx_version: "1.24"
    haproxy_version: "2.4"
    ssl_cert_path: "/etc/ssl/certs"
    ssl_key_path: "/etc/ssl/private"
    
  tasks:
    - name: Update system packages
      package:
        name: "*"
        state: latest
      when: ansible_os_family == "RedHat"
      
    - name: Install required packages
      package:
        name:
          - nginx
          - haproxy
          - openssl
          - logrotate
          - htop
          - curl
          - telnet
        state: present

    - name: Create nginx configuration directory
      file:
        path: /etc/nginx/conf.d
        state: directory
        owner: root
        group: root
        mode: '0755'

    - name: Template nginx configuration
      template:
        src: nginx.conf.j2
        dest: /etc/nginx/nginx.conf
        backup: yes
        owner: root
        group: root
        mode: '0644'
      notify: reload nginx

    - name: Template HAProxy configuration
      template:
        src: haproxy.cfg.j2
        dest: /etc/haproxy/haproxy.cfg
        backup: yes
        owner: root
        group: root
        mode: '0644'
      notify: reload haproxy

    - name: Configure SSL certificates
      copy:
        src: "{{ item.src }}"
        dest: "{{ item.dest }}"
        owner: root
        group: root
        mode: '0600'
      with_items:
        - { src: "ssl/{{ inventory_hostname }}.crt", dest: "{{ ssl_cert_path }}/{{ inventory_hostname }}.crt" }
        - { src: "ssl/{{ inventory_hostname }}.key", dest: "{{ ssl_key_path }}/{{ inventory_hostname }}.key" }
      notify:
        - reload nginx
        - reload haproxy

    - name: Configure log rotation
      template:
        src: logrotate.j2
        dest: /etc/logrotate.d/load-balancer
        owner: root
        group: root
        mode: '0644'

    - name: Start and enable services
      systemd:
        name: "{{ item }}"
        state: started
        enabled: yes
        daemon_reload: yes
      with_items:
        - nginx
        - haproxy

    - name: Configure firewall rules
      firewalld:
        port: "{{ item }}"
        permanent: yes
        state: enabled
        immediate: yes
      with_items:
        - "80/tcp"
        - "443/tcp"
        - "8080/tcp"  # HAProxy stats
      when: ansible_os_family == "RedHat"

    - name: Health check script
      template:
        src: health_check.sh.j2
        dest: /usr/local/bin/health_check.sh
        owner: root
        group: root
        mode: '0755'

    - name: Schedule health checks
      cron:
        name: "Load balancer health check"
        minute: "*/5"
        job: "/usr/local/bin/health_check.sh"

  handlers:
    - name: reload nginx
      systemd:
        name: nginx
        state: reloaded

    - name: reload haproxy
      systemd:
        name: haproxy
        state: reloaded

# Inventory file
# inventory/production
[load_balancers]
lb1.example.com ansible_host=10.0.1.10
lb2.example.com ansible_host=10.0.1.11

[load_balancers:vars]
environment=production
backend_servers=['web1:8080', 'web2:8080', 'web3:8080']
```

```jinja2
# templates/nginx.conf.j2
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

    # Logging format
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for" '
                    'rt=$request_time uct="$upstream_connect_time" '
                    'uht="$upstream_header_time" urt="$upstream_response_time"';

    access_log /var/log/nginx/access.log main;

    # Performance optimizations
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 16M;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=login:10m rate=1r/s;

    # Upstream configuration
    upstream backend_web {
        least_conn;
        {% for server in backend_servers %}
        server {{ server }} max_fails=3 fail_timeout=30s;
        {% endfor %}
        keepalive 32;
    }

    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    server {
        listen 80;
        server_name {{ ansible_fqdn }};
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name {{ ansible_fqdn }};

        ssl_certificate {{ ssl_cert_path }}/{{ ansible_fqdn }}.crt;
        ssl_certificate_key {{ ssl_key_path }}/{{ ansible_fqdn }}.key;

        location / {
            proxy_pass http://backend_web;
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
        }

        location /api/ {
            limit_req zone=api burst=5 nodelay;
            proxy_pass http://backend_web;
            # Same proxy settings as above
        }

        location /nginx-status {
            stub_status on;
            access_log off;
            allow 127.0.0.1;
            allow {{ ansible_default_ipv4.address }};
            deny all;
        }

        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }
    }
}
```

---

## Module Assessment

### Practical Exercise

**Scenario**: Design a complete DevOps pipeline for a global e-commerce platform's load balancer infrastructure with:
- Multi-region deployment (US, EU, Asia)  
- Microservices architecture (20+ services)
- Peak traffic: 100K requests/minute
- Zero-downtime deployment requirement
- Compliance requirements (PCI-DSS, GDPR)

**Deliverables**:
1. **Infrastructure as Code**: Complete Terraform modules for multi-region setup
2. **CI/CD Pipeline**: GitLab CI or GitHub Actions with security scanning
3. **Deployment Strategy**: Blue-green or canary deployment implementation  
4. **Configuration Management**: Ansible playbooks for server configuration
5. **Monitoring Integration**: Full observability stack setup
6. **Disaster Recovery**: Automated failover and recovery procedures

### Knowledge Assessment

1. **Compare deployment strategies**: When would you use blue-green vs canary vs rolling deployments?

2. **Infrastructure as Code**: Design a Terraform module structure for load balancers that supports multiple environments and regions.

3. **CI/CD Security**: What security checks should be mandatory in a load balancer deployment pipeline?

4. **Configuration Drift**: How do you prevent and detect configuration drift in production load balancers?

---

## Next Module Preview
**Module 5: Performance & Scalability**
- Connection pooling and keep-alive optimization
- Auto-scaling strategies and metrics
- Global load balancing and CDN integration
- Performance testing and capacity planning

---

## Key Takeaways

1. **Infrastructure as Code** enables consistent, repeatable load balancer deployments
2. **CI/CD pipelines** provide automated testing and safe deployment practices
3. **Blue-green and canary deployments** enable zero-downtime updates
4. **Configuration management** ensures consistency across environments
5. **Automated testing** catches issues before they reach production
6. **Security scanning** should be integrated into every deployment pipeline

These DevOps practices are essential for managing load balancer infrastructure at enterprise scale and ensuring reliable, secure deployments.