# Hands-On Project: Building a Scalable Social Media Database

## Project Overview

Design and implement a database architecture for a social media platform that needs to handle:
- 10 million users
- 100 million posts per day
- Real-time notifications
- Global user base
- High availability requirements

## Phase 1: Initial Design

### Requirements Analysis
1. **Functional Requirements**:
   - User registration and authentication
   - Post creation, editing, deletion
   - Following/followers relationships
   - News feed generation
   - Like/comment system
   - Real-time notifications

2. **Non-Functional Requirements**:
   - 99.9% availability
   - < 100ms response time for feeds
   - Support for 50K concurrent users
   - Global deployment
   - GDPR compliance for EU users

### Database Schema Design

#### Initial Tables
```sql
-- Users table
CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    bio TEXT,
    avatar_url VARCHAR(255),
    location VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_verified BOOLEAN DEFAULT FALSE,
    follower_count INT DEFAULT 0,
    following_count INT DEFAULT 0
);

-- Posts table
CREATE TABLE posts (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    media_urls JSON,
    post_type ENUM('text', 'image', 'video') DEFAULT 'text',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    like_count INT DEFAULT 0,
    comment_count INT DEFAULT 0,
    share_count INT DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE,
    
    INDEX idx_user_created (user_id, created_at),
    INDEX idx_created_at (created_at)
);

-- Follows table (relationships)
CREATE TABLE follows (
    follower_id BIGINT NOT NULL REFERENCES users(id),
    followed_id BIGINT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (follower_id, followed_id),
    INDEX idx_followed_user (followed_id, created_at)
);

-- Likes table
CREATE TABLE likes (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    post_id BIGINT NOT NULL REFERENCES posts(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY unique_user_post (user_id, post_id),
    INDEX idx_post_created (post_id, created_at)
);

-- Comments table
CREATE TABLE comments (
    id BIGINT PRIMARY KEY,
    post_id BIGINT NOT NULL REFERENCES posts(id),
    user_id BIGINT NOT NULL REFERENCES users(id),
    parent_comment_id BIGINT REFERENCES comments(id),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    like_count INT DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE,
    
    INDEX idx_post_created (post_id, created_at),
    INDEX idx_parent_comment (parent_comment_id)
);
```

#### Task 1: Identify Potential Issues
Analyze the schema above and identify potential scalability issues:

1. **Single point of failure**: All data in one database
2. **Hot partitions**: Popular users will create uneven load
3. **Fan-out problem**: Users with millions of followers
4. **Cross-table joins**: Complex queries for feed generation
5. **Storage growth**: Posts and media data will grow rapidly

## Phase 2: Implement Sharding Strategy

### User-Based Sharding
```python
import hashlib
import mysql.connector

class DatabaseShardManager:
    def __init__(self, shard_configs):
        self.shards = {}
        self.shard_count = len(shard_configs)
        
        for i, config in enumerate(shard_configs):
            self.shards[i] = mysql.connector.connect(**config)
    
    def get_shard_for_user(self, user_id):
        """Route user to specific shard based on user_id"""
        shard_id = hash(str(user_id)) % self.shard_count
        return self.shards[shard_id]
    
    def get_user(self, user_id):
        conn = self.get_shard_for_user(user_id)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()
    
    def get_user_posts(self, user_id, limit=20, offset=0):
        conn = self.get_shard_for_user(user_id)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM posts 
            WHERE user_id = %s AND is_deleted = FALSE
            ORDER BY created_at DESC 
            LIMIT %s OFFSET %s
        """, (user_id, limit, offset))
        return cursor.fetchall()
    
    def follow_user(self, follower_id, followed_id):
        # Follow relationship stored in follower's shard
        follower_conn = self.get_shard_for_user(follower_id)
        followed_conn = self.get_shard_for_user(followed_id)
        
        # Insert follow relationship
        cursor = follower_conn.cursor()
        cursor.execute("""
            INSERT INTO follows (follower_id, followed_id) 
            VALUES (%s, %s)
        """, (follower_id, followed_id))
        
        # Update counters (requires cross-shard coordination)
        self.update_follow_counts(follower_id, followed_id)
```

### Task 2: Implement Cross-Shard Queries
```python
def get_user_feed(self, user_id, limit=20):
    """Generate feed for user - requires cross-shard queries"""
    # Get user's following list
    conn = self.get_shard_for_user(user_id)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT followed_id FROM follows 
        WHERE follower_id = %s
    """, (user_id,))
    following_list = [row[0] for row in cursor.fetchall()]
    
    if not following_list:
        return []
    
    # Group following by shard
    posts_by_shard = {}
    for followed_id in following_list:
        shard_id = hash(str(followed_id)) % self.shard_count
        if shard_id not in posts_by_shard:
            posts_by_shard[shard_id] = []
        posts_by_shard[shard_id].append(followed_id)
    
    # Query each shard in parallel
    all_posts = []
    for shard_id, user_ids in posts_by_shard.items():
        conn = self.shards[shard_id]
        cursor = conn.cursor(dictionary=True)
        
        placeholders = ','.join(['%s'] * len(user_ids))
        cursor.execute(f"""
            SELECT p.*, u.username, u.avatar_url
            FROM posts p
            JOIN users u ON p.user_id = u.id
            WHERE p.user_id IN ({placeholders})
            AND p.is_deleted = FALSE
            ORDER BY p.created_at DESC
            LIMIT 100
        """, user_ids)
        
        all_posts.extend(cursor.fetchall())
    
    # Sort all posts by created_at and take top N
    all_posts.sort(key=lambda x: x['created_at'], reverse=True)
    return all_posts[:limit]
```

## Phase 3: Implement Caching Layer

### Redis Cache Implementation
```python
import redis
import json
from datetime import timedelta

class SocialMediaCache:
    def __init__(self, redis_config):
        self.redis_client = redis.Redis(**redis_config)
        self.default_ttl = 3600  # 1 hour
    
    def get_user_feed_cache(self, user_id):
        """Get cached user feed"""
        cache_key = f"feed:user:{user_id}"
        cached_feed = self.redis_client.get(cache_key)
        
        if cached_feed:
            return json.loads(cached_feed)
        return None
    
    def set_user_feed_cache(self, user_id, feed_data):
        """Cache user feed"""
        cache_key = f"feed:user:{user_id}"
        self.redis_client.setex(
            cache_key,
            self.default_ttl,
            json.dumps(feed_data, default=str)
        )
    
    def invalidate_user_caches(self, user_id):
        """Invalidate all caches for a user when they post"""
        # Get user's followers
        followers = self.get_user_followers(user_id)
        
        # Invalidate their feeds
        pipeline = self.redis_client.pipeline()
        for follower_id in followers:
            cache_key = f"feed:user:{follower_id}"
            pipeline.delete(cache_key)
        pipeline.execute()
    
    def cache_popular_posts(self):
        """Cache trending/popular posts"""
        # Implementation for caching trending content
        pass
```

### Task 3: Implement Feed Generation with Caching
```python
def get_user_feed_with_cache(self, user_id, limit=20):
    """Get user feed with caching strategy"""
    
    # Try cache first
    cached_feed = self.cache.get_user_feed_cache(user_id)
    if cached_feed:
        return cached_feed[:limit]
    
    # Cache miss - generate feed
    feed = self.get_user_feed(user_id, limit)
    
    # Cache the result
    self.cache.set_user_feed_cache(user_id, feed)
    
    return feed

def create_post(self, user_id, content, post_type='text', media_urls=None):
    """Create post and handle cache invalidation"""
    
    # Insert post into database
    conn = self.get_shard_for_user(user_id)
    cursor = conn.cursor()
    
    post_id = self.generate_post_id()
    cursor.execute("""
        INSERT INTO posts (id, user_id, content, post_type, media_urls)
        VALUES (%s, %s, %s, %s, %s)
    """, (post_id, user_id, content, post_type, json.dumps(media_urls)))
    
    # Invalidate relevant caches
    self.cache.invalidate_user_caches(user_id)
    
    return post_id
```

## Phase 4: Add Read Replicas

### Database Configuration
```python
class ShardWithReplicas:
    def __init__(self, master_config, replica_configs):
        self.master = mysql.connector.connect(**master_config)
        self.replicas = [
            mysql.connector.connect(**config) 
            for config in replica_configs
        ]
        self.current_replica = 0
    
    def get_write_connection(self):
        """Always use master for writes"""
        return self.master
    
    def get_read_connection(self):
        """Round-robin across read replicas"""
        if not self.replicas:
            return self.master
        
        replica = self.replicas[self.current_replica]
        self.current_replica = (self.current_replica + 1) % len(self.replicas)
        return replica
    
    def execute_read_query(self, query, params=None):
        """Execute read query on replica"""
        conn = self.get_read_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        return cursor.fetchall()
    
    def execute_write_query(self, query, params=None):
        """Execute write query on master"""
        conn = self.get_write_connection()
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        conn.commit()
        return cursor.lastrowid
```

### Task 4: Implement Read/Write Splitting
```python
def get_user_posts_optimized(self, user_id, limit=20, offset=0):
    """Use read replica for fetching posts"""
    shard = self.get_shard_for_user(user_id)
    
    return shard.execute_read_query("""
        SELECT p.*, u.username, u.avatar_url
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.user_id = %s AND p.is_deleted = FALSE
        ORDER BY p.created_at DESC 
        LIMIT %s OFFSET %s
    """, (user_id, limit, offset))

def like_post(self, user_id, post_id):
    """Handle post likes with proper read/write splitting"""
    post_owner_id = self.get_post_owner(post_id)
    shard = self.get_shard_for_user(post_owner_id)
    
    # Write to master
    try:
        shard.execute_write_query("""
            INSERT INTO likes (user_id, post_id) 
            VALUES (%s, %s)
        """, (user_id, post_id))
        
        # Update like count
        shard.execute_write_query("""
            UPDATE posts 
            SET like_count = like_count + 1 
            WHERE id = %s
        """, (post_id,))
        
        return True
    except mysql.connector.IntegrityError:
        # User already liked this post
        return False
```

## Phase 5: Performance Monitoring

### Metrics Collection
```python
import time
from functools import wraps

class DatabaseMetrics:
    def __init__(self):
        self.query_times = {}
        self.query_counts = {}
        self.error_counts = {}
    
    def track_query(self, query_type):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    
                    # Record successful execution
                    execution_time = time.time() - start_time
                    self.record_query_time(query_type, execution_time)
                    self.increment_query_count(query_type)
                    
                    return result
                except Exception as e:
                    # Record error
                    self.increment_error_count(query_type, type(e).__name__)
                    raise
            return wrapper
        return decorator
    
    def record_query_time(self, query_type, time_ms):
        if query_type not in self.query_times:
            self.query_times[query_type] = []
        self.query_times[query_type].append(time_ms)
    
    def get_performance_summary(self):
        summary = {}
        for query_type, times in self.query_times.items():
            summary[query_type] = {
                'count': len(times),
                'avg_time': sum(times) / len(times),
                'max_time': max(times),
                'min_time': min(times)
            }
        return summary
```

### Task 5: Add Monitoring to Your Implementation
```python
class MonitoredSocialMediaDB(DatabaseShardManager):
    def __init__(self, shard_configs):
        super().__init__(shard_configs)
        self.metrics = DatabaseMetrics()
    
    @DatabaseMetrics.track_query('get_user_feed')
    def get_user_feed_with_cache(self, user_id, limit=20):
        return super().get_user_feed_with_cache(user_id, limit)
    
    @DatabaseMetrics.track_query('create_post')
    def create_post(self, user_id, content, post_type='text', media_urls=None):
        return super().create_post(user_id, content, post_type, media_urls)
    
    @DatabaseMetrics.track_query('follow_user')
    def follow_user(self, follower_id, followed_id):
        return super().follow_user(follower_id, followed_id)
```

## Phase 6: Testing & Benchmarking

### Load Testing Script
```python
import asyncio
import aiohttp
import random
import time

class SocialMediaLoadTest:
    def __init__(self, base_url, num_users=1000):
        self.base_url = base_url
        self.num_users = num_users
        self.user_tokens = {}
    
    async def simulate_user_activity(self, session, user_id):
        """Simulate realistic user activity"""
        activities = [
            ('view_feed', 0.4),      # 40% chance
            ('create_post', 0.2),    # 20% chance
            ('like_post', 0.2),      # 20% chance
            ('follow_user', 0.1),    # 10% chance
            ('comment_post', 0.1)    # 10% chance
        ]
        
        activity = random.choices(
            [a[0] for a in activities],
            weights=[a[1] for a in activities]
        )[0]
        
        if activity == 'view_feed':
            await self.view_feed(session, user_id)
        elif activity == 'create_post':
            await self.create_post(session, user_id)
        elif activity == 'like_post':
            await self.like_random_post(session, user_id)
        # ... implement other activities
    
    async def view_feed(self, session, user_id):
        start_time = time.time()
        async with session.get(f'{self.base_url}/feed/{user_id}') as response:
            duration = time.time() - start_time
            self.record_metric('view_feed', duration, response.status)
    
    async def run_load_test(self, duration_minutes=10):
        """Run load test for specified duration"""
        async with aiohttp.ClientSession() as session:
            tasks = []
            end_time = time.time() + (duration_minutes * 60)
            
            while time.time() < end_time:
                # Create tasks for concurrent user simulation
                for user_id in range(1, self.num_users + 1):
                    if len(tasks) < 100:  # Limit concurrent tasks
                        task = asyncio.create_task(
                            self.simulate_user_activity(session, user_id)
                        )
                        tasks.append(task)
                
                # Remove completed tasks
                tasks = [t for t in tasks if not t.done()]
                await asyncio.sleep(0.1)
```

### Task 6: Performance Optimization

Based on your load testing results, identify and implement optimizations:

1. **Query Optimization**:
   - Add missing indexes
   - Optimize expensive joins
   - Use query result caching

2. **Cache Strategy Improvements**:
   - Implement cache warming
   - Add cache compression
   - Optimize cache invalidation

3. **Database Tuning**:
   - Connection pool optimization
   - Buffer pool tuning
   - Query plan optimization

## Phase 7: Advanced Features

### Real-time Notifications
```python
import asyncio
import websockets
import json

class NotificationService:
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.connected_clients = {}
    
    async def handle_client(self, websocket, path):
        user_id = await self.authenticate_user(websocket)
        if not user_id:
            await websocket.close(code=4001, reason="Authentication failed")
            return
        
        self.connected_clients[user_id] = websocket
        
        try:
            # Listen for messages from Redis pub/sub
            pubsub = self.redis_client.pubsub()
            pubsub.subscribe(f"notifications:{user_id}")
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    notification = json.loads(message['data'])
                    await websocket.send(json.dumps(notification))
        
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            if user_id in self.connected_clients:
                del self.connected_clients[user_id]
    
    def send_notification(self, user_id, notification_type, data):
        """Send notification via Redis pub/sub"""
        notification = {
            'type': notification_type,
            'data': data,
            'timestamp': time.time()
        }
        
        self.redis_client.publish(
            f"notifications:{user_id}",
            json.dumps(notification)
        )
```

### Task 7: Implement Additional Features
1. **Search functionality**: Add Elasticsearch integration
2. **Content moderation**: Flag inappropriate content
3. **Analytics**: Track user engagement metrics
4. **Geographic features**: Location-based posts and recommendations

## Deliverables

### Final Implementation Requirements
1. **Working database schema** with proper indexing
2. **SQLAlchemy models** with relationships and hybrid properties
3. **Repository pattern implementation** with proper interfaces
4. **Service layer** with business logic and validation
5. **FastAPI application** with dependency injection
6. **Sharding implementation** with cross-shard query support
7. **Caching layer** with Redis integration
8. **Read replica support** with proper read/write splitting
9. **Unit tests** for repositories and services
10. **Integration tests** for API endpoints
11. **Monitoring and metrics** collection
12. **Load testing results** with performance analysis
13. **Documentation** of architecture decisions and trade-offs

### Presentation of Results
Create a summary document covering:
- **Architecture overview**: High-level design decisions
- **Performance metrics**: Throughput, latency, scalability limits
- **Trade-off analysis**: Consistency vs performance vs cost
- **Future improvements**: What would you do differently at 100M users?
- **Lessons learned**: Key insights for staff engineers

This hands-on project will give you practical experience with all the concepts covered in the learning modules and prepare you for real-world database architecture decisions.