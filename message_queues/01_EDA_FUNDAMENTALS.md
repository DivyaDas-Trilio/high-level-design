# Module 1: Event Driven Architecture Fundamentals
## From Request-Response to Event-Driven Systems

---

## 🎯 **Learning Objectives**
By the end of this module, you will:
- ✅ Understand the paradigm shift from synchronous to asynchronous communication
- ✅ Master the distinctions between events, commands, and queries
- ✅ Design robust event schemas with versioning strategies
- ✅ Implement basic pub/sub patterns with Python
- ✅ Analyze trade-offs between EDA and traditional architectures

---

## 📋 **Module Prerequisites**
- Understanding of distributed systems basics
- Experience with REST APIs and HTTP protocols
- Knowledge of database transactions and ACID properties
- Familiarity with Python async/await patterns

---

## 🏗️ **Part 1: The Event-Driven Paradigm Shift**

### Traditional Request-Response Limitations

In traditional synchronous architectures, services communicate through direct API calls:

```python
# Traditional synchronous approach
class OrderService:
    def create_order(self, order_data):
        # 1. Validate order
        if not self.validate_order(order_data):
            raise ValueError("Invalid order")
        
        # 2. Check inventory (synchronous call)
        inventory_service = InventoryService()
        if not inventory_service.check_availability(order_data.items):
            raise ValueError("Items not available")
        
        # 3. Process payment (synchronous call)
        payment_service = PaymentService()
        payment_result = payment_service.charge_customer(order_data.payment_info)
        
        # 4. Update inventory (synchronous call)
        inventory_service.reserve_items(order_data.items)
        
        # 5. Save order
        return self.save_order(order_data)
```

**Problems with this approach:**
- **Tight Coupling**: Services are directly dependent on each other
- **Cascading Failures**: If payment service is down, entire order process fails
- **Poor Scalability**: Each request locks resources across multiple services
- **Performance Bottlenecks**: Response time = sum of all service call times
- **Limited Resilience**: No mechanism to handle partial failures gracefully

### Event-Driven Solution

```python
# Event-driven approach
class OrderService:
    def __init__(self, event_publisher):
        self.event_publisher = event_publisher
    
    def create_order(self, order_data):
        # 1. Validate and save order in PENDING state
        order = self.save_order_pending(order_data)
        
        # 2. Publish event - fire and forget
        event = OrderCreatedEvent(
            order_id=order.id,
            customer_id=order.customer_id,
            items=order.items,
            payment_info=order.payment_info,
            timestamp=datetime.utcnow()
        )
        self.event_publisher.publish("orders.created", event)
        
        return order

# Separate services handle the event asynchronously
class InventoryService:
    def handle_order_created(self, event: OrderCreatedEvent):
        if self.check_availability(event.items):
            self.reserve_items(event.items)
            self.publish_event("inventory.reserved", event.order_id)
        else:
            self.publish_event("inventory.unavailable", event.order_id)

class PaymentService:
    def handle_inventory_reserved(self, event: InventoryReservedEvent):
        payment_result = self.process_payment(event.payment_info)
        if payment_result.success:
            self.publish_event("payment.completed", event.order_id)
        else:
            self.publish_event("payment.failed", event.order_id)
```

**Benefits of the event-driven approach:**
- **Loose Coupling**: Services only know about events, not each other
- **Resilience**: Individual service failures don't cascade
- **Scalability**: Services can scale independently based on event load
- **Extensibility**: New services can subscribe to existing events
- **Auditability**: Complete event log provides audit trail

---

## 📊 **Part 2: Events vs Commands vs Queries (EQC Pattern)**

Understanding the distinction between these three types of messages is crucial for designing clear event-driven systems.

### Commands
Commands represent an **intention to change state**. They are directed to a specific service and can be rejected.

```python
class CreateOrderCommand:
    def __init__(self, customer_id: str, items: List[OrderItem], payment_info: PaymentInfo):
        self.customer_id = customer_id
        self.items = items
        self.payment_info = payment_info
        self.command_id = uuid4()
        self.timestamp = datetime.utcnow()
        
    def validate(self):
        if not self.customer_id:
            raise ValidationError("Customer ID is required")
        if not self.items:
            raise ValidationError("Order must contain items")

class CommandHandler:
    def handle_create_order(self, command: CreateOrderCommand):
        try:
            # Validate command
            command.validate()
            
            # Execute business logic
            order = self.order_service.create_order(command)
            
            # Emit domain event
            self.event_publisher.publish(OrderCreatedEvent(order))
            
        except ValidationError as e:
            self.event_publisher.publish(OrderCreationFailedEvent(command.command_id, str(e)))
```

**Command Characteristics:**
- **Imperative naming**: CreateOrder, UpdateInventory, ProcessPayment
- **Can be rejected**: Commands can fail validation or business rules
- **Single handler**: One service should handle each command type
- **Idempotent**: Safe to retry if processing fails

### Events
Events represent **facts about what happened**. They are published to multiple subscribers and cannot be rejected.

```python
class OrderCreatedEvent:
    def __init__(self, order_id: str, customer_id: str, items: List[OrderItem], 
                 total_amount: Decimal, created_at: datetime):
        self.event_id = uuid4()
        self.event_type = "orders.order_created"
        self.event_version = "1.0"
        self.timestamp = datetime.utcnow()
        
        # Event payload
        self.order_id = order_id
        self.customer_id = customer_id
        self.items = items
        self.total_amount = total_amount
        self.created_at = created_at
        
    def to_dict(self):
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "event_version": self.event_version,
            "timestamp": self.timestamp.isoformat(),
            "data": {
                "order_id": self.order_id,
                "customer_id": self.customer_id,
                "items": [item.to_dict() for item in self.items],
                "total_amount": str(self.total_amount),
                "created_at": self.created_at.isoformat()
            }
        }
```

**Event Characteristics:**
- **Past tense naming**: OrderCreated, PaymentProcessed, InventoryUpdated
- **Immutable**: Events cannot be changed once published
- **Multiple subscribers**: Many services can react to the same event
- **Always successful**: Events represent facts, they cannot fail

### Queries
Queries represent **requests for information** without changing state.

```python
class GetOrderStatusQuery:
    def __init__(self, order_id: str, customer_id: str):
        self.order_id = order_id
        self.customer_id = customer_id
        self.query_id = uuid4()
        self.timestamp = datetime.utcnow()

class QueryHandler:
    def handle_get_order_status(self, query: GetOrderStatusQuery) -> OrderStatusResponse:
        # Read from read model/projection
        order_status = self.order_read_model.get_status(query.order_id, query.customer_id)
        
        return OrderStatusResponse(
            order_id=query.order_id,
            status=order_status.status,
            items=order_status.items,
            tracking_info=order_status.tracking_info
        )
```

**Query Characteristics:**
- **Question-like naming**: GetOrderStatus, FindCustomerByEmail
- **Read-only**: Queries never modify state
- **Can be cached**: Results can be cached for performance
- **May use projections**: Often read from denormalized views

---

## 🔧 **Part 3: Event Schema Design and Versioning**

### Event Schema Best Practices

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

class EventMetadata(BaseModel):
    event_id: str = Field(..., description="Unique identifier for this event")
    event_type: str = Field(..., description="Type of event (e.g., 'orders.created')")
    event_version: str = Field(..., description="Schema version (e.g., '1.0')")
    timestamp: datetime = Field(..., description="When the event occurred")
    correlation_id: Optional[str] = Field(None, description="ID to track related events")
    causation_id: Optional[str] = Field(None, description="ID of the event that caused this one")
    source_service: str = Field(..., description="Service that generated the event")

class OrderItemV1(BaseModel):
    product_id: str
    quantity: int
    unit_price: Decimal

class OrderCreatedEventV1(BaseModel):
    metadata: EventMetadata
    
    # Event payload
    order_id: str
    customer_id: str
    items: List[OrderItemV1]
    total_amount: Decimal
    currency: str = "USD"
    shipping_address: Optional[str] = None
```

### Schema Evolution Strategies

#### 1. Backward Compatible Evolution (Recommended)
```python
# Version 1.0
class OrderItemV1(BaseModel):
    product_id: str
    quantity: int
    unit_price: Decimal

# Version 1.1 - Adding optional fields (backward compatible)
class OrderItemV1_1(BaseModel):
    product_id: str
    quantity: int
    unit_price: Decimal
    discount_amount: Optional[Decimal] = None  # New optional field
    tax_amount: Optional[Decimal] = None       # New optional field

# Version 1.2 - Adding more optional fields
class OrderItemV1_2(BaseModel):
    product_id: str
    quantity: int
    unit_price: Decimal
    discount_amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    product_category: Optional[str] = None     # New optional field
```

#### 2. Breaking Changes (New Major Version)
```python
# Version 2.0 - Breaking change: splitting address into components
class OrderCreatedEventV2(BaseModel):
    metadata: EventMetadata
    
    order_id: str
    customer_id: str
    items: List[OrderItemV2]
    total_amount: Decimal
    currency: str = "USD"
    
    # Breaking change: detailed address instead of string
    shipping_address: ShippingAddressV2

class ShippingAddressV2(BaseModel):
    street: str
    city: str
    state: str
    zip_code: str
    country: str
```

### Schema Registry Implementation

```python
import json
from typing import Dict, Any
from abc import ABC, abstractmethod

class EventSerializer(ABC):
    @abstractmethod
    def serialize(self, event: Any) -> bytes:
        pass
    
    @abstractmethod
    def deserialize(self, data: bytes, event_type: str, version: str) -> Any:
        pass

class JsonEventSerializer(EventSerializer):
    def __init__(self):
        self.schema_registry = {
            ("orders.created", "1.0"): OrderCreatedEventV1,
            ("orders.created", "1.1"): OrderCreatedEventV1_1,
            ("orders.created", "2.0"): OrderCreatedEventV2,
        }
    
    def serialize(self, event: Any) -> bytes:
        if isinstance(event, BaseModel):
            data = event.model_dump()
        else:
            data = event
        return json.dumps(data).encode('utf-8')
    
    def deserialize(self, data: bytes, event_type: str, version: str) -> Any:
        json_data = json.loads(data.decode('utf-8'))
        
        schema_key = (event_type, version)
        if schema_key not in self.schema_registry:
            raise ValueError(f"Unknown event schema: {event_type} v{version}")
        
        event_class = self.schema_registry[schema_key]
        return event_class(**json_data)
```

---

## 🔄 **Part 4: Basic Pub/Sub Implementation**

### Simple In-Memory Event Bus

```python
import asyncio
from typing import Dict, List, Callable, Any
from collections import defaultdict

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._event_queue = asyncio.Queue()
        self._running = False
    
    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe a handler to an event type"""
        self._subscribers[event_type].append(handler)
    
    async def publish(self, event_type: str, event_data: Any):
        """Publish an event to all subscribers"""
        await self._event_queue.put((event_type, event_data))
    
    async def start_processing(self):
        """Start processing events from the queue"""
        self._running = True
        while self._running:
            try:
                event_type, event_data = await asyncio.wait_for(
                    self._event_queue.get(), timeout=1.0
                )
                await self._process_event(event_type, event_data)
            except asyncio.TimeoutError:
                continue
    
    async def _process_event(self, event_type: str, event_data: Any):
        """Process an event by calling all registered handlers"""
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            print(f"No handlers for event type: {event_type}")
            return
        
        # Run all handlers concurrently
        tasks = [self._safe_handle_event(handler, event_data) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _safe_handle_event(self, handler: Callable, event_data: Any):
        """Safely execute a handler, catching any exceptions"""
        try:
            if asyncio.iscoroutinefunction(handler):
                await handler(event_data)
            else:
                handler(event_data)
        except Exception as e:
            print(f"Error in event handler {handler.__name__}: {e}")
    
    def stop(self):
        """Stop processing events"""
        self._running = False

# Example usage
async def main():
    event_bus = EventBus()
    
    # Define event handlers
    async def handle_order_created(event):
        print(f"Order created: {event.order_id}")
        # Simulate some async work
        await asyncio.sleep(0.1)
    
    def handle_order_created_sync(event):
        print(f"Sync handler - Order created: {event.order_id}")
    
    # Subscribe handlers
    event_bus.subscribe("order.created", handle_order_created)
    event_bus.subscribe("order.created", handle_order_created_sync)
    
    # Start event processing
    processing_task = asyncio.create_task(event_bus.start_processing())
    
    # Publish events
    order_event = OrderCreatedEventV1(
        metadata=EventMetadata(
            event_id="123",
            event_type="order.created",
            event_version="1.0",
            timestamp=datetime.utcnow(),
            source_service="order-service"
        ),
        order_id="order-123",
        customer_id="customer-456",
        items=[],
        total_amount=Decimal("99.99")
    )
    
    await event_bus.publish("order.created", order_event)
    
    # Let events process
    await asyncio.sleep(0.5)
    
    # Stop processing
    event_bus.stop()
    await processing_task

if __name__ == "__main__":
    asyncio.run(main())
```

### Redis-based Pub/Sub

```python
import redis.asyncio as redis
import json
from typing import Any, Callable

class RedisPubSub:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_client = redis.from_url(redis_url)
        self.pubsub = self.redis_client.pubsub()
        self.serializer = JsonEventSerializer()
    
    async def publish(self, channel: str, event: Any):
        """Publish an event to a Redis channel"""
        serialized_event = self.serializer.serialize(event)
        await self.redis_client.publish(channel, serialized_event)
    
    async def subscribe(self, channel: str, handler: Callable):
        """Subscribe to a Redis channel and process messages"""
        await self.pubsub.subscribe(channel)
        
        async for message in self.pubsub.listen():
            if message['type'] == 'message':
                try:
                    # Deserialize the event
                    event_data = json.loads(message['data'])
                    
                    # Extract event metadata
                    event_type = event_data.get('metadata', {}).get('event_type')
                    event_version = event_data.get('metadata', {}).get('event_version')
                    
                    # Deserialize to proper event object
                    event = self.serializer.deserialize(
                        message['data'], event_type, event_version
                    )
                    
                    # Handle the event
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                        
                except Exception as e:
                    print(f"Error processing message: {e}")
    
    async def close(self):
        await self.pubsub.close()
        await self.redis_client.close()
```

---

## 📈 **Part 5: Trade-off Analysis**

### When to Use Event-Driven Architecture

#### ✅ **Good Use Cases**

1. **Microservices Integration**
   - Services need to stay loosely coupled
   - Different scaling requirements per service
   - Team autonomy is important

2. **Real-time Data Processing**
   - Streaming analytics requirements
   - Real-time dashboards and monitoring
   - IoT sensor data processing

3. **Workflow Orchestration**
   - Long-running business processes
   - Complex approval workflows
   - Multi-step data transformations

4. **Audit and Compliance**
   - Need for complete event history
   - Regulatory compliance requirements
   - Forensic analysis capabilities

#### ❌ **When NOT to Use EDA**

1. **Simple CRUD Applications**
   - Direct database operations suffice
   - No complex business workflows
   - Immediate consistency requirements

2. **Small Monolithic Applications**
   - Single team, single deployment
   - No independent scaling needs
   - Synchronous operations are simpler

3. **Strong Consistency Requirements**
   - Financial transactions requiring ACID guarantees
   - Inventory systems with immediate consistency needs
   - Real-time gaming with strict ordering

### Performance Characteristics

| Aspect | Synchronous | Asynchronous (EDA) |
|--------|-------------|-------------------|
| **Latency** | Low (direct calls) | Higher (message overhead) |
| **Throughput** | Limited by slowest service | High (parallel processing) |
| **Scalability** | Vertical (limited) | Horizontal (unlimited) |
| **Resilience** | Chain failure risk | Individual service isolation |
| **Consistency** | Strong | Eventual |
| **Complexity** | Low | High |

---

## ✅ **Module 1 Assessment**

### Practical Exercise: Design an Event-Driven Order System

**Scenario:** Design events for an e-commerce order processing system that handles:
- Order creation and validation
- Inventory checking and reservation
- Payment processing
- Shipping and fulfillment
- Customer notifications

**Requirements:**
1. Define event types (commands vs events vs queries)
2. Design event schemas with proper versioning
3. Implement basic pub/sub with error handling
4. Consider failure scenarios and compensating events

### Assessment Questions

1. **Event Design (20 points)**
   - Design 5 different events for the order processing flow
   - Ensure proper naming conventions and payload structure
   - Include metadata and correlation IDs

2. **Schema Evolution (15 points)**
   - Show how to evolve an order event to include new fields
   - Demonstrate backward compatibility preservation
   - Explain versioning strategy

3. **Trade-off Analysis (15 points)**
   - Compare EDA vs synchronous approach for this scenario
   - Identify potential consistency issues and solutions
   - Justify when to use each approach

4. **Implementation (25 points)**
   - Implement the pub/sub system with proper error handling
   - Include event serialization/deserialization
   - Add monitoring and logging

5. **Failure Scenarios (25 points)**
   - Identify 3 potential failure points
   - Design compensating events for rollback scenarios
   - Implement retry and dead letter queue patterns

### Hands-on Lab

Create a working implementation of the order processing system using the concepts learned in this module. The implementation should include:

```python
# Your implementation should demonstrate:
1. Event schema definitions
2. Event bus implementation
3. Multiple event handlers
4. Error handling and logging
5. Basic testing

# Example structure:
src/
├── events/
│   ├── order_events.py
│   ├── inventory_events.py
│   └── payment_events.py
├── handlers/
│   ├── order_handlers.py
│   ├── inventory_handlers.py
│   └── payment_handlers.py
├── event_bus.py
├── serialization.py
└── main.py
```

---

## 🔗 **Next Steps**

After completing this module, you should:
1. ✅ Understand when and why to use event-driven architectures
2. ✅ Be able to design proper event schemas
3. ✅ Implement basic pub/sub patterns
4. ✅ Analyze trade-offs between different architectural approaches

**Next Module:** [02_MESSAGE_QUEUE_TECHNOLOGIES.md](02_MESSAGE_QUEUE_TECHNOLOGIES.md)
- Deep dive into Apache Kafka, RabbitMQ, and cloud messaging services
- Production-ready message queue implementations
- Advanced messaging patterns and configurations

---

## 📚 **Additional Resources**

### Books
- "Building Event-Driven Microservices" by Adam Bellemare
- "Designing Event-Driven Systems" by Ben Stopford
- "Enterprise Integration Patterns" by Gregor Hohpe

### Papers
- "Life Beyond Distributed Transactions" by Pat Helland
- "Event Sourcing" by Martin Fowler
- "CQRS" by Greg Young

### Online Resources
- [Event Storming Workshop Guide](https://www.eventstorming.com/)
- [Domain-Driven Design Reference](https://domainlanguage.com/ddd/)
- [Microservices.io Event-Driven Architecture](https://microservices.io/patterns/data/event-driven-architecture.html)

**Estimated completion time: 2-3 weeks**
**Next module preparation: Set up local Kafka and RabbitMQ environments**