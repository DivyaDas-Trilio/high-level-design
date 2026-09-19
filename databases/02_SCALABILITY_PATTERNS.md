# Database Scalability Patterns

## Vertical vs Horizontal Scaling

### Vertical Scaling (Scale Up)
**Approach**: Increase hardware resources (CPU, RAM, storage)

**Advantages**:
- Simple to implement
- No application changes needed
- Maintains ACID properties
- Single point of administration

**Limitations**:
- Hardware limits
- Single point of failure
- Cost increases exponentially
- Downtime during upgrades

**When to Use**:
- Predictable growth
- Strong consistency requirements
- Limited development resources
- Cost-effective up to certain scale

### Horizontal Scaling (Scale Out)
**Approach**: Add more servers/nodes

**Advantages**:
- Theoretically unlimited scaling
- Better fault tolerance
- Cost-effective at large scale
- Geographic distribution possible

**Challenges**:
- Complexity increases
- Consistency challenges
- Data distribution complexity
- Cross-node queries expensive

**When to Use**:
- Massive scale requirements
- Global user base
- High availability needs
- Budget constraints for large hardware

## Read Replicas & Load Distribution

### Read Replica Patterns

#### Master-Slave Replication
```
[Write Master] ---> [Read Replica 1]
      |        \--> [Read Replica 2]
      |         \-> [Read Replica 3]
      v
[Application Logic]
```

**Implementation Considerations**:
- Replication lag (eventual consistency)
- Failover procedures
- Read/write splitting in application
- Geographic distribution

#### Configuration Example (MySQL)
```sql
-- On Master
CREATE USER 'replicator'@'%' IDENTIFIED BY 'password';
GRANT REPLICATION SLAVE ON *.* TO 'replicator'@'%';
SHOW MASTER STATUS;

-- On Slave
CHANGE MASTER TO
  MASTER_HOST='master-host',
  MASTER_USER='replicator',
  MASTER_PASSWORD='password',
  MASTER_LOG_FILE='mysql-bin.000001',
  MASTER_LOG_POS=154;
START SLAVE;
```

### Load Balancing Strategies

#### Round Robin
- Simple distribution
- Equal load assumption
- No connection state awareness

#### Least Connections
- Routes to server with fewest active connections
- Better for varying request durations
- Requires connection tracking

#### Health Check Based
- Routes only to healthy servers
- Implements circuit breaker pattern
- Automatic failover

#### Geographic Routing
```python
# Example: Route to nearest replica
def get_database_connection(user_location):
    if user_location in ['US-WEST', 'US-EAST']:
        return us_replica_pool.get_connection()
    elif user_location in ['EU-WEST', 'EU-CENTRAL']:
        return eu_replica_pool.get_connection()
    else:
        return asia_replica_pool.get_connection()
```

## Database Partitioning Strategies

### Horizontal Partitioning (Sharding)

#### Range-Based Sharding
```sql
-- Example: Partition by user ID ranges
Shard 1: user_id 1-1000000
Shard 2: user_id 1000001-2000000
Shard 3: user_id 2000001-3000000
```

**Advantages**:
- Simple to implement
- Range queries stay within shard
- Easy to add new ranges

**Disadvantages**:
- Uneven data distribution
- Hotspots possible
- Rebalancing requires data movement

#### Hash-Based Sharding
```python
def get_shard(user_id, num_shards):
    return hash(user_id) % num_shards

# Consistent hashing for better distribution
class ConsistentHasher:
    def __init__(self, nodes, replicas=3):
        self.replicas = replicas
        self.ring = {}
        self.sorted_keys = []
        for node in nodes:
            self.add_node(node)
    
    def add_node(self, node):
        for i in range(self.replicas):
            key = hash(f"{node}:{i}")
            self.ring[key] = node
            self.sorted_keys.append(key)
        self.sorted_keys.sort()
    
    def get_node(self, item):
        if not self.ring:
            return None
        key = hash(item)
        for ring_key in self.sorted_keys:
            if key <= ring_key:
                return self.ring[ring_key]
        return self.ring[self.sorted_keys[0]]
```

#### Directory-Based Sharding
- Lookup service maps keys to shards
- Flexible routing logic
- Single point of failure (mitigated by replication)

### Vertical Partitioning
Split tables by columns:
```sql
-- Split user table
users_basic: id, username, email
users_profile: id, bio, avatar, preferences
users_analytics: id, last_login, page_views, activity_score
```

**Benefits**:
- Reduce I/O for common queries
- Different storage engines per partition
- Better cache utilization

**Challenges**:
- Join complexity
- Referential integrity
- Schema evolution

## Caching Layers

### Cache-Aside Pattern
```python
def get_user(user_id):
    # Try cache first
    user = cache.get(f"user:{user_id}")
    if user is None:
        # Cache miss - fetch from database
        user = db.get_user(user_id)
        # Store in cache for next time
        cache.set(f"user:{user_id}", user, ttl=3600)
    return user

def update_user(user_id, data):
    # Update database
    db.update_user(user_id, data)
    # Invalidate cache
    cache.delete(f"user:{user_id}")
```

### Write-Through Pattern
```python
def update_user(user_id, data):
    # Update database first
    db.update_user(user_id, data)
    # Update cache
    user = db.get_user(user_id)
    cache.set(f"user:{user_id}", user, ttl=3600)
```

### Write-Behind Pattern
```python
def update_user(user_id, data):
    # Update cache immediately
    cache.set(f"user:{user_id}", data, ttl=3600)
    # Queue database update
    queue.enqueue('update_user_db', user_id, data)
```

### Cache Levels
1. **Application Cache**: In-memory cache within app
2. **Distributed Cache**: Redis, Memcached
3. **Database Cache**: Query result cache, buffer pools
4. **CDN**: Geographic content distribution

## Connection Pooling

### Why Connection Pooling?
- Database connections are expensive
- Limit concurrent connections
- Reduce latency
- Resource management

### Implementation Example
```python
import psycopg2.pool

# Create connection pool
connection_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=10,      # Minimum connections
    maxconn=50,      # Maximum connections
    host="localhost",
    database="mydb",
    user="user",
    password="password"
)

def execute_query(query, params=None):
    conn = connection_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    finally:
        connection_pool.putconn(conn)
```

### Pool Configuration Guidelines
- **Min connections**: Based on steady-state load
- **Max connections**: Database connection limit ÷ number of app instances
- **Idle timeout**: Balance resource usage vs connection overhead
- **Validation queries**: Detect broken connections

## Practical Scaling Scenarios

### Scenario 1: E-commerce Platform
**Requirements**:
- 1M products, 10M users
- Read-heavy (browsing) vs write-heavy (orders)
- Global user base

**Solution**:
```
Products DB (Read Replicas by Region)
├── US-West: Product catalog + inventory
├── US-East: Product catalog + inventory  
└── EU: Product catalog + inventory

User/Orders DB (Sharded by user_id)
├── Shard 1: users 1-2.5M + their orders
├── Shard 2: users 2.5M-5M + their orders
├── Shard 3: users 5M-7.5M + their orders
└── Shard 4: users 7.5M-10M + their orders

Cache Layer (Redis Cluster)
├── Product cache
├── User session cache
└── Shopping cart cache
```

### Scenario 2: Social Media Platform
**Requirements**:
- 100M users posting content
- Timeline generation
- Real-time features

**Solution**:
```
User Data: Sharded by user_id
Content Data: Sharded by content_id
Relationships: Graph database
Timeline Cache: Pre-computed feeds
Search Index: Elasticsearch cluster
```

## Monitoring & Metrics

### Key Performance Indicators
- **Throughput**: Queries per second (QPS)
- **Latency**: P95, P99 response times
- **Error rates**: Failed queries, timeouts
- **Resource utilization**: CPU, memory, disk I/O

### Database-Specific Metrics
```sql
-- PostgreSQL: Monitor slow queries
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- MySQL: Monitor replication lag
SHOW SLAVE STATUS\G
```

### Application Metrics
```python
import time
from functools import wraps

def monitor_query(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            metrics.increment('db.query.success')
            return result
        except Exception as e:
            metrics.increment('db.query.error')
            raise
        finally:
            duration = time.time() - start_time
            metrics.timing('db.query.duration', duration)
    return wrapper
```

## Trade-off Analysis

### Consistency vs Performance
- **Strong Consistency**: Synchronous replication, higher latency
- **Eventual Consistency**: Asynchronous replication, better performance
- **Session Consistency**: Read your writes guarantee

### Availability vs Partition Tolerance
- **CA Systems**: Traditional RDBMS, fail during network partitions
- **AP Systems**: NoSQL, continue operating during partitions
- **CP Systems**: Consistent distributed systems, may become unavailable

### Cost vs Performance
- **Vertical scaling**: Higher cost per unit performance
- **Horizontal scaling**: Lower cost, higher complexity
- **Managed services**: Higher cost, lower operational overhead

## Best Practices for Staff Engineers

1. **Start with simplest solution**: Scale complexity with actual needs
2. **Measure before optimizing**: Use real performance data
3. **Plan for failure**: Design for graceful degradation
4. **Automate operations**: Reduce manual intervention
5. **Document decisions**: Capture reasoning for future reference

## Next Module
Continue to `03_REPLICATION_AND_HA.md` for high availability patterns.