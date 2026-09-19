# Essential SQL Queries for Staff Engineers

## Fundamental SQL Operations

### 1. CREATE - Data Definition Language (DDL)

#### Create Database and Schema
```sql
-- Create database
CREATE DATABASE company_db;

-- Create schema for organization
CREATE SCHEMA hr;
CREATE SCHEMA finance;

-- Use specific database/schema
USE company_db;  -- MySQL
SET search_path TO hr;  -- PostgreSQL
```

#### Create Tables with Constraints
```sql
-- Basic table creation with various constraints
CREATE TABLE users (
    id SERIAL PRIMARY KEY,  -- PostgreSQL auto-increment
    -- id INT AUTO_INCREMENT PRIMARY KEY,  -- MySQL version
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    date_of_birth DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  -- MySQL
    is_active BOOLEAN DEFAULT TRUE,
    profile_data JSON,  -- PostgreSQL JSONB, MySQL JSON
    
    -- Constraints
    CONSTRAINT chk_email_format CHECK (email LIKE '%@%.%'),
    CONSTRAINT chk_birth_date CHECK (date_of_birth < CURRENT_DATE),
    CONSTRAINT chk_username_length CHECK (LENGTH(username) >= 3)
);

-- Table with foreign key relationships
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT,
    slug VARCHAR(250) UNIQUE,
    status VARCHAR(20) DEFAULT 'draft',
    view_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP,
    
    -- Foreign key with actions
    CONSTRAINT fk_posts_user 
        FOREIGN KEY (user_id) 
        REFERENCES users(id) 
        ON DELETE CASCADE 
        ON UPDATE CASCADE,
    
    -- Check constraints
    CONSTRAINT chk_status CHECK (status IN ('draft', 'published', 'archived')),
    CONSTRAINT chk_view_count CHECK (view_count >= 0)
);

-- Many-to-many relationship table
CREATE TABLE user_roles (
    user_id INTEGER,
    role_id INTEGER,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by INTEGER,
    
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_by) REFERENCES users(id)
);
```

#### Create Indexes
```sql
-- Single column index
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_posts_created_at ON posts(created_at);

-- Composite index
CREATE INDEX idx_posts_user_status ON posts(user_id, status);
CREATE INDEX idx_posts_status_created ON posts(status, created_at DESC);

-- Partial index (PostgreSQL)
CREATE INDEX idx_active_users ON users(email) WHERE is_active = TRUE;

-- Functional index
CREATE INDEX idx_users_lower_username ON users(LOWER(username));

-- Unique index
CREATE UNIQUE INDEX idx_posts_slug ON posts(slug) WHERE slug IS NOT NULL;

-- Full-text search index (PostgreSQL)
CREATE INDEX idx_posts_fts ON posts USING GIN(to_tsvector('english', title || ' ' || content));

-- JSON index (PostgreSQL)
CREATE INDEX idx_users_profile_data ON users USING GIN(profile_data);

-- Concurrent index creation (PostgreSQL - no table locking)
CREATE INDEX CONCURRENTLY idx_posts_user_created ON posts(user_id, created_at);
```

### 2. SELECT - Data Retrieval

#### Basic SELECT Patterns
```sql
-- Basic select
SELECT * FROM users;
SELECT id, username, email FROM users;

-- With aliases
SELECT 
    u.id,
    u.username,
    u.email,
    u.created_at AS registration_date
FROM users u;

-- Distinct values
SELECT DISTINCT status FROM posts;
SELECT DISTINCT user_id, status FROM posts;  -- Multiple columns

-- Limiting results
SELECT * FROM users ORDER BY created_at DESC LIMIT 10;  -- Latest 10 users
SELECT * FROM users ORDER BY id OFFSET 20 LIMIT 10;     -- Pagination

-- Conditional selection
SELECT * FROM users WHERE is_active = TRUE;
SELECT * FROM users WHERE created_at > '2024-01-01';
SELECT * FROM users WHERE username ILIKE '%john%';  -- Case-insensitive (PostgreSQL)
SELECT * FROM users WHERE email LIKE '%@gmail.com';
```

#### Advanced WHERE Clauses
```sql
-- Multiple conditions
SELECT * FROM users 
WHERE is_active = TRUE 
    AND created_at > '2024-01-01' 
    AND (first_name IS NOT NULL OR last_name IS NOT NULL);

-- IN and NOT IN
SELECT * FROM posts WHERE status IN ('published', 'featured');
SELECT * FROM users WHERE id NOT IN (1, 5, 10, 15);

-- BETWEEN
SELECT * FROM posts WHERE created_at BETWEEN '2024-01-01' AND '2024-12-31';
SELECT * FROM users WHERE id BETWEEN 100 AND 200;

-- NULL handling
SELECT * FROM users WHERE phone_number IS NULL;
SELECT * FROM users WHERE phone_number IS NOT NULL;

-- Pattern matching
SELECT * FROM users WHERE username LIKE 'admin%';  -- Starts with 'admin'
SELECT * FROM users WHERE email LIKE '%@company.com';  -- Company emails
SELECT * FROM users WHERE username ~ '^[a-zA-Z]';  -- Regex (PostgreSQL)

-- Array operations (PostgreSQL)
SELECT * FROM users WHERE tags @> ARRAY['vip'];  -- Contains 'vip'
SELECT * FROM users WHERE 'premium' = ANY(tags);  -- Any element equals 'premium'
```

#### JOIN Operations
```sql
-- INNER JOIN - only matching records
SELECT 
    u.username,
    u.email,
    p.title,
    p.created_at
FROM users u
INNER JOIN posts p ON u.id = p.user_id
WHERE u.is_active = TRUE;

-- LEFT JOIN - all records from left table
SELECT 
    u.username,
    u.email,
    COUNT(p.id) as post_count
FROM users u
LEFT JOIN posts p ON u.id = p.user_id
GROUP BY u.id, u.username, u.email
ORDER BY post_count DESC;

-- RIGHT JOIN - all records from right table
SELECT 
    u.username,
    p.title
FROM users u
RIGHT JOIN posts p ON u.id = p.user_id;

-- FULL OUTER JOIN - all records from both tables
SELECT 
    u.username,
    p.title
FROM users u
FULL OUTER JOIN posts p ON u.id = p.user_id;

-- Self JOIN - joining table with itself
SELECT 
    e1.name as employee,
    e2.name as manager
FROM employees e1
LEFT JOIN employees e2 ON e1.manager_id = e2.id;

-- Multiple JOINs
SELECT 
    u.username,
    p.title,
    c.comment_text,
    c.created_at
FROM users u
JOIN posts p ON u.id = p.user_id
JOIN comments c ON p.id = c.post_id
WHERE p.status = 'published'
ORDER BY c.created_at DESC;
```

#### Aggregate Functions and GROUP BY
```sql
-- Basic aggregations
SELECT COUNT(*) as total_users FROM users;
SELECT COUNT(DISTINCT user_id) as unique_posters FROM posts;
SELECT AVG(view_count) as avg_views FROM posts;
SELECT SUM(view_count) as total_views FROM posts;
SELECT MIN(created_at) as first_post, MAX(created_at) as last_post FROM posts;

-- GROUP BY with aggregations
SELECT 
    status,
    COUNT(*) as post_count,
    AVG(view_count) as avg_views,
    MAX(view_count) as max_views
FROM posts
GROUP BY status;

-- HAVING clause (filtering after grouping)
SELECT 
    user_id,
    COUNT(*) as post_count,
    SUM(view_count) as total_views
FROM posts
GROUP BY user_id
HAVING COUNT(*) > 5
ORDER BY total_views DESC;

-- Multiple grouping columns
SELECT 
    EXTRACT(YEAR FROM created_at) as year,
    EXTRACT(MONTH FROM created_at) as month,
    COUNT(*) as posts_count
FROM posts
GROUP BY EXTRACT(YEAR FROM created_at), EXTRACT(MONTH FROM created_at)
ORDER BY year, month;
```

#### Subqueries
```sql
-- Scalar subquery
SELECT 
    username,
    email,
    (SELECT COUNT(*) FROM posts WHERE user_id = users.id) as post_count
FROM users;

-- EXISTS subquery
SELECT * FROM users u
WHERE EXISTS (
    SELECT 1 FROM posts p 
    WHERE p.user_id = u.id 
    AND p.status = 'published'
);

-- NOT EXISTS subquery
SELECT * FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM posts p 
    WHERE p.user_id = u.id
);

-- IN subquery
SELECT * FROM posts
WHERE user_id IN (
    SELECT id FROM users 
    WHERE created_at > '2024-01-01'
);

-- Correlated subquery
SELECT 
    p.title,
    p.view_count,
    (SELECT AVG(view_count) 
     FROM posts p2 
     WHERE p2.user_id = p.user_id
    ) as user_avg_views
FROM posts p;
```

#### Advanced SELECT Features
```sql
-- CASE expressions
SELECT 
    username,
    CASE 
        WHEN created_at > CURRENT_DATE - INTERVAL '30 days' THEN 'New'
        WHEN created_at > CURRENT_DATE - INTERVAL '1 year' THEN 'Recent'
        ELSE 'Veteran'
    END as user_type,
    CASE 
        WHEN email LIKE '%@gmail.com' THEN 'Gmail'
        WHEN email LIKE '%@yahoo.com' THEN 'Yahoo'
        ELSE 'Other'
    END as email_provider
FROM users;

-- UNION operations
SELECT username as name, 'user' as type FROM users
UNION ALL
SELECT title as name, 'post' as type FROM posts;

-- Common Table Expressions (CTEs)
WITH recent_posts AS (
    SELECT * FROM posts 
    WHERE created_at > CURRENT_DATE - INTERVAL '7 days'
),
post_stats AS (
    SELECT 
        user_id,
        COUNT(*) as recent_post_count,
        AVG(view_count) as avg_views
    FROM recent_posts
    GROUP BY user_id
)
SELECT 
    u.username,
    ps.recent_post_count,
    ps.avg_views
FROM users u
JOIN post_stats ps ON u.id = ps.user_id;
```

### 3. INSERT - Data Creation

#### Basic INSERT Operations
```sql
-- Single row insert
INSERT INTO users (username, email, first_name, last_name)
VALUES ('johndoe', 'john@example.com', 'John', 'Doe');

-- Multiple rows insert
INSERT INTO users (username, email, first_name, last_name) VALUES
    ('alice', 'alice@example.com', 'Alice', 'Smith'),
    ('bob', 'bob@example.com', 'Bob', 'Johnson'),
    ('carol', 'carol@example.com', 'Carol', 'Brown');

-- Insert with all columns
INSERT INTO users (
    username, email, password_hash, first_name, last_name, 
    date_of_birth, is_active, profile_data
) VALUES (
    'admin',
    'admin@company.com',
    '$2b$12$hash...',
    'Admin',
    'User',
    '1990-01-01',
    TRUE,
    '{"role": "administrator", "permissions": ["all"]}'::JSON
);
```

#### Advanced INSERT Operations
```sql
-- INSERT with SELECT (copying data)
INSERT INTO archived_posts (user_id, title, content, original_created_at)
SELECT user_id, title, content, created_at
FROM posts
WHERE created_at < '2023-01-01';

-- INSERT with ON CONFLICT (PostgreSQL) / ON DUPLICATE KEY (MySQL)
-- PostgreSQL version
INSERT INTO users (username, email, first_name, last_name)
VALUES ('johndoe', 'john@example.com', 'John', 'Doe')
ON CONFLICT (username) 
DO UPDATE SET 
    email = EXCLUDED.email,
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    updated_at = CURRENT_TIMESTAMP;

-- MySQL version
INSERT INTO users (username, email, first_name, last_name)
VALUES ('johndoe', 'john@example.com', 'John', 'Doe')
ON DUPLICATE KEY UPDATE
    email = VALUES(email),
    first_name = VALUES(first_name),
    last_name = VALUES(last_name),
    updated_at = CURRENT_TIMESTAMP;

-- INSERT IGNORE (MySQL) - skip if duplicate
INSERT IGNORE INTO users (username, email) 
VALUES ('existing_user', 'existing@example.com');

-- Returning inserted data (PostgreSQL)
INSERT INTO posts (user_id, title, content)
VALUES (1, 'New Post', 'Post content')
RETURNING id, created_at;
```

### 4. UPDATE - Data Modification

#### Basic UPDATE Operations
```sql
-- Simple update
UPDATE users 
SET email = 'newemail@example.com' 
WHERE id = 1;

-- Multiple columns update
UPDATE users 
SET 
    first_name = 'Updated',
    last_name = 'Name',
    updated_at = CURRENT_TIMESTAMP
WHERE username = 'johndoe';

-- Conditional update
UPDATE posts 
SET status = 'published', published_at = CURRENT_TIMESTAMP
WHERE status = 'draft' AND user_id = 1;

-- Mathematical updates
UPDATE posts 
SET view_count = view_count + 1
WHERE id = 123;

-- Update with CASE
UPDATE users
SET status = CASE 
    WHEN last_login < CURRENT_DATE - INTERVAL '1 year' THEN 'inactive'
    WHEN last_login < CURRENT_DATE - INTERVAL '30 days' THEN 'dormant'
    ELSE 'active'
END;
```

#### Advanced UPDATE Operations
```sql
-- Update with JOIN (PostgreSQL)
UPDATE posts 
SET view_count = view_count + 1
FROM users 
WHERE posts.user_id = users.id 
    AND users.username = 'johndoe'
    AND posts.status = 'published';

-- MySQL JOIN syntax for UPDATE
UPDATE posts p
JOIN users u ON p.user_id = u.id
SET p.view_count = p.view_count + 1
WHERE u.username = 'johndoe' 
    AND p.status = 'published';

-- Update with subquery
UPDATE users 
SET post_count = (
    SELECT COUNT(*) 
    FROM posts 
    WHERE posts.user_id = users.id
);

-- Bulk update with ranges
UPDATE posts 
SET status = 'archived'
WHERE created_at < CURRENT_DATE - INTERVAL '2 years'
    AND status != 'featured';

-- Update JSON fields (PostgreSQL)
UPDATE users 
SET profile_data = profile_data || '{"last_updated": "2024-01-01"}'::JSONB
WHERE id = 1;

-- Update with RETURNING (PostgreSQL)
UPDATE posts 
SET view_count = view_count + 1
WHERE id = 123
RETURNING id, title, view_count;
```

### 5. DELETE - Data Removal

#### Basic DELETE Operations
```sql
-- Simple delete
DELETE FROM users WHERE id = 1;

-- Conditional delete
DELETE FROM posts 
WHERE status = 'draft' 
    AND created_at < CURRENT_DATE - INTERVAL '30 days';

-- Delete with multiple conditions
DELETE FROM user_sessions
WHERE expires_at < CURRENT_TIMESTAMP
    OR last_activity < CURRENT_DATE - INTERVAL '7 days';
```

#### Advanced DELETE Operations
```sql
-- Delete with JOIN (PostgreSQL)
DELETE FROM posts
USING users
WHERE posts.user_id = users.id
    AND users.is_active = FALSE;

-- MySQL JOIN syntax for DELETE
DELETE p FROM posts p
JOIN users u ON p.user_id = u.id
WHERE u.is_active = FALSE;

-- Delete with subquery
DELETE FROM comments
WHERE post_id IN (
    SELECT id FROM posts 
    WHERE status = 'deleted'
);

-- Delete with EXISTS
DELETE FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM posts p 
    WHERE p.user_id = u.id
) AND u.created_at < CURRENT_DATE - INTERVAL '1 year';

-- Limited delete (useful for large tables)
DELETE FROM logs 
WHERE created_at < CURRENT_DATE - INTERVAL '90 days'
LIMIT 1000;  -- MySQL syntax

-- Delete with RETURNING (PostgreSQL)
DELETE FROM posts 
WHERE status = 'spam'
RETURNING id, title, user_id;
```

### 6. ALTER - Schema Modifications

#### ALTER TABLE Operations
```sql
-- Add columns
ALTER TABLE users ADD COLUMN phone VARCHAR(20);
ALTER TABLE users ADD COLUMN created_ip INET;  -- PostgreSQL IP type
ALTER TABLE users ADD COLUMN preferences JSON DEFAULT '{}';

-- Modify columns
ALTER TABLE users ALTER COLUMN email SET NOT NULL;
ALTER TABLE users ALTER COLUMN username TYPE VARCHAR(100);
ALTER TABLE posts ALTER COLUMN view_count SET DEFAULT 0;

-- Drop columns
ALTER TABLE users DROP COLUMN old_field;
ALTER TABLE users DROP COLUMN temp_field CASCADE;  -- Drop dependent objects

-- Add constraints
ALTER TABLE users ADD CONSTRAINT uk_users_email UNIQUE (email);
ALTER TABLE posts ADD CONSTRAINT fk_posts_category 
    FOREIGN KEY (category_id) REFERENCES categories(id);
ALTER TABLE users ADD CONSTRAINT chk_email_valid 
    CHECK (email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$');

-- Drop constraints
ALTER TABLE users DROP CONSTRAINT chk_age_positive;
ALTER TABLE posts DROP CONSTRAINT fk_posts_user;

-- Rename table/column
ALTER TABLE old_table_name RENAME TO new_table_name;
ALTER TABLE users RENAME COLUMN username TO user_name;

-- Add/drop indexes
CREATE INDEX idx_users_created_at ON users(created_at);
DROP INDEX idx_old_index;
```

### 7. DROP - Remove Database Objects

#### DROP Operations
```sql
-- Drop table
DROP TABLE IF EXISTS temp_table;
DROP TABLE old_table CASCADE;  -- Drop with dependent objects

-- Drop index
DROP INDEX IF EXISTS idx_old_index;
DROP INDEX CONCURRENTLY idx_large_table_index;  -- PostgreSQL non-blocking

-- Drop constraints
ALTER TABLE users DROP CONSTRAINT IF EXISTS old_constraint;

-- Drop database
DROP DATABASE IF EXISTS old_database;

-- Drop schema
DROP SCHEMA IF EXISTS temp_schema CASCADE;

-- Drop view
DROP VIEW IF EXISTS user_summary_view;

-- Drop function (PostgreSQL)
DROP FUNCTION IF EXISTS calculate_age(DATE);
```

### 8. Transaction Control

#### Transaction Management
```sql
-- Basic transaction
BEGIN;  -- or START TRANSACTION in MySQL
UPDATE users SET email = 'new@example.com' WHERE id = 1;
UPDATE posts SET title = 'Updated Title' WHERE user_id = 1;
COMMIT;

-- Rollback transaction
BEGIN;
DELETE FROM posts WHERE user_id = 1;
-- Something went wrong
ROLLBACK;

-- Savepoints (PostgreSQL)
BEGIN;
INSERT INTO users (username, email) VALUES ('test1', 'test1@example.com');
SAVEPOINT sp1;
INSERT INTO posts (user_id, title) VALUES (1, 'Test Post');
-- Error occurred, rollback to savepoint
ROLLBACK TO SAVEPOINT sp1;
-- Continue with other operations
INSERT INTO users (username, email) VALUES ('test2', 'test2@example.com');
COMMIT;

-- Transaction isolation levels
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;
```

### 9. Data Types and Constraints Reference

#### Common Data Types
```sql
-- Numeric types
INTEGER, BIGINT, SMALLINT
DECIMAL(10,2), NUMERIC(15,2)
FLOAT, DOUBLE PRECISION
SERIAL, BIGSERIAL  -- PostgreSQL auto-increment

-- String types  
CHAR(10)          -- Fixed length
VARCHAR(255)      -- Variable length
TEXT              -- Unlimited length
CITEXT            -- Case-insensitive text (PostgreSQL)

-- Date/Time types
DATE              -- Date only
TIME              -- Time only  
TIMESTAMP         -- Date and time
TIMESTAMPTZ       -- Timestamp with timezone (PostgreSQL)
INTERVAL          -- Time interval

-- Boolean
BOOLEAN, BOOL

-- JSON types
JSON              -- Standard JSON
JSONB             -- Binary JSON (PostgreSQL, more efficient)

-- Array types (PostgreSQL)
INTEGER[]         -- Array of integers
TEXT[]            -- Array of text

-- Network types (PostgreSQL)
INET              -- IP address
CIDR              -- Network address
MACADDR           -- MAC address

-- UUID type
UUID              -- Universally unique identifier
```

#### Constraint Examples
```sql
-- Primary key
id SERIAL PRIMARY KEY
id INTEGER PRIMARY KEY AUTO_INCREMENT  -- MySQL

-- Foreign key with actions
user_id INTEGER REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE

-- Unique constraints
email VARCHAR(100) UNIQUE
UNIQUE(username, email)  -- Composite unique

-- Check constraints
age INTEGER CHECK (age >= 0 AND age <= 150)
email VARCHAR(100) CHECK (email ~ '^[^@]+@[^@]+\.[^@]+$')  -- PostgreSQL regex
status VARCHAR(20) CHECK (status IN ('active', 'inactive', 'pending'))

-- Not null
username VARCHAR(50) NOT NULL
email VARCHAR(100) NOT NULL

-- Default values
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
is_active BOOLEAN DEFAULT TRUE
status VARCHAR(20) DEFAULT 'pending'
```

This comprehensive reference covers all fundamental SQL operations that staff engineers need for daily database work, from basic CRUD to advanced schema management.

### 1. Finding Slow Queries

#### PostgreSQL - Top Slow Queries
```sql
-- Get slowest queries from pg_stat_statements
SELECT 
    query,
    calls,
    total_time,
    mean_time,
    max_time,
    rows,
    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
```
**Explanation**: Shows queries with highest average execution time. `hit_percent` indicates cache efficiency - lower values suggest queries that read from disk frequently.

#### MySQL - Top Slow Queries
```sql
-- Enable slow query log first: SET GLOBAL slow_query_log = 'ON';
-- Get performance schema slow queries
SELECT 
    TRUNCATE(TIMER_WAIT/1000000000000,6) as query_time_seconds,
    SQL_TEXT,
    ROWS_EXAMINED,
    ROWS_SENT,
    CREATED_TMP_TABLES,
    CREATED_TMP_DISK_TABLES
FROM performance_schema.events_statements_history_long 
WHERE TIMER_WAIT > 1000000000000  -- > 1 second
ORDER BY TIMER_WAIT DESC 
LIMIT 10;
```
**Explanation**: Identifies queries taking more than 1 second. `CREATED_TMP_DISK_TABLES` indicates queries that spill to disk.

### 2. Index Usage Analysis

#### PostgreSQL - Unused Indexes
```sql
-- Find indexes that are never used
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes 
WHERE idx_tup_read = 0 
    AND idx_tup_fetch = 0
ORDER BY pg_relation_size(indexrelid) DESC;
```
**Explanation**: Finds indexes consuming space but never used for queries. Consider dropping these to save storage and improve write performance.

#### PostgreSQL - Missing Index Suggestions
```sql
-- Tables with high sequential scan counts (might need indexes)
SELECT 
    schemaname,
    tablename,
    seq_scan,
    seq_tup_read,
    idx_scan,
    seq_tup_read / seq_scan as avg_seq_tup_read
FROM pg_stat_user_tables 
WHERE seq_scan > 100 
    AND seq_tup_read / seq_scan > 1000
ORDER BY seq_tup_read DESC;
```
**Explanation**: Tables with many sequential scans reading lots of rows likely need indexes on frequently queried columns.

### 3. Query Execution Plan Analysis

#### PostgreSQL - Analyze Query Plans
```sql
-- Get actual execution plan with timing and buffers
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) 
SELECT u.username, COUNT(p.id) as post_count
FROM users u 
LEFT JOIN posts p ON u.id = p.user_id 
WHERE u.created_at > '2024-01-01'
GROUP BY u.id, u.username
HAVING COUNT(p.id) > 5;
```
**Explanation**: `ANALYZE` shows actual execution time, `BUFFERS` shows I/O statistics. Look for "Seq Scan" on large tables or high "Buffers" values.

#### MySQL - Execution Plan Analysis
```sql
-- Get execution plan with cost information
EXPLAIN FORMAT=JSON
SELECT u.username, COUNT(p.id) as post_count
FROM users u 
LEFT JOIN posts p ON u.id = p.user_id 
WHERE u.created_at > '2024-01-01'
GROUP BY u.id, u.username
HAVING COUNT(p.id) > 5;
```
**Explanation**: JSON format provides detailed cost estimates. Look for high "query_cost" or "table" scans without indexes.

## Database Monitoring & Health

### 4. Connection Monitoring

#### PostgreSQL - Active Connections
```sql
-- Monitor current connections and their state
SELECT 
    pid,
    usename,
    application_name,
    client_addr,
    state,
    query_start,
    state_change,
    query
FROM pg_stat_activity 
WHERE state != 'idle'
ORDER BY query_start;
```
**Explanation**: Shows active connections and running queries. Use to identify long-running queries or connection leaks.

#### PostgreSQL - Connection Limits
```sql
-- Check connection usage vs limits
SELECT 
    COUNT(*) as current_connections,
    setting::int as max_connections,
    COUNT(*)::float / setting::int * 100 as connection_usage_percent
FROM pg_stat_activity, pg_settings 
WHERE name = 'max_connections';
```
**Explanation**: Monitors connection pool usage. Alert if usage consistently exceeds 80%.

### 5. Lock Detection

#### PostgreSQL - Blocking Queries
```sql
-- Find queries blocking other queries
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS current_statement_in_blocking_process,
    blocked_activity.application_name AS blocked_application,
    blocking_activity.application_name AS blocking_application
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```
**Explanation**: Identifies which queries are blocking others. Essential for debugging deadlocks and performance issues.

### 6. Database Size & Growth

#### PostgreSQL - Table Sizes
```sql
-- Get table sizes with row counts
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) as indexes_size,
    n_tup_ins + n_tup_upd + n_tup_del as total_writes,
    n_live_tup as estimated_rows
FROM pg_tables 
LEFT JOIN pg_stat_user_tables ON pg_tables.tablename = pg_stat_user_tables.relname
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```
**Explanation**: Shows table sizes including indexes. Use for capacity planning and identifying tables that need partitioning.

#### MySQL - Table Sizes
```sql
-- Get table sizes from information schema
SELECT 
    table_schema,
    table_name,
    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS total_size_mb,
    ROUND((data_length / 1024 / 1024), 2) AS data_size_mb,
    ROUND((index_length / 1024 / 1024), 2) AS index_size_mb,
    table_rows
FROM information_schema.tables 
WHERE table_schema NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys')
ORDER BY (data_length + index_length) DESC;
```
**Explanation**: Provides table size breakdown for MySQL. Monitor growth trends for capacity planning.

## Advanced Data Analysis

### 7. Window Functions for Analytics

#### Running Totals and Moving Averages
```sql
-- Calculate running totals and moving averages
SELECT 
    order_date,
    daily_revenue,
    SUM(daily_revenue) OVER (
        ORDER BY order_date 
        ROWS UNBOUNDED PRECEDING
    ) as running_total,
    AVG(daily_revenue) OVER (
        ORDER BY order_date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as seven_day_moving_avg,
    LEAD(daily_revenue, 1) OVER (ORDER BY order_date) as next_day_revenue,
    LAG(daily_revenue, 1) OVER (ORDER BY order_date) as prev_day_revenue
FROM (
    SELECT 
        DATE(created_at) as order_date,
        SUM(total_amount) as daily_revenue
    FROM orders 
    WHERE created_at >= '2024-01-01'
    GROUP BY DATE(created_at)
) daily_stats
ORDER BY order_date;
```
**Explanation**: Window functions calculate aggregates without grouping rows. Essential for time-series analysis and reporting.

#### Ranking and Percentiles
```sql
-- Rank customers by revenue with percentiles
SELECT 
    customer_id,
    total_revenue,
    RANK() OVER (ORDER BY total_revenue DESC) as revenue_rank,
    DENSE_RANK() OVER (ORDER BY total_revenue DESC) as dense_revenue_rank,
    PERCENT_RANK() OVER (ORDER BY total_revenue) as percentile_rank,
    NTILE(10) OVER (ORDER BY total_revenue DESC) as revenue_decile
FROM (
    SELECT 
        customer_id,
        SUM(total_amount) as total_revenue
    FROM orders 
    GROUP BY customer_id
) customer_revenue;
```
**Explanation**: Ranking functions help identify top performers and segment customers/users by performance metrics.

### 8. Common Table Expressions (CTEs)

#### Recursive CTE - Organizational Hierarchy
```sql
-- Get employee hierarchy with recursive CTE
WITH RECURSIVE employee_hierarchy AS (
    -- Base case: top-level managers
    SELECT 
        employee_id,
        name,
        manager_id,
        1 as level,
        CAST(name AS VARCHAR(1000)) as path
    FROM employees 
    WHERE manager_id IS NULL
    
    UNION ALL
    
    -- Recursive case: subordinates
    SELECT 
        e.employee_id,
        e.name,
        e.manager_id,
        eh.level + 1,
        CONCAT(eh.path, ' -> ', e.name)
    FROM employees e
    JOIN employee_hierarchy eh ON e.manager_id = eh.employee_id
)
SELECT 
    employee_id,
    name,
    level,
    path as hierarchy_path
FROM employee_hierarchy
ORDER BY level, name;
```
**Explanation**: Recursive CTEs traverse hierarchical data like organization charts, categories, or threaded comments.

#### Complex Analytics with Multiple CTEs
```sql
-- Customer lifecycle analysis
WITH customer_first_order AS (
    SELECT 
        customer_id,
        MIN(created_at) as first_order_date,
        MIN(total_amount) as first_order_amount
    FROM orders 
    GROUP BY customer_id
),
customer_metrics AS (
    SELECT 
        o.customer_id,
        COUNT(*) as total_orders,
        SUM(o.total_amount) as lifetime_value,
        MAX(o.created_at) as last_order_date,
        co.first_order_date,
        co.first_order_amount
    FROM orders o
    JOIN customer_first_order co ON o.customer_id = co.customer_id
    GROUP BY o.customer_id, co.first_order_date, co.first_order_amount
),
customer_segments AS (
    SELECT 
        *,
        CASE 
            WHEN total_orders = 1 THEN 'One-time'
            WHEN total_orders BETWEEN 2 AND 5 THEN 'Regular'
            WHEN total_orders > 5 THEN 'VIP'
        END as customer_segment,
        EXTRACT(days FROM (CURRENT_DATE - last_order_date)) as days_since_last_order
    FROM customer_metrics
)
SELECT 
    customer_segment,
    COUNT(*) as customer_count,
    AVG(lifetime_value) as avg_lifetime_value,
    AVG(total_orders) as avg_orders,
    AVG(days_since_last_order) as avg_days_since_last_order
FROM customer_segments
GROUP BY customer_segment
ORDER BY avg_lifetime_value DESC;
```
**Explanation**: CTEs break complex analysis into readable steps. Essential for building data pipelines and reports.

## JSON and Modern Data Types

### 9. JSON Operations (PostgreSQL)

#### JSON Query and Manipulation
```sql
-- Query and update JSON data
SELECT 
    id,
    user_data->>'name' as name,
    user_data->>'email' as email,
    (user_data->>'age')::int as age,
    jsonb_array_length(user_data->'skills') as skill_count,
    user_data->'skills' as skills
FROM users 
WHERE user_data->>'status' = 'active'
    AND (user_data->>'age')::int > 25
    AND user_data->'skills' ? 'python';  -- Check if array contains 'python'

-- Update JSON fields
UPDATE users 
SET user_data = jsonb_set(
    user_data, 
    '{last_login}', 
    to_jsonb(CURRENT_TIMESTAMP)
)
WHERE id = 123;

-- Add new skill to array
UPDATE users 
SET user_data = jsonb_set(
    user_data,
    '{skills}',
    (user_data->'skills') || '"sql"'::jsonb
)
WHERE id = 123;
```
**Explanation**: PostgreSQL's JSONB provides powerful querying and manipulation. Use `->` for JSON objects, `->>` for text, and `?` for key/element existence.

#### JSON Aggregation
```sql
-- Aggregate data into JSON
SELECT 
    department,
    json_agg(
        json_build_object(
            'employee_id', employee_id,
            'name', name,
            'salary', salary
        ) ORDER BY salary DESC
    ) as employees,
    AVG(salary) as avg_salary,
    COUNT(*) as employee_count
FROM employees 
GROUP BY department;
```
**Explanation**: `json_agg()` aggregates rows into JSON arrays. Useful for API responses and nested data structures.

### 10. Full-Text Search

#### PostgreSQL - Full-Text Search
```sql
-- Create text search index
CREATE INDEX idx_posts_search ON posts 
USING GIN(to_tsvector('english', title || ' ' || content));

-- Full-text search with ranking
SELECT 
    id,
    title,
    ts_rank(
        to_tsvector('english', title || ' ' || content),
        plainto_tsquery('english', 'database performance')
    ) as rank
FROM posts 
WHERE to_tsvector('english', title || ' ' || content) 
    @@ plainto_tsquery('english', 'database performance')
ORDER BY rank DESC;

-- Advanced search with highlighting
SELECT 
    id,
    title,
    ts_headline(
        'english',
        content,
        plainto_tsquery('english', 'database performance'),
        'MaxWords=20, MinWords=5, ShortWord=3'
    ) as highlighted_content
FROM posts 
WHERE to_tsvector('english', title || ' ' || content) 
    @@ plainto_tsquery('english', 'database performance');
```
**Explanation**: PostgreSQL's full-text search provides ranking and highlighting. GIN indexes make searches fast on large datasets.

## Database Administration

### 11. User Management and Security

#### PostgreSQL - User and Permission Management
```sql
-- Create role with specific permissions
CREATE ROLE app_user WITH LOGIN PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE myapp TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE ON users, orders TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- Create read-only user for analytics
CREATE ROLE analytics_user WITH LOGIN PASSWORD 'analytics_password';
GRANT CONNECT ON DATABASE myapp TO analytics_user;
GRANT USAGE ON SCHEMA public TO analytics_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO analytics_user;

-- Check current permissions
SELECT 
    r.rolname as role_name,
    r.rolsuper as is_superuser,
    r.rolcreaterole as can_create_role,
    r.rolcreatedb as can_create_db,
    r.rolcanlogin as can_login,
    r.rolconnlimit as connection_limit
FROM pg_roles r
WHERE r.rolname NOT LIKE 'pg_%'
ORDER BY r.rolname;
```
**Explanation**: Follow principle of least privilege. Grant only necessary permissions and use separate roles for different application functions.

### 12. Maintenance Operations

#### PostgreSQL - VACUUM and ANALYZE
```sql
-- Check table bloat and maintenance stats
SELECT 
    schemaname,
    tablename,
    n_dead_tup,
    n_live_tup,
    ROUND(n_dead_tup::float / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 2) as dead_tuple_percent,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY dead_tuple_percent DESC;

-- Manual vacuum and analyze
VACUUM ANALYZE users;  -- Reclaim space and update statistics

-- Reindex to rebuild indexes
REINDEX TABLE users;  -- Use CONCURRENTLY in production
```
**Explanation**: Regular maintenance prevents table bloat and keeps query planner statistics current for optimal performance.

#### MySQL - Optimization Commands
```sql
-- Optimize table (defragments and rebuilds indexes)
OPTIMIZE TABLE users;

-- Analyze table to update index statistics
ANALYZE TABLE users;

-- Check table for errors
CHECK TABLE users;

-- Repair table if corrupted
REPAIR TABLE users;
```
**Explanation**: MySQL maintenance commands help maintain performance and fix corruption. Run during low-traffic periods.

### 13. Backup and Recovery Verification

#### PostgreSQL - Backup Commands
```sql
-- Check point-in-time recovery info
SELECT 
    pg_is_in_recovery() as is_in_recovery,
    pg_last_wal_receive_lsn() as last_wal_received,
    pg_last_wal_replay_lsn() as last_wal_replayed,
    CASE 
        WHEN pg_last_wal_receive_lsn() = pg_last_wal_replay_lsn() 
        THEN 'Up to date'
        ELSE 'Lag: ' || pg_wal_lsn_diff(pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn())
    END as replication_status;

-- Create logical backup
-- pg_dump -h localhost -U postgres -d myapp -f backup.sql

-- Continuous archiving status
SELECT 
    name,
    setting,
    unit,
    short_desc
FROM pg_settings 
WHERE name IN ('wal_level', 'archive_mode', 'archive_command', 'max_wal_senders');
```
**Explanation**: Monitor replication lag and backup status. Essential for disaster recovery planning.

## Performance Troubleshooting Queries

### 14. Identifying Performance Bottlenecks

#### PostgreSQL - Buffer Cache Analysis
```sql
-- Check buffer cache hit ratio
SELECT 
    'buffer_cache' as metric,
    ROUND(
        (blks_hit * 100.0 / (blks_hit + blks_read)), 2
    ) as hit_percentage
FROM pg_stat_database 
WHERE datname = current_database();

-- Table-level cache analysis
SELECT 
    schemaname,
    tablename,
    heap_blks_read,
    heap_blks_hit,
    ROUND(
        heap_blks_hit * 100.0 / NULLIF(heap_blks_hit + heap_blks_read, 0), 2
    ) as cache_hit_ratio
FROM pg_statio_user_tables
WHERE heap_blks_read + heap_blks_hit > 0
ORDER BY cache_hit_ratio ASC;
```
**Explanation**: Buffer cache hit ratio should be >95%. Lower ratios indicate queries reading from disk frequently.

#### MySQL - Performance Schema Queries
```sql
-- Top tables by wait time
SELECT 
    OBJECT_SCHEMA,
    OBJECT_NAME,
    COUNT_STAR as total_io_requests,
    SUM_TIMER_WAIT/1000000000000 as total_wait_time_sec,
    AVG_TIMER_WAIT/1000000000000 as avg_wait_time_sec
FROM performance_schema.table_io_waits_summary_by_table 
WHERE OBJECT_SCHEMA NOT IN ('mysql', 'information_schema', 'performance_schema')
ORDER BY SUM_TIMER_WAIT DESC
LIMIT 10;

-- Memory usage by query
SELECT 
    SQL_TEXT,
    CURRENT_MEMORY,
    MAX_MEMORY_USED,
    EXEC_COUNT
FROM performance_schema.events_statements_summary_by_digest 
ORDER BY MAX_MEMORY_USED DESC
LIMIT 10;
```
**Explanation**: Performance Schema provides detailed metrics about query execution and resource usage.

## Quick Reference Commands

### 15. Emergency Troubleshooting

#### Kill Long-Running Queries
```sql
-- PostgreSQL: Find and kill long-running queries
SELECT 
    pid,
    now() - pg_stat_activity.query_start AS duration,
    query 
FROM pg_stat_activity 
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
    AND state = 'active';

-- Kill specific query
SELECT pg_terminate_backend(12345);  -- Replace with actual PID

-- MySQL: Find and kill queries
SELECT 
    id,
    user,
    host,
    db,
    command,
    time,
    state,
    info
FROM information_schema.processlist 
WHERE time > 300  -- Running more than 5 minutes
    AND command = 'Query';

-- Kill specific query
KILL 12345;  -- Replace with actual ID
```
**Explanation**: Use to stop runaway queries that are affecting system performance. Always verify the query before killing it.

This comprehensive SQL reference provides essential queries for database performance monitoring, troubleshooting, and administration that every staff engineer should master.