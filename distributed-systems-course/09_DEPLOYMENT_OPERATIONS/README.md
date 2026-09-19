# Module 09: Deployment & Operations
*Production-Ready Deployment and Operational Excellence*

## Learning Objectives

By the end of this module, you will:
- Master Kubernetes deployment patterns and best practices
- Implement robust CI/CD pipelines for distributed systems
- Apply GitOps principles for infrastructure management
- Configure blue-green and canary deployment strategies
- Implement infrastructure as code with proper governance
- Design incident response and disaster recovery procedures
- Apply Site Reliability Engineering (SRE) practices
- Manage secrets and security in production environments

## Why Deployment and Operations Matter

Effective deployment and operations are critical for:

- **System Reliability**: Minimizing downtime and service disruptions
- **Development Velocity**: Fast, safe deployments enable rapid iteration
- **Operational Efficiency**: Automated operations reduce manual effort and errors
- **Risk Management**: Proper deployment strategies minimize blast radius
- **Compliance**: Meeting regulatory and security requirements

## Table of Contents

1. [Kubernetes Production Patterns](#kubernetes-production-patterns)
2. [CI/CD for Distributed Systems](#cicd-for-distributed-systems)
3. [GitOps and Infrastructure as Code](#gitops-and-infrastructure-as-code)
4. [Deployment Strategies](#deployment-strategies)
5. [Secrets Management](#secrets-management)
6. [Monitoring and Alerting](#monitoring-and-alerting)
7. [Incident Response](#incident-response)
8. [Site Reliability Engineering](#site-reliability-engineering)

---

## Kubernetes Production Patterns

### Production-Ready Kubernetes Manifests

```yaml
# k8s/production/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ecommerce-prod
  labels:
    environment: production
    app: ecommerce
    managed-by: gitops
---
# k8s/production/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service
  namespace: ecommerce-prod
  labels:
    app: user-service
    version: v1.2.3
    environment: production
spec:
  replicas: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
      maxSurge: 2
  selector:
    matchLabels:
      app: user-service
  template:
    metadata:
      labels:
        app: user-service
        version: v1.2.3
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: user-service
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 2000
      containers:
      - name: user-service
        image: registry.company.com/user-service:v1.2.3
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8080
          name: http
          protocol: TCP
        - containerPort: 9090
          name: metrics
          protocol: TCP
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: user-service-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            configMapKeyRef:
              name: user-service-config
              key: redis-url
        - name: LOG_LEVEL
          value: "INFO"
        - name: ENVIRONMENT
          value: "production"
        resources:
          requests:
            cpu: 200m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        startupProbe:
          httpGet:
            path: /health/startup
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 30
        volumeMounts:
        - name: config-volume
          mountPath: /app/config
          readOnly: true
        - name: tmp-volume
          mountPath: /tmp
      volumes:
      - name: config-volume
        configMap:
          name: user-service-config
      - name: tmp-volume
        emptyDir: {}
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - user-service
              topologyKey: kubernetes.io/hostname
      tolerations:
      - key: "workload"
        operator: "Equal"
        value: "production"
        effect: "NoSchedule"
      nodeSelector:
        workload: production
---
# k8s/production/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: user-service
  namespace: ecommerce-prod
  labels:
    app: user-service
spec:
  selector:
    app: user-service
  ports:
  - name: http
    port: 80
    targetPort: 8080
    protocol: TCP
  type: ClusterIP
---
# k8s/production/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: user-service-hpa
  namespace: ecommerce-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: user-service
  minReplicas: 5
  maxReplicas: 50
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: requests_per_second
      target:
        type: AverageValue
        averageValue: "100"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
---
# k8s/production/pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: user-service-pdb
  namespace: ecommerce-prod
spec:
  minAvailable: 3
  selector:
    matchLabels:
      app: user-service
---
# k8s/production/network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: user-service-netpol
  namespace: ecommerce-prod
spec:
  podSelector:
    matchLabels:
      app: user-service
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ecommerce-prod
    - namespaceSelector:
        matchLabels:
          name: istio-system
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          name: ecommerce-prod
    ports:
    - protocol: TCP
      port: 5432  # PostgreSQL
    - protocol: TCP
      port: 6379  # Redis
  - to: []  # Allow DNS
    ports:
    - protocol: UDP
      port: 53
```

### Kubernetes Operator for Application Management

```python
# k8s/operator/user_service_operator.py
import asyncio
import kopf
import kubernetes
from typing import Dict, Any
import yaml
import logging

# Configure Kubernetes client
kubernetes.config.load_incluster_config()
v1 = kubernetes.client.CoreV1Api()
apps_v1 = kubernetes.client.AppsV1Api()

@kopf.on.create('apps.company.com', 'v1', 'userservices')
async def create_user_service(spec: Dict[str, Any], name: str, namespace: str, **kwargs):
    """Handle UserService custom resource creation"""
    
    # Extract configuration from custom resource
    replicas = spec.get('replicas', 3)
    image = spec.get('image')
    database_config = spec.get('database', {})
    monitoring = spec.get('monitoring', {})
    
    logging.info(f"Creating UserService {name} in namespace {namespace}")
    
    # Create ConfigMap
    config_map = create_config_map(name, namespace, spec)
    await create_k8s_resource(v1.create_namespaced_config_map, namespace, config_map)
    
    # Create Secret
    secret = create_secret(name, namespace, database_config)
    await create_k8s_resource(v1.create_namespaced_secret, namespace, secret)
    
    # Create Deployment
    deployment = create_deployment(name, namespace, spec)
    await create_k8s_resource(apps_v1.create_namespaced_deployment, namespace, deployment)
    
    # Create Service
    service = create_service(name, namespace, spec)
    await create_k8s_resource(v1.create_namespaced_service, namespace, service)
    
    # Create ServiceMonitor if monitoring is enabled
    if monitoring.get('enabled', False):
        service_monitor = create_service_monitor(name, namespace, monitoring)
        await create_custom_resource('monitoring.coreos.com', 'v1', 'servicemonitors', 
                                    namespace, service_monitor)
    
    return {'status': 'created', 'message': f'UserService {name} created successfully'}

@kopf.on.update('apps.company.com', 'v1', 'userservices')
async def update_user_service(spec: Dict[str, Any], status: Dict[str, Any], 
                            name: str, namespace: str, **kwargs):
    """Handle UserService custom resource updates"""
    
    logging.info(f"Updating UserService {name} in namespace {namespace}")
    
    # Update deployment with new configuration
    deployment = create_deployment(name, namespace, spec)
    
    try:
        await update_k8s_resource(
            apps_v1.patch_namespaced_deployment, 
            name, namespace, deployment
        )
        
        # Wait for rollout to complete
        await wait_for_deployment_ready(name, namespace)
        
        return {'status': 'updated', 'message': f'UserService {name} updated successfully'}
        
    except Exception as e:
        logging.error(f"Failed to update UserService {name}: {e}")
        raise kopf.TemporaryError(f"Update failed: {e}", delay=30)

@kopf.on.delete('apps.company.com', 'v1', 'userservices')
async def delete_user_service(spec: Dict[str, Any], name: str, namespace: str, **kwargs):
    """Handle UserService custom resource deletion"""
    
    logging.info(f"Deleting UserService {name} in namespace {namespace}")
    
    # Delete resources in reverse order
    resources_to_delete = [
        (v1.delete_namespaced_service, name),
        (apps_v1.delete_namespaced_deployment, name),
        (v1.delete_namespaced_secret, f"{name}-secret"),
        (v1.delete_namespaced_config_map, f"{name}-config")
    ]
    
    for delete_func, resource_name in resources_to_delete:
        try:
            await delete_k8s_resource(delete_func, resource_name, namespace)
        except kubernetes.client.ApiException as e:
            if e.status != 404:  # Ignore not found errors
                logging.warning(f"Failed to delete {resource_name}: {e}")
    
    return {'status': 'deleted', 'message': f'UserService {name} deleted successfully'}

def create_deployment(name: str, namespace: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Create Deployment manifest"""
    
    replicas = spec.get('replicas', 3)
    image = spec.get('image')
    resources = spec.get('resources', {})
    
    return {
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {
            'name': name,
            'namespace': namespace,
            'labels': {
                'app': name,
                'managed-by': 'user-service-operator'
            }
        },
        'spec': {
            'replicas': replicas,
            'selector': {
                'matchLabels': {'app': name}
            },
            'template': {
                'metadata': {
                    'labels': {'app': name}
                },
                'spec': {
                    'containers': [{
                        'name': name,
                        'image': image,
                        'ports': [{'containerPort': 8080}],
                        'env': [
                            {
                                'name': 'DATABASE_URL',
                                'valueFrom': {
                                    'secretKeyRef': {
                                        'name': f'{name}-secret',
                                        'key': 'database-url'
                                    }
                                }
                            }
                        ],
                        'resources': resources,
                        'livenessProbe': {
                            'httpGet': {
                                'path': '/health',
                                'port': 8080
                            },
                            'initialDelaySeconds': 30,
                            'periodSeconds': 10
                        },
                        'readinessProbe': {
                            'httpGet': {
                                'path': '/ready',
                                'port': 8080
                            },
                            'initialDelaySeconds': 5,
                            'periodSeconds': 5
                        }
                    }]
                }
            }
        }
    }

def create_service(name: str, namespace: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Create Service manifest"""
    
    return {
        'apiVersion': 'v1',
        'kind': 'Service',
        'metadata': {
            'name': name,
            'namespace': namespace,
            'labels': {
                'app': name,
                'managed-by': 'user-service-operator'
            }
        },
        'spec': {
            'selector': {'app': name},
            'ports': [{
                'port': 80,
                'targetPort': 8080,
                'protocol': 'TCP'
            }],
            'type': 'ClusterIP'
        }
    }

def create_config_map(name: str, namespace: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Create ConfigMap manifest"""
    
    config_data = spec.get('config', {})
    
    return {
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {
            'name': f'{name}-config',
            'namespace': namespace,
            'labels': {
                'app': name,
                'managed-by': 'user-service-operator'
            }
        },
        'data': config_data
    }

def create_secret(name: str, namespace: str, database_config: Dict[str, Any]) -> Dict[str, Any]:
    """Create Secret manifest"""
    
    return {
        'apiVersion': 'v1',
        'kind': 'Secret',
        'metadata': {
            'name': f'{name}-secret',
            'namespace': namespace,
            'labels': {
                'app': name,
                'managed-by': 'user-service-operator'
            }
        },
        'type': 'Opaque',
        'stringData': {
            'database-url': database_config.get('url', ''),
            'database-password': database_config.get('password', '')
        }
    }

async def create_k8s_resource(create_func, namespace: str, manifest: Dict[str, Any]):
    """Helper to create Kubernetes resource"""
    try:
        response = create_func(namespace, body=manifest)
        logging.info(f"Created {manifest['kind']} {manifest['metadata']['name']}")
        return response
    except kubernetes.client.ApiException as e:
        if e.status == 409:  # Already exists
            logging.warning(f"Resource {manifest['metadata']['name']} already exists")
        else:
            raise

async def wait_for_deployment_ready(name: str, namespace: str, timeout: int = 300):
    """Wait for deployment to be ready"""
    start_time = asyncio.get_event_loop().time()
    
    while (asyncio.get_event_loop().time() - start_time) < timeout:
        try:
            deployment = apps_v1.read_namespaced_deployment(name, namespace)
            
            if (deployment.status.ready_replicas and 
                deployment.status.ready_replicas == deployment.spec.replicas):
                return True
                
        except kubernetes.client.ApiException:
            pass
        
        await asyncio.sleep(5)
    
    raise kopf.TemporaryError(f"Deployment {name} not ready within {timeout} seconds")
```

---

## CI/CD for Distributed Systems

### GitHub Actions CI/CD Pipeline

```yaml
# .github/workflows/ci-cd.yml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

env:
  REGISTRY: registry.company.com
  IMAGE_NAME: user-service

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: testpass
          POSTGRES_DB: testdb
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:6
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
        cache: 'pip'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

    - name: Run linting
      run: |
        flake8 src/ tests/
        black --check src/ tests/
        isort --check-only src/ tests/

    - name: Run type checking
      run: mypy src/

    - name: Run security scan
      run: bandit -r src/

    - name: Run unit tests
      run: |
        pytest tests/unit/ --cov=src --cov-report=xml
      env:
        DATABASE_URL: postgresql://postgres:testpass@localhost:5432/testdb
        REDIS_URL: redis://localhost:6379

    - name: Run integration tests
      run: |
        pytest tests/integration/ --cov-append --cov=src --cov-report=xml
      env:
        DATABASE_URL: postgresql://postgres:testpass@localhost:5432/testdb
        REDIS_URL: redis://localhost:6379

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push'
    
    outputs:
      image-digest: ${{ steps.build.outputs.digest }}
      image-tag: ${{ steps.meta.outputs.tags }}

    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2

    - name: Log in to Container Registry
      uses: docker/login-action@v2
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ secrets.REGISTRY_USERNAME }}
        password: ${{ secrets.REGISTRY_PASSWORD }}

    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v4
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=sha,prefix={{branch}}-
          type=raw,value=latest,enable={{is_default_branch}}

    - name: Build and push Docker image
      id: build
      uses: docker/build-push-action@v4
      with:
        context: .
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
        platforms: linux/amd64,linux/arm64

    - name: Run container security scan
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
        format: 'sarif'
        output: 'trivy-results.sarif'

    - name: Upload security scan results
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: 'trivy-results.sarif'

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'
    environment: staging

    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Set up kubectl
      uses: azure/setup-kubectl@v3

    - name: Configure kubectl
      run: |
        echo "${{ secrets.STAGING_KUBECONFIG }}" | base64 -d > kubeconfig
        export KUBECONFIG=kubeconfig

    - name: Deploy to staging
      run: |
        export KUBECONFIG=kubeconfig
        
        # Update image in kustomization
        cd k8s/overlays/staging
        kustomize edit set image ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
        
        # Apply manifests
        kubectl apply -k .
        
        # Wait for rollout
        kubectl rollout status deployment/user-service -n ecommerce-staging --timeout=300s

    - name: Run smoke tests
      run: |
        export KUBECONFIG=kubeconfig
        
        # Wait for service to be ready
        kubectl wait --for=condition=ready pod -l app=user-service -n ecommerce-staging --timeout=180s
        
        # Run smoke tests
        pytest tests/smoke/ --staging
      env:
        STAGING_URL: https://api.staging.company.com

    - name: Notify deployment
      uses: 8398a7/action-slack@v3
      with:
        status: ${{ job.status }}
        text: "Staging deployment ${{ github.sha }} completed"
      env:
        SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}

  deploy-production:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment: production

    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Set up kubectl
      uses: azure/setup-kubectl@v3

    - name: Configure kubectl
      run: |
        echo "${{ secrets.PROD_KUBECONFIG }}" | base64 -d > kubeconfig
        export KUBECONFIG=kubeconfig

    - name: Deploy to production (Blue-Green)
      run: |
        export KUBECONFIG=kubeconfig
        
        # Run blue-green deployment script
        ./scripts/blue-green-deploy.sh ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}

    - name: Run production health checks
      run: |
        export KUBECONFIG=kubeconfig
        
        # Run comprehensive health checks
        ./scripts/health-check.sh production
        
        # Run production smoke tests
        pytest tests/smoke/ --production
      env:
        PRODUCTION_URL: https://api.company.com

    - name: Notify deployment
      uses: 8398a7/action-slack@v3
      with:
        status: ${{ job.status }}
        text: "Production deployment ${{ github.sha }} completed successfully"
      env:
        SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}

  security-scan:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Run SAST scan
      uses: github/codeql-action/init@v2
      with:
        languages: python

    - name: Perform CodeQL Analysis
      uses: github/codeql-action/analyze@v2

    - name: Run dependency scan
      uses: pypa/gh-action-pip-audit@v1.0.8
      with:
        inputs: requirements.txt

    - name: Run infrastructure scan
      uses: aquasecurity/tfsec-action@v1.0.0
      with:
        soft_fail: true
```

### Blue-Green Deployment Script

```bash
#!/bin/bash
# scripts/blue-green-deploy.sh

set -euo pipefail

IMAGE=$1
NAMESPACE="ecommerce-prod"
SERVICE_NAME="user-service"
DEPLOYMENT_NAME="user-service"

echo "Starting blue-green deployment for $IMAGE"

# Get current deployment color
CURRENT_COLOR=$(kubectl get deployment $DEPLOYMENT_NAME -n $NAMESPACE -o jsonpath='{.metadata.labels.color}' || echo "blue")

# Determine new color
if [ "$CURRENT_COLOR" = "blue" ]; then
    NEW_COLOR="green"
else
    NEW_COLOR="blue"
fi

echo "Current color: $CURRENT_COLOR, New color: $NEW_COLOR"

# Create new deployment with new color
NEW_DEPLOYMENT_NAME="${DEPLOYMENT_NAME}-${NEW_COLOR}"

# Copy current deployment and update it
kubectl get deployment $DEPLOYMENT_NAME -n $NAMESPACE -o yaml | \
    sed "s/name: $DEPLOYMENT_NAME/name: $NEW_DEPLOYMENT_NAME/" | \
    sed "s/color: $CURRENT_COLOR/color: $NEW_COLOR/" | \
    sed "s|image: .*|image: $IMAGE|" | \
    kubectl apply -f -

echo "Created new deployment: $NEW_DEPLOYMENT_NAME"

# Wait for new deployment to be ready
echo "Waiting for new deployment to be ready..."
kubectl rollout status deployment/$NEW_DEPLOYMENT_NAME -n $NAMESPACE --timeout=600s

# Run health checks on new deployment
echo "Running health checks..."
NEW_PODS=$(kubectl get pods -n $NAMESPACE -l app=$SERVICE_NAME,color=$NEW_COLOR -o jsonpath='{.items[*].metadata.name}')

for POD in $NEW_PODS; do
    echo "Health checking pod: $POD"
    kubectl exec -n $NAMESPACE $POD -- curl -f http://localhost:8080/health || {
        echo "Health check failed for $POD"
        exit 1
    }
done

# Update service to point to new deployment
echo "Switching traffic to new deployment..."
kubectl patch service $SERVICE_NAME -n $NAMESPACE -p '{"spec":{"selector":{"color":"'$NEW_COLOR'"}}}'

# Wait for traffic to settle
echo "Waiting for traffic to settle..."
sleep 30

# Run final health checks
echo "Running final health checks..."
SERVICE_IP=$(kubectl get service $SERVICE_NAME -n $NAMESPACE -o jsonpath='{.spec.clusterIP}')
for i in {1..10}; do
    kubectl run health-check-$i --image=curlimages/curl:latest --rm -i --restart=Never -- \
        curl -f http://$SERVICE_IP/health || {
        echo "Final health check failed"
        
        # Rollback
        echo "Rolling back..."
        kubectl patch service $SERVICE_NAME -n $NAMESPACE -p '{"spec":{"selector":{"color":"'$CURRENT_COLOR'"}}}'
        exit 1
    }
done

echo "Health checks passed, cleaning up old deployment..."

# Delete old deployment
OLD_DEPLOYMENT_NAME="${DEPLOYMENT_NAME}-${CURRENT_COLOR}"
if kubectl get deployment $OLD_DEPLOYMENT_NAME -n $NAMESPACE > /dev/null 2>&1; then
    kubectl delete deployment $OLD_DEPLOYMENT_NAME -n $NAMESPACE
fi

# Rename new deployment to standard name
kubectl patch deployment $NEW_DEPLOYMENT_NAME -n $NAMESPACE -p '{"metadata":{"name":"'$DEPLOYMENT_NAME'"}}'

echo "Blue-green deployment completed successfully!"

# Send metrics to monitoring
curl -X POST "https://metrics.company.com/api/events" \
    -H "Content-Type: application/json" \
    -d '{
        "event": "deployment_completed",
        "service": "'$SERVICE_NAME'",
        "environment": "production",
        "strategy": "blue-green",
        "image": "'$IMAGE'",
        "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
    }' || echo "Failed to send metrics"
```

---

## GitOps and Infrastructure as Code

### ArgoCD Application Configuration

```yaml
# gitops/applications/user-service.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: user-service
  namespace: argocd
  labels:
    environment: production
    team: backend
spec:
  project: ecommerce
  source:
    repoURL: https://github.com/company/user-service-config
    targetRevision: main
    path: k8s/overlays/production
  destination:
    server: https://kubernetes.default.svc
    namespace: ecommerce-prod
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
      allowEmpty: false
    syncOptions:
    - CreateNamespace=true
    - PrunePropagationPolicy=foreground
    - PruneLast=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
  revisionHistoryLimit: 3
  ignoreDifferences:
  - group: apps
    kind: Deployment
    jsonPointers:
    - /spec/replicas
---
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: ecommerce
  namespace: argocd
spec:
  description: E-commerce platform applications
  sourceRepos:
  - https://github.com/company/*
  destinations:
  - namespace: ecommerce-*
    server: https://kubernetes.default.svc
  clusterResourceWhitelist:
  - group: ''
    kind: Namespace
  - group: 'rbac.authorization.k8s.io'
    kind: ClusterRole
  - group: 'rbac.authorization.k8s.io'
    kind: ClusterRoleBinding
  namespaceResourceWhitelist:
  - group: ''
    kind: ConfigMap
  - group: ''
    kind: Secret
  - group: ''
    kind: Service
  - group: 'apps'
    kind: Deployment
  - group: 'apps'
    kind: ReplicaSet
  - group: 'networking.k8s.io'
    kind: NetworkPolicy
  - group: 'policy'
    kind: PodDisruptionBudget
  roles:
  - name: developers
    description: Developers can sync applications
    policies:
    - p, proj:ecommerce:developers, applications, sync, ecommerce/*, allow
    groups:
    - company:developers
  - name: admins
    description: Admins have full access
    policies:
    - p, proj:ecommerce:admins, applications, *, ecommerce/*, allow
    groups:
    - company:platform-team
```

### Terraform Infrastructure Configuration

```hcl
# terraform/modules/kubernetes-cluster/main.tf
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.20"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.10"
    }
  }
}

# EKS Cluster
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = var.cluster_name
  cluster_version = var.kubernetes_version

  vpc_id                         = var.vpc_id
  subnet_ids                     = var.subnet_ids
  cluster_endpoint_public_access = var.cluster_endpoint_public_access

  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent = true
    }
  }

  eks_managed_node_groups = {
    main = {
      min_size     = var.node_group_min_size
      max_size     = var.node_group_max_size
      desired_size = var.node_group_desired_size

      instance_types = var.node_instance_types
      capacity_type  = "SPOT"

      k8s_labels = {
        Environment   = var.environment
        NodeGroup     = "main"
        WorkloadType  = "general"
      }

      taints = {
        dedicated = {
          key    = "workload"
          value  = var.environment
          effect = "NO_SCHEDULE"
        }
      }

      tags = var.tags
    }

    monitoring = {
      min_size     = 1
      max_size     = 3
      desired_size = 2

      instance_types = ["t3.large"]
      capacity_type  = "ON_DEMAND"

      k8s_labels = {
        Environment  = var.environment
        NodeGroup    = "monitoring"
        WorkloadType = "monitoring"
      }

      taints = {
        monitoring = {
          key    = "workload"
          value  = "monitoring"
          effect = "NO_SCHEDULE"
        }
      }
    }
  }

  manage_aws_auth_configmap = true
  aws_auth_roles = [
    {
      rolearn  = aws_iam_role.cluster_admin.arn
      username = "cluster-admin"
      groups   = ["system:masters"]
    },
  ]

  tags = var.tags
}

# IAM Role for cluster administration
resource "aws_iam_role" "cluster_admin" {
  name = "${var.cluster_name}-cluster-admin"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = var.admin_role_arns
        }
      }
    ]
  })

  tags = var.tags
}

# Install ArgoCD
resource "helm_release" "argocd" {
  depends_on = [module.eks]

  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = "5.34.6"
  namespace  = "argocd"

  create_namespace = true
  wait             = true
  timeout          = 600

  values = [
    templatefile("${path.module}/argocd-values.yaml", {
      hostname = var.argocd_hostname
    })
  ]
}

# Install Istio
resource "helm_release" "istio_base" {
  depends_on = [module.eks]

  name       = "istio-base"
  repository = "https://istio-release.storage.googleapis.com/charts"
  chart      = "base"
  version    = "1.18.1"
  namespace  = "istio-system"

  create_namespace = true
  wait             = true
  timeout          = 300
}

resource "helm_release" "istiod" {
  depends_on = [helm_release.istio_base]

  name       = "istiod"
  repository = "https://istio-release.storage.googleapis.com/charts"
  chart      = "istiod"
  version    = "1.18.1"
  namespace  = "istio-system"

  wait    = true
  timeout = 600

  values = [
    file("${path.module}/istiod-values.yaml")
  ]
}

# Install Prometheus Operator
resource "helm_release" "prometheus_operator" {
  depends_on = [module.eks]

  name       = "prometheus-operator"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  version    = "48.3.1"
  namespace  = "monitoring"

  create_namespace = true
  wait             = true
  timeout          = 600

  values = [
    templatefile("${path.module}/prometheus-values.yaml", {
      environment = var.environment
      cluster_name = var.cluster_name
    })
  ]
}

# Outputs
output "cluster_id" {
  description = "EKS cluster ID"
  value       = module.eks.cluster_id
}

output "cluster_arn" {
  description = "EKS cluster ARN"
  value       = module.eks.cluster_arn
}

output "cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = module.eks.cluster_endpoint
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = module.eks.cluster_security_group_id
}
```

---

## Deployment Strategies

### Canary Deployment with Istio

```yaml
# deployments/canary/virtual-service.yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: user-service
  namespace: ecommerce-prod
spec:
  hosts:
  - user-service
  http:
  - match:
    - headers:
        canary:
          exact: "true"
    route:
    - destination:
        host: user-service
        subset: v2
      weight: 100
  - route:
    - destination:
        host: user-service
        subset: v1
      weight: 90
    - destination:
        host: user-service
        subset: v2
      weight: 10
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: user-service
  namespace: ecommerce-prod
spec:
  host: user-service
  subsets:
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v2
    trafficPolicy:
      circuitBreaker:
        consecutiveErrors: 3
        interval: 30s
        baseEjectionTime: 30s
---
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: user-service-rollout
  namespace: ecommerce-prod
spec:
  replicas: 10
  strategy:
    canary:
      maxSurge: "25%"
      maxUnavailable: 0
      canaryService: user-service-canary
      stableService: user-service-stable
      trafficRouting:
        istio:
          virtualService:
            name: user-service
            routes:
            - primary
          destinationRule:
            name: user-service
            canarySubsetName: v2
            stableSubsetName: v1
      steps:
      - setWeight: 5
      - pause: {duration: 2m}
      - analysis:
          templates:
          - templateName: success-rate
          args:
          - name: service-name
            value: user-service
      - setWeight: 20
      - pause: {duration: 2m}
      - analysis:
          templates:
          - templateName: success-rate
          - templateName: latency-check
          args:
          - name: service-name
            value: user-service
      - setWeight: 50
      - pause: {duration: 5m}
      - setWeight: 100
      - pause: {duration: 2m}
  selector:
    matchLabels:
      app: user-service
  template:
    metadata:
      labels:
        app: user-service
    spec:
      containers:
      - name: user-service
        image: registry.company.com/user-service:latest
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: 200m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
---
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: success-rate
  namespace: ecommerce-prod
spec:
  args:
  - name: service-name
  metrics:
  - name: success-rate
    interval: 1m
    count: 5
    successCondition: result[0] >= 0.95
    failureLimit: 3
    provider:
      prometheus:
        address: http://prometheus:9090
        query: |
          sum(rate(http_requests_total{service="{{args.service-name}}",code!~"5.."}[2m])) /
          sum(rate(http_requests_total{service="{{args.service-name}}"}[2m]))
---
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: latency-check
  namespace: ecommerce-prod
spec:
  args:
  - name: service-name
  metrics:
  - name: p95-latency
    interval: 1m
    count: 3
    successCondition: result[0] <= 1000
    failureLimit: 2
    provider:
      prometheus:
        address: http://prometheus:9090
        query: |
          histogram_quantile(0.95,
            sum(rate(http_request_duration_seconds_bucket{service="{{args.service-name}}"}[2m])) by (le)
          ) * 1000
```

---

## Secrets Management

### External Secrets Operator Configuration

```yaml
# secrets/external-secrets/cluster-secret-store.yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-west-2
      auth:
        secretRef:
          accessKeyID:
            name: aws-credentials
            key: access-key-id
            namespace: external-secrets
          secretAccessKey:
            name: aws-credentials
            key: secret-access-key
            namespace: external-secrets
---
# secrets/external-secrets/external-secret.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: user-service-secrets
  namespace: ecommerce-prod
spec:
  refreshInterval: 15m
  secretStoreRef:
    kind: ClusterSecretStore
    name: aws-secrets-manager
  target:
    name: user-service-secrets
    creationPolicy: Owner
    template:
      type: Opaque
      data:
        database-url: "postgresql://{{ .database_username }}:{{ .database_password }}@{{ .database_host }}:5432/{{ .database_name }}"
        redis-url: "redis://{{ .redis_password }}@{{ .redis_host }}:6379"
        jwt-secret: "{{ .jwt_secret }}"
        api-key: "{{ .api_key }}"
  data:
  - secretKey: database_username
    remoteRef:
      key: ecommerce/database/user-service
      property: username
  - secretKey: database_password
    remoteRef:
      key: ecommerce/database/user-service
      property: password
  - secretKey: database_host
    remoteRef:
      key: ecommerce/database/user-service
      property: host
  - secretKey: database_name
    remoteRef:
      key: ecommerce/database/user-service
      property: database
  - secretKey: redis_password
    remoteRef:
      key: ecommerce/cache/redis
      property: password
  - secretKey: redis_host
    remoteRef:
      key: ecommerce/cache/redis
      property: host
  - secretKey: jwt_secret
    remoteRef:
      key: ecommerce/auth/jwt
      property: secret
  - secretKey: api_key
    remoteRef:
      key: ecommerce/external/payment-service
      property: api_key
```

### Vault Integration for Development

```python
# secrets/vault_client.py
import hvac
import os
from typing import Dict, Any, Optional
import logging

class VaultClient:
    def __init__(self, vault_url: str, vault_token: Optional[str] = None):
        self.vault_url = vault_url
        self.client = hvac.Client(url=vault_url)
        
        if vault_token:
            self.client.token = vault_token
        else:
            self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Vault using Kubernetes service account"""
        try:
            # Try Kubernetes auth first
            jwt_token_path = '/var/run/secrets/kubernetes.io/serviceaccount/token'
            if os.path.exists(jwt_token_path):
                with open(jwt_token_path, 'r') as token_file:
                    jwt_token = token_file.read().strip()
                
                auth_response = self.client.auth.kubernetes.login(
                    role='user-service',
                    jwt=jwt_token
                )
                
                self.client.token = auth_response['auth']['client_token']
                logging.info("Authenticated with Vault using Kubernetes auth")
                return
        
        except Exception as e:
            logging.warning(f"Kubernetes auth failed: {e}")
        
        # Fallback to token from environment
        vault_token = os.getenv('VAULT_TOKEN')
        if vault_token:
            self.client.token = vault_token
            logging.info("Using Vault token from environment")
        else:
            raise RuntimeError("No authentication method available for Vault")
    
    def get_secret(self, path: str, mount_point: str = 'secret') -> Optional[Dict[str, Any]]:
        """Get secret from Vault"""
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=mount_point
            )
            return response['data']['data']
        
        except Exception as e:
            logging.error(f"Failed to get secret {path}: {e}")
            return None
    
    def put_secret(self, path: str, secret_dict: Dict[str, Any], 
                  mount_point: str = 'secret') -> bool:
        """Put secret to Vault"""
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=secret_dict,
                mount_point=mount_point
            )
            logging.info(f"Successfully stored secret at {path}")
            return True
        
        except Exception as e:
            logging.error(f"Failed to store secret {path}: {e}")
            return False
    
    def delete_secret(self, path: str, mount_point: str = 'secret') -> bool:
        """Delete secret from Vault"""
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path,
                mount_point=mount_point
            )
            logging.info(f"Successfully deleted secret at {path}")
            return True
        
        except Exception as e:
            logging.error(f"Failed to delete secret {path}: {e}")
            return False
    
    def create_policy(self, name: str, policy: str) -> bool:
        """Create or update Vault policy"""
        try:
            self.client.sys.create_or_update_policy(
                name=name,
                policy=policy
            )
            logging.info(f"Successfully created/updated policy {name}")
            return True
        
        except Exception as e:
            logging.error(f"Failed to create policy {name}: {e}")
            return False

# Example usage in application
class SecretManager:
    def __init__(self):
        self.vault_client = None
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
        
        # Initialize Vault client if in production
        if os.getenv('ENVIRONMENT') == 'production':
            vault_url = os.getenv('VAULT_URL', 'https://vault.company.com')
            self.vault_client = VaultClient(vault_url)
    
    async def get_secret(self, key: str) -> Optional[str]:
        """Get secret value by key"""
        
        # Check cache first
        if key in self.cache:
            secret_data, timestamp = self.cache[key]
            if time.time() - timestamp < self.cache_ttl:
                return secret_data
        
        # Try Vault if available
        if self.vault_client:
            try:
                secret_path = f"ecommerce/user-service/{key}"
                secret_data = self.vault_client.get_secret(secret_path)
                
                if secret_data and 'value' in secret_data:
                    value = secret_data['value']
                    self.cache[key] = (value, time.time())
                    return value
                    
            except Exception as e:
                logging.warning(f"Failed to get secret {key} from Vault: {e}")
        
        # Fallback to environment variable
        env_value = os.getenv(key.upper().replace('-', '_'))
        if env_value:
            self.cache[key] = (env_value, time.time())
            return env_value
        
        logging.error(f"Secret {key} not found in any source")
        return None
    
    async def rotate_secret(self, key: str, new_value: str) -> bool:
        """Rotate secret value"""
        if not self.vault_client:
            logging.error("Secret rotation requires Vault")
            return False
        
        try:
            secret_path = f"ecommerce/user-service/{key}"
            
            # Store new secret
            success = self.vault_client.put_secret(secret_path, {'value': new_value})
            
            if success:
                # Clear cache to force refresh
                if key in self.cache:
                    del self.cache[key]
                
                logging.info(f"Successfully rotated secret {key}")
                return True
            
        except Exception as e:
            logging.error(f"Failed to rotate secret {key}: {e}")
        
        return False

# Example application integration
async def main():
    secret_manager = SecretManager()
    
    # Get database credentials
    db_password = await secret_manager.get_secret('database-password')
    redis_password = await secret_manager.get_secret('redis-password')
    jwt_secret = await secret_manager.get_secret('jwt-secret')
    
    if not all([db_password, redis_password, jwt_secret]):
        raise RuntimeError("Required secrets not found")
    
    # Use secrets to configure application
    database_url = f"postgresql://user:{db_password}@db:5432/userdb"
    redis_url = f"redis://:{redis_password}@redis:6379"
    
    print("Application configured with secrets from Vault")
```

I'll continue with the remaining sections and then create Module 10. Let me know when you'd like me to continue with the complete Module 09 and then create Module 10: Organizational Patterns.

---

*This covers the essential deployment and operations patterns for production-ready distributed systems. The module includes comprehensive CI/CD pipelines, GitOps workflows, deployment strategies, and secrets management - all critical for operational excellence.*