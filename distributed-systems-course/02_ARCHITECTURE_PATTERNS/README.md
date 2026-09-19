# Module 02: Architecture Patterns
*Designing scalable system architectures*

## Learning Objectives

By the end of this module, you will:
- Design microservices architectures using Domain-Driven Design principles
- Implement event-driven architectures with CQRS and Event Sourcing
- Build service mesh infrastructures for inter-service communication
- Apply API gateway patterns for traffic management
- Design system boundaries and manage service dependencies

## Topics Covered

1. **Monoliths vs Microservices** - When and how to decompose
2. **Domain-Driven Design** - Finding service boundaries
3. **Event-Driven Architecture** - Decoupling through events
4. **CQRS & Event Sourcing** - Separating reads from writes
5. **Service Mesh** - Infrastructure for service communication
6. **API Gateway Patterns** - Managing external interfaces

---

## 1. Monoliths vs Microservices

### The Monolith-First Approach

```python
# Example: E-commerce monolith
from flask import Flask, request, jsonify
from sqlalchemy import create_engine, Column, String, Integer, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

app = Flask(__name__)
Base = declarative_base()

# All domain entities in one place
class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True)
    email = Column(String, unique=True)
    name = Column(String)

class Product(Base):
    __tablename__ = 'products'
    id = Column(String, primary_key=True)
    name = Column(String)
    price = Column(Float)
    inventory = Column(Integer)

class Order(Base):
    __tablename__ = 'orders'
    id = Column(String, primary_key=True)
    user_id = Column(String)
    product_id = Column(String)
    quantity = Column(Integer)
    total_amount = Column(Float)

# All business logic in one service
class ECommerceService:
    def __init__(self, db_session):
        self.db = db_session
    
    def create_user(self, email: str, name: str) -> dict:
        user = User(id=str(uuid.uuid4()), email=email, name=name)
        self.db.add(user)
        self.db.commit()
        return {"id": user.id, "email": user.email, "name": user.name}
    
    def add_product(self, name: str, price: float, inventory: int) -> dict:
        product = Product(
            id=str(uuid.uuid4()), 
            name=name, 
            price=price, 
            inventory=inventory
        )
        self.db.add(product)
        self.db.commit()
        return {"id": product.id, "name": product.name, "price": product.price}
    
    def place_order(self, user_id: str, product_id: str, quantity: int) -> dict:
        # Single transaction - ACID guarantees
        user = self.db.query(User).filter_by(id=user_id).first()
        product = self.db.query(Product).filter_by(id=product_id).first()
        
        if not user or not product:
            raise ValueError("User or product not found")
        
        if product.inventory < quantity:
            raise ValueError("Insufficient inventory")
        
        # Update inventory
        product.inventory -= quantity
        
        # Create order
        order = Order(
            id=str(uuid.uuid4()),
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            total_amount=product.price * quantity
        )
        
        self.db.add(order)
        self.db.commit()
        
        return {
            "id": order.id,
            "total_amount": order.total_amount,
            "user": user.name,
            "product": product.name
        }

# Simple API endpoints
service = ECommerceService(db_session)

@app.route('/users', methods=['POST'])
def create_user():
    data = request.json
    return jsonify(service.create_user(data['email'], data['name']))

@app.route('/products', methods=['POST'])
def add_product():
    data = request.json
    return jsonify(service.add_product(data['name'], data['price'], data['inventory']))

@app.route('/orders', methods=['POST'])
def place_order():
    data = request.json
    return jsonify(service.place_order(data['user_id'], data['product_id'], data['quantity']))
```

### When to Break into Microservices

**Triggers for decomposition:**
1. **Team scaling**: Conway's Law - teams > 8-10 people
2. **Different scaling needs**: Some components need more resources
3. **Technology diversity**: Different parts benefit from different tech stacks
4. **Release cadence**: Different features need different deployment cycles
5. **Data isolation**: Different consistency or security requirements

### Microservices Decomposition

```python
# User Service
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class UserCreate(BaseModel):
    email: str
    name: str

class UserService:
    def __init__(self):
        # User service has its own database
        self.engine = create_engine("postgresql://user-service/users")
        
    async def create_user(self, user_data: UserCreate) -> dict:
        # User creation logic
        user = User(id=str(uuid.uuid4()), **user_data.dict())
        # Save to user database
        
        # Publish event for other services
        await self.event_bus.publish("user.created", {
            "user_id": user.id,
            "email": user.email,
            "name": user.name
        })
        
        return {"id": user.id, "email": user.email, "name": user.name}

@app.post("/users")
async def create_user_endpoint(user: UserCreate):
    service = UserService()
    return await service.create_user(user)

# Product Service (separate microservice)
class ProductService:
    def __init__(self):
        # Product service has its own database
        self.engine = create_engine("postgresql://product-service/products")
    
    async def add_product(self, product_data: dict) -> dict:
        product = Product(**product_data)
        # Save to product database
        
        await self.event_bus.publish("product.created", {
            "product_id": product.id,
            "name": product.name,
            "price": product.price
        })
        
        return {"id": product.id, "name": product.name, "price": product.price}

# Order Service (separate microservice)
class OrderService:
    def __init__(self):
        # Order service has its own database
        self.engine = create_engine("postgresql://order-service/orders")
        self.user_service_client = UserServiceClient()
        self.product_service_client = ProductServiceClient()
    
    async def place_order(self, order_data: dict) -> dict:
        # Distributed transaction using Saga pattern
        order_id = str(uuid.uuid4())
        
        try:
            # Step 1: Validate user exists
            user = await self.user_service_client.get_user(order_data['user_id'])
            if not user:
                raise HTTPException(400, "User not found")
            
            # Step 2: Reserve inventory
            reservation = await self.product_service_client.reserve_inventory(
                order_data['product_id'], 
                order_data['quantity']
            )
            
            # Step 3: Create order
            order = Order(id=order_id, **order_data)
            # Save to order database
            
            # Step 4: Process payment (would call payment service)
            # payment = await self.payment_service_client.charge(...)
            
            # Step 5: Commit inventory reservation
            await self.product_service_client.commit_reservation(reservation.id)
            
            await self.event_bus.publish("order.placed", {
                "order_id": order.id,
                "user_id": order.user_id,
                "total_amount": order.total_amount
            })
            
            return {"id": order.id, "status": "placed"}
            
        except Exception as e:
            # Compensate: release inventory reservation
            if reservation:
                await self.product_service_client.cancel_reservation(reservation.id)
            raise
```

---

## 2. Domain-Driven Design (DDD)

### Identifying Bounded Contexts

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

# Domain Model - User Management Context
class UserAggregate:
    """User bounded context - handles identity and authentication"""
    
    def __init__(self, user_id: str, email: str, name: str):
        self.user_id = user_id
        self.email = email
        self.name = name
        self.is_active = True
        self.created_at = datetime.utcnow()
        self.domain_events: List[DomainEvent] = []
    
    def activate(self):
        if self.is_active:
            raise DomainError("User is already active")
        self.is_active = True
        self.domain_events.append(UserActivated(self.user_id))
    
    def deactivate(self):
        if not self.is_active:
            raise DomainError("User is already inactive")
        self.is_active = False
        self.domain_events.append(UserDeactivated(self.user_id))

# Domain Model - Catalog Context
class ProductAggregate:
    """Product catalog bounded context - handles product information"""
    
    def __init__(self, product_id: str, name: str, category: str, price: float):
        self.product_id = product_id
        self.name = name
        self.category = category
        self.price = price
        self.is_available = True
        self.domain_events: List[DomainEvent] = []
    
    def update_price(self, new_price: float):
        if new_price <= 0:
            raise DomainError("Price must be positive")
        
        old_price = self.price
        self.price = new_price
        self.domain_events.append(ProductPriceChanged(
            self.product_id, old_price, new_price
        ))
    
    def discontinue(self):
        self.is_available = False
        self.domain_events.append(ProductDiscontinued(self.product_id))

# Domain Model - Inventory Context
class InventoryAggregate:
    """Inventory bounded context - handles stock levels"""
    
    def __init__(self, product_id: str, quantity: int, reserved: int = 0):
        self.product_id = product_id
        self.quantity = quantity
        self.reserved = reserved
        self.domain_events: List[DomainEvent] = []
    
    @property
    def available(self) -> int:
        return self.quantity - self.reserved
    
    def reserve(self, amount: int) -> str:
        if amount > self.available:
            raise DomainError("Insufficient inventory")
        
        reservation_id = str(uuid.uuid4())
        self.reserved += amount
        
        self.domain_events.append(InventoryReserved(
            self.product_id, amount, reservation_id
        ))
        
        return reservation_id
    
    def commit_reservation(self, amount: int):
        self.quantity -= amount
        self.reserved -= amount
        self.domain_events.append(InventoryCommitted(self.product_id, amount))
    
    def cancel_reservation(self, amount: int):
        self.reserved -= amount
        self.domain_events.append(InventoryReservationCancelled(self.product_id, amount))

# Domain Model - Order Context  
class OrderAggregate:
    """Order bounded context - handles order lifecycle"""
    
    def __init__(self, order_id: str, customer_id: str):
        self.order_id = order_id
        self.customer_id = customer_id
        self.items: List[OrderItem] = []
        self.status = OrderStatus.PENDING
        self.created_at = datetime.utcnow()
        self.domain_events: List[DomainEvent] = []
    
    def add_item(self, product_id: str, quantity: int, price: float):
        if self.status != OrderStatus.PENDING:
            raise DomainError("Cannot modify confirmed order")
        
        item = OrderItem(product_id, quantity, price)
        self.items.append(item)
        
        self.domain_events.append(OrderItemAdded(
            self.order_id, product_id, quantity, price
        ))
    
    def confirm(self):
        if not self.items:
            raise DomainError("Cannot confirm empty order")
        
        self.status = OrderStatus.CONFIRMED
        self.domain_events.append(OrderConfirmed(
            self.order_id, self.customer_id, self.total_amount
        ))
    
    @property
    def total_amount(self) -> float:
        return sum(item.quantity * item.price for item in self.items)

# Domain Services - Cross-aggregate business logic
class OrderDomainService:
    """Coordinates order placement across multiple aggregates"""
    
    def __init__(self, 
                 user_repo: UserRepository,
                 inventory_repo: InventoryRepository,
                 order_repo: OrderRepository):
        self.user_repo = user_repo
        self.inventory_repo = inventory_repo
        self.order_repo = order_repo
    
    async def place_order(self, customer_id: str, items: List[Dict]) -> str:
        """Domain service orchestrates order placement"""
        
        # Validate customer exists and is active
        customer = await self.user_repo.get(customer_id)
        if not customer or not customer.is_active:
            raise DomainError("Invalid customer")
        
        # Create order aggregate
        order = OrderAggregate(str(uuid.uuid4()), customer_id)
        
        # Reserve inventory for each item
        reservations = []
        try:
            for item in items:
                inventory = await self.inventory_repo.get(item['product_id'])
                reservation_id = inventory.reserve(item['quantity'])
                reservations.append((inventory, reservation_id, item['quantity']))
                
                order.add_item(
                    item['product_id'],
                    item['quantity'], 
                    item['price']
                )
            
            # If all reservations successful, confirm order
            order.confirm()
            
            # Commit all reservations
            for inventory, reservation_id, quantity in reservations:
                inventory.commit_reservation(quantity)
                await self.inventory_repo.save(inventory)
            
            await self.order_repo.save(order)
            
            return order.order_id
            
        except Exception as e:
            # Cancel all reservations on failure
            for inventory, reservation_id, quantity in reservations:
                inventory.cancel_reservation(quantity)
                await self.inventory_repo.save(inventory)
            raise

# Context Map - Define relationships between bounded contexts
class ContextMap:
    """
    Defines relationships between bounded contexts:
    
    User Context -> Order Context: Customer/Supplier
    Catalog Context -> Order Context: Published Language (product info)
    Inventory Context <-> Order Context: Partnership (tight collaboration)
    Order Context -> Payment Context: Customer/Supplier
    """
    
    contexts = {
        'user': {
            'services': ['user-service'],
            'database': 'user-db',
            'relationships': {
                'order': 'customer_supplier'  # User context supplies to Order
            }
        },
        'catalog': {
            'services': ['catalog-service'],
            'database': 'catalog-db', 
            'relationships': {
                'order': 'published_language',  # Catalog publishes product schema
                'inventory': 'shared_kernel'    # Shared product concepts
            }
        },
        'inventory': {
            'services': ['inventory-service'],
            'database': 'inventory-db',
            'relationships': {
                'order': 'partnership'  # Close collaboration for reservations
            }
        },
        'order': {
            'services': ['order-service'],
            'database': 'order-db',
            'relationships': {
                'payment': 'customer_supplier'  # Order context uses Payment
            }
        }
    }
```

### Service Boundaries Based on DDD

```python
# User Service - Bounded Context implementation
from fastapi import FastAPI, Depends, HTTPException

app = FastAPI(title="User Service")

class UserService:
    def __init__(self, user_repo: UserRepository, event_bus: EventBus):
        self.user_repo = user_repo
        self.event_bus = event_bus
    
    async def create_user(self, email: str, name: str) -> UserAggregate:
        # Domain logic within bounded context
        if await self.user_repo.exists_by_email(email):
            raise DomainError("Email already exists")
        
        user = UserAggregate(str(uuid.uuid4()), email, name)
        await self.user_repo.save(user)
        
        # Publish domain events
        for event in user.domain_events:
            await self.event_bus.publish(event)
        
        return user

@app.post("/users")
async def create_user_endpoint(
    email: str, 
    name: str,
    user_service: UserService = Depends()
):
    try:
        user = await user_service.create_user(email, name)
        return {"id": user.user_id, "email": user.email, "name": user.name}
    except DomainError as e:
        raise HTTPException(400, str(e))

# Inventory Service - Separate bounded context
class InventoryService:
    def __init__(self, inventory_repo: InventoryRepository, event_bus: EventBus):
        self.inventory_repo = inventory_repo
        self.event_bus = event_bus
    
    async def reserve_inventory(self, product_id: str, quantity: int) -> str:
        inventory = await self.inventory_repo.get(product_id)
        if not inventory:
            raise DomainError("Product not found in inventory")
        
        reservation_id = inventory.reserve(quantity)
        await self.inventory_repo.save(inventory)
        
        # Publish domain events
        for event in inventory.domain_events:
            await self.event_bus.publish(event)
        
        return reservation_id

# Anti-corruption Layer - Protects domain from external services
class PaymentGatewayAdapter:
    """Translates between domain and external payment gateway"""
    
    def __init__(self, external_gateway: ExternalPaymentGateway):
        self.gateway = external_gateway
    
    async def process_payment(self, order: OrderAggregate) -> PaymentResult:
        # Translate domain model to external service format
        external_request = {
            "amount": order.total_amount * 100,  # Convert to cents
            "customer_id": order.customer_id,
            "reference": order.order_id,
            "items": [
                {
                    "sku": item.product_id,
                    "quantity": item.quantity,
                    "amount": int(item.price * 100)
                }
                for item in order.items
            ]
        }
        
        # Call external service
        external_response = await self.gateway.charge(external_request)
        
        # Translate response back to domain
        if external_response["status"] == "success":
            return PaymentResult(
                success=True,
                transaction_id=external_response["transaction_id"],
                amount=order.total_amount
            )
        else:
            return PaymentResult(
                success=False,
                error=external_response.get("error", "Payment failed")
            )
```

---

## 3. Event-Driven Architecture

### Event Types and Patterns

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List
import asyncio

# Domain Events - Internal to bounded context
class DomainEvent(ABC):
    def __init__(self):
        self.event_id = str(uuid.uuid4())
        self.occurred_at = datetime.utcnow()
        self.version = 1

class UserCreated(DomainEvent):
    def __init__(self, user_id: str, email: str, name: str):
        super().__init__()
        self.user_id = user_id
        self.email = email
        self.name = name

class OrderPlaced(DomainEvent):
    def __init__(self, order_id: str, customer_id: str, items: List[Dict], total: float):
        super().__init__()
        self.order_id = order_id
        self.customer_id = customer_id
        self.items = items
        self.total = total

# Integration Events - Cross-bounded context communication
class IntegrationEvent(ABC):
    def __init__(self):
        self.event_id = str(uuid.uuid4())
        self.occurred_at = datetime.utcnow()
        self.version = 1

class CustomerRegistered(IntegrationEvent):
    def __init__(self, customer_id: str, email: str):
        super().__init__()
        self.customer_id = customer_id
        self.email = email

class OrderConfirmed(IntegrationEvent):
    def __init__(self, order_id: str, customer_id: str, amount: float):
        super().__init__()
        self.order_id = order_id
        self.customer_id = customer_id
        self.amount = amount

# Event Bus Implementation
class EventBus:
    def __init__(self):
        self.handlers: Dict[str, List[Callable]] = {}
        self.message_broker = MessageBroker()
    
    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe handler to event type"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
    
    async def publish(self, event: Any):
        """Publish event to subscribers"""
        event_type = event.__class__.__name__
        
        # Handle local subscribers (within same service)
        if event_type in self.handlers:
            for handler in self.handlers[event_type]:
                try:
                    await handler(event)
                except Exception as e:
                    # Log error but don't stop other handlers
                    logging.error(f"Event handler failed for {event_type}: {e}")
        
        # Publish integration events to message broker
        if isinstance(event, IntegrationEvent):
            await self.message_broker.publish(event_type, event)

# Message Broker (Kafka/RabbitMQ adapter)
class MessageBroker:
    def __init__(self, broker_url: str = "kafka://localhost:9092"):
        self.broker_url = broker_url
        self.producer = KafkaProducer(broker_url)
        self.consumers: Dict[str, KafkaConsumer] = {}
    
    async def publish(self, topic: str, event: IntegrationEvent):
        """Publish event to message broker"""
        message = {
            "event_id": event.event_id,
            "event_type": event.__class__.__name__,
            "occurred_at": event.occurred_at.isoformat(),
            "version": event.version,
            "payload": event.__dict__
        }
        
        await self.producer.send(topic, json.dumps(message))
    
    async def subscribe(self, topic: str, handler: Callable):
        """Subscribe to events from message broker"""
        if topic not in self.consumers:
            self.consumers[topic] = KafkaConsumer(topic, self.broker_url)
        
        consumer = self.consumers[topic]
        
        async for message in consumer:
            try:
                event_data = json.loads(message.value)
                await handler(event_data)
            except Exception as e:
                logging.error(f"Failed to process message from {topic}: {e}")

# Event Sourcing Store
class EventStore:
    def __init__(self, db_connection):
        self.db = db_connection
    
    async def save_events(self, aggregate_id: str, events: List[DomainEvent], 
                         expected_version: int):
        """Save events for an aggregate"""
        try:
            for i, event in enumerate(events):
                event_record = {
                    "aggregate_id": aggregate_id,
                    "event_type": event.__class__.__name__,
                    "event_data": json.dumps(event.__dict__, default=str),
                    "event_version": expected_version + i + 1,
                    "occurred_at": event.occurred_at
                }
                await self.db.execute("INSERT INTO events VALUES (...)", event_record)
            
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise
    
    async def get_events(self, aggregate_id: str, from_version: int = 0) -> List[Dict]:
        """Get events for aggregate from specific version"""
        result = await self.db.fetch("""
            SELECT event_type, event_data, event_version, occurred_at 
            FROM events 
            WHERE aggregate_id = %s AND event_version > %s
            ORDER BY event_version
        """, aggregate_id, from_version)
        
        return [dict(row) for row in result]

# Aggregate with Event Sourcing
class EventSourcedAggregate(ABC):
    def __init__(self, aggregate_id: str):
        self.aggregate_id = aggregate_id
        self.version = 0
        self.uncommitted_events: List[DomainEvent] = []
    
    def apply_event(self, event: DomainEvent):
        """Apply event to aggregate state"""
        self._when(event)  # Update state based on event
        self.version += 1
    
    def mark_events_as_committed(self):
        """Clear uncommitted events after saving"""
        self.uncommitted_events.clear()
    
    def load_from_history(self, events: List[Dict]):
        """Rebuild aggregate from event history"""
        for event_data in events:
            event = self._deserialize_event(event_data)
            self.apply_event(event)
    
    @abstractmethod
    def _when(self, event: DomainEvent):
        """Handle specific event types - implemented by subclasses"""
        pass
    
    @abstractmethod
    def _deserialize_event(self, event_data: Dict) -> DomainEvent:
        """Deserialize event from storage"""
        pass

# Example: Event-Sourced Order Aggregate
class EventSourcedOrder(EventSourcedAggregate):
    def __init__(self, order_id: str):
        super().__init__(order_id)
        self.customer_id: Optional[str] = None
        self.items: List[OrderItem] = []
        self.status = OrderStatus.DRAFT
        self.total_amount = 0.0
    
    def create_order(self, customer_id: str):
        if self.version > 0:
            raise DomainError("Order already exists")
        
        event = OrderCreated(self.aggregate_id, customer_id)
        self.apply_event(event)
        self.uncommitted_events.append(event)
    
    def add_item(self, product_id: str, quantity: int, price: float):
        if self.status != OrderStatus.DRAFT:
            raise DomainError("Cannot modify non-draft order")
        
        event = ItemAdded(self.aggregate_id, product_id, quantity, price)
        self.apply_event(event)
        self.uncommitted_events.append(event)
    
    def _when(self, event: DomainEvent):
        if isinstance(event, OrderCreated):
            self.customer_id = event.customer_id
            self.status = OrderStatus.DRAFT
        elif isinstance(event, ItemAdded):
            item = OrderItem(event.product_id, event.quantity, event.price)
            self.items.append(item)
            self.total_amount += event.quantity * event.price
        elif isinstance(event, OrderConfirmed):
            self.status = OrderStatus.CONFIRMED
```

### Event Processing Patterns

```python
# Command Handler with Events
class OrderCommandHandler:
    def __init__(self, order_repo: EventSourcedRepository, event_bus: EventBus):
        self.order_repo = order_repo
        self.event_bus = event_bus
    
    async def handle_create_order(self, command: CreateOrderCommand):
        order = EventSourcedOrder(command.order_id)
        order.create_order(command.customer_id)
        
        await self.order_repo.save(order)
        
        # Publish domain events
        for event in order.uncommitted_events:
            await self.event_bus.publish(event)

# Event Projections for Read Models
class OrderProjection:
    """Projects order events to read models for queries"""
    
    def __init__(self, read_db):
        self.read_db = read_db
    
    async def handle_order_created(self, event: OrderCreated):
        await self.read_db.execute("""
            INSERT INTO order_summary (order_id, customer_id, status, created_at)
            VALUES (%s, %s, %s, %s)
        """, event.order_id, event.customer_id, "DRAFT", event.occurred_at)
    
    async def handle_item_added(self, event: ItemAdded):
        await self.read_db.execute("""
            UPDATE order_summary 
            SET total_amount = total_amount + %s
            WHERE order_id = %s
        """, event.quantity * event.price, event.order_id)
        
        await self.read_db.execute("""
            INSERT INTO order_items (order_id, product_id, quantity, price)
            VALUES (%s, %s, %s, %s)
        """, event.order_id, event.product_id, event.quantity, event.price)

# Saga Orchestrator using Events
class OrderSaga:
    """Coordinates order fulfillment across multiple services"""
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.setup_event_handlers()
    
    def setup_event_handlers(self):
        self.event_bus.subscribe("OrderCreated", self.handle_order_created)
        self.event_bus.subscribe("InventoryReserved", self.handle_inventory_reserved)
        self.event_bus.subscribe("PaymentProcessed", self.handle_payment_processed)
        self.event_bus.subscribe("PaymentFailed", self.handle_payment_failed)
    
    async def handle_order_created(self, event: OrderCreated):
        """Start saga when order is created"""
        # Request inventory reservation
        await self.event_bus.publish(ReserveInventoryCommand(
            event.order_id, event.items
        ))
    
    async def handle_inventory_reserved(self, event: InventoryReserved):
        """Continue saga after inventory reserved"""
        # Request payment processing
        await self.event_bus.publish(ProcessPaymentCommand(
            event.order_id, event.amount
        ))
    
    async def handle_payment_processed(self, event: PaymentProcessed):
        """Complete saga after successful payment"""
        # Confirm order
        await self.event_bus.publish(ConfirmOrderCommand(event.order_id))
        
        # Commit inventory
        await self.event_bus.publish(CommitInventoryCommand(event.order_id))
    
    async def handle_payment_failed(self, event: PaymentFailed):
        """Compensate saga after payment failure"""
        # Cancel order
        await self.event_bus.publish(CancelOrderCommand(event.order_id))
        
        # Release inventory
        await self.event_bus.publish(ReleaseInventoryCommand(event.order_id))
```

---

## 4. CQRS & Event Sourcing

### CQRS Implementation

```python
# Command Side (Write Model)
from abc import ABC, abstractmethod

class Command(ABC):
    """Base class for all commands"""
    def __init__(self):
        self.command_id = str(uuid.uuid4())
        self.timestamp = datetime.utcnow()

class CreateProductCommand(Command):
    def __init__(self, product_id: str, name: str, price: float, category: str):
        super().__init__()
        self.product_id = product_id
        self.name = name
        self.price = price
        self.category = category

class UpdateProductPriceCommand(Command):
    def __init__(self, product_id: str, new_price: float):
        super().__init__()
        self.product_id = product_id
        self.new_price = new_price

# Command Handlers (Write Side)
class ProductCommandHandler:
    def __init__(self, product_repo: ProductRepository, event_bus: EventBus):
        self.product_repo = product_repo
        self.event_bus = event_bus
    
    async def handle(self, command: Command):
        if isinstance(command, CreateProductCommand):
            await self._handle_create_product(command)
        elif isinstance(command, UpdateProductPriceCommand):
            await self._handle_update_price(command)
    
    async def _handle_create_product(self, command: CreateProductCommand):
        # Check business rules
        if await self.product_repo.exists(command.product_id):
            raise DomainError("Product already exists")
        
        # Create aggregate and apply command
        product = ProductAggregate.create(
            command.product_id,
            command.name,
            command.price,
            command.category
        )
        
        # Save aggregate (events get persisted)
        await self.product_repo.save(product)
        
        # Publish events for read side
        for event in product.uncommitted_events:
            await self.event_bus.publish(event)
    
    async def _handle_update_price(self, command: UpdateProductPriceCommand):
        # Load aggregate from events
        product = await self.product_repo.get(command.product_id)
        if not product:
            raise DomainError("Product not found")
        
        # Apply business logic
        product.update_price(command.new_price)
        
        # Save updated aggregate
        await self.product_repo.save(product)
        
        # Publish events
        for event in product.uncommitted_events:
            await self.event_bus.publish(event)

# Query Side (Read Model)
class ProductReadModel:
    """Optimized for queries"""
    def __init__(self, product_id: str, name: str, price: float, 
                 category: str, is_available: bool, stock_level: int):
        self.product_id = product_id
        self.name = name
        self.price = price
        self.category = category
        self.is_available = is_available
        self.stock_level = stock_level

class Query(ABC):
    """Base class for queries"""
    pass

class GetProductByIdQuery(Query):
    def __init__(self, product_id: str):
        self.product_id = product_id

class GetProductsByCategoryQuery(Query):
    def __init__(self, category: str, page: int = 1, page_size: int = 20):
        self.category = category
        self.page = page
        self.page_size = page_size

class SearchProductsQuery(Query):
    def __init__(self, search_term: str, filters: Dict[str, Any]):
        self.search_term = search_term
        self.filters = filters

# Query Handlers (Read Side)
class ProductQueryHandler:
    def __init__(self, read_db):
        self.read_db = read_db
    
    async def handle(self, query: Query) -> Any:
        if isinstance(query, GetProductByIdQuery):
            return await self._get_product_by_id(query)
        elif isinstance(query, GetProductsByCategoryQuery):
            return await self._get_products_by_category(query)
        elif isinstance(query, SearchProductsQuery):
            return await self._search_products(query)
    
    async def _get_product_by_id(self, query: GetProductByIdQuery) -> Optional[ProductReadModel]:
        result = await self.read_db.fetch_one("""
            SELECT product_id, name, price, category, is_available, stock_level
            FROM product_read_model
            WHERE product_id = %s
        """, query.product_id)
        
        return ProductReadModel(**result) if result else None
    
    async def _get_products_by_category(self, query: GetProductsByCategoryQuery) -> List[ProductReadModel]:
        offset = (query.page - 1) * query.page_size
        
        results = await self.read_db.fetch_all("""
            SELECT product_id, name, price, category, is_available, stock_level
            FROM product_read_model
            WHERE category = %s AND is_available = true
            ORDER BY name
            LIMIT %s OFFSET %s
        """, query.category, query.page_size, offset)
        
        return [ProductReadModel(**row) for row in results]
    
    async def _search_products(self, query: SearchProductsQuery) -> List[ProductReadModel]:
        # Complex search query optimized for reads
        sql = """
            SELECT product_id, name, price, category, is_available, stock_level,
                   ts_rank(search_vector, plainto_tsquery(%s)) as rank
            FROM product_read_model
            WHERE search_vector @@ plainto_tsquery(%s)
        """
        params = [query.search_term, query.search_term]
        
        # Add filters
        if 'category' in query.filters:
            sql += " AND category = %s"
            params.append(query.filters['category'])
        
        if 'price_range' in query.filters:
            min_price, max_price = query.filters['price_range']
            sql += " AND price BETWEEN %s AND %s"
            params.extend([min_price, max_price])
        
        sql += " ORDER BY rank DESC, name"
        
        results = await self.read_db.fetch_all(sql, *params)
        return [ProductReadModel(**row) for row in results]

# Event Projections (Update Read Models)
class ProductProjection:
    """Projects product events to read models"""
    
    def __init__(self, read_db, event_bus: EventBus):
        self.read_db = read_db
        self.setup_event_handlers(event_bus)
    
    def setup_event_handlers(self, event_bus: EventBus):
        event_bus.subscribe("ProductCreated", self.handle_product_created)
        event_bus.subscribe("ProductPriceChanged", self.handle_price_changed)
        event_bus.subscribe("ProductDiscontinued", self.handle_product_discontinued)
        event_bus.subscribe("InventoryUpdated", self.handle_inventory_updated)
    
    async def handle_product_created(self, event: ProductCreated):
        await self.read_db.execute("""
            INSERT INTO product_read_model 
            (product_id, name, price, category, is_available, stock_level, search_vector)
            VALUES (%s, %s, %s, %s, %s, %s, to_tsvector(%s))
        """, 
        event.product_id, event.name, event.price, event.category, 
        True, 0, f"{event.name} {event.category}")
    
    async def handle_price_changed(self, event: ProductPriceChanged):
        await self.read_db.execute("""
            UPDATE product_read_model
            SET price = %s, updated_at = %s
            WHERE product_id = %s
        """, event.new_price, datetime.utcnow(), event.product_id)
    
    async def handle_product_discontinued(self, event: ProductDiscontinued):
        await self.read_db.execute("""
            UPDATE product_read_model
            SET is_available = false, updated_at = %s
            WHERE product_id = %s
        """, datetime.utcnow(), event.product_id)
    
    async def handle_inventory_updated(self, event: InventoryUpdated):
        """Handle events from inventory service to update stock levels"""
        await self.read_db.execute("""
            UPDATE product_read_model
            SET stock_level = %s, updated_at = %s
            WHERE product_id = %s
        """, event.new_stock_level, datetime.utcnow(), event.product_id)

# CQRS Mediator Pattern
class Mediator:
    """Mediates between commands/queries and their handlers"""
    
    def __init__(self):
        self.command_handlers: Dict[type, Any] = {}
        self.query_handlers: Dict[type, Any] = {}
    
    def register_command_handler(self, command_type: type, handler: Any):
        self.command_handlers[command_type] = handler
    
    def register_query_handler(self, query_type: type, handler: Any):
        self.query_handlers[query_type] = handler
    
    async def send_command(self, command: Command):
        handler = self.command_handlers.get(type(command))
        if not handler:
            raise ValueError(f"No handler registered for {type(command)}")
        
        await handler.handle(command)
    
    async def send_query(self, query: Query):
        handler = self.query_handlers.get(type(query))
        if not handler:
            raise ValueError(f"No handler registered for {type(query)}")
        
        return await handler.handle(query)
```

---

## 5. Service Mesh Patterns

### Istio Service Mesh Configuration

```yaml
# Product Service Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: product-service
  labels:
    app: product-service
    version: v1
spec:
  replicas: 3
  selector:
    matchLabels:
      app: product-service
      version: v1
  template:
    metadata:
      labels:
        app: product-service
        version: v1
      annotations:
        sidecar.istio.io/inject: "true"  # Enable Istio sidecar injection
    spec:
      containers:
      - name: product-service
        image: myregistry/product-service:v1.0
        ports:
        - containerPort: 8080
        env:
        - name: DB_HOST
          value: "product-db"
---
# Service definition
apiVersion: v1
kind: Service
metadata:
  name: product-service
  labels:
    app: product-service
spec:
  ports:
  - port: 8080
    name: http
  selector:
    app: product-service
---
# Virtual Service - Traffic routing
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: product-service-vs
spec:
  hosts:
  - product-service
  http:
  - match:
    - headers:
        x-version:
          exact: v2
    route:
    - destination:
        host: product-service
        subset: v2
      weight: 100
  - route:
    - destination:
        host: product-service
        subset: v1
      weight: 90
    - destination:
        host: product-service
        subset: v2
      weight: 10  # Canary deployment: 10% traffic to v2
---
# Destination Rule - Service subsets and policies
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: product-service-dr
spec:
  host: product-service
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        http1MaxPendingRequests: 50
        maxRequestsPerConnection: 10
    circuitBreaker:
      consecutiveErrors: 5
      interval: 30s
      baseEjectionTime: 30s
      maxEjectionPercent: 50
    retryPolicy:
      attempts: 3
      perTryTimeout: 2s
  subsets:
  - name: v1
    labels:
      version: v1
  - name: v2
    labels:
      version: v2
    trafficPolicy:
      connectionPool:
        tcp:
          maxConnections: 50  # More conservative for v2
---
# Security Policy - mTLS and authorization
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: product-service-mtls
spec:
  selector:
    matchLabels:
      app: product-service
  mtls:
    mode: STRICT  # Require mTLS for all communication
---
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata:
  name: product-service-authz
spec:
  selector:
    matchLabels:
      app: product-service
  rules:
  - from:
    - source:
        principals: ["cluster.local/ns/default/sa/order-service"]
    to:
    - operation:
        methods: ["GET", "POST"]
        paths: ["/api/products/*"]
  - from:
    - source:
        principals: ["cluster.local/ns/default/sa/inventory-service"]
    to:
    - operation:
        methods: ["GET"]
        paths: ["/api/products/*/inventory"]
```

### Service Mesh Observability

```python
# Distributed Tracing Integration
import opentelemetry
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# Set up tracing
tracer = trace.get_tracer(__name__)

def setup_tracing(app_name: str):
    # Configure Jaeger exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name="jaeger-agent",
        agent_port=6831,
    )
    
    # Set up tracing
    trace.set_tracer_provider(
        TracerProvider(
            resource=Resource.create({"service.name": app_name})
        )
    )
    
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(jaeger_exporter)
    )
    
    # Auto-instrument frameworks
    FastAPIInstrumentor.instrument()
    RequestsInstrumentor.instrument()
    SQLAlchemyInstrumentor.instrument()

# Custom tracing in business logic
class TracedProductService:
    def __init__(self, product_repo, inventory_client):
        self.product_repo = product_repo
        self.inventory_client = inventory_client
    
    async def get_product_with_inventory(self, product_id: str) -> Dict:
        with tracer.start_as_current_span("get_product_with_inventory") as span:
            span.set_attribute("product.id", product_id)
            
            # Get product info
            with tracer.start_as_current_span("get_product_info"):
                product = await self.product_repo.get(product_id)
                if not product:
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", "Product not found")
                    raise ProductNotFoundError(product_id)
            
            # Get inventory info
            with tracer.start_as_current_span("get_inventory_info") as inventory_span:
                inventory_span.set_attribute("inventory.product_id", product_id)
                try:
                    inventory = await self.inventory_client.get_inventory(product_id)
                    span.set_attribute("inventory.available", inventory.available)
                except Exception as e:
                    inventory_span.set_attribute("error", True)
                    inventory_span.set_attribute("error.message", str(e))
                    # Don't fail the request, just mark inventory as unavailable
                    inventory = {"available": 0, "reserved": 0}
            
            result = {
                "product": product,
                "inventory": inventory,
                "in_stock": inventory.get("available", 0) > 0
            }
            
            span.set_attribute("result.in_stock", result["in_stock"])
            return result

# Service-to-Service Communication with Circuit Breaker
import aiohttp
import asyncio
from typing import Optional

class ServiceClient:
    """Base class for service-to-service communication"""
    
    def __init__(self, service_url: str, timeout: int = 30):
        self.service_url = service_url
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.circuit_breaker = CircuitBreaker(failure_threshold=5)
    
    async def get(self, path: str, headers: Optional[Dict] = None) -> Dict:
        async with self.circuit_breaker:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Add tracing headers
                if not headers:
                    headers = {}
                
                # Inject trace context into headers for distributed tracing
                trace_headers = {}
                trace.get_current_span().get_span_context().trace_id
                headers.update(trace_headers)
                
                async with session.get(f"{self.service_url}{path}", headers=headers) as response:
                    response.raise_for_status()
                    return await response.json()

class InventoryServiceClient(ServiceClient):
    def __init__(self):
        super().__init__(service_url="http://inventory-service:8080")
    
    async def get_inventory(self, product_id: str) -> Dict:
        return await self.get(f"/api/inventory/{product_id}")
    
    async def reserve_inventory(self, product_id: str, quantity: int) -> Dict:
        async with aiohttp.ClientSession() as session:
            payload = {"product_id": product_id, "quantity": quantity}
            async with session.post(
                f"{self.service_url}/api/inventory/reserve",
                json=payload
            ) as response:
                response.raise_for_status()
                return await response.json()
```

---

## 6. API Gateway Patterns

### API Gateway Implementation

```python
# API Gateway with FastAPI
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import jwt
import time
from typing import Dict, Optional

app = FastAPI(title="E-commerce API Gateway")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://mystore.com", "https://admin.mystore.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class APIGateway:
    def __init__(self):
        self.services = {
            "user": "http://user-service:8080",
            "product": "http://product-service:8080", 
            "order": "http://order-service:8080",
            "inventory": "http://inventory-service:8080"
        }
        self.rate_limiter = RateLimiter()
        self.circuit_breakers = {
            service: CircuitBreaker(failure_threshold=5) 
            for service in self.services
        }
    
    async def proxy_request(self, service: str, path: str, method: str, 
                          headers: Dict, body: Optional[bytes] = None) -> Dict:
        """Proxy request to backend service"""
        
        if service not in self.services:
            raise HTTPException(404, f"Service {service} not found")
        
        service_url = self.services[service]
        circuit_breaker = self.circuit_breakers[service]
        
        # Circuit breaker check
        if circuit_breaker.state == "OPEN":
            raise HTTPException(503, f"Service {service} is currently unavailable")
        
        try:
            async with httpx.AsyncClient() as client:
                # Add correlation ID for tracing
                headers["X-Correlation-ID"] = headers.get("X-Correlation-ID", str(uuid.uuid4()))
                
                response = await client.request(
                    method=method,
                    url=f"{service_url}{path}",
                    headers=headers,
                    content=body,
                    timeout=30.0
                )
                
                circuit_breaker.record_success()
                
                return {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.content
                }
                
        except Exception as e:
            circuit_breaker.record_failure()
            raise HTTPException(502, f"Service {service} error: {str(e)}")

# Authentication Middleware
class JWTAuthMiddleware:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
    
    async def authenticate(self, request: Request) -> Optional[Dict]:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return {
                "user_id": payload.get("sub"),
                "email": payload.get("email"),
                "roles": payload.get("roles", [])
            }
        except jwt.InvalidTokenError:
            return None

# Rate Limiting
from collections import defaultdict, deque
import time

class RateLimiter:
    def __init__(self):
        # Store request timestamps per client
        self.clients: Dict[str, deque] = defaultdict(deque)
        self.limits = {
            "default": {"requests": 100, "window": 60},  # 100 req/min
            "premium": {"requests": 1000, "window": 60}, # 1000 req/min
            "admin": {"requests": 10000, "window": 60}   # 10000 req/min
        }
    
    def is_allowed(self, client_id: str, tier: str = "default") -> bool:
        now = time.time()
        limit_config = self.limits.get(tier, self.limits["default"])
        window_size = limit_config["window"]
        max_requests = limit_config["requests"]
        
        # Clean old entries
        client_requests = self.clients[client_id]
        while client_requests and client_requests[0] < now - window_size:
            client_requests.popleft()
        
        # Check if limit exceeded
        if len(client_requests) >= max_requests:
            return False
        
        # Add current request
        client_requests.append(now)
        return True

# API Gateway Routes
gateway = APIGateway()
auth_middleware = JWTAuthMiddleware("your-secret-key")

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Get client identifier
    client_id = request.client.host
    
    # Check authentication for tier
    auth_info = await auth_middleware.authenticate(request)
    tier = "premium" if auth_info and "premium" in auth_info.get("roles", []) else "default"
    
    if not gateway.rate_limiter.is_allowed(client_id, tier):
        return HTTPException(429, "Rate limit exceeded")
    
    response = await call_next(request)
    return response

# User Management Routes
@app.post("/api/users")
async def create_user(request: Request):
    body = await request.body()
    headers = dict(request.headers)
    
    result = await gateway.proxy_request(
        service="user",
        path="/users",
        method="POST",
        headers=headers,
        body=body
    )
    
    return Response(
        content=result["body"],
        status_code=result["status_code"],
        headers=result["headers"]
    )

@app.get("/api/users/{user_id}")
async def get_user(user_id: str, request: Request, auth_info: Dict = Depends(auth_middleware.authenticate)):
    if not auth_info:
        raise HTTPException(401, "Authentication required")
    
    # Authorization check
    if auth_info["user_id"] != user_id and "admin" not in auth_info.get("roles", []):
        raise HTTPException(403, "Access denied")
    
    headers = dict(request.headers)
    headers["X-User-ID"] = auth_info["user_id"]
    
    result = await gateway.proxy_request(
        service="user",
        path=f"/users/{user_id}",
        method="GET",
        headers=headers
    )
    
    return Response(
        content=result["body"],
        status_code=result["status_code"]
    )

# Product Routes (Public)
@app.get("/api/products")
async def list_products(request: Request):
    headers = dict(request.headers)
    
    result = await gateway.proxy_request(
        service="product",
        path="/products" + ("?" + str(request.query_params) if request.query_params else ""),
        method="GET",
        headers=headers
    )
    
    return Response(
        content=result["body"],
        status_code=result["status_code"]
    )

# Order Routes (Authenticated)
@app.post("/api/orders")
async def create_order(request: Request, auth_info: Dict = Depends(auth_middleware.authenticate)):
    if not auth_info:
        raise HTTPException(401, "Authentication required")
    
    body = await request.body()
    headers = dict(request.headers)
    headers["X-User-ID"] = auth_info["user_id"]
    
    result = await gateway.proxy_request(
        service="order",
        path="/orders",
        method="POST",
        headers=headers,
        body=body
    )
    
    return Response(
        content=result["body"],
        status_code=result["status_code"]
    )

# Admin Routes (Role-based)
@app.get("/api/admin/metrics")
async def get_metrics(auth_info: Dict = Depends(auth_middleware.authenticate)):
    if not auth_info or "admin" not in auth_info.get("roles", []):
        raise HTTPException(403, "Admin access required")
    
    # Aggregate metrics from all services
    metrics = {}
    for service_name in gateway.services:
        try:
            result = await gateway.proxy_request(
                service=service_name,
                path="/metrics",
                method="GET",
                headers={"X-Admin": "true"}
            )
            metrics[service_name] = result
        except:
            metrics[service_name] = {"error": "Service unavailable"}
    
    return metrics

# Health Check Endpoint
@app.get("/health")
async def health_check():
    """Gateway health check"""
    service_health = {}
    
    for service_name, service_url in gateway.services.items():
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{service_url}/health", timeout=5.0)
                service_health[service_name] = "healthy" if response.status_code == 200 else "unhealthy"
        except:
            service_health[service_name] = "unreachable"
    
    overall_health = "healthy" if all(h == "healthy" for h in service_health.values()) else "degraded"
    
    return {
        "gateway": "healthy",
        "services": service_health,
        "overall": overall_health
    }

# Request/Response Transformation
@app.middleware("http")
async def transform_middleware(request: Request, call_next):
    # Request transformation
    if request.url.path.startswith("/api/v1/"):
        # Transform v1 API calls to v2 format
        request.url.path = request.url.path.replace("/api/v1/", "/api/v2/")
    
    response = await call_next(request)
    
    # Response transformation
    if request.headers.get("Accept") == "application/xml":
        # Convert JSON to XML if requested
        # (implementation would depend on your needs)
        pass
    
    return response
```

---

## Labs and Projects

### Lab 1: Microservices Decomposition
Take a monolithic e-commerce application and decompose it into microservices based on DDD principles.

### Lab 2: Event-Driven Architecture
Implement a complete order processing system using event sourcing and CQRS.

### Lab 3: Service Mesh Setup
Deploy microservices with Istio and configure traffic management, security, and observability.

### Lab 4: API Gateway Implementation
Build a production-ready API gateway with authentication, rate limiting, and circuit breakers.

## Assessment

### Architecture Review Exercise
Design a distributed system for a specific domain (e.g., social media platform, IoT system, financial services) covering:

1. Service boundaries and responsibilities
2. Communication patterns and data flow
3. Consistency and transaction management
4. Scalability and reliability patterns
5. Security and operational concerns

## References

### Essential Reading
- "Building Microservices" by Sam Newman
- "Microservices Patterns" by Chris Richardson  
- "Event Storming" by Alberto Brandolini

### Technical Resources
- [Microservices.io](https://microservices.io/) - Patterns and practices
- [Istio Documentation](https://istio.io/latest/docs/)
- [CQRS Journey](https://docs.microsoft.com/en-us/previous-versions/msp-n-p/jj554200(v=pandp.10))

---

*Next: [Module 03 - Data Consistency](../03_DATA_CONSISTENCY/)*