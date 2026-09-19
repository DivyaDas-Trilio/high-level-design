# Database Design & Scalability Quick Reference

## ACID Properties Summary
- **Atomicity**: All or nothing execution
- **Consistency**: Valid state maintained
- **Isolation**: Concurrent transactions don't interfere
- **Durability**: Committed data survives failures

## CAP Theorem
**Pick any two**:
- **Consistency**: All nodes see the same data
- **Availability**: System remains operational
- **Partition Tolerance**: System continues despite network failures

## Database Types by Use Case

### SQL Databases (ACID)
- **PostgreSQL**: Complex queries, ACID compliance
- **MySQL**: Web applications, read-heavy workloads
- **Oracle**: Enterprise applications, complex transactions

### NoSQL Databases (BASE)

#### Document Stores
- **MongoDB**: Flexible schemas, rapid development
- **CouchDB**: Multi-master replication, offline-first

#### Key-Value Stores
- **Redis**: Caching, session storage, real-time analytics
- **DynamoDB**: Serverless, auto-scaling, AWS ecosystem

#### Column Stores
- **Cassandra**: Time-series, write-heavy workloads
- **HBase**: Large-scale analytics, Hadoop ecosystem

#### Graph Databases
- **Neo4j**: Social networks, recommendation engines
- **Amazon Neptune**: Managed graph database

## Scalability Patterns Quick Reference

### Vertical Scaling
```
Before: [4 CPU, 8GB RAM] → After: [8 CPU, 16GB RAM]
```
✅ Simple implementation  
❌ Hardware limits, single point of failure

### Horizontal Scaling
```
Before: [1 Server] → After: [Server 1] [Server 2] [Server 3]
```
✅ No theoretical limits  
❌ Increased complexity, consistency challenges

### Read Replicas
```
[Master] → [Replica 1] [Replica 2] [Replica 3]
```
- **Use case**: Read-heavy workloads
- **Trade-off**: Eventual consistency for better performance

### Sharding Strategies

#### Range-Based
```
Shard 1: users 1-1M
Shard 2: users 1M-2M  
Shard 3: users 2M-3M
```
✅ Simple range queries  
❌ Uneven distribution, hotspots

#### Hash-Based
```python
shard = hash(user_id) % num_shards
```
✅ Even distribution  
❌ No range queries, resharding difficult

#### Directory-Based
```
[Lookup Service] → Routes to appropriate shard
```
✅ Flexible routing  
❌ Additional complexity, potential bottleneck

## Consistency Models

### Strong Consistency
- All reads receive the most recent write
- **Examples**: Traditional SQL databases
- **Use cases**: Financial transactions, inventory

### Eventual Consistency  
- System will become consistent over time
- **Examples**: DNS, NoSQL databases
- **Use cases**: Social media feeds, content distribution

### Session Consistency
- Consistency within a user session
- **Examples**: Shopping cart, user preferences
- **Use cases**: Web applications, mobile apps

## Caching Strategies

### Cache-Aside
```python
data = cache.get(key)
if data is None:
    data = database.get(key)
    cache.set(key, data)
return data
```

### Write-Through
```python
database.update(key, value)
cache.set(key, value)
```

### Write-Behind
```python
cache.set(key, value)
queue.enqueue('update_db', key, value)
```

## Replication Types

### Master-Slave
- **Reads**: Slaves  
- **Writes**: Master only
- **Failover**: Manual or automated promotion

### Master-Master
- **Reads/Writes**: Any master
- **Conflict Resolution**: Required
- **Use case**: Geographic distribution

## Index Types Quick Guide

### B-Tree Index
- **Best for**: Range queries, sorting
- **Example**: `WHERE created_at BETWEEN '2024-01-01' AND '2024-12-31'`

### Hash Index
- **Best for**: Equality lookups
- **Example**: `WHERE user_id = 12345`

### Covering Index
```sql
CREATE INDEX idx_user_posts ON posts (user_id) INCLUDE (title, created_at);
```

### Partial Index
```sql
CREATE INDEX idx_active_users ON users (email) WHERE is_active = true;
```

## Query Optimization Checklist

- [ ] **Indexes**: Add indexes for WHERE, ORDER BY, JOIN columns
- [ ] **Query plans**: Use EXPLAIN to analyze execution
- [ ] **Joins**: Avoid N+1 queries, use appropriate join types
- [ ] **Limits**: Always use LIMIT for large result sets
- [ ] **Pagination**: Use cursor-based pagination for large datasets

## Common Anti-Patterns

### Database Design
❌ **Fat tables**: Tables with too many columns  
❌ **God tables**: One table doing everything  
❌ **No indexes**: Missing indexes on query columns  
❌ **Over-indexing**: Too many unused indexes

### Queries
❌ **SELECT \***: Fetching unnecessary columns  
❌ **N+1 queries**: Multiple queries in loops  
❌ **Unbounded queries**: No LIMIT clauses  
❌ **Cartesian products**: Missing JOIN conditions

### Architecture
❌ **Single database**: No read replicas or sharding  
❌ **No caching**: Direct database hits for all reads  
❌ **Synchronous replication**: Blocking writes  
❌ **No monitoring**: Flying blind

## Performance Metrics

### Database Metrics
- **QPS**: Queries per second
- **Latency**: P95, P99 response times  
- **Connection pool**: Active/idle connections
- **Replication lag**: Master-slave delay
- **Disk I/O**: Read/write operations per second

### Application Metrics
- **Cache hit ratio**: Percentage of cache hits
- **Error rate**: Failed requests percentage
- **Throughput**: Requests per second
- **Resource utilization**: CPU, memory, network

## Capacity Planning

### Growth Estimation
```
Current: 1M users, 10M requests/day
Growth: 20% monthly
6 months: 3M users, 30M requests/day
12 months: 8.9M users, 89M requests/day
```

### Hardware Scaling
```
Database server requirements per 1M active users:
- CPU: 4-8 cores
- RAM: 16-32 GB  
- Storage: 1-5 TB SSD
- Network: 1-10 Gbps
```

## Disaster Recovery

### RTO/RPO Guidelines
- **Tier 1**: RTO < 1 hour, RPO < 15 minutes
- **Tier 2**: RTO < 4 hours, RPO < 1 hour  
- **Tier 3**: RTO < 24 hours, RPO < 8 hours

### Backup Strategy (3-2-1 Rule)
- **3** copies of data
- **2** different media types
- **1** offsite backup

## Monitoring Commands

### PostgreSQL
```sql
-- Active connections
SELECT count(*) FROM pg_stat_activity;

-- Slow queries
SELECT query, mean_time FROM pg_stat_statements ORDER BY mean_time DESC;

-- Replication lag
SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), flush_lsn) AS lag_bytes FROM pg_stat_replication;
```

### MySQL
```sql
-- Show running processes
SHOW PROCESSLIST;

-- Replication status
SHOW SLAVE STATUS\G

-- InnoDB status
SHOW ENGINE INNODB STATUS\G
```

### Redis
```bash
# Memory usage
INFO memory

# Connected clients
INFO clients

# Hit rate
INFO stats
```

## Common Interview Questions

### Design Questions
1. "Design a database for Instagram with 1 billion users"
2. "How would you handle friend suggestions in a social network?"
3. "Design a URL shortener like bit.ly"
4. "How would you implement a chat application database?"

### Technical Questions
1. "Explain the trade-offs between SQL and NoSQL"
2. "How do you handle database migrations with zero downtime?"
3. "What's the difference between sharding and partitioning?"
4. "How do you ensure data consistency in a distributed system?"

### Troubleshooting Questions
1. "Database queries are suddenly slow, how do you debug?"
2. "You have high replication lag, what could cause this?"
3. "Application is getting database connection timeouts, what's wrong?"
4. "How would you handle a database failover scenario?"

## Tools & Resources

### Database Tools
- **pgAdmin**: PostgreSQL administration
- **MySQL Workbench**: MySQL GUI client
- **Redis Desktop Manager**: Redis GUI client
- **DataGrip**: Universal database IDE

### Monitoring Tools
- **Prometheus + Grafana**: Time-series monitoring
- **DataDog**: Application performance monitoring
- **New Relic**: Database performance insights
- **Percona Monitoring**: MySQL/PostgreSQL monitoring

### Load Testing
- **Apache JMeter**: Database load testing
- **Artillery**: Modern load testing toolkit  
- **sysbench**: Database benchmark suite

### Migration Tools
- **Flyway**: Database migration tool
- **Liquibase**: Database change management
- **gh-ost**: GitHub's MySQL migration tool

## Next Steps

1. **Pick a database type** based on your use case
2. **Start with a simple design** and iterate
3. **Measure performance** before optimizing
4. **Plan for failure** scenarios
5. **Document your decisions** for the team