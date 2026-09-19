# Event-Driven Architecture Quick Reference
## Staff Engineer Cheat Sheet

---

## 🎯 **Core EDA Patterns**

### **Events vs Commands vs Queries**

| Type | Purpose | Direction | Can Fail | Naming |
|------|---------|-----------|----------|---------|
| **Event** | What happened | 1:N (broadcast) | No | Past tense (OrderCreated) |
| **Command** | What to do | 1:1 (directed) | Yes | Imperative (CreateOrder) |
| **Query** | Get information | 1:1 (request) | Yes | Question (GetOrderStatus) |

### **Event Types by Scope**

```python
# Domain Event (within bounded context)
class OrderCreated(DomainEvent):
    order_id: str
    customer_id: str
    items: List[OrderItem]

# Integration Event (cross-service)
class OrderProcessingStarted(IntegrationEvent):
    order_id: str
    customer_id: str
    # Minimal data for privacy/coupling

# System Event (infrastructure)
class OrderServiceStarted(SystemEvent):
    service_version: str
    start_time: datetime
```

---

## 📋 **Event Schema Design**

### **Standard Event Structure**

```python
class StandardEvent(BaseModel):
    # Metadata (same for all events)
    metadata: EventMetadata = Field(...)
    
    # Event-specific payload
    order_id: str
    customer_id: str
    # ... other fields

class EventMetadata(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = Field(...)  # "order.created"
    event_version: str = Field(...) # "1.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    source_service: str = Field(...)
    aggregate_id: Optional[str] = None
```

### **Schema Evolution Patterns**

```python
# ✅ Safe Changes (Backward Compatible)
- Add optional fields
- Add new event types
- Expand enum values
- Make required fields optional

# ❌ Breaking Changes (Need New Version)
- Remove fields
- Change field types
- Make optional fields required
- Change field semantics
```

---

## 🚀 **Message Queue Technology Comparison**

| Feature | Apache Kafka | RabbitMQ | AWS SQS/SNS | Redis Streams |
|---------|-------------|----------|-------------|---------------|
| **Throughput** | Very High | High | Medium | High |
| **Latency** | Medium | Low | Medium | Very Low |
| **Ordering** | Partition-level | Queue-level | FIFO queues | Stream-level |
| **Durability** | Excellent | Good | Excellent | Good |
| **Complexity** | High | Medium | Low | Low |
| **Use Case** | Event streaming | Task queues | Cloud-native | Caching + events |

### **When to Use Each**

```python
# Kafka: High-volume event streaming
use_kafka_when = [
    "High throughput requirements (>10k events/sec)",
    "Event sourcing and replay capabilities",
    "Multiple consumers need same events",
    "Long-term event storage requirements",
    "Complex event processing pipelines"
]

# RabbitMQ: Reliable message queuing
use_rabbitmq_when = [
    "Complex routing requirements",
    "Need guaranteed delivery",
    "Work queue patterns",
    "Priority message handling",
    "Protocol flexibility (AMQP, MQTT, STOMP)"
]

# Cloud Services: Managed simplicity
use_cloud_services_when = [
    "Prefer managed infrastructure",
    "Auto-scaling requirements",
    "Integration with cloud ecosystem",
    "Minimal operational overhead"
]
```

---

## 🏗️ **Architecture Patterns**

### **Event Choreography vs Orchestration**

```python
# Choreography: Decentralized, event-driven
class OrderService:
    def create_order(self, order_data):
        order = self.save_order(order_data)
        self.publish_event(OrderCreated(order))  # Fire and forget

class InventoryService:
    def handle_order_created(self, event: OrderCreated):
        if self.reserve_items(event.items):
            self.publish_event(InventoryReserved(event.order_id))

# Orchestration: Centralized process manager
class OrderSagaOrchestrator:
    def handle_order_created(self, event: OrderCreated):
        # Step 1: Reserve inventory
        self.send_command(ReserveInventory(event.order_id, event.items))
    
    def handle_inventory_reserved(self, event: InventoryReserved):
        # Step 2: Process payment
        self.send_command(ProcessPayment(event.order_id))
```

### **Event Sourcing Pattern**

```python
# Aggregate with event sourcing
class Order:
    def __init__(self):
        self._uncommitted_events = []
        self.version = 0
    
    def create_order(self, customer_id, items):
        event = OrderCreated(customer_id=customer_id, items=items)
        self._apply_event(event)
        self._uncommitted_events.append(event)
    
    def _apply_event(self, event):
        if isinstance(event, OrderCreated):
            self.status = "PENDING"
            self.items = event.items
        # ... handle other events
        
        self.version += 1
    
    def load_from_events(self, events):
        for event in events:
            self._apply_event(event)

# Event store operations
class EventStore:
    async def save_events(self, aggregate_id, events, expected_version):
        # Optimistic concurrency check
        current_version = await self.get_version(aggregate_id)
        if current_version != expected_version:
            raise ConcurrencyException()
        
        # Save events atomically
        for event in events:
            await self.append_event(aggregate_id, event)
```

### **CQRS Pattern**

```python
# Command side (writes)
class CreateOrderHandler:
    def handle(self, command: CreateOrder):
        order = Order.create_new(command.customer_id, command.items)
        self.order_repository.save(order)
        
        # Publish events
        for event in order.get_uncommitted_events():
            self.event_publisher.publish(event)

# Query side (reads)
class OrderQueryHandler:
    def handle(self, query: GetOrderStatus):
        # Read from optimized read model
        return self.order_read_model.get_order_status(query.order_id)

# Projection builder
class OrderProjectionBuilder:
    def handle(self, event: OrderCreated):
        projection = OrderProjection(
            order_id=event.order_id,
            status="PENDING",
            created_at=event.timestamp
        )
        self.order_read_model.save(projection)
```

---

## ⚡ **Performance Patterns**

### **Batching and Bulk Operations**

```python
# Producer batching
class BatchedEventPublisher:
    def __init__(self, batch_size=100, flush_interval=1.0):
        self.batch = []
        self.batch_size = batch_size
        self.flush_interval = flush_interval
    
    async def publish(self, event):
        self.batch.append(event)
        if len(self.batch) >= self.batch_size:
            await self.flush()
    
    async def flush(self):
        if self.batch:
            await self.kafka_producer.send_batch(self.batch)
            self.batch.clear()

# Consumer micro-batching
class MicroBatchConsumer:
    async def consume_with_microbatch(self, batch_size=50):
        batch = []
        async for message in self.consumer:
            batch.append(message)
            
            if len(batch) >= batch_size:
                await self.process_batch(batch)
                batch.clear()
```

### **Partitioning Strategies**

```python
# Key-based partitioning
def get_partition_key(event):
    if isinstance(event, OrderEvent):
        return event.customer_id  # Same customer = same partition
    elif isinstance(event, InventoryEvent):
        return event.product_id   # Same product = same partition

# Hash-based partitioning for even distribution
import hashlib

def hash_partition_key(key: str, num_partitions: int) -> int:
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % num_partitions

# Time-based partitioning for time-series data
def time_partition_key(timestamp: datetime) -> str:
    return timestamp.strftime("%Y%m%d%H")  # Hourly partitions
```

---

## 🔧 **Error Handling Patterns**

### **Retry with Exponential Backoff**

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

class ResilientEventPublisher:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        reraise=True
    )
    async def publish_with_retry(self, event):
        try:
            await self.kafka_producer.send(event)
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            raise  # Will trigger retry
```

### **Dead Letter Queue Pattern**

```python
class DeadLetterQueueHandler:
    def __init__(self, max_retries=3):
        self.max_retries = max_retries
    
    async def handle_message(self, message):
        retry_count = message.headers.get('retry_count', 0)
        
        try:
            await self.process_message(message)
        except Exception as e:
            if retry_count < self.max_retries:
                # Retry with delay
                await self.schedule_retry(message, retry_count + 1)
            else:
                # Send to dead letter queue
                await self.send_to_dlq(message, str(e))

async def schedule_retry(self, message, retry_count):
    delay = 2 ** retry_count  # Exponential backoff
    message.headers['retry_count'] = retry_count
    await asyncio.sleep(delay)
    await self.event_bus.publish(message)
```

### **Circuit Breaker Pattern**

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenException()
        
        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise
    
    def on_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
```

---

## 📊 **Monitoring and Observability**

### **Key Metrics to Track**

```python
# Event processing metrics
from prometheus_client import Counter, Histogram, Gauge

events_published = Counter(
    'events_published_total',
    'Total events published',
    ['event_type', 'service']
)

event_processing_duration = Histogram(
    'event_processing_duration_seconds',
    'Time spent processing events',
    ['event_type', 'handler']
)

queue_depth = Gauge(
    'message_queue_depth',
    'Current queue depth',
    ['queue_name']
)

# Usage
events_published.labels(event_type='order.created', service='order-service').inc()
with event_processing_duration.labels(event_type='order.created', handler='inventory').time():
    await process_order_created(event)
```

### **Distributed Tracing**

```python
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Setup tracing
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)

span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

# Usage in event handlers
async def handle_order_created(event):
    with tracer.start_as_current_span("handle_order_created") as span:
        span.set_attribute("order_id", event.order_id)
        span.set_attribute("customer_id", event.customer_id)
        
        # Process event
        await process_inventory_check(event)
        
        span.set_attribute("status", "success")
```

### **Structured Logging**

```python
import structlog

logger = structlog.get_logger()

async def handle_payment_processed(event):
    log = logger.bind(
        event_type=event.get_event_type(),
        event_id=event.metadata.event_id,
        order_id=event.order_id,
        correlation_id=event.metadata.correlation_id
    )
    
    log.info("Processing payment event")
    
    try:
        await process_payment(event)
        log.info("Payment processed successfully")
    except Exception as e:
        log.error("Payment processing failed", error=str(e))
        raise
```

---

## 🔒 **Security Best Practices**

### **Event Encryption**

```python
from cryptography.fernet import Fernet

class EncryptedEventPublisher:
    def __init__(self, encryption_key):
        self.cipher = Fernet(encryption_key)
    
    def publish_sensitive_event(self, event):
        # Encrypt sensitive fields
        if hasattr(event, 'personal_data'):
            event.personal_data = self.cipher.encrypt(
                event.personal_data.encode()
            ).decode()
        
        self.kafka_producer.send(event)
```

### **Event Authorization**

```python
class EventAuthorizer:
    def can_publish_event(self, user_id: str, event_type: str) -> bool:
        permissions = self.get_user_permissions(user_id)
        return f"publish:{event_type}" in permissions
    
    def can_consume_event(self, service_id: str, event_type: str) -> bool:
        permissions = self.get_service_permissions(service_id)
        return f"consume:{event_type}" in permissions
```

---

## 🧪 **Testing Patterns**

### **Event-Driven Testing**

```python
import pytest
from unittest.mock import AsyncMock

class TestOrderService:
    @pytest.fixture
    def event_publisher(self):
        return AsyncMock()
    
    @pytest.fixture
    def order_service(self, event_publisher):
        return OrderService(event_publisher)
    
    async def test_create_order_publishes_event(self, order_service, event_publisher):
        # Arrange
        order_data = {"customer_id": "123", "items": [...]}
        
        # Act
        await order_service.create_order(order_data)
        
        # Assert
        event_publisher.publish.assert_called_once()
        published_event = event_publisher.publish.call_args[0][0]
        assert isinstance(published_event, OrderCreated)
        assert published_event.customer_id == "123"

# Integration testing with test containers
from testcontainers.kafka import KafkaContainer

@pytest.fixture(scope="session")
def kafka_container():
    with KafkaContainer() as kafka:
        yield kafka

async def test_end_to_end_order_flow(kafka_container):
    # Setup real Kafka for integration test
    kafka_client = KafkaClient(kafka_container.get_bootstrap_server())
    
    # Test actual event flow
    order_service = OrderService(kafka_client)
    inventory_service = InventoryService(kafka_client)
    
    # Create order and verify inventory reservation
    await order_service.create_order(order_data)
    
    # Wait for event processing
    await asyncio.sleep(1)
    
    # Verify inventory was reserved
    inventory_status = await inventory_service.get_inventory_status(product_id)
    assert inventory_status.reserved_quantity == expected_quantity
```

---

## 📚 **Common Antipatterns to Avoid**

### **❌ Event Sourcing Everything**
```python
# Don't do this for simple CRUD
class UserProfile:  # Simple entity
    def update_email(self, new_email):
        # Just update the database directly
        self.email = new_email
        self.save()
```

### **❌ Chatty Events**
```python
# Avoid too many fine-grained events
class Order:
    def add_item(self, item):
        self.items.append(item)
        self.publish(ItemAdded(item))  # ❌ Too chatty
        
        self.total += item.price
        self.publish(TotalUpdated(self.total))  # ❌ Too chatty

# Better: Single meaningful event
class Order:
    def add_item(self, item):
        self.items.append(item)
        self.total += item.price
        self.publish(OrderItemAdded(item, self.total))  # ✅ Single event
```

### **❌ Event Coupling**
```python
# Don't couple events to specific consumers
class OrderCreated:
    customer_id: str
    items: List[Item]
    send_email_to_customer: bool  # ❌ Coupled to email service
    update_analytics_dashboard: bool  # ❌ Coupled to analytics

# Better: Generic event, let consumers decide
class OrderCreated:
    customer_id: str
    items: List[Item]
    # Consumers decide what to do
```

---

## 🚀 **Quick Setup Commands**

### **Kafka Setup**

```bash
# Start Kafka with Docker
docker run -d --name kafka \
  -p 9092:9092 \
  -e KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 \
  confluent/kafka

# Create topic
kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --replication-factor 1 \
  --partitions 3 \
  --topic order-events

# List topics
kafka-topics --list --bootstrap-server localhost:9092

# Consume messages
kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic order-events \
  --from-beginning
```

### **Python Event System Setup**

```bash
# Install dependencies
pip install fastapi uvicorn kafka-python confluent-kafka \
           pydantic sqlalchemy asyncpg redis structlog \
           prometheus-client opentelemetry-api

# Run FastAPI service
uvicorn main:app --reload --port 8000

# Run Celery worker
celery -A app.celery worker --loglevel=info
```

---

## 📋 **Decision Matrix**

### **Architecture Decision Framework**

| Factor | Synchronous | Event-Driven | Score Criteria |
|--------|-------------|---------------|----------------|
| **Consistency** | Strong | Eventual | Strong = 5, Eventual = 3 |
| **Latency** | Low | Medium | <100ms = 5, <1s = 3, >1s = 1 |
| **Scalability** | Limited | High | Horizontal = 5, Vertical = 3 |
| **Complexity** | Low | High | Simple = 5, Complex = 1 |
| **Reliability** | Medium | High | 99.9% = 5, 99% = 3, <99% = 1 |
| **Cost** | Low | Medium | Low = 5, Medium = 3, High = 1 |

**Use Case Scoring:**
- **E-commerce Orders**: Scalability (5), Reliability (5), Consistency (3) → Event-Driven
- **Banking Transfers**: Consistency (5), Reliability (5), Latency (5) → Synchronous
- **Social Media Posts**: Scalability (5), Latency (3), Complexity (3) → Event-Driven

This quick reference serves as your go-to guide for implementing event-driven architectures at the staff engineer level. Keep it handy during design sessions and code reviews!