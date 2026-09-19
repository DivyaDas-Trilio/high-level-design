# RabbitMQ Deep Dive: Complete Feature Reference
## Comprehensive Guide to RabbitMQ Concepts and Implementation

---

## 📋 **Table of Contents**

1. [Core Architecture & Concepts](#core-architecture--concepts)
2. [Exchange Types & Routing](#exchange-types--routing)
3. [Queue Features & Configuration](#queue-features--configuration)
4. [Message Properties & Persistence](#message-properties--persistence)
5. [Consumer Patterns & Acknowledgments](#consumer-patterns--acknowledgments)
6. [Advanced Features](#advanced-features)
7. [Request-Reply (RPC) Patterns](#request-reply-rpc-patterns)
8. [Enterprise Integration Patterns](#enterprise-integration-patterns)
9. [Clustering & High Availability](#clustering--high-availability)
10. [Management & Monitoring](#management--monitoring)
11. [Command Line Tools (rabbitmqctl & rabbitmqadmin)](#command-line-tools-rabbitmqctl--rabbitmqadmin)
12. [Performance Tuning](#performance-tuning)
13. [Security Features](#security-features)
14. [Production Deployment & Infrastructure](#production-deployment--infrastructure)
15. [Operational Procedures](#operational-procedures)
16. [Practical Implementation Examples](#practical-implementation-examples)

---

## 🏗️ **Core Architecture & Concepts**

### **AMQP Model Overview**

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Producer   │───▶│  Exchange   │───▶│    Queue    │───▶│  Consumer   │
│             │    │             │    │             │    │             │
│ Publishes   │    │ Routes      │    │ Stores      │    │ Consumes    │
│ Messages    │    │ Messages    │    │ Messages    │    │ Messages    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                           │                   ▲
                           └─── Binding ───────┘
                         (Routing Rules)
```

### **Core Components**

#### **1. Connection & Channel**

```python
import pika
from typing import Optional

class RabbitMQConnection:
    """Manages RabbitMQ connection and channels"""
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 5672,
        username: str = 'guest',
        password: str = 'guest',
        virtual_host: str = '/',
        heartbeat: int = 600,
        blocked_connection_timeout: int = 300
    ):
        self.connection_params = pika.ConnectionParameters(
            host=host,
            port=port,
            virtual_host=virtual_host,
            credentials=pika.PlainCredentials(username, password),
            heartbeat=heartbeat,
            blocked_connection_timeout=blocked_connection_timeout
        )
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
    
    def connect(self):
        """Establish connection and create channel"""
        self.connection = pika.BlockingConnection(self.connection_params)
        self.channel = self.connection.channel()
        
        # Enable publisher confirms for reliability
        self.channel.confirm_delivery()
        print("✅ Connected to RabbitMQ")
    
    def close(self):
        """Close connection gracefully"""
        if self.channel and not self.channel.is_closed:
            self.channel.close()
        if self.connection and not self.connection.is_closed:
            self.connection.close()
        print("🔌 Disconnected from RabbitMQ")
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Basic usage
with RabbitMQConnection() as rmq:
    channel = rmq.channel
    # Use channel for operations
```

#### **2. Virtual Hosts (vhosts)**

```python
def create_virtual_host_example():
    """Virtual hosts provide logical separation"""
    
    # Virtual hosts are like separate RabbitMQ instances
    # Common patterns:
    
    environments = {
        '/dev': 'Development environment',
        '/staging': 'Staging environment', 
        '/prod': 'Production environment'
    }
    
    applications = {
        '/ecommerce': 'E-commerce application',
        '/analytics': 'Analytics application',
        '/notifications': 'Notification service'
    }
    
    # Each vhost has its own:
    # - Exchanges, queues, bindings
    # - User permissions
    # - Resource limits
    
    print("🏠 Virtual hosts provide isolation and multi-tenancy")
```

---

## 🔄 **Exchange Types & Routing**

### **1. Direct Exchange**

Routes messages to queues based on exact routing key match.

```python
def direct_exchange_example():
    """Direct exchange: exact routing key matching"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # Declare direct exchange
        exchange_name = 'orders_direct'
        channel.exchange_declare(
            exchange=exchange_name,
            exchange_type='direct',
            durable=True
        )
        
        # Create queues for different order types
        queues = ['priority_orders', 'standard_orders', 'bulk_orders']
        
        for queue in queues:
            # Declare queue
            channel.queue_declare(queue=queue, durable=True)
            
            # Bind queue with routing key
            channel.queue_bind(
                exchange=exchange_name,
                queue=queue,
                routing_key=queue.replace('_orders', '')
            )
        
        # Publish messages with specific routing keys
        orders = [
            ('priority', {'order_id': '001', 'customer': 'VIP'}),
            ('standard', {'order_id': '002', 'customer': 'Regular'}),
            ('bulk', {'order_id': '003', 'customer': 'Wholesale'})
        ]
        
        for routing_key, order_data in orders:
            channel.basic_publish(
                exchange=exchange_name,
                routing_key=routing_key,
                body=json.dumps(order_data),
                properties=pika.BasicProperties(delivery_mode=2)  # Persistent
            )
            print(f"📦 Published {routing_key} order to {routing_key}_orders queue")

# Routing behavior:
# priority -> priority_orders queue
# standard -> standard_orders queue  
# bulk -> bulk_orders queue
# unknown -> nowhere (returned or dropped)
```

### **2. Topic Exchange**

Routes messages based on pattern matching with wildcards.

```python
def topic_exchange_example():
    """Topic exchange: pattern-based routing with wildcards"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # Declare topic exchange
        exchange_name = 'events_topic'
        channel.exchange_declare(
            exchange=exchange_name,
            exchange_type='topic',
            durable=True
        )
        
        # Queue bindings with wildcard patterns
        bindings = [
            ('user_events', 'user.*'),           # All user events
            ('order_events', 'order.*'),         # All order events
            ('critical_alerts', '*.critical'),   # All critical events
            ('audit_log', '#'),                  # All events (# = zero or more words)
            ('payment_processing', 'payment.processed'),  # Specific event
            ('us_orders', 'order.*.us'),         # US orders only
        ]
        
        for queue_name, routing_pattern in bindings:
            # Declare queue
            channel.queue_declare(queue=queue_name, durable=True)
            
            # Bind with pattern
            channel.queue_bind(
                exchange=exchange_name,
                queue=queue_name,
                routing_key=routing_pattern
            )
        
        # Publish events with hierarchical routing keys
        events = [
            ('user.created', {'user_id': '123', 'email': 'user@example.com'}),
            ('user.updated', {'user_id': '123', 'field': 'email'}),
            ('user.critical', {'user_id': '123', 'issue': 'security_breach'}),
            ('order.created.us', {'order_id': '456', 'region': 'us'}),
            ('order.shipped.eu', {'order_id': '789', 'region': 'eu'}),
            ('payment.processed', {'payment_id': '101', 'amount': 99.99}),
            ('system.critical', {'alert': 'disk_full', 'server': 'web01'})
        ]
        
        for routing_key, event_data in events:
            channel.basic_publish(
                exchange=exchange_name,
                routing_key=routing_key,
                body=json.dumps(event_data),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    headers={'event_type': routing_key}
                )
            )
            print(f"📡 Published event: {routing_key}")

# Wildcard rules:
# * (star) = exactly one word
# # (hash) = zero or more words
# 
# Example routing:
# user.created -> user_events, audit_log
# user.critical -> user_events, critical_alerts, audit_log
# order.created.us -> order_events, us_orders, audit_log
# payment.processed -> payment_processing, audit_log
```

### **3. Fanout Exchange**

Routes messages to ALL bound queues (broadcast).

```python
def fanout_exchange_example():
    """Fanout exchange: broadcast to all queues"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # Declare fanout exchange
        exchange_name = 'notifications_fanout'
        channel.exchange_declare(
            exchange=exchange_name,
            exchange_type='fanout',
            durable=True
        )
        
        # Multiple services subscribe to user events
        subscriber_queues = [
            'email_notifications',
            'push_notifications',
            'sms_notifications',
            'analytics_events',
            'audit_trail'
        ]
        
        for queue_name in subscriber_queues:
            # Declare queue
            channel.queue_declare(queue=queue_name, durable=True)
            
            # Bind to fanout exchange (routing key ignored)
            channel.queue_bind(
                exchange=exchange_name,
                queue=queue_name,
                routing_key=''  # Ignored in fanout
            )
        
        # Publish user registration event
        user_registered = {
            'event': 'user_registered',
            'user_id': '789',
            'email': 'newuser@example.com',
            'registration_time': '2024-01-15T10:30:00Z',
            'source': 'web_app'
        }
        
        channel.basic_publish(
            exchange=exchange_name,
            routing_key='',  # Ignored in fanout
            body=json.dumps(user_registered),
            properties=pika.BasicProperties(
                delivery_mode=2,
                message_id=str(uuid4()),
                timestamp=int(time.time())
            )
        )
        
        print(f"📢 Broadcasted user registration to {len(subscriber_queues)} services")

# Fanout behavior:
# Single message -> ALL bound queues receive a copy
# Perfect for event broadcasting and pub/sub patterns
```

### **4. Headers Exchange**

Routes messages based on header attributes instead of routing key.

```python
def headers_exchange_example():
    """Headers exchange: route based on message headers"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # Declare headers exchange
        exchange_name = 'content_headers'
        channel.exchange_declare(
            exchange=exchange_name,
            exchange_type='headers',
            durable=True
        )
        
        # Queue bindings based on headers
        queue_bindings = [
            # Format: (queue_name, header_conditions, match_type)
            ('image_processor', {'type': 'image', 'priority': 'high'}, 'all'),
            ('video_processor', {'type': 'video'}, 'any'),
            ('priority_queue', {'priority': 'high'}, 'any'),
            ('archive_queue', {'archive': 'true', 'processed': 'true'}, 'all'),
            ('error_queue', {'status': 'error'}, 'any')
        ]
        
        for queue_name, headers, match_type in queue_bindings:
            # Declare queue
            channel.queue_declare(queue=queue_name, durable=True)
            
            # Prepare binding arguments
            binding_args = headers.copy()
            binding_args['x-match'] = match_type  # 'all' or 'any'
            
            # Bind with header conditions
            channel.queue_bind(
                exchange=exchange_name,
                queue=queue_name,
                routing_key='',  # Ignored in headers exchange
                arguments=binding_args
            )
        
        # Publish messages with different headers
        messages = [
            {
                'body': {'file': 'photo.jpg', 'size': '2MB'},
                'headers': {'type': 'image', 'priority': 'high', 'format': 'jpeg'}
            },
            {
                'body': {'file': 'video.mp4', 'size': '100MB'}, 
                'headers': {'type': 'video', 'priority': 'low', 'format': 'mp4'}
            },
            {
                'body': {'file': 'document.pdf', 'size': '1MB'},
                'headers': {'type': 'document', 'priority': 'high', 'format': 'pdf'}
            },
            {
                'body': {'file': 'corrupted.bin', 'error': 'parse_failed'},
                'headers': {'status': 'error', 'type': 'unknown'}
            }
        ]
        
        for message in messages:
            channel.basic_publish(
                exchange=exchange_name,
                routing_key='',
                body=json.dumps(message['body']),
                properties=pika.BasicProperties(
                    headers=message['headers'],
                    delivery_mode=2
                )
            )
            print(f"📤 Published message with headers: {message['headers']}")

# Headers routing logic:
# x-match = 'all': ALL header conditions must match
# x-match = 'any': ANY header condition must match
#
# Example routing:
# image + high priority -> image_processor, priority_queue
# video (any priority) -> video_processor  
# document + high priority -> priority_queue
# error status -> error_queue
```

---

## 📦 **Queue Features & Configuration**

### **1. Basic Queue Declaration**

```python
def queue_declaration_examples():
    """Different queue declaration patterns"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # 1. Basic durable queue
        channel.queue_declare(
            queue='orders',
            durable=True,        # Survives broker restart
            exclusive=False,     # Can be accessed by multiple connections
            auto_delete=False    # Won't be deleted when last consumer disconnects
        )
        
        # 2. Temporary exclusive queue (for RPC patterns)
        result = channel.queue_declare(
            queue='',           # Empty name = server generates unique name
            exclusive=True,     # Only this connection can access
            auto_delete=True    # Deleted when connection closes
        )
        temp_queue = result.method.queue
        print(f"🎫 Created temporary queue: {temp_queue}")
        
        # 3. Queue with TTL (Time To Live)
        channel.queue_declare(
            queue='temp_processing',
            durable=True,
            arguments={
                'x-message-ttl': 60000,  # Messages expire after 60 seconds
                'x-expires': 300000      # Queue deleted after 5 minutes of inactivity
            }
        )
        
        # 4. Queue with size limits
        channel.queue_declare(
            queue='limited_queue',
            durable=True,
            arguments={
                'x-max-length': 1000,           # Max 1000 messages
                'x-max-length-bytes': 10485760, # Max 10MB total size
                'x-overflow': 'reject-publish'  # Reject new messages when full
            }
        )
        
        # 5. Priority queue
        channel.queue_declare(
            queue='priority_tasks',
            durable=True,
            arguments={
                'x-max-priority': 10  # Priorities 0-10, higher = more priority
            }
        )
        
        print("📋 Created queues with various configurations")
```

### **2. Dead Letter Exchange (DLX)**

```python
def dead_letter_exchange_example():
    """Dead Letter Exchange for handling failed messages"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # 1. Create dead letter exchange and queue
        dlx_exchange = 'failed_messages_dlx'
        dlq_queue = 'failed_messages_dlq'
        
        channel.exchange_declare(exchange=dlx_exchange, exchange_type='direct')
        channel.queue_declare(queue=dlq_queue, durable=True)
        channel.queue_bind(exchange=dlx_exchange, queue=dlq_queue, routing_key='failed')
        
        # 2. Create main queue with DLX configuration
        main_queue = 'processing_queue'
        channel.queue_declare(
            queue=main_queue,
            durable=True,
            arguments={
                'x-dead-letter-exchange': dlx_exchange,
                'x-dead-letter-routing-key': 'failed',
                'x-message-ttl': 30000,  # 30 seconds TTL
            }
        )
        
        # 3. Publish test message
        test_message = {'task': 'process_data', 'data': 'sample'}
        channel.basic_publish(
            exchange='',
            routing_key=main_queue,
            body=json.dumps(test_message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        
        print(f"💀 Set up DLX: {dlx_exchange} -> {dlq_queue}")
        print("Messages go to DLQ when: TTL expires, rejected, max retries reached")

# Dead letter scenarios:
# 1. Message TTL expires
# 2. Consumer rejects with requeue=False  
# 3. Queue length/size limit exceeded
# 4. Max delivery attempts reached
```

### **3. Lazy Queues**

```python
def lazy_queue_example():
    """Lazy queues for memory-efficient storage"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # Create lazy queue - keeps messages on disk
        channel.queue_declare(
            queue='large_batch_queue',
            durable=True,
            arguments={
                'x-queue-mode': 'lazy'  # Store messages on disk by default
            }
        )
        
        # Lazy queues are ideal for:
        # - Large message backlogs
        # - Infrequent message consumption  
        # - Memory-constrained environments
        # - Long-term message storage
        
        print("💾 Created lazy queue - messages stored on disk")

# Lazy queue benefits:
# ✅ Lower memory usage
# ✅ Can handle millions of messages
# ✅ Consistent performance
# ❌ Slightly higher latency
```

### **4. Quorum Queues (HA Queues)**

```python
def quorum_queue_example():
    """Quorum queues for high availability"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # Create quorum queue (requires RabbitMQ 3.8+)
        try:
            channel.queue_declare(
                queue='ha_orders',
                durable=True,
                arguments={
                    'x-queue-type': 'quorum',  # Replicated across cluster
                    'x-quorum-initial-group-size': 3  # Minimum 3 nodes
                }
            )
            print("🏛️ Created quorum queue for high availability")
        except Exception as e:
            print(f"⚠️ Quorum queues require cluster setup: {e}")

# Quorum queue features:
# ✅ Built-in replication
# ✅ Automatic leader election
# ✅ Data safety guarantees
# ✅ Poison message handling
# ❌ Higher resource usage
```

---

## 📧 **Message Properties & Persistence**

### **Message Properties Overview**

```python
import time
import uuid
from datetime import datetime

def message_properties_example():
    """Comprehensive message properties usage"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # Declare queue
        channel.queue_declare(queue='property_demo', durable=True)
        
        # Create message with all properties
        message_body = {
            'order_id': 'ORD-12345',
            'customer_id': 'CUST-67890',
            'items': [{'sku': 'ITEM-001', 'quantity': 2}],
            'total': 99.99
        }
        
        properties = pika.BasicProperties(
            # Message persistence
            delivery_mode=2,  # 1=non-persistent, 2=persistent
            
            # Message identification
            message_id=str(uuid.uuid4()),
            correlation_id='order-processing-123',
            
            # Content properties
            content_type='application/json',
            content_encoding='utf-8',
            
            # Timestamps
            timestamp=int(time.time()),
            
            # Expiration (TTL for this specific message)
            expiration='60000',  # 60 seconds (string format required)
            
            # Priority (requires priority queue)
            priority=5,  # 0-255, higher = more priority
            
            # Reply information (for RPC patterns)
            reply_to='response_queue',
            
            # Application headers (custom metadata)
            headers={
                'source_service': 'order-api',
                'version': '1.0',
                'region': 'us-east-1',
                'customer_tier': 'premium',
                'retry_count': 0
            },
            
            # Application ID
            app_id='ecommerce-platform',
            
            # User ID (for access control)
            user_id='system'
        )
        
        # Publish message
        channel.basic_publish(
            exchange='',
            routing_key='property_demo',
            body=json.dumps(message_body),
            properties=properties
        )
        
        print("📋 Published message with comprehensive properties")
        
        # Demonstrate property access in consumer
        def callback(ch, method, props, body):
            print(f"📨 Received message:")
            print(f"   Message ID: {props.message_id}")
            print(f"   Correlation ID: {props.correlation_id}")
            print(f"   Timestamp: {datetime.fromtimestamp(props.timestamp)}")
            print(f"   Priority: {props.priority}")
            print(f"   Headers: {props.headers}")
            print(f"   Content: {json.loads(body)}")
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
        
        # Consume message
        channel.basic_consume(queue='property_demo', on_message_callback=callback)
        print("👂 Started consuming messages...")
        
        # Process one message then stop
        try:
            connection.process_data_events(time_limit=1)
        except:
            pass
```

### **Message Persistence Strategies**

```python
def persistence_strategies():
    """Different approaches to message persistence"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # Strategy 1: Full persistence (queue + messages)
        channel.queue_declare(queue='persistent_orders', durable=True)
        
        persistent_message = {'order_id': '001', 'amount': 100.0}
        channel.basic_publish(
            exchange='',
            routing_key='persistent_orders',
            body=json.dumps(persistent_message),
            properties=pika.BasicProperties(delivery_mode=2)  # Persistent
        )
        
        # Strategy 2: Transient queue with persistent messages
        channel.queue_declare(queue='temp_persistent', durable=False)
        channel.basic_publish(
            exchange='',
            routing_key='temp_persistent',
            body=json.dumps({'temp': 'data'}),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        
        # Strategy 3: Persistent queue with transient messages (for speed)
        channel.queue_declare(queue='fast_processing', durable=True)
        channel.basic_publish(
            exchange='',
            routing_key='fast_processing',
            body=json.dumps({'fast': 'data'}),
            properties=pika.BasicProperties(delivery_mode=1)  # Non-persistent
        )
        
        print("💾 Demonstrated different persistence strategies")

# Persistence decision matrix:
# High-value data + Reliability required = Persistent queue + Persistent messages
# Temporary data processing = Any queue + Non-persistent messages  
# Fast processing needed = Persistent queue + Non-persistent messages
# Development/testing = Non-persistent everything
```

---

## 👥 **Consumer Patterns & Acknowledgments**

### **1. Basic Consumer Patterns**

```python
def basic_consumer_patterns():
    """Different consumer implementation patterns"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # Setup test queue
        channel.queue_declare(queue='consumer_demo', durable=True)
        
        # Pattern 1: Auto-acknowledgment (fastest, least reliable)
        def auto_ack_callback(ch, method, properties, body):
            print(f"🚀 Auto-ack: {json.loads(body)}")
            # Message is automatically acknowledged
        
        channel.basic_consume(
            queue='consumer_demo',
            on_message_callback=auto_ack_callback,
            auto_ack=True  # Automatic acknowledgment
        )
        
        # Pattern 2: Manual acknowledgment (reliable)
        def manual_ack_callback(ch, method, properties, body):
            try:
                message = json.loads(body)
                print(f"✅ Processing: {message}")
                
                # Simulate processing
                time.sleep(0.1)
                
                # Acknowledge after successful processing
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
            except Exception as e:
                print(f"❌ Processing failed: {e}")
                
                # Reject and requeue for retry
                ch.basic_nack(
                    delivery_tag=method.delivery_tag,
                    requeue=True  # Put back in queue
                )
        
        channel.basic_consume(
            queue='consumer_demo',
            on_message_callback=manual_ack_callback,
            auto_ack=False  # Manual acknowledgment
        )
        
        # Pattern 3: Batch acknowledgment
        def batch_ack_callback(ch, method, properties, body):
            # Process multiple messages then ack all at once
            ch.basic_ack(delivery_tag=method.delivery_tag, multiple=True)
        
        print("👥 Setup different consumer patterns")
```

### **2. Quality of Service (QoS)**

```python
def qos_examples():
    """Consumer QoS settings for load balancing"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # QoS Setting 1: Prefetch count (most common)
        channel.basic_qos(prefetch_count=10)  # Max 10 unacked messages
        
        # This means:
        # - Consumer receives max 10 messages at once
        # - Must ack messages to receive more
        # - Enables load balancing across consumers
        
        # QoS Setting 2: Prefetch size (less common)
        channel.basic_qos(prefetch_size=1024)  # Max 1KB unacked messages
        
        # QoS Setting 3: Global QoS (affects all consumers on channel)
        channel.basic_qos(prefetch_count=50, global_qos=True)
        
        # Example: Worker with controlled load
        def controlled_worker(ch, method, properties, body):
            message = json.loads(body)
            processing_time = message.get('processing_time', 1)
            
            print(f"🔧 Processing for {processing_time} seconds...")
            time.sleep(processing_time)
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f"✅ Completed processing")
        
        channel.basic_consume(
            queue='work_queue',
            on_message_callback=controlled_worker,
            auto_ack=False
        )
        
        print("⚖️ Setup QoS for load balancing")

# QoS benefits:
# ✅ Fair work distribution among consumers
# ✅ Prevents memory exhaustion
# ✅ Better resource utilization
# ✅ Graceful handling of slow consumers
```

### **3. Advanced Consumer Patterns**

```python
import threading
from concurrent.futures import ThreadPoolExecutor

class AdvancedRabbitMQConsumer:
    """Advanced consumer with threading and retry logic"""
    
    def __init__(self, connection_params, max_workers=10):
        self.connection_params = connection_params
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running = False
    
    def start_consuming(self, queue_name, message_handler):
        """Start consuming with parallel processing"""
        
        connection = pika.BlockingConnection(self.connection_params)
        channel = connection.channel()
        
        # Set QoS for parallel processing
        channel.basic_qos(prefetch_count=self.max_workers * 2)
        
        self.running = True
        
        def callback(ch, method, properties, body):
            # Submit to thread pool for parallel processing
            future = self.executor.submit(
                self._process_message_safely,
                ch, method, properties, body, message_handler
            )
            
            # Store future for tracking (optional)
            # futures.append(future)
        
        channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=False
        )
        
        print(f"🚀 Started consuming {queue_name} with {self.max_workers} workers")
        
        try:
            while self.running:
                connection.process_data_events(time_limit=1)
        except KeyboardInterrupt:
            print("🛑 Stopping consumer...")
            self.stop()
        finally:
            connection.close()
    
    def _process_message_safely(self, ch, method, properties, body, handler):
        """Safely process message with retry logic"""
        
        max_retries = 3
        retry_count = 0
        
        # Get retry count from headers
        if properties.headers:
            retry_count = properties.headers.get('retry_count', 0)
        
        try:
            # Process message
            handler(json.loads(body), properties)
            
            # Acknowledge successful processing
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            print(f"❌ Processing failed (attempt {retry_count + 1}): {e}")
            
            if retry_count < max_retries:
                # Retry with exponential backoff
                self._retry_message(ch, method, properties, body, retry_count + 1)
            else:
                # Send to dead letter queue or reject
                print(f"💀 Max retries exceeded for message")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    def _retry_message(self, ch, method, properties, body, retry_count):
        """Retry message with delay"""
        
        # Calculate delay (exponential backoff)
        delay = min(2 ** retry_count, 60)  # Max 60 seconds
        
        # Update retry count in headers
        headers = properties.headers or {}
        headers['retry_count'] = retry_count
        headers['retry_delay'] = delay
        
        # Create new properties with updated headers
        new_properties = pika.BasicProperties(
            headers=headers,
            delivery_mode=properties.delivery_mode,
            correlation_id=properties.correlation_id,
            message_id=properties.message_id
        )
        
        # Publish to retry queue with TTL
        retry_exchange = 'retry_exchange'
        
        try:
            ch.basic_publish(
                exchange=retry_exchange,
                routing_key=method.routing_key,
                body=body,
                properties=new_properties
            )
            
            # Acknowledge original message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
            print(f"🔄 Scheduled retry #{retry_count} with {delay}s delay")
            
        except Exception as e:
            print(f"❌ Failed to schedule retry: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    def stop(self):
        """Stop consuming"""
        self.running = False
        self.executor.shutdown(wait=True)

# Usage example
def example_message_handler(message_data, properties):
    """Example message handler that might fail"""
    
    if 'error' in message_data:
        raise Exception(f"Simulated error: {message_data['error']}")
    
    print(f"✅ Successfully processed: {message_data}")
    time.sleep(0.1)  # Simulate processing time

# Start advanced consumer
# consumer = AdvancedRabbitMQConsumer(connection_params)
# consumer.start_consuming('work_queue', example_message_handler)
```

### **4. Advanced Acknowledgment Strategies**

```python
def advanced_acknowledgment_patterns():
    """Advanced acknowledgment patterns for different scenarios"""
    
    class AckStrategy:
        """Base acknowledgment strategy"""
        
        def should_ack(self, processing_result, attempt_count, message_age):
            raise NotImplementedError
    
    class ImmediateAckStrategy(AckStrategy):
        """Acknowledge immediately after successful processing"""
        
        def should_ack(self, processing_result, attempt_count, message_age):
            return processing_result == 'success'
    
    class DelayedAckStrategy(AckStrategy):
        """Acknowledge after validation or downstream confirmation"""
        
        def __init__(self, validation_timeout=30):
            self.validation_timeout = validation_timeout
            self.pending_validations = {}
        
        def should_ack(self, processing_result, attempt_count, message_age):
            if processing_result == 'success':
                # Don't ack immediately - wait for validation
                return False
            return processing_result == 'validated'
    
    class BatchAckStrategy(AckStrategy):
        """Acknowledge in batches for high throughput"""
        
        def __init__(self, batch_size=10, timeout_seconds=5):
            self.batch_size = batch_size
            self.timeout_seconds = timeout_seconds
            self.pending_acks = []
            self.last_ack_time = time.time()
        
        def should_ack_batch(self):
            return (len(self.pending_acks) >= self.batch_size or
                    time.time() - self.last_ack_time > self.timeout_seconds)
    
    class AdaptiveAckStrategy(AckStrategy):
        """Adapt acknowledgment based on system load and error rate"""
        
        def __init__(self):
            self.error_rate = 0.0
            self.system_load = 0.0
            self.recent_results = []
        
        def update_metrics(self, processing_result):
            self.recent_results.append(processing_result)
            if len(self.recent_results) > 100:
                self.recent_results.pop(0)
            
            errors = sum(1 for r in self.recent_results if r == 'error')
            self.error_rate = errors / len(self.recent_results)
        
        def should_ack(self, processing_result, attempt_count, message_age):
            self.update_metrics(processing_result)
            
            # High error rate: be more conservative
            if self.error_rate > 0.1:
                return processing_result == 'success' and attempt_count == 1
            
            # Normal operation: standard ack
            return processing_result in ['success', 'skip']

class SmartConsumer:
    """Consumer with pluggable acknowledgment strategies"""
    
    def __init__(self, connection, ack_strategy):
        self.connection = connection
        self.channel = connection.channel()
        self.ack_strategy = ack_strategy
        self.message_tracker = {}
    
    def consume_with_strategy(self, queue_name, message_processor):
        """Consume messages using configured ack strategy"""
        
        def callback(ch, method, properties, body):
            message_id = properties.message_id or str(uuid.uuid4())
            
            try:
                # Track message processing
                start_time = time.time()
                result = message_processor(json.loads(body), properties)
                processing_time = time.time() - start_time
                
                # Get retry count from headers
                retry_count = 0
                if properties.headers and 'retry_count' in properties.headers:
                    retry_count = properties.headers['retry_count']
                
                # Determine if should acknowledge
                if self.ack_strategy.should_ack(result, retry_count, processing_time):
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    print(f"✅ Acknowledged message {message_id}")
                else:
                    # Handle based on result
                    if result == 'retry':
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                        print(f"🔄 Requeued message {message_id}")
                    elif result == 'skip':
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        print(f"⏭️ Skipped message {message_id}")
                    else:
                        # Default: don't ack, let message timeout
                        print(f"⏸️ Deferred ack for message {message_id}")
                
            except Exception as e:
                print(f"❌ Processing error for {message_id}: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        
        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=False
        )
        
        self.channel.start_consuming()

def conditional_acknowledgment_example():
    """Example of conditional acknowledgment based on business logic"""
    
    class OrderProcessor:
        def __init__(self):
            self.inventory_service = InventoryServiceClient()
            self.payment_service = PaymentServiceClient()
        
        def process_order(self, order_data, properties):
            """Process order with conditional acknowledgment"""
            
            order_id = order_data.get('order_id')
            
            # Step 1: Validate order format
            if not self.validate_order_format(order_data):
                return 'invalid_format'  # Don't requeue - bad data
            
            # Step 2: Check inventory
            inventory_result = self.inventory_service.check_availability(order_data['items'])
            if inventory_result == 'out_of_stock':
                return 'retry'  # Requeue - inventory might become available
            elif inventory_result == 'discontinued':
                return 'skip'   # Don't requeue - item no longer available
            
            # Step 3: Process payment
            try:
                payment_result = self.payment_service.charge(order_data['payment'])
                if payment_result == 'success':
                    return 'success'  # Acknowledge - order processed
                elif payment_result == 'insufficient_funds':
                    return 'skip'     # Don't requeue - customer issue
                else:
                    return 'retry'    # Requeue - payment service might be down
            except Exception:
                return 'retry'        # Requeue - temporary error
        
        def validate_order_format(self, order_data):
            required_fields = ['order_id', 'customer_id', 'items', 'payment']
            return all(field in order_data for field in required_fields)

def transactional_acknowledgment_example():
    """Acknowledgment tied to database transactions"""
    
    class TransactionalConsumer:
        def __init__(self, rabbitmq_channel, database_connection):
            self.channel = rabbitmq_channel
            self.db = database_connection
        
        def process_with_transaction(self, ch, method, properties, body):
            """Process message within database transaction"""
            
            transaction = self.db.begin_transaction()
            
            try:
                # Parse message
                message_data = json.loads(body)
                
                # Process business logic within transaction
                self.update_customer_balance(message_data, transaction)
                self.log_transaction(message_data, transaction)
                self.update_analytics(message_data, transaction)
                
                # Commit database transaction
                transaction.commit()
                
                # Only acknowledge after successful DB commit
                ch.basic_ack(delivery_tag=method.delivery_tag)
                print(f"✅ Message processed and acknowledged")
                
            except DatabaseError as e:
                # Database error - rollback and requeue
                transaction.rollback()
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                print(f"🔄 Database error, message requeued: {e}")
                
            except ValidationError as e:
                # Business logic error - rollback but don't requeue
                transaction.rollback()
                ch.basic_ack(delivery_tag=method.delivery_tag)
                self.send_to_dead_letter(message_data, str(e))
                print(f"💀 Validation error, message sent to DLQ: {e}")
                
            except Exception as e:
                # Unexpected error - rollback and requeue
                transaction.rollback()
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                print(f"❌ Unexpected error, message requeued: {e}")

def heartbeat_acknowledgment_example():
    """Acknowledgment with heartbeat for long-running processes"""
    
    class HeartbeatConsumer:
        def __init__(self, channel):
            self.channel = channel
            self.active_messages = {}
        
        def process_long_running_task(self, ch, method, properties, body):
            """Handle long-running tasks with periodic heartbeats"""
            
            message_id = properties.message_id or str(uuid.uuid4())
            delivery_tag = method.delivery_tag
            
            # Track active message
            self.active_messages[message_id] = {
                'delivery_tag': delivery_tag,
                'start_time': time.time(),
                'last_heartbeat': time.time()
            }
            
            try:
                # Start heartbeat thread
                heartbeat_thread = threading.Thread(
                    target=self.send_periodic_heartbeat,
                    args=(message_id,),
                    daemon=True
                )
                heartbeat_thread.start()
                
                # Simulate long-running processing
                self.perform_long_task(json.loads(body))
                
                # Task completed - acknowledge
                ch.basic_ack(delivery_tag=delivery_tag)
                print(f"✅ Long-running task completed: {message_id}")
                
            except Exception as e:
                print(f"❌ Long-running task failed: {e}")
                ch.basic_nack(delivery_tag=delivery_tag, requeue=True)
                
            finally:
                # Clean up tracking
                self.active_messages.pop(message_id, None)
        
        def send_periodic_heartbeat(self, message_id):
            """Send heartbeat to prevent message timeout"""
            
            while message_id in self.active_messages:
                try:
                    # Update last heartbeat time
                    self.active_messages[message_id]['last_heartbeat'] = time.time()
                    
                    # Connection heartbeat is handled automatically by Pika
                    # This is for application-level heartbeat logging
                    print(f"💓 Heartbeat for message {message_id}")
                    
                    time.sleep(10)  # Send heartbeat every 10 seconds
                    
                except Exception as e:
                    print(f"❌ Heartbeat failed for {message_id}: {e}")
                    break
        
        def perform_long_task(self, message_data):
            """Simulate long-running task"""
            # Simulate processing that takes several minutes
            total_steps = 30
            for step in range(total_steps):
                time.sleep(2)  # 2 seconds per step = 60 seconds total
                print(f"📊 Processing step {step + 1}/{total_steps}")

# Example usage of advanced acknowledgment patterns
def acknowledgment_patterns_demo():
    """Demonstrate different acknowledgment patterns"""
    
    # Example 1: Immediate acknowledgment for fast processing
    immediate_strategy = ImmediateAckStrategy()
    
    # Example 2: Delayed acknowledgment for validation workflows
    delayed_strategy = DelayedAckStrategy(validation_timeout=60)
    
    # Example 3: Batch acknowledgment for high throughput
    batch_strategy = BatchAckStrategy(batch_size=20, timeout_seconds=10)
    
    # Example 4: Adaptive acknowledgment based on system conditions
    adaptive_strategy = AdaptiveAckStrategy()
    
    print("🎯 Advanced acknowledgment strategies configured")
    return immediate_strategy, delayed_strategy, batch_strategy, adaptive_strategy

# Acknowledgment best practices summary
acknowledgment_best_practices = """
## 🎯 Acknowledgment Best Practices

### ✅ When to Use Each Pattern

**Auto-Acknowledgment:**
- Fast, non-critical messages
- High throughput scenarios
- When message loss is acceptable

**Manual Acknowledgment:**
- Critical business operations
- When processing might fail
- Need for guaranteed processing

**Batch Acknowledgment:**
- High-volume message processing
- When individual acks create overhead
- Balanced reliability vs performance

**Conditional Acknowledgment:**
- Complex business logic
- Multiple processing outcomes
- When retry logic varies by error type

**Transactional Acknowledgment:**
- Database consistency required
- Financial transactions
- When message processing must be atomic

### ⚠️ Common Pitfalls

- Don't ack before processing completes
- Avoid acking on retryable errors
- Don't use auto-ack for critical messages
- Implement proper error handling
- Consider message timeout vs processing time
- Monitor unacknowledged message counts
"""

print(acknowledgment_best_practices)
```

---

## 🚀 **Advanced Features**

### **1. Publisher Confirms**

```python
def publisher_confirms_example():
    """Publisher confirms for reliable message delivery"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # Enable publisher confirms
        channel.confirm_delivery()
        
        # Method 1: Synchronous confirm (blocking)
        try:
            channel.basic_publish(
                exchange='',
                routing_key='test_queue',
                body='Test message',
                properties=pika.BasicProperties(delivery_mode=2)
            )
            print("✅ Message confirmed by broker")
        except pika.exceptions.UnroutableError:
            print("❌ Message was returned (no route)")
        
        # Method 2: Batch confirms
        messages = [f"Message {i}" for i in range(10)]
        
        for message in messages:
            channel.basic_publish(
                exchange='',
                routing_key='batch_queue',
                body=message,
                properties=pika.BasicProperties(delivery_mode=2)
            )
        
        # Confirm all pending messages
        if channel.wait_for_confirms():
            print("✅ All batch messages confirmed")
        else:
            print("❌ Some batch messages failed")

# Publisher confirms guarantee:
# ✅ Message reached the broker
# ✅ Message was routed to at least one queue
# ✅ Message was persisted (if durable)
```

### **2. Transactions**

```python
def transaction_example():
    """AMQP transactions for atomic operations"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        try:
            # Start transaction
            channel.tx_select()
            
            # Publish multiple messages atomically
            messages = [
                {'account': 'A', 'amount': -100, 'type': 'debit'},
                {'account': 'B', 'amount': +100, 'type': 'credit'}
            ]
            
            for message in messages:
                channel.basic_publish(
                    exchange='financial_transactions',
                    routing_key='bank_transfer',
                    body=json.dumps(message),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
            
            # Commit transaction (all messages sent together)
            channel.tx_commit()
            print("💳 Transaction committed successfully")
            
        except Exception as e:
            # Rollback transaction (discard all messages)
            channel.tx_rollback()
            print(f"❌ Transaction rolled back: {e}")

# Note: Transactions have significant performance impact
# Use publisher confirms for better performance in most cases
```

### **3. Consumer Cancellation**

```python
def consumer_cancellation_example():
    """Handle consumer cancellation gracefully"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # Setup cancellation callback
        def on_consumer_cancelled(method_frame):
            print(f"😵 Consumer was cancelled by broker: {method_frame}")
            # Implement reconnection logic here
        
        channel.add_on_cancel_callback(on_consumer_cancelled)
        
        # Setup consumer with cancellation handling
        def resilient_callback(ch, method, properties, body):
            try:
                # Process message
                print(f"📨 Processing: {json.loads(body)}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                print(f"❌ Error: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        
        consumer_tag = channel.basic_consume(
            queue='resilient_queue',
            on_message_callback=resilient_callback,
            auto_ack=False
        )
        
        print(f"👂 Started consumer with tag: {consumer_tag}")

# Consumer cancellation scenarios:
# - Queue deletion
# - Node failure in cluster
# - Resource constraints
# - Administrative actions
```

### **4. Flow Control**

```python
def flow_control_example():
    """Handle flow control and connection blocking"""
    
    def on_connection_blocked(connection, reason):
        print(f"🚫 Connection blocked: {reason}")
        # Pause publishing, implement backpressure
    
    def on_connection_unblocked(connection, reason):
        print(f"✅ Connection unblocked")
        # Resume publishing
    
    # Setup connection with flow control callbacks
    connection_params = pika.ConnectionParameters(
        host='localhost',
        blocked_connection_timeout=300  # 5 minutes timeout
    )
    
    connection = pika.BlockingConnection(connection_params)
    connection.add_on_connection_blocked_callback(on_connection_blocked)
    connection.add_on_connection_unblocked_callback(on_connection_unblocked)
    
    channel = connection.channel()
    
    # Publishing with flow control awareness
    def publish_with_backpressure(messages):
        for message in messages:
            try:
                channel.basic_publish(
                    exchange='',
                    routing_key='flow_control_queue',
                    body=json.dumps(message),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
            except pika.exceptions.ConnectionClosed:
                print("🔌 Connection closed during publishing")
                break
    
    print("🌊 Setup flow control handling")

# Flow control triggers:
# - Memory threshold exceeded
# - Disk space low  
# - Too many connections
# - Queue length limits
```

---

## 🔄 **Request-Reply (RPC) Patterns**

Request-Reply patterns enable synchronous communication over asynchronous messaging infrastructure, essential for microservices architectures where services need to call each other and wait for responses.

### **1. Basic RPC Implementation**

#### **Simple RPC Client**

```python
import uuid
import json
import asyncio
import time
from typing import Optional, Any, Dict
import pika
from concurrent.futures import Future

class RabbitMQRPCClient:
    """Production-ready RPC client for RabbitMQ"""
    
    def __init__(self, connection_params, timeout=30):
        self.connection_params = connection_params
        self.timeout = timeout
        self.connection = None
        self.channel = None
        self.callback_queue = None
        self.correlation_id = None
        self.response = None
        self.response_future = None
        
    def connect(self):
        """Establish connection and setup callback queue"""
        self.connection = pika.BlockingConnection(self.connection_params)
        self.channel = self.connection.channel()
        
        # Declare temporary exclusive callback queue
        result = self.channel.queue_declare(queue='', exclusive=True, auto_delete=True)
        self.callback_queue = result.method.queue
        
        # Start consuming from callback queue
        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self._on_response,
            auto_ack=True
        )
        
        print(f"🔄 RPC client connected with callback queue: {self.callback_queue}")
    
    def call(self, queue_name: str, message: Any, timeout: Optional[int] = None) -> Any:
        """Make synchronous RPC call"""
        
        if not self.connection:
            self.connect()
        
        # Generate unique correlation ID
        self.correlation_id = str(uuid.uuid4())
        self.response = None
        self.response_future = Future()
        
        # Publish request message
        self.channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.correlation_id,
                delivery_mode=2,  # Persistent
                timestamp=int(time.time())
            ),
            body=json.dumps(message, default=str)
        )
        
        print(f"📤 RPC request sent to {queue_name} with correlation_id: {self.correlation_id}")
        
        # Wait for response with timeout
        call_timeout = timeout or self.timeout
        start_time = time.time()
        
        while self.response is None:
            self.connection.process_data_events(time_limit=0.1)
            
            if time.time() - start_time > call_timeout:
                raise TimeoutError(f"RPC call timed out after {call_timeout} seconds")
        
        return self.response
    
    async def call_async(self, queue_name: str, message: Any, timeout: Optional[int] = None) -> Any:
        """Make asynchronous RPC call"""
        
        if not self.connection:
            self.connect()
        
        # Generate unique correlation ID
        self.correlation_id = str(uuid.uuid4())
        self.response = None
        self.response_future = Future()
        
        # Publish request message
        self.channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.correlation_id,
                delivery_mode=2
            ),
            body=json.dumps(message, default=str)
        )
        
        # Wait for response asynchronously
        call_timeout = timeout or self.timeout
        try:
            # Convert Future to asyncio coroutine
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, self.response_future.result),
                timeout=call_timeout
            )
            return response
        except asyncio.TimeoutError:
            raise TimeoutError(f"Async RPC call timed out after {call_timeout} seconds")
    
    def _on_response(self, ch, method, props, body):
        """Handle RPC response"""
        
        if self.correlation_id == props.correlation_id:
            try:
                self.response = json.loads(body)
                if self.response_future:
                    self.response_future.set_result(self.response)
                print(f"📥 RPC response received for {self.correlation_id}")
            except json.JSONDecodeError:
                error_msg = f"Invalid JSON response: {body}"
                print(f"❌ {error_msg}")
                if self.response_future:
                    self.response_future.set_exception(ValueError(error_msg))
                self.response = {"error": error_msg}
    
    def close(self):
        """Close connection"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            print("🔌 RPC client connection closed")

#### **RPC Server Implementation**

class RabbitMQRPCServer:
    """Production-ready RPC server for RabbitMQ"""
    
    def __init__(self, connection_params, queue_name):
        self.connection_params = connection_params
        self.queue_name = queue_name
        self.connection = None
        self.channel = None
        self.handlers = {}
        self.running = False
        
    def register_handler(self, method_name: str, handler_func):
        """Register RPC method handler"""
        self.handlers[method_name] = handler_func
        print(f"📋 Registered RPC handler: {method_name}")
    
    def start_server(self):
        """Start RPC server"""
        
        # Setup connection
        self.connection = pika.BlockingConnection(self.connection_params)
        self.channel = self.connection.channel()
        
        # Declare RPC queue
        self.channel.queue_declare(queue=self.queue_name, durable=True)
        
        # Set QoS to handle one request at a time
        self.channel.basic_qos(prefetch_count=1)
        
        # Start consuming
        self.channel.basic_consume(
            queue=self.queue_name,
            on_message_callback=self._on_request,
            auto_ack=False
        )
        
        self.running = True
        print(f"🚀 RPC server started on queue: {self.queue_name}")
        
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            print("🛑 Stopping RPC server...")
            self.stop_server()
    
    def _on_request(self, ch, method, props, body):
        """Handle RPC request"""
        
        correlation_id = props.correlation_id
        reply_to = props.reply_to
        
        if not reply_to or not correlation_id:
            print("❌ Invalid RPC request: missing reply_to or correlation_id")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
        
        try:
            # Parse request
            request = json.loads(body)
            method_name = request.get('method')
            params = request.get('params', {})
            
            print(f"📨 RPC request: {method_name} with correlation_id: {correlation_id}")
            
            # Execute handler
            if method_name in self.handlers:
                result = self.handlers[method_name](params)
                response = {"result": result, "error": None}
            else:
                response = {
                    "result": None,
                    "error": f"Method '{method_name}' not found"
                }
            
            # Send response
            ch.basic_publish(
                exchange='',
                routing_key=reply_to,
                properties=pika.BasicProperties(
                    correlation_id=correlation_id,
                    delivery_mode=2
                ),
                body=json.dumps(response, default=str)
            )
            
            print(f"📤 RPC response sent for {correlation_id}")
            
        except Exception as e:
            # Send error response
            error_response = {
                "result": None,
                "error": f"Server error: {str(e)}"
            }
            
            ch.basic_publish(
                exchange='',
                routing_key=reply_to,
                properties=pika.BasicProperties(correlation_id=correlation_id),
                body=json.dumps(error_response)
            )
            
            print(f"❌ RPC error for {correlation_id}: {e}")
        
        finally:
            ch.basic_ack(delivery_tag=method.delivery_tag)
    
    def stop_server(self):
        """Stop RPC server"""
        self.running = False
        if self.channel:
            self.channel.stop_consuming()
        if self.connection and not self.connection.is_closed:
            self.connection.close()
        print("🔌 RPC server stopped")

# Example usage
def rpc_example():
    """Example of RPC client and server usage"""
    
    connection_params = pika.ConnectionParameters('localhost')
    
    # Server-side handlers
    def calculate_fibonacci(params):
        n = params.get('n', 0)
        if n <= 1:
            return n
        
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b
    
    def process_order(params):
        order_id = params.get('order_id')
        items = params.get('items', [])
        
        # Simulate order processing
        total = sum(item.get('price', 0) * item.get('quantity', 0) for item in items)
        
        return {
            'order_id': order_id,
            'status': 'processed',
            'total': total,
            'processing_time': time.time()
        }
    
    # Setup server (would run in separate process)
    server = RabbitMQRPCServer(connection_params, 'rpc_queue')
    server.register_handler('fibonacci', calculate_fibonacci)
    server.register_handler('process_order', process_order)
    
    # Setup client
    client = RabbitMQRPCClient(connection_params)
    
    # Example calls
    try:
        # Call Fibonacci
        fib_request = {"method": "fibonacci", "params": {"n": 10}}
        fib_result = client.call('rpc_queue', fib_request)
        print(f"Fibonacci result: {fib_result}")
        
        # Call order processing
        order_request = {
            "method": "process_order",
            "params": {
                "order_id": "ORD-123",
                "items": [
                    {"name": "Widget", "price": 19.99, "quantity": 2},
                    {"name": "Gadget", "price": 29.99, "quantity": 1}
                ]
            }
        }
        order_result = client.call('rpc_queue', order_request)
        print(f"Order result: {order_result}")
        
    finally:
        client.close()

# Async RPC example
async def async_rpc_example():
    """Example of async RPC calls"""
    
    connection_params = pika.ConnectionParameters('localhost')
    client = RabbitMQRPCClient(connection_params)
    
    try:
        # Multiple async calls
        tasks = []
        for i in range(5):
            request = {"method": "fibonacci", "params": {"n": i * 5}}
            task = client.call_async('rpc_queue', request)
            tasks.append(task)
        
        # Wait for all responses
        results = await asyncio.gather(*tasks)
        
        for i, result in enumerate(results):
            print(f"Async result {i}: {result}")
    
    finally:
        client.close()
```

### **2. Advanced RPC Patterns**

#### **Connection Pool for RPC Clients**

```python
import threading
from queue import Queue, Empty
from contextlib import contextmanager

class RabbitMQRPCConnectionPool:
    """Connection pool for RPC clients"""
    
    def __init__(self, connection_params, pool_size=10, timeout=30):
        self.connection_params = connection_params
        self.pool_size = pool_size
        self.timeout = timeout
        self.pool = Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        
        # Initialize pool
        for _ in range(pool_size):
            client = RabbitMQRPCClient(connection_params, timeout)
            client.connect()
            self.pool.put(client)
    
    @contextmanager
    def get_client(self, timeout=5):
        """Get RPC client from pool"""
        
        client = None
        try:
            client = self.pool.get(timeout=timeout)
            yield client
        except Empty:
            raise RuntimeError("No RPC clients available in pool")
        finally:
            if client:
                self.pool.put(client)
    
    def call(self, queue_name: str, message: Any, timeout: Optional[int] = None) -> Any:
        """Make RPC call using pooled connection"""
        
        with self.get_client() as client:
            return client.call(queue_name, message, timeout)
    
    async def call_async(self, queue_name: str, message: Any, timeout: Optional[int] = None) -> Any:
        """Make async RPC call using pooled connection"""
        
        with self.get_client() as client:
            return await client.call_async(queue_name, message, timeout)
    
    def close_all(self):
        """Close all connections in pool"""
        
        while not self.pool.empty():
            try:
                client = self.pool.get_nowait()
                client.close()
            except Empty:
                break

#### **RPC Circuit Breaker Pattern**

class RPCCircuitBreaker:
    """Circuit breaker for RPC calls"""
    
    def __init__(self, failure_threshold=5, recovery_timeout=60, expected_exception=Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        
        if self.state == 'OPEN':
            if self._should_attempt_reset():
                self.state = 'HALF_OPEN'
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self):
        return (
            self.last_failure_time and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self):
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'

class ResilientRPCClient:
    """RPC client with circuit breaker and retry logic"""
    
    def __init__(self, connection_pool, max_retries=3):
        self.connection_pool = connection_pool
        self.max_retries = max_retries
        self.circuit_breaker = RPCCircuitBreaker()
    
    def call_with_resilience(self, queue_name: str, message: Any, timeout: Optional[int] = None) -> Any:
        """Make resilient RPC call with circuit breaker and retries"""
        
        def make_call():
            return self.connection_pool.call(queue_name, message, timeout)
        
        # Attempt call with circuit breaker
        for attempt in range(self.max_retries + 1):
            try:
                return self.circuit_breaker.call(make_call)
            except Exception as e:
                if attempt == self.max_retries:
                    raise
                
                # Exponential backoff
                wait_time = 2 ** attempt
                print(f"🔄 RPC attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
```

### **3. RPC Load Balancing and Service Discovery**

```python
import random
from typing import List

class RPCServiceRegistry:
    """Service registry for RPC endpoints"""
    
    def __init__(self):
        self.services = {}  # service_name -> List[queue_name]
    
    def register_service(self, service_name: str, queue_name: str):
        """Register RPC service endpoint"""
        if service_name not in self.services:
            self.services[service_name] = []
        
        if queue_name not in self.services[service_name]:
            self.services[service_name].append(queue_name)
            print(f"📋 Registered service {service_name} -> {queue_name}")
    
    def unregister_service(self, service_name: str, queue_name: str):
        """Unregister RPC service endpoint"""
        if service_name in self.services:
            if queue_name in self.services[service_name]:
                self.services[service_name].remove(queue_name)
                print(f"📋 Unregistered service {service_name} -> {queue_name}")
    
    def get_service_endpoints(self, service_name: str) -> List[str]:
        """Get all endpoints for a service"""
        return self.services.get(service_name, [])
    
    def get_endpoint(self, service_name: str, strategy='round_robin') -> str:
        """Get endpoint using load balancing strategy"""
        endpoints = self.get_service_endpoints(service_name)
        
        if not endpoints:
            raise ValueError(f"No endpoints available for service: {service_name}")
        
        if strategy == 'round_robin':
            # Simple round-robin (in production, use proper implementation)
            return endpoints[hash(time.time()) % len(endpoints)]
        elif strategy == 'random':
            return random.choice(endpoints)
        else:
            return endpoints[0]

class LoadBalancedRPCClient:
    """RPC client with load balancing and service discovery"""
    
    def __init__(self, connection_pool, service_registry):
        self.connection_pool = connection_pool
        self.service_registry = service_registry
        self.health_checker = RPCHealthChecker(connection_pool)
    
    def call_service(
        self, 
        service_name: str, 
        message: Any, 
        strategy: str = 'round_robin',
        timeout: Optional[int] = None
    ) -> Any:
        """Call service with load balancing"""
        
        # Get healthy endpoints
        healthy_endpoints = self.health_checker.get_healthy_endpoints(service_name)
        
        if not healthy_endpoints:
            raise RuntimeError(f"No healthy endpoints for service: {service_name}")
        
        # Select endpoint using strategy
        if strategy == 'round_robin':
            endpoint = healthy_endpoints[hash(time.time()) % len(healthy_endpoints)]
        elif strategy == 'random':
            endpoint = random.choice(healthy_endpoints)
        elif strategy == 'least_loaded':
            endpoint = self.health_checker.get_least_loaded_endpoint(healthy_endpoints)
        else:
            endpoint = healthy_endpoints[0]
        
        # Make call
        return self.connection_pool.call(endpoint, message, timeout)

class RPCHealthChecker:
    """Health checker for RPC endpoints"""
    
    def __init__(self, connection_pool, health_check_interval=30):
        self.connection_pool = connection_pool
        self.health_check_interval = health_check_interval
        self.endpoint_health = {}  # endpoint -> {'healthy': bool, 'last_check': time}
        self.endpoint_load = {}    # endpoint -> request_count
    
    def check_endpoint_health(self, endpoint: str) -> bool:
        """Check if endpoint is healthy"""
        
        try:
            # Send health check message
            health_request = {
                "method": "health_check",
                "params": {"timestamp": time.time()}
            }
            
            response = self.connection_pool.call(endpoint, health_request, timeout=5)
            
            is_healthy = response and response.get('result') == 'healthy'
            
            self.endpoint_health[endpoint] = {
                'healthy': is_healthy,
                'last_check': time.time()
            }
            
            return is_healthy
            
        except Exception as e:
            print(f"❌ Health check failed for {endpoint}: {e}")
            self.endpoint_health[endpoint] = {
                'healthy': False,
                'last_check': time.time()
            }
            return False
    
    def get_healthy_endpoints(self, service_name: str) -> List[str]:
        """Get list of healthy endpoints for service"""
        
        all_endpoints = self.service_registry.get_service_endpoints(service_name)
        healthy_endpoints = []
        
        for endpoint in all_endpoints:
            # Check if health check is recent
            health_info = self.endpoint_health.get(endpoint)
            
            if (not health_info or 
                time.time() - health_info['last_check'] > self.health_check_interval):
                # Perform health check
                self.check_endpoint_health(endpoint)
            
            # Add to healthy list if healthy
            if self.endpoint_health.get(endpoint, {}).get('healthy', False):
                healthy_endpoints.append(endpoint)
        
        return healthy_endpoints
    
    def get_least_loaded_endpoint(self, endpoints: List[str]) -> str:
        """Get endpoint with lowest load"""
        
        if not endpoints:
            raise ValueError("No endpoints provided")
        
        # Return endpoint with minimum load
        return min(endpoints, key=lambda ep: self.endpoint_load.get(ep, 0))
    
    def record_request(self, endpoint: str):
        """Record request for load tracking"""
        self.endpoint_load[endpoint] = self.endpoint_load.get(endpoint, 0) + 1

# Example usage of load-balanced RPC
def load_balanced_rpc_example():
    """Example of load-balanced RPC system"""
    
    # Setup
    connection_params = pika.ConnectionParameters('localhost')
    pool = RabbitMQRPCConnectionPool(connection_params, pool_size=5)
    registry = RPCServiceRegistry()
    client = LoadBalancedRPCClient(pool, registry)
    
    # Register multiple instances of a service
    registry.register_service('calculator', 'calculator_queue_1')
    registry.register_service('calculator', 'calculator_queue_2')
    registry.register_service('calculator', 'calculator_queue_3')
    
    # Make load-balanced calls
    for i in range(10):
        request = {
            "method": "add",
            "params": {"a": i, "b": i * 2}
        }
        
        try:
            result = client.call_service('calculator', request, strategy='round_robin')
            print(f"Calculator result {i}: {result}")
        except Exception as e:
            print(f"❌ Call {i} failed: {e}")
```

### **4. RPC Monitoring and Metrics**

```python
import time
from collections import defaultdict, deque
from threading import Lock

class RPCMetrics:
    """Metrics collection for RPC calls"""
    
    def __init__(self, window_size=1000):
        self.window_size = window_size
        self.lock = Lock()
        
        # Metrics storage
        self.call_counts = defaultdict(int)
        self.response_times = defaultdict(deque)
        self.error_counts = defaultdict(int)
        self.success_counts = defaultdict(int)
        
    def record_call(self, method: str, response_time: float, success: bool):
        """Record RPC call metrics"""
        
        with self.lock:
            self.call_counts[method] += 1
            
            # Store response time (sliding window)
            self.response_times[method].append(response_time)
            if len(self.response_times[method]) > self.window_size:
                self.response_times[method].popleft()
            
            if success:
                self.success_counts[method] += 1
            else:
                self.error_counts[method] += 1
    
    def get_metrics(self, method: str) -> Dict:
        """Get metrics for specific method"""
        
        with self.lock:
            response_times = list(self.response_times[method])
            
            if not response_times:
                return {
                    'method': method,
                    'call_count': self.call_counts[method],
                    'success_rate': 0.0,
                    'avg_response_time': 0.0,
                    'p95_response_time': 0.0,
                    'error_rate': 0.0
                }
            
            # Calculate statistics
            avg_response_time = sum(response_times) / len(response_times)
            sorted_times = sorted(response_times)
            p95_index = int(len(sorted_times) * 0.95)
            p95_response_time = sorted_times[p95_index] if sorted_times else 0
            
            total_calls = self.call_counts[method]
            success_rate = self.success_counts[method] / total_calls if total_calls > 0 else 0
            error_rate = self.error_counts[method] / total_calls if total_calls > 0 else 0
            
            return {
                'method': method,
                'call_count': total_calls,
                'success_rate': success_rate,
                'error_rate': error_rate,
                'avg_response_time': avg_response_time,
                'p95_response_time': p95_response_time
            }
    
    def get_all_metrics(self) -> Dict:
        """Get metrics for all methods"""
        
        all_methods = set(
            list(self.call_counts.keys()) + 
            list(self.response_times.keys())
        )
        
        return {method: self.get_metrics(method) for method in all_methods}

class MonitoredRPCClient:
    """RPC client with built-in monitoring"""
    
    def __init__(self, connection_pool):
        self.connection_pool = connection_pool
        self.metrics = RPCMetrics()
    
    def call(self, queue_name: str, message: Any, timeout: Optional[int] = None) -> Any:
        """Make monitored RPC call"""
        
        method = message.get('method', 'unknown') if isinstance(message, dict) else 'unknown'
        start_time = time.time()
        success = False
        
        try:
            result = self.connection_pool.call(queue_name, message, timeout)
            success = True
            return result
        except Exception as e:
            print(f"❌ RPC call failed for {method}: {e}")
            raise
        finally:
            response_time = time.time() - start_time
            self.metrics.record_call(method, response_time, success)
    
    def get_metrics_summary(self):
        """Get metrics summary"""
        return self.metrics.get_all_metrics()
```

This comprehensive Request-Reply (RPC) section covers synchronous communication patterns, connection pooling, circuit breakers, load balancing, service discovery, and monitoring - all essential for enterprise microservices architectures.

---

## 🏗️ **Enterprise Integration Patterns**

### **1. Cluster Configuration**

```python
def cluster_awareness_example():
    """Code patterns for cluster-aware applications"""
    
    # Multiple broker endpoints for failover
    cluster_endpoints = [
        {'host': 'rabbitmq-01.example.com', 'port': 5672},
        {'host': 'rabbitmq-02.example.com', 'port': 5672}, 
        {'host': 'rabbitmq-03.example.com', 'port': 5672}
    ]
    
    # Create connection parameters for each node
    connection_params = [
        pika.ConnectionParameters(**endpoint) 
        for endpoint in cluster_endpoints
    ]
    
    try:
        # Automatic failover connection
        connection = pika.BlockingConnection(connection_params)
        print("🏛️ Connected to RabbitMQ cluster")
        
        # The driver automatically tries nodes in order
        # and fails over if current node becomes unavailable
        
    except pika.exceptions.AMQPConnectionError:
        print("❌ Failed to connect to any cluster node")

# Cluster benefits:
# ✅ High availability 
# ✅ Load distribution
# ✅ Automatic failover
# ✅ Horizontal scaling
```

### **2. Queue Mirroring (Classic HA)**

```python
def queue_mirroring_setup():
    """Setup mirrored queues for HA (legacy approach)"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # Create mirrored queue using policy
        # Note: This is typically done via management UI or rabbitmqctl
        
        # Policy would be: rabbitmqctl set_policy ha-all "^ha\." '{"ha-mode":"all"}'
        
        # Create queue with HA naming convention
        channel.queue_declare(
            queue='ha.orders',  # Prefix matches policy
            durable=True
        )
        
        # Alternative: Set HA policy via queue arguments (deprecated)
        channel.queue_declare(
            queue='orders_mirrored',
            durable=True,
            arguments={
                'x-ha-policy': 'all',  # Mirror to all nodes
                # 'x-ha-policy': 'exactly',
                # 'x-ha-policy-params': 2,  # Mirror to exactly 2 nodes
            }
        )
        
        print("🪞 Created mirrored queues for HA")

# Mirroring policies:
# - 'all': Mirror to all cluster nodes
# - 'exactly': Mirror to specific number of nodes  
# - 'nodes': Mirror to specific named nodes
```

### **3. Quorum Queues (Modern HA)**

```python
def quorum_queue_setup():
    """Setup quorum queues (modern HA approach)"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # Create quorum queue (RabbitMQ 3.8+)
        try:
            channel.queue_declare(
                queue='orders_quorum',
                durable=True,
                arguments={
                    'x-queue-type': 'quorum',
                    'x-quorum-initial-group-size': 3,  # Minimum replicas
                    'x-dead-letter-exchange': 'orders_dlx'
                }
            )
            print("🏛️ Created quorum queue")
        except Exception as e:
            print(f"⚠️ Quorum queues require 3+ node cluster: {e}")

# Quorum queue advantages over mirrored queues:
# ✅ Better performance
# ✅ Built-in poison message handling  
# ✅ Automatic leader election
# ✅ Data safety guarantees
# ✅ Simpler operation
```

### **4. Federation & Shovel**

```python
def federation_shovel_concepts():
    """Federation and Shovel for distributed messaging"""
    
    # Federation: Link exchanges/queues across clusters
    federation_config = {
        'upstream_name': 'remote_cluster',
        'upstream_uri': 'amqp://remote.example.com',
        'exchange': 'federated_orders',
        'policy_pattern': '^federated\.',
        'max_hops': 1  # Prevent loops
    }
    
    # Shovel: Move messages between queues/clusters
    shovel_config = {
        'source_queue': 'source_queue@source_cluster',
        'destination_queue': 'destination_queue@dest_cluster',
        'source_uri': 'amqp://source.example.com',
        'destination_uri': 'amqp://dest.example.com'
    }
    
    print("🌐 Federation: Links exchanges across clusters")
    print("🚜 Shovel: Moves messages between queues")

# Use cases:
# Federation: Multi-datacenter messaging, loose coupling
# Shovel: Data migration, cross-cluster replication, backup
```

### **5. Split Brain Scenarios & Network Partitions**

Split brain scenarios are one of the most critical challenges in distributed RabbitMQ clusters. Understanding and properly handling these scenarios is essential for maintaining data consistency and system availability.

#### **What is a Split Brain Scenario?**

A split brain scenario occurs when a RabbitMQ cluster becomes divided into separate groups due to network partitions, with each group believing it's the only functioning part of the cluster.

```
# Normal 3-node cluster
[Node A] ←→ [Node B] ←→ [Node C]
    ↖         ↗
      All connected

# Network partition causing split brain
[Node A]     X     [Node B] ←→ [Node C]
                        ↖     ↗
                      Minority believes
                      it's the cluster
     Isolated node
     believes it's
     the cluster
```

#### **Partition Handling Strategies**

RabbitMQ provides several strategies for handling network partitions:

```python
def partition_handling_strategies():
    """Different strategies for handling network partitions"""
    
    strategies = {
        'ignore': {
            'description': 'Continue operating normally, ignore partitions',
            'pros': ['High availability', 'No service interruption'],
            'cons': ['Data inconsistency risk', 'Split brain syndrome'],
            'use_case': 'Never recommended for production',
            'config': 'cluster_partition_handling = ignore'
        },
        
        'pause_minority': {
            'description': 'Pause nodes that are in the minority partition',
            'pros': ['Prevents split brain', 'Maintains data consistency'],
            'cons': ['Reduced availability during partitions'],
            'use_case': 'Most common production setting',
            'config': 'cluster_partition_handling = pause_minority'
        },
        
        'pause_if_all_down': {
            'description': 'Pause if all other nodes in cluster are down',
            'pros': ['Balanced approach', 'Good for small clusters'],
            'cons': ['Complex decision logic'],
            'use_case': '2-node clusters or specific network topologies',
            'config': 'cluster_partition_handling = pause_if_all_down'
        },
        
        'autoheal': {
            'description': 'Automatically restart minority nodes to rejoin',
            'pros': ['Automatic recovery', 'Minimal manual intervention'],
            'cons': ['Potential data loss', 'Service disruption'],
            'use_case': 'Development environments only',
            'config': 'cluster_partition_handling = autoheal'
        }
    }
    
    return strategies

# Configuration examples
def configure_partition_handling():
    """Configure partition handling in rabbitmq.conf"""
    
    configurations = {
        'production_recommended': """
# Production-recommended configuration
cluster_partition_handling = pause_minority

# Additional cluster settings
cluster_formation.peer_discovery_backend = classic_config
cluster_formation.classic_config.nodes.1 = rabbit@node1
cluster_formation.classic_config.nodes.2 = rabbit@node2  
cluster_formation.classic_config.nodes.3 = rabbit@node3

# Network timeout settings
net_ticktime = 60
cluster_keepalive_interval = 10000
""",
        
        'two_node_setup': """
# Two-node cluster configuration
cluster_partition_handling = pause_if_all_down

# Ensure proper network detection
net_ticktime = 60
cluster_keepalive_interval = 10000
""",
        
        'development': """
# Development environment (NOT for production)
cluster_partition_handling = autoheal

# Faster recovery for development
net_ticktime = 10
cluster_keepalive_interval = 5000
"""
    }
    
    return configurations
```

#### **Detecting and Monitoring Partitions**

```python
def partition_monitoring_tools():
    """Tools and commands for detecting partitions"""
    
    monitoring_commands = {
        'check_partitions': {
            'rabbitmqctl': 'rabbitmqctl cluster_status',
            'description': 'Check current cluster status and partitions',
            'example_output': '''
Cluster status of node rabbit@node1 ...
Basics
Cluster name: rabbit@node1
Disk Nodes
rabbit@node1
rabbit@node2
rabbit@node3

Running Nodes
rabbit@node1
rabbit@node2

Partitions
{rabbit@node3, [rabbit@node1, rabbit@node2]}
'''
        },
        
        'node_health': {
            'rabbitmqctl': 'rabbitmqctl node_health_check',
            'description': 'Check if current node can communicate with cluster'
        },
        
        'network_connectivity': {
            'rabbitmqctl': 'rabbitmqctl eval "net_adm:ping(\'rabbit@node2\')."',
            'description': 'Test network connectivity to specific nodes'
        },
        
        'partition_history': {
            'log_location': '/var/log/rabbitmq/rabbit@hostname.log',
            'grep_pattern': 'grep -i partition /var/log/rabbitmq/rabbit@*.log'
        }
    }
    
    return monitoring_commands

class PartitionMonitor:
    """Monitor for network partitions and split brain scenarios"""
    
    def __init__(self, nodes):
        self.nodes = nodes
        self.last_status = {}
        self.partition_history = []
    
    def check_cluster_health(self):
        """Check for partitions across all nodes"""
        
        partition_detected = False
        cluster_views = {}
        
        for node in self.nodes:
            try:
                # Get cluster status from each node
                status = self.get_node_cluster_status(node)
                cluster_views[node] = status
                
                # Check if this node sees any partitions
                if status.get('partitions'):
                    partition_detected = True
                    self.log_partition_event(node, status['partitions'])
                    
            except ConnectionError:
                # Node unreachable - potential partition
                self.log_connectivity_issue(node)
                partition_detected = True
        
        if partition_detected:
            self.handle_partition_detected(cluster_views)
        
        return not partition_detected
    
    def get_node_cluster_status(self, node):
        """Get cluster status from specific node"""
        # Implementation would use rabbitmqctl or management API
        # This is a simplified version
        import subprocess
        
        try:
            result = subprocess.run([
                'rabbitmqctl', '-n', f'rabbit@{node}', 'cluster_status'
            ], capture_output=True, text=True, timeout=30)
            
            return self.parse_cluster_status(result.stdout)
            
        except subprocess.TimeoutExpired:
            raise ConnectionError(f"Timeout connecting to {node}")
    
    def parse_cluster_status(self, output):
        """Parse rabbitmqctl cluster_status output"""
        # Simplified parser - in reality would need robust parsing
        status = {
            'running_nodes': [],
            'disc_nodes': [],
            'partitions': {}
        }
        
        # Extract information from cluster_status output
        # This would need more robust parsing in production
        
        return status
    
    def handle_partition_detected(self, cluster_views):
        """Handle detected network partition"""
        
        print("🚨 NETWORK PARTITION DETECTED!")
        
        # Determine partition topology
        partitions = self.analyze_partition_topology(cluster_views)
        
        # Log partition details
        for partition in partitions:
            print(f"   Partition: {partition['nodes']} (size: {partition['size']})")
        
        # Identify majority/minority partitions
        largest_partition = max(partitions, key=lambda p: p['size'])
        minority_partitions = [p for p in partitions if p != largest_partition]
        
        print(f"   Majority partition: {largest_partition['nodes']}")
        print(f"   Minority partitions: {[p['nodes'] for p in minority_partitions]}")
        
        # Send alerts
        self.send_partition_alert(partitions)
        
        # Record in partition history
        self.partition_history.append({
            'timestamp': datetime.now(),
            'partitions': partitions,
            'majority': largest_partition['nodes']
        })
    
    def analyze_partition_topology(self, cluster_views):
        """Analyze partition topology from different node views"""
        
        # Group nodes by their view of the cluster
        partition_groups = {}
        
        for node, status in cluster_views.items():
            running_nodes = tuple(sorted(status.get('running_nodes', [node])))
            
            if running_nodes not in partition_groups:
                partition_groups[running_nodes] = []
            partition_groups[running_nodes].append(node)
        
        # Convert to partition list
        partitions = []
        for running_nodes, member_nodes in partition_groups.items():
            partitions.append({
                'nodes': member_nodes,
                'size': len(member_nodes),
                'cluster_view': running_nodes
            })
        
        return partitions
    
    def send_partition_alert(self, partitions):
        """Send alert about network partition"""
        
        alert_message = {
            'severity': 'CRITICAL',
            'event': 'NETWORK_PARTITION',
            'timestamp': datetime.now().isoformat(),
            'partitions': partitions,
            'action_required': 'Manual intervention may be required'
        }
        
        # Send to monitoring system
        print(f"📧 Sending partition alert: {alert_message}")
        
        # In production, would integrate with:
        # - PagerDuty
        # - Slack notifications  
        # - Email alerts
        # - SNMP traps
```

#### **Partition Recovery Procedures**

```python
def partition_recovery_procedures():
    """Step-by-step partition recovery procedures"""
    
    recovery_steps = {
        'assessment': [
            "1. Identify partition scope using 'rabbitmqctl cluster_status'",
            "2. Determine majority vs minority partitions", 
            "3. Check application impact and message loss",
            "4. Verify network connectivity between nodes",
            "5. Check for any hardware or infrastructure issues"
        ],
        
        'manual_recovery': [
            "1. Fix underlying network issues",
            "2. Stop minority partition nodes: 'rabbitmqctl stop_app'", 
            "3. Restart minority nodes to rejoin cluster: 'rabbitmqctl start_app'",
            "4. Verify cluster status: 'rabbitmqctl cluster_status'",
            "5. Check for data consistency issues",
            "6. Resume normal operations"
        ],
        
        'forced_recovery': [
            "⚠️  ONLY if automatic recovery fails",
            "1. Stop all nodes: 'rabbitmqctl stop'",
            "2. Start majority partition leader first",
            "3. Start remaining majority nodes",
            "4. Force reset minority nodes: 'rabbitmqctl force_reset'", 
            "5. Rejoin minority nodes to cluster",
            "6. Restore lost data from backups if necessary"
        ]
    }
    
    return recovery_steps

def partition_recovery_script():
    """Automated partition recovery script"""
    
    script = '''#!/bin/bash
# partition_recovery.sh - Automated RabbitMQ partition recovery

set -euo pipefail

NODES=("rabbit@node1" "rabbit@node2" "rabbit@node3")
LOG_FILE="/var/log/rabbitmq-recovery.log"

log() {
    echo "$(date): $1" | tee -a $LOG_FILE
}

check_partition() {
    log "Checking for partitions..."
    
    for node in "${NODES[@]}"; do
        if rabbitmqctl -n $node cluster_status | grep -q "Partitions"; then
            log "Partition detected on $node"
            return 0
        fi
    done
    
    log "No partitions detected"
    return 1
}

identify_majority() {
    # Find the partition with the most nodes
    local max_nodes=0
    local majority_nodes=()
    
    for node in "${NODES[@]}"; do
        local running_nodes
        running_nodes=$(rabbitmqctl -n $node eval "length(mnesia:system_info(running_db_nodes))." 2>/dev/null || echo "0")
        
        if [[ $running_nodes -gt $max_nodes ]]; then
            max_nodes=$running_nodes
            majority_nodes=($node)
        elif [[ $running_nodes -eq $max_nodes ]]; then
            majority_nodes+=($node)
        fi
    done
    
    echo "${majority_nodes[@]}"
}

recover_partition() {
    log "Starting partition recovery..."
    
    # Get majority partition
    majority_nodes=($(identify_majority))
    log "Majority partition: ${majority_nodes[*]}"
    
    # Stop minority nodes
    for node in "${NODES[@]}"; do
        if [[ ! " ${majority_nodes[*]} " =~ " ${node} " ]]; then
            log "Stopping minority node: $node"
            rabbitmqctl -n $node stop_app || true
        fi
    done
    
    # Wait for network issues to resolve
    sleep 10
    
    # Restart minority nodes to rejoin
    for node in "${NODES[@]}"; do
        if [[ ! " ${majority_nodes[*]} " =~ " ${node} " ]]; then
            log "Restarting minority node: $node"
            rabbitmqctl -n $node start_app
            sleep 5
        fi
    done
    
    # Verify recovery
    if check_partition; then
        log "❌ Partition still exists - manual intervention required"
        exit 1
    else
        log "✅ Partition recovery successful"
    fi
}

# Main execution
if check_partition; then
    recover_partition
else
    log "No recovery needed"
fi
'''
    
    return script
```

#### **Prevention Strategies**

```python
def partition_prevention_strategies():
    """Strategies to prevent and minimize partition impact"""
    
    strategies = {
        'network_design': [
            "Use redundant network paths between nodes",
            "Implement network monitoring and alerting",
            "Use dedicated cluster interconnect networks", 
            "Avoid single points of network failure",
            "Configure appropriate network timeouts"
        ],
        
        'cluster_topology': [
            "Use odd number of nodes (3, 5, 7)",
            "Distribute nodes across availability zones",
            "Consider geographic distribution vs latency",
            "Use witness/arbiter nodes for tie-breaking",
            "Implement proper load balancer configuration"
        ],
        
        'configuration_best_practices': [
            "Set appropriate net_ticktime values",
            "Configure cluster_keepalive_interval",
            "Use pause_minority for production",
            "Monitor cluster health continuously", 
            "Implement automated recovery procedures"
        ],
        
        'application_design': [
            "Design for eventual consistency",
            "Implement client-side retry logic",
            "Use circuit breakers for resilience",
            "Design idempotent message processing",
            "Implement proper error handling"
        ]
    }
    
    return strategies

# Production configuration for partition resilience
production_config = """
# Network partition handling
cluster_partition_handling = pause_minority

# Network timeouts (in seconds)
net_ticktime = 60
cluster_keepalive_interval = 10000

# Heartbeat settings
heartbeat = 60

# Memory settings to prevent false partitions due to GC
vm_memory_high_watermark.relative = 0.6

# Logging for partition debugging
log.file.level = info
log.connection.level = info
log.channel.level = info
"""
```

#### **Quorum Queues and Partition Tolerance**

```python
def quorum_queues_partition_behavior():
    """How quorum queues handle network partitions"""
    
    behavior_explanation = """
    Quorum queues provide better partition tolerance than classic mirrored queues:
    
    1. **Raft Consensus**: Uses Raft algorithm for leader election
    2. **Majority Required**: Requires majority of replicas to be available
    3. **Automatic Recovery**: Automatically recovers when partition heals
    4. **Data Safety**: Guarantees no message loss during partitions
    5. **Poison Message Handling**: Built-in poison message detection
    """
    
    partition_scenarios = {
        'majority_partition': {
            'scenario': 'Majority of nodes available',
            'behavior': 'Queue remains available for reads and writes',
            'example': '3-node cluster, 2 nodes in majority partition'
        },
        
        'minority_partition': {
            'scenario': 'Minority of nodes available', 
            'behavior': 'Queue becomes unavailable (read-only or offline)',
            'example': '3-node cluster, 1 node in minority partition'
        },
        
        'split_even': {
            'scenario': 'Even split of nodes',
            'behavior': 'Queue becomes unavailable (no majority)',
            'example': '4-node cluster split 2-2 (not recommended topology)'
        }
    }
    
    # Example: Monitor quorum queue status during partition
    monitoring_code = """
# Check quorum queue status
rabbitmqctl list_quorum_queues name online members

# Example output during partition:
# orders_queue    [rabbit@node1, rabbit@node2]    [rabbit@node1, rabbit@node2, rabbit@node3]

# 'online' shows currently available replicas
# 'members' shows all configured replicas
"""
    
    return {
        'explanation': behavior_explanation,
        'scenarios': partition_scenarios, 
        'monitoring': monitoring_code
    }
```

#### **Testing Split Brain Scenarios**

```python
def split_brain_testing():
    """Tools and procedures for testing split brain scenarios"""
    
    testing_procedures = {
        'network_isolation': """
# Simulate network partition using iptables
# On node1, block communication with node3:
iptables -A INPUT -s <node3_ip> -j DROP
iptables -A OUTPUT -d <node3_ip> -j DROP

# Restore communication:
iptables -D INPUT -s <node3_ip> -j DROP  
iptables -D OUTPUT -d <node3_ip> -j DROP
""",
        
        'chaos_engineering': """
# Using Chaos Monkey tools
# 1. Pumba for Docker containers
pumba netem --duration 1m --interface eth0 delay --time 2000ms rabbitmq-node3

# 2. Kubernetes chaos engineering
kubectl apply -f chaos-experiment.yaml
""",
        
        'manual_testing': """
# Test different partition scenarios
1. Stop network on minority node
2. Verify majority partition continues operating
3. Verify minority node pauses (with pause_minority)
4. Restore network
5. Verify cluster heals automatically
6. Check for data consistency
""",
        
        'automated_testing': """
#!/bin/bash
# automated_partition_test.sh

test_partition_scenario() {
    local scenario=$1
    
    echo "Testing scenario: $scenario"
    
    # Create test messages
    publish_test_messages
    
    # Simulate partition based on scenario
    simulate_partition $scenario
    
    # Verify expected behavior
    verify_partition_behavior $scenario
    
    # Heal partition
    heal_partition
    
    # Verify recovery
    verify_recovery
    
    echo "Scenario $scenario: PASSED"
}

# Test all scenarios
for scenario in "minority_isolated" "even_split" "majority_isolated"; do
    test_partition_scenario $scenario
done
"""
    }
    
    return testing_procedures
```

This comprehensive split brain section covers detection, prevention, recovery, and testing of network partition scenarios - essential knowledge for managing production RabbitMQ clusters.

---

## 📊 **Management & Monitoring**

### **1. Management API**

```python
import requests
from requests.auth import HTTPBasicAuth

class RabbitMQManagement:
    """RabbitMQ Management API client"""
    
    def __init__(self, host='localhost', port=15672, username='guest', password='guest'):
        self.base_url = f"http://{host}:{port}/api"
        self.auth = HTTPBasicAuth(username, password)
    
    def get_overview(self):
        """Get cluster overview"""
        response = requests.get(f"{self.base_url}/overview", auth=self.auth)
        return response.json()
    
    def get_queues(self, vhost='/'):
        """Get queue information"""
        response = requests.get(f"{self.base_url}/queues/{vhost}", auth=self.auth)
        return response.json()
    
    def get_queue_details(self, queue_name, vhost='/'):
        """Get detailed queue information"""
        response = requests.get(
            f"{self.base_url}/queues/{vhost}/{queue_name}",
            auth=self.auth
        )
        return response.json()
    
    def get_exchanges(self, vhost='/'):
        """Get exchange information"""
        response = requests.get(f"{self.base_url}/exchanges/{vhost}", auth=self.auth)
        return response.json()
    
    def get_connections(self):
        """Get connection information"""
        response = requests.get(f"{self.base_url}/connections", auth=self.auth)
        return response.json()
    
    def get_channels(self):
        """Get channel information"""
        response = requests.get(f"{self.base_url}/channels", auth=self.auth)
        return response.json()

# Usage example
def monitoring_example():
    """Monitor RabbitMQ via Management API"""
    
    mgmt = RabbitMQManagement()
    
    # Get cluster overview
    overview = mgmt.get_overview()
    print(f"📊 RabbitMQ Version: {overview['rabbitmq_version']}")
    print(f"📊 Total Queues: {overview['object_totals']['queues']}")
    print(f"📊 Total Connections: {overview['object_totals']['connections']}")
    
    # Monitor queue depths
    queues = mgmt.get_queues()
    for queue in queues:
        name = queue['name']
        messages = queue['messages']
        consumers = queue['consumers']
        
        if messages > 1000:  # Alert threshold
            print(f"⚠️ Queue {name} has {messages} messages!")
        
        if consumers == 0 and messages > 0:
            print(f"🚨 Queue {name} has no consumers but {messages} messages!")
    
    # Monitor connections
    connections = mgmt.get_connections()
    for conn in connections:
        if conn['state'] != 'running':
            print(f"🔌 Connection {conn['name']} is {conn['state']}")
```

### **2. Metrics Collection**

```python
def metrics_collection_example():
    """Collect RabbitMQ metrics for monitoring systems"""
    
    import time
    from collections import defaultdict
    
    class RabbitMQMetricsCollector:
        def __init__(self, management_client):
            self.mgmt = management_client
            self.metrics = defaultdict(list)
        
        def collect_metrics(self):
            """Collect key metrics"""
            timestamp = time.time()
            
            # Queue metrics
            queues = self.mgmt.get_queues()
            for queue in queues:
                queue_name = queue['name']
                
                # Message counts
                self.metrics[f"queue.{queue_name}.messages"].append({
                    'timestamp': timestamp,
                    'value': queue['messages']
                })
                
                # Consumer count
                self.metrics[f"queue.{queue_name}.consumers"].append({
                    'timestamp': timestamp,
                    'value': queue['consumers']
                })
                
                # Message rates
                if 'message_stats' in queue:
                    stats = queue['message_stats']
                    
                    # Publish rate
                    if 'publish_details' in stats:
                        self.metrics[f"queue.{queue_name}.publish_rate"].append({
                            'timestamp': timestamp,
                            'value': stats['publish_details'].get('rate', 0)
                        })
                    
                    # Consume rate
                    if 'deliver_get_details' in stats:
                        self.metrics[f"queue.{queue_name}.consume_rate"].append({
                            'timestamp': timestamp,
                            'value': stats['deliver_get_details'].get('rate', 0)
                        })
            
            # Node metrics
            overview = self.mgmt.get_overview()
            
            # Memory usage
            self.metrics['cluster.memory_used'].append({
                'timestamp': timestamp,
                'value': overview.get('memory_used', 0)
            })
            
            # Disk free space
            self.metrics['cluster.disk_free'].append({
                'timestamp': timestamp,
                'value': overview.get('disk_free', 0)
            })
            
            # Connection count
            self.metrics['cluster.connections'].append({
                'timestamp': timestamp,
                'value': overview['object_totals']['connections']
            })
        
        def get_alerts(self):
            """Generate alerts based on metrics"""
            alerts = []
            
            # Check queue depths
            queues = self.mgmt.get_queues()
            for queue in queues:
                name = queue['name']
                messages = queue['messages']
                consumers = queue['consumers']
                
                # High queue depth
                if messages > 10000:
                    alerts.append({
                        'severity': 'warning',
                        'message': f"Queue {name} has {messages} messages (>10k threshold)"
                    })
                
                # No consumers
                if consumers == 0 and messages > 0:
                    alerts.append({
                        'severity': 'critical',
                        'message': f"Queue {name} has no consumers but {messages} messages"
                    })
                
                # Slow consumption rate
                if 'message_stats' in queue and 'deliver_get_details' in queue['message_stats']:
                    consume_rate = queue['message_stats']['deliver_get_details'].get('rate', 0)
                    if consume_rate < 1 and messages > 100:
                        alerts.append({
                            'severity': 'warning',
                            'message': f"Queue {name} has slow consumption rate: {consume_rate}/sec"
                        })
            
            return alerts
    
    # Usage
    mgmt = RabbitMQManagement()
    collector = RabbitMQMetricsCollector(mgmt)
    
    # Collect metrics
    collector.collect_metrics()
    
    # Check for alerts
    alerts = collector.get_alerts()
    for alert in alerts:
        print(f"🚨 {alert['severity'].upper()}: {alert['message']}")
```

### **3. Health Checks**

```python
def health_check_example():
    """Implement comprehensive health checks"""
    
    class RabbitMQHealthCheck:
        def __init__(self, connection_params, management_client):
            self.connection_params = connection_params
            self.mgmt = management_client
        
        def check_connectivity(self):
            """Check basic connectivity"""
            try:
                connection = pika.BlockingConnection(self.connection_params)
                connection.close()
                return True, "Connectivity OK"
            except Exception as e:
                return False, f"Connectivity failed: {e}"
        
        def check_node_health(self):
            """Check node health via management API"""
            try:
                overview = self.mgmt.get_overview()
                
                # Check if node is running
                if overview.get('running', False):
                    return True, "Node is running"
                else:
                    return False, "Node is not running"
                    
            except Exception as e:
                return False, f"Health check failed: {e}"
        
        def check_queue_health(self, critical_queues):
            """Check health of critical queues"""
            try:
                queues = self.mgmt.get_queues()
                queue_map = {q['name']: q for q in queues}
                
                issues = []
                
                for queue_name in critical_queues:
                    if queue_name not in queue_map:
                        issues.append(f"Critical queue {queue_name} not found")
                        continue
                    
                    queue = queue_map[queue_name]
                    
                    # Check if queue has consumers
                    if queue['consumers'] == 0:
                        issues.append(f"Queue {queue_name} has no consumers")
                    
                    # Check message buildup
                    if queue['messages'] > 50000:
                        issues.append(f"Queue {queue_name} has {queue['messages']} messages")
                
                if issues:
                    return False, "; ".join(issues)
                else:
                    return True, "All critical queues healthy"
                    
            except Exception as e:
                return False, f"Queue health check failed: {e}"
        
        def check_cluster_health(self):
            """Check cluster health"""
            try:
                nodes = self.mgmt.get_overview().get('nodes', [])
                
                if not nodes:
                    return False, "No nodes found in cluster"
                
                running_nodes = [n for n in nodes if n.get('running', False)]
                
                if len(running_nodes) == 0:
                    return False, "No nodes running"
                elif len(running_nodes) < len(nodes):
                    return False, f"Only {len(running_nodes)}/{len(nodes)} nodes running"
                else:
                    return True, f"All {len(nodes)} nodes running"
                    
            except Exception as e:
                return False, f"Cluster health check failed: {e}"
        
        def comprehensive_health_check(self, critical_queues=None):
            """Run all health checks"""
            critical_queues = critical_queues or []
            
            checks = [
                ("Connectivity", self.check_connectivity),
                ("Node Health", self.check_node_health),
                ("Cluster Health", self.check_cluster_health),
            ]
            
            if critical_queues:
                checks.append(("Queue Health", lambda: self.check_queue_health(critical_queues)))
            
            results = {}
            overall_healthy = True
            
            for check_name, check_func in checks:
                try:
                    healthy, message = check_func()
                    results[check_name] = {'healthy': healthy, 'message': message}
                    
                    if not healthy:
                        overall_healthy = False
                        
                except Exception as e:
                    results[check_name] = {'healthy': False, 'message': str(e)}
                    overall_healthy = False
            
            results['overall'] = {'healthy': overall_healthy}
            return results
    
    # Usage
    connection_params = pika.ConnectionParameters('localhost')
    mgmt = RabbitMQManagement()
    
    health_checker = RabbitMQHealthCheck(connection_params, mgmt)
    
    # Run comprehensive health check
    critical_queues = ['orders', 'payments', 'notifications']
    health_results = health_checker.comprehensive_health_check(critical_queues)
    
    # Print results
    for check_name, result in health_results.items():
        status = "✅" if result['healthy'] else "❌"
        message = result.get('message', '')
        print(f"{status} {check_name}: {message}")
```

---

## 🛠️ **Command Line Tools (rabbitmqctl & rabbitmqadmin)**

RabbitMQ provides powerful command-line tools for administration, monitoring, and management. This section covers the most important commands for production environments.

### **1. rabbitmqctl - Core Administration Tool**

`rabbitmqctl` is the primary tool for managing RabbitMQ servers and clusters.

#### **Cluster Management**

```bash
# Cluster Status and Information
rabbitmqctl cluster_status
rabbitmqctl status
rabbitmqctl environment
rabbitmqctl report  # Comprehensive system report

# Node Management
rabbitmqctl start_app
rabbitmqctl stop_app
rabbitmqctl restart
rabbitmqctl shutdown

# Join/Leave Cluster
rabbitmqctl stop_app
rabbitmqctl reset  # Reset node to default state
rabbitmqctl join_cluster rabbit@node1
rabbitmqctl start_app

# Remove node from cluster (run from remaining node)
rabbitmqctl forget_cluster_node rabbit@failed_node

# Force cluster reset (dangerous - data loss)
rabbitmqctl force_reset
```

#### **User Management**

```bash
# Create Users
rabbitmqctl add_user username password
rabbitmqctl add_user admin StrongPassword123
rabbitmqctl add_user api_service ServicePass456

# Delete Users
rabbitmqctl delete_user username
rabbitmqctl delete_user old_user

# List Users
rabbitmqctl list_users

# Change Password
rabbitmqctl change_password username new_password

# Set User Tags (roles)
rabbitmqctl set_user_tags username administrator
rabbitmqctl set_user_tags api_service monitoring
rabbitmqctl set_user_tags readonly_user monitoring

# Available tags: administrator, monitoring, policymaker, management, impersonator

# Clear User Tags
rabbitmqctl set_user_tags username
```

#### **Virtual Host Management**

```bash
# Create Virtual Hosts
rabbitmqctl add_vhost /production
rabbitmqctl add_vhost /staging  
rabbitmqctl add_vhost /development

# Delete Virtual Hosts
rabbitmqctl delete_vhost /old_environment

# List Virtual Hosts
rabbitmqctl list_vhosts
rabbitmqctl list_vhosts name tracing

# Set Virtual Host Limits
rabbitmqctl set_vhost_limits -p /production '{"connection-limit": 1000, "queue-limit": 500}'
rabbitmqctl clear_vhost_limits -p /production
```

#### **Permissions Management**

```bash
# Set User Permissions
# Format: rabbitmqctl set_permissions [-p vhost] username configure write read
rabbitmqctl set_permissions -p /production api_user "^api\." "^api\." "^api\."
rabbitmqctl set_permissions -p /production readonly_user "" "" ".*"
rabbitmqctl set_permissions -p /production admin_user ".*" ".*" ".*"

# Examples of permission patterns:
# ".*" - all resources
# "^orders\." - resources starting with "orders."
# "" - no access
# "^(orders|payments)\." - resources starting with "orders." or "payments."

# List Permissions
rabbitmqctl list_permissions -p /production
rabbitmqctl list_user_permissions username

# Clear Permissions
rabbitmqctl clear_permissions -p /production username
```

#### **Queue Management**

```bash
# List Queues
rabbitmqctl list_queues
rabbitmqctl list_queues name messages consumers
rabbitmqctl list_queues name messages messages_ready messages_unacknowledged

# Detailed Queue Information
rabbitmqctl list_queues name messages consumers memory messages_ready \
    messages_unacknowledged messages_persistent message_bytes \
    message_bytes_ready message_bytes_unacknowledged

# Queue Operations
rabbitmqctl purge_queue queue_name  # Delete all messages
rabbitmqctl delete_queue queue_name  # Delete entire queue

# List Queues in Specific VHost
rabbitmqctl list_queues -p /production name messages

# Queue Information with Totals
rabbitmqctl list_queues --formatter=pretty_table
```

#### **Exchange Management**

```bash
# List Exchanges
rabbitmqctl list_exchanges
rabbitmqctl list_exchanges name type durable auto_delete

# List Exchanges in Specific VHost
rabbitmqctl list_exchanges -p /production

# Exchange Information
rabbitmqctl list_exchanges name type durable auto_delete arguments policy
```

#### **Binding Management**

```bash
# List Bindings
rabbitmqctl list_bindings
rabbitmqctl list_bindings source_name destination_name destination_type routing_key

# List Bindings for Specific VHost
rabbitmqctl list_bindings -p /production

# Specific Binding Queries
rabbitmqctl list_bindings -p /production | grep "orders"
```

#### **Connection and Channel Management**

```bash
# List Connections
rabbitmqctl list_connections
rabbitmqctl list_connections name peer_host peer_port state channels

# Detailed Connection Information
rabbitmqctl list_connections name user vhost host port ssl \
    peer_host peer_port state channels recv_cnt send_cnt \
    recv_oct send_oct

# List Channels
rabbitmqctl list_channels
rabbitmqctl list_channels connection name number user vhost \
    consumer_count messages_unacknowledged

# Close Connection
rabbitmqctl close_connection "<connection_name>" "Maintenance shutdown"

# List Consumers
rabbitmqctl list_consumers
rabbitmqctl list_consumers -p /production queue_name channel_name \
    consumer_tag ack_required prefetch_count
```

#### **Policy Management**

```bash
# Set Policies
# High Availability Policy
rabbitmqctl set_policy -p /production ha-all "^ha\." \
    '{"ha-mode":"all","ha-sync-mode":"automatic"}'

# TTL Policy
rabbitmqctl set_policy -p /production ttl-policy "^temp\." \
    '{"message-ttl":3600000}'

# Max Length Policy
rabbitmqctl set_policy -p /production max-length "^limited\." \
    '{"max-length":10000,"overflow":"reject-publish"}'

# Dead Letter Exchange Policy
rabbitmqctl set_policy -p /production dlx-policy "^critical\." \
    '{"dead-letter-exchange":"failed-messages","dead-letter-routing-key":"failed"}'

# Federation Policy
rabbitmqctl set_policy -p /production federation-policy "^fed\." \
    '{"federation-upstream":"remote-cluster"}'

# List Policies
rabbitmqctl list_policies
rabbitmqctl list_policies -p /production

# Clear Policy
rabbitmqctl clear_policy -p /production policy-name
```

#### **Parameter Management**

```bash
# Set Parameters
# Federation Upstream
rabbitmqctl set_parameter -p /production federation-upstream remote-cluster \
    '{"uri":"amqp://user:pass@remote.example.com","trust-user-id":false}'

# Shovel
rabbitmqctl set_parameter -p /production shovel my-shovel \
    '{"src-queue":"source","src-uri":"amqp://","dest-queue":"dest","dest-uri":"amqp://remote"}'

# List Parameters
rabbitmqctl list_parameters
rabbitmqctl list_parameters -p /production

# Clear Parameter
rabbitmqctl clear_parameter -p /production federation-upstream remote-cluster
```

#### **Monitoring and Diagnostics**

```bash
# Node Status
rabbitmqctl node_health_check
rabbitmqctl ping

# Memory Usage
rabbitmqctl status | grep memory
rabbitmqctl eval 'rabbit_vm:memory().'

# Disk Usage
rabbitmqctl eval 'rabbit_disk_monitor:get_disk_free().'

# Alarms
rabbitmqctl eval 'rabbit_alarm:get_alarms().'

# Plugin Status
rabbitmqctl list_enabled_plugins
rabbitmqctl enable_plugin rabbitmq_management
rabbitmqctl disable_plugin plugin_name

# Log Levels
rabbitmqctl set_log_level debug
rabbitmqctl set_log_level info
rabbitmqctl set_log_level warning
rabbitmqctl set_log_level error
```

#### **Maintenance Operations**

```bash
# Force GC on All Processes
rabbitmqctl eval 'rabbit_memory_monitor:force_gc().'

# Rotate Logs
rabbitmqctl rotate_logs

# Sync Queue (for HA queues)
rabbitmqctl sync_queue queue_name

# Cancel Sync
rabbitmqctl cancel_sync_queue queue_name

# Set Memory High Watermark
rabbitmqctl eval 'vm_memory_monitor:set_vm_memory_high_watermark(0.6).'

# Block/Unblock Connections
rabbitmqctl set_vm_memory_high_watermark 0.1  # Low threshold to block
rabbitmqctl set_vm_memory_high_watermark 0.6  # Normal threshold
```

### **2. rabbitmqadmin - HTTP API Tool**

`rabbitmqadmin` is a convenient tool that uses the HTTP API for management operations.

#### **Installation and Setup**

```bash
# Download rabbitmqadmin (adjust URL for your RabbitMQ version)
wget http://localhost:15672/cli/rabbitmqadmin
chmod +x rabbitmqadmin

# Or install via package manager
# Ubuntu/Debian: apt-get install rabbitmq-server
# The tool is included with RabbitMQ

# Basic Configuration
export RABBITMQ_ADMIN_URL=http://localhost:15672
export RABBITMQ_ADMIN_USER=admin
export RABBITMQ_ADMIN_PASS=password

# Test Connection
./rabbitmqadmin --help
```

#### **Basic Operations**

```bash
# List Resources
./rabbitmqadmin list exchanges
./rabbitmqadmin list queues
./rabbitmqadmin list bindings
./rabbitmqadmin list connections
./rabbitmqadmin list channels
./rabbitmqadmin list consumers

# List with Specific Columns
./rabbitmqadmin list queues name messages consumers
./rabbitmqadmin list exchanges name type durable
```

#### **Declare Resources**

```bash
# Declare Exchange
./rabbitmqadmin declare exchange name=my-exchange type=direct durable=true

# Declare Topic Exchange with Arguments
./rabbitmqadmin declare exchange name=events type=topic durable=true \
    arguments='{"alternate-exchange":"unrouted"}'

# Declare Queue
./rabbitmqadmin declare queue name=my-queue durable=true

# Declare Queue with Arguments
./rabbitmqadmin declare queue name=priority-queue durable=true \
    arguments='{"x-max-priority":10,"x-message-ttl":3600000}'

# Declare Dead Letter Queue Setup
./rabbitmqadmin declare queue name=main-queue durable=true \
    arguments='{"x-dead-letter-exchange":"dlx","x-dead-letter-routing-key":"failed"}'
./rabbitmqadmin declare exchange name=dlx type=direct
./rabbitmqadmin declare queue name=dead-letters durable=true
```

#### **Binding Management**

```bash
# Create Bindings
./rabbitmqadmin declare binding source=my-exchange destination=my-queue \
    routing_key=my.routing.key

# Topic Binding
./rabbitmqadmin declare binding source=events destination=order-queue \
    routing_key="order.*"

# Fanout Binding (no routing key needed)
./rabbitmqadmin declare binding source=notifications destination=email-queue

# Headers Binding
./rabbitmqadmin declare binding source=content destination=image-queue \
    arguments='{"x-match":"all","type":"image","priority":"high"}'
```

#### **Message Operations**

```bash
# Publish Messages
./rabbitmqadmin publish exchange=my-exchange routing_key=test \
    payload="Hello World"

# Publish JSON Message
./rabbitmqadmin publish exchange=events routing_key=order.created \
    payload='{"order_id":"123","customer":"john@example.com"}' \
    properties='{"content_type":"application/json","delivery_mode":2}'

# Publish with Headers
./rabbitmqadmin publish exchange=my-exchange routing_key=test \
    payload="Test message" \
    properties='{"headers":{"source":"admin","priority":"high"}}'

# Get Messages (consume)
./rabbitmqadmin get queue=my-queue requeue=true count=5
./rabbitmqadmin get queue=my-queue requeue=false  # Remove from queue
```

#### **Import/Export Definitions**

```bash
# Export All Definitions
./rabbitmqadmin export rabbit-backup.json

# Export Specific VHost
./rabbitmqadmin -V /production export production-backup.json

# Import Definitions
./rabbitmqadmin import rabbit-backup.json

# Export Only Specific Resource Types
./rabbitmqadmin list queues --format=long > queues-backup.txt
./rabbitmqadmin list exchanges --format=long > exchanges-backup.txt
```

#### **Advanced Operations**

```bash
# Purge Queue
./rabbitmqadmin purge queue name=my-queue

# Delete Resources
./rabbitmqadmin delete queue name=temp-queue
./rabbitmqadmin delete exchange name=old-exchange
./rabbitmqadmin delete binding source=my-exchange destination=my-queue \
    properties_key=my.routing.key

# Close Connection
./rabbitmqadmin close connection name="127.0.0.1:12345 -> 127.0.0.1:5672"

# Different Output Formats
./rabbitmqadmin list queues --format=table
./rabbitmqadmin list queues --format=long
./rabbitmqadmin list queues --format=kvp
./rabbitmqadmin list queues --format=tsv
```

#### **Monitoring with rabbitmqadmin**

```bash
# Monitor Queue Depths
./rabbitmqadmin list queues name messages | \
    awk 'NR>1 && $2>1000 {print "Alert: Queue "$1" has "$2" messages"}'

# Monitor Connection Count
./rabbitmqadmin list connections --format=tsv | wc -l

# Check Node Health via API
./rabbitmqadmin show overview

# Monitor Memory Usage
./rabbitmqadmin show overview | jq '.memory_used'
```

### **3. Advanced CLI Workflows**

#### **Cluster Maintenance Script**

```bash
#!/bin/bash
# cluster_health_check.sh

echo "=== RabbitMQ Cluster Health Check ==="

# Check cluster status
echo "1. Cluster Status:"
rabbitmqctl cluster_status

# Check node health
echo -e "\n2. Node Health:"
rabbitmqctl node_health_check

# Check memory usage
echo -e "\n3. Memory Usage:"
rabbitmqctl status | grep memory

# Check queue depths
echo -e "\n4. Queue Depths (>1000 messages):"
rabbitmqctl list_queues name messages | awk 'NR>1 && $2>1000 {print $1": "$2" messages"}'

# Check connections
echo -e "\n5. Connection Count:"
rabbitmqctl list_connections | wc -l

# Check for alarms
echo -e "\n6. Active Alarms:"
rabbitmqctl eval 'rabbit_alarm:get_alarms().'

echo -e "\n=== Health Check Complete ==="
```

#### **Backup and Restore Script**

```bash
#!/bin/bash
# backup_rabbitmq.sh

BACKUP_DIR="/opt/rabbitmq-backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/rabbitmq_backup_$DATE.json"

# Create backup directory
mkdir -p $BACKUP_DIR

# Export definitions
echo "Creating backup: $BACKUP_FILE"
rabbitmqadmin export $BACKUP_FILE

# Backup permissions and users separately
rabbitmqctl list_users > "$BACKUP_DIR/users_$DATE.txt"
rabbitmqctl list_permissions > "$BACKUP_DIR/permissions_$DATE.txt"
rabbitmqctl list_policies > "$BACKUP_DIR/policies_$DATE.txt"

echo "Backup complete!"
echo "Files created:"
ls -la $BACKUP_DIR/*$DATE*
```

#### **Queue Monitoring Script**

```bash
#!/bin/bash
# monitor_queues.sh

# Set thresholds
MESSAGE_THRESHOLD=5000
CONSUMER_THRESHOLD=0

echo "=== Queue Monitoring Report ==="
echo "Date: $(date)"
echo ""

# Check for queues with high message count
echo "Queues with >$MESSAGE_THRESHOLD messages:"
rabbitmqctl list_queues name messages consumers | \
awk -v threshold=$MESSAGE_THRESHOLD 'NR>1 && $2>threshold {
    printf "  %-30s %8d messages, %d consumers\n", $1, $2, $3
}'

echo ""

# Check for queues with no consumers
echo "Queues with no consumers (but have messages):"
rabbitmqctl list_queues name messages consumers | \
awk 'NR>1 && $2>0 && $3==0 {
    printf "  %-30s %8d messages, NO CONSUMERS\n", $1, $2
}'

echo ""

# Memory usage by queue
echo "Top 10 queues by memory usage:"
rabbitmqctl list_queues name memory | \
sort -k2 -nr | head -10 | \
awk 'NR>1 {
    printf "  %-30s %10d bytes\n", $1, $2
}'
```

#### **User Management Script**

```bash
#!/bin/bash
# manage_users.sh

create_service_user() {
    local username=$1
    local password=$2
    local vhost=$3
    local permissions=${4:-"\"\" \"\" \"\""}  # Default: no permissions
    
    echo "Creating user: $username"
    rabbitmqctl add_user $username $password
    rabbitmqctl set_permissions -p $vhost $username $permissions
    echo "User $username created with permissions on $vhost"
}

create_admin_user() {
    local username=$1
    local password=$2
    
    echo "Creating admin user: $username"
    rabbitmqctl add_user $username $password
    rabbitmqctl set_user_tags $username administrator
    rabbitmqctl set_permissions -p / $username ".*" ".*" ".*"
    echo "Admin user $username created"
}

# Examples:
# create_service_user "order-service" "SecurePass123" "/production" "\"^orders\.\" \"^orders\.\" \"^orders\.\""
# create_admin_user "prod-admin" "AdminPass456"
```

### **4. Quick Reference Commands**

#### **Emergency Commands**

```bash
# Stop accepting new connections (emergency)
rabbitmqctl set_vm_memory_high_watermark 0.0

# Resume normal operations
rabbitmqctl set_vm_memory_high_watermark 0.6

# Force garbage collection (high memory usage)
rabbitmqctl eval 'rabbit_memory_monitor:force_gc().'

# Emergency queue purge
rabbitmqctl purge_queue dangerous_queue

# Emergency node reset (DATA LOSS!)
rabbitmqctl stop_app
rabbitmqctl force_reset
rabbitmqctl start_app
```

#### **Daily Operations**

```bash
# Quick health check
rabbitmqctl node_health_check && echo "Node healthy"

# Check queue depths
rabbitmqctl list_queues name messages | sort -k2 -nr | head -10

# Monitor connections
watch -n 5 'rabbitmqctl list_connections | wc -l'

# Check cluster status
rabbitmqctl cluster_status | grep nodes

# View recent logs
tail -f /var/log/rabbitmq/rabbit@$(hostname).log
```

#### **Performance Commands**

```bash
# Check memory distribution
rabbitmqctl eval 'rabbit_vm:memory().'

# Check disk usage
df -h /var/lib/rabbitmq/

# Monitor message rates
rabbitmqctl list_queues name message_stats.publish_details.rate \
    message_stats.deliver_get_details.rate

# Check connection states
rabbitmqctl list_connections state | sort | uniq -c
```

This comprehensive command reference covers the essential `rabbitmqctl` and `rabbitmqadmin` commands needed for production RabbitMQ management, from basic operations to advanced troubleshooting and maintenance tasks.

---

## ⚡ **Performance Tuning**

### **1. Connection and Channel Optimization**

```python
def connection_optimization_example():
    """Optimize connections and channels for performance"""
    
    # Connection pooling for applications
    class RabbitMQConnectionPool:
        def __init__(self, connection_params, pool_size=10):
            self.connection_params = connection_params
            self.pool_size = pool_size
            self.connections = []
            self.available_connections = []
            
            # Create connection pool
            for _ in range(pool_size):
                conn = pika.BlockingConnection(connection_params)
                self.connections.append(conn)
                self.available_connections.append(conn)
        
        def get_connection(self):
            """Get connection from pool"""
            if self.available_connections:
                return self.available_connections.pop()
            else:
                # Pool exhausted - create temporary connection
                return pika.BlockingConnection(self.connection_params)
        
        def return_connection(self, connection):
            """Return connection to pool"""
            if connection in self.connections:
                self.available_connections.append(connection)
            else:
                # Temporary connection - close it
                connection.close()
        
        def close_all(self):
            """Close all connections"""
            for conn in self.connections:
                if not conn.is_closed:
                    conn.close()
    
    # Channel optimization
    def optimized_publisher_example():
        """Publisher with optimized channel usage"""
        
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        
        # Use single channel for multiple operations
        channel = connection.channel()
        channel.confirm_delivery()
        
        # Batch publishing for better performance
        def publish_batch(messages, exchange, routing_key):
            successful = 0
            failed = 0
            
            for message in messages:
                try:
                    channel.basic_publish(
                        exchange=exchange,
                        routing_key=routing_key,
                        body=json.dumps(message),
                        properties=pika.BasicProperties(
                            delivery_mode=2,  # Persistent
                            content_type='application/json'
                        )
                    )
                    successful += 1
                except pika.exceptions.UnroutableError:
                    failed += 1
            
            return successful, failed
        
        # Example usage
        test_messages = [{'id': i, 'data': f'message-{i}'} for i in range(1000)]
        success, failure = publish_batch(test_messages, '', 'test_queue')
        
        print(f"📊 Published: {success} successful, {failure} failed")
        
        connection.close()

# Performance tips:
# ✅ Use connection pooling
# ✅ Reuse channels when possible  
# ✅ Enable publisher confirms for reliability
# ✅ Batch operations when possible
# ❌ Don't create new connection per message
# ❌ Don't create excessive channels
```

### **2. Queue and Exchange Optimization**

```python
def queue_optimization_example():
    """Optimize queue and exchange settings"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # Optimized queue for high throughput
        channel.queue_declare(
            queue='high_throughput_queue',
            durable=True,
            arguments={
                # Lazy loading for memory efficiency
                'x-queue-mode': 'lazy',
                
                # Limit queue size to prevent memory issues
                'x-max-length': 100000,
                'x-overflow': 'drop-head',  # Drop oldest messages
                
                # Optimize for single consumer
                'x-single-active-consumer': True,
                
                # TTL for automatic cleanup
                'x-message-ttl': 3600000,  # 1 hour
            }
        )
        
        # Optimized exchange for routing
        channel.exchange_declare(
            exchange='optimized_topic',
            exchange_type='topic',
            durable=True,
            arguments={
                'alternate-exchange': 'unrouted_messages'  # Handle unrouted messages
            }
        )
        
        # Direct exchange for simple routing (fastest)
        channel.exchange_declare(
            exchange='fast_direct',
            exchange_type='direct',
            durable=True
        )
        
        print("🚀 Created optimized queues and exchanges")

# Optimization guidelines:
# - Use lazy queues for large message volumes
# - Use direct exchange when possible (fastest routing)
# - Set appropriate queue limits
# - Use single active consumer for ordered processing
# - Configure TTL to prevent message buildup
```

### **3. Consumer Optimization**

```python
def consumer_optimization_example():
    """Optimize consumer performance"""
    
    with RabbitMQConnection() as rmq:
        channel = rmq.channel
        
        # Optimal QoS settings
        channel.basic_qos(
            prefetch_count=50,  # Higher for throughput, lower for fair distribution
            prefetch_size=0,    # 0 = unlimited message size
            global_qos=False    # Per-consumer vs per-channel
        )
        
        # High-performance consumer
        def optimized_callback(ch, method, properties, body):
            """Optimized message processing"""
            
            try:
                # Fast deserialization
                message = json.loads(body)
                
                # Batch acknowledgments for throughput
                if method.delivery_tag % 10 == 0:  # Ack every 10th message
                    ch.basic_ack(delivery_tag=method.delivery_tag, multiple=True)
                
                # Minimal processing logic
                process_message_fast(message)
                
            except Exception as e:
                # Fast rejection for problematic messages
                ch.basic_nack(
                    delivery_tag=method.delivery_tag,
                    requeue=False,  # Don't requeue bad messages
                    multiple=False
                )
        
        channel.basic_consume(
            queue='optimized_queue',
            on_message_callback=optimized_callback,
            auto_ack=False  # Manual ack for reliability
        )
        
        print("🏃 Setup optimized consumer")

def process_message_fast(message):
    """Fast message processing"""
    # Keep processing logic simple and fast
    # Move heavy processing to background workers
    pass

# Consumer optimization tips:
# ✅ Set appropriate prefetch_count
# ✅ Use batch acknowledgments for throughput
# ✅ Process messages quickly
# ✅ Use multiple consumers for parallelism
# ❌ Don't do heavy processing in callback
# ❌ Don't requeue bad messages indefinitely
```

### **4. Memory and Disk Optimization**

```python
def resource_optimization_config():
    """Configuration for memory and disk optimization"""
    
    # RabbitMQ configuration (rabbitmq.conf)
    rabbitmq_config = """
    # Memory management
    vm_memory_high_watermark.relative = 0.6  # Use 60% of available memory
    vm_memory_calculation_strategy = allocated  # More accurate memory calculation
    
    # Disk management  
    disk_free_limit.absolute = 2GB  # Stop accepting messages below 2GB free
    
    # Lazy queue defaults
    queue_master_locator = min-masters  # Distribute masters evenly
    
    # Cluster settings
    cluster_formation.peer_discovery_backend = classic_config
    cluster_partition_handling = pause_minority
    
    # Log settings
    log.file.level = warning  # Reduce log volume in production
    """
    
    # Queue configuration for memory efficiency
    memory_efficient_queue_args = {
        'x-queue-mode': 'lazy',  # Store messages on disk
        'x-max-length': 10000,   # Limit queue length
        'x-overflow': 'drop-head',  # Drop old messages
        'x-message-ttl': 1800000,   # 30 minutes TTL
    }
    
    print("💾 Memory and disk optimization configuration")
    return memory_efficient_queue_args

# Resource optimization strategies:
# ✅ Use lazy queues for large volumes
# ✅ Set memory watermarks appropriately
# ✅ Monitor disk usage
# ✅ Configure TTL to prevent buildup
# ✅ Use message size limits
```

---

## 🔒 **Security Features**

### **1. Authentication and Authorization**

```python
def authentication_example():
    """RabbitMQ authentication methods"""
    
    # Method 1: Username/Password (default)
    basic_auth_params = pika.ConnectionParameters(
        host='rabbitmq.example.com',
        port=5672,
        virtual_host='/',
        credentials=pika.PlainCredentials('username', 'password'),
        ssl_options=pika.SSLOptions(context=None, server_hostname=None)
    )
    
    # Method 2: X.509 Certificate Authentication
    import ssl
    
    ssl_context = ssl.create_default_context(cafile='ca_certificate.pem')
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    ssl_context.load_cert_chain('client_certificate.pem', 'client_key.pem')
    
    cert_auth_params = pika.ConnectionParameters(
        host='rabbitmq.example.com',
        port=5671,  # TLS port
        virtual_host='/',
        ssl_options=pika.SSLOptions(ssl_context, 'rabbitmq.example.com')
    )
    
    # Method 3: OAuth 2.0 / JWT (with plugin)
    # Requires rabbitmq-auth-backend-oauth2 plugin
    oauth_headers = {
        'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
    }
    
    print("🔐 Multiple authentication methods available")

def authorization_example():
    """User permissions and access control"""
    
    # RabbitMQ permission model: configure, write, read
    # configure: create/delete queues and exchanges
    # write: publish messages  
    # read: consume messages
    
    permission_examples = {
        'admin_user': {
            'configure': '.*',  # All resources
            'write': '.*',      # All resources
            'read': '.*'        # All resources
        },
        'publisher_service': {
            'configure': '',        # No creation rights
            'write': '^orders\.',   # Can publish to orders.* exchanges
            'read': ''              # No consumption rights
        },
        'consumer_service': {
            'configure': '^temp\.',  # Can create temp queues
            'write': '',             # No publishing rights
            'read': '^orders\.'      # Can consume from orders.* queues
        },
        'monitoring_service': {
            'configure': '',    # No creation rights
            'write': '',        # No publishing rights
            'read': '.*'        # Can read from all queues (monitoring)
        }
    }
    
    # Commands to set permissions (run via rabbitmqctl):
    # rabbitmqctl set_permissions -p / publisher_service "" "^orders\\." ""
    # rabbitmqctl set_permissions -p / consumer_service "^temp\\." "" "^orders\\."
    
    print("👮 User permissions define fine-grained access control")
```

### **2. TLS/SSL Configuration**

```python
def tls_ssl_example():
    """TLS/SSL secure connections"""
    
    import ssl
    
    # Client-side TLS configuration
    def create_secure_connection():
        """Create TLS-secured connection"""
        
        # Create SSL context
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False  # Disable hostname verification for testing
        
        # For production: verify certificates
        # ssl_context.check_hostname = True
        # ssl_context.verify_mode = ssl.CERT_REQUIRED
        # ssl_context.load_verify_locations('ca_bundle.pem')
        
        # Client certificate (if required by server)
        # ssl_context.load_cert_chain('client.pem', 'client.key')
        
        connection_params = pika.ConnectionParameters(
            host='rabbitmq.example.com',
            port=5671,  # Standard TLS port
            virtual_host='/',
            credentials=pika.PlainCredentials('username', 'password'),
            ssl_options=pika.SSLOptions(ssl_context, 'rabbitmq.example.com')
        )
        
        try:
            connection = pika.BlockingConnection(connection_params)
            print("🔒 Secure TLS connection established")
            return connection
        except Exception as e:
            print(f"❌ TLS connection failed: {e}")
            return None
    
    # TLS configuration for different security levels
    security_levels = {
        'development': {
            'verify_mode': ssl.CERT_NONE,
            'check_hostname': False,
            'description': 'No certificate verification'
        },
        'staging': {
            'verify_mode': ssl.CERT_OPTIONAL,
            'check_hostname': False,
            'description': 'Optional certificate verification'
        },
        'production': {
            'verify_mode': ssl.CERT_REQUIRED,
            'check_hostname': True,
            'description': 'Full certificate verification'
        }
    }
    
    print("🛡️ TLS provides encryption and authentication")
    return create_secure_connection

# TLS Best practices:
# ✅ Use TLS 1.2 or higher
# ✅ Verify certificates in production
# ✅ Use strong cipher suites
# ✅ Rotate certificates regularly
# ✅ Monitor certificate expiration
```

### **3. Message Encryption**

```python
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

def message_encryption_example():
    """End-to-end message encryption"""
    
    class EncryptedMessageHandler:
        """Handle encrypted message publishing and consuming"""
        
        def __init__(self, password: str):
            """Initialize with encryption key derived from password"""
            
            # Generate salt
            salt = os.urandom(16)
            
            # Derive key from password
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
            
            # Create cipher
            self.cipher = Fernet(key)
            self.salt = salt
        
        def encrypt_message(self, message_data: dict) -> bytes:
            """Encrypt message data"""
            
            # Serialize message
            message_json = json.dumps(message_data)
            
            # Encrypt
            encrypted_data = self.cipher.encrypt(message_json.encode())
            
            return encrypted_data
        
        def decrypt_message(self, encrypted_data: bytes) -> dict:
            """Decrypt message data"""
            
            # Decrypt
            decrypted_data = self.cipher.decrypt(encrypted_data)
            
            # Deserialize
            message_data = json.loads(decrypted_data.decode())
            
            return message_data
        
        def publish_encrypted(self, channel, exchange, routing_key, message_data):
            """Publish encrypted message"""
            
            encrypted_data = self.encrypt_message(message_data)
            
            channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=encrypted_data,
                properties=pika.BasicProperties(
                    content_type='application/octet-stream',  # Binary data
                    headers={
                        'encrypted': True,
                        'encryption_method': 'fernet'
                    }
                )
            )
        
        def consume_encrypted(self, channel, method, properties, body):
            """Consume and decrypt message"""
            
            try:
                # Check if message is encrypted
                if properties.headers and properties.headers.get('encrypted'):
                    message_data = self.decrypt_message(body)
                else:
                    # Fallback to unencrypted
                    message_data = json.loads(body)
                
                print(f"🔓 Decrypted message: {message_data}")
                
                # Process decrypted message
                self.process_message(message_data)
                
                channel.basic_ack(delivery_tag=method.delivery_tag)
                
            except Exception as e:
                print(f"❌ Decryption failed: {e}")
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        def process_message(self, message_data):
            """Process decrypted message"""
            # Application logic here
            pass
    
    # Usage example
    def encryption_demo():
        with RabbitMQConnection() as rmq:
            channel = rmq.channel
            
            # Setup encryption handler
            encryption_key = "your-secure-password-here"
            handler = EncryptedMessageHandler(encryption_key)
            
            # Declare queue
            channel.queue_declare(queue='encrypted_messages', durable=True)
            
            # Publish encrypted message
            sensitive_data = {
                'customer_id': 'CUST-12345',
                'credit_card': '4111-1111-1111-1111',
                'amount': 299.99,
                'personal_info': {
                    'ssn': '123-45-6789',
                    'email': 'customer@example.com'
                }
            }
            
            handler.publish_encrypted(
                channel, '', 'encrypted_messages', sensitive_data
            )
            
            print("🔒 Published encrypted message")
            
            # Setup consumer
            channel.basic_consume(
                queue='encrypted_messages',
                on_message_callback=handler.consume_encrypted,
                auto_ack=False
            )
    
    return encryption_demo

# Encryption considerations:
# ✅ Use strong encryption algorithms
# ✅ Secure key management
# ✅ Key rotation policies
# ✅ Performance impact assessment
# ❌ Don't store keys in code
# ❌ Don't use weak encryption
```

### **4. Network Security**

```python
def network_security_example():
    """Network-level security configuration"""
    
    # Firewall rules for RabbitMQ
    firewall_rules = {
        'rabbitmq_amqp': {
            'port': 5672,
            'protocol': 'TCP',
            'source': 'application_subnet',
            'description': 'AMQP protocol'
        },
        'rabbitmq_amqps': {
            'port': 5671, 
            'protocol': 'TCP',
            'source': 'application_subnet',
            'description': 'AMQP over TLS'
        },
        'rabbitmq_management': {
            'port': 15672,
            'protocol': 'TCP', 
            'source': 'admin_subnet',
            'description': 'Management UI (restrict access)'
        },
        'rabbitmq_prometheus': {
            'port': 15692,
            'protocol': 'TCP',
            'source': 'monitoring_subnet',
            'description': 'Prometheus metrics'
        },
        'epmd': {
            'port': 4369,
            'protocol': 'TCP',
            'source': 'cluster_subnet',
            'description': 'Erlang Port Mapper Daemon'
        },
        'cluster_communication': {
            'port_range': '25672-25682',
            'protocol': 'TCP',
            'source': 'cluster_subnet',
            'description': 'Inter-node communication'
        }
    }
    
    # VPC/Network segmentation
    network_segments = {
        'dmz': {
            'components': ['load_balancer', 'reverse_proxy'],
            'access': 'internet'
        },
        'application_tier': {
            'components': ['app_servers', 'rabbitmq_clients'],
            'access': 'dmz_only'
        },
        'message_tier': {
            'components': ['rabbitmq_cluster'],
            'access': 'application_tier_only'
        },
        'data_tier': {
            'components': ['databases', 'persistent_storage'],
            'access': 'message_tier_only'
        }
    }
    
    # Connection security recommendations
    security_recommendations = [
        "Use TLS for all client connections",
        "Restrict management interface access",
        "Implement network segmentation",
        "Use VPN for remote access",
        "Enable connection rate limiting",
        "Monitor unusual connection patterns",
        "Implement IP allowlisting",
        "Use proper firewall rules"
    ]
    
    print("🌐 Network security is multi-layered")
    return firewall_rules, network_segments, security_recommendations

# Network security best practices:
# ✅ Use TLS for all connections
# ✅ Restrict management access
# ✅ Implement network segmentation
# ✅ Monitor connection patterns
# ✅ Use VPNs for remote access
# ✅ Regular security audits
```

---

## 🚀 **Production Deployment & Infrastructure**

### **1. Docker Deployment**

#### **Basic Docker Setup**

```yaml
# docker-compose.yml
version: '3.8'

services:
  rabbitmq:
    image: rabbitmq:3.12-management
    container_name: rabbitmq
    hostname: rabbitmq-server
    ports:
      - "5672:5672"    # AMQP port
      - "15672:15672"  # Management UI
      - "15692:15692"  # Prometheus metrics
    environment:
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
      RABBITMQ_DEFAULT_VHOST: /
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
      - ./rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
      - ./definitions.json:/etc/rabbitmq/definitions.json:ro
      - ./enabled_plugins:/etc/rabbitmq/enabled_plugins:ro
    networks:
      - rabbitmq_network
    restart: unless-stopped
    healthcheck:
      test: rabbitmq-diagnostics check_port_connectivity
      interval: 30s
      timeout: 30s
      retries: 3

volumes:
  rabbitmq_data:
    driver: local

networks:
  rabbitmq_network:
    driver: bridge
```

#### **Production Docker Configuration**

```bash
# rabbitmq.conf
# Cluster configuration
cluster_formation.peer_discovery_backend = classic_config
cluster_formation.classic_config.nodes.1 = rabbit@rabbitmq-1
cluster_formation.classic_config.nodes.2 = rabbit@rabbitmq-2
cluster_formation.classic_config.nodes.3 = rabbit@rabbitmq-3

# Memory and disk settings
vm_memory_high_watermark.relative = 0.6
disk_free_limit.absolute = 2GB

# Network settings
listeners.tcp.default = 5672
management.tcp.port = 15672

# Security settings
auth_backends.1 = rabbit_auth_backend_ldap
auth_backends.2 = rabbit_auth_backend_internal

# SSL/TLS settings
listeners.ssl.default = 5671
ssl_options.cacertfile = /etc/ssl/certs/ca-cert.pem
ssl_options.certfile = /etc/ssl/certs/server-cert.pem
ssl_options.keyfile = /etc/ssl/private/server-key.pem
ssl_options.verify = verify_peer
ssl_options.fail_if_no_peer_cert = true

# Logging
log.file.level = info
log.console = true
log.console.level = info

# Plugins
enabled_plugins = [rabbitmq_management,
                  rabbitmq_prometheus,
                  rabbitmq_shovel,
                  rabbitmq_federation]
```

#### **Docker Cluster Setup**

```yaml
# docker-compose-cluster.yml
version: '3.8'

services:
  rabbitmq-1:
    image: rabbitmq:3.12-management
    hostname: rabbitmq-1
    environment:
      RABBITMQ_ERLANG_COOKIE: 'your-secret-cookie'
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
      RABBITMQ_NODENAME: rabbit@rabbitmq-1
    volumes:
      - rabbitmq1_data:/var/lib/rabbitmq
      - ./rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
    networks:
      - rabbitmq_cluster
    ports:
      - "5672:5672"
      - "15672:15672"

  rabbitmq-2:
    image: rabbitmq:3.12-management
    hostname: rabbitmq-2
    environment:
      RABBITMQ_ERLANG_COOKIE: 'your-secret-cookie'
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
      RABBITMQ_NODENAME: rabbit@rabbitmq-2
    volumes:
      - rabbitmq2_data:/var/lib/rabbitmq
      - ./rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
    networks:
      - rabbitmq_cluster
    depends_on:
      - rabbitmq-1

  rabbitmq-3:
    image: rabbitmq:3.12-management
    hostname: rabbitmq-3
    environment:
      RABBITMQ_ERLANG_COOKIE: 'your-secret-cookie'
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
      RABBITMQ_NODENAME: rabbit@rabbitmq-3
    volumes:
      - rabbitmq3_data:/var/lib/rabbitmq
      - ./rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
    networks:
      - rabbitmq_cluster
    depends_on:
      - rabbitmq-1

  haproxy:
    image: haproxy:2.8
    ports:
      - "5673:5673"    # Load balanced AMQP
      - "15673:15673"  # Load balanced Management
    volumes:
      - ./haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro
    networks:
      - rabbitmq_cluster
    depends_on:
      - rabbitmq-1
      - rabbitmq-2
      - rabbitmq-3

volumes:
  rabbitmq1_data:
  rabbitmq2_data:
  rabbitmq3_data:

networks:
  rabbitmq_cluster:
    driver: bridge
```

#### **HAProxy Load Balancer Configuration**

```bash
# haproxy.cfg
global
    daemon
    log stdout local0 info

defaults
    mode tcp
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms
    log global

# AMQP Load Balancing
listen rabbitmq_amqp
    bind *:5673
    mode tcp
    balance roundrobin
    option tcplog
    server rabbit1 rabbitmq-1:5672 check
    server rabbit2 rabbitmq-2:5672 check
    server rabbit3 rabbitmq-3:5672 check

# Management UI Load Balancing
listen rabbitmq_management
    bind *:15673
    mode http
    balance roundrobin
    option httplog
    server rabbit1 rabbitmq-1:15672 check
    server rabbit2 rabbitmq-2:15672 check
    server rabbit3 rabbitmq-3:15672 check

# Health check endpoint
listen stats
    bind *:8404
    stats enable
    stats uri /stats
    stats refresh 30s
    stats admin if TRUE
```

### **2. Kubernetes Deployment**

#### **Kubernetes Manifests**

```yaml
# rabbitmq-namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: rabbitmq

---
# rabbitmq-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rabbitmq-config
  namespace: rabbitmq
data:
  rabbitmq.conf: |
    cluster_formation.peer_discovery_backend = k8s
    cluster_formation.k8s.host = kubernetes.default.svc.cluster.local
    cluster_formation.k8s.address_type = hostname
    cluster_formation.k8s.service_name = rabbitmq-headless
    cluster_formation.k8s.hostname_suffix = .rabbitmq-headless.rabbitmq.svc.cluster.local
    cluster_partition_handling = pause_minority
    queue_master_locator = min-masters
    
    vm_memory_high_watermark.relative = 0.6
    disk_free_limit.absolute = 2GB
    
    management.tcp.port = 15672
    prometheus.tcp.port = 15692

  enabled_plugins: |
    [rabbitmq_management,
     rabbitmq_peer_discovery_k8s,
     rabbitmq_prometheus].

---
# rabbitmq-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: rabbitmq-secret
  namespace: rabbitmq
type: Opaque
data:
  erlang-cookie: eW91ci1zZWNyZXQtY29va2ll  # base64 encoded
  username: YWRtaW4=                        # base64 encoded 'admin'
  password: cGFzc3dvcmQ=                    # base64 encoded 'password'

---
# rabbitmq-rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: rabbitmq
  namespace: rabbitmq

---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: rabbitmq-peer-discovery
  namespace: rabbitmq
rules:
- apiGroups: [""]
  resources: ["endpoints"]
  verbs: ["get"]
- apiGroups: [""]
  resources: ["events"]
  verbs: ["create"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: rabbitmq-peer-discovery
  namespace: rabbitmq
subjects:
- kind: ServiceAccount
  name: rabbitmq
  namespace: rabbitmq
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: rabbitmq-peer-discovery

---
# rabbitmq-services.yaml
apiVersion: v1
kind: Service
metadata:
  name: rabbitmq-headless
  namespace: rabbitmq
spec:
  clusterIP: None
  selector:
    app: rabbitmq
  ports:
  - name: amqp
    port: 5672
    targetPort: 5672
  - name: management
    port: 15672
    targetPort: 15672

---
apiVersion: v1
kind: Service
metadata:
  name: rabbitmq-management
  namespace: rabbitmq
spec:
  selector:
    app: rabbitmq
  type: LoadBalancer
  ports:
  - name: management
    port: 15672
    targetPort: 15672

---
apiVersion: v1
kind: Service
metadata:
  name: rabbitmq-amqp
  namespace: rabbitmq
spec:
  selector:
    app: rabbitmq
  type: LoadBalancer
  ports:
  - name: amqp
    port: 5672
    targetPort: 5672

---
# rabbitmq-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: rabbitmq
  namespace: rabbitmq
spec:
  serviceName: rabbitmq-headless
  replicas: 3
  selector:
    matchLabels:
      app: rabbitmq
  template:
    metadata:
      labels:
        app: rabbitmq
    spec:
      serviceAccountName: rabbitmq
      containers:
      - name: rabbitmq
        image: rabbitmq:3.12-management
        ports:
        - containerPort: 5672
          name: amqp
        - containerPort: 15672
          name: management
        - containerPort: 15692
          name: prometheus
        env:
        - name: RABBITMQ_DEFAULT_USER
          valueFrom:
            secretKeyRef:
              name: rabbitmq-secret
              key: username
        - name: RABBITMQ_DEFAULT_PASS
          valueFrom:
            secretKeyRef:
              name: rabbitmq-secret
              key: password
        - name: RABBITMQ_ERLANG_COOKIE
          valueFrom:
            secretKeyRef:
              name: rabbitmq-secret
              key: erlang-cookie
        - name: K8S_SERVICE_NAME
          value: rabbitmq-headless
        - name: POD_IP
          valueFrom:
            fieldRef:
              fieldPath: status.podIP
        - name: POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: POD_NAMESPACE
          valueFrom:
            fieldRef:
              fieldPath: metadata.namespace
        - name: RABBITMQ_USE_LONGNAME
          value: "true"
        - name: RABBITMQ_NODENAME
          value: "rabbit@$(POD_NAME).rabbitmq-headless.$(POD_NAMESPACE).svc.cluster.local"
        resources:
          requests:
            memory: 1Gi
            cpu: 500m
          limits:
            memory: 2Gi
            cpu: 1000m
        volumeMounts:
        - name: rabbitmq-data
          mountPath: /var/lib/rabbitmq
        - name: rabbitmq-config
          mountPath: /etc/rabbitmq
          readOnly: true
        livenessProbe:
          exec:
            command: ["rabbitmq-diagnostics", "ping"]
          initialDelaySeconds: 60
          periodSeconds: 60
          timeoutSeconds: 15
        readinessProbe:
          exec:
            command: ["rabbitmq-diagnostics", "check_port_connectivity"]
          initialDelaySeconds: 20
          periodSeconds: 60
          timeoutSeconds: 10
      volumes:
      - name: rabbitmq-config
        configMap:
          name: rabbitmq-config
          items:
          - key: rabbitmq.conf
            path: rabbitmq.conf
          - key: enabled_plugins
            path: enabled_plugins
  volumeClaimTemplates:
  - metadata:
      name: rabbitmq-data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      storageClassName: "fast-ssd"
      resources:
        requests:
          storage: 10Gi
```

#### **Helm Chart Deployment**

```yaml
# values.yaml for RabbitMQ Helm Chart
replicaCount: 3

auth:
  username: admin
  password: "secure-password"
  erlangCookie: "your-secret-erlang-cookie"

clustering:
  enabled: true
  addressType: hostname
  rebalance: true

persistence:
  enabled: true
  storageClass: "fast-ssd"
  size: 10Gi

resources:
  limits:
    cpu: 1000m
    memory: 2Gi
  requests:
    cpu: 500m
    memory: 1Gi

service:
  type: LoadBalancer
  port: 5672
  managerPort: 15672

metrics:
  enabled: true
  serviceMonitor:
    enabled: true

extraConfiguration: |
  vm_memory_high_watermark.relative = 0.6
  disk_free_limit.absolute = 2GB
  cluster_partition_handling = pause_minority
  queue_master_locator = min-masters

loadDefinition:
  enabled: true
  secretName: rabbitmq-load-definition

memoryHighWatermark:
  enabled: true
  type: relative
  value: 0.6
```

#### **Deploy with Helm**

```bash
# Add Bitnami Helm repository
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Deploy RabbitMQ cluster
helm install my-rabbitmq bitnami/rabbitmq \
  --namespace rabbitmq \
  --create-namespace \
  --values values.yaml

# Get connection info
kubectl get secret --namespace rabbitmq my-rabbitmq -o jsonpath="{.data.rabbitmq-password}" | base64 --decode
kubectl get svc --namespace rabbitmq
```

### **3. Cloud Provider Deployments**

#### **AWS EKS Deployment**

```bash
#!/bin/bash
# deploy-rabbitmq-eks.sh

# Create EKS cluster
eksctl create cluster \
  --name rabbitmq-cluster \
  --region us-west-2 \
  --nodes 3 \
  --nodes-min 3 \
  --nodes-max 6 \
  --node-type m5.large \
  --with-oidc \
  --ssh-access \
  --ssh-public-key ~/.ssh/id_rsa.pub

# Install EBS CSI driver for persistent volumes
kubectl apply -k "github.com/kubernetes-sigs/aws-ebs-csi-driver/deploy/kubernetes/overlays/stable/?ref=master"

# Create storage class for EBS
cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: rabbitmq-storage
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
allowVolumeExpansion: true
volumeBindingMode: WaitForFirstConsumer
EOF

# Deploy RabbitMQ with Helm
helm install rabbitmq bitnami/rabbitmq \
  --namespace rabbitmq \
  --create-namespace \
  --set persistence.storageClass=rabbitmq-storage \
  --set service.type=LoadBalancer \
  --set service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-type"="nlb"
```

#### **Azure AKS Deployment**

```bash
#!/bin/bash
# deploy-rabbitmq-aks.sh

# Create resource group
az group create --name rabbitmq-rg --location eastus

# Create AKS cluster
az aks create \
  --resource-group rabbitmq-rg \
  --name rabbitmq-cluster \
  --node-count 3 \
  --enable-addons monitoring \
  --generate-ssh-keys

# Get credentials
az aks get-credentials --resource-group rabbitmq-rg --name rabbitmq-cluster

# Create storage class for Azure Disk
cat <<EOF | kubectl apply -f -
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: rabbitmq-storage
provisioner: disk.csi.azure.com
parameters:
  skuName: Premium_LRS
allowVolumeExpansion: true
volumeBindingMode: WaitForFirstConsumer
EOF

# Deploy RabbitMQ
helm install rabbitmq bitnami/rabbitmq \
  --namespace rabbitmq \
  --create-namespace \
  --set persistence.storageClass=rabbitmq-storage
```

### **4. Production Environment Setup**

#### **Environment Configuration Management**

```bash
# environments/production/rabbitmq.conf
cluster_formation.peer_discovery_backend = classic_config
cluster_formation.classic_config.nodes.1 = rabbit@rabbitmq-prod-1
cluster_formation.classic_config.nodes.2 = rabbit@rabbitmq-prod-2
cluster_formation.classic_config.nodes.3 = rabbit@rabbitmq-prod-3

vm_memory_high_watermark.relative = 0.6
disk_free_limit.absolute = 5GB

listeners.tcp.default = 5672
listeners.ssl.default = 5671

ssl_options.cacertfile = /etc/ssl/certs/ca-cert.pem
ssl_options.certfile = /etc/ssl/certs/server-cert.pem
ssl_options.keyfile = /etc/ssl/private/server-key.pem
ssl_options.verify = verify_peer
ssl_options.fail_if_no_peer_cert = true

management.tcp.port = 15672
management.ssl.port = 15671

log.file.level = warning
log.console = false

# environments/staging/rabbitmq.conf
vm_memory_high_watermark.relative = 0.7
disk_free_limit.absolute = 1GB
log.file.level = info

# environments/development/rabbitmq.conf
vm_memory_high_watermark.relative = 0.8
disk_free_limit.absolute = 500MB
log.file.level = debug
log.console = true
```

#### **CI/CD Pipeline Configuration**

```yaml
# .github/workflows/deploy-rabbitmq.yml
name: Deploy RabbitMQ

on:
  push:
    branches: [main]
    paths: ['rabbitmq/**']

jobs:
  deploy:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        environment: [staging, production]
    
    environment: ${{ matrix.environment }}
    
    steps:
    - name: Checkout
      uses: actions/checkout@v3
    
    - name: Configure kubectl
      uses: azure/k8s-set-context@v3
      with:
        method: kubeconfig
        kubeconfig: ${{ secrets.KUBECONFIG }}
    
    - name: Deploy RabbitMQ
      run: |
        envsubst < rabbitmq/k8s/rabbitmq-${{ matrix.environment }}.yaml | kubectl apply -f -
        
    - name: Wait for deployment
      run: |
        kubectl rollout status statefulset/rabbitmq -n rabbitmq-${{ matrix.environment }}
        
    - name: Run health checks
      run: |
        kubectl exec -n rabbitmq-${{ matrix.environment }} rabbitmq-0 -- rabbitmq-diagnostics check_port_connectivity
        kubectl exec -n rabbitmq-${{ matrix.environment }} rabbitmq-0 -- rabbitmq-diagnostics node_health_check

    - name: Load definitions
      if: matrix.environment == 'production'
      run: |
        kubectl exec -n rabbitmq-production rabbitmq-0 -- rabbitmqctl import_definitions /etc/rabbitmq/definitions.json
```

### **5. Monitoring & Observability Setup**

#### **Prometheus Monitoring**

```yaml
# rabbitmq-servicemonitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: rabbitmq-metrics
  namespace: rabbitmq
spec:
  selector:
    matchLabels:
      app: rabbitmq
  endpoints:
  - port: prometheus
    interval: 30s
    path: /metrics

---
# rabbitmq-prometheusrule.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: rabbitmq-alerts
  namespace: rabbitmq
spec:
  groups:
  - name: rabbitmq
    rules:
    - alert: RabbitMQHighQueueDepth
      expr: rabbitmq_queue_messages > 10000
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "RabbitMQ queue depth is high"
        description: "Queue {{ $labels.queue }} has {{ $value }} messages"
    
    - alert: RabbitMQNodeDown
      expr: up{job="rabbitmq"} == 0
      for: 2m
      labels:
        severity: critical
      annotations:
        summary: "RabbitMQ node is down"
        description: "RabbitMQ node {{ $labels.instance }} is down"
    
    - alert: RabbitMQHighMemoryUsage
      expr: rabbitmq_process_resident_memory_bytes / rabbitmq_vm_memory_limit_bytes > 0.8
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "RabbitMQ high memory usage"
        description: "RabbitMQ memory usage is {{ $value | humanizePercentage }}"
```

#### **Grafana Dashboard**

```json
{
  "dashboard": {
    "title": "RabbitMQ Monitoring",
    "panels": [
      {
        "title": "Message Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "sum(rate(rabbitmq_queue_messages_published_total[5m])) by (instance)"
          }
        ]
      },
      {
        "title": "Queue Depths",
        "type": "graph",
        "targets": [
          {
            "expr": "rabbitmq_queue_messages"
          }
        ]
      },
      {
        "title": "Memory Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "rabbitmq_process_resident_memory_bytes"
          }
        ]
      }
    ]
  }
}
```

### **6. Backup and Disaster Recovery**

#### **Backup Strategy**

```bash
#!/bin/bash
# backup-rabbitmq.sh

BACKUP_DIR="/opt/rabbitmq-backups/$(date +%Y%m%d)"
RETENTION_DAYS=7

# Create backup directory
mkdir -p $BACKUP_DIR

# Export definitions
rabbitmqadmin export $BACKUP_DIR/definitions.json

# Backup node data (if using shared storage)
# rsync -av /var/lib/rabbitmq/ $BACKUP_DIR/data/

# Create compressed archive
tar -czf $BACKUP_DIR/rabbitmq-backup-$(date +%Y%m%d-%H%M%S).tar.gz \
    $BACKUP_DIR/definitions.json

# Cleanup old backups
find /opt/rabbitmq-backups -name "rabbitmq-backup-*.tar.gz" -mtime +$RETENTION_DAYS -delete

# Upload to cloud storage (optional)
# aws s3 cp $BACKUP_DIR/rabbitmq-backup-*.tar.gz s3://your-backup-bucket/rabbitmq/
```

#### **Disaster Recovery Plan**

```bash
#!/bin/bash
# disaster-recovery.sh

# 1. Restore RabbitMQ cluster
kubectl apply -f k8s/rabbitmq-cluster.yaml

# 2. Wait for cluster to be ready
kubectl wait --for=condition=ready pod -l app=rabbitmq --timeout=300s

# 3. Restore definitions
kubectl cp definitions.json rabbitmq-0:/tmp/definitions.json
kubectl exec rabbitmq-0 -- rabbitmqctl import_definitions /tmp/definitions.json

# 4. Verify cluster health
kubectl exec rabbitmq-0 -- rabbitmqctl cluster_status
kubectl exec rabbitmq-0 -- rabbitmqctl node_health_check

echo "Disaster recovery completed"
```

This comprehensive deployment section covers Docker, Kubernetes, cloud deployments, CI/CD, monitoring, and disaster recovery - everything needed for production RabbitMQ deployments.

---

## 💻 **Practical Implementation Examples**

### **1. E-commerce Order Processing System**

```python
def ecommerce_order_system():
    """Complete e-commerce order processing with RabbitMQ"""
    
    class OrderProcessingSystem:
        def __init__(self):
            self.connection = None
            self.channel = None
            self.setup_infrastructure()
        
        def setup_infrastructure(self):
            """Setup exchanges, queues, and bindings"""
            
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters('localhost')
            )
            self.channel = self.connection.channel()
            
            # Declare exchanges
            exchanges = [
                ('orders', 'topic'),
                ('inventory', 'direct'),
                ('payments', 'direct'),
                ('notifications', 'fanout')
            ]
            
            for exchange_name, exchange_type in exchanges:
                self.channel.exchange_declare(
                    exchange=exchange_name,
                    exchange_type=exchange_type,
                    durable=True
                )
            
            # Declare queues with DLX
            queues = [
                'order_processing',
                'inventory_updates', 
                'payment_processing',
                'email_notifications',
                'sms_notifications',
                'order_status_updates'
            ]
            
            for queue in queues:
                self.channel.queue_declare(
                    queue=queue,
                    durable=True,
                    arguments={
                        'x-dead-letter-exchange': f'{queue}_dlx',
                        'x-dead-letter-routing-key': 'failed'
                    }
                )
                
                # Create DLX and DLQ
                self.channel.exchange_declare(
                    exchange=f'{queue}_dlx',
                    exchange_type='direct'
                )
                self.channel.queue_declare(queue=f'{queue}_dlq', durable=True)
                self.channel.queue_bind(
                    exchange=f'{queue}_dlx',
                    queue=f'{queue}_dlq',
                    routing_key='failed'
                )
            
            # Setup bindings
            bindings = [
                ('orders', 'order_processing', 'order.created'),
                ('orders', 'inventory_updates', 'order.*'),
                ('inventory', 'order_processing', 'inventory.reserved'),
                ('payments', 'order_processing', 'payment.completed'),
                ('notifications', 'email_notifications', ''),
                ('notifications', 'sms_notifications', ''),
            ]
            
            for exchange, queue, routing_key in bindings:
                self.channel.queue_bind(
                    exchange=exchange,
                    queue=queue,
                    routing_key=routing_key
                )
        
        def create_order(self, order_data):
            """Process new order creation"""
            
            order_event = {
                'event_type': 'order_created',
                'order_id': order_data['order_id'],
                'customer_id': order_data['customer_id'],
                'items': order_data['items'],
                'total_amount': order_data['total_amount'],
                'timestamp': time.time()
            }
            
            # Publish order created event
            self.channel.basic_publish(
                exchange='orders',
                routing_key='order.created',
                body=json.dumps(order_event),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    correlation_id=order_data['order_id']
                )
            )
            
            print(f"📦 Created order: {order_data['order_id']}")
        
        def process_inventory_check(self, ch, method, properties, body):
            """Process inventory check for order"""
            
            order_event = json.loads(body)
            
            # Simulate inventory check
            all_available = True
            for item in order_event['items']:
                # Check inventory (simulated)
                available_quantity = self.check_inventory(item['sku'])
                if available_quantity < item['quantity']:
                    all_available = False
                    break
            
            if all_available:
                # Reserve inventory
                for item in order_event['items']:
                    self.reserve_inventory(item['sku'], item['quantity'])
                
                # Publish inventory reserved event
                inventory_event = {
                    'event_type': 'inventory_reserved',
                    'order_id': order_event['order_id'],
                    'items': order_event['items'],
                    'timestamp': time.time()
                }
                
                self.channel.basic_publish(
                    exchange='inventory',
                    routing_key='inventory.reserved',
                    body=json.dumps(inventory_event),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        correlation_id=order_event['order_id']
                    )
                )
                
                print(f"✅ Inventory reserved for order: {order_event['order_id']}")
            else:
                # Insufficient inventory
                self.handle_insufficient_inventory(order_event)
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
        
        def process_payment(self, ch, method, properties, body):
            """Process payment for order"""
            
            inventory_event = json.loads(body)
            
            # Simulate payment processing
            payment_successful = self.process_payment_gateway(
                inventory_event['order_id'],
                sum(item['price'] * item['quantity'] for item in inventory_event['items'])
            )
            
            if payment_successful:
                payment_event = {
                    'event_type': 'payment_completed',
                    'order_id': inventory_event['order_id'],
                    'amount': sum(item['price'] * item['quantity'] for item in inventory_event['items']),
                    'timestamp': time.time()
                }
                
                self.channel.basic_publish(
                    exchange='payments',
                    routing_key='payment.completed',
                    body=json.dumps(payment_event),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        correlation_id=inventory_event['order_id']
                    )
                )
                
                print(f"💳 Payment processed for order: {inventory_event['order_id']}")
                
                # Send notifications
                self.send_order_confirmation(inventory_event['order_id'])
            else:
                # Payment failed - release inventory
                self.handle_payment_failure(inventory_event)
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
        
        def send_order_confirmation(self, order_id):
            """Send order confirmation notifications"""
            
            notification_event = {
                'event_type': 'order_confirmed',
                'order_id': order_id,
                'message': f'Your order {order_id} has been confirmed!',
                'timestamp': time.time()
            }
            
            # Broadcast to all notification services
            self.channel.basic_publish(
                exchange='notifications',
                routing_key='',
                body=json.dumps(notification_event),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            
            print(f"📧 Sent confirmation for order: {order_id}")
        
        def start_consumers(self):
            """Start all consumer processes"""
            
            # Setup consumers
            consumers = [
                ('order_processing', self.process_inventory_check),
                ('inventory_updates', self.process_payment),
                ('email_notifications', self.send_email_notification),
                ('sms_notifications', self.send_sms_notification)
            ]
            
            for queue, callback in consumers:
                self.channel.basic_qos(prefetch_count=10)
                self.channel.basic_consume(
                    queue=queue,
                    on_message_callback=callback,
                    auto_ack=False
                )
            
            print("🚀 Started all consumers")
            self.channel.start_consuming()
        
        # Helper methods (simplified implementations)
        def check_inventory(self, sku):
            return 100  # Simulate available quantity
        
        def reserve_inventory(self, sku, quantity):
            pass  # Simulate inventory reservation
        
        def process_payment_gateway(self, order_id, amount):
            return True  # Simulate successful payment
        
        def handle_insufficient_inventory(self, order_event):
            print(f"❌ Insufficient inventory for order: {order_event['order_id']}")
        
        def handle_payment_failure(self, inventory_event):
            print(f"❌ Payment failed for order: {inventory_event['order_id']}")
        
        def send_email_notification(self, ch, method, properties, body):
            event = json.loads(body)
            print(f"📧 Email: {event['message']}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        
        def send_sms_notification(self, ch, method, properties, body):
            event = json.loads(body)
            print(f"📱 SMS: {event['message']}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
    
    return OrderProcessingSystem

# Usage example:
# system = ecommerce_order_system()()
# system.create_order({
#     'order_id': 'ORD-001',
#     'customer_id': 'CUST-123', 
#     'items': [{'sku': 'ITEM-001', 'quantity': 2, 'price': 29.99}],
#     'total_amount': 59.98
# })
# system.start_consumers()
```

### **2. Microservices Communication Pattern**

```python
def microservices_communication():
    """RabbitMQ for microservices communication"""
    
    class MicroserviceBase:
        """Base class for microservices using RabbitMQ"""
        
        def __init__(self, service_name):
            self.service_name = service_name
            self.connection = None
            self.channel = None
            self.setup_connection()
            self.setup_service_infrastructure()
        
        def setup_connection(self):
            """Setup RabbitMQ connection"""
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters('localhost')
            )
            self.channel = self.connection.channel()
            self.channel.confirm_delivery()
        
        def setup_service_infrastructure(self):
            """Setup service-specific exchanges and queues"""
            
            # Service command queue (direct commands to this service)
            self.command_queue = f"{self.service_name}_commands"
            self.channel.queue_declare(queue=self.command_queue, durable=True)
            
            # Service event exchange (events from this service)
            self.event_exchange = f"{self.service_name}_events"
            self.channel.exchange_declare(
                exchange=self.event_exchange,
                exchange_type='topic',
                durable=True
            )
            
            # Subscribe to relevant events from other services
            self.setup_event_subscriptions()
        
        def setup_event_subscriptions(self):
            """Override in subclasses to subscribe to events"""
            pass
        
        def send_command(self, target_service, command_data):
            """Send command to another service"""
            
            command_message = {
                'command_type': command_data['type'],
                'data': command_data['data'],
                'from_service': self.service_name,
                'timestamp': time.time(),
                'correlation_id': str(uuid.uuid4())
            }
            
            self.channel.basic_publish(
                exchange='',
                routing_key=f"{target_service}_commands",
                body=json.dumps(command_message),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    reply_to=f"{self.service_name}_responses"
                )
            )
        
        def publish_event(self, event_type, event_data):
            """Publish event to service exchange"""
            
            event_message = {
                'event_type': event_type,
                'data': event_data,
                'service': self.service_name,
                'timestamp': time.time(),
                'event_id': str(uuid.uuid4())
            }
            
            self.channel.basic_publish(
                exchange=self.event_exchange,
                routing_key=event_type,
                body=json.dumps(event_message),
                properties=pika.BasicProperties(delivery_mode=2)
            )
        
        def start_consuming(self):
            """Start consuming commands and events"""
            
            # Consume commands
            self.channel.basic_consume(
                queue=self.command_queue,
                on_message_callback=self.handle_command,
                auto_ack=False
            )
            
            print(f"🚀 {self.service_name} service started")
            self.channel.start_consuming()
        
        def handle_command(self, ch, method, properties, body):
            """Handle incoming commands"""
            
            try:
                command = json.loads(body)
                command_type = command['command_type']
                
                # Route to appropriate handler
                handler_name = f"handle_{command_type}"
                if hasattr(self, handler_name):
                    handler = getattr(self, handler_name)
                    handler(command)
                else:
                    print(f"❌ Unknown command type: {command_type}")
                
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
            except Exception as e:
                print(f"❌ Command processing failed: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    class UserService(MicroserviceBase):
        """User management microservice"""
        
        def __init__(self):
            super().__init__('user')
        
        def setup_event_subscriptions(self):
            """Subscribe to relevant events"""
            
            # Subscribe to order events for user analytics
            self.channel.exchange_declare(exchange='order_events', exchange_type='topic')
            result = self.channel.queue_declare(queue='', exclusive=True)
            user_analytics_queue = result.method.queue
            
            self.channel.queue_bind(
                exchange='order_events',
                queue=user_analytics_queue,
                routing_key='order.completed'
            )
            
            self.channel.basic_consume(
                queue=user_analytics_queue,
                on_message_callback=self.handle_order_completed,
                auto_ack=False
            )
        
        def handle_create_user(self, command):
            """Handle user creation command"""
            
            user_data = command['data']
            user_id = str(uuid.uuid4())
            
            # Create user (simulated)
            print(f"👤 Creating user: {user_data['email']}")
            
            # Publish user created event
            self.publish_event('user.created', {
                'user_id': user_id,
                'email': user_data['email'],
                'name': user_data['name']
            })
        
        def handle_order_completed(self, ch, method, properties, body):
            """Handle order completion for user analytics"""
            
            order_event = json.loads(body)
            customer_id = order_event['data']['customer_id']
            
            print(f"📊 Updating user analytics for customer: {customer_id}")
            
            # Update user order history, preferences, etc.
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
    
    class OrderService(MicroserviceBase):
        """Order management microservice"""
        
        def __init__(self):
            super().__init__('order')
        
        def setup_event_subscriptions(self):
            """Subscribe to user and inventory events"""
            
            # Subscribe to user events
            self.channel.exchange_declare(exchange='user_events', exchange_type='topic')
            result = self.channel.queue_declare(queue='', exclusive=True)
            user_events_queue = result.method.queue
            
            self.channel.queue_bind(
                exchange='user_events',
                queue=user_events_queue,
                routing_key='user.created'
            )
            
            self.channel.basic_consume(
                queue=user_events_queue,
                on_message_callback=self.handle_user_created,
                auto_ack=False
            )
        
        def handle_create_order(self, command):
            """Handle order creation command"""
            
            order_data = command['data']
            order_id = str(uuid.uuid4())
            
            print(f"📦 Creating order: {order_id}")
            
            # Validate order, check inventory, etc.
            
            # Publish order created event
            self.publish_event('order.created', {
                'order_id': order_id,
                'customer_id': order_data['customer_id'],
                'items': order_data['items'],
                'total': order_data['total']
            })
        
        def handle_user_created(self, ch, method, properties, body):
            """Handle new user creation"""
            
            user_event = json.loads(body)
            user_id = user_event['data']['user_id']
            
            print(f"🎁 Setting up welcome offer for new user: {user_id}")
            
            # Create welcome discount, setup user preferences, etc.
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
    
    return UserService, OrderService

# Usage example:
# UserServiceClass, OrderServiceClass = microservices_communication()
# 
# # Start services (typically in separate processes)
# user_service = UserServiceClass()
# order_service = OrderServiceClass()
# 
# # Send commands between services
# user_service.send_command('order', {
#     'type': 'create_order',
#     'data': {'customer_id': '123', 'items': [...], 'total': 99.99}
# })
```

### **3. Real-time Chat System**

```python
def realtime_chat_system():
    """Real-time chat system using RabbitMQ"""
    
    class ChatSystem:
        """WebSocket-like chat system with RabbitMQ backend"""
        
        def __init__(self):
            self.connection = None
            self.channel = None
            self.setup_infrastructure()
        
        def setup_infrastructure(self):
            """Setup chat infrastructure"""
            
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters('localhost')
            )
            self.channel = self.connection.channel()
            
            # Chat rooms exchange (topic-based routing)
            self.channel.exchange_declare(
                exchange='chat_rooms',
                exchange_type='topic',
                durable=True
            )
            
            # Direct messages exchange
            self.channel.exchange_declare(
                exchange='direct_messages',
                exchange_type='direct',
                durable=True
            )
            
            # Presence exchange (user online/offline)
            self.channel.exchange_declare(
                exchange='user_presence',
                exchange_type='fanout',
                durable=False  # Transient for real-time presence
            )
            
            # Message history (for persistence)
            self.channel.queue_declare(
                queue='message_history',
                durable=True,
                arguments={
                    'x-message-ttl': 86400000,  # 24 hours
                    'x-max-length': 100000       # Max 100k messages
                }
            )
        
        def join_room(self, user_id, room_id):
            """User joins a chat room"""
            
            # Create user-specific queue for the room
            user_room_queue = f"user_{user_id}_room_{room_id}"
            
            self.channel.queue_declare(
                queue=user_room_queue,
                durable=False,  # Temporary queue
                exclusive=True,
                auto_delete=True
            )
            
            # Bind to room messages
            self.channel.queue_bind(
                exchange='chat_rooms',
                queue=user_room_queue,
                routing_key=f"room.{room_id}"
            )
            
            # Announce user joined
            join_message = {
                'type': 'user_joined',
                'user_id': user_id,
                'room_id': room_id,
                'timestamp': time.time()
            }
            
            self.channel.basic_publish(
                exchange='chat_rooms',
                routing_key=f"room.{room_id}",
                body=json.dumps(join_message),
                properties=pika.BasicProperties(
                    delivery_mode=1  # Non-persistent for real-time
                )
            )
            
            print(f"👋 User {user_id} joined room {room_id}")
            return user_room_queue
        
        def send_message(self, user_id, room_id, message_text):
            """Send message to chat room"""
            
            message = {
                'type': 'chat_message',
                'message_id': str(uuid.uuid4()),
                'user_id': user_id,
                'room_id': room_id,
                'text': message_text,
                'timestamp': time.time()
            }
            
            # Send to room
            self.channel.basic_publish(
                exchange='chat_rooms',
                routing_key=f"room.{room_id}",
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=1)
            )
            
            # Store in history
            self.channel.basic_publish(
                exchange='',
                routing_key='message_history',
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2)  # Persistent
            )
            
            print(f"💬 Message sent to room {room_id}: {message_text[:50]}...")
        
        def send_direct_message(self, from_user_id, to_user_id, message_text):
            """Send direct message between users"""
            
            message = {
                'type': 'direct_message',
                'message_id': str(uuid.uuid4()),
                'from_user_id': from_user_id,
                'to_user_id': to_user_id,
                'text': message_text,
                'timestamp': time.time()
            }
            
            # Send to recipient's direct message queue
            self.channel.basic_publish(
                exchange='direct_messages',
                routing_key=f"user_{to_user_id}",
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=1)
            )
            
            # Store in history
            self.channel.basic_publish(
                exchange='',
                routing_key='message_history',
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            
            print(f"📩 Direct message sent from {from_user_id} to {to_user_id}")
        
        def update_user_presence(self, user_id, status):
            """Update user presence (online/offline/away)"""
            
            presence_message = {
                'type': 'presence_update',
                'user_id': user_id,
                'status': status,  # online, offline, away
                'timestamp': time.time()
            }
            
            self.channel.basic_publish(
                exchange='user_presence',
                routing_key='',
                body=json.dumps(presence_message),
                properties=pika.BasicProperties(
                    delivery_mode=1,
                    expiration='30000'  # 30 seconds expiry
                )
            )
            
            print(f"🔘 User {user_id} is now {status}")
        
        def start_user_consumer(self, user_id):
            """Start consuming messages for a user"""
            
            # Setup direct message queue
            dm_queue = f"user_{user_id}_direct"
            self.channel.queue_declare(
                queue=dm_queue,
                durable=False,
                exclusive=True,
                auto_delete=True
            )
            
            self.channel.queue_bind(
                exchange='direct_messages',
                queue=dm_queue,
                routing_key=f"user_{user_id}"
            )
            
            # Setup presence updates queue
            presence_queue = f"user_{user_id}_presence"
            result = self.channel.queue_declare(queue='', exclusive=True)
            presence_queue = result.method.queue
            
            self.channel.queue_bind(
                exchange='user_presence',
                queue=presence_queue,
                routing_key=''
            )
            
            # Consumer callback
            def message_callback(ch, method, properties, body):
                message = json.loads(body)
                self.handle_user_message(user_id, message)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            
            # Start consuming
            self.channel.basic_consume(
                queue=dm_queue,
                on_message_callback=message_callback,
                auto_ack=False
            )
            
            self.channel.basic_consume(
                queue=presence_queue,
                on_message_callback=message_callback,
                auto_ack=False
            )
            
            print(f"👂 Started consuming messages for user {user_id}")
            self.channel.start_consuming()
        
        def handle_user_message(self, user_id, message):
            """Handle incoming message for user"""
            
            message_type = message['type']
            
            if message_type == 'chat_message':
                print(f"📱 [{message['room_id']}] {message['user_id']}: {message['text']}")
            
            elif message_type == 'direct_message':
                print(f"📩 DM from {message['from_user_id']}: {message['text']}")
            
            elif message_type == 'user_joined':
                print(f"👋 {message['user_id']} joined room {message['room_id']}")
            
            elif message_type == 'presence_update':
                if message['user_id'] != user_id:  # Don't show own presence
                    print(f"🔘 {message['user_id']} is {message['status']}")
        
        def get_message_history(self, room_id, limit=50):
            """Get recent message history for room"""
            
            # In real implementation, would query message history
            # with proper filtering and pagination
            
            print(f"📚 Retrieved {limit} recent messages for room {room_id}")
            
            # Simulated history
            return [
                {
                    'user_id': 'user1',
                    'text': 'Hello everyone!',
                    'timestamp': time.time() - 3600
                },
                {
                    'user_id': 'user2', 
                    'text': 'Hey there!',
                    'timestamp': time.time() - 3500
                }
            ]
    
    return ChatSystem

# Usage example:
# chat = realtime_chat_system()()
# 
# # User joins room and sends messages
# user_queue = chat.join_room('alice', 'general')
# chat.send_message('alice', 'general', 'Hello everyone!')
# chat.send_direct_message('alice', 'bob', 'Private message')
# chat.update_user_presence('alice', 'online')
# 
# # Start consuming (would be in separate thread/process)
# chat.start_user_consumer('alice')
```

---

## 🔀 **Enterprise Integration Patterns**

RabbitMQ implements many Enterprise Integration Patterns (EIP) from Gregor Hohpe's book. These patterns solve common integration challenges in enterprise environments.

### **1. Message Routing Patterns**

#### **Content-Based Router**
Routes messages based on message content rather than just headers.

```python
def content_based_router():
    """Content-based message routing pattern"""
    
    import pika
    import json
    import re
    
    class ContentBasedRouter:
        """Routes messages based on content analysis"""
        
        def __init__(self):
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters('localhost')
            )
            self.channel = self.connection.channel()
            
            # Setup routing infrastructure
            self.setup_routing_infrastructure()
            
            # Define routing rules
            self.routing_rules = [
                {
                    'name': 'high_priority_orders',
                    'condition': lambda msg: msg.get('order_total', 0) > 1000,
                    'exchange': 'priority_processing',
                    'routing_key': 'high_priority'
                },
                {
                    'name': 'international_orders',
                    'condition': lambda msg: msg.get('country') not in ['US', 'CA'],
                    'exchange': 'international_processing',
                    'routing_key': 'international'
                },
                {
                    'name': 'vip_customers',
                    'condition': lambda msg: msg.get('customer_tier') == 'VIP',
                    'exchange': 'vip_processing',
                    'routing_key': 'vip'
                },
                {
                    'name': 'bulk_orders',
                    'condition': lambda msg: len(msg.get('items', [])) > 10,
                    'exchange': 'bulk_processing',
                    'routing_key': 'bulk'
                }
            ]
        
        def setup_routing_infrastructure(self):
            """Setup exchanges and queues for routing"""
            
            # Input exchange
            self.channel.exchange_declare(
                exchange='order_intake',
                exchange_type='direct',
                durable=True
            )
            
            # Output exchanges
            routing_exchanges = [
                'priority_processing',
                'international_processing', 
                'vip_processing',
                'bulk_processing',
                'standard_processing'
            ]
            
            for exchange in routing_exchanges:
                self.channel.exchange_declare(
                    exchange=exchange,
                    exchange_type='direct',
                    durable=True
                )
                
                # Create processing queue for each exchange
                queue_name = f"{exchange}_queue"
                self.channel.queue_declare(queue=queue_name, durable=True)
                self.channel.queue_bind(
                    exchange=exchange,
                    queue=queue_name,
                    routing_key=exchange.split('_')[0]  # high, international, vip, etc.
                )
        
        def route_message(self, ch, method, properties, body):
            """Route message based on content"""
            
            try:
                message = json.loads(body)
                routed = False
                
                # Apply routing rules
                for rule in self.routing_rules:
                    if rule['condition'](message):
                        self.channel.basic_publish(
                            exchange=rule['exchange'],
                            routing_key=rule['routing_key'],
                            body=body,
                            properties=pika.BasicProperties(
                                delivery_mode=2,
                                headers={
                                    'original_routing_key': method.routing_key,
                                    'route_applied': rule['name'],
                                    'route_timestamp': time.time()
                                }
                            )
                        )
                        routed = True
                        print(f"🎯 Applied route: {rule['name']}")
                
                # Default route if no rules matched
                if not routed:
                    self.channel.basic_publish(
                        exchange='standard_processing',
                        routing_key='standard',
                        body=body,
                        properties=pika.BasicProperties(delivery_mode=2)
                    )
                    print("📦 Routed to standard processing")
                
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
            except Exception as e:
                print(f"❌ Routing failed: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        def start_routing(self):
            """Start content-based routing"""
            
            # Create input queue
            self.channel.queue_declare(queue='incoming_orders', durable=True)
            self.channel.queue_bind(
                exchange='order_intake',
                queue='incoming_orders',
                routing_key='new_order'
            )
            
            # Start consuming
            self.channel.basic_consume(
                queue='incoming_orders',
                on_message_callback=self.route_message
            )
            
            print("🔀 Content-based router started")
            self.channel.start_consuming()
    
    return ContentBasedRouter

# Usage:
# router = content_based_router()()
# router.start_routing()
```

#### **Recipient List Pattern**
Sends message to multiple specific recipients.

```python
def recipient_list_pattern():
    """Recipient list enterprise integration pattern"""
    
    import pika
    import json
    import time
    
    class RecipientListRouter:
        """Sends messages to dynamically determined recipients"""
        
        def __init__(self):
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters('localhost')
            )
            self.channel = self.connection.channel()
            self.setup_infrastructure()
            
            # Recipient determination rules
            self.recipient_rules = {
                'order_events': {
                    'order.created': ['inventory', 'accounting', 'shipping'],
                    'order.cancelled': ['inventory', 'accounting', 'customer_service'],
                    'order.completed': ['accounting', 'analytics', 'customer_service'],
                    'order.refunded': ['accounting', 'inventory', 'customer_service']
                },
                'user_events': {
                    'user.registered': ['marketing', 'analytics', 'customer_service'],
                    'user.upgraded': ['accounting', 'marketing', 'analytics'],
                    'user.churned': ['marketing', 'analytics']
                },
                'system_events': {
                    'system.error': ['monitoring', 'engineering', 'management'],
                    'system.maintenance': ['customer_service', 'marketing'],
                    'system.security_alert': ['security', 'engineering', 'management']
                }
            }
        
        def setup_infrastructure(self):
            """Setup recipient infrastructure"""
            
            # Input exchange for events
            self.channel.exchange_declare(
                exchange='event_distribution',
                exchange_type='topic',
                durable=True
            )
            
            # Recipient service exchanges
            services = [
                'inventory', 'accounting', 'shipping', 'customer_service',
                'marketing', 'analytics', 'monitoring', 'engineering',
                'management', 'security'
            ]
            
            for service in services:
                # Service exchange
                self.channel.exchange_declare(
                    exchange=f"{service}_events",
                    exchange_type='topic',
                    durable=True
                )
                
                # Service queue
                self.channel.queue_declare(
                    queue=f"{service}_queue",
                    durable=True,
                    arguments={
                        'x-max-length': 10000,
                        'x-overflow': 'drop-head'
                    }
                )
                
                # Bind service queue to its exchange
                self.channel.queue_bind(
                    exchange=f"{service}_events",
                    queue=f"{service}_queue",
                    routing_key='#'  # Receive all events for this service
                )
        
        def distribute_to_recipients(self, ch, method, properties, body):
            """Distribute message to determined recipients"""
            
            try:
                message = json.loads(body)
                event_category = method.routing_key.split('.')[0]  # order, user, system
                event_type = method.routing_key
                
                # Determine recipients
                recipients = self.determine_recipients(event_category, event_type, message)
                
                if not recipients:
                    print(f"⚠️  No recipients found for {event_type}")
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return
                
                # Enhance message with distribution metadata
                enhanced_message = {
                    **message,
                    'distribution_metadata': {
                        'original_event': event_type,
                        'recipients': recipients,
                        'distributed_at': time.time(),
                        'distribution_id': str(uuid.uuid4())
                    }
                }
                
                # Send to each recipient
                successful_deliveries = 0
                
                for recipient in recipients:
                    try:
                        self.channel.basic_publish(
                            exchange=f"{recipient}_events",
                            routing_key=event_type,
                            body=json.dumps(enhanced_message),
                            properties=pika.BasicProperties(
                                delivery_mode=2,
                                headers={
                                    'recipient': recipient,
                                    'original_routing_key': method.routing_key
                                }
                            )
                        )
                        successful_deliveries += 1
                        
                    except Exception as e:
                        print(f"❌ Failed to deliver to {recipient}: {e}")
                
                print(f"📬 Distributed {event_type} to {successful_deliveries}/{len(recipients)} recipients")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
            except Exception as e:
                print(f"❌ Distribution failed: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        def determine_recipients(self, category, event_type, message):
            """Determine recipients based on rules and message content"""
            
            recipients = []
            
            # Static rules based on event type
            if category in self.recipient_rules:
                recipients.extend(
                    self.recipient_rules[category].get(event_type, [])
                )
            
            # Dynamic rules based on message content
            if category == 'order_events':
                order_total = message.get('total', 0)
                if order_total > 1000:  # High value orders
                    recipients.extend(['management', 'security'])
                
                if message.get('payment_method') == 'crypto':
                    recipients.append('security')
            
            elif category == 'user_events':
                user_tier = message.get('tier', 'standard')
                if user_tier == 'enterprise':
                    recipients.extend(['management', 'enterprise_support'])
            
            # Remove duplicates and return
            return list(set(recipients))
        
        def start_distribution(self):
            """Start recipient list distribution"""
            
            # Create distribution queue
            self.channel.queue_declare(queue='event_distribution_queue', durable=True)
            self.channel.queue_bind(
                exchange='event_distribution',
                queue='event_distribution_queue',
                routing_key='#'  # Receive all events
            )
            
            # Start consuming
            self.channel.basic_consume(
                queue='event_distribution_queue',
                on_message_callback=self.distribute_to_recipients
            )
            
            print("📬 Recipient list router started")
            self.channel.start_consuming()
    
    return RecipientListRouter

# Usage:
# distributor = recipient_list_pattern()()
# distributor.start_distribution()
```

### **2. Message Transformation Patterns**

#### **Message Translator**
Transforms message format between different systems.

```python
def message_translator_pattern():
    """Message translator for format conversion"""
    
    import pika
    import json
    import xml.etree.ElementTree as ET
    from datetime import datetime
    
    class MessageTranslator:
        """Translates between different message formats"""
        
        def __init__(self):
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters('localhost')
            )
            self.channel = self.connection.channel()
            self.setup_infrastructure()
            
            # Translation mappings
            self.field_mappings = {
                'legacy_to_modern': {
                    'cust_id': 'customer_id',
                    'ord_num': 'order_number',
                    'ord_date': 'order_date',
                    'prod_code': 'product_code',
                    'qty': 'quantity',
                    'amt': 'amount'
                },
                'modern_to_legacy': {
                    'customer_id': 'cust_id',
                    'order_number': 'ord_num',
                    'order_date': 'ord_date',
                    'product_code': 'prod_code',
                    'quantity': 'qty',
                    'amount': 'amt'
                }
            }
        
        def setup_infrastructure(self):
            """Setup translation infrastructure"""
            
            exchanges = [
                ('legacy_input', 'direct'),
                ('modern_input', 'direct'),
                ('legacy_output', 'direct'),
                ('modern_output', 'direct'),
                ('xml_output', 'direct')
            ]
            
            for exchange_name, exchange_type in exchanges:
                self.channel.exchange_declare(
                    exchange=exchange_name,
                    exchange_type=exchange_type,
                    durable=True
                )
            
            # Translation queues
            queues = [
                'legacy_to_modern_queue',
                'modern_to_legacy_queue',
                'json_to_xml_queue',
                'xml_to_json_queue'
            ]
            
            for queue in queues:
                self.channel.queue_declare(queue=queue, durable=True)
        
        def translate_legacy_to_modern(self, ch, method, properties, body):
            """Translate legacy format to modern format"""
            
            try:
                legacy_data = json.loads(body)
                
                # Transform field names
                modern_data = {}
                for legacy_field, legacy_value in legacy_data.items():
                    modern_field = self.field_mappings['legacy_to_modern'].get(
                        legacy_field, legacy_field
                    )
                    modern_data[modern_field] = legacy_value
                
                # Transform data types and formats
                if 'order_date' in modern_data:
                    # Convert from MM/DD/YYYY to ISO format
                    try:
                        old_date = datetime.strptime(modern_data['order_date'], '%m/%d/%Y')
                        modern_data['order_date'] = old_date.isoformat()
                    except ValueError:
                        pass  # Keep original if parsing fails
                
                # Add modern schema metadata
                modern_data['_metadata'] = {
                    'schema_version': '2.0',
                    'translated_from': 'legacy',
                    'translation_timestamp': datetime.utcnow().isoformat()
                }
                
                # Publish translated message
                self.channel.basic_publish(
                    exchange='modern_output',
                    routing_key='translated',
                    body=json.dumps(modern_data),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        headers={'translation_type': 'legacy_to_modern'}
                    )
                )
                
                print("🔄 Translated legacy to modern format")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
            except Exception as e:
                print(f"❌ Legacy translation failed: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        def translate_json_to_xml(self, ch, method, properties, body):
            """Convert JSON message to XML format"""
            
            try:
                json_data = json.loads(body)
                
                # Create XML structure
                root = ET.Element('message')
                
                def dict_to_xml(parent, data):
                    for key, value in data.items():
                        element = ET.SubElement(parent, key)
                        if isinstance(value, dict):
                            dict_to_xml(element, value)
                        elif isinstance(value, list):
                            for item in value:
                                item_element = ET.SubElement(element, 'item')
                                if isinstance(item, dict):
                                    dict_to_xml(item_element, item)
                                else:
                                    item_element.text = str(item)
                        else:
                            element.text = str(value)
                
                dict_to_xml(root, json_data)
                
                # Add XML metadata
                root.set('format', 'translated_xml')
                root.set('timestamp', datetime.utcnow().isoformat())
                
                xml_string = ET.tostring(root, encoding='unicode')
                
                # Publish XML message
                self.channel.basic_publish(
                    exchange='xml_output',
                    routing_key='xml_data',
                    body=xml_string,
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        content_type='application/xml',
                        headers={'translation_type': 'json_to_xml'}
                    )
                )
                
                print("🔄 Translated JSON to XML format")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
            except Exception as e:
                print(f"❌ JSON to XML translation failed: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        def start_translation_services(self):
            """Start all translation services"""
            
            # Bind queues to exchanges
            self.channel.queue_bind(
                exchange='legacy_input',
                queue='legacy_to_modern_queue',
                routing_key='legacy_data'
            )
            
            self.channel.queue_bind(
                exchange='modern_input',
                queue='json_to_xml_queue',
                routing_key='json_data'
            )
            
            # Setup consumers
            self.channel.basic_consume(
                queue='legacy_to_modern_queue',
                on_message_callback=self.translate_legacy_to_modern
            )
            
            self.channel.basic_consume(
                queue='json_to_xml_queue',
                on_message_callback=self.translate_json_to_xml
            )
            
            print("🔄 Message translator services started")
            self.channel.start_consuming()
    
    return MessageTranslator

# Usage:
# translator = message_translator_pattern()()
# translator.start_translation_services()
```

### **3. Message Aggregation Patterns**

#### **Aggregator Pattern**
Combines related messages into a single message.

```python
def message_aggregator_pattern():
    """Message aggregator for combining related messages"""
    
    import pika
    import json
    import time
    import threading
    from collections import defaultdict
    
    class MessageAggregator:
        """Aggregates multiple messages into composite messages"""
        
        def __init__(self):
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters('localhost')
            )
            self.channel = self.connection.channel()
            self.setup_infrastructure()
            
            # Aggregation state
            self.aggregation_buffers = defaultdict(list)
            self.aggregation_timers = {}
            self.lock = threading.Lock()
            
            # Aggregation rules
            self.aggregation_rules = {
                'order_items': {
                    'group_by': 'order_id',
                    'timeout_seconds': 30,
                    'max_messages': 10,
                    'output_exchange': 'aggregated_orders'
                },
                'inventory_updates': {
                    'group_by': 'product_id',
                    'timeout_seconds': 60,
                    'max_messages': 20,
                    'output_exchange': 'batch_inventory_updates'
                },
                'user_actions': {
                    'group_by': 'user_id',
                    'timeout_seconds': 300,  # 5 minutes
                    'max_messages': 50,
                    'output_exchange': 'user_behavior_batches'
                }
            }
        
        def setup_infrastructure(self):
            """Setup aggregation infrastructure"""
            
            # Input exchanges
            input_exchanges = ['order_events', 'inventory_events', 'user_events']
            for exchange in input_exchanges:
                self.channel.exchange_declare(
                    exchange=exchange,
                    exchange_type='topic',
                    durable=True
                )
            
            # Output exchanges
            output_exchanges = [
                'aggregated_orders',
                'batch_inventory_updates', 
                'user_behavior_batches'
            ]
            for exchange in output_exchanges:
                self.channel.exchange_declare(
                    exchange=exchange,
                    exchange_type='direct',
                    durable=True
                )
                
                # Create output queue
                queue_name = f"{exchange}_queue"
                self.channel.queue_declare(queue=queue_name, durable=True)
                self.channel.queue_bind(
                    exchange=exchange,
                    queue=queue_name,
                    routing_key='aggregated'
                )
        
        def aggregate_order_items(self, ch, method, properties, body):
            """Aggregate order item messages"""
            
            try:
                message = json.loads(body)
                order_id = message.get('order_id')
                
                if not order_id:
                    print("❌ No order_id found in message")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                    return
                
                with self.lock:
                    # Add to aggregation buffer
                    buffer_key = f"order_items_{order_id}"
                    self.aggregation_buffers[buffer_key].append({
                        'message': message,
                        'received_at': time.time(),
                        'routing_key': method.routing_key
                    })
                    
                    # Check aggregation conditions
                    rule = self.aggregation_rules['order_items']
                    buffer = self.aggregation_buffers[buffer_key]
                    
                    should_aggregate = (
                        len(buffer) >= rule['max_messages'] or
                        (buffer and time.time() - buffer[0]['received_at'] >= rule['timeout_seconds'])
                    )
                    
                    if should_aggregate:
                        self.create_aggregated_order(order_id, buffer)
                        del self.aggregation_buffers[buffer_key]
                        
                        # Cancel timer if it exists
                        if buffer_key in self.aggregation_timers:
                            self.aggregation_timers[buffer_key].cancel()
                            del self.aggregation_timers[buffer_key]
                    
                    elif buffer_key not in self.aggregation_timers:
                        # Start timeout timer
                        timer = threading.Timer(
                            rule['timeout_seconds'],
                            self.timeout_aggregation,
                            args=[buffer_key]
                        )
                        timer.start()
                        self.aggregation_timers[buffer_key] = timer
                
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
            except Exception as e:
                print(f"❌ Order aggregation failed: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        def create_aggregated_order(self, order_id, buffer):
            """Create aggregated order message"""
            
            aggregated_message = {
                'aggregation_type': 'order_completion',
                'order_id': order_id,
                'items': [],
                'total_items': len(buffer),
                'aggregation_period': {
                    'start_time': buffer[0]['received_at'],
                    'end_time': time.time()
                },
                'metadata': {
                    'aggregated_at': time.time(),
                    'message_count': len(buffer)
                }
            }
            
            # Combine all order items
            total_amount = 0
            for entry in buffer:
                item_data = entry['message']
                aggregated_message['items'].append(item_data)
                total_amount += item_data.get('amount', 0)
            
            aggregated_message['total_amount'] = total_amount
            
            # Publish aggregated message
            self.channel.basic_publish(
                exchange='aggregated_orders',
                routing_key='aggregated',
                body=json.dumps(aggregated_message),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    headers={
                        'aggregation_type': 'order_items',
                        'message_count': len(buffer)
                    }
                )
            )
            
            print(f"📦 Aggregated {len(buffer)} order items for order {order_id}")
        
        def timeout_aggregation(self, buffer_key):
            """Handle aggregation timeout"""
            
            with self.lock:
                if buffer_key in self.aggregation_buffers:
                    buffer = self.aggregation_buffers[buffer_key]
                    
                    if buffer:
                        # Extract identifiers and create aggregation
                        if buffer_key.startswith('order_items_'):
                            order_id = buffer_key.replace('order_items_', '')
                            self.create_aggregated_order(order_id, buffer)
                        
                        # Clean up
                        del self.aggregation_buffers[buffer_key]
                        if buffer_key in self.aggregation_timers:
                            del self.aggregation_timers[buffer_key]
                        
                        print(f"⏰ Timeout aggregation for {buffer_key}")
        
        def start_aggregation(self):
            """Start message aggregation services"""
            
            # Create aggregation queues
            self.channel.queue_declare(queue='order_items_aggregation', durable=True)
            self.channel.queue_bind(
                exchange='order_events',
                queue='order_items_aggregation',
                routing_key='order.item.*'
            )
            
            # Start consuming
            self.channel.basic_consume(
                queue='order_items_aggregation',
                on_message_callback=self.aggregate_order_items
            )
            
            print("📦 Message aggregator started")
            self.channel.start_consuming()
    
    return MessageAggregator

# Usage:
# aggregator = message_aggregator_pattern()()
# aggregator.start_aggregation()
```

---

## ⚙️ **Operational Procedures**

Production RabbitMQ requires well-defined operational procedures for maintenance, monitoring, disaster recovery, and troubleshooting.

### **1. Health Monitoring & Alerting**

#### **Comprehensive Health Checks**

```python
def rabbitmq_health_monitoring():
    """Comprehensive RabbitMQ health monitoring system"""
    
    import pika
    import requests
    import json
    import time
    import psutil
    import logging
    from dataclasses import dataclass
    from typing import Dict, List, Optional
    
    @dataclass
    class HealthMetric:
        """Health metric data structure"""
        name: str
        value: float
        threshold: float
        status: str
        message: str
        timestamp: float
    
    class RabbitMQHealthMonitor:
        """Production-grade health monitoring"""
        
        def __init__(self, management_url='http://localhost:15672', 
                     username='guest', password='guest'):
            self.management_url = management_url
            self.auth = (username, password)
            
            # Health thresholds
            self.thresholds = {
                'memory_usage_percent': 85.0,
                'disk_usage_percent': 90.0,
                'queue_depth_critical': 10000,
                'queue_depth_warning': 5000,
                'consumer_utilization_min': 0.8,
                'connection_count_max': 1000,
                'message_rate_min': 1.0,
                'node_cpu_percent_max': 80.0,
                'cluster_partition_count': 0
            }
            
            # Setup logging
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger(__name__)
        
        def check_cluster_status(self) -> List[HealthMetric]:
            """Check overall cluster health"""
            
            metrics = []
            
            try:
                # Check cluster nodes
                response = requests.get(
                    f"{self.management_url}/api/nodes",
                    auth=self.auth,
                    timeout=10
                )
                
                if response.status_code == 200:
                    nodes = response.json()
                    
                    running_nodes = [n for n in nodes if n['running']]
                    total_nodes = len(nodes)
                    
                    metrics.append(HealthMetric(
                        name='cluster_nodes_running',
                        value=len(running_nodes),
                        threshold=total_nodes,
                        status='HEALTHY' if len(running_nodes) == total_nodes else 'CRITICAL',
                        message=f"{len(running_nodes)}/{total_nodes} nodes running",
                        timestamp=time.time()
                    ))
                    
                    # Check for network partitions
                    partitioned_nodes = [n for n in nodes if len(n.get('partitions', [])) > 0]
                    
                    metrics.append(HealthMetric(
                        name='cluster_partitions',
                        value=len(partitioned_nodes),
                        threshold=self.thresholds['cluster_partition_count'],
                        status='CRITICAL' if partitioned_nodes else 'HEALTHY',
                        message=f"Network partitions detected: {[n['name'] for n in partitioned_nodes]}",
                        timestamp=time.time()
                    ))
                
            except Exception as e:
                metrics.append(HealthMetric(
                    name='cluster_api_connectivity',
                    value=0,
                    threshold=1,
                    status='CRITICAL',
                    message=f"Management API unreachable: {e}",
                    timestamp=time.time()
                ))
            
            return metrics
        
        def check_node_resources(self) -> List[HealthMetric]:
            """Check individual node resource usage"""
            
            metrics = []
            
            try:
                # Memory usage
                response = requests.get(
                    f"{self.management_url}/api/nodes",
                    auth=self.auth,
                    timeout=10
                )
                
                if response.status_code == 200:
                    nodes = response.json()
                    
                    for node in nodes:
                        node_name = node['name']
                        
                        # Memory metrics
                        mem_used = node.get('mem_used', 0)
                        mem_limit = node.get('mem_limit', 1)
                        mem_percent = (mem_used / mem_limit) * 100 if mem_limit > 0 else 0
                        
                        metrics.append(HealthMetric(
                            name=f'memory_usage_{node_name}',
                            value=mem_percent,
                            threshold=self.thresholds['memory_usage_percent'],
                            status='CRITICAL' if mem_percent > self.thresholds['memory_usage_percent'] else 'HEALTHY',
                            message=f"Memory usage: {mem_percent:.1f}%",
                            timestamp=time.time()
                        ))
                        
                        # Disk space
                        disk_free = node.get('disk_free', 0)
                        disk_free_limit = node.get('disk_free_limit', 1)
                        disk_usage_percent = ((disk_free_limit - disk_free) / disk_free_limit) * 100
                        
                        metrics.append(HealthMetric(
                            name=f'disk_usage_{node_name}',
                            value=disk_usage_percent,
                            threshold=self.thresholds['disk_usage_percent'],
                            status='CRITICAL' if disk_usage_percent > self.thresholds['disk_usage_percent'] else 'HEALTHY',
                            message=f"Disk usage: {disk_usage_percent:.1f}%",
                            timestamp=time.time()
                        ))
                        
                        # File descriptors
                        fd_used = node.get('fd_used', 0)
                        fd_total = node.get('fd_total', 1)
                        fd_percent = (fd_used / fd_total) * 100 if fd_total > 0 else 0
                        
                        metrics.append(HealthMetric(
                            name=f'file_descriptors_{node_name}',
                            value=fd_percent,
                            threshold=80.0,
                            status='WARNING' if fd_percent > 80.0 else 'HEALTHY',
                            message=f"File descriptors: {fd_percent:.1f}% ({fd_used}/{fd_total})",
                            timestamp=time.time()
                        ))
                
            except Exception as e:
                self.logger.error(f"Node resource check failed: {e}")
            
            return metrics
        
        def check_queue_health(self) -> List[HealthMetric]:
            """Check queue health and performance"""
            
            metrics = []
            
            try:
                response = requests.get(
                    f"{self.management_url}/api/queues",
                    auth=self.auth,
                    timeout=10
                )
                
                if response.status_code == 200:
                    queues = response.json()
                    
                    for queue in queues:
                        queue_name = queue['name']
                        vhost = queue['vhost']
                        
                        # Queue depth
                        messages = queue.get('messages', 0)
                        
                        status = 'HEALTHY'
                        if messages > self.thresholds['queue_depth_critical']:
                            status = 'CRITICAL'
                        elif messages > self.thresholds['queue_depth_warning']:
                            status = 'WARNING'
                        
                        metrics.append(HealthMetric(
                            name=f'queue_depth_{vhost}_{queue_name}',
                            value=messages,
                            threshold=self.thresholds['queue_depth_warning'],
                            status=status,
                            message=f"Queue depth: {messages} messages",
                            timestamp=time.time()
                        ))
                        
                        # Consumer count
                        consumers = queue.get('consumers', 0)
                        
                        metrics.append(HealthMetric(
                            name=f'queue_consumers_{vhost}_{queue_name}',
                            value=consumers,
                            threshold=1,
                            status='WARNING' if consumers == 0 and messages > 0 else 'HEALTHY',
                            message=f"Active consumers: {consumers}",
                            timestamp=time.time()
                        ))
                        
                        # Message rates
                        message_stats = queue.get('message_stats', {})
                        publish_rate = message_stats.get('publish_details', {}).get('rate', 0)
                        consume_rate = message_stats.get('deliver_get_details', {}).get('rate', 0)
                        
                        if publish_rate > 0:
                            consumer_utilization = consume_rate / publish_rate
                            
                            metrics.append(HealthMetric(
                                name=f'consumer_utilization_{vhost}_{queue_name}',
                                value=consumer_utilization,
                                threshold=self.thresholds['consumer_utilization_min'],
                                status='WARNING' if consumer_utilization < self.thresholds['consumer_utilization_min'] else 'HEALTHY',
                                message=f"Consumer utilization: {consumer_utilization:.2f}",
                                timestamp=time.time()
                            ))
                
            except Exception as e:
                self.logger.error(f"Queue health check failed: {e}")
            
            return metrics
        
        def check_connection_health(self) -> List[HealthMetric]:
            """Check connection and channel health"""
            
            metrics = []
            
            try:
                # Check connections
                response = requests.get(
                    f"{self.management_url}/api/connections",
                    auth=self.auth,
                    timeout=10
                )
                
                if response.status_code == 200:
                    connections = response.json()
                    
                    total_connections = len(connections)
                    
                    metrics.append(HealthMetric(
                        name='total_connections',
                        value=total_connections,
                        threshold=self.thresholds['connection_count_max'],
                        status='WARNING' if total_connections > self.thresholds['connection_count_max'] else 'HEALTHY',
                        message=f"Total connections: {total_connections}",
                        timestamp=time.time()
                    ))
                    
                    # Connection states
                    running_connections = [c for c in connections if c['state'] == 'running']
                    blocked_connections = [c for c in connections if c['state'] == 'blocked']
                    
                    if blocked_connections:
                        metrics.append(HealthMetric(
                            name='blocked_connections',
                            value=len(blocked_connections),
                            threshold=0,
                            status='WARNING',
                            message=f"Blocked connections: {len(blocked_connections)}",
                            timestamp=time.time()
                        ))
                
                # Check channels
                response = requests.get(
                    f"{self.management_url}/api/channels",
                    auth=self.auth,
                    timeout=10
                )
                
                if response.status_code == 200:
                    channels = response.json()
                    
                    total_channels = len(channels)
                    
                    metrics.append(HealthMetric(
                        name='total_channels',
                        value=total_channels,
                        threshold=self.thresholds['connection_count_max'] * 2,  # Rough estimate
                        status='HEALTHY',
                        message=f"Total channels: {total_channels}",
                        timestamp=time.time()
                    ))
                
            except Exception as e:
                self.logger.error(f"Connection health check failed: {e}")
            
            return metrics
        
        def generate_health_report(self) -> Dict:
            """Generate comprehensive health report"""
            
            all_metrics = []
            
            # Collect all metrics
            all_metrics.extend(self.check_cluster_status())
            all_metrics.extend(self.check_node_resources())
            all_metrics.extend(self.check_queue_health())
            all_metrics.extend(self.check_connection_health())
            
            # Categorize by status
            critical_metrics = [m for m in all_metrics if m.status == 'CRITICAL']
            warning_metrics = [m for m in all_metrics if m.status == 'WARNING']
            healthy_metrics = [m for m in all_metrics if m.status == 'HEALTHY']
            
            # Overall system status
            overall_status = 'HEALTHY'
            if critical_metrics:
                overall_status = 'CRITICAL'
            elif warning_metrics:
                overall_status = 'WARNING'
            
            report = {
                'timestamp': time.time(),
                'overall_status': overall_status,
                'summary': {
                    'total_checks': len(all_metrics),
                    'critical_issues': len(critical_metrics),
                    'warnings': len(warning_metrics),
                    'healthy_checks': len(healthy_metrics)
                },
                'critical_issues': [
                    {'name': m.name, 'message': m.message, 'value': m.value, 'threshold': m.threshold}
                    for m in critical_metrics
                ],
                'warnings': [
                    {'name': m.name, 'message': m.message, 'value': m.value, 'threshold': m.threshold}
                    for m in warning_metrics
                ],
                'all_metrics': [
                    {
                        'name': m.name,
                        'value': m.value,
                        'threshold': m.threshold,
                        'status': m.status,
                        'message': m.message,
                        'timestamp': m.timestamp
                    }
                    for m in all_metrics
                ]
            }
            
            return report
        
        def start_monitoring(self, check_interval=60):
            """Start continuous health monitoring"""
            
            self.logger.info("🔍 Starting RabbitMQ health monitoring")
            
            while True:
                try:
                    report = self.generate_health_report()
                    
                    # Log summary
                    status_emoji = {
                        'HEALTHY': '✅',
                        'WARNING': '⚠️',
                        'CRITICAL': '🚨'
                    }
                    
                    emoji = status_emoji.get(report['overall_status'], '❓')
                    self.logger.info(
                        f"{emoji} System Status: {report['overall_status']} "
                        f"({report['summary']['critical_issues']} critical, "
                        f"{report['summary']['warnings']} warnings)"
                    )
                    
                    # Alert on issues
                    if report['critical_issues']:
                        for issue in report['critical_issues']:
                            self.logger.critical(f"🚨 CRITICAL: {issue['name']} - {issue['message']}")
                    
                    if report['warnings']:
                        for warning in report['warnings']:
                            self.logger.warning(f"⚠️  WARNING: {warning['name']} - {warning['message']}")
                    
                    # Send to monitoring system (Prometheus, DataDog, etc.)
                    self.send_metrics_to_monitoring(report)
                    
                    time.sleep(check_interval)
                    
                except KeyboardInterrupt:
                    self.logger.info("Health monitoring stopped")
                    break
                except Exception as e:
                    self.logger.error(f"Health monitoring error: {e}")
                    time.sleep(10)  # Short retry interval
        
        def send_metrics_to_monitoring(self, report):
            """Send metrics to external monitoring system"""
            
            # Example: Send to Prometheus pushgateway
            # In production, implement actual monitoring integration
            pass
    
    return RabbitMQHealthMonitor

# Usage:
# monitor = rabbitmq_health_monitoring()(
#     management_url='http://localhost:15672',
#     username='admin',
#     password='admin'
# )
# monitor.start_monitoring(check_interval=30)
```

### **2. Backup & Disaster Recovery**

#### **Comprehensive Backup Strategy**

```python
def rabbitmq_backup_procedures():
    """Comprehensive backup and disaster recovery procedures"""
    
    import subprocess
    import json
    import os
    import time
    import gzip
    import shutil
    import boto3
    from datetime import datetime, timedelta
    from pathlib import Path
    
    class RabbitMQBackupManager:
        """Production backup and recovery manager"""
        
        def __init__(self, backup_config):
            self.config = backup_config
            self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # AWS S3 client for remote backup storage
            if self.config.get('s3_enabled'):
                self.s3_client = boto3.client('s3',
                    aws_access_key_id=self.config['s3_access_key'],
                    aws_secret_access_key=self.config['s3_secret_key'],
                    region_name=self.config['s3_region']
                )
        
        def backup_definitions(self):
            """Backup RabbitMQ definitions (exchanges, queues, bindings)"""
            
            print("📋 Backing up RabbitMQ definitions...")
            
            backup_dir = Path(self.config['local_backup_dir']) / f"backup_{self.timestamp}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Export definitions using management API
            definitions_file = backup_dir / "definitions.json"
            
            export_cmd = [
                'curl', '-u', f"{self.config['username']}:{self.config['password']}",
                f"{self.config['management_url']}/api/definitions",
                '-o', str(definitions_file)
            ]
            
            try:
                subprocess.run(export_cmd, check=True, capture_output=True)
                print(f"✅ Definitions exported to {definitions_file}")
                
                # Compress definitions
                with open(definitions_file, 'rb') as f_in:
                    with gzip.open(f"{definitions_file}.gz", 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                os.remove(definitions_file)
                print("✅ Definitions compressed")
                
                return f"{definitions_file}.gz"
                
            except subprocess.CalledProcessError as e:
                print(f"❌ Definitions backup failed: {e}")
                return None
        
        def backup_messages(self, queues=None):
            """Backup message contents from specified queues"""
            
            print("💾 Backing up queue messages...")
            
            backup_dir = Path(self.config['local_backup_dir']) / f"backup_{self.timestamp}"
            messages_dir = backup_dir / "messages"
            messages_dir.mkdir(exist_ok=True)
            
            if queues is None:
                # Get all queue names
                queues = self.get_all_queues()
            
            backed_up_files = []
            
            for queue_name in queues:
                try:
                    # Use rabbitmqctl to dump messages
                    queue_file = messages_dir / f"{queue_name}.json"
                    
                    # Get messages via management API (limited approach)
                    # In production, use shovel plugin or custom consumer for full backup
                    get_cmd = [
                        'curl', '-u', f"{self.config['username']}:{self.config['password']}",
                        f"{self.config['management_url']}/api/queues/%2F/{queue_name}/get",
                        '-H', 'Content-Type: application/json',
                        '-d', '{"count":1000,"ackmode":"ack_requeue_false","encoding":"auto"}',
                        '-o', str(queue_file)
                    ]
                    
                    subprocess.run(get_cmd, check=True, capture_output=True)
                    
                    # Compress queue file
                    with open(queue_file, 'rb') as f_in:
                        with gzip.open(f"{queue_file}.gz", 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    os.remove(queue_file)
                    backed_up_files.append(f"{queue_file}.gz")
                    
                    print(f"✅ Backed up queue: {queue_name}")
                    
                except Exception as e:
                    print(f"❌ Failed to backup queue {queue_name}: {e}")
            
            return backed_up_files
        
        def backup_configuration(self):
            """Backup RabbitMQ configuration files"""
            
            print("⚙️  Backing up configuration files...")
            
            backup_dir = Path(self.config['local_backup_dir']) / f"backup_{self.timestamp}"
            config_dir = backup_dir / "config"
            config_dir.mkdir(exist_ok=True)
            
            config_files = [
                '/etc/rabbitmq/rabbitmq.conf',
                '/etc/rabbitmq/advanced.config', 
                '/etc/rabbitmq/enabled_plugins',
                '/var/lib/rabbitmq/.erlang.cookie'
            ]
            
            backed_up_configs = []
            
            for config_file in config_files:
                if os.path.exists(config_file):
                    try:
                        filename = os.path.basename(config_file)
                        dest_file = config_dir / filename
                        shutil.copy2(config_file, dest_file)
                        
                        # Compress config
                        with open(dest_file, 'rb') as f_in:
                            with gzip.open(f"{dest_file}.gz", 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        
                        os.remove(dest_file)
                        backed_up_configs.append(f"{dest_file}.gz")
                        
                        print(f"✅ Backed up config: {filename}")
                        
                    except Exception as e:
                        print(f"❌ Failed to backup {config_file}: {e}")
            
            return backed_up_configs
        
        def create_full_backup(self):
            """Create comprehensive backup"""
            
            print(f"🔄 Starting full backup at {self.timestamp}")
            
            backup_manifest = {
                'backup_timestamp': self.timestamp,
                'backup_type': 'full',
                'rabbitmq_version': self.get_rabbitmq_version(),
                'files': {}
            }
            
            # Backup definitions
            definitions_file = self.backup_definitions()
            if definitions_file:
                backup_manifest['files']['definitions'] = definitions_file
            
            # Backup configurations
            config_files = self.backup_configuration()
            backup_manifest['files']['configurations'] = config_files
            
            # Backup messages from critical queues
            critical_queues = self.config.get('critical_queues', [])
            if critical_queues:
                message_files = self.backup_messages(critical_queues)
                backup_manifest['files']['messages'] = message_files
            
            # Save manifest
            backup_dir = Path(self.config['local_backup_dir']) / f"backup_{self.timestamp}"
            manifest_file = backup_dir / "backup_manifest.json"
            
            with open(manifest_file, 'w') as f:
                json.dump(backup_manifest, f, indent=2)
            
            # Create backup archive
            archive_name = f"rabbitmq_backup_{self.timestamp}"
            archive_path = shutil.make_archive(
                str(Path(self.config['local_backup_dir']) / archive_name),
                'gztar',
                str(backup_dir)
            )
            
            print(f"✅ Backup archive created: {archive_path}")
            
            # Upload to remote storage
            if self.config.get('s3_enabled'):
                self.upload_to_s3(archive_path, f"{archive_name}.tar.gz")
            
            # Cleanup old backups
            self.cleanup_old_backups()
            
            return archive_path
        
        def restore_from_backup(self, backup_path, restore_type='definitions_only'):
            """Restore RabbitMQ from backup"""
            
            print(f"🔄 Starting restore from {backup_path}")
            
            # Extract backup
            extract_dir = Path(self.config['local_backup_dir']) / f"restore_{int(time.time())}"
            extract_dir.mkdir(parents=True, exist_ok=True)
            
            shutil.unpack_archive(backup_path, extract_dir)
            
            # Find backup directory
            backup_dirs = [d for d in extract_dir.iterdir() if d.is_dir() and d.name.startswith('backup_')]
            if not backup_dirs:
                print("❌ No backup directory found in archive")
                return False
            
            backup_dir = backup_dirs[0]
            
            # Load manifest
            manifest_file = backup_dir / "backup_manifest.json"
            if manifest_file.exists():
                with open(manifest_file) as f:
                    manifest = json.load(f)
                    print(f"📋 Restoring backup from {manifest['backup_timestamp']}")
            
            # Restore definitions
            if restore_type in ['definitions_only', 'full']:
                definitions_file = backup_dir / "definitions.json.gz"
                if definitions_file.exists():
                    
                    # Decompress definitions
                    temp_def_file = extract_dir / "temp_definitions.json"
                    with gzip.open(definitions_file, 'rb') as f_in:
                        with open(temp_def_file, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    # Import definitions
                    import_cmd = [
                        'curl', '-u', f"{self.config['username']}:{self.config['password']}",
                        f"{self.config['management_url']}/api/definitions",
                        '-H', 'Content-Type: application/json',
                        '-T', str(temp_def_file)
                    ]
                    
                    try:
                        subprocess.run(import_cmd, check=True, capture_output=True)
                        print("✅ Definitions restored")
                    except subprocess.CalledProcessError as e:
                        print(f"❌ Definitions restore failed: {e}")
                        return False
            
            # Restore configurations (requires RabbitMQ restart)
            if restore_type == 'full':
                print("⚠️  Full restore requires manual configuration file replacement and service restart")
                print("   Configuration files are available in: config/")
            
            # Cleanup
            shutil.rmtree(extract_dir)
            
            print("✅ Restore completed")
            return True
        
        def get_all_queues(self):
            """Get list of all queue names"""
            
            try:
                import requests
                
                response = requests.get(
                    f"{self.config['management_url']}/api/queues",
                    auth=(self.config['username'], self.config['password']),
                    timeout=10
                )
                
                if response.status_code == 200:
                    queues = response.json()
                    return [q['name'] for q in queues]
                
            except Exception as e:
                print(f"❌ Failed to get queue list: {e}")
            
            return []
        
        def get_rabbitmq_version(self):
            """Get RabbitMQ version"""
            
            try:
                result = subprocess.run(
                    ['rabbitmqctl', 'version'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                return result.stdout.strip()
            except:
                return "unknown"
        
        def upload_to_s3(self, file_path, s3_key):
            """Upload backup to S3"""
            
            try:
                self.s3_client.upload_file(
                    file_path,
                    self.config['s3_bucket'],
                    f"rabbitmq-backups/{s3_key}"
                )
                print(f"☁️  Uploaded to S3: s3://{self.config['s3_bucket']}/rabbitmq-backups/{s3_key}")
                
            except Exception as e:
                print(f"❌ S3 upload failed: {e}")
        
        def cleanup_old_backups(self):
            """Remove old local backups"""
            
            retention_days = self.config.get('backup_retention_days', 7)
            cutoff_time = time.time() - (retention_days * 24 * 3600)
            
            backup_dir = Path(self.config['local_backup_dir'])
            
            for backup_file in backup_dir.glob("rabbitmq_backup_*.tar.gz"):
                if backup_file.stat().st_mtime < cutoff_time:
                    backup_file.unlink()
                    print(f"🗑️  Removed old backup: {backup_file.name}")
        
        def schedule_backups(self):
            """Schedule automated backups"""
            
            print("⏰ Starting scheduled backup service")
            
            while True:
                try:
                    # Check if it's time for backup
                    now = datetime.now()
                    backup_hour = self.config.get('backup_hour', 2)  # Default 2 AM
                    
                    if now.hour == backup_hour and now.minute < 5:
                        self.create_full_backup()
                        time.sleep(3600)  # Wait an hour to avoid duplicate backups
                    
                    time.sleep(300)  # Check every 5 minutes
                    
                except KeyboardInterrupt:
                    print("Backup scheduler stopped")
                    break
                except Exception as e:
                    print(f"❌ Backup scheduler error: {e}")
                    time.sleep(600)  # Wait 10 minutes on error
    
    return RabbitMQBackupManager

# Configuration example:
backup_config = {
    'local_backup_dir': '/opt/rabbitmq/backups',
    'management_url': 'http://localhost:15672',
    'username': 'admin',
    'password': 'admin',
    'critical_queues': ['orders', 'payments', 'notifications'],
    'backup_retention_days': 14,
    'backup_hour': 2,  # 2 AM
    's3_enabled': True,
    's3_bucket': 'my-rabbitmq-backups',
    's3_access_key': 'YOUR_ACCESS_KEY',
    's3_secret_key': 'YOUR_SECRET_KEY',
    's3_region': 'us-west-2'
}

# Usage:
# backup_manager = rabbitmq_backup_procedures()(backup_config)
# 
# # Manual backup
# backup_manager.create_full_backup()
# 
# # Scheduled backups
# backup_manager.schedule_backups()
# 
# # Restore from backup
# backup_manager.restore_from_backup('/path/to/backup.tar.gz', 'definitions_only')
```

### **3. Performance Tuning Procedures**

```bash
#!/bin/bash
# RabbitMQ Performance Tuning Script

# System-level optimizations
optimize_system() {
    echo "🔧 Optimizing system parameters..."
    
    # Increase file descriptor limits
    echo "rabbitmq soft nofile 65536" >> /etc/security/limits.conf
    echo "rabbitmq hard nofile 65536" >> /etc/security/limits.conf
    
    # TCP optimization
    echo "net.core.somaxconn = 4096" >> /etc/sysctl.conf
    echo "net.ipv4.tcp_fin_timeout = 30" >> /etc/sysctl.conf
    echo "net.ipv4.tcp_keepalive_intvl = 30" >> /etc/sysctl.conf
    echo "net.ipv4.tcp_keepalive_probes = 5" >> /etc/sysctl.conf
    echo "net.ipv4.tcp_keepalive_time = 120" >> /etc/sysctl.conf
    
    sysctl -p
    
    echo "✅ System optimizations applied"
}

# RabbitMQ configuration tuning
tune_rabbitmq_config() {
    echo "⚙️  Tuning RabbitMQ configuration..."
    
    cat << 'EOF' > /etc/rabbitmq/rabbitmq.conf
# Memory and disk settings
vm_memory_high_watermark.relative = 0.6
disk_free_limit.relative = 2.0

# Connection settings
heartbeat = 60
frame_max = 131072
channel_max = 2047

# Queue settings
queue_index_embed_msgs_below = 4096
msg_store_file_size_limit = 16777216

# Clustering settings
cluster_partition_handling = pause_minority
cluster_keepalive_interval = 10000

# Performance settings
collect_statistics = coarse
collect_statistics_interval = 5000
EOF

    echo "✅ RabbitMQ configuration tuned"
}

# Memory optimization
optimize_memory() {
    echo "💾 Optimizing memory usage..."
    
    # Enable lazy queues for large message backlogs
    rabbitmqctl set_policy lazy-queues ".*" '{"queue-mode":"lazy"}' --priority 1
    
    # Set memory alarms
    rabbitmqctl set_vm_memory_high_watermark 0.6
    
    echo "✅ Memory optimizations applied"
}

# Network optimization  
optimize_network() {
    echo "🌐 Optimizing network settings..."
    
    # TCP buffer optimization
    rabbitmqctl eval 'application:set_env(rabbit, tcp_listen_options, [binary, {packet, raw}, {reuseaddr, true}, {backlog, 128}, {nodelay, true}, {exit_on_close, false}, {keepalive, true}]).'
    
    echo "✅ Network optimizations applied"
}

# Main execution
main() {
    echo "🚀 Starting RabbitMQ performance tuning..."
    
    optimize_system
    tune_rabbitmq_config
    optimize_memory
    optimize_network
    
    echo "🎯 Performance tuning completed. Restart RabbitMQ to apply all changes."
}

main "$@"
```

### **4. Troubleshooting Procedures**

```python
def rabbitmq_troubleshooting_toolkit():
    """Comprehensive troubleshooting toolkit"""
    
    import subprocess
    import json
    import re
    import time
    from datetime import datetime
    
    class RabbitMQTroubleshooter:
        """Production troubleshooting utilities"""
        
        def __init__(self, management_url='http://localhost:15672', 
                     username='admin', password='admin'):
            self.management_url = management_url
            self.auth = (username, password)
        
        def diagnose_high_memory_usage(self):
            """Diagnose and resolve high memory usage"""
            
            print("🔍 Diagnosing high memory usage...")
            
            try:
                # Get memory usage breakdown
                result = subprocess.run(
                    ['rabbitmqctl', 'status'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # Parse memory information
                memory_info = {}
                for line in result.stdout.split('\n'):
                    if 'memory' in line.lower():
                        print(f"  {line.strip()}")
                
                # Get top queues by memory
                import requests
                response = requests.get(
                    f"{self.management_url}/api/queues",
                    auth=self.auth
                )
                
                if response.status_code == 200:
                    queues = response.json()
                    
                    # Sort by memory usage
                    memory_queues = sorted(
                        [(q['name'], q.get('memory', 0)) for q in queues],
                        key=lambda x: x[1],
                        reverse=True
                    )
                    
                    print("\n📊 Top memory-consuming queues:")
                    for queue_name, memory_bytes in memory_queues[:10]:
                        memory_mb = memory_bytes / (1024 * 1024)
                        print(f"  {queue_name}: {memory_mb:.2f} MB")
                
                # Recommendations
                print("\n💡 Memory optimization recommendations:")
                print("  1. Enable lazy queues for large message backlogs")
                print("  2. Reduce message TTL to prevent accumulation")
                print("  3. Increase consumer capacity or optimize processing")
                print("  4. Consider message compression")
                print("  5. Monitor and purge unused queues")
                
            except Exception as e:
                print(f"❌ Memory diagnosis failed: {e}")
        
        def diagnose_connection_issues(self):
            """Diagnose connection and networking issues"""
            
            print("🔍 Diagnosing connection issues...")
            
            try:
                # Check connection states
                result = subprocess.run(
                    ['rabbitmqctl', 'list_connections', 'name', 'state', 'channels'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                connections = []
                for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        connections.append({
                            'name': parts[0],
                            'state': parts[1],
                            'channels': parts[2]
                        })
                
                # Analyze connection states
                state_counts = {}
                blocked_connections = []
                
                for conn in connections:
                    state = conn['state']
                    state_counts[state] = state_counts.get(state, 0) + 1
                    
                    if state == 'blocked':
                        blocked_connections.append(conn['name'])
                
                print("\n📊 Connection state summary:")
                for state, count in state_counts.items():
                    print(f"  {state}: {count}")
                
                if blocked_connections:
                    print(f"\n⚠️  Blocked connections ({len(blocked_connections)}):")
                    for conn_name in blocked_connections[:10]:  # Show first 10
                        print(f"  {conn_name}")
                    
                    print("\n💡 Blocked connection troubleshooting:")
                    print("  1. Check memory/disk alarms")
                    print("  2. Verify client heartbeat settings")
                    print("  3. Review network latency")
                    print("  4. Check publishing rate vs consumption rate")
                
                # Check for connection leaks
                high_channel_connections = [
                    conn for conn in connections 
                    if conn['channels'].isdigit() and int(conn['channels']) > 100
                ]
                
                if high_channel_connections:
                    print(f"\n⚠️  High channel count connections:")
                    for conn in high_channel_connections:
                        print(f"  {conn['name']}: {conn['channels']} channels")
                    
                    print("\n💡 High channel count troubleshooting:")
                    print("  1. Check for channel leaks in applications")
                    print("  2. Implement proper channel pooling")
                    print("  3. Review application connection management")
                
            except Exception as e:
                print(f"❌ Connection diagnosis failed: {e}")
        
        def diagnose_queue_problems(self):
            """Diagnose queue-related issues"""
            
            print("🔍 Diagnosing queue problems...")
            
            try:
                # Get queue information
                result = subprocess.run(
                    ['rabbitmqctl', 'list_queues', 'name', 'messages', 'consumers', 'memory'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                queues = []
                for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                    parts = line.split('\t')
                    if len(parts) >= 4:
                        queues.append({
                            'name': parts[0],
                            'messages': int(parts[1]) if parts[1].isdigit() else 0,
                            'consumers': int(parts[2]) if parts[2].isdigit() else 0,
                            'memory': int(parts[3]) if parts[3].isdigit() else 0
                        })
                
                # Identify problem queues
                problem_queues = {
                    'no_consumers_with_messages': [],
                    'high_message_count': [],
                    'high_memory_usage': [],
                    'no_consumers_no_messages': []
                }
                
                for queue in queues:
                    if queue['messages'] > 0 and queue['consumers'] == 0:
                        problem_queues['no_consumers_with_messages'].append(queue)
                    
                    if queue['messages'] > 10000:
                        problem_queues['high_message_count'].append(queue)
                    
                    if queue['memory'] > 100 * 1024 * 1024:  # 100MB
                        problem_queues['high_memory_usage'].append(queue)
                    
                    if queue['messages'] == 0 and queue['consumers'] == 0:
                        problem_queues['no_consumers_no_messages'].append(queue)
                
                # Report findings
                print("\n📊 Queue problem analysis:")
                
                if problem_queues['no_consumers_with_messages']:
                    print(f"\n⚠️  Queues with messages but no consumers ({len(problem_queues['no_consumers_with_messages'])}):")
                    for queue in problem_queues['no_consumers_with_messages'][:10]:
                        print(f"  {queue['name']}: {queue['messages']} messages")
                    print("  💡 Action: Start consumers or purge if messages are stale")
                
                if problem_queues['high_message_count']:
                    print(f"\n⚠️  Queues with high message count ({len(problem_queues['high_message_count'])}):")
                    for queue in problem_queues['high_message_count'][:10]:
                        print(f"  {queue['name']}: {queue['messages']} messages")
                    print("  💡 Action: Scale consumers or enable lazy queues")
                
                if problem_queues['high_memory_usage']:
                    print(f"\n⚠️  Queues with high memory usage ({len(problem_queues['high_memory_usage'])}):")
                    for queue in problem_queues['high_memory_usage'][:10]:
                        memory_mb = queue['memory'] / (1024 * 1024)
                        print(f"  {queue['name']}: {memory_mb:.2f} MB")
                    print("  💡 Action: Enable lazy queues or reduce message size")
                
                if len(problem_queues['no_consumers_no_messages']) > 50:
                    print(f"\n⚠️  Many unused queues ({len(problem_queues['no_consumers_no_messages'])}):")
                    print("  💡 Action: Clean up unused queues to reduce metadata overhead")
                
            except Exception as e:
                print(f"❌ Queue diagnosis failed: {e}")
        
        def diagnose_cluster_issues(self):
            """Diagnose cluster-related problems"""
            
            print("🔍 Diagnosing cluster issues...")
            
            try:
                # Check cluster status
                result = subprocess.run(
                    ['rabbitmqctl', 'cluster_status'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                print("📊 Cluster status:")
                print(result.stdout)
                
                # Check for partitions
                partition_result = subprocess.run(
                    ['rabbitmqctl', 'eval', 'rabbit_mnesia:status().'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                if 'partitions' in partition_result.stdout:
                    print("\n⚠️  Network partitions detected!")
                    print("💡 Partition recovery actions:")
                    print("  1. Identify partition cause (network issues, GC pauses)")
                    print("  2. Choose partition recovery strategy")
                    print("  3. Use 'rabbitmqctl forget_cluster_node' if necessary")
                    print("  4. Review cluster_partition_handling policy")
                
                # Check node synchronization
                sync_result = subprocess.run(
                    ['rabbitmqctl', 'list_queues', 'name', 'slave_pids', 'synchronised_slave_pids'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                unsync_queues = []
                for line in sync_result.stdout.strip().split('\n')[1:]:
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        slaves = parts[1] if parts[1] != '[]' else ''
                        sync_slaves = parts[2] if parts[2] != '[]' else ''
                        
                        if slaves and slaves != sync_slaves:
                            unsync_queues.append(parts[0])
                
                if unsync_queues:
                    print(f"\n⚠️  Unsynchronized mirror queues ({len(unsync_queues)}):")
                    for queue_name in unsync_queues[:10]:
                        print(f"  {queue_name}")
                    print("💡 Action: Use 'rabbitmqctl sync_queue' to synchronize")
                
            except Exception as e:
                print(f"❌ Cluster diagnosis failed: {e}")
        
        def generate_comprehensive_report(self):
            """Generate comprehensive troubleshooting report"""
            
            print("📋 Generating comprehensive troubleshooting report...")
            print("=" * 80)
            
            print(f"\n🕐 Report generated at: {datetime.now()}")
            
            print("\n" + "=" * 80)
            self.diagnose_high_memory_usage()
            
            print("\n" + "=" * 80)
            self.diagnose_connection_issues()
            
            print("\n" + "=" * 80)
            self.diagnose_queue_problems()
            
            print("\n" + "=" * 80)
            self.diagnose_cluster_issues()
            
            print("\n" + "=" * 80)
            print("✅ Troubleshooting report completed")
    
    return RabbitMQTroubleshooter

# Usage:
# troubleshooter = rabbitmq_troubleshooting_toolkit()(
#     management_url='http://localhost:15672',
#     username='admin',
#     password='admin'
# )
# 
# # Run comprehensive diagnosis
# troubleshooter.generate_comprehensive_report()
```

---

## 📝 **Summary**

This comprehensive RabbitMQ guide covers:

### **🎯 Core Concepts**
- ✅ AMQP model and architecture
- ✅ Exchanges, queues, bindings, and routing
- ✅ Virtual hosts and connections

### **🔄 Exchange Types**
- ✅ Direct: Exact routing key matching
- ✅ Topic: Pattern-based routing with wildcards
- ✅ Fanout: Broadcast to all bound queues
- ✅ Headers: Route based on message headers

### **📦 Advanced Features**
- ✅ Dead letter exchanges and queues
- ✅ TTL, priority queues, lazy queues
- ✅ Quorum queues for high availability
- ✅ Publisher confirms and transactions

### **👥 Consumer Patterns**
- ✅ Manual vs auto acknowledgments
- ✅ QoS settings for load balancing
- ✅ Error handling and retry logic
- ✅ Parallel processing patterns

### **🏛️ High Availability**
- ✅ Clustering and node management
- ✅ Queue mirroring vs quorum queues
- ✅ Federation and shovel
- ✅ Failover strategies

### **📊 Operations**
- ✅ Management API integration
- ✅ Monitoring and metrics collection
- ✅ Health checks and alerting
- ✅ Performance tuning

### **🔒 Security**
- ✅ Authentication methods
- ✅ Authorization and permissions
- ✅ TLS/SSL configuration
- ✅ Message encryption

### **💻 Real-World Examples**
- ✅ E-commerce order processing
- ✅ Microservices communication
- ✅ Real-time chat system
- ✅ Production-ready patterns

This guide serves as your comprehensive reference for implementing RabbitMQ in production environments at the staff engineer level. Each concept includes practical code examples and real-world usage patterns.

---

**🚀 Ready to implement RabbitMQ in your systems? Use this guide as your comprehensive reference!**