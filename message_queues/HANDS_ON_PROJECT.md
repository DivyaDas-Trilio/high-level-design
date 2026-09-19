# Hands-On Project: Event-Driven E-Commerce Platform
## Complete Implementation Guide for Staff Engineers

---

## 🎯 **Project Overview**

Build a production-ready, event-driven e-commerce platform that demonstrates all EDA patterns and technologies covered in this course. This project will serve as your portfolio piece and practical application of event-driven architecture principles.

### **System Architecture**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │    │   Event Store   │    │  Read Models    │
│   (FastAPI)     │    │    (Kafka)      │    │ (PostgreSQL)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Order Service   │◄──►│ Inventory Svc   │◄──►│ Payment Service │
│ (Event Sourced) │    │ (Traditional)   │    │ (Saga Pattern)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │ Notification    │
                    │ Service         │
                    └─────────────────┘
```

---

## 🏗️ **Phase 1: Foundation Setup (Week 1-2)**

### **1.1 Infrastructure Setup**

Create the base infrastructure with Docker Compose:

```yaml
# docker-compose.yml
version: '3.8'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.4.0
    hostname: zookeeper
    container_name: zookeeper
    ports:
      - "2181:2181"
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000

  kafka:
    image: confluentinc/cp-kafka:7.4.0
    hostname: kafka
    container_name: kafka
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
      - "9997:9997"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: 'zookeeper:2181'
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_METRIC_REPORTERS: io.confluent.metrics.reporter.ConfluentMetricsReporter
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_CONFLUENT_METRICS_REPORTER_BOOTSTRAP_SERVERS: kafka:29092
      KAFKA_CONFLUENT_METRICS_REPORTER_TOPIC_REPLICAS: 1
      KAFKA_CONFLUENT_METRICS_ENABLE: 'true'
      KAFKA_CONFLUENT_SUPPORT_CUSTOMER_ID: anonymous

  schema-registry:
    image: confluentinc/cp-schema-registry:7.4.0
    hostname: schema-registry
    container_name: schema-registry
    depends_on:
      - kafka
    ports:
      - "8081:8081"
    environment:
      SCHEMA_REGISTRY_HOST_NAME: schema-registry
      SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: 'kafka:29092'
      SCHEMA_REGISTRY_LISTENERS: http://0.0.0.0:8081

  postgres:
    image: postgres:14
    hostname: postgres
    container_name: postgres
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: ecommerce
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d

  redis:
    image: redis:7-alpine
    hostname: redis
    container_name: redis
    ports:
      - "6379:6379"

  prometheus:
    image: prom/prometheus
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  postgres_data:
  grafana_data:
```

### **1.2 Project Structure**

```
ecommerce-platform/
├── docker-compose.yml
├── requirements.txt
├── README.md
├── .env
├── .gitignore
├── init-scripts/
│   └── init.sql
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
├── src/
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── events/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── order_events.py
│   │   │   ├── inventory_events.py
│   │   │   ├── payment_events.py
│   │   │   └── notification_events.py
│   │   ├── infrastructure/
│   │   │   ├── __init__.py
│   │   │   ├── event_store.py
│   │   │   ├── kafka_client.py
│   │   │   ├── database.py
│   │   │   └── monitoring.py
│   │   └── domain/
│   │       ├── __init__.py
│   │       ├── models.py
│   │       └── exceptions.py
│   ├── services/
│   │   ├── order_service/
│   │   │   ├── __init__.py
│   │   │   ├── api.py
│   │   │   ├── domain/
│   │   │   ├── handlers/
│   │   │   └── repository/
│   │   ├── inventory_service/
│   │   ├── payment_service/
│   │   └── notification_service/
│   ├── api_gateway/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── routes/
│   │   └── middleware/
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── e2e/
├── scripts/
│   ├── setup.sh
│   ├── seed_data.py
│   └── performance_test.py
└── docs/
    ├── architecture.md
    ├── api_docs.md
    └── deployment.md
```

### **1.3 Core Dependencies**

```toml
# pyproject.toml
[tool.poetry]
name = "event-driven-ecommerce"
version = "0.1.0"
description = "Event-driven e-commerce platform"

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.104.1"
uvicorn = "^0.24.0"
pydantic = "^2.5.0"
sqlalchemy = "^2.0.23"
asyncpg = "^0.29.0"
alembic = "^1.13.0"
kafka-python = "^2.0.2"
confluent-kafka = "^2.3.0"
redis = "^5.0.1"
celery = "^5.3.4"
prometheus-client = "^0.19.0"
opentelemetry-api = "^1.21.0"
opentelemetry-sdk = "^1.21.0"
structlog = "^23.2.0"
tenacity = "^8.2.3"
httpx = "^0.25.2"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.3"
pytest-asyncio = "^0.21.1"
pytest-cov = "^4.1.0"
testcontainers = "^3.7.1"
black = "^23.11.0"
isort = "^5.12.0"
mypy = "^1.7.1"
```

---

## 🎯 **Phase 2: Event Infrastructure (Week 2-3)**

### **2.1 Base Event Classes**

```python
# src/shared/events/base.py
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class EventMetadata(BaseModel):
    """Common metadata for all events"""
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = Field(..., description="Type of event")
    event_version: str = Field(..., description="Schema version")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[UUID] = Field(None, description="ID to track related events")
    causation_id: Optional[UUID] = Field(None, description="ID of the event that caused this one")
    source_service: str = Field(..., description="Service that generated the event")
    aggregate_id: Optional[str] = Field(None, description="ID of the aggregate this event belongs to")
    aggregate_version: Optional[int] = Field(None, description="Version of the aggregate after this event")


class DomainEvent(BaseModel, ABC):
    """Base class for all domain events"""
    metadata: EventMetadata

    @abstractmethod
    def get_event_type(self) -> str:
        """Return the event type identifier"""
        pass

    @abstractmethod
    def get_event_version(self) -> str:
        """Return the schema version"""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization"""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DomainEvent':
        """Create event from dictionary"""
        return cls(**data)


class IntegrationEvent(BaseModel, ABC):
    """Base class for integration events (cross-service communication)"""
    metadata: EventMetadata

    @abstractmethod
    def get_event_type(self) -> str:
        pass

    @abstractmethod
    def get_event_version(self) -> str:
        pass


class Command(BaseModel, ABC):
    """Base class for commands"""
    command_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[UUID] = None

    @abstractmethod
    def validate_business_rules(self) -> None:
        """Validate command against business rules"""
        pass


class Query(BaseModel, ABC):
    """Base class for queries"""
    query_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### **2.2 Event Store Implementation**

```python
# src/shared/infrastructure/event_store.py
import json
import uuid
from datetime import datetime
from typing import List, Optional, AsyncIterator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.events.base import DomainEvent, EventMetadata


class EventStore:
    """Event store implementation using PostgreSQL"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def append_events(
        self, 
        aggregate_id: str, 
        events: List[DomainEvent], 
        expected_version: Optional[int] = None
    ) -> None:
        """Append events to the event store"""
        
        # Check optimistic concurrency if expected version is provided
        if expected_version is not None:
            current_version = await self._get_aggregate_version(aggregate_id)
            if current_version != expected_version:
                raise OptimisticConcurrencyException(
                    f"Expected version {expected_version}, got {current_version}"
                )
        
        # Insert events
        for i, event in enumerate(events):
            await self._insert_event(aggregate_id, event, expected_version + i + 1 if expected_version else i + 1)
    
    async def get_events(
        self, 
        aggregate_id: str, 
        from_version: int = 1
    ) -> AsyncIterator[DomainEvent]:
        """Get events for an aggregate from a specific version"""
        
        query = text("""
            SELECT event_data, event_type, event_version 
            FROM event_store 
            WHERE aggregate_id = :aggregate_id 
            AND version >= :from_version 
            ORDER BY version
        """)
        
        result = await self.session.execute(
            query, 
            {"aggregate_id": aggregate_id, "from_version": from_version}
        )
        
        async for row in result:
            event_data = json.loads(row.event_data)
            # Deserialize based on event type and version
            event = await self._deserialize_event(event_data, row.event_type, row.event_version)
            yield event
    
    async def get_all_events(
        self, 
        from_timestamp: Optional[datetime] = None
    ) -> AsyncIterator[DomainEvent]:
        """Get all events from a specific timestamp"""
        
        if from_timestamp:
            query = text("""
                SELECT event_data, event_type, event_version 
                FROM event_store 
                WHERE timestamp >= :from_timestamp 
                ORDER BY timestamp, version
            """)
            result = await self.session.execute(query, {"from_timestamp": from_timestamp})
        else:
            query = text("""
                SELECT event_data, event_type, event_version 
                FROM event_store 
                ORDER BY timestamp, version
            """)
            result = await self.session.execute(query)
        
        async for row in result:
            event_data = json.loads(row.event_data)
            event = await self._deserialize_event(event_data, row.event_type, row.event_version)
            yield event
    
    async def _insert_event(self, aggregate_id: str, event: DomainEvent, version: int) -> None:
        """Insert a single event"""
        
        query = text("""
            INSERT INTO event_store 
            (event_id, aggregate_id, event_type, event_version, event_data, timestamp, version)
            VALUES (:event_id, :aggregate_id, :event_type, :event_version, :event_data, :timestamp, :version)
        """)
        
        await self.session.execute(query, {
            "event_id": str(event.metadata.event_id),
            "aggregate_id": aggregate_id,
            "event_type": event.get_event_type(),
            "event_version": event.get_event_version(),
            "event_data": json.dumps(event.to_dict()),
            "timestamp": event.metadata.timestamp,
            "version": version
        })
    
    async def _get_aggregate_version(self, aggregate_id: str) -> int:
        """Get the current version of an aggregate"""
        
        query = text("""
            SELECT COALESCE(MAX(version), 0) as version 
            FROM event_store 
            WHERE aggregate_id = :aggregate_id
        """)
        
        result = await self.session.execute(query, {"aggregate_id": aggregate_id})
        row = await result.fetchone()
        return row.version if row else 0
    
    async def _deserialize_event(self, event_data: dict, event_type: str, event_version: str) -> DomainEvent:
        """Deserialize event data to proper event object"""
        # This would use your event registry/factory
        from src.shared.events import EventRegistry
        
        event_class = EventRegistry.get_event_class(event_type, event_version)
        return event_class.from_dict(event_data)


class OptimisticConcurrencyException(Exception):
    """Raised when optimistic concurrency check fails"""
    pass
```

### **2.3 Kafka Event Publisher**

```python
# src/shared/infrastructure/kafka_client.py
import json
import asyncio
from typing import Any, Dict, Optional
from confluent_kafka import Producer, Consumer
from confluent_kafka.admin import AdminClient, NewTopic
import structlog
from src.shared.events.base import DomainEvent, IntegrationEvent

logger = structlog.get_logger()


class KafkaEventPublisher:
    """Kafka event publisher with reliability features"""
    
    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.config = {
            'bootstrap.servers': bootstrap_servers,
            'acks': 'all',  # Wait for all replicas to acknowledge
            'retries': 3,
            'retry.backoff.ms': 100,
            'compression.type': 'snappy',
            'max.in.flight.requests.per.connection': 5,
            'enable.idempotence': True,  # Prevent duplicate messages
        }
        self.producer = Producer(self.config)
        self._delivery_reports = {}
    
    async def publish_event(
        self, 
        topic: str, 
        event: DomainEvent | IntegrationEvent, 
        partition_key: Optional[str] = None
    ) -> None:
        """Publish an event to Kafka topic"""
        
        try:
            # Serialize event
            event_data = self._serialize_event(event)
            
            # Create message headers
            headers = {
                'event_type': event.get_event_type(),
                'event_version': event.get_event_version(),
                'event_id': str(event.metadata.event_id),
                'timestamp': event.metadata.timestamp.isoformat(),
            }
            
            # Publish to Kafka
            future = asyncio.get_event_loop().create_future()
            self._delivery_reports[str(event.metadata.event_id)] = future
            
            self.producer.produce(
                topic=topic,
                key=partition_key,
                value=event_data,
                headers=headers,
                callback=self._delivery_callback
            )
            
            # Flush to ensure delivery
            self.producer.flush(timeout=10)
            
            # Wait for delivery confirmation
            await future
            
            logger.info(
                "Event published successfully",
                event_type=event.get_event_type(),
                event_id=str(event.metadata.event_id),
                topic=topic
            )
            
        except Exception as e:
            logger.error(
                "Failed to publish event",
                event_type=event.get_event_type(),
                event_id=str(event.metadata.event_id),
                error=str(e)
            )
            raise
    
    def _serialize_event(self, event: DomainEvent | IntegrationEvent) -> str:
        """Serialize event to JSON"""
        return json.dumps(event.to_dict(), default=str)
    
    def _delivery_callback(self, err, msg):
        """Callback for delivery reports"""
        event_id = None
        if msg.headers():
            for header in msg.headers():
                if header[0] == 'event_id':
                    event_id = header[1].decode()
                    break
        
        future = self._delivery_reports.pop(event_id, None)
        if future:
            if err:
                future.set_exception(Exception(f"Message delivery failed: {err}"))
            else:
                future.set_result(True)
    
    async def create_topic(self, topic_name: str, num_partitions: int = 3, replication_factor: int = 1):
        """Create a Kafka topic"""
        admin_client = AdminClient({'bootstrap.servers': self.config['bootstrap.servers']})
        
        topic = NewTopic(
            topic=topic_name,
            num_partitions=num_partitions,
            replication_factor=replication_factor
        )
        
        result = admin_client.create_topics([topic])
        
        # Wait for topic creation
        for topic, future in result.items():
            try:
                future.result()
                logger.info(f"Topic {topic} created successfully")
            except Exception as e:
                logger.error(f"Failed to create topic {topic}: {e}")
    
    def close(self):
        """Close the producer"""
        self.producer.flush()
        self.producer = None


class KafkaEventConsumer:
    """Kafka event consumer with error handling"""
    
    def __init__(
        self, 
        group_id: str, 
        bootstrap_servers: str = "localhost:9092",
        auto_offset_reset: str = "earliest"
    ):
        self.config = {
            'bootstrap.servers': bootstrap_servers,
            'group.id': group_id,
            'auto.offset.reset': auto_offset_reset,
            'enable.auto.commit': False,  # Manual commit for reliability
            'session.timeout.ms': 30000,
            'heartbeat.interval.ms': 10000,
        }
        self.consumer = Consumer(self.config)
        self._running = False
    
    async def subscribe_and_consume(self, topics: List[str], message_handler):
        """Subscribe to topics and start consuming messages"""
        
        self.consumer.subscribe(topics)
        self._running = True
        
        logger.info(f"Started consuming from topics: {topics}")
        
        try:
            while self._running:
                # Poll for messages
                msg = self.consumer.poll(timeout=1.0)
                
                if msg is None:
                    continue
                
                if msg.error():
                    logger.error(f"Consumer error: {msg.error()}")
                    continue
                
                try:
                    # Deserialize and handle message
                    await self._handle_message(msg, message_handler)
                    
                    # Commit offset after successful processing
                    self.consumer.commit(msg)
                    
                except Exception as e:
                    logger.error(
                        "Failed to process message",
                        error=str(e),
                        topic=msg.topic(),
                        partition=msg.partition(),
                        offset=msg.offset()
                    )
                    # Could implement dead letter queue here
        
        finally:
            self.consumer.close()
    
    async def _handle_message(self, msg, handler):
        """Handle a single message"""
        
        # Extract headers
        headers = {}
        if msg.headers():
            headers = {k: v.decode() if isinstance(v, bytes) else v 
                      for k, v in msg.headers()}
        
        # Deserialize event
        event_data = json.loads(msg.value().decode())
        
        # Get event type and version from headers
        event_type = headers.get('event_type')
        event_version = headers.get('event_version')
        
        # Create event object
        event = self._deserialize_event(event_data, event_type, event_version)
        
        # Handle the event
        await handler(event)
    
    def _deserialize_event(self, event_data: dict, event_type: str, event_version: str):
        """Deserialize event data to proper event object"""
        from src.shared.events import EventRegistry
        
        event_class = EventRegistry.get_event_class(event_type, event_version)
        return event_class.from_dict(event_data)
    
    def stop(self):
        """Stop consuming"""
        self._running = False
```

---

## 🛍️ **Phase 3: Order Service with Event Sourcing (Week 3-4)**

### **3.1 Order Domain Events**

```python
# src/shared/events/order_events.py
from decimal import Decimal
from datetime import datetime
from typing import List
from uuid import UUID
from src.shared.events.base import DomainEvent, EventMetadata


class OrderCreated(DomainEvent):
    """Event fired when a new order is created"""
    
    order_id: str
    customer_id: str
    items: List['OrderItem']
    total_amount: Decimal
    currency: str = "USD"
    shipping_address: 'ShippingAddress'
    
    def get_event_type(self) -> str:
        return "order.created"
    
    def get_event_version(self) -> str:
        return "1.0"


class OrderConfirmed(DomainEvent):
    """Event fired when order is confirmed (inventory reserved and payment authorized)"""
    
    order_id: str
    confirmed_at: datetime
    
    def get_event_type(self) -> str:
        return "order.confirmed"
    
    def get_event_version(self) -> str:
        return "1.0"


class OrderShipped(DomainEvent):
    """Event fired when order is shipped"""
    
    order_id: str
    tracking_number: str
    carrier: str
    shipped_at: datetime
    
    def get_event_type(self) -> str:
        return "order.shipped"
    
    def get_event_version(self) -> str:
        return "1.0"


class OrderCancelled(DomainEvent):
    """Event fired when order is cancelled"""
    
    order_id: str
    reason: str
    cancelled_at: datetime
    refund_amount: Decimal
    
    def get_event_type(self) -> str:
        return "order.cancelled"
    
    def get_event_version(self) -> str:
        return "1.0"


class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal


class ShippingAddress(BaseModel):
    street: str
    city: str
    state: str
    zip_code: str
    country: str
```

### **3.2 Order Aggregate**

```python
# src/services/order_service/domain/order_aggregate.py
from enum import Enum
from decimal import Decimal
from datetime import datetime
from typing import List
from src.shared.events.order_events import (
    OrderCreated, OrderConfirmed, OrderShipped, OrderCancelled,
    OrderItem, ShippingAddress
)
from src.shared.events.base import DomainEvent


class OrderStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Order:
    """Order aggregate with event sourcing"""
    
    def __init__(self, order_id: str):
        self.order_id = order_id
        self.version = 0
        self.status = None
        self.customer_id = None
        self.items: List[OrderItem] = []
        self.total_amount = Decimal('0')
        self.shipping_address = None
        self.created_at = None
        self.confirmed_at = None
        self.shipped_at = None
        self.cancelled_at = None
        self.tracking_number = None
        self.carrier = None
        self.cancellation_reason = None
        self.refund_amount = None
        
        # Event tracking
        self._uncommitted_events: List[DomainEvent] = []
    
    @classmethod
    def create_new(
        cls, 
        order_id: str, 
        customer_id: str, 
        items: List[OrderItem], 
        shipping_address: ShippingAddress
    ) -> 'Order':
        """Create a new order"""
        
        order = cls(order_id)
        
        # Calculate total
        total_amount = sum(item.total_price for item in items)
        
        # Create event
        event = OrderCreated(
            metadata=EventMetadata(
                event_type="order.created",
                event_version="1.0",
                source_service="order-service",
                aggregate_id=order_id
            ),
            order_id=order_id,
            customer_id=customer_id,
            items=items,
            total_amount=total_amount,
            shipping_address=shipping_address
        )
        
        # Apply event
        order._apply_event(event)
        order._mark_event_as_uncommitted(event)
        
        return order
    
    def confirm(self) -> None:
        """Confirm the order"""
        
        if self.status != OrderStatus.PENDING:
            raise DomainException(f"Cannot confirm order in status {self.status}")
        
        event = OrderConfirmed(
            metadata=EventMetadata(
                event_type="order.confirmed",
                event_version="1.0",
                source_service="order-service",
                aggregate_id=self.order_id
            ),
            order_id=self.order_id,
            confirmed_at=datetime.utcnow()
        )
        
        self._apply_event(event)
        self._mark_event_as_uncommitted(event)
    
    def ship(self, tracking_number: str, carrier: str) -> None:
        """Ship the order"""
        
        if self.status != OrderStatus.CONFIRMED:
            raise DomainException(f"Cannot ship order in status {self.status}")
        
        event = OrderShipped(
            metadata=EventMetadata(
                event_type="order.shipped",
                event_version="1.0",
                source_service="order-service",
                aggregate_id=self.order_id
            ),
            order_id=self.order_id,
            tracking_number=tracking_number,
            carrier=carrier,
            shipped_at=datetime.utcnow()
        )
        
        self._apply_event(event)
        self._mark_event_as_uncommitted(event)
    
    def cancel(self, reason: str, refund_amount: Decimal = None) -> None:
        """Cancel the order"""
        
        if self.status in [OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
            raise DomainException(f"Cannot cancel order in status {self.status}")
        
        event = OrderCancelled(
            metadata=EventMetadata(
                event_type="order.cancelled",
                event_version="1.0",
                source_service="order-service",
                aggregate_id=self.order_id
            ),
            order_id=self.order_id,
            reason=reason,
            cancelled_at=datetime.utcnow(),
            refund_amount=refund_amount or self.total_amount
        )
        
        self._apply_event(event)
        self._mark_event_as_uncommitted(event)
    
    def load_from_events(self, events: List[DomainEvent]) -> None:
        """Load aggregate state from event history"""
        
        for event in events:
            self._apply_event(event)
            self.version += 1
    
    def get_uncommitted_events(self) -> List[DomainEvent]:
        """Get uncommitted events"""
        return self._uncommitted_events.copy()
    
    def mark_events_as_committed(self) -> None:
        """Mark all uncommitted events as committed"""
        self._uncommitted_events.clear()
    
    def _apply_event(self, event: DomainEvent) -> None:
        """Apply an event to update aggregate state"""
        
        if isinstance(event, OrderCreated):
            self._apply_order_created(event)
        elif isinstance(event, OrderConfirmed):
            self._apply_order_confirmed(event)
        elif isinstance(event, OrderShipped):
            self._apply_order_shipped(event)
        elif isinstance(event, OrderCancelled):
            self._apply_order_cancelled(event)
        else:
            raise UnknownEventException(f"Unknown event type: {type(event)}")
    
    def _apply_order_created(self, event: OrderCreated) -> None:
        self.status = OrderStatus.PENDING
        self.customer_id = event.customer_id
        self.items = event.items
        self.total_amount = event.total_amount
        self.shipping_address = event.shipping_address
        self.created_at = event.metadata.timestamp
    
    def _apply_order_confirmed(self, event: OrderConfirmed) -> None:
        self.status = OrderStatus.CONFIRMED
        self.confirmed_at = event.confirmed_at
    
    def _apply_order_shipped(self, event: OrderShipped) -> None:
        self.status = OrderStatus.SHIPPED
        self.tracking_number = event.tracking_number
        self.carrier = event.carrier
        self.shipped_at = event.shipped_at
    
    def _apply_order_cancelled(self, event: OrderCancelled) -> None:
        self.status = OrderStatus.CANCELLED
        self.cancellation_reason = event.reason
        self.cancelled_at = event.cancelled_at
        self.refund_amount = event.refund_amount
    
    def _mark_event_as_uncommitted(self, event: DomainEvent) -> None:
        self._uncommitted_events.append(event)
        self.version += 1


class DomainException(Exception):
    """Domain-specific exception"""
    pass


class UnknownEventException(Exception):
    """Raised when an unknown event type is encountered"""
    pass
```

---

## ⚡ **Phase 4: Implementation Continuation & Assessment**

### **Deliverables for Each Phase**

#### **Phase 1 Deliverables:**
- [ ] Complete Docker Compose setup with all services
- [ ] Project structure with proper package organization
- [ ] Basic CI/CD pipeline configuration
- [ ] Environment configuration and secrets management

#### **Phase 2 Deliverables:**
- [ ] Event store implementation with PostgreSQL
- [ ] Kafka producer/consumer with reliability features
- [ ] Schema registry integration
- [ ] Monitoring and logging setup

#### **Phase 3 Deliverables:**
- [ ] Complete Order service with event sourcing
- [ ] Order aggregate with proper domain events
- [ ] Event-driven workflow implementation
- [ ] Unit and integration tests

#### **Phase 4 Deliverables:**
- [ ] Inventory service with traditional CRUD
- [ ] Payment service with Saga pattern
- [ ] Notification service
- [ ] API Gateway with request/response handling

### **Assessment Criteria**

#### **Technical Implementation (40%)**
- [ ] Proper event sourcing implementation
- [ ] Correct use of event-driven patterns
- [ ] Code quality and architecture
- [ ] Error handling and resilience
- [ ] Performance optimization

#### **System Design (30%)**
- [ ] Clear separation of concerns
- [ ] Proper bounded contexts
- [ ] Event schema design
- [ ] Scalability considerations
- [ ] Security implementation

#### **Operations & Monitoring (20%)**
- [ ] Comprehensive monitoring setup
- [ ] Distributed tracing implementation
- [ ] Log aggregation and correlation
- [ ] Health checks and alerts
- [ ] Performance metrics

#### **Documentation & Testing (10%)**
- [ ] Architecture documentation
- [ ] API documentation
- [ ] Comprehensive test suite
- [ ] Deployment documentation
- [ ] Troubleshooting guides

---

## 🎯 **Final Project Showcase**

### **Demo Scenarios**

1. **Happy Path Flow**
   - Create order → Inventory check → Payment → Shipping → Delivery

2. **Failure Scenarios**
   - Out of stock handling
   - Payment failure with compensation
   - Service unavailability resilience

3. **Performance Testing**
   - Load testing with concurrent orders
   - Latency monitoring under load
   - Resource usage optimization

4. **Observability Demo**
   - Distributed tracing across services
   - Real-time monitoring dashboard
   - Alert handling and incident response

### **Portfolio Value**

This project demonstrates:
- ✅ **Staff Engineer Level Expertise**: Complex distributed system design and implementation
- ✅ **Production Ready Code**: Enterprise-grade patterns and practices
- ✅ **Leadership Skills**: Architecture decision making and trade-off analysis
- ✅ **Modern Technologies**: Cutting-edge tools and frameworks
- ✅ **Operational Excellence**: Comprehensive monitoring and reliability

**Estimated Completion Time: 8-10 weeks**
**Final Outcome: Production-ready event-driven platform suitable for staff engineer portfolio**

---

## 📋 **Success Metrics**

### **Technical Metrics**
- [ ] System handles 1000+ concurrent orders
- [ ] 99.9% uptime across all services
- [ ] <100ms average response time for API calls
- [ ] <5 second end-to-end order processing
- [ ] Zero data loss during failures

### **Code Quality Metrics**
- [ ] 90%+ test coverage
- [ ] Zero critical security vulnerabilities
- [ ] <10% code duplication
- [ ] All services independently deployable
- [ ] Complete API documentation with examples

This hands-on project will solidify your understanding of event-driven architecture while building a impressive portfolio piece that demonstrates staff-level engineering capabilities.