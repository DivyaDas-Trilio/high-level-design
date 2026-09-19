# ACID Properties & Database Fundamentals

## ACID Properties Deep Dive

### Atomicity
**Definition**: All operations in a transaction succeed or fail together.

**Implementation Techniques**:
- Write-Ahead Logging (WAL)
- Shadow Paging
- Rollback segments

**Example Scenario**:
```sql
-- Bank transfer: Both operations must succeed or fail together
BEGIN TRANSACTION;
UPDATE accounts SET balance = balance - 100 WHERE account_id = 'A';
UPDATE accounts SET balance = balance + 100 WHERE account_id = 'B';
COMMIT;
```

**Staff Engineer Considerations**:
- How does atomicity work across microservices?
- Trade-offs with distributed transactions
- Saga pattern as alternative

### Consistency
**Definition**: Database remains in valid state before and after transaction.

**Types of Consistency**:
1. **Application-level**: Business rules and constraints
2. **Database-level**: Referential integrity, constraints
3. **Distributed**: Eventual vs Strong consistency

**Implementation**:
- Check constraints
- Foreign key constraints
- Triggers
- Application validation

**Challenges at Scale**:
- Cross-partition consistency
- Eventually consistent systems
- Conflict resolution strategies

### Isolation
**Definition**: Concurrent transactions don't interfere with each other.

**Isolation Levels**:
1. **Read Uncommitted** - Dirty reads possible
2. **Read Committed** - No dirty reads, phantom reads possible
3. **Repeatable Read** - No dirty/non-repeatable reads, phantom reads possible
4. **Serializable** - No dirty/non-repeatable/phantom reads

**Implementation Mechanisms**:
- Locking (Pessimistic)
- Multi-Version Concurrency Control (MVCC)
- Timestamp ordering

**Performance vs Correctness Trade-offs**:
```python
# Example: Choosing isolation level based on use case
# High-frequency trading: SERIALIZABLE
# Analytics queries: READ UNCOMMITTED
# User sessions: READ COMMITTED
```

### Durability
**Definition**: Committed data survives system failures.

**Implementation Strategies**:
- Write-Ahead Logging
- Synchronous replication
- Persistent storage
- Checkpointing

**Staff Engineer Focus**:
- Recovery time objectives (RTO)
- Recovery point objectives (RPO)
- Backup strategies
- Multi-region durability

## Database Design Principles

### Normalization
**Purpose**: Eliminate data redundancy and update anomalies

**Normal Forms**:
- 1NF: Atomic values, no repeating groups
- 2NF: No partial dependencies
- 3NF: No transitive dependencies
- BCNF: Every determinant is a candidate key

**When to Denormalize**:
- Read-heavy workloads
- Performance requirements
- Distributed systems
- Data warehousing

### Indexing Strategies

#### B-Tree Indexes
- Best for: Range queries, ordering
- Structure: Balanced tree with sorted keys
- Use cases: Primary keys, foreign keys, date ranges

#### Hash Indexes
- Best for: Equality lookups
- Structure: Hash table
- Use cases: Unique lookups, caching layers

#### LSM Trees (Log-Structured Merge)
- Best for: Write-heavy workloads
- Structure: Memory + disk segments
- Use cases: Time-series data, logging systems

#### Covering Indexes
```sql
-- Include frequently queried columns in index
CREATE INDEX idx_user_email_name ON users (email) INCLUDE (first_name, last_name);
```

### Query Optimization

#### Execution Plan Analysis
```sql
-- PostgreSQL
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM orders WHERE customer_id = 123;

-- MySQL
EXPLAIN FORMAT=JSON SELECT * FROM orders WHERE customer_id = 123;
```

#### Common Optimization Techniques
1. **Index selection**: Choose right index type
2. **Query rewriting**: Avoid correlated subqueries
3. **Partition pruning**: Use partition keys effectively
4. **Join ordering**: Optimal join sequence
5. **Statistics maintenance**: Keep stats current

## Data Modeling Patterns

### Entity-Relationship Modeling
- Identify entities, attributes, relationships
- Choose appropriate cardinalities
- Handle inheritance and polymorphism

### Dimensional Modeling (Data Warehousing)
- Fact tables: Measurements, metrics
- Dimension tables: Context, attributes
- Star vs Snowflake schemas

### Document Modeling (NoSQL)
- Embed vs Reference
- Schema flexibility vs query efficiency
- Handling relationships in document stores

## Practical Exercises

### Exercise 1: Design a E-commerce Database
Requirements:
- Users, products, orders, reviews
- Handle inventory management
- Support multiple payment methods
- Scale to millions of products

### Exercise 2: Analyze Query Performance
```sql
-- Given this slow query, identify issues and optimize
SELECT c.name, COUNT(o.id) as order_count, SUM(oi.quantity * oi.price) as total
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
LEFT JOIN order_items oi ON o.id = oi.order_id
WHERE o.created_at > '2024-01-01'
GROUP BY c.id, c.name
HAVING total > 1000
ORDER BY total DESC;
```

### Exercise 3: Transaction Design
Design transactions for:
1. Multi-step user registration
2. Inventory management with reservations
3. Financial accounting with double-entry bookkeeping

## Assessment Questions

### Scenario-Based Questions
1. A banking application needs to transfer money between accounts. Design the transaction and explain how each ACID property is maintained.

2. Your application has a read-heavy workload with occasional writes. How would you design the database architecture?

3. Explain how you would handle a situation where isolation level SERIALIZABLE is causing too many conflicts.

### Design Problems
1. Design a database for a chat application with 10M+ users
2. How would you migrate from one database schema to another with zero downtime?
3. Design a multi-tenant SaaS database with strict data isolation

## Key Takeaways for Staff Engineers

1. **ACID is foundational but has trade-offs at scale**
2. **Choose consistency models based on business requirements**
3. **Performance tuning requires deep understanding of storage engines**
4. **Modern applications often need polyglot persistence**
5. **Database design decisions have long-term architectural implications**

## Next Module
Proceed to `02_SCALABILITY_PATTERNS.md` for horizontal scaling strategies.