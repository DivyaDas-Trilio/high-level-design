# Replication & High Availability

## Replication Models

### Master-Slave Replication

#### Architecture
```
[Primary/Master]
    |
    | (Async/Sync Replication)
    v
[Secondary/Slave 1] [Secondary/Slave 2] [Secondary/Slave 3]
```

#### Configuration & Management
```sql
-- MySQL Master Configuration
[mysqld]
server-id = 1
log-bin = /var/log/mysql/mysql-bin.log
binlog-do-db = production_db

-- Slave Configuration  
[mysqld]
server-id = 2
relay-log = /var/log/mysql/relay-bin
read-only = 1
```

**Advantages**:
- Simple to implement and understand
- Scales read workloads effectively
- Clear separation of write and read traffic
- Proven pattern with mature tooling

**Challenges**:
- Single point of failure (master)
- Replication lag affects consistency
- Failover complexity
- Manual intervention often required

### Master-Master Replication

#### Active-Active Configuration
```
[Master A] <---> [Master B]
    |              |
    v              v
[Slave A1]     [Slave B1]
[Slave A2]     [Slave B2]
```

#### Conflict Resolution Strategies
```sql
-- MySQL: Auto-increment offset to avoid primary key conflicts
# Master A
auto_increment_increment = 2
auto_increment_offset = 1

# Master B  
auto_increment_increment = 2
auto_increment_offset = 2
```

**Application-Level Conflict Resolution**:
```python
def resolve_user_update_conflict(local_version, remote_version):
    # Last-writer-wins with timestamp
    if remote_version.updated_at > local_version.updated_at:
        return remote_version
    
    # Field-level merge for non-conflicting changes
    merged = local_version.copy()
    for field, value in remote_version.fields.items():
        if field not in local_version.dirty_fields:
            merged[field] = value
    
    return merged
```

**Advantages**:
- No single point of failure
- Geographic distribution
- Load distribution across masters
- Faster failover

**Challenges**:
- Complex conflict resolution
- Split-brain scenarios
- Data consistency guarantees
- Operational complexity

### Multi-Master Replication

#### Ring Topology
```
[Master A] --> [Master B] --> [Master C] --> [Master A]
```

#### Star Topology
```
    [Master B]
        |
[Master A] <--> [Hub] <--> [Master C]
        |
    [Master D]
```

**Use Cases**:
- Global applications with regional masters
- High write throughput requirements
- Geographic compliance requirements

## Consensus Algorithms

### Raft Consensus

#### Core Concepts
- **Leader Election**: One node acts as leader
- **Log Replication**: Leader replicates to followers
- **Safety**: Committed entries never lost

#### Leader Election Process
```python
class RaftNode:
    def __init__(self, node_id, peers):
        self.node_id = node_id
        self.peers = peers
        self.state = 'follower'
        self.current_term = 0
        self.voted_for = None
        self.election_timeout = random.randint(150, 300)  # ms
    
    def start_election(self):
        self.current_term += 1
        self.state = 'candidate'
        self.voted_for = self.node_id
        
        votes = 1  # Vote for self
        for peer in self.peers:
            if self.request_vote(peer):
                votes += 1
        
        if votes > len(self.peers) // 2 + 1:
            self.become_leader()
    
    def request_vote(self, peer):
        # Send vote request to peer
        # Return True if vote granted
        pass
```

#### Log Replication
```python
def append_entries(self, entries, prev_log_index, prev_log_term):
    # Consistency check
    if self.log[prev_log_index].term != prev_log_term:
        return False
    
    # Append new entries
    self.log.extend(entries)
    
    # Update commit index
    if leader_commit > self.commit_index:
        self.commit_index = min(leader_commit, len(self.log) - 1)
    
    return True
```

### Paxos Consensus

#### Three Phases
1. **Prepare Phase**: Propose a proposal number
2. **Promise Phase**: Acceptors promise not to accept lower proposals
3. **Accept Phase**: Propose value, acceptors accept

**Use in Databases**:
- Google Spanner
- Apache Cassandra
- CockroachDB

## High Availability Patterns

### Active-Passive Failover

#### Architecture
```
[Primary DB] --> [Standby DB]
     |              |
     v              v
[App Servers] --> [Load Balancer]
```

#### Implementation with Heartbeats
```python
import time
import subprocess

class DatabaseMonitor:
    def __init__(self, primary_host, standby_host):
        self.primary_host = primary_host
        self.standby_host = standby_host
        self.failover_triggered = False
    
    def check_primary_health(self):
        try:
            # Simple connection test
            conn = psycopg2.connect(
                host=self.primary_host,
                database="healthcheck",
                user="monitor",
                connect_timeout=5
            )
            conn.close()
            return True
        except:
            return False
    
    def trigger_failover(self):
        if self.failover_triggered:
            return
        
        # Promote standby to primary
        subprocess.run([
            "pg_ctl", "promote", 
            "-D", "/var/lib/postgresql/data"
        ])
        
        # Update DNS/load balancer
        self.update_dns_record(self.standby_host)
        
        self.failover_triggered = True
    
    def monitor_loop(self):
        consecutive_failures = 0
        while True:
            if self.check_primary_health():
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= 3:  # 3 consecutive failures
                    self.trigger_failover()
                    break
            time.sleep(10)  # Check every 10 seconds
```

### Active-Active Failover

#### Load Balancer Configuration
```yaml
# HAProxy example
backend database_cluster
    balance roundrobin
    option httpchk GET /health
    server db1 10.0.1.10:5432 check inter 2s
    server db2 10.0.1.11:5432 check inter 2s
    server db3 10.0.1.12:5432 check inter 2s
```

#### Application-Level Health Checks
```python
class DatabasePool:
    def __init__(self, servers):
        self.servers = servers
        self.healthy_servers = set(servers)
        self.circuit_breakers = {
            server: CircuitBreaker() for server in servers
        }
    
    def get_connection(self):
        for server in self.healthy_servers:
            if self.circuit_breakers[server].can_execute():
                try:
                    conn = psycopg2.connect(server.connection_string)
                    self.circuit_breakers[server].record_success()
                    return conn
                except Exception as e:
                    self.circuit_breakers[server].record_failure()
                    if self.circuit_breakers[server].is_open():
                        self.healthy_servers.discard(server)
        
        raise Exception("No healthy database servers available")
```

## Backup & Recovery Strategies

### Backup Types

#### Full Backup
```bash
# PostgreSQL
pg_dump -h localhost -U postgres -d mydb > backup_full.sql

# MySQL
mysqldump -u root -p --all-databases > backup_full.sql

# MongoDB
mongodump --host localhost:27017 --out /backup/full/
```

#### Incremental Backup
```bash
# PostgreSQL with WAL-E
wal-e backup-push /var/lib/postgresql/9.6/main

# MySQL with binary logs
mysqlbinlog --start-datetime="2024-01-01 00:00:00" mysql-bin.000001 > incremental.sql
```

#### Point-in-Time Recovery (PITR)
```sql
-- PostgreSQL: Restore to specific timestamp
SELECT pg_start_backup('backup-label', false, false);
-- Copy data directory
SELECT pg_stop_backup();

-- Recovery configuration
restore_command = 'cp /backup/wal/%f %p'
recovery_target_time = '2024-01-01 12:00:00'
```

### Backup Best Practices

#### 3-2-1 Rule
- **3** copies of important data
- **2** different storage media
- **1** offsite backup

#### Automated Backup Pipeline
```python
import boto3
import subprocess
from datetime import datetime, timedelta

class BackupManager:
    def __init__(self, db_config, s3_bucket):
        self.db_config = db_config
        self.s3_client = boto3.client('s3')
        self.s3_bucket = s3_bucket
    
    def create_backup(self):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"backup_{timestamp}.sql"
        
        # Create database dump
        subprocess.run([
            'pg_dump', 
            '-h', self.db_config['host'],
            '-U', self.db_config['user'],
            '-d', self.db_config['database'],
            '-f', backup_file
        ])
        
        # Compress backup
        subprocess.run(['gzip', backup_file])
        compressed_file = f"{backup_file}.gz"
        
        # Upload to S3
        self.s3_client.upload_file(
            compressed_file,
            self.s3_bucket,
            f"backups/{compressed_file}"
        )
        
        # Cleanup old backups (keep 30 days)
        self.cleanup_old_backups()
    
    def cleanup_old_backups(self):
        cutoff_date = datetime.now() - timedelta(days=30)
        # List and delete old objects from S3
        pass
```

## Disaster Recovery Planning

### RTO and RPO Objectives

#### Recovery Time Objective (RTO)
- Maximum acceptable downtime
- Influences architecture decisions
- Cost vs availability trade-off

```python
# Example: Different RTO strategies
RTO_STRATEGIES = {
    "immediate": {
        "cost": "high",
        "setup": "active-active with auto-failover",
        "complexity": "high"
    },
    "5_minutes": {
        "cost": "medium", 
        "setup": "warm standby with monitoring",
        "complexity": "medium"
    },
    "1_hour": {
        "cost": "low",
        "setup": "cold standby with manual failover",
        "complexity": "low"
    }
}
```

#### Recovery Point Objective (RPO)
- Maximum acceptable data loss
- Determines backup frequency
- Influences replication strategy

### Disaster Recovery Testing
```python
class DisasterRecoveryTest:
    def __init__(self, primary_db, backup_db):
        self.primary_db = primary_db
        self.backup_db = backup_db
    
    def test_failover(self):
        # 1. Create test data on primary
        test_data = self.create_test_transactions()
        
        # 2. Verify replication
        time.sleep(5)  # Allow replication
        self.verify_data_replicated(test_data)
        
        # 3. Simulate primary failure
        self.simulate_primary_failure()
        
        # 4. Execute failover
        failover_start = time.time()
        self.execute_failover()
        failover_time = time.time() - failover_start
        
        # 5. Verify application connectivity
        self.verify_application_connectivity()
        
        # 6. Measure data loss
        data_loss = self.measure_data_loss(test_data)
        
        return {
            "failover_time": failover_time,
            "data_loss": data_loss,
            "success": data_loss == 0 and failover_time < RTO_TARGET
        }
```

## Monitoring & Alerting

### Key Metrics to Monitor

#### Replication Health
```sql
-- PostgreSQL: Check replication lag
SELECT 
    client_addr, 
    state, 
    pg_wal_lsn_diff(pg_current_wal_lsn(), flush_lsn) AS lag_bytes
FROM pg_stat_replication;

-- MySQL: Check slave lag
SHOW SLAVE STATUS\G
# Look for Seconds_Behind_Master
```

#### Database Health
```python
def collect_database_metrics():
    metrics = {
        'connections': get_active_connections(),
        'query_throughput': get_queries_per_second(),
        'replication_lag': get_replication_lag(),
        'disk_usage': get_disk_usage(),
        'backup_age': get_last_backup_age(),
        'slow_queries': get_slow_query_count()
    }
    
    # Send to monitoring system
    for metric, value in metrics.items():
        send_metric(f"database.{metric}", value)
```

#### Alerting Rules
```yaml
# Prometheus alerting rules
groups:
- name: database_alerts
  rules:
  - alert: DatabaseDown
    expr: up{job="database"} == 0
    for: 30s
    labels:
      severity: critical
    annotations:
      summary: "Database instance is down"
  
  - alert: ReplicationLagHigh
    expr: mysql_slave_lag_seconds > 60
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "MySQL replication lag is high"
  
  - alert: BackupOverdue
    expr: time() - last_backup_timestamp > 86400
    labels:
      severity: critical
    annotations:
      summary: "Database backup is overdue"
```

## Real-World Implementation Examples

### Netflix: Cross-Region Disaster Recovery
- Active-Active across AWS regions
- Cassandra with eventual consistency
- Automated failover with Hystrix circuit breakers

### Uber: Database Reliability Engineering
- Schemaless (MySQL + Cassandra)
- Ring Pop for consistent hashing
- Automated migration and failover

### GitHub: MySQL High Availability
- Master-Master MySQL with Orchestrator
- ProxySQL for connection routing
- GitLab Pages on separate infrastructure

## Best Practices Checklist

### Design Phase
- [ ] Define RTO and RPO requirements
- [ ] Choose appropriate replication strategy
- [ ] Plan for split-brain scenarios
- [ ] Design monitoring and alerting
- [ ] Document runbooks and procedures

### Implementation Phase
- [ ] Implement automated failover
- [ ] Set up comprehensive monitoring
- [ ] Create backup and recovery procedures
- [ ] Test disaster recovery regularly
- [ ] Train team on emergency procedures

### Operational Phase
- [ ] Regular backup verification
- [ ] Periodic DR drills
- [ ] Performance baseline monitoring
- [ ] Capacity planning reviews
- [ ] Security audit compliance

## Next Module
Continue to `04_DISTRIBUTED_SYSTEMS.md` for distributed database concepts.