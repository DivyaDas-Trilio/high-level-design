# Cloud-Native Database & DevOps Patterns

## Cloud Database Services Overview

### AWS Database Services
```python
import boto3
from sqlalchemy import create_engine
import pymysql
import psycopg2

class AWSRDSConnection:
    """Manage AWS RDS connections with best practices"""
    
    def __init__(self, region='us-west-2'):
        self.region = region
        self.rds_client = boto3.client('rds', region_name=region)
        self.secretsmanager = boto3.client('secretsmanager', region_name=region)
    
    def get_rds_credentials(self, secret_name: str):
        """Retrieve RDS credentials from AWS Secrets Manager"""
        try:
            response = self.secretsmanager.get_secret_value(SecretId=secret_name)
            secret = json.loads(response['SecretString'])
            return secret
        except Exception as e:
            raise Exception(f"Failed to retrieve credentials: {e}")
    
    def create_aurora_engine(self, cluster_identifier: str, secret_name: str):
        """Create engine for Aurora cluster with read/write endpoints"""
        credentials = self.get_rds_credentials(secret_name)
        
        # Get cluster endpoints
        cluster_info = self.rds_client.describe_db_clusters(
            DBClusterIdentifier=cluster_identifier
        )
        cluster = cluster_info['DBClusters'][0]
        
        writer_endpoint = cluster['Endpoint']
        reader_endpoint = cluster['ReaderEndpoint']
        
        # Writer engine
        writer_engine = create_engine(
            f"postgresql://{credentials['username']}:{credentials['password']}"
            f"@{writer_endpoint}:{credentials['port']}/{credentials['dbname']}",
            pool_size=20,
            max_overflow=30,
            pool_recycle=3600,
            pool_pre_ping=True
        )
        
        # Reader engine
        reader_engine = create_engine(
            f"postgresql://{credentials['username']}:{credentials['password']}"
            f"@{reader_endpoint}:{credentials['port']}/{credentials['dbname']}",
            pool_size=15,
            max_overflow=25,
            pool_recycle=3600,
            pool_pre_ping=True
        )
        
        return writer_engine, reader_engine

# Aurora Serverless integration
class AuroraServerlessManager:
    """Manage Aurora Serverless databases"""
    
    def __init__(self, region='us-west-2'):
        self.region = region
        self.rds_data = boto3.client('rds-data', region_name=region)
    
    def execute_statement(self, cluster_arn: str, secret_arn: str, 
                         database: str, sql: str, parameters=None):
        """Execute SQL statement on Aurora Serverless"""
        try:
            request = {
                'resourceArn': cluster_arn,
                'secretArn': secret_arn,
                'database': database,
                'sql': sql
            }
            
            if parameters:
                request['parameters'] = parameters
            
            response = self.rds_data.execute_statement(**request)
            return response
            
        except Exception as e:
            raise Exception(f"Failed to execute statement: {e}")
    
    def begin_transaction(self, cluster_arn: str, secret_arn: str, database: str):
        """Begin transaction in Aurora Serverless"""
        return self.rds_data.begin_transaction(
            resourceArn=cluster_arn,
            secretArn=secret_arn,
            database=database
        )
```

### Google Cloud SQL Integration
```python
from google.cloud import secretmanager
from google.cloud.sql.connector import Connector
import sqlalchemy

class GoogleCloudSQLManager:
    """Manage Google Cloud SQL connections"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.connector = Connector()
        self.secret_client = secretmanager.SecretManagerServiceClient()
    
    def get_secret(self, secret_id: str, version_id="latest"):
        """Get secret from Secret Manager"""
        name = f"projects/{self.project_id}/secrets/{secret_id}/versions/{version_id}"
        response = self.secret_client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    
    def create_cloud_sql_engine(self, instance_connection_name: str, 
                               db_user: str, db_pass: str, db_name: str):
        """Create engine for Cloud SQL with connector"""
        
        def getconn():
            return self.connector.connect(
                instance_connection_name,
                "pg8000",
                user=db_user,
                password=db_pass,
                db=db_name
            )
        
        engine = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=getconn,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=1800
        )
        
        return engine
    
    def cleanup(self):
        """Cleanup connector"""
        self.connector.close()

# Cloud SQL Proxy configuration
class CloudSQLProxy:
    """Manage Cloud SQL Proxy connections"""
    
    def __init__(self):
        self.proxy_process = None
    
    def start_proxy(self, instance_connection_string: str, port: int = 5432):
        """Start Cloud SQL Proxy"""
        import subprocess
        
        cmd = [
            "cloud_sql_proxy",
            f"-instances={instance_connection_string}=tcp:{port}"
        ]
        
        self.proxy_process = subprocess.Popen(cmd)
        time.sleep(3)  # Wait for proxy to start
        
        return f"localhost:{port}"
    
    def stop_proxy(self):
        """Stop Cloud SQL Proxy"""
        if self.proxy_process:
            self.proxy_process.terminate()
            self.proxy_process.wait()
```

### Azure Database Integration
```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import pyodbc

class AzureDatabaseManager:
    """Manage Azure Database connections"""
    
    def __init__(self, key_vault_url: str):
        self.credential = DefaultAzureCredential()
        self.secret_client = SecretClient(vault_url=key_vault_url, credential=self.credential)
    
    def get_secret(self, secret_name: str):
        """Get secret from Azure Key Vault"""
        secret = self.secret_client.get_secret(secret_name)
        return secret.value
    
    def create_azure_sql_engine(self, server: str, database: str, 
                               username_secret: str, password_secret: str):
        """Create engine for Azure SQL Database"""
        username = self.get_secret(username_secret)
        password = self.get_secret(password_secret)
        
        # Azure SQL connection string
        connection_string = (
            f"mssql+pyodbc://{username}:{password}@{server}.database.windows.net:1433/"
            f"{database}?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes"
            "&TrustServerCertificate=no&Connection+Timeout=30"
        )
        
        engine = create_engine(
            connection_string,
            pool_size=20,
            max_overflow=30,
            pool_timeout=30,
            pool_recycle=3600
        )
        
        return engine
    
    def create_cosmosdb_connection(self, account_url: str, key_secret: str):
        """Create Azure Cosmos DB connection"""
        from azure.cosmos import CosmosClient
        
        key = self.get_secret(key_secret)
        client = CosmosClient(account_url, key)
        
        return client
```

## Infrastructure as Code (IaC)

### Terraform Database Infrastructure
```hcl
# terraform/modules/rds/main.tf
resource "aws_db_subnet_group" "main" {
  name       = "${var.environment}-db-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name        = "${var.environment} DB subnet group"
    Environment = var.environment
  }
}

resource "aws_security_group" "rds" {
  name        = "${var.environment}-rds-sg"
  description = "Security group for RDS instances"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.app_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.environment}-rds-sg"
    Environment = var.environment
  }
}

resource "aws_rds_cluster_parameter_group" "main" {
  family = "aurora-postgresql14"
  name   = "${var.environment}-aurora-cluster-pg"

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements,pg_hint_plan"
  }

  parameter {
    name  = "log_statement"
    value = "all"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # Log queries taking more than 1 second
  }
}

resource "aws_rds_cluster" "main" {
  cluster_identifier      = "${var.environment}-aurora-cluster"
  engine                 = "aurora-postgresql"
  engine_version         = "14.6"
  database_name          = var.database_name
  master_username        = var.master_username
  manage_master_user_password = true
  
  backup_retention_period = var.backup_retention_period
  preferred_backup_window = "07:00-09:00"
  preferred_maintenance_window = "sun:09:00-sun:10:00"
  
  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.main.name
  db_subnet_group_name           = aws_db_subnet_group.main.name
  vpc_security_group_ids         = [aws_security_group.rds.id]
  
  storage_encrypted = true
  kms_key_id       = var.kms_key_id
  
  enabled_cloudwatch_logs_exports = ["postgresql"]
  
  deletion_protection = var.environment == "production" ? true : false
  skip_final_snapshot = var.environment != "production"
  
  tags = {
    Name        = "${var.environment}-aurora-cluster"
    Environment = var.environment
  }
}

resource "aws_rds_cluster_instance" "main" {
  count              = var.instance_count
  identifier         = "${var.environment}-aurora-instance-${count.index}"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = var.instance_class
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version
  
  performance_insights_enabled    = true
  performance_insights_kms_key_id = var.kms_key_id
  monitoring_interval             = 60
  monitoring_role_arn            = aws_iam_role.rds_enhanced_monitoring.arn
  
  tags = {
    Name        = "${var.environment}-aurora-instance-${count.index}"
    Environment = var.environment
  }
}

# Enhanced monitoring role
resource "aws_iam_role" "rds_enhanced_monitoring" {
  name = "${var.environment}-rds-enhanced-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring" {
  role       = aws_iam_role.rds_enhanced_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}
```

```hcl
# terraform/modules/rds/variables.tf
variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where RDS will be deployed"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for RDS"
  type        = list(string)
}

variable "app_security_group_id" {
  description = "Security group ID of application servers"
  type        = string
}

variable "database_name" {
  description = "Name of the database"
  type        = string
  default     = "appdb"
}

variable "master_username" {
  description = "Master username for RDS"
  type        = string
  default     = "dbadmin"
}

variable "instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.r6g.large"
}

variable "instance_count" {
  description = "Number of RDS instances"
  type        = number
  default     = 2
}

variable "backup_retention_period" {
  description = "Backup retention period in days"
  type        = number
  default     = 30
}

variable "kms_key_id" {
  description = "KMS key ID for encryption"
  type        = string
}
```

### Kubernetes Database Deployment
```yaml
# k8s/postgres-cluster.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: postgres-config
  namespace: database
data:
  postgresql.conf: |
    # Connection settings
    max_connections = 200
    shared_buffers = 256MB
    effective_cache_size = 1GB
    maintenance_work_mem = 64MB
    checkpoint_completion_target = 0.9
    wal_buffers = 16MB
    default_statistics_target = 100
    random_page_cost = 1.1
    effective_io_concurrency = 200
    work_mem = 4MB
    min_wal_size = 1GB
    max_wal_size = 4GB
    
    # Logging
    log_destination = 'stderr'
    logging_collector = on
    log_directory = 'pg_log'
    log_statement = 'all'
    log_min_duration_statement = 1000
    log_checkpoints = on
    log_connections = on
    log_disconnections = on
    log_lock_waits = on
    log_temp_files = 10MB

---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres-primary
  namespace: database
spec:
  serviceName: postgres-primary-service
  replicas: 1
  selector:
    matchLabels:
      app: postgres-primary
      role: master
  template:
    metadata:
      labels:
        app: postgres-primary
        role: master
    spec:
      containers:
      - name: postgres
        image: postgres:14.6-alpine
        env:
        - name: POSTGRES_DB
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: database
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: username
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: password
        - name: POSTGRES_REPLICATION_USER
          value: "replicator"
        - name: POSTGRES_REPLICATION_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: replication_password
        ports:
        - containerPort: 5432
          name: postgres
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        - name: postgres-config
          mountPath: /etc/postgresql/postgresql.conf
          subPath: postgresql.conf
        resources:
          requests:
            memory: 512Mi
            cpu: 250m
          limits:
            memory: 2Gi
            cpu: 1000m
        livenessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - $(POSTGRES_USER)
            - -d
            - $(POSTGRES_DB)
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command:
            - pg_isready
            - -U
            - $(POSTGRES_USER)
            - -d
            - $(POSTGRES_DB)
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: postgres-config
        configMap:
          name: postgres-config
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: "fast-ssd"
      resources:
        requests:
          storage: 100Gi

---
apiVersion: v1
kind: Service
metadata:
  name: postgres-primary-service
  namespace: database
spec:
  selector:
    app: postgres-primary
    role: master
  ports:
  - port: 5432
    targetPort: 5432
    name: postgres
  type: ClusterIP
```

## Database CI/CD Pipelines

### GitHub Actions Pipeline
```yaml
# .github/workflows/database-ci-cd.yml
name: Database CI/CD

on:
  push:
    branches: [main, develop]
    paths:
    - 'migrations/**'
    - 'database/**'
  pull_request:
    branches: [main]
    paths:
    - 'migrations/**'
    - 'database/**'

env:
  PYTHON_VERSION: '3.11'
  POETRY_VERSION: '1.4.0'

jobs:
  database-tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: testpass
          POSTGRES_USER: testuser
          POSTGRES_DB: testdb
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
        - 5432:5432
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ env.PYTHON_VERSION }}
    
    - name: Install Poetry
      uses: snok/install-poetry@v1
      with:
        version: ${{ env.POETRY_VERSION }}
    
    - name: Install dependencies
      run: poetry install
    
    - name: Run database migrations
      env:
        DATABASE_URL: postgresql://testuser:testpass@localhost:5432/testdb
      run: |
        poetry run alembic upgrade head
    
    - name: Run database tests
      env:
        DATABASE_URL: postgresql://testuser:testpass@localhost:5432/testdb
      run: |
        poetry run pytest tests/database/ -v --cov=database
    
    - name: Run migration tests
      env:
        DATABASE_URL: postgresql://testuser:testpass@localhost:5432/testdb
      run: |
        poetry run pytest tests/migrations/ -v
    
    - name: Validate schema
      env:
        DATABASE_URL: postgresql://testuser:testpass@localhost:5432/testdb
      run: |
        poetry run python scripts/validate_schema.py

  security-scan:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        scan-type: 'fs'
        scan-ref: '.'
        format: 'sarif'
        output: 'trivy-results.sarif'
    
    - name: Upload Trivy scan results
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: 'trivy-results.sarif'

  deploy-staging:
    if: github.ref == 'refs/heads/develop'
    needs: [database-tests, security-scan]
    runs-on: ubuntu-latest
    environment: staging
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: us-west-2
    
    - name: Run database migrations on staging
      env:
        DATABASE_URL: ${{ secrets.STAGING_DATABASE_URL }}
      run: |
        poetry install
        poetry run alembic upgrade head
    
    - name: Run post-deployment tests
      env:
        DATABASE_URL: ${{ secrets.STAGING_DATABASE_URL }}
      run: |
        poetry run pytest tests/integration/ -v

  deploy-production:
    if: github.ref == 'refs/heads/main'
    needs: [database-tests, security-scan]
    runs-on: ubuntu-latest
    environment: production
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: us-west-2
    
    - name: Create database backup
      run: |
        aws rds create-db-cluster-snapshot \
          --db-cluster-identifier production-aurora-cluster \
          --db-cluster-snapshot-identifier "backup-$(date +%Y%m%d-%H%M%S)"
    
    - name: Wait for backup completion
      run: |
        aws rds wait db-cluster-snapshot-completed \
          --db-cluster-snapshot-identifier "backup-$(date +%Y%m%d-%H%M%S)"
    
    - name: Run database migrations on production
      env:
        DATABASE_URL: ${{ secrets.PRODUCTION_DATABASE_URL }}
      run: |
        poetry install
        poetry run alembic upgrade head
    
    - name: Run smoke tests
      env:
        DATABASE_URL: ${{ secrets.PRODUCTION_DATABASE_URL }}
      run: |
        poetry run pytest tests/smoke/ -v
```

### Database Migration Safety Checks
```python
# scripts/migration_safety_checker.py
import sqlalchemy as sa
from sqlalchemy import text
import re
from typing import List, Dict, Any

class MigrationSafetyChecker:
    """Check database migrations for potentially dangerous operations"""
    
    DANGEROUS_OPERATIONS = [
        'DROP TABLE',
        'DROP COLUMN',
        'ALTER COLUMN.*DROP NOT NULL',
        'ALTER COLUMN.*TYPE',
        'DROP INDEX',
        'DROP CONSTRAINT'
    ]
    
    BLOCKING_OPERATIONS = [
        'ALTER TABLE.*ADD COLUMN.*NOT NULL',
        'CREATE INDEX(?!.*CONCURRENTLY)',
        'ALTER TABLE.*ADD CONSTRAINT.*FOREIGN KEY'
    ]
    
    def __init__(self, database_url: str):
        self.engine = sa.create_engine(database_url)
    
    def check_migration_file(self, migration_content: str) -> Dict[str, List[str]]:
        """Check migration file for dangerous operations"""
        issues = {
            'dangerous': [],
            'blocking': [],
            'warnings': []
        }
        
        lines = migration_content.split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line_upper = line.upper().strip()
            
            # Check for dangerous operations
            for pattern in self.DANGEROUS_OPERATIONS:
                if re.search(pattern, line_upper):
                    issues['dangerous'].append(
                        f"Line {line_num}: Potentially dangerous operation: {line.strip()}"
                    )
            
            # Check for blocking operations
            for pattern in self.BLOCKING_OPERATIONS:
                if re.search(pattern, line_upper):
                    issues['blocking'].append(
                        f"Line {line_num}: Potentially blocking operation: {line.strip()}"
                    )
            
            # Check for missing CONCURRENTLY on index creation
            if 'CREATE INDEX' in line_upper and 'CONCURRENTLY' not in line_upper:
                issues['warnings'].append(
                    f"Line {line_num}: Consider using CREATE INDEX CONCURRENTLY: {line.strip()}"
                )
        
        return issues
    
    def check_table_size(self, table_name: str) -> int:
        """Check table size to determine if operations might be slow"""
        with self.engine.connect() as conn:
            result = conn.execute(text(
                "SELECT pg_total_relation_size(relid) as size "
                "FROM pg_stat_user_tables WHERE relname = :table_name"
            ), {"table_name": table_name})
            row = result.fetchone()
            return row[0] if row else 0
    
    def suggest_safe_alternatives(self, issues: Dict[str, List[str]]) -> List[str]:
        """Suggest safer alternatives for dangerous operations"""
        suggestions = []
        
        for issue in issues['dangerous']:
            if 'DROP COLUMN' in issue:
                suggestions.append(
                    "Instead of DROP COLUMN, consider:\n"
                    "1. First migration: ALTER COLUMN SET DEFAULT NULL, make nullable\n"
                    "2. Deploy application without using the column\n"
                    "3. Second migration: DROP COLUMN"
                )
            
            elif 'ALTER COLUMN.*TYPE' in issue:
                suggestions.append(
                    "For column type changes:\n"
                    "1. Add new column with new type\n"
                    "2. Backfill data to new column\n"
                    "3. Update application to use new column\n"
                    "4. Drop old column"
                )
        
        return suggestions

# Usage in CI/CD
def validate_migration_safety():
    """Validate migration safety in CI/CD pipeline"""
    import sys
    import glob
    
    checker = MigrationSafetyChecker(os.getenv('DATABASE_URL'))
    
    # Find all migration files
    migration_files = glob.glob('migrations/versions/*.py')
    
    total_issues = 0
    
    for file_path in migration_files:
        with open(file_path, 'r') as f:
            content = f.read()
        
        issues = checker.check_migration_file(content)
        
        if any(issues.values()):
            print(f"\n🚨 Issues found in {file_path}:")
            
            for issue_type, issue_list in issues.items():
                if issue_list:
                    print(f"\n{issue_type.upper()}:")
                    for issue in issue_list:
                        print(f"  - {issue}")
                        total_issues += 1
            
            suggestions = checker.suggest_safe_alternatives(issues)
            if suggestions:
                print(f"\n💡 Suggestions:")
                for suggestion in suggestions:
                    print(f"  {suggestion}")
    
    if total_issues > 0:
        print(f"\n❌ Found {total_issues} potential issues in migrations")
        sys.exit(1)
    else:
        print("\n✅ All migrations passed safety checks")

if __name__ == "__main__":
    validate_migration_safety()
```

## Database Monitoring & Observability

### Prometheus Metrics Collection
```python
# monitoring/database_metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time
import psutil
import sqlalchemy as sa
from functools import wraps

# Prometheus metrics
DB_CONNECTIONS_ACTIVE = Gauge(
    'db_connections_active_total',
    'Number of active database connections',
    ['database', 'host']
)

DB_CONNECTIONS_IDLE = Gauge(
    'db_connections_idle_total', 
    'Number of idle database connections',
    ['database', 'host']
)

DB_QUERY_DURATION = Histogram(
    'db_query_duration_seconds',
    'Database query execution time',
    ['query_type', 'table', 'status'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
)

DB_QUERY_TOTAL = Counter(
    'db_queries_total',
    'Total database queries executed',
    ['query_type', 'table', 'status']
)

DB_SLOW_QUERIES = Counter(
    'db_slow_queries_total',
    'Number of slow queries (>1s)',
    ['query_type', 'table']
)

DB_POOL_SIZE = Gauge(
    'db_pool_size_current',
    'Current database connection pool size',
    ['database', 'pool_type']
)

class DatabaseMonitor:
    """Monitor database performance and metrics"""
    
    def __init__(self, engine: sa.Engine, slow_query_threshold: float = 1.0):
        self.engine = engine
        self.slow_query_threshold = slow_query_threshold
    
    def monitor_query(self, query_type: str = 'unknown', table: str = 'unknown'):
        """Decorator to monitor database queries"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                status = 'success'
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    status = 'error'
                    raise
                finally:
                    duration = time.time() - start_time
                    
                    # Record metrics
                    DB_QUERY_DURATION.labels(
                        query_type=query_type,
                        table=table,
                        status=status
                    ).observe(duration)
                    
                    DB_QUERY_TOTAL.labels(
                        query_type=query_type,
                        table=table,
                        status=status
                    ).inc()
                    
                    # Track slow queries
                    if duration > self.slow_query_threshold:
                        DB_SLOW_QUERIES.labels(
                            query_type=query_type,
                            table=table
                        ).inc()
            
            return wrapper
        return decorator
    
    def collect_connection_metrics(self):
        """Collect connection pool metrics"""
        pool = self.engine.pool
        
        # Pool metrics
        DB_POOL_SIZE.labels(
            database=self.engine.url.database,
            pool_type='total'
        ).set(pool.size())
        
        DB_POOL_SIZE.labels(
            database=self.engine.url.database,
            pool_type='checked_out'
        ).set(pool.checkedout())
        
        DB_POOL_SIZE.labels(
            database=self.engine.url.database,
            pool_type='checked_in'
        ).set(pool.checkedin())
    
    def collect_database_metrics(self):
        """Collect database-specific metrics"""
        try:
            with self.engine.connect() as conn:
                # Active connections
                result = conn.execute(sa.text(
                    "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
                ))
                active_connections = result.scalar()
                
                DB_CONNECTIONS_ACTIVE.labels(
                    database=self.engine.url.database,
                    host=self.engine.url.host
                ).set(active_connections)
                
                # Idle connections
                result = conn.execute(sa.text(
                    "SELECT count(*) FROM pg_stat_activity WHERE state = 'idle'"
                ))
                idle_connections = result.scalar()
                
                DB_CONNECTIONS_IDLE.labels(
                    database=self.engine.url.database,
                    host=self.engine.url.host
                ).set(idle_connections)
        
        except Exception as e:
            logging.error(f"Failed to collect database metrics: {e}")
    
    def start_metrics_collection(self, interval: int = 30):
        """Start periodic metrics collection"""
        import threading
        
        def collect_metrics():
            while True:
                self.collect_connection_metrics()
                self.collect_database_metrics()
                time.sleep(interval)
        
        thread = threading.Thread(target=collect_metrics, daemon=True)
        thread.start()

# Usage with SQLAlchemy repositories
class MonitoredUserRepository:
    def __init__(self, session, monitor: DatabaseMonitor):
        self.session = session
        self.monitor = monitor
    
    @monitor.monitor_query(query_type='select', table='users')
    def get_user_by_id(self, user_id: int):
        return self.session.query(User).filter_by(id=user_id).first()
    
    @monitor.monitor_query(query_type='insert', table='users')
    def create_user(self, user_data: dict):
        user = User(**user_data)
        self.session.add(user)
        self.session.commit()
        return user
    
    @monitor.monitor_query(query_type='select', table='users')
    def search_users(self, search_term: str):
        return self.session.query(User).filter(
            User.username.ilike(f"%{search_term}%")
        ).all()
```

### Grafana Dashboard Configuration
```json
{
  "dashboard": {
    "title": "Database Performance Dashboard",
    "panels": [
      {
        "title": "Query Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(db_queries_total[5m])",
            "legendFormat": "{{query_type}} - {{status}}"
          }
        ]
      },
      {
        "title": "Query Duration P95",
        "type": "stat",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(db_query_duration_seconds_bucket[5m]))",
            "legendFormat": "P95 Duration"
          }
        ]
      },
      {
        "title": "Database Connections",
        "type": "graph",
        "targets": [
          {
            "expr": "db_connections_active_total",
            "legendFormat": "Active"
          },
          {
            "expr": "db_connections_idle_total", 
            "legendFormat": "Idle"
          }
        ]
      },
      {
        "title": "Connection Pool Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "db_pool_size_current{pool_type='checked_out'}",
            "legendFormat": "Used"
          },
          {
            "expr": "db_pool_size_current{pool_type='total'}",
            "legendFormat": "Total"
          }
        ]
      },
      {
        "title": "Slow Queries",
        "type": "table",
        "targets": [
          {
            "expr": "increase(db_slow_queries_total[1h])",
            "legendFormat": "{{query_type}} - {{table}}"
          }
        ]
      }
    ]
  }
}
```

## Serverless Database Patterns

### AWS Lambda with RDS Proxy
```python
import json
import boto3
import logging
from typing import Dict, Any

# Lambda function with RDS Proxy
def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Lambda function using RDS Proxy for connection management"""
    
    try:
        # RDS Proxy endpoint handles connection pooling
        engine = create_engine(
            f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
            f"@{os.getenv('RDS_PROXY_ENDPOINT')}:5432/{os.getenv('DB_NAME')}",
            pool_size=1,  # Lambda containers reuse connections
            max_overflow=0,
            pool_recycle=3600
        )
        
        with engine.connect() as conn:
            # Process request
            result = process_database_request(conn, event)
            
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }
    
    except Exception as e:
        logging.error(f"Lambda function error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }

def process_database_request(conn, event):
    """Process database request with minimal connection overhead"""
    
    # Use prepared statements for better performance
    query = sa.text("""
        SELECT id, username, email 
        FROM users 
        WHERE created_at > :since_date
        ORDER BY created_at DESC 
        LIMIT :limit
    """)
    
    result = conn.execute(query, {
        'since_date': event.get('since_date'),
        'limit': event.get('limit', 100)
    })
    
    return [dict(row) for row in result]
```

This comprehensive guide covers cloud-native database patterns and DevOps practices essential for senior staff engineers managing modern database infrastructures.