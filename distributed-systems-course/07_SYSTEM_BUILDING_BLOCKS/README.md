# Module 07: System Building Blocks
*Essential Infrastructure Components for Distributed Systems*

## Learning Objectives

By the end of this module, you will:
- Understand core infrastructure components needed for distributed systems
- Know when and how to use different database types (SQL, NoSQL, Graph, Time-series)
- Implement effective caching strategies with Redis and distributed caches
- Design message queues and streaming systems with Kafka and RabbitMQ
- Configure load balancers for high availability and performance
- Select appropriate storage systems (object, block, file storage)
- Implement API gateways and service mesh infrastructure
- Set up monitoring and observability infrastructure

## Why Infrastructure Building Blocks Matter

Modern distributed systems are built on a foundation of infrastructure components. Understanding these building blocks is essential for:

- **Architecture Decisions**: Choosing the right tool for the job
- **Performance Optimization**: Understanding performance characteristics
- **Scalability Planning**: Knowing scaling patterns and limitations
- **Cost Management**: Making informed trade-offs between features and cost
- **Operational Excellence**: Understanding operational requirements and failure modes

## Table of Contents

1. [Databases and Storage](#databases-and-storage)
2. [Caching Systems](#caching-systems)
3. [Message Queues and Streaming](#message-queues-and-streaming)
4. [Load Balancers](#load-balancers)
5. [Storage Systems](#storage-systems)
6. [Search and Analytics](#search-and-analytics)
7. [API Gateway and Service Mesh](#api-gateway-and-service-mesh)
8. [Monitoring and Observability Tools](#monitoring-and-observability-tools)

---

## Databases and Storage

### Relational Databases (RDBMS)

**When to Use**: ACID compliance, complex joins, mature ecosystems
**Popular Options**: PostgreSQL, MySQL, Aurora, CockroachDB

#### PostgreSQL Example with Connection Pooling

```python
# database/postgres_client.py
import asyncio
import asyncpg
from asyncpg import Pool
from typing import Optional, List, Dict, Any
import logging

class PostgreSQLClient:
    def __init__(self, connection_string: str, min_size: int = 10, max_size: int = 20):
        self.connection_string = connection_string
        self.min_size = min_size
        self.max_size = max_size
        self.pool: Optional[Pool] = None
        
    async def connect(self):
        """Initialize connection pool"""
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=self.min_size,
            max_size=self.max_size,
            command_timeout=60
        )
        logging.info(f"PostgreSQL pool created: {self.min_size}-{self.max_size} connections")
    
    async def disconnect(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            logging.info("PostgreSQL pool closed")
    
    async def execute_query(self, query: str, *args) -> List[Dict[str, Any]]:
        """Execute SELECT query"""
        async with self.pool.acquire() as connection:
            try:
                rows = await connection.fetch(query, *args)
                return [dict(row) for row in rows]
            except Exception as e:
                logging.error(f"Query failed: {e}")
                raise
    
    async def execute_command(self, command: str, *args) -> str:
        """Execute INSERT/UPDATE/DELETE command"""
        async with self.pool.acquire() as connection:
            try:
                result = await connection.execute(command, *args)
                return result
            except Exception as e:
                logging.error(f"Command failed: {e}")
                raise
    
    async def execute_transaction(self, commands: List[tuple]):
        """Execute multiple commands in a transaction"""
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                results = []
                for command, args in commands:
                    result = await connection.execute(command, *args)
                    results.append(result)
                return results

# Example usage
async def main():
    db = PostgreSQLClient("postgresql://user:pass@localhost/dbname")
    await db.connect()
    
    # Create users table
    await db.execute_command("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Insert user
    await db.execute_command(
        "INSERT INTO users (username, email) VALUES ($1, $2)",
        "john_doe", "john@example.com"
    )
    
    # Query users
    users = await db.execute_query("SELECT * FROM users WHERE username = $1", "john_doe")
    print(f"Users: {users}")
    
    await db.disconnect()
```

#### Database Sharding Implementation

```python
# database/sharding.py
import hashlib
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class ShardConfig:
    shard_id: int
    connection_string: str
    weight: int = 1

class DatabaseSharding:
    def __init__(self, shard_configs: List[ShardConfig]):
        self.shards = {config.shard_id: config for config in shard_configs}
        self.shard_ring = self._build_consistent_hash_ring()
        
    def _build_consistent_hash_ring(self) -> List[int]:
        """Build consistent hash ring for sharding"""
        ring = []
        for shard_config in self.shard_configs:
            # Add multiple points for better distribution
            for i in range(shard_config.weight * 100):
                point = int(hashlib.md5(f"{shard_config.shard_id}:{i}".encode()).hexdigest(), 16)
                ring.append((point, shard_config.shard_id))
        
        ring.sort(key=lambda x: x[0])
        return ring
    
    def get_shard_id(self, shard_key: str) -> int:
        """Get shard ID for a given key"""
        if not self.shard_ring:
            return list(self.shards.keys())[0]
        
        key_hash = int(hashlib.md5(shard_key.encode()).hexdigest(), 16)
        
        # Find the first shard >= key_hash
        for hash_point, shard_id in self.shard_ring:
            if key_hash <= hash_point:
                return shard_id
        
        # Wrap around to first shard
        return self.shard_ring[0][1]
    
    def get_shard_config(self, shard_key: str) -> ShardConfig:
        """Get shard configuration for a key"""
        shard_id = self.get_shard_id(shard_key)
        return self.shards[shard_id]

# Usage example
sharding = DatabaseSharding([
    ShardConfig(1, "postgresql://user:pass@shard1:5432/db", weight=2),
    ShardConfig(2, "postgresql://user:pass@shard2:5432/db", weight=2),
    ShardConfig(3, "postgresql://user:pass@shard3:5432/db", weight=1),
])

user_id = "user_12345"
shard_config = sharding.get_shard_config(user_id)
print(f"User {user_id} belongs to shard {shard_config.shard_id}")
```

### NoSQL Databases

#### Document Store (MongoDB)

```python
# database/mongodb_client.py
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel
import logging
from typing import Dict, List, Any, Optional

class MongoDBClient:
    def __init__(self, connection_string: str, database_name: str):
        self.client = AsyncIOMotorClient(connection_string)
        self.db = self.client[database_name]
        
    async def create_indexes(self, collection_name: str, indexes: List[IndexModel]):
        """Create indexes for better query performance"""
        collection = self.db[collection_name]
        try:
            result = await collection.create_indexes(indexes)
            logging.info(f"Created indexes for {collection_name}: {result}")
        except Exception as e:
            logging.error(f"Failed to create indexes: {e}")
            
    async def insert_document(self, collection_name: str, document: Dict[str, Any]) -> str:
        """Insert a single document"""
        collection = self.db[collection_name]
        result = await collection.insert_one(document)
        return str(result.inserted_id)
    
    async def find_documents(self, collection_name: str, filter_dict: Dict[str, Any], 
                           limit: int = 100) -> List[Dict[str, Any]]:
        """Find documents matching filter"""
        collection = self.db[collection_name]
        cursor = collection.find(filter_dict).limit(limit)
        documents = []
        async for doc in cursor:
            doc['_id'] = str(doc['_id'])  # Convert ObjectId to string
            documents.append(doc)
        return documents
    
    async def update_document(self, collection_name: str, filter_dict: Dict[str, Any], 
                            update_dict: Dict[str, Any]) -> bool:
        """Update document matching filter"""
        collection = self.db[collection_name]
        result = await collection.update_one(filter_dict, {"$set": update_dict})
        return result.modified_count > 0
    
    async def aggregate(self, collection_name: str, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute aggregation pipeline"""
        collection = self.db[collection_name]
        cursor = collection.aggregate(pipeline)
        results = []
        async for doc in cursor:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
            results.append(doc)
        return results

# Example: Product catalog with MongoDB
async def setup_product_catalog():
    mongo = MongoDBClient("mongodb://localhost:27017", "ecommerce")
    
    # Create indexes for product search
    indexes = [
        IndexModel([("name", "text"), ("description", "text")]),
        IndexModel([("category", 1), ("price", 1)]),
        IndexModel([("tags", 1)])
    ]
    await mongo.create_indexes("products", indexes)
    
    # Insert product
    product = {
        "name": "Wireless Headphones",
        "description": "High-quality wireless headphones with noise cancellation",
        "category": "electronics",
        "price": 299.99,
        "tags": ["audio", "wireless", "noise-cancelling"],
        "specifications": {
            "battery_life": "30 hours",
            "connectivity": "Bluetooth 5.0",
            "weight": "250g"
        },
        "inventory": 50
    }
    
    product_id = await mongo.insert_document("products", product)
    print(f"Inserted product with ID: {product_id}")
    
    # Search products
    search_results = await mongo.find_documents(
        "products",
        {"$text": {"$search": "wireless headphones"}}
    )
    print(f"Search results: {search_results}")
```

#### Key-Value Store (Redis)

```python
# database/redis_client.py
import aioredis
import json
import pickle
from typing import Any, Optional, Dict, List
import logging

class RedisClient:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis = None
        
    async def connect(self):
        """Initialize Redis connection"""
        self.redis = await aioredis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20
        )
        logging.info("Redis client connected")
        
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            logging.info("Redis client disconnected")
    
    # String operations
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set key-value with optional TTL"""
        serialized_value = json.dumps(value) if not isinstance(value, str) else value
        if ttl:
            return await self.redis.setex(key, ttl, serialized_value)
        return await self.redis.set(key, serialized_value)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key"""
        value = await self.redis.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    
    # Hash operations
    async def hset(self, hash_key: str, field: str, value: Any) -> bool:
        """Set hash field"""
        serialized_value = json.dumps(value) if not isinstance(value, str) else value
        return await self.redis.hset(hash_key, field, serialized_value)
    
    async def hget(self, hash_key: str, field: str) -> Optional[Any]:
        """Get hash field value"""
        value = await self.redis.hget(hash_key, field)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
            
    async def hgetall(self, hash_key: str) -> Dict[str, Any]:
        """Get all hash fields"""
        hash_data = await self.redis.hgetall(hash_key)
        result = {}
        for field, value in hash_data.items():
            try:
                result[field] = json.loads(value)
            except json.JSONDecodeError:
                result[field] = value
        return result
    
    # List operations
    async def lpush(self, list_key: str, *values: Any) -> int:
        """Push values to left of list"""
        serialized_values = [json.dumps(v) if not isinstance(v, str) else v for v in values]
        return await self.redis.lpush(list_key, *serialized_values)
    
    async def rpop(self, list_key: str) -> Optional[Any]:
        """Pop value from right of list"""
        value = await self.redis.rpop(list_key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    
    # Set operations
    async def sadd(self, set_key: str, *members: Any) -> int:
        """Add members to set"""
        serialized_members = [json.dumps(m) if not isinstance(m, str) else m for m in members]
        return await self.redis.sadd(set_key, *serialized_members)
    
    async def sismember(self, set_key: str, member: Any) -> bool:
        """Check if member exists in set"""
        serialized_member = json.dumps(member) if not isinstance(member, str) else member
        return await self.redis.sismember(set_key, serialized_member)
```

---

## Caching Systems

### Cache Strategies Implementation

```python
# caching/cache_strategies.py
import asyncio
import aioredis
import time
from typing import Any, Optional, Callable
from enum import Enum
import logging
import json

class CacheStrategy(Enum):
    CACHE_ASIDE = "cache_aside"
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    REFRESH_AHEAD = "refresh_ahead"

class CacheManager:
    def __init__(self, redis_client: aioredis.Redis, default_ttl: int = 3600):
        self.redis = redis_client
        self.default_ttl = default_ttl
        
    async def cache_aside_get(self, key: str, loader_func: Callable, ttl: Optional[int] = None) -> Any:
        """Cache-aside pattern: Check cache first, load from source if miss"""
        # Try cache first
        cached_value = await self.redis.get(key)
        if cached_value:
            logging.info(f"Cache hit for key: {key}")
            return json.loads(cached_value)
        
        # Cache miss - load from source
        logging.info(f"Cache miss for key: {key}")
        value = await loader_func()
        
        # Store in cache for future requests
        cache_ttl = ttl or self.default_ttl
        await self.redis.setex(key, cache_ttl, json.dumps(value))
        
        return value
    
    async def write_through_set(self, key: str, value: Any, writer_func: Callable, 
                               ttl: Optional[int] = None):
        """Write-through pattern: Write to cache and storage simultaneously"""
        # Write to storage first
        await writer_func(value)
        
        # Write to cache
        cache_ttl = ttl or self.default_ttl
        await self.redis.setex(key, cache_ttl, json.dumps(value))
        
        logging.info(f"Write-through completed for key: {key}")

# Multi-level caching
class MultiLevelCache:
    def __init__(self, l1_cache: dict, l2_redis: aioredis.Redis, l3_loader: Callable):
        self.l1_cache = l1_cache  # In-memory cache
        self.l2_redis = l2_redis  # Redis cache
        self.l3_loader = l3_loader  # Database loader
        
    async def get(self, key: str) -> Any:
        """Get value from multi-level cache"""
        # L1 Cache (Memory)
        if key in self.l1_cache:
            logging.info(f"L1 cache hit: {key}")
            return self.l1_cache[key]
        
        # L2 Cache (Redis)
        redis_value = await self.l2_redis.get(key)
        if redis_value:
            logging.info(f"L2 cache hit: {key}")
            value = json.loads(redis_value)
            self.l1_cache[key] = value  # Promote to L1
            return value
        
        # L3 Load from source
        logging.info(f"Cache miss, loading from source: {key}")
        value = await self.l3_loader(key)
        
        # Store in all levels
        self.l1_cache[key] = value
        await self.l2_redis.setex(key, 3600, json.dumps(value))
        
        return value
```

---

## Message Queues and Streaming

### Apache Kafka Implementation

```python
# messaging/kafka_client.py
from kafka import KafkaProducer, KafkaConsumer
import json
import logging
from typing import Dict, Any, List, Callable, Optional
import asyncio
import time

class KafkaProducerClient:
    def __init__(self, bootstrap_servers: List[str], **config):
        self.config = {
            'bootstrap_servers': bootstrap_servers,
            'value_serializer': lambda v: json.dumps(v).encode('utf-8'),
            'key_serializer': lambda k: k.encode('utf-8') if k else None,
            'acks': 'all',  # Wait for all replicas
            'retries': 5,
            'retry_backoff_ms': 300,
            'batch_size': 16384,
            'linger_ms': 10,
            **config
        }
        self.producer = None
    
    def connect(self):
        """Initialize Kafka producer"""
        self.producer = KafkaProducer(**self.config)
        logging.info("Kafka producer connected")
    
    async def send_message(self, topic: str, message: Dict[str, Any], 
                          key: Optional[str] = None) -> bool:
        """Send message to Kafka topic"""
        try:
            future = self.producer.send(topic, value=message, key=key)
            record_metadata = future.get(timeout=10)
            logging.info(f"Message sent to {record_metadata.topic}:{record_metadata.partition}@{record_metadata.offset}")
            return True
        except Exception as e:
            logging.error(f"Failed to send message: {e}")
            return False
    
    def close(self):
        """Close producer connection"""
        if self.producer:
            self.producer.flush()
            self.producer.close()

class KafkaConsumerClient:
    def __init__(self, topics: List[str], group_id: str, bootstrap_servers: List[str], **config):
        self.topics = topics
        self.config = {
            'bootstrap_servers': bootstrap_servers,
            'group_id': group_id,
            'value_deserializer': lambda v: json.loads(v.decode('utf-8')),
            'key_deserializer': lambda k: k.decode('utf-8') if k else None,
            'auto_offset_reset': 'earliest',
            'enable_auto_commit': False,  # Manual commit for better control
            'max_poll_records': 100,
            **config
        }
        self.consumer = None
        self.message_handlers: Dict[str, Callable] = {}
        
    def connect(self):
        """Initialize Kafka consumer"""
        self.consumer = KafkaConsumer(**self.config)
        self.consumer.subscribe(self.topics)
        logging.info(f"Kafka consumer connected to topics: {self.topics}")
    
    def register_handler(self, topic: str, handler: Callable):
        """Register message handler for specific topic"""
        self.message_handlers[topic] = handler
    
    async def consume_messages(self):
        """Start consuming messages"""
        while True:
            try:
                message_batch = self.consumer.poll(timeout_ms=1000)
                
                for topic_partition, messages in message_batch.items():
                    topic = topic_partition.topic
                    handler = self.message_handlers.get(topic)
                    
                    if handler:
                        for message in messages:
                            try:
                                await handler(message.value, message.key, message)
                                logging.info(f"Processed message from {topic}:{message.partition}@{message.offset}")
                            except Exception as e:
                                logging.error(f"Error processing message: {e}")
                    
                    # Commit offsets after successful processing
                    self.consumer.commit()
                    
            except Exception as e:
                logging.error(f"Consumer error: {e}")
                await asyncio.sleep(1)
```

---

## Load Balancers

### Layer 4 Load Balancer Implementation

```python
# load_balancing/layer4_lb.py
import asyncio
import socket
import logging
from typing import List, Dict, Any
from enum import Enum
from dataclasses import dataclass
import time
import random

class LoadBalancingAlgorithm(Enum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    IP_HASH = "ip_hash"

@dataclass
class BackendServer:
    host: str
    port: int
    weight: int = 1
    active_connections: int = 0
    total_requests: int = 0
    healthy: bool = True

class Layer4LoadBalancer:
    def __init__(self, backend_servers: List[BackendServer], 
                 algorithm: LoadBalancingAlgorithm = LoadBalancingAlgorithm.ROUND_ROBIN):
        self.backend_servers = backend_servers
        self.algorithm = algorithm
        self.current_index = 0
        
    def select_server(self, client_ip: str = None) -> BackendServer:
        """Select backend server based on load balancing algorithm"""
        healthy_servers = [s for s in self.backend_servers if s.healthy]
        
        if not healthy_servers:
            raise Exception("No healthy backend servers available")
        
        if self.algorithm == LoadBalancingAlgorithm.ROUND_ROBIN:
            return self._round_robin(healthy_servers)
        elif self.algorithm == LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN:
            return self._weighted_round_robin(healthy_servers)
        elif self.algorithm == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
            return self._least_connections(healthy_servers)
        elif self.algorithm == LoadBalancingAlgorithm.IP_HASH:
            return self._ip_hash(healthy_servers, client_ip)
    
    def _round_robin(self, servers: List[BackendServer]) -> BackendServer:
        """Simple round-robin selection"""
        server = servers[self.current_index % len(servers)]
        self.current_index += 1
        return server
    
    def _weighted_round_robin(self, servers: List[BackendServer]) -> BackendServer:
        """Weighted round-robin selection"""
        total_weight = sum(s.weight for s in servers)
        random_weight = random.randint(1, total_weight)
        
        current_weight = 0
        for server in servers:
            current_weight += server.weight
            if random_weight <= current_weight:
                return server
        
        return servers[0]  # Fallback
    
    def _least_connections(self, servers: List[BackendServer]) -> BackendServer:
        """Select server with least active connections"""
        return min(servers, key=lambda s: s.active_connections)
    
    def _ip_hash(self, servers: List[BackendServer], client_ip: str) -> BackendServer:
        """Select server based on client IP hash"""
        import hashlib
        if not client_ip:
            return self._round_robin(servers)
        
        hash_value = int(hashlib.md5(client_ip.encode()).hexdigest(), 16)
        index = hash_value % len(servers)
        return servers[index]
```

---

## Storage Systems

### Object Storage (S3-compatible)

```python
# storage/object_storage.py
import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any, List, Optional
import logging
from dataclasses import dataclass
from datetime import datetime

@dataclass
class StorageObject:
    key: str
    size: int
    last_modified: datetime
    etag: str
    metadata: Dict[str, str]

class ObjectStorageClient:
    def __init__(self, endpoint_url: str, access_key: str, secret_key: str, 
                 bucket_name: str, region: str = 'us-east-1'):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        
    def create_bucket(self):
        """Create storage bucket"""
        try:
            self.s3_client.create_bucket(Bucket=self.bucket_name)
            logging.info(f"Created bucket: {self.bucket_name}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'BucketAlreadyExists':
                logging.info(f"Bucket {self.bucket_name} already exists")
            else:
                logging.error(f"Failed to create bucket: {e}")
                raise
```

---

## Search and Analytics

### Elasticsearch Implementation

```python
# search/elasticsearch_client.py
from elasticsearch import AsyncElasticsearch
from typing import Dict, Any, List, Optional
import logging
import json

class ElasticsearchClient:
    def __init__(self, hosts: List[str], **config):
        self.es_client = AsyncElasticsearch(hosts, **config)
        
    async def close(self):
        """Close Elasticsearch connection"""
        await self.es_client.close()
    
    async def create_index(self, index_name: str, mapping: Dict[str, Any], 
                          settings: Dict[str, Any] = None):
        """Create index with mapping and settings"""
        body = {"mappings": mapping}
        if settings:
            body["settings"] = settings
            
        try:
            await self.es_client.indices.create(index=index_name, body=body)
            logging.info(f"Created index: {index_name}")
        except Exception as e:
            if "resource_already_exists_exception" in str(e):
                logging.info(f"Index {index_name} already exists")
            else:
                logging.error(f"Failed to create index: {e}")
                raise
```

---

## API Gateway and Service Mesh

### API Gateway Implementation

```python
# gateway/api_gateway.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import time
from typing import Dict, Any, List, Optional
import asyncio
import logging
from dataclasses import dataclass

@dataclass
class ServiceRoute:
    path_prefix: str
    service_url: str
    timeout: int = 30
    retries: int = 3
    auth_required: bool = True

class APIGateway:
    def __init__(self):
        self.app = FastAPI(title="API Gateway", version="1.0.0")
        self.services: Dict[str, ServiceRoute] = {}
        self.setup_middleware()
        self.setup_routes()
        
    def setup_middleware(self):
        """Setup gateway middleware"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        @self.app.middleware("http")
        async def logging_middleware(request: Request, call_next):
            start_time = time.time()
            response = await call_next(request)
            process_time = time.time() - start_time
            logging.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
            response.headers["X-Process-Time"] = str(process_time)
            return response
```

---

## Monitoring and Observability Tools

### Comprehensive Monitoring Stack

```python
# monitoring/metrics_collector.py
import time
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque
import psutil
import logging

@dataclass
class Metric:
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)
    metric_type: str = "gauge"  # gauge, counter, histogram, summary

class MetricsCollector:
    def __init__(self):
        self.metrics: Dict[str, List[Metric]] = defaultdict(list)
        self.counters: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
    def counter(self, name: str, value: float = 1.0, tags: Dict[str, str] = None):
        """Increment counter metric"""
        self.counters[name] += value
        metric = Metric(name, self.counters[name], time.time(), tags or {}, "counter")
        self.metrics[name].append(metric)
        
    def gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """Set gauge metric"""
        metric = Metric(name, value, time.time(), tags or {}, "gauge")
        self.metrics[name].append(metric)
        
    def histogram(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record histogram metric"""
        self.histograms[name].append(value)
        metric = Metric(name, value, time.time(), tags or {}, "histogram")
        self.metrics[name].append(metric)
```

---

## Summary and Best Practices

### Infrastructure Selection Matrix

| Use Case | Database | Cache | Message Queue | Load Balancer | Storage |
|----------|----------|-------|---------------|---------------|---------|
| **E-commerce** | PostgreSQL + Redis | Redis (multi-level) | Kafka + RabbitMQ | Nginx/HAProxy | S3 + CDN |
| **Analytics** | ClickHouse + Elasticsearch | Redis Cluster | Kafka | Application LB | Data Lake (S3/HDFS) |
| **Social Media** | MongoDB + PostgreSQL | Redis + Memcached | Kafka | Geographic LB | Object Storage + CDN |
| **IoT Platform** | TimescaleDB + InfluxDB | Redis + Local Cache | MQTT + Kafka | IoT Gateway | Time-series Storage |
| **Microservices** | PostgreSQL per service | Distributed Redis | Service Mesh + Kafka | Service Mesh LB | Distributed Storage |

### Performance Considerations

#### Database Performance
- **Connection Pooling**: Always use connection pools (10-20 connections per service)
- **Read Replicas**: Separate read and write workloads
- **Sharding**: Horizontal partitioning for scale
- **Indexing**: Proper indexing strategy for query patterns

#### Caching Best Practices
- **Cache Hierarchy**: L1 (memory) → L2 (Redis) → L3 (database)
- **TTL Strategy**: Short TTL for frequently changing data, longer for static data
- **Cache Warming**: Pre-populate cache with expected data
- **Invalidation**: Implement proper cache invalidation strategies

#### Message Queue Optimization
- **Partitioning**: Use topic partitioning for scalability
- **Batch Processing**: Process messages in batches for efficiency
- **Dead Letter Queues**: Handle failed messages appropriately
- **Monitoring**: Track queue depth and processing latency

### Operational Excellence

#### Monitoring Strategy
1. **Golden Signals**: Latency, traffic, errors, saturation
2. **Business Metrics**: Revenue, user engagement, conversion rates
3. **Infrastructure Metrics**: CPU, memory, disk, network
4. **Application Metrics**: Response times, error rates, throughput

### Security Considerations

#### Database Security
- **Encryption**: Data at rest and in transit
- **Access Control**: Role-based access control (RBAC)
- **Network Security**: VPC, private subnets, security groups
- **Audit Logging**: Track all database access and changes

#### API Security
- **Authentication**: JWT tokens, OAuth 2.0
- **Authorization**: Role-based and attribute-based access control
- **Rate Limiting**: Prevent abuse and DDoS attacks
- **Input Validation**: Sanitize all input data

---

## Lab Exercises

### Exercise 1: Database Selection and Setup
**Objective**: Set up different database types for various use cases

**Tasks**:
1. Set up PostgreSQL with connection pooling for transactional data
2. Configure Redis cluster for caching layer
3. Set up MongoDB for document storage
4. Implement database sharding for user data
5. Create read replicas and measure performance difference

### Exercise 2: Caching Strategy Implementation
**Objective**: Implement multi-level caching with various strategies

**Tasks**:
1. Implement cache-aside pattern with Redis
2. Set up multi-level caching (L1 memory, L2 Redis)
3. Implement distributed caching with consistent hashing
4. Create cache warming and invalidation strategies
5. Measure cache hit rates and performance impact

### Exercise 3: Message Queue and Streaming
**Objective**: Build event-driven system with Kafka and RabbitMQ

**Tasks**:
1. Set up Kafka cluster with multiple topics
2. Implement stream processing for real-time analytics
3. Set up RabbitMQ for task queues
4. Create event sourcing pattern
5. Implement saga pattern for distributed transactions

### Exercise 4: Load Balancer and API Gateway
**Objective**: Implement traffic management and API gateway

**Tasks**:
1. Set up Layer 4 load balancer with health checks
2. Implement API gateway with authentication and rate limiting
3. Configure service discovery
4. Set up circuit breakers
5. Implement request routing and transformation

### Exercise 5: Monitoring and Observability
**Objective**: Build comprehensive monitoring stack

**Tasks**:
1. Set up metrics collection (Prometheus)
2. Implement distributed tracing (Jaeger)
3. Configure log aggregation (ELK stack)
4. Create dashboards (Grafana)
5. Set up alerting rules and notification channels

---

## Next Steps

After completing this module, you should:

1. **Understand Infrastructure Components**: Know when and how to use different building blocks
2. **Make Informed Decisions**: Understand trade-offs between different technologies
3. **Implement Best Practices**: Apply performance, security, and operational best practices
4. **Design for Scale**: Plan for growth and handle increased load
5. **Operate Reliably**: Monitor, alert, and troubleshoot distributed systems

### Continue Learning

- **Module 08**: [Performance and Scalability](../08_PERFORMANCE_SCALABILITY/)
- **Module 09**: [Deployment and Operations](../09_DEPLOYMENT_OPERATIONS/)
- **Module 10**: [Organizational Patterns](../10_ORGANIZATIONAL_PATTERNS/)
- **Hands-on Projects**: [Start with Project 1](../hands-on-projects/01_ecommerce_microservices/)

---

*Remember: Infrastructure choices have long-term implications. Choose technologies that align with your team's expertise, operational capabilities, and growth trajectory. Start simple and evolve based on actual requirements and constraints.*