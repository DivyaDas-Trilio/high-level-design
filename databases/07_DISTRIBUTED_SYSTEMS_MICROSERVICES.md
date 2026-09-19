# Distributed Systems & Microservices Database Patterns

## Database-per-Service Pattern

### Concept Overview
Each microservice owns its database, ensuring loose coupling and independent deployability.

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   User      │    │   Order     │    │   Payment   │
│   Service   │    │   Service   │    │   Service   │
│             │    │             │    │             │
├─────────────┤    ├─────────────┤    ├─────────────┤
│   User DB   │    │  Order DB   │    │ Payment DB  │
│ (PostgreSQL)│    │ (PostgreSQL)│    │  (MongoDB)  │
└─────────────┘    └─────────────┘    └─────────────┘
```

### Implementation Strategies

#### 1. Private Tables per Service
```python
# User Service Database
class UserService:
    def __init__(self):
        self.engine = create_engine("postgresql://user:pass@userdb/users")
        self.Session = sessionmaker(bind=self.engine)

class User(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True)  # UUID
    username = Column(String(50), unique=True)
    email = Column(String(100), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Order Service Database  
class OrderService:
    def __init__(self):
        self.engine = create_engine("postgresql://user:pass@orderdb/orders")
        self.Session = sessionmaker(bind=self.engine)

class Order(Base):
    __tablename__ = 'orders'
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)  # Foreign key reference via API
    total_amount = Column(Numeric(10, 2))
    status = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### 2. Service Communication Patterns
```python
import httpx
import asyncio
from typing import Optional, Dict

class ServiceCommunicator:
    """Handle inter-service communication"""
    
    def __init__(self, service_registry: Dict[str, str]):
        self.service_registry = service_registry
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user data from User Service"""
        try:
            user_service_url = self.service_registry['user_service']
            response = await self.client.get(f"{user_service_url}/users/{user_id}")
            response.raise_for_status()
            return response.json()
        except httpx.RequestError:
            return None
    
    async def get_user_orders(self, user_id: str) -> List[Dict]:
        """Get orders for user from Order Service"""
        try:
            order_service_url = self.service_registry['order_service']
            response = await self.client.get(
                f"{order_service_url}/orders", 
                params={"user_id": user_id}
            )
            response.raise_for_status()
            return response.json()
        except httpx.RequestError:
            return []

# Usage in service
class UserProfileService:
    def __init__(self, db_session, communicator: ServiceCommunicator):
        self.db_session = db_session
        self.communicator = communicator
    
    async def get_user_profile(self, user_id: str) -> Dict:
        """Get complete user profile from multiple services"""
        # Get user data from local database
        user = self.db_session.query(User).filter_by(id=user_id).first()
        if not user:
            raise ValueError("User not found")
        
        # Get orders from Order Service
        orders = await self.communicator.get_user_orders(user_id)
        
        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email
            },
            "orders": orders
        }
```

## Distributed Transaction Management

### Saga Pattern Implementation

#### Orchestration-Based Saga
```python
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Callable, Any, Optional
import asyncio

class SagaStepStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"

@dataclass
class SagaStep:
    name: str
    service_url: str
    action_endpoint: str
    compensation_endpoint: str
    payload: dict
    status: SagaStepStatus = SagaStepStatus.PENDING
    response: Optional[dict] = None
    error: Optional[str] = None

class DistributedSaga:
    """Orchestration-based saga for distributed transactions"""
    
    def __init__(self, saga_id: str, steps: List[SagaStep]):
        self.saga_id = saga_id
        self.steps = steps
        self.completed_steps: List[SagaStep] = []
        self.client = httpx.AsyncClient()
    
    async def execute(self) -> bool:
        """Execute saga steps"""
        try:
            for step in self.steps:
                success = await self._execute_step(step)
                if not success:
                    await self._compensate()
                    return False
                self.completed_steps.append(step)
            
            return True
        except Exception as e:
            await self._compensate()
            raise
    
    async def _execute_step(self, step: SagaStep) -> bool:
        """Execute individual saga step"""
        try:
            url = f"{step.service_url}{step.action_endpoint}"
            response = await self.client.post(url, json=step.payload)
            
            if response.status_code == 200:
                step.status = SagaStepStatus.COMPLETED
                step.response = response.json()
                return True
            else:
                step.status = SagaStepStatus.FAILED
                step.error = f"HTTP {response.status_code}: {response.text}"
                return False
                
        except Exception as e:
            step.status = SagaStepStatus.FAILED
            step.error = str(e)
            return False
    
    async def _compensate(self):
        """Execute compensation in reverse order"""
        for step in reversed(self.completed_steps):
            if step.status == SagaStepStatus.COMPLETED:
                try:
                    url = f"{step.service_url}{step.compensation_endpoint}"
                    compensation_payload = {
                        "saga_id": self.saga_id,
                        "original_response": step.response
                    }
                    
                    await self.client.post(url, json=compensation_payload)
                    step.status = SagaStepStatus.COMPENSATED
                    
                except Exception as e:
                    # Log compensation failure - critical issue
                    logging.error(f"Compensation failed for step {step.name}: {e}")

# Example: Order Processing Saga
async def create_order_saga(user_id: str, items: List[dict], payment_info: dict):
    """Create order using saga pattern"""
    
    order_id = str(uuid.uuid4())
    
    steps = [
        SagaStep(
            name="reserve_inventory",
            service_url="http://inventory-service",
            action_endpoint="/reserve",
            compensation_endpoint="/release",
            payload={"order_id": order_id, "items": items}
        ),
        SagaStep(
            name="create_order",
            service_url="http://order-service", 
            action_endpoint="/orders",
            compensation_endpoint="/orders/cancel",
            payload={"order_id": order_id, "user_id": user_id, "items": items}
        ),
        SagaStep(
            name="process_payment",
            service_url="http://payment-service",
            action_endpoint="/charge",
            compensation_endpoint="/refund", 
            payload={"order_id": order_id, "payment_info": payment_info}
        ),
        SagaStep(
            name="update_inventory",
            service_url="http://inventory-service",
            action_endpoint="/commit",
            compensation_endpoint="/rollback",
            payload={"order_id": order_id, "items": items}
        )
    ]
    
    saga = DistributedSaga(f"order_{order_id}", steps)
    success = await saga.execute()
    
    return {"order_id": order_id, "success": success}
```

#### Choreography-Based Saga
```python
import json
from typing import Dict, Any

class EventBus:
    """Simple event bus for choreography-based sagas"""
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}
    
    def subscribe(self, event_type: str, handler: Callable):
        """Subscribe to event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
    
    async def publish(self, event_type: str, event_data: Dict[str, Any]):
        """Publish event to subscribers"""
        if event_type in self.subscribers:
            for handler in self.subscribers[event_type]:
                try:
                    await handler(event_data)
                except Exception as e:
                    logging.error(f"Event handler failed for {event_type}: {e}")

# Event-driven services
class OrderService:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.setup_event_handlers()
    
    def setup_event_handlers(self):
        self.event_bus.subscribe("inventory_reserved", self.handle_inventory_reserved)
        self.event_bus.subscribe("payment_failed", self.handle_payment_failed)
    
    async def create_order(self, order_data: dict):
        """Create order and publish event"""
        # Create order in database
        order = Order(**order_data)
        # ... save to database
        
        # Publish event for next step
        await self.event_bus.publish("order_created", {
            "order_id": order.id,
            "user_id": order.user_id,
            "items": order.items
        })
    
    async def handle_inventory_reserved(self, event_data: dict):
        """Handle inventory reservation confirmation"""
        order_id = event_data["order_id"]
        # Update order status
        # Publish payment request event
        await self.event_bus.publish("payment_requested", event_data)
    
    async def handle_payment_failed(self, event_data: dict):
        """Handle payment failure - compensate"""
        order_id = event_data["order_id"]
        # Cancel order
        # Publish inventory release event
        await self.event_bus.publish("inventory_release_requested", event_data)

class InventoryService:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.setup_event_handlers()
    
    def setup_event_handlers(self):
        self.event_bus.subscribe("order_created", self.handle_order_created)
        self.event_bus.subscribe("inventory_release_requested", self.handle_release_request)
    
    async def handle_order_created(self, event_data: dict):
        """Reserve inventory for order"""
        try:
            # Reserve inventory logic
            success = await self.reserve_inventory(event_data["items"])
            
            if success:
                await self.event_bus.publish("inventory_reserved", event_data)
            else:
                await self.event_bus.publish("inventory_reservation_failed", event_data)
        except Exception as e:
            await self.event_bus.publish("inventory_reservation_failed", {
                **event_data,
                "error": str(e)
            })
```

## Event Sourcing Pattern

### Event Store Implementation
```python
from datetime import datetime
from typing import List, Dict, Any
import json

class Event(Base):
    """Event sourcing event storage"""
    __tablename__ = 'events'
    
    id = Column(String, primary_key=True)
    aggregate_id = Column(String, nullable=False, index=True)
    aggregate_type = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    event_data = Column(JSON, nullable=False)
    event_version = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('ix_aggregate_version', 'aggregate_id', 'event_version'),
    )

class EventStore:
    """Event store for event sourcing"""
    
    def __init__(self, session):
        self.session = session
    
    def save_events(self, aggregate_id: str, aggregate_type: str, 
                   events: List[Dict], expected_version: int):
        """Save events to store"""
        try:
            for i, event_data in enumerate(events):
                event = Event(
                    id=str(uuid.uuid4()),
                    aggregate_id=aggregate_id,
                    aggregate_type=aggregate_type,
                    event_type=event_data['event_type'],
                    event_data=event_data,
                    event_version=expected_version + i + 1
                )
                self.session.add(event)
            
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
    
    def get_events(self, aggregate_id: str, from_version: int = 0) -> List[Event]:
        """Get events for aggregate"""
        return self.session.query(Event).filter(
            Event.aggregate_id == aggregate_id,
            Event.event_version > from_version
        ).order_by(Event.event_version).all()
    
    def get_all_events_after(self, checkpoint: datetime) -> List[Event]:
        """Get all events after checkpoint for projections"""
        return self.session.query(Event).filter(
            Event.created_at > checkpoint
        ).order_by(Event.created_at).all()

# Aggregate implementation
class UserAggregate:
    """User aggregate using event sourcing"""
    
    def __init__(self, user_id: str):
        self.id = user_id
        self.username = None
        self.email = None
        self.is_active = True
        self.version = 0
        self.uncommitted_events = []
    
    def create_user(self, username: str, email: str):
        """Create user command"""
        if self.version > 0:
            raise ValueError("User already exists")
        
        event = {
            'event_type': 'UserCreated',
            'username': username,
            'email': email,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self._apply_event(event)
        self.uncommitted_events.append(event)
    
    def change_email(self, new_email: str):
        """Change email command"""
        if not self.is_active:
            raise ValueError("Cannot change email for inactive user")
        
        event = {
            'event_type': 'EmailChanged',
            'old_email': self.email,
            'new_email': new_email,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self._apply_event(event)
        self.uncommitted_events.append(event)
    
    def deactivate(self):
        """Deactivate user command"""
        if not self.is_active:
            raise ValueError("User already inactive")
        
        event = {
            'event_type': 'UserDeactivated',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self._apply_event(event)
        self.uncommitted_events.append(event)
    
    def _apply_event(self, event: Dict):
        """Apply event to aggregate state"""
        if event['event_type'] == 'UserCreated':
            self.username = event['username']
            self.email = event['email']
            self.is_active = True
        elif event['event_type'] == 'EmailChanged':
            self.email = event['new_email']
        elif event['event_type'] == 'UserDeactivated':
            self.is_active = False
        
        self.version += 1
    
    def load_from_history(self, events: List[Event]):
        """Rebuild aggregate from event history"""
        for event in events:
            self._apply_event(event.event_data)
    
    def get_uncommitted_events(self) -> List[Dict]:
        """Get uncommitted events"""
        return self.uncommitted_events.copy()
    
    def mark_events_as_committed(self):
        """Mark events as committed"""
        self.uncommitted_events.clear()

# Repository for event-sourced aggregates
class UserRepository:
    """Repository for event-sourced user aggregates"""
    
    def __init__(self, event_store: EventStore):
        self.event_store = event_store
    
    def get(self, user_id: str) -> UserAggregate:
        """Get user aggregate by rebuilding from events"""
        events = self.event_store.get_events(user_id)
        
        user = UserAggregate(user_id)
        user.load_from_history(events)
        
        return user
    
    def save(self, user: UserAggregate):
        """Save user aggregate by storing events"""
        uncommitted_events = user.get_uncommitted_events()
        
        if uncommitted_events:
            self.event_store.save_events(
                user.id,
                'User',
                uncommitted_events,
                user.version - len(uncommitted_events)
            )
            user.mark_events_as_committed()
```

## CQRS (Command Query Responsibility Segregation)

### CQRS Implementation
```python
from abc import ABC, abstractmethod

# Command side (Write model)
class Command(ABC):
    """Base command class"""
    pass

class CreateUserCommand(Command):
    def __init__(self, user_id: str, username: str, email: str):
        self.user_id = user_id
        self.username = username
        self.email = email

class ChangeEmailCommand(Command):
    def __init__(self, user_id: str, new_email: str):
        self.user_id = user_id
        self.new_email = new_email

class CommandHandler(ABC):
    """Base command handler"""
    
    @abstractmethod
    def handle(self, command: Command):
        pass

class UserCommandHandler(CommandHandler):
    """Handle user commands"""
    
    def __init__(self, user_repository: UserRepository, event_bus: EventBus):
        self.repository = user_repository
        self.event_bus = event_bus
    
    def handle(self, command: Command):
        if isinstance(command, CreateUserCommand):
            self._handle_create_user(command)
        elif isinstance(command, ChangeEmailCommand):
            self._handle_change_email(command)
    
    def _handle_create_user(self, command: CreateUserCommand):
        user = UserAggregate(command.user_id)
        user.create_user(command.username, command.email)
        self.repository.save(user)
        
        # Publish events for read side
        for event in user.get_uncommitted_events():
            asyncio.create_task(
                self.event_bus.publish(event['event_type'], event)
            )
    
    def _handle_change_email(self, command: ChangeEmailCommand):
        user = self.repository.get(command.user_id)
        user.change_email(command.new_email)
        self.repository.save(user)

# Query side (Read model)
class UserReadModel(Base):
    """Read model for user queries"""
    __tablename__ = 'user_read_model'
    
    id = Column(String, primary_key=True)
    username = Column(String(50))
    email = Column(String(100))
    is_active = Column(Boolean)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    post_count = Column(Integer, default=0)
    follower_count = Column(Integer, default=0)

class UserQuery(ABC):
    """Base query class"""
    pass

class GetUserByIdQuery(UserQuery):
    def __init__(self, user_id: str):
        self.user_id = user_id

class GetUsersByEmailQuery(UserQuery):
    def __init__(self, email_pattern: str):
        self.email_pattern = email_pattern

class UserQueryHandler:
    """Handle user queries using read models"""
    
    def __init__(self, session):
        self.session = session
    
    def handle(self, query: UserQuery):
        if isinstance(query, GetUserByIdQuery):
            return self._get_user_by_id(query)
        elif isinstance(query, GetUsersByEmailQuery):
            return self._get_users_by_email(query)
    
    def _get_user_by_id(self, query: GetUserByIdQuery):
        return self.session.query(UserReadModel).filter_by(
            id=query.user_id
        ).first()
    
    def _get_users_by_email(self, query: GetUsersByEmailQuery):
        return self.session.query(UserReadModel).filter(
            UserReadModel.email.ilike(f"%{query.email_pattern}%")
        ).all()

# Read model projection
class UserProjection:
    """Project events to read models"""
    
    def __init__(self, session):
        self.session = session
    
    async def handle_user_created(self, event_data: dict):
        """Project UserCreated event"""
        read_model = UserReadModel(
            id=event_data.get('user_id'),
            username=event_data['username'],
            email=event_data['email'],
            is_active=True,
            created_at=datetime.fromisoformat(event_data['timestamp'])
        )
        
        self.session.add(read_model)
        self.session.commit()
    
    async def handle_email_changed(self, event_data: dict):
        """Project EmailChanged event"""
        read_model = self.session.query(UserReadModel).filter_by(
            id=event_data.get('user_id')
        ).first()
        
        if read_model:
            read_model.email = event_data['new_email']
            read_model.updated_at = datetime.fromisoformat(event_data['timestamp'])
            self.session.commit()
```

## Data Synchronization Patterns

### Outbox Pattern
```python
class Outbox(Base):
    """Outbox pattern for reliable event publishing"""
    __tablename__ = 'outbox'
    
    id = Column(String, primary_key=True)
    aggregate_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    event_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    processed = Column(Boolean, default=False)

class OutboxService:
    """Service for managing outbox events"""
    
    def __init__(self, session, event_publisher):
        self.session = session
        self.event_publisher = event_publisher
    
    def add_event(self, aggregate_id: str, event_type: str, event_data: dict):
        """Add event to outbox"""
        outbox_event = Outbox(
            id=str(uuid.uuid4()),
            aggregate_id=aggregate_id,
            event_type=event_type,
            event_data=event_data
        )
        
        self.session.add(outbox_event)
        # Note: Don't commit here - commit with business transaction
    
    async def process_outbox_events(self, batch_size: int = 100):
        """Process unprocessed outbox events"""
        unprocessed_events = self.session.query(Outbox).filter(
            Outbox.processed == False
        ).order_by(Outbox.created_at).limit(batch_size).all()
        
        for event in unprocessed_events:
            try:
                # Publish event
                await self.event_publisher.publish(
                    event.event_type,
                    event.event_data
                )
                
                # Mark as processed
                event.processed = True
                event.processed_at = datetime.utcnow()
                
            except Exception as e:
                logging.error(f"Failed to process outbox event {event.id}: {e}")
        
        self.session.commit()

# Usage with business logic
class UserService:
    def __init__(self, session, outbox_service):
        self.session = session
        self.outbox_service = outbox_service
    
    def create_user(self, user_data: dict):
        """Create user and add event to outbox in same transaction"""
        try:
            # Business logic
            user = User(**user_data)
            self.session.add(user)
            
            # Add event to outbox
            self.outbox_service.add_event(
                user.id,
                'UserCreated',
                {
                    'user_id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            )
            
            # Single transaction for both business logic and outbox
            self.session.commit()
            
        except Exception:
            self.session.rollback()
            raise
```

## Best Practices for Microservices Databases

### 1. Data Consistency Strategies
```python
# Eventual consistency with compensation
class EventualConsistencyHandler:
    def __init__(self, retry_policy):
        self.retry_policy = retry_policy
    
    async def handle_with_retry(self, operation, *args, **kwargs):
        for attempt in range(self.retry_policy.max_retries):
            try:
                return await operation(*args, **kwargs)
            except TemporaryFailure as e:
                if attempt < self.retry_policy.max_retries - 1:
                    await asyncio.sleep(self.retry_policy.backoff_delay * (2 ** attempt))
                else:
                    # Final compensation logic
                    await self.compensate(operation, *args, **kwargs)
                    raise

# 2. Circuit breaker for service calls
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, service_func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")
        
        try:
            result = await service_func(*args, **kwargs)
            
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
                self.failure_count = 0
            
            return result
            
        except Exception as e:
            self.failure_count += 1
            
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
                self.last_failure_time = time.time()
            
            raise
```

This comprehensive guide covers the essential distributed systems and microservices database patterns that senior staff engineers must master for modern application architectures.