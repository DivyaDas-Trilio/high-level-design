# Module 2: Message Queue Technologies Deep Dive
## Mastering Apache Kafka, RabbitMQ, and Cloud Services

---

## 🎯 **Learning Objectives**
By the end of this module, you will:
- ✅ Master Apache Kafka architecture and operations at scale
- ✅ Implement reliable messaging patterns with RabbitMQ
- ✅ Design cloud-native solutions with AWS, GCP, and Azure services
- ✅ Make informed technology choices based on specific requirements
- ✅ Optimize performance and reliability for different use cases
- ✅ Implement monitoring and operational practices for each technology

---

## 📋 **Module Prerequisites**
- Completed Module 1: EDA Fundamentals
- Understanding of distributed systems concepts
- Basic knowledge of network protocols
- Experience with Docker and containerization
- Familiarity with cloud platforms (preferred but not required)

---

## 🚀 **Part 1: Apache Kafka Deep Dive**

### **1.1 Kafka Architecture Fundamentals**

Kafka is a distributed streaming platform designed for high-throughput, fault-tolerant event streaming.

#### **Core Components**

```
┌─────────────────────────────────────────────────────────────┐
│                    Kafka Cluster                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Broker 1  │  │   Broker 2  │  │   Broker 3  │        │
│  │             │  │             │  │             │        │
│  │ Topic A     │  │ Topic A     │  │ Topic A     │        │
│  │ Partition 0 │  │ Partition 1 │  │ Partition 2 │        │
│  │ (Leader)    │  │ (Follower)  │  │ (Leader)    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
            │                              │
    ┌─────────────┐                ┌─────────────┐
    │  Producer   │                │  Consumer   │
    │  Groups     │                │  Groups     │
    └─────────────┘                └─────────────┘
```

#### **Kafka Components Explained**

```python
# Kafka Core Concepts Implementation

from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum

class ReplicationFactor(Enum):
    DEVELOPMENT = 1
    STAGING = 2
    PRODUCTION = 3

@dataclass
class KafkaTopic:
    name: str
    partitions: int
    replication_factor: ReplicationFactor
    retention_hours: int = 168  # 7 days default
    cleanup_policy: str = "delete"  # or "compact"
    
    def __post_init__(self):
        if self.partitions < 1:
            raise ValueError("Topic must have at least 1 partition")
        if self.retention_hours < 1:
            raise ValueError("Retention must be positive")

@dataclass
class KafkaPartition:
    topic: str
    partition_id: int
    leader_broker: int
    replica_brokers: List[int]
    isr_brokers: List[int]  # In-Sync Replicas
    
    @property
    def is_healthy(self) -> bool:
        """Check if partition has sufficient replicas"""
        return len(self.isr_brokers) >= len(self.replica_brokers) // 2 + 1

class KafkaBroker:
    def __init__(self, broker_id: int, host: str, port: int = 9092):
        self.broker_id = broker_id
        self.host = host
        self.port = port
        self.topics: Dict[str, List[int]] = {}  # topic -> partition IDs
        self.is_controller = False
    
    def add_partition_leadership(self, topic: str, partition_id: int):
        if topic not in self.topics:
            self.topics[topic] = []
        self.topics[topic].append(partition_id)
    
    def get_partition_count(self) -> int:
        return sum(len(partitions) for partitions in self.topics.values())

# Example cluster setup
def create_kafka_cluster() -> List[KafkaBroker]:
    return [
        KafkaBroker(1, "kafka-1.example.com"),
        KafkaBroker(2, "kafka-2.example.com"),
        KafkaBroker(3, "kafka-3.example.com")
    ]
```

### **1.2 Advanced Kafka Producer Patterns**

#### **High-Performance Producer Configuration**

```python
from confluent_kafka import Producer
import asyncio
import json
from typing import Any, Dict, Optional, Callable
import structlog
from datetime import datetime

logger = structlog.get_logger()

class HighPerformanceKafkaProducer:
    """Production-ready Kafka producer with advanced features"""
    
    def __init__(
        self,
        bootstrap_servers: str,
        client_id: str = "high-perf-producer",
        **kwargs
    ):
        # Optimized configuration for high throughput
        self.config = {
            'bootstrap.servers': bootstrap_servers,
            'client.id': client_id,
            
            # Reliability settings
            'acks': 'all',  # Wait for all replicas
            'retries': 2147483647,  # Retry indefinitely
            'max.in.flight.requests.per.connection': 5,
            'enable.idempotence': True,  # Prevent duplicates
            
            # Performance optimization
            'compression.type': 'snappy',  # Good balance of speed/compression
            'batch.size': 65536,  # 64KB batch size
            'linger.ms': 10,  # Wait 10ms for batching
            'buffer.memory': 134217728,  # 128MB buffer
            
            # Timeout settings
            'request.timeout.ms': 30000,
            'delivery.timeout.ms': 300000,  # 5 minutes total
            'retry.backoff.ms': 100,
            
            # Custom settings
            **kwargs
        }
        
        self.producer = Producer(self.config)
        self.delivery_reports = {}
        
    async def produce_async(
        self,
        topic: str,
        value: Any,
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        partition: Optional[int] = None,
        callback: Optional[Callable] = None
    ) -> str:
        """Async producer with delivery confirmation"""
        
        message_id = f"{topic}-{datetime.utcnow().timestamp()}"
        future = asyncio.get_event_loop().create_future()
        self.delivery_reports[message_id] = future
        
        # Prepare message
        serialized_value = self._serialize_value(value)
        kafka_headers = self._prepare_headers(headers, message_id)
        
        try:
            self.producer.produce(
                topic=topic,
                value=serialized_value,
                key=key,
                headers=kafka_headers,
                partition=partition,
                callback=lambda err, msg: self._delivery_callback(
                    err, msg, message_id, callback
                )
            )
            
            # Poll to handle delivery reports
            self.producer.poll(0)
            
            # Wait for delivery confirmation
            await future
            
            logger.info(
                "Message produced successfully",
                topic=topic,
                message_id=message_id,
                partition=partition
            )
            
            return message_id
            
        except Exception as e:
            logger.error(
                "Failed to produce message",
                topic=topic,
                error=str(e),
                message_id=message_id
            )
            self.delivery_reports.pop(message_id, None)
            raise
    
    def produce_batch(
        self,
        messages: List[Dict[str, Any]],
        flush_timeout: float = 30.0
    ) -> List[str]:
        """Produce multiple messages efficiently"""
        
        message_ids = []
        
        for message in messages:
            try:
                message_id = f"batch-{datetime.utcnow().timestamp()}"
                message_ids.append(message_id)
                
                self.producer.produce(
                    topic=message['topic'],
                    value=self._serialize_value(message['value']),
                    key=message.get('key'),
                    headers=self._prepare_headers(message.get('headers'), message_id),
                    partition=message.get('partition'),
                    callback=lambda err, msg, mid=message_id: 
                        self._simple_delivery_callback(err, msg, mid)
                )
                
            except Exception as e:
                logger.error(f"Failed to produce message in batch: {e}")
                continue
        
        # Flush all messages
        unflushed_messages = self.producer.flush(timeout=flush_timeout)
        
        if unflushed_messages > 0:
            logger.warning(f"{unflushed_messages} messages failed to flush")
        
        return message_ids
    
    def _serialize_value(self, value: Any) -> bytes:
        """Serialize message value"""
        if isinstance(value, (dict, list)):
            return json.dumps(value, default=str).encode('utf-8')
        elif isinstance(value, str):
            return value.encode('utf-8')
        elif isinstance(value, bytes):
            return value
        else:
            return str(value).encode('utf-8')
    
    def _prepare_headers(
        self, 
        headers: Optional[Dict[str, str]], 
        message_id: str
    ) -> Dict[str, bytes]:
        """Prepare Kafka headers"""
        kafka_headers = {
            'message_id': message_id.encode(),
            'producer_timestamp': str(datetime.utcnow().timestamp()).encode(),
            'producer_id': self.config['client.id'].encode()
        }
        
        if headers:
            for k, v in headers.items():
                kafka_headers[k] = str(v).encode()
        
        return kafka_headers
    
    def _delivery_callback(
        self, 
        err, 
        msg, 
        message_id: str, 
        user_callback: Optional[Callable]
    ):
        """Handle delivery report"""
        future = self.delivery_reports.pop(message_id, None)
        
        if err:
            error_msg = f"Message delivery failed: {err}"
            logger.error(error_msg, message_id=message_id)
            if future:
                future.set_exception(Exception(error_msg))
        else:
            logger.debug(
                "Message delivered",
                topic=msg.topic(),
                partition=msg.partition(),
                offset=msg.offset(),
                message_id=message_id
            )
            if future:
                future.set_result(True)
        
        # Call user callback if provided
        if user_callback:
            try:
                user_callback(err, msg)
            except Exception as e:
                logger.error(f"Error in user callback: {e}")
    
    def _simple_delivery_callback(self, err, msg, message_id: str):
        """Simple callback for batch operations"""
        if err:
            logger.error(f"Batch message failed: {err}", message_id=message_id)
        else:
            logger.debug(f"Batch message delivered", message_id=message_id)
    
    def close(self):
        """Close producer"""
        unflushed = self.producer.flush(timeout=30)
        if unflushed > 0:
            logger.warning(f"{unflushed} messages were not flushed")
        
        logger.info("Kafka producer closed")


# Example usage
async def producer_example():
    producer = HighPerformanceKafkaProducer("localhost:9092")
    
    # Single message
    message_id = await producer.produce_async(
        topic="user-events",
        value={"user_id": "123", "action": "login"},
        key="user-123",
        headers={"source": "auth-service"}
    )
    
    # Batch messages
    messages = [
        {
            "topic": "user-events",
            "value": {"user_id": "124", "action": "signup"},
            "key": "user-124"
        },
        {
            "topic": "order-events", 
            "value": {"order_id": "ord-456", "status": "created"},
            "key": "ord-456"
        }
    ]
    
    batch_ids = producer.produce_batch(messages)
    
    producer.close()
```

### **1.3 Advanced Kafka Consumer Patterns**

#### **Scalable Consumer Implementation**

```python
from confluent_kafka import Consumer, TopicPartition
import asyncio
from typing import List, Dict, Callable, Optional, Set
from concurrent.futures import ThreadPoolExecutor
import signal
import sys

class ScalableKafkaConsumer:
    """Production-ready Kafka consumer with advanced patterns"""
    
    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str,
        topics: List[str],
        max_workers: int = 10,
        **kwargs
    ):
        self.config = {
            'bootstrap.servers': bootstrap_servers,
            'group.id': group_id,
            'auto.offset.reset': 'earliest',
            
            # Performance settings
            'fetch.min.bytes': 1024,  # 1KB minimum fetch
            'fetch.max.wait.ms': 500,  # Max wait for min bytes
            'max.partition.fetch.bytes': 1048576,  # 1MB per partition
            'session.timeout.ms': 30000,  # 30 second session timeout
            'heartbeat.interval.ms': 3000,  # Heartbeat every 3s
            
            # Reliability settings
            'enable.auto.commit': False,  # Manual commit for reliability
            'isolation.level': 'read_committed',  # Only read committed messages
            
            **kwargs
        }
        
        self.consumer = Consumer(self.config)
        self.topics = topics
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running = False
        self.message_handlers: Dict[str, Callable] = {}
        self.error_handlers: Dict[str, Callable] = {}
        
        # Metrics
        self.processed_count = 0
        self.error_count = 0
        
    def register_handler(self, topic: str, handler: Callable):
        """Register a message handler for a specific topic"""
        self.message_handlers[topic] = handler
    
    def register_error_handler(self, topic: str, error_handler: Callable):
        """Register an error handler for a specific topic"""
        self.error_handlers[topic] = error_handler
    
    async def start_consuming(self):
        """Start consuming messages with parallel processing"""
        
        try:
            self.consumer.subscribe(self.topics)
            self.running = True
            
            logger.info(
                "Started consuming",
                topics=self.topics,
                group_id=self.config['group.id'],
                max_workers=self.max_workers
            )
            
            # Set up graceful shutdown
            self._setup_signal_handlers()
            
            # Processing loop
            while self.running:
                try:
                    # Poll for messages
                    msg = self.consumer.poll(timeout=1.0)
                    
                    if msg is None:
                        continue
                    
                    if msg.error():
                        logger.error(f"Consumer error: {msg.error()}")
                        continue
                    
                    # Process message asynchronously
                    asyncio.create_task(self._process_message_async(msg))
                    
                except KeyboardInterrupt:
                    logger.info("Received interrupt signal")
                    break
                except Exception as e:
                    logger.error(f"Unexpected error in consumer loop: {e}")
                    await asyncio.sleep(1)
            
        finally:
            await self._cleanup()
    
    async def _process_message_async(self, msg):
        """Process a single message asynchronously"""
        
        topic = msg.topic()
        
        try:
            # Deserialize message
            message_data = self._deserialize_message(msg)
            
            # Get handler for topic
            handler = self.message_handlers.get(topic)
            if not handler:
                logger.warning(f"No handler registered for topic: {topic}")
                return
            
            # Process message in thread pool for CPU-intensive work
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor, 
                self._safe_handle_message, 
                handler, 
                message_data, 
                msg
            )
            
            # Commit offset after successful processing
            self.consumer.commit(msg)
            self.processed_count += 1
            
            logger.debug(
                "Message processed successfully",
                topic=topic,
                partition=msg.partition(),
                offset=msg.offset()
            )
            
        except Exception as e:
            self.error_count += 1
            logger.error(
                "Failed to process message",
                topic=topic,
                partition=msg.partition(),
                offset=msg.offset(),
                error=str(e)
            )
            
            # Handle error
            await self._handle_processing_error(msg, e)
    
    def _safe_handle_message(self, handler: Callable, message_data: Dict, msg):
        """Safely execute message handler"""
        try:
            handler(message_data, msg)
        except Exception as e:
            logger.error(f"Error in message handler: {e}")
            raise
    
    def _deserialize_message(self, msg) -> Dict:
        """Deserialize Kafka message"""
        try:
            # Extract headers
            headers = {}
            if msg.headers():
                headers = {
                    k: v.decode() if isinstance(v, bytes) else v 
                    for k, v in msg.headers()
                }
            
            # Deserialize value
            if msg.value():
                value = json.loads(msg.value().decode('utf-8'))
            else:
                value = None
            
            return {
                'topic': msg.topic(),
                'partition': msg.partition(),
                'offset': msg.offset(),
                'timestamp': msg.timestamp(),
                'key': msg.key().decode('utf-8') if msg.key() else None,
                'value': value,
                'headers': headers
            }
            
        except Exception as e:
            logger.error(f"Failed to deserialize message: {e}")
            raise
    
    async def _handle_processing_error(self, msg, error: Exception):
        """Handle message processing errors"""
        
        topic = msg.topic()
        error_handler = self.error_handlers.get(topic)
        
        if error_handler:
            try:
                # Run error handler in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    self.executor,
                    error_handler,
                    msg,
                    error
                )
            except Exception as e:
                logger.error(f"Error handler failed: {e}")
        
        # Could implement dead letter queue here
        # await self._send_to_dlq(msg, error)
    
    def _setup_signal_handlers(self):
        """Setup graceful shutdown signal handlers"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}")
            self.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def stop(self):
        """Stop consuming"""
        logger.info("Stopping consumer...")
        self.running = False
    
    async def _cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up consumer resources...")
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Close consumer
        self.consumer.close()
        
        logger.info(
            "Consumer cleanup complete",
            processed_count=self.processed_count,
            error_count=self.error_count
        )

# Consumer with manual partition assignment
class PartitionAwareConsumer:
    """Consumer with manual partition assignment for advanced use cases"""
    
    def __init__(self, bootstrap_servers: str, group_id: str):
        self.config = {
            'bootstrap.servers': bootstrap_servers,
            'group.id': group_id,
            'enable.auto.commit': False,
            'auto.offset.reset': 'earliest'
        }
        self.consumer = Consumer(self.config)
    
    async def consume_specific_partitions(
        self, 
        topic_partitions: List[TopicPartition],
        handler: Callable
    ):
        """Consume from specific partitions"""
        
        self.consumer.assign(topic_partitions)
        
        try:
            while True:
                msg = self.consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                
                if msg.error():
                    logger.error(f"Consumer error: {msg.error()}")
                    continue
                
                # Process message
                await handler(msg)
                
                # Commit offset
                self.consumer.commit(msg)
                
        except KeyboardInterrupt:
            logger.info("Stopping partition consumer")
        finally:
            self.consumer.close()

# Example usage
def example_message_handler(message_data: Dict, msg):
    """Example message handler"""
    logger.info(
        "Processing message",
        topic=message_data['topic'],
        key=message_data['key'],
        value=message_data['value']
    )
    
    # Simulate processing
    import time
    time.sleep(0.1)

def example_error_handler(msg, error: Exception):
    """Example error handler"""
    logger.error(
        "Message processing failed",
        topic=msg.topic(),
        partition=msg.partition(),
        offset=msg.offset(),
        error=str(error)
    )

async def consumer_example():
    consumer = ScalableKafkaConsumer(
        bootstrap_servers="localhost:9092",
        group_id="example-consumer-group",
        topics=["user-events", "order-events"],
        max_workers=5
    )
    
    # Register handlers
    consumer.register_handler("user-events", example_message_handler)
    consumer.register_handler("order-events", example_message_handler)
    consumer.register_error_handler("user-events", example_error_handler)
    
    # Start consuming
    await consumer.start_consuming()
```

### **1.4 Kafka Streams for Real-time Processing**

```python
from kafka import KafkaProducer, KafkaConsumer
from typing import Dict, Any, Callable, Optional
import json
from collections import defaultdict, deque
from datetime import datetime, timedelta
import asyncio

class KafkaStreamsProcessor:
    """Simple Kafka Streams-like processing in Python"""
    
    def __init__(self, bootstrap_servers: str, application_id: str):
        self.bootstrap_servers = bootstrap_servers
        self.application_id = application_id
        self.topology = StreamTopology()
        
    def stream(self, topic: str) -> 'KafkaStream':
        """Create a stream from a Kafka topic"""
        return KafkaStream(topic, self)
    
    def table(self, topic: str) -> 'KafkaTable':
        """Create a table from a compacted Kafka topic"""
        return KafkaTable(topic, self)
    
    async def start(self):
        """Start stream processing"""
        await self.topology.start_processing(self.bootstrap_servers, self.application_id)

class KafkaStream:
    """Stream processing operations"""
    
    def __init__(self, topic: str, processor: KafkaStreamsProcessor):
        self.topic = topic
        self.processor = processor
        self.operations = []
    
    def filter(self, predicate: Callable[[Dict], bool]) -> 'KafkaStream':
        """Filter records based on predicate"""
        self.operations.append(('filter', predicate))
        return self
    
    def map(self, mapper: Callable[[Dict], Dict]) -> 'KafkaStream':
        """Transform records"""
        self.operations.append(('map', mapper))
        return self
    
    def group_by_key(self) -> 'GroupedKafkaStream':
        """Group records by key"""
        return GroupedKafkaStream(self.topic, self.processor, self.operations)
    
    def to(self, output_topic: str):
        """Write stream to output topic"""
        self.operations.append(('to', output_topic))
        self.processor.topology.add_stream(self)

class GroupedKafkaStream:
    """Grouped stream for aggregations"""
    
    def __init__(self, topic: str, processor: KafkaStreamsProcessor, operations: list):
        self.topic = topic
        self.processor = processor
        self.operations = operations
    
    def count(self, window_size: timedelta = None) -> 'KafkaTable':
        """Count records in groups"""
        self.operations.append(('count', window_size))
        return KafkaTable(f"{self.topic}-count", self.processor, self.operations)
    
    def aggregate(
        self, 
        initializer: Callable[[], Any],
        aggregator: Callable[[Any, Dict], Any],
        window_size: timedelta = None
    ) -> 'KafkaTable':
        """Aggregate records in groups"""
        self.operations.append(('aggregate', {
            'initializer': initializer,
            'aggregator': aggregator,
            'window_size': window_size
        }))
        return KafkaTable(f"{self.topic}-agg", self.processor, self.operations)

class KafkaTable:
    """Table abstraction for stateful operations"""
    
    def __init__(self, topic: str, processor: KafkaStreamsProcessor, operations: list = None):
        self.topic = topic
        self.processor = processor
        self.operations = operations or []
    
    def to_stream(self) -> KafkaStream:
        """Convert table to stream"""
        stream = KafkaStream(self.topic, self.processor)
        stream.operations = self.operations.copy()
        return stream

class StreamTopology:
    """Manages stream processing topology"""
    
    def __init__(self):
        self.streams = []
        self.state_stores = defaultdict(dict)
        self.running = False
    
    def add_stream(self, stream: KafkaStream):
        self.streams.append(stream)
    
    async def start_processing(self, bootstrap_servers: str, application_id: str):
        """Start processing all streams"""
        self.running = True
        
        tasks = []
        for stream in self.streams:
            task = asyncio.create_task(
                self._process_stream(stream, bootstrap_servers, application_id)
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks)
    
    async def _process_stream(self, stream: KafkaStream, bootstrap_servers: str, application_id: str):
        """Process a single stream"""
        
        # Create consumer for input topic
        consumer = KafkaConsumer(
            stream.topic,
            bootstrap_servers=bootstrap_servers,
            group_id=f"{application_id}-{stream.topic}",
            auto_offset_reset='earliest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        
        # Create producer for output
        producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda x: json.dumps(x).encode('utf-8')
        )
        
        try:
            for message in consumer:
                if not self.running:
                    break
                
                # Process message through operations pipeline
                result = await self._apply_operations(
                    stream.operations, 
                    {
                        'key': message.key.decode('utf-8') if message.key else None,
                        'value': message.value,
                        'topic': message.topic,
                        'partition': message.partition,
                        'offset': message.offset,
                        'timestamp': message.timestamp
                    }
                )
                
                # Handle output
                if result and 'output_topic' in result:
                    producer.send(
                        result['output_topic'],
                        key=result.get('key'),
                        value=result.get('value')
                    )
        
        finally:
            consumer.close()
            producer.close()
    
    async def _apply_operations(self, operations: list, record: Dict) -> Optional[Dict]:
        """Apply stream operations to a record"""
        
        current_record = record
        
        for op_type, op_config in operations:
            if op_type == 'filter':
                if not op_config(current_record):
                    return None
                    
            elif op_type == 'map':
                current_record = op_config(current_record)
                
            elif op_type == 'count':
                window_size = op_config
                key = current_record['key']
                self._update_count(key, window_size)
                current_record['value'] = self.state_stores['count'][key]
                
            elif op_type == 'aggregate':
                key = current_record['key']
                initializer = op_config['initializer']
                aggregator = op_config['aggregator']
                window_size = op_config['window_size']
                
                if key not in self.state_stores['aggregate']:
                    self.state_stores['aggregate'][key] = initializer()
                
                self.state_stores['aggregate'][key] = aggregator(
                    self.state_stores['aggregate'][key],
                    current_record
                )
                current_record['value'] = self.state_stores['aggregate'][key]
                
            elif op_type == 'to':
                current_record['output_topic'] = op_config
        
        return current_record
    
    def _update_count(self, key: str, window_size: Optional[timedelta]):
        """Update count for a key"""
        if key not in self.state_stores['count']:
            self.state_stores['count'][key] = 0
        self.state_stores['count'][key] += 1

# Example: Real-time analytics pipeline
async def kafka_streams_example():
    """Example of real-time order analytics"""
    
    processor = KafkaStreamsProcessor("localhost:9092", "order-analytics")
    
    # Process order events
    (processor
        .stream("order-events")
        .filter(lambda record: record['value']['status'] == 'completed')
        .map(lambda record: {
            **record,
            'value': {
                'customer_id': record['value']['customer_id'],
                'amount': record['value']['total_amount'],
                'timestamp': record['timestamp']
            }
        })
        .group_by_key()
        .aggregate(
            initializer=lambda: {'total_amount': 0, 'order_count': 0},
            aggregator=lambda agg, record: {
                'total_amount': agg['total_amount'] + record['value']['amount'],
                'order_count': agg['order_count'] + 1
            }
        )
        .to_stream()
        .to("customer-analytics"))
    
    # Start processing
    await processor.start()

# Real-world example: Fraud detection
class FraudDetectionProcessor:
    """Real-time fraud detection using Kafka Streams"""
    
    def __init__(self, bootstrap_servers: str):
        self.bootstrap_servers = bootstrap_servers
        self.transaction_windows = defaultdict(lambda: deque())
        self.fraud_thresholds = {
            'max_amount': 10000,
            'max_transactions_per_minute': 10,
            'velocity_threshold': 5000  # Max spending in 5 minutes
        }
    
    async def start_fraud_detection(self):
        """Start fraud detection pipeline"""
        
        consumer = KafkaConsumer(
            'payment-events',
            bootstrap_servers=self.bootstrap_servers,
            group_id='fraud-detection',
            auto_offset_reset='latest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        
        producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda x: json.dumps(x).encode('utf-8')
        )
        
        try:
            for message in consumer:
                transaction = message.value
                
                # Analyze transaction for fraud
                fraud_score = await self._analyze_transaction(transaction)
                
                if fraud_score > 0.8:  # High fraud probability
                    # Send to fraud alerts topic
                    alert = {
                        'transaction_id': transaction['transaction_id'],
                        'customer_id': transaction['customer_id'],
                        'amount': transaction['amount'],
                        'fraud_score': fraud_score,
                        'timestamp': datetime.utcnow().isoformat(),
                        'reasons': self._get_fraud_reasons(transaction)
                    }
                    
                    producer.send('fraud-alerts', value=alert)
                    
                    logger.warning(
                        "Potential fraud detected",
                        transaction_id=transaction['transaction_id'],
                        fraud_score=fraud_score
                    )
        
        finally:
            consumer.close()
            producer.close()
    
    async def _analyze_transaction(self, transaction: Dict) -> float:
        """Analyze transaction and return fraud score (0-1)"""
        
        customer_id = transaction['customer_id']
        amount = transaction['amount']
        timestamp = datetime.fromisoformat(transaction['timestamp'])
        
        fraud_indicators = []
        
        # Check amount threshold
        if amount > self.fraud_thresholds['max_amount']:
            fraud_indicators.append(('high_amount', 0.7))
        
        # Check transaction velocity
        self._update_transaction_window(customer_id, timestamp, amount)
        recent_transactions = self._get_recent_transactions(customer_id, timestamp, minutes=1)
        
        if len(recent_transactions) > self.fraud_thresholds['max_transactions_per_minute']:
            fraud_indicators.append(('high_velocity', 0.8))
        
        # Check spending velocity
        recent_spending = sum(t['amount'] for t in self._get_recent_transactions(customer_id, timestamp, minutes=5))
        if recent_spending > self.fraud_thresholds['velocity_threshold']:
            fraud_indicators.append(('high_spending_velocity', 0.6))
        
        # Calculate overall fraud score
        if not fraud_indicators:
            return 0.0
        
        # Take maximum fraud score (could use more sophisticated logic)
        return max(score for _, score in fraud_indicators)
    
    def _update_transaction_window(self, customer_id: str, timestamp: datetime, amount: float):
        """Update sliding window of transactions for customer"""
        
        window = self.transaction_windows[customer_id]
        window.append({
            'timestamp': timestamp,
            'amount': amount
        })
        
        # Remove old transactions (older than 5 minutes)
        cutoff_time = timestamp - timedelta(minutes=5)
        while window and window[0]['timestamp'] < cutoff_time:
            window.popleft()
    
    def _get_recent_transactions(self, customer_id: str, current_time: datetime, minutes: int) -> List[Dict]:
        """Get transactions within specified time window"""
        
        cutoff_time = current_time - timedelta(minutes=minutes)
        window = self.transaction_windows[customer_id]
        
        return [t for t in window if t['timestamp'] >= cutoff_time]
    
    def _get_fraud_reasons(self, transaction: Dict) -> List[str]:
        """Get human-readable fraud reasons"""
        reasons = []
        
        if transaction['amount'] > self.fraud_thresholds['max_amount']:
            reasons.append(f"High transaction amount: ${transaction['amount']}")
        
        # Add more specific fraud reasons based on analysis
        
        return reasons
```

---

## 🐰 **Part 2: RabbitMQ Advanced Patterns**

### **2.1 RabbitMQ Architecture and Exchange Types**

```python
import pika
import json
import asyncio
import aio_pika
from typing import Dict, Any, Callable, Optional, List
from enum import Enum
from dataclasses import dataclass

class ExchangeType(Enum):
    DIRECT = "direct"
    TOPIC = "topic"
    FANOUT = "fanout"
    HEADERS = "headers"

@dataclass
class QueueConfig:
    name: str
    durable: bool = True
    exclusive: bool = False
    auto_delete: bool = False
    arguments: Dict[str, Any] = None

@dataclass
class ExchangeConfig:
    name: str
    type: ExchangeType
    durable: bool = True
    auto_delete: bool = False
    arguments: Dict[str, Any] = None

class RabbitMQConnection:
    """Production-ready RabbitMQ connection management"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5672,
        username: str = "guest",
        password: str = "guest",
        virtual_host: str = "/",
        **kwargs
    ):
        self.connection_params = pika.ConnectionParameters(
            host=host,
            port=port,
            virtual_host=virtual_host,
            credentials=pika.PlainCredentials(username, password),
            heartbeat=600,  # 10 minute heartbeat
            blocked_connection_timeout=300,  # 5 minute timeout
            **kwargs
        )
        self.connection = None
        self.channel = None
    
    def connect(self):
        """Establish connection to RabbitMQ"""
        try:
            self.connection = pika.BlockingConnection(self.connection_params)
            self.channel = self.connection.channel()
            
            # Enable publisher confirms for reliability
            self.channel.confirm_delivery()
            
            logger.info("Connected to RabbitMQ")
            
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    def disconnect(self):
        """Close connection"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("Disconnected from RabbitMQ")
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

class RabbitMQPublisher:
    """Advanced RabbitMQ publisher with reliability features"""
    
    def __init__(self, connection: RabbitMQConnection):
        self.connection = connection
        self.mandatory = True  # Return unroutable messages
        
    def setup_topology(
        self, 
        exchanges: List[ExchangeConfig], 
        queues: List[QueueConfig],
        bindings: List[Dict[str, str]]
    ):
        """Setup exchanges, queues, and bindings"""
        
        channel = self.connection.channel
        
        # Declare exchanges
        for exchange in exchanges:
            channel.exchange_declare(
                exchange=exchange.name,
                exchange_type=exchange.type.value,
                durable=exchange.durable,
                auto_delete=exchange.auto_delete,
                arguments=exchange.arguments
            )
            logger.info(f"Declared exchange: {exchange.name}")
        
        # Declare queues
        for queue in queues:
            channel.queue_declare(
                queue=queue.name,
                durable=queue.durable,
                exclusive=queue.exclusive,
                auto_delete=queue.auto_delete,
                arguments=queue.arguments
            )
            logger.info(f"Declared queue: {queue.name}")
        
        # Setup bindings
        for binding in bindings:
            channel.queue_bind(
                exchange=binding['exchange'],
                queue=binding['queue'],
                routing_key=binding.get('routing_key', ''),
                arguments=binding.get('arguments')
            )
            logger.info(f"Bound queue {binding['queue']} to exchange {binding['exchange']}")
    
    def publish_message(
        self,
        exchange: str,
        routing_key: str,
        message: Dict[str, Any],
        properties: Optional[pika.BasicProperties] = None,
        mandatory: bool = None
    ) -> bool:
        """Publish message with delivery confirmation"""
        
        channel = self.connection.channel
        mandatory = mandatory if mandatory is not None else self.mandatory
        
        # Default properties
        if properties is None:
            properties = pika.BasicProperties(
                delivery_mode=2,  # Persistent message
                timestamp=int(datetime.utcnow().timestamp()),
                message_id=str(uuid4()),
                content_type='application/json'
            )
        
        try:
            # Serialize message
            body = json.dumps(message, default=str).encode()
            
            # Publish with confirmation
            confirmed = channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=body,
                properties=properties,
                mandatory=mandatory
            )
            
            if confirmed:
                logger.debug(
                    "Message published successfully",
                    exchange=exchange,
                    routing_key=routing_key,
                    message_id=properties.message_id
                )
                return True
            else:
                logger.error(
                    "Message publication not confirmed",
                    exchange=exchange,
                    routing_key=routing_key
                )
                return False
                
        except pika.exceptions.UnroutableError:
            logger.error(
                "Message was returned as unroutable",
                exchange=exchange,
                routing_key=routing_key
            )
            return False
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            return False

class RabbitMQConsumer:
    """Advanced RabbitMQ consumer with error handling and retry logic"""
    
    def __init__(
        self, 
        connection: RabbitMQConnection,
        queue: str,
        prefetch_count: int = 10
    ):
        self.connection = connection
        self.queue = queue
        self.prefetch_count = prefetch_count
        self.message_handlers: Dict[str, Callable] = {}
        self.error_handlers: Dict[str, Callable] = {}
        self.consuming = False
    
    def register_handler(self, message_type: str, handler: Callable):
        """Register handler for specific message type"""
        self.message_handlers[message_type] = handler
    
    def register_error_handler(self, message_type: str, error_handler: Callable):
        """Register error handler for specific message type"""
        self.error_handlers[message_type] = error_handler
    
    def start_consuming(self):
        """Start consuming messages"""
        
        channel = self.connection.channel
        
        # Set QoS to control message prefetching
        channel.basic_qos(prefetch_count=self.prefetch_count)
        
        # Setup consumer
        channel.basic_consume(
            queue=self.queue,
            on_message_callback=self._on_message_callback,
            auto_ack=False  # Manual acknowledgment
        )
        
        self.consuming = True
        logger.info(f"Started consuming from queue: {self.queue}")
        
        try:
            channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Stopping consumer...")
            self.stop_consuming()
    
    def stop_consuming(self):
        """Stop consuming messages"""
        if self.consuming:
            self.connection.channel.stop_consuming()
            self.consuming = False
            logger.info("Stopped consuming")
    
    def _on_message_callback(self, channel, method, properties, body):
        """Handle incoming message"""
        
        try:
            # Deserialize message
            message = json.loads(body.decode())
            
            # Extract message type from headers or properties
            message_type = self._extract_message_type(properties, message)
            
            # Get handler
            handler = self.message_handlers.get(message_type)
            if not handler:
                logger.warning(f"No handler for message type: {message_type}")
                channel.basic_nack(method.delivery_tag, requeue=False)
                return
            
            # Process message
            success = self._process_message(handler, message, properties)
            
            if success:
                # Acknowledge message
                channel.basic_ack(method.delivery_tag)
                logger.debug(f"Message processed successfully: {properties.message_id}")
            else:
                # Handle processing failure
                self._handle_processing_failure(
                    channel, method, properties, message, message_type
                )
                
        except json.JSONDecodeError:
            logger.error("Failed to decode message JSON")
            channel.basic_nack(method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error(f"Unexpected error processing message: {e}")
            channel.basic_nack(method.delivery_tag, requeue=False)
    
    def _extract_message_type(self, properties, message):
        """Extract message type from properties or message content"""
        
        # Try to get from headers
        if properties.headers and 'message_type' in properties.headers:
            return properties.headers['message_type']
        
        # Try to get from message content
        if isinstance(message, dict) and 'type' in message:
            return message['type']
        
        # Default
        return 'unknown'
    
    def _process_message(self, handler: Callable, message: Dict, properties) -> bool:
        """Process message with error handling"""
        
        try:
            handler(message, properties)
            return True
        except Exception as e:
            logger.error(f"Handler error: {e}")
            return False
    
    def _handle_processing_failure(
        self, 
        channel, 
        method, 
        properties, 
        message, 
        message_type
    ):
        """Handle message processing failure"""
        
        # Get retry count from headers
        retry_count = 0
        if properties.headers and 'retry_count' in properties.headers:
            retry_count = properties.headers['retry_count']
        
        max_retries = 3
        
        if retry_count < max_retries:
            # Retry message
            self._retry_message(channel, method, properties, message, retry_count + 1)
        else:
            # Send to dead letter queue or call error handler
            error_handler = self.error_handlers.get(message_type)
            if error_handler:
                try:
                    error_handler(message, properties, f"Max retries exceeded")
                except Exception as e:
                    logger.error(f"Error handler failed: {e}")
            
            # Reject message (will go to DLQ if configured)
            channel.basic_nack(method.delivery_tag, requeue=False)
    
    def _retry_message(self, channel, method, properties, message, retry_count):
        """Retry message with exponential backoff"""
        
        # Calculate delay
        delay = min(2 ** retry_count, 60)  # Max 60 seconds
        
        # Update headers
        headers = properties.headers or {}
        headers['retry_count'] = retry_count
        headers['original_message_id'] = properties.message_id
        
        # Create new properties
        new_properties = pika.BasicProperties(
            headers=headers,
            delivery_mode=properties.delivery_mode,
            timestamp=int((datetime.utcnow() + timedelta(seconds=delay)).timestamp()),
            message_id=str(uuid4()),
            content_type=properties.content_type
        )
        
        # Publish to retry exchange/queue
        # This would typically go to a delayed exchange or TTL queue
        retry_exchange = f"{self.queue}-retry"
        
        try:
            channel.basic_publish(
                exchange=retry_exchange,
                routing_key=self.queue,
                body=json.dumps(message).encode(),
                properties=new_properties
            )
            
            # Acknowledge original message
            channel.basic_ack(method.delivery_tag)
            
            logger.info(
                f"Message scheduled for retry #{retry_count}",
                message_id=properties.message_id,
                delay=delay
            )
            
        except Exception as e:
            logger.error(f"Failed to schedule retry: {e}")
            channel.basic_nack(method.delivery_tag, requeue=False)

# Advanced routing patterns
class AdvancedRabbitMQPatterns:
    """Advanced RabbitMQ messaging patterns"""
    
    @staticmethod
    def setup_work_queue_pattern(connection: RabbitMQConnection, queue_name: str):
        """Setup work queue pattern for task distribution"""
        
        publisher = RabbitMQPublisher(connection)
        
        # Setup topology
        queues = [
            QueueConfig(
                name=queue_name,
                durable=True,
                arguments={
                    'x-dead-letter-exchange': f"{queue_name}-dlx",
                    'x-dead-letter-routing-key': f"{queue_name}-dlq"
                }
            ),
            QueueConfig(name=f"{queue_name}-dlq", durable=True)  # Dead letter queue
        ]
        
        exchanges = [
            ExchangeConfig(name=f"{queue_name}-dlx", type=ExchangeType.DIRECT)
        ]
        
        bindings = [
            {
                'exchange': f"{queue_name}-dlx",
                'queue': f"{queue_name}-dlq",
                'routing_key': f"{queue_name}-dlq"
            }
        ]
        
        publisher.setup_topology(exchanges, queues, bindings)
        
        return publisher
    
    @staticmethod
    def setup_pub_sub_pattern(
        connection: RabbitMQConnection, 
        exchange_name: str, 
        subscriber_queues: List[str]
    ):
        """Setup publish/subscribe pattern"""
        
        publisher = RabbitMQPublisher(connection)
        
        # Setup fanout exchange
        exchanges = [
            ExchangeConfig(name=exchange_name, type=ExchangeType.FANOUT)
        ]
        
        # Setup subscriber queues
        queues = [
            QueueConfig(name=queue_name, durable=True, exclusive=False)
            for queue_name in subscriber_queues
        ]
        
        # Bind all queues to the fanout exchange
        bindings = [
            {
                'exchange': exchange_name,
                'queue': queue_name,
                'routing_key': ''  # Fanout ignores routing key
            }
            for queue_name in subscriber_queues
        ]
        
        publisher.setup_topology(exchanges, queues, bindings)
        return publisher
    
    @staticmethod
    def setup_topic_routing_pattern(
        connection: RabbitMQConnection,
        exchange_name: str,
        topic_bindings: Dict[str, str]  # queue_name -> routing_pattern
    ):
        """Setup topic-based routing pattern"""
        
        publisher = RabbitMQPublisher(connection)
        
        exchanges = [
            ExchangeConfig(name=exchange_name, type=ExchangeType.TOPIC)
        ]
        
        queues = [
            QueueConfig(name=queue_name, durable=True)
            for queue_name in topic_bindings.keys()
        ]
        
        bindings = [
            {
                'exchange': exchange_name,
                'queue': queue_name,
                'routing_key': routing_pattern
            }
            for queue_name, routing_pattern in topic_bindings.items()
        ]
        
        publisher.setup_topology(exchanges, queues, bindings)
        return publisher

# Example usage
def rabbitmq_example():
    """Example of advanced RabbitMQ usage"""
    
    # Setup connection
    with RabbitMQConnection() as conn:
        
        # 1. Work Queue Pattern
        work_queue_publisher = AdvancedRabbitMQPatterns.setup_work_queue_pattern(
            conn, "image-processing-tasks"
        )
        
        # Publish work tasks
        for i in range(10):
            task = {
                'task_id': f"task-{i}",
                'image_url': f"https://example.com/image-{i}.jpg",
                'operations': ['resize', 'watermark', 'compress']
            }
            
            work_queue_publisher.publish_message(
                exchange='',  # Default exchange
                routing_key='image-processing-tasks',
                message=task
            )
        
        # 2. Pub/Sub Pattern
        pub_sub_publisher = AdvancedRabbitMQPatterns.setup_pub_sub_pattern(
            conn, 
            "user-events",
            ["analytics-service", "notification-service", "audit-service"]
        )
        
        # Publish event to all subscribers
        user_event = {
            'event_type': 'user_registered',
            'user_id': 'user-123',
            'timestamp': datetime.utcnow().isoformat(),
            'data': {
                'email': 'user@example.com',
                'registration_source': 'web'
            }
        }
        
        pub_sub_publisher.publish_message(
            exchange="user-events",
            routing_key='',
            message=user_event
        )
        
        # 3. Topic Routing Pattern
        topic_bindings = {
            'order-processing': 'order.created',
            'inventory-updates': 'order.*',
            'customer-notifications': '*.created',
            'analytics-all': '#'  # All messages
        }
        
        topic_publisher = AdvancedRabbitMQPatterns.setup_topic_routing_pattern(
            conn, "business-events", topic_bindings
        )
        
        # Publish different types of events
        events = [
            ('order.created', {'order_id': 'ord-123', 'customer_id': 'cust-456'}),
            ('order.shipped', {'order_id': 'ord-123', 'tracking_number': 'TRK789'}),
            ('user.created', {'user_id': 'user-789', 'email': 'new@example.com'})
        ]
        
        for routing_key, event_data in events:
            topic_publisher.publish_message(
                exchange="business-events",
                routing_key=routing_key,
                message=event_data
            )
        
        logger.info("Published all example messages")

if __name__ == "__main__":
    rabbitmq_example()
```

---

## ☁️ **Part 3: Cloud Message Services**

### **3.1 AWS SQS/SNS/EventBridge Patterns**

```python
import boto3
import json
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from botocore.exceptions import ClientError
import asyncio
import aioboto3

@dataclass
class SQSConfig:
    queue_name: str
    visibility_timeout: int = 30
    message_retention_period: int = 1209600  # 14 days
    receive_message_wait_time: int = 20  # Long polling
    dead_letter_queue: Optional[str] = None
    max_receive_count: int = 3

@dataclass
class SNSConfig:
    topic_name: str
    display_name: Optional[str] = None
    delivery_policy: Optional[Dict] = None
    message_retention_period: Optional[int] = None

class AWSMessageService:
    """Unified AWS messaging service wrapper"""
    
    def __init__(self, region_name: str = 'us-east-1'):
        self.region_name = region_name
        self.sqs_client = boto3.client('sqs', region_name=region_name)
        self.sns_client = boto3.client('sns', region_name=region_name)
        self.eventbridge_client = boto3.client('events', region_name=region_name)
        
        # Cache for queue and topic URLs/ARNs
        self.queue_urls = {}
        self.topic_arns = {}
    
    def create_sqs_queue(self, config: SQSConfig) -> str:
        """Create SQS queue with advanced configuration"""
        
        attributes = {
            'VisibilityTimeoutSeconds': str(config.visibility_timeout),
            'MessageRetentionPeriod': str(config.message_retention_period),
            'ReceiveMessageWaitTimeSeconds': str(config.receive_message_wait_time),
            'DelaySeconds': '0',
        }
        
        # Setup dead letter queue if specified
        if config.dead_letter_queue:
            dlq_url = self.create_dlq(config.dead_letter_queue)
            dlq_arn = self.get_queue_arn(dlq_url)
            
            redrive_policy = {
                'deadLetterTargetArn': dlq_arn,
                'maxReceiveCount': config.max_receive_count
            }
            attributes['RedrivePolicy'] = json.dumps(redrive_policy)
        
        try:
            response = self.sqs_client.create_queue(
                QueueName=config.queue_name,
                Attributes=attributes
            )
            
            queue_url = response['QueueUrl']
            self.queue_urls[config.queue_name] = queue_url
            
            logger.info(f"Created SQS queue: {config.queue_name}")
            return queue_url
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'QueueAlreadyExists':
                queue_url = self.sqs_client.get_queue_url(
                    QueueName=config.queue_name
                )['QueueUrl']
                self.queue_urls[config.queue_name] = queue_url
                return queue_url
            else:
                logger.error(f"Failed to create queue: {e}")
                raise
    
    def create_dlq(self, dlq_name: str) -> str:
        """Create dead letter queue"""
        
        dlq_config = SQSConfig(
            queue_name=dlq_name,
            message_retention_period=1209600,  # 14 days
            dead_letter_queue=None  # No DLQ for DLQ
        )
        return self.create_sqs_queue(dlq_config)
    
    def create_sns_topic(self, config: SNSConfig) -> str:
        """Create SNS topic"""
        
        attributes = {}
        
        if config.display_name:
            attributes['DisplayName'] = config.display_name
        
        if config.delivery_policy:
            attributes['DeliveryPolicy'] = json.dumps(config.delivery_policy)
        
        try:
            response = self.sns_client.create_topic(
                Name=config.topic_name,
                Attributes=attributes
            )
            
            topic_arn = response['TopicArn']
            self.topic_arns[config.topic_name] = topic_arn
            
            logger.info(f"Created SNS topic: {config.topic_name}")
            return topic_arn
            
        except ClientError as e:
            logger.error(f"Failed to create topic: {e}")
            raise
    
    def subscribe_sqs_to_sns(self, queue_name: str, topic_name: str) -> str:
        """Subscribe SQS queue to SNS topic"""
        
        queue_url = self.queue_urls.get(queue_name)
        topic_arn = self.topic_arns.get(topic_name)
        
        if not queue_url or not topic_arn:
            raise ValueError("Queue or topic not found")
        
        queue_arn = self.get_queue_arn(queue_url)
        
        # Subscribe queue to topic
        subscription = self.sns_client.subscribe(
            TopicArn=topic_arn,
            Protocol='sqs',
            Endpoint=queue_arn
        )
        
        # Set queue policy to allow SNS to send messages
        self.set_sqs_policy_for_sns(queue_url, queue_arn, topic_arn)
        
        logger.info(f"Subscribed queue {queue_name} to topic {topic_name}")
        return subscription['SubscriptionArn']
    
    def set_sqs_policy_for_sns(self, queue_url: str, queue_arn: str, topic_arn: str):
        """Set SQS policy to allow SNS access"""
        
        policy = {
            "Version": "2012-10-17",
            "Id": f"{queue_arn}/SQSDefaultPolicy",
            "Statement": [
                {
                    "Sid": "AllowSNSAccess",
                    "Effect": "Allow",
                    "Principal": {"Service": "sns.amazonaws.com"},
                    "Action": "sqs:SendMessage",
                    "Resource": queue_arn,
                    "Condition": {
                        "ArnEquals": {
                            "aws:SourceArn": topic_arn
                        }
                    }
                }
            ]
        }
        
        self.sqs_client.set_queue_attributes(
            QueueUrl=queue_url,
            Attributes={
                'Policy': json.dumps(policy)
            }
        )
    
    def get_queue_arn(self, queue_url: str) -> str:
        """Get queue ARN from URL"""
        
        attributes = self.sqs_client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['QueueArn']
        )
        return attributes['Attributes']['QueueArn']

class HighPerformanceSQSProducer:
    """High-performance SQS message producer"""
    
    def __init__(self, region_name: str = 'us-east-1'):
        self.session = aioboto3.Session()
        self.region_name = region_name
    
    async def send_message(
        self,
        queue_url: str,
        message_body: Dict[str, Any],
        message_attributes: Optional[Dict[str, Any]] = None,
        delay_seconds: int = 0
    ) -> str:
        """Send single message to SQS"""
        
        async with self.session.client('sqs', region_name=self.region_name) as sqs:
            
            # Prepare message attributes
            sqs_attributes = {}
            if message_attributes:
                for key, value in message_attributes.items():
                    sqs_attributes[key] = {
                        'StringValue': str(value),
                        'DataType': 'String'
                    }
            
            try:
                response = await sqs.send_message(
                    QueueUrl=queue_url,
                    MessageBody=json.dumps(message_body, default=str),
                    MessageAttributes=sqs_attributes,
                    DelaySeconds=delay_seconds
                )
                
                logger.debug(f"Message sent: {response['MessageId']}")
                return response['MessageId']
                
            except ClientError as e:
                logger.error(f"Failed to send message: {e}")
                raise
    
    async def send_message_batch(
        self,
        queue_url: str,
        messages: List[Dict[str, Any]],
        batch_size: int = 10
    ) -> List[str]:
        """Send multiple messages in batches (max 10 per batch for SQS)"""
        
        message_ids = []
        
        async with self.session.client('sqs', region_name=self.region_name) as sqs:
            
            # Process in batches of 10 (SQS limit)
            for i in range(0, len(messages), batch_size):
                batch = messages[i:i + batch_size]
                
                # Prepare batch entries
                entries = []
                for idx, message in enumerate(batch):
                    entry = {
                        'Id': f"msg-{i + idx}",
                        'MessageBody': json.dumps(message['body'], default=str)
                    }
                    
                    # Add message attributes if present
                    if 'attributes' in message:
                        entry['MessageAttributes'] = {
                            key: {'StringValue': str(value), 'DataType': 'String'}
                            for key, value in message['attributes'].items()
                        }
                    
                    # Add delay if specified
                    if 'delay_seconds' in message:
                        entry['DelaySeconds'] = message['delay_seconds']
                    
                    entries.append(entry)
                
                try:
                    response = await sqs.send_message_batch(
                        QueueUrl=queue_url,
                        Entries=entries
                    )
                    
                    # Collect successful message IDs
                    for success in response.get('Successful', []):
                        message_ids.append(success['MessageId'])
                    
                    # Log any failures
                    for failure in response.get('Failed', []):
                        logger.error(
                            f"Batch message failed: {failure['Code']} - {failure['Message']}"
                        )
                
                except ClientError as e:
                    logger.error(f"Batch send failed: {e}")
                    continue
        
        return message_ids

class SQSConsumer:
    """High-performance SQS consumer with parallel processing"""
    
    def __init__(
        self,
        queue_url: str,
        region_name: str = 'us-east-1',
        max_concurrent_messages: int = 10
    ):
        self.queue_url = queue_url
        self.region_name = region_name
        self.max_concurrent_messages = max_concurrent_messages
        self.message_handlers: Dict[str, Callable] = {}
        self.running = False
    
    def register_handler(self, message_type: str, handler: Callable):
        """Register message handler for specific message type"""
        self.message_handlers[message_type] = handler
    
    async def start_consuming(self):
        """Start consuming messages with parallel processing"""
        
        self.running = True
        
        async with aioboto3.Session().client('sqs', region_name=self.region_name) as sqs:
            
            logger.info(f"Started consuming from SQS queue: {self.queue_url}")
            
            # Create semaphore to limit concurrent processing
            semaphore = asyncio.Semaphore(self.max_concurrent_messages)
            
            while self.running:
                try:
                    # Receive messages (up to 10 at a time)
                    response = await sqs.receive_message(
                        QueueUrl=self.queue_url,
                        MaxNumberOfMessages=10,
                        WaitTimeSeconds=20,  # Long polling
                        MessageAttributeNames=['All'],
                        AttributeNames=['All']
                    )
                    
                    messages = response.get('Messages', [])
                    
                    if not messages:
                        continue
                    
                    # Process messages concurrently
                    tasks = [
                        asyncio.create_task(
                            self._process_message_with_semaphore(sqs, message, semaphore)
                        )
                        for message in messages
                    ]
                    
                    await asyncio.gather(*tasks, return_exceptions=True)
                    
                except Exception as e:
                    logger.error(f"Error in consumer loop: {e}")
                    await asyncio.sleep(1)
    
    async def _process_message_with_semaphore(self, sqs, message, semaphore):
        """Process message with concurrency control"""
        
        async with semaphore:
            await self._process_message(sqs, message)
    
    async def _process_message(self, sqs, message):
        """Process a single SQS message"""
        
        try:
            # Parse message body
            body = json.loads(message['Body'])
            
            # Handle SNS-wrapped messages
            if 'Type' in body and body['Type'] == 'Notification':
                # This is an SNS message
                actual_message = json.loads(body['Message'])
                message_type = body.get('Subject', 'unknown')
            else:
                # Direct SQS message
                actual_message = body
                message_type = message.get('MessageAttributes', {}).get(
                    'message_type', {}
                ).get('StringValue', 'unknown')
            
            # Get handler
            handler = self.message_handlers.get(message_type)
            if not handler:
                logger.warning(f"No handler for message type: {message_type}")
                await self._delete_message(sqs, message)
                return
            
            # Process message
            success = await self._safe_handle_message(handler, actual_message, message)
            
            if success:
                # Delete message from queue
                await self._delete_message(sqs, message)
                logger.debug(f"Message processed and deleted: {message['MessageId']}")
            else:
                logger.error(f"Message processing failed: {message['MessageId']}")
                # Message will become visible again after visibility timeout
        
        except Exception as e:
            logger.error(f"Error processing message {message['MessageId']}: {e}")
    
    async def _safe_handle_message(self, handler: Callable, message: Dict, raw_message) -> bool:
        """Safely execute message handler"""
        
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(message, raw_message)
            else:
                handler(message, raw_message)
            return True
        except Exception as e:
            logger.error(f"Handler error: {e}")
            return False
    
    async def _delete_message(self, sqs, message):
        """Delete processed message"""
        
        try:
            await sqs.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=message['ReceiptHandle']
            )
        except ClientError as e:
            logger.error(f"Failed to delete message: {e}")
    
    def stop(self):
        """Stop consuming"""
        self.running = False
        logger.info("SQS consumer stopped")

# EventBridge patterns
class EventBridgeService:
    """AWS EventBridge service wrapper"""
    
    def __init__(self, region_name: str = 'us-east-1'):
        self.client = boto3.client('events', region_name=region_name)
        self.region_name = region_name
    
    def create_custom_event_bus(self, name: str, tags: Optional[Dict[str, str]] = None) -> str:
        """Create custom event bus"""
        
        try:
            response = self.client.create_event_bus(Name=name)
            
            # Add tags if provided
            if tags:
                self.client.tag_resource(
                    ResourceARN=response['EventBusArn'],
                    Tags=[{'Key': k, 'Value': v} for k, v in tags.items()]
                )
            
            logger.info(f"Created EventBridge bus: {name}")
            return response['EventBusArn']
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceAlreadyExistsException':
                # Bus already exists
                buses = self.client.list_event_buses(NamePrefix=name)
                for bus in buses['EventBuses']:
                    if bus['Name'] == name:
                        return bus['Arn']
            logger.error(f"Failed to create event bus: {e}")
            raise
    
    def create_rule(
        self,
        name: str,
        event_pattern: Dict[str, Any],
        targets: List[Dict[str, Any]],
        event_bus_name: str = 'default',
        description: Optional[str] = None
    ) -> str:
        """Create EventBridge rule with targets"""
        
        try:
            # Create rule
            rule_args = {
                'Name': name,
                'EventPattern': json.dumps(event_pattern),
                'State': 'ENABLED'
            }
            
            if event_bus_name != 'default':
                rule_args['EventBusName'] = event_bus_name
            
            if description:
                rule_args['Description'] = description
            
            response = self.client.put_rule(**rule_args)
            rule_arn = response['RuleArn']
            
            # Add targets
            self.client.put_targets(
                Rule=name,
                EventBusName=event_bus_name,
                Targets=targets
            )
            
            logger.info(f"Created EventBridge rule: {name}")
            return rule_arn
            
        except ClientError as e:
            logger.error(f"Failed to create rule: {e}")
            raise
    
    def publish_event(
        self,
        source: str,
        detail_type: str,
        detail: Dict[str, Any],
        event_bus_name: str = 'default',
        resources: Optional[List[str]] = None
    ) -> str:
        """Publish event to EventBridge"""
        
        entry = {
            'Source': source,
            'DetailType': detail_type,
            'Detail': json.dumps(detail, default=str),
            'Time': datetime.utcnow()
        }
        
        if resources:
            entry['Resources'] = resources
        
        if event_bus_name != 'default':
            entry['EventBusName'] = event_bus_name
        
        try:
            response = self.client.put_events(Entries=[entry])
            
            if response['FailedEntryCount'] > 0:
                logger.error(f"Failed entries: {response['Entries']}")
                raise Exception("Event publication failed")
            
            logger.debug(f"Published event: {source}/{detail_type}")
            return response['Entries'][0]['EventId']
            
        except ClientError as e:
            logger.error(f"Failed to publish event: {e}")
            raise

# Example: Complete AWS messaging setup
async def aws_messaging_example():
    """Complete example of AWS messaging patterns"""
    
    # Initialize services
    msg_service = AWSMessageService()
    
    # 1. Create SQS queues with DLQ
    order_queue_config = SQSConfig(
        queue_name="order-processing",
        dead_letter_queue="order-processing-dlq",
        max_receive_count=3
    )
    
    order_queue_url = msg_service.create_sqs_queue(order_queue_config)
    
    # 2. Create SNS topic for order events
    order_topic_config = SNSConfig(
        topic_name="order-events",
        display_name="Order Events Topic"
    )
    
    order_topic_arn = msg_service.create_sns_topic(order_topic_config)
    
    # 3. Subscribe SQS to SNS
    msg_service.subscribe_sqs_to_sns("order-processing", "order-events")
    
    # 4. Setup EventBridge for complex event routing
    eventbridge = EventBridgeService()
    
    # Create custom event bus
    custom_bus_arn = eventbridge.create_custom_event_bus(
        "ecommerce-events",
        tags={"Environment": "production", "Service": "order-processing"}
    )
    
    # Create rule for order events
    order_event_pattern = {
        "source": ["ecommerce.orders"],
        "detail-type": ["Order Created", "Order Updated"],
        "detail": {
            "status": ["pending", "confirmed"]
        }
    }
    
    # Target: Send to SQS queue
    targets = [
        {
            'Id': '1',
            'Arn': msg_service.get_queue_arn(order_queue_url),
            'SqsParameters': {
                'MessageGroupId': 'order-events'
            }
        }
    ]
    
    eventbridge.create_rule(
        name="order-processing-rule",
        event_pattern=order_event_pattern,
        targets=targets,
        event_bus_name="ecommerce-events"
    )
    
    # 5. Publish some events
    producer = HighPerformanceSQSProducer()
    
    # Publish via SNS (will fan out to all subscribers)
    sns_client = boto3.client('sns')
    sns_client.publish(
        TopicArn=order_topic_arn,
        Message=json.dumps({
            'order_id': 'order-123',
            'customer_id': 'customer-456',
            'total_amount': 99.99,
            'status': 'pending'
        }),
        Subject='order_created'
    )
    
    # Publish via EventBridge
    eventbridge.publish_event(
        source="ecommerce.orders",
        detail_type="Order Created",
        detail={
            'order_id': 'order-124',
            'customer_id': 'customer-789',
            'total_amount': 149.99,
            'status': 'pending'
        },
        event_bus_name="ecommerce-events"
    )
    
    # 6. Start consuming messages
    consumer = SQSConsumer(order_queue_url)
    
    # Register handlers
    def handle_order_created(message, raw_message):
        logger.info(f"Processing order: {message}")
        # Process order logic here
    
    consumer.register_handler('order_created', handle_order_created)
    
    # Start consuming (would run indefinitely in real app)
    await consumer.start_consuming()

if __name__ == "__main__":
    asyncio.run(aws_messaging_example())
```

---

## 📊 **Part 4: Technology Comparison and Selection**

### **4.1 Comprehensive Comparison Matrix**

```python
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional

class UseCase(Enum):
    HIGH_THROUGHPUT_STREAMING = "high_throughput_streaming"
    RELIABLE_TASK_QUEUE = "reliable_task_queue"  
    PUB_SUB_FANOUT = "pub_sub_fanout"
    EVENT_SOURCING = "event_sourcing"
    MICROSERVICES_COMMUNICATION = "microservices_communication"
    REAL_TIME_ANALYTICS = "real_time_analytics"
    IOT_DATA_INGESTION = "iot_data_ingestion"
    BATCH_PROCESSING = "batch_processing"

@dataclass
class TechnologyRating:
    performance: int  # 1-5 scale
    reliability: int
    scalability: int
    ease_of_use: int
    operational_complexity: int  # 1=simple, 5=complex
    cost: int  # 1=cheap, 5=expensive
    ecosystem: int  # Tool ecosystem richness

class MessageQueueComparison:
    """Comprehensive comparison of message queue technologies"""
    
    def __init__(self):
        self.ratings = self._initialize_ratings()
        self.use_case_scores = self._calculate_use_case_scores()
    
    def _initialize_ratings(self) -> Dict[str, TechnologyRating]:
        """Initialize ratings for each technology"""
        
        return {
            'kafka': TechnologyRating(
                performance=5,
                reliability=5,
                scalability=5,
                ease_of_use=2,
                operational_complexity=5,
                cost=3,
                ecosystem=5
            ),
            'rabbitmq': TechnologyRating(
                performance=4,
                reliability=5,
                scalability=3,
                ease_of_use=4,
                operational_complexity=3,
                cost=2,
                ecosystem=4
            ),
            'aws_sqs_sns': TechnologyRating(
                performance=3,
                reliability=5,
                scalability=5,
                ease_of_use=5,
                operational_complexity=1,
                cost=4,
                ecosystem=4
            ),
            'gcp_pubsub': TechnologyRating(
                performance=4,
                reliability=5,
                scalability=5,
                ease_of_use=4,
                operational_complexity=1,
                cost=3,
                ecosystem=3
            ),
            'azure_service_bus': TechnologyRating(
                performance=3,
                reliability=5,
                scalability=4,
                ease_of_use=4,
                operational_complexity=1,
                cost=4,
                ecosystem=3
            ),
            'redis_streams': TechnologyRating(
                performance=5,
                reliability=3,
                scalability=3,
                ease_of_use=4,
                operational_complexity=2,
                cost=1,
                ecosystem=2
            ),
            'nats': TechnologyRating(
                performance=5,
                reliability=4,
                scalability=4,
                ease_of_use=5,
                operational_complexity=2,
                cost=1,
                ecosystem=2
            )
        }
    
    def _calculate_use_case_scores(self) -> Dict[UseCase, Dict[str, float]]:
        """Calculate scores for each use case"""
        
        # Define weights for different use cases
        use_case_weights = {
            UseCase.HIGH_THROUGHPUT_STREAMING: {
                'performance': 0.4,
                'scalability': 0.3,
                'reliability': 0.2,
                'cost': 0.1
            },
            UseCase.RELIABLE_TASK_QUEUE: {
                'reliability': 0.4,
                'ease_of_use': 0.3,
                'operational_complexity': -0.2,  # Lower is better
                'cost': 0.1
            },
            UseCase.PUB_SUB_FANOUT: {
                'scalability': 0.3,
                'reliability': 0.3,
                'ease_of_use': 0.2,
                'performance': 0.2
            },
            UseCase.EVENT_SOURCING: {
                'reliability': 0.4,
                'performance': 0.3,
                'ecosystem': 0.2,
                'scalability': 0.1
            },
            UseCase.MICROSERVICES_COMMUNICATION: {
                'ease_of_use': 0.3,
                'reliability': 0.3,
                'operational_complexity': -0.2,
                'scalability': 0.2
            },
            UseCase.REAL_TIME_ANALYTICS: {
                'performance': 0.4,
                'scalability': 0.3,
                'ecosystem': 0.2,
                'cost': 0.1
            },
            UseCase.IOT_DATA_INGESTION: {
                'scalability': 0.4,
                'performance': 0.3,
                'cost': 0.2,
                'reliability': 0.1
            },
            UseCase.BATCH_PROCESSING: {
                'cost': 0.3,
                'scalability': 0.3,
                'ease_of_use': 0.2,
                'reliability': 0.2
            }
        }
        
        scores = {}
        
        for use_case, weights in use_case_weights.items():
            scores[use_case] = {}
            
            for tech, rating in self.ratings.items():
                score = 0
                
                for attribute, weight in weights.items():
                    value = getattr(rating, attribute.replace('-', '_'))
                    
                    # Handle negative weights (where lower is better)
                    if weight < 0:
                        # Invert the score for attributes where lower is better
                        value = 6 - value
                        weight = abs(weight)
                    
                    score += value * weight
                
                scores[use_case][tech] = score
        
        return scores
    
    def recommend_technology(
        self, 
        use_case: UseCase, 
        constraints: Optional[Dict[str, int]] = None
    ) -> List[tuple]:
        """Recommend technologies for a specific use case"""
        
        scores = self.use_case_scores[use_case].copy()
        
        # Apply constraints if provided
        if constraints:
            for tech in list(scores.keys()):
                rating = self.ratings[tech]
                
                # Check if technology meets constraints
                for constraint, min_value in constraints.items():
                    if getattr(rating, constraint) < min_value:
                        del scores[tech]
                        break
        
        # Sort by score
        recommendations = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        return recommendations
    
    def get_detailed_comparison(self, technologies: List[str]) -> Dict[str, Dict[str, int]]:
        """Get detailed comparison of specific technologies"""
        
        comparison = {}
        
        for tech in technologies:
            if tech in self.ratings:
                rating = self.ratings[tech]
                comparison[tech] = {
                    'Performance': rating.performance,
                    'Reliability': rating.reliability,
                    'Scalability': rating.scalability,
                    'Ease of Use': rating.ease_of_use,
                    'Operational Complexity': rating.operational_complexity,
                    'Cost': rating.cost,
                    'Ecosystem': rating.ecosystem
                }
        
        return comparison

# Decision framework implementation
class TechnologyDecisionFramework:
    """Framework for making technology decisions"""
    
    def __init__(self):
        self.comparison = MessageQueueComparison()
        self.decision_tree = self._build_decision_tree()
    
    def _build_decision_tree(self) -> Dict:
        """Build decision tree for technology selection"""
        
        return {
            "throughput_requirements": {
                "high": {
                    "next": "latency_requirements",
                    "candidates": ["kafka", "nats", "redis_streams"]
                },
                "medium": {
                    "next": "reliability_requirements", 
                    "candidates": ["rabbitmq", "gcp_pubsub", "kafka"]
                },
                "low": {
                    "next": "operational_complexity",
                    "candidates": ["aws_sqs_sns", "rabbitmq", "redis_streams"]
                }
            },
            "latency_requirements": {
                "ultra_low": {
                    "next": "consistency_requirements",
                    "candidates": ["nats", "redis_streams"]
                },
                "low": {
                    "next": "ordering_requirements",
                    "candidates": ["kafka", "nats", "redis_streams"]
                },
                "medium": {
                    "next": "reliability_requirements",
                    "candidates": ["kafka", "rabbitmq", "gcp_pubsub"]
                }
            },
            "reliability_requirements": {
                "critical": {
                    "next": "operational_complexity",
                    "candidates": ["kafka", "rabbitmq", "aws_sqs_sns"]
                },
                "high": {
                    "next": "cost_sensitivity",
                    "candidates": ["rabbitmq", "gcp_pubsub", "kafka"]
                },
                "medium": {
                    "next": "ease_of_use",
                    "candidates": ["redis_streams", "nats", "rabbitmq"]
                }
            },
            "operational_complexity": {
                "prefer_managed": {
                    "result": ["aws_sqs_sns", "gcp_pubsub", "azure_service_bus"]
                },
                "can_manage": {
                    "next": "team_expertise",
                    "candidates": ["kafka", "rabbitmq", "nats"]
                },
                "prefer_simple": {
                    "result": ["redis_streams", "nats"]
                }
            },
            "cost_sensitivity": {
                "high": {
                    "result": ["redis_streams", "nats", "rabbitmq"]
                },
                "medium": {
                    "result": ["kafka", "gcp_pubsub", "rabbitmq"]
                },
                "low": {
                    "result": ["aws_sqs_sns", "azure_service_bus", "kafka"]
                }
            },
            "team_expertise": {
                "kafka_expert": {
                    "result": ["kafka"]
                },
                "rabbitmq_expert": {
                    "result": ["rabbitmq"]
                },
                "cloud_native": {
                    "result": ["aws_sqs_sns", "gcp_pubsub", "azure_service_bus"]
                },
                "generalist": {
                    "result": ["nats", "redis_streams"]
                }
            }
        }
    
    def guided_selection(self) -> List[str]:
        """Interactive guided technology selection"""
        
        current_node = "throughput_requirements"
        candidates = list(self.comparison.ratings.keys())
        
        while current_node in self.decision_tree:
            node = self.decision_tree[current_node]
            
            # This would be interactive in a real implementation
            if current_node == "throughput_requirements":
                choice = "high"  # Example: would ask user
            elif current_node == "latency_requirements":
                choice = "low"
            elif current_node == "reliability_requirements":
                choice = "critical"
            elif current_node == "operational_complexity":
                choice = "can_manage"
            elif current_node == "team_expertise":
                choice = "kafka_expert"
            else:
                choice = "medium"  # Default
            
            if choice in node:
                selected = node[choice]
                
                if "result" in selected:
                    return selected["result"]
                
                if "candidates" in selected:
                    candidates = selected["candidates"]
                
                current_node = selected.get("next")
            else:
                break
        
        return candidates

# Practical examples
def technology_selection_examples():
    """Examples of technology selection for different scenarios"""
    
    comparison = MessageQueueComparison()
    framework = TechnologyDecisionFramework()
    
    # Scenario 1: High-throughput event streaming
    print("=== Scenario 1: High-throughput event streaming ===")
    recommendations = comparison.recommend_technology(
        UseCase.HIGH_THROUGHPUT_STREAMING,
        constraints={
            'performance': 4,
            'scalability': 4
        }
    )
    
    for tech, score in recommendations[:3]:
        print(f"{tech}: {score:.2f}")
    
    # Scenario 2: Reliable task queue for small team
    print("\n=== Scenario 2: Reliable task queue ===")
    recommendations = comparison.recommend_technology(
        UseCase.RELIABLE_TASK_QUEUE,
        constraints={
            'ease_of_use': 3,
            'operational_complexity': 3  # Not too complex
        }
    )
    
    for tech, score in recommendations[:3]:
        print(f"{tech}: {score:.2f}")
    
    # Scenario 3: IoT data ingestion (cost-sensitive)
    print("\n=== Scenario 3: IoT data ingestion ===")
    recommendations = comparison.recommend_technology(
        UseCase.IOT_DATA_INGESTION,
        constraints={
            'scalability': 4,
            'cost': 3  # Cost-conscious
        }
    )
    
    for tech, score in recommendations[:3]:
        print(f"{tech}: {score:.2f}")
    
    # Decision tree example
    print("\n=== Guided Selection Example ===")
    recommended = framework.guided_selection()
    print(f"Recommended technologies: {recommended}")
    
    # Detailed comparison
    print("\n=== Detailed Comparison: Top 3 Technologies ===")
    top_technologies = ['kafka', 'rabbitmq', 'aws_sqs_sns']
    detailed = comparison.get_detailed_comparison(top_technologies)
    
    # Print comparison table
    print(f"{'Attribute':<20}", end="")
    for tech in top_technologies:
        print(f"{tech:<15}", end="")
    print()
    
    attributes = ['Performance', 'Reliability', 'Scalability', 'Ease of Use', 
                 'Operational Complexity', 'Cost', 'Ecosystem']
    
    for attr in attributes:
        print(f"{attr:<20}", end="")
        for tech in top_technologies:
            value = detailed[tech][attr]
            print(f"{value:<15}", end="")
        print()

if __name__ == "__main__":
    technology_selection_examples()
```

---

## ✅ **Module 2 Assessment**

### **Practical Exercise: Multi-Technology Message Architecture**

**Scenario:** Design a complete messaging architecture for a large e-commerce platform with the following requirements:

- **Order Processing**: 50,000 orders/hour peak, strong consistency required
- **Inventory Updates**: Real-time inventory tracking across 1M+ products
- **Customer Notifications**: Email, SMS, push notifications to 10M+ users
- **Analytics**: Real-time dashboards and batch analytics
- **Fraud Detection**: Sub-second transaction analysis
- **Audit Logging**: Immutable audit trail for compliance

**Your Task:**
1. Choose appropriate technologies for each use case
2. Design the complete message flow
3. Implement producers and consumers for critical paths
4. Include monitoring and error handling
5. Plan for disaster recovery and scaling

### **Assessment Criteria**

#### **Technology Selection (25 points)**
- [ ] Appropriate technology choice for each use case
- [ ] Clear justification for technology decisions
- [ ] Consideration of operational complexity
- [ ] Cost-performance trade-off analysis

#### **Implementation Quality (30 points)**
- [ ] Production-ready producer patterns
- [ ] Scalable consumer implementations  
- [ ] Proper error handling and retry logic
- [ ] Message schema design and versioning

#### **Architecture Design (25 points)**
- [ ] Clear message flow diagrams
- [ ] Proper separation of concerns
- [ ] Scalability and reliability considerations
- [ ] Security implementation

#### **Operations & Monitoring (20 points)**
- [ ] Comprehensive monitoring setup
- [ ] Alerting and SLA definitions
- [ ] Disaster recovery planning
- [ ] Performance optimization

---

## 🔗 **Next Steps**

After completing this module, you should:
1. ✅ Understand the strengths and weaknesses of major message queue technologies
2. ✅ Be able to implement production-ready producers and consumers
3. ✅ Make informed technology selection decisions
4. ✅ Design scalable message architectures for real-world scenarios

**Next Module:** [03_ADVANCED_EDA_PATTERNS.md](03_ADVANCED_EDA_PATTERNS.md)
- Event Sourcing and CQRS implementation
- Distributed Saga patterns for transactions
- Complex event processing and stream analytics
- Advanced consistency and ordering patterns

---

## 📚 **Additional Resources**

### **Technology-Specific Documentation**
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [RabbitMQ Tutorials](https://www.rabbitmq.com/getstarted.html)
- [AWS SQS/SNS Developer Guides](https://docs.aws.amazon.com/sqs/)
- [Google Cloud Pub/Sub Documentation](https://cloud.google.com/pubsub/docs)

### **Performance Benchmarks**
- [Kafka Performance Testing](https://kafka.apache.org/documentation/#performance)
- [RabbitMQ Performance Tuning](https://www.rabbitmq.com/performance.html)
- [Cloud Message Service Comparisons](https://cloud.google.com/pubsub/docs/publisher)

### **Production Case Studies**
- [LinkedIn's Kafka Usage](https://engineering.linkedin.com/kafka/running-kafka-scale)
- [Netflix's Message Queue Architecture](https://netflixtechblog.com/kafka-inside-keystone-pipeline-dd5aeabaf6bb)
- [Uber's Real-time Data Platform](https://eng.uber.com/kafka/)

**Estimated completion time: 3-4 weeks**
**Next module preparation: Set up event store and CQRS environment**