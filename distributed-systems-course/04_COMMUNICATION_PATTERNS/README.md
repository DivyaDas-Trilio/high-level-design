# Module 04: Communication Patterns
*Inter-service communication in distributed systems*

## Learning Objectives

By the end of this module, you will:
- Design effective APIs using REST, GraphQL, and gRPC
- Implement asynchronous communication with message queues and event streaming
- Build service discovery and load balancing mechanisms
- Apply message patterns for reliable communication
- Choose appropriate communication protocols for different use cases

## Topics Covered

1. **Synchronous Communication** - REST, GraphQL, gRPC, and their trade-offs
2. **Asynchronous Messaging** - Message queues, pub/sub, and event streaming
3. **Service Discovery** - Finding and connecting services dynamically
4. **Load Balancing** - Distributing requests across service instances
5. **Message Reliability** - Ensuring message delivery and processing
6. **Communication Protocols** - Protocol selection and optimization

---

## 1. Synchronous Communication

### REST API Design and Implementation

```python
from fastapi import FastAPI, HTTPException, Depends, Query, Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
from enum import Enum

# Data Models
class ProductStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"

class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    price: float = Field(..., gt=0)
    category_id: str
    status: ProductStatus = ProductStatus.ACTIVE

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    price: Optional[float] = Field(None, gt=0)
    category_id: Optional[str] = None
    status: Optional[ProductStatus] = None

class ProductResponse(ProductBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class PaginatedResponse(BaseModel):
    items: List[ProductResponse]
    total: int
    page: int
    size: int
    pages: int

# RESTful Product Service
app = FastAPI(
    title="Product Catalog API",
    description="RESTful API for product catalog management",
    version="1.0.0"
)

class ProductService:
    def __init__(self):
        # In-memory storage for demo
        self.products: Dict[str, Dict] = {}
        self.categories: Dict[str, str] = {
            "electronics": "Electronics",
            "books": "Books", 
            "clothing": "Clothing"
        }
    
    def create_product(self, product_data: ProductCreate) -> ProductResponse:
        """Create a new product"""
        if product_data.category_id not in self.categories:
            raise HTTPException(status_code=400, detail="Invalid category")
        
        product_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        product = {
            "id": product_id,
            "name": product_data.name,
            "description": product_data.description,
            "price": product_data.price,
            "category_id": product_data.category_id,
            "status": product_data.status,
            "created_at": now,
            "updated_at": now
        }
        
        self.products[product_id] = product
        return ProductResponse(**product)
    
    def get_product(self, product_id: str) -> ProductResponse:
        """Get product by ID"""
        if product_id not in self.products:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return ProductResponse(**self.products[product_id])
    
    def update_product(self, product_id: str, product_data: ProductUpdate) -> ProductResponse:
        """Update existing product"""
        if product_id not in self.products:
            raise HTTPException(status_code=404, detail="Product not found")
        
        product = self.products[product_id]
        update_data = product_data.dict(exclude_unset=True)
        
        if "category_id" in update_data and update_data["category_id"] not in self.categories:
            raise HTTPException(status_code=400, detail="Invalid category")
        
        for field, value in update_data.items():
            product[field] = value
        
        product["updated_at"] = datetime.utcnow()
        return ProductResponse(**product)
    
    def delete_product(self, product_id: str) -> bool:
        """Delete product"""
        if product_id not in self.products:
            raise HTTPException(status_code=404, detail="Product not found")
        
        del self.products[product_id]
        return True
    
    def list_products(self, category_id: Optional[str] = None, 
                     status: Optional[ProductStatus] = None,
                     page: int = 1, size: int = 10) -> PaginatedResponse:
        """List products with filtering and pagination"""
        filtered_products = list(self.products.values())
        
        # Apply filters
        if category_id:
            filtered_products = [p for p in filtered_products if p["category_id"] == category_id]
        
        if status:
            filtered_products = [p for p in filtered_products if p["status"] == status]
        
        # Sort by creation date
        filtered_products.sort(key=lambda x: x["created_at"], reverse=True)
        
        # Pagination
        total = len(filtered_products)
        start = (page - 1) * size
        end = start + size
        items = filtered_products[start:end]
        
        return PaginatedResponse(
            items=[ProductResponse(**item) for item in items],
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size
        )

# Dependency injection
product_service = ProductService()

def get_product_service() -> ProductService:
    return product_service

# REST Endpoints following RESTful principles
@app.post("/api/v1/products", response_model=ProductResponse, status_code=201)
def create_product(
    product: ProductCreate,
    service: ProductService = Depends(get_product_service)
):
    """Create a new product"""
    return service.create_product(product)

@app.get("/api/v1/products/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: str = Path(..., description="Product ID"),
    service: ProductService = Depends(get_product_service)
):
    """Get product by ID"""
    return service.get_product(product_id)

@app.put("/api/v1/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str = Path(..., description="Product ID"),
    product: ProductUpdate = ...,
    service: ProductService = Depends(get_product_service)
):
    """Update existing product"""
    return service.update_product(product_id, product)

@app.delete("/api/v1/products/{product_id}", status_code=204)
def delete_product(
    product_id: str = Path(..., description="Product ID"),
    service: ProductService = Depends(get_product_service)
):
    """Delete product"""
    service.delete_product(product_id)

@app.get("/api/v1/products", response_model=PaginatedResponse)
def list_products(
    category_id: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[ProductStatus] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    service: ProductService = Depends(get_product_service)
):
    """List products with filtering and pagination"""
    return service.list_products(category_id, status, page, size)

# API versioning and content negotiation
@app.get("/api/v1/products/{product_id}/summary")
def get_product_summary(product_id: str):
    """Get product summary (lighter response)"""
    product = product_service.get_product(product_id)
    return {
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "status": product.status
    }
```

### GraphQL Implementation

```python
import strawberry
from typing import List, Optional
import asyncio

# GraphQL Types
@strawberry.type
class Product:
    id: str
    name: str
    description: Optional[str]
    price: float
    category: "Category"
    status: str
    created_at: datetime

@strawberry.type
class Category:
    id: str
    name: str
    products: List[Product]

@strawberry.input
class ProductInput:
    name: str
    description: Optional[str]
    price: float
    category_id: str

@strawberry.input
class ProductFilter:
    category_id: Optional[str] = None
    status: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None

# GraphQL Resolvers
@strawberry.type
class Query:
    @strawberry.field
    def product(self, id: str) -> Optional[Product]:
        """Get single product by ID"""
        return product_service.get_product_graphql(id)
    
    @strawberry.field
    def products(self, filter: Optional[ProductFilter] = None, 
                limit: int = 10, offset: int = 0) -> List[Product]:
        """Get products with filtering"""
        return product_service.get_products_graphql(filter, limit, offset)
    
    @strawberry.field
    def categories(self) -> List[Category]:
        """Get all categories"""
        return product_service.get_categories_graphql()
    
    @strawberry.field
    async def product_recommendations(self, product_id: str) -> List[Product]:
        """Get product recommendations (async resolver)"""
        # Simulate async operation (e.g., ML model call)
        await asyncio.sleep(0.1)
        return product_service.get_recommendations_graphql(product_id)

@strawberry.type 
class Mutation:
    @strawberry.mutation
    def create_product(self, input: ProductInput) -> Product:
        """Create new product"""
        return product_service.create_product_graphql(input)
    
    @strawberry.mutation
    def update_product(self, id: str, input: ProductInput) -> Product:
        """Update existing product"""
        return product_service.update_product_graphql(id, input)
    
    @strawberry.mutation
    def delete_product(self, id: str) -> bool:
        """Delete product"""
        return product_service.delete_product_graphql(id)

# GraphQL Schema
schema = strawberry.Schema(query=Query, mutation=Mutation)

# GraphQL Service Extensions
class ProductService:
    # ... (previous REST methods)
    
    def get_product_graphql(self, product_id: str) -> Optional[Product]:
        """GraphQL resolver for single product"""
        if product_id not in self.products:
            return None
        
        product_data = self.products[product_id]
        category = self._get_category(product_data["category_id"])
        
        return Product(
            id=product_data["id"],
            name=product_data["name"],
            description=product_data["description"],
            price=product_data["price"],
            category=category,
            status=product_data["status"],
            created_at=product_data["created_at"]
        )
    
    def get_products_graphql(self, filter: Optional[ProductFilter], 
                           limit: int, offset: int) -> List[Product]:
        """GraphQL resolver for product list"""
        products = list(self.products.values())
        
        # Apply filters
        if filter:
            if filter.category_id:
                products = [p for p in products if p["category_id"] == filter.category_id]
            if filter.status:
                products = [p for p in products if p["status"] == filter.status]
            if filter.min_price:
                products = [p for p in products if p["price"] >= filter.min_price]
            if filter.max_price:
                products = [p for p in products if p["price"] <= filter.max_price]
        
        # Pagination
        products = products[offset:offset + limit]
        
        # Convert to GraphQL objects
        result = []
        for product_data in products:
            category = self._get_category(product_data["category_id"])
            product = Product(
                id=product_data["id"],
                name=product_data["name"],
                description=product_data["description"],
                price=product_data["price"],
                category=category,
                status=product_data["status"],
                created_at=product_data["created_at"]
            )
            result.append(product)
        
        return result
    
    def _get_category(self, category_id: str) -> Category:
        """Get category with lazy loading of products"""
        category_name = self.categories.get(category_id, "Unknown")
        
        # Lazy load products in this category
        category_products = [
            p for p in self.products.values() 
            if p["category_id"] == category_id
        ]
        
        return Category(
            id=category_id,
            name=category_name,
            products=[self.get_product_graphql(p["id"]) for p in category_products]
        )

# DataLoader for N+1 query optimization
from strawberry.dataloader import DataLoader

async def load_categories(keys: List[str]) -> List[Category]:
    """Batch load categories to avoid N+1 queries"""
    categories = {}
    for key in keys:
        category_name = product_service.categories.get(key, "Unknown")
        categories[key] = Category(id=key, name=category_name, products=[])
    
    return [categories[key] for key in keys]

category_loader = DataLoader(load_fn=load_categories)
```

### gRPC Implementation

```python
# product.proto (Protocol Buffer definition)
"""
syntax = "proto3";

package product;

service ProductService {
    rpc GetProduct(GetProductRequest) returns (Product);
    rpc ListProducts(ListProductsRequest) returns (ListProductsResponse);
    rpc CreateProduct(CreateProductRequest) returns (Product);
    rpc UpdateProduct(UpdateProductRequest) returns (Product);
    rpc DeleteProduct(DeleteProductRequest) returns (google.protobuf.Empty);
    rpc StreamProducts(StreamProductsRequest) returns (stream Product);
}

message Product {
    string id = 1;
    string name = 2;
    string description = 3;
    double price = 4;
    string category_id = 5;
    ProductStatus status = 6;
    int64 created_at = 7;
    int64 updated_at = 8;
}

enum ProductStatus {
    ACTIVE = 0;
    INACTIVE = 1;
    DISCONTINUED = 2;
}

message GetProductRequest {
    string id = 1;
}

message ListProductsRequest {
    string category_id = 1;
    ProductStatus status = 2;
    int32 page = 3;
    int32 size = 4;
}

message ListProductsResponse {
    repeated Product products = 1;
    int32 total = 2;
    int32 page = 3;
    int32 size = 4;
}

message CreateProductRequest {
    string name = 1;
    string description = 2;
    double price = 3;
    string category_id = 4;
}

message UpdateProductRequest {
    string id = 1;
    string name = 2;
    string description = 3;
    double price = 4;
    string category_id = 5;
    ProductStatus status = 6;
}

message DeleteProductRequest {
    string id = 1;
}

message StreamProductsRequest {
    string category_id = 1;
}
"""

# Generated Python code (simplified)
import grpc
from concurrent import futures
import time
from typing import Iterator

# gRPC Service Implementation
class ProductServiceServicer:
    def __init__(self):
        self.product_service = ProductService()
    
    def GetProduct(self, request, context):
        """Get single product"""
        try:
            product_data = self.product_service.products.get(request.id)
            if not product_data:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Product not found")
                return Product()
            
            return Product(
                id=product_data["id"],
                name=product_data["name"],
                description=product_data["description"] or "",
                price=product_data["price"],
                category_id=product_data["category_id"],
                status=self._convert_status(product_data["status"]),
                created_at=int(product_data["created_at"].timestamp()),
                updated_at=int(product_data["updated_at"].timestamp())
            )
        
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return Product()
    
    def ListProducts(self, request, context):
        """List products with pagination"""
        try:
            # Apply filters
            products = list(self.product_service.products.values())
            
            if request.category_id:
                products = [p for p in products if p["category_id"] == request.category_id]
            
            if request.status != ProductStatus.ACTIVE:  # Default is ACTIVE
                status_str = self._convert_status_to_string(request.status)
                products = [p for p in products if p["status"] == status_str]
            
            # Pagination
            page = max(1, request.page)
            size = max(1, min(100, request.size))
            start = (page - 1) * size
            end = start + size
            
            paginated_products = products[start:end]
            
            # Convert to protobuf
            product_list = []
            for product_data in paginated_products:
                product_list.append(Product(
                    id=product_data["id"],
                    name=product_data["name"],
                    description=product_data["description"] or "",
                    price=product_data["price"],
                    category_id=product_data["category_id"],
                    status=self._convert_status(product_data["status"]),
                    created_at=int(product_data["created_at"].timestamp()),
                    updated_at=int(product_data["updated_at"].timestamp())
                ))
            
            return ListProductsResponse(
                products=product_list,
                total=len(products),
                page=page,
                size=size
            )
        
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return ListProductsResponse()
    
    def CreateProduct(self, request, context):
        """Create new product"""
        try:
            product_create = ProductCreate(
                name=request.name,
                description=request.description,
                price=request.price,
                category_id=request.category_id
            )
            
            product = self.product_service.create_product(product_create)
            
            return Product(
                id=product.id,
                name=product.name,
                description=product.description or "",
                price=product.price,
                category_id=product.category_id,
                status=self._convert_status(product.status),
                created_at=int(product.created_at.timestamp()),
                updated_at=int(product.updated_at.timestamp())
            )
        
        except Exception as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
            return Product()
    
    def StreamProducts(self, request, context) -> Iterator[Product]:
        """Stream products (server streaming)"""
        try:
            products = list(self.product_service.products.values())
            
            if request.category_id:
                products = [p for p in products if p["category_id"] == request.category_id]
            
            for product_data in products:
                yield Product(
                    id=product_data["id"],
                    name=product_data["name"],
                    description=product_data["description"] or "",
                    price=product_data["price"],
                    category_id=product_data["category_id"],
                    status=self._convert_status(product_data["status"]),
                    created_at=int(product_data["created_at"].timestamp()),
                    updated_at=int(product_data["updated_at"].timestamp())
                )
                
                # Simulate streaming delay
                time.sleep(0.1)
        
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
    
    def _convert_status(self, status_str: str) -> int:
        """Convert string status to protobuf enum"""
        status_map = {
            "active": 0,
            "inactive": 1,
            "discontinued": 2
        }
        return status_map.get(status_str, 0)
    
    def _convert_status_to_string(self, status_enum: int) -> str:
        """Convert protobuf enum to string"""
        status_map = {
            0: "active",
            1: "inactive", 
            2: "discontinued"
        }
        return status_map.get(status_enum, "active")

# gRPC Server Setup
def serve():
    """Start gRPC server"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Add service to server
    add_ProductServiceServicer_to_server(ProductServiceServicer(), server)
    
    # Configure server
    listen_addr = '[::]:50051'
    server.add_insecure_port(listen_addr)
    
    print(f"Starting gRPC server on {listen_addr}")
    server.start()
    
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)

# gRPC Client
class ProductServiceClient:
    def __init__(self, host='localhost', port=50051):
        self.channel = grpc.insecure_channel(f'{host}:{port}')
        self.stub = ProductServiceStub(self.channel)
    
    def get_product(self, product_id: str) -> Product:
        """Get product by ID"""
        request = GetProductRequest(id=product_id)
        return self.stub.GetProduct(request)
    
    def list_products(self, category_id: str = None, page: int = 1, size: int = 10):
        """List products"""
        request = ListProductsRequest(
            category_id=category_id or "",
            page=page,
            size=size
        )
        return self.stub.ListProducts(request)
    
    def stream_products(self, category_id: str = None):
        """Stream products"""
        request = StreamProductsRequest(category_id=category_id or "")
        for product in self.stub.StreamProducts(request):
            yield product
    
    def close(self):
        """Close connection"""
        self.channel.close()
```

---

## 2. Asynchronous Messaging

### Message Queue Implementation

```python
import asyncio
import json
import uuid
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass
from enum import Enum
import time
from collections import defaultdict, deque

class MessagePriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class Message:
    id: str
    topic: str
    payload: Any
    priority: MessagePriority = MessagePriority.NORMAL
    created_at: float = None
    expires_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    headers: Dict[str, str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.headers is None:
            self.headers = {}

class MessageQueue:
    """In-memory message queue with priorities and reliability features"""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.queues: Dict[str, deque] = defaultdict(deque)
        self.subscriptions: Dict[str, List[Callable]] = defaultdict(list)
        self.dlq: deque = deque()  # Dead Letter Queue
        self.metrics = {
            "messages_published": 0,
            "messages_consumed": 0,
            "messages_failed": 0,
            "messages_in_dlq": 0
        }
    
    async def publish(self, topic: str, payload: Any, 
                     priority: MessagePriority = MessagePriority.NORMAL,
                     ttl: Optional[int] = None, headers: Dict[str, str] = None) -> str:
        """Publish message to topic"""
        message_id = str(uuid.uuid4())
        expires_at = time.time() + ttl if ttl else None
        
        message = Message(
            id=message_id,
            topic=topic,
            payload=payload,
            priority=priority,
            expires_at=expires_at,
            headers=headers or {}
        )
        
        # Check queue size limit
        if len(self.queues[topic]) >= self.max_size:
            raise Exception(f"Queue {topic} is full")
        
        # Insert message based on priority
        self._insert_by_priority(self.queues[topic], message)
        
        self.metrics["messages_published"] += 1
        
        # Trigger delivery to subscribers
        asyncio.create_task(self._deliver_to_subscribers(topic, message))
        
        return message_id
    
    def _insert_by_priority(self, queue: deque, message: Message):
        """Insert message into queue based on priority"""
        # For simplicity, append to end (in practice, would use priority queue)
        # Higher priority messages would be inserted at the front
        if message.priority == MessagePriority.CRITICAL:
            queue.appendleft(message)
        else:
            queue.append(message)
    
    async def subscribe(self, topic: str, handler: Callable) -> None:
        """Subscribe to topic with message handler"""
        self.subscriptions[topic].append(handler)
        
        # Process any existing messages in queue
        await self._process_queue_for_subscriber(topic, handler)
    
    async def consume(self, topic: str, auto_ack: bool = True) -> Optional[Message]:
        """Consume single message from topic"""
        queue = self.queues[topic]
        
        while queue:
            message = queue.popleft()
            
            # Check if message expired
            if message.expires_at and time.time() > message.expires_at:
                continue
            
            if auto_ack:
                self.metrics["messages_consumed"] += 1
            
            return message
        
        return None
    
    async def ack(self, message: Message):
        """Acknowledge message processing"""
        self.metrics["messages_consumed"] += 1
    
    async def nack(self, message: Message, requeue: bool = True):
        """Negative acknowledge - message processing failed"""
        message.retry_count += 1
        
        if requeue and message.retry_count <= message.max_retries:
            # Requeue with exponential backoff delay
            delay = 2 ** (message.retry_count - 1)
            await asyncio.sleep(delay)
            
            # Requeue message
            self._insert_by_priority(self.queues[message.topic], message)
        else:
            # Send to dead letter queue
            self.dlq.append(message)
            self.metrics["messages_in_dlq"] += 1
        
        self.metrics["messages_failed"] += 1
    
    async def _deliver_to_subscribers(self, topic: str, message: Message):
        """Deliver message to all topic subscribers"""
        handlers = self.subscriptions.get(topic, [])
        
        for handler in handlers:
            try:
                await handler(message)
                await self.ack(message)
            except Exception as e:
                print(f"Message handler failed: {e}")
                await self.nack(message)
    
    async def _process_queue_for_subscriber(self, topic: str, handler: Callable):
        """Process existing queue messages for new subscriber"""
        while True:
            message = await self.consume(topic, auto_ack=False)
            if not message:
                break
            
            try:
                await handler(message)
                await self.ack(message)
            except Exception as e:
                print(f"Message handler failed: {e}")
                await self.nack(message)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get queue metrics"""
        queue_sizes = {topic: len(queue) for topic, queue in self.queues.items()}
        
        return {
            **self.metrics,
            "queue_sizes": queue_sizes,
            "active_topics": list(self.queues.keys()),
            "subscriber_counts": {
                topic: len(handlers) 
                for topic, handlers in self.subscriptions.items()
            }
        }

# Event Streaming Implementation
class EventStream:
    """Event streaming with partitioning and consumer groups"""
    
    def __init__(self, stream_name: str, partition_count: int = 3):
        self.stream_name = stream_name
        self.partition_count = partition_count
        self.partitions: List[deque] = [deque() for _ in range(partition_count)]
        self.consumer_groups: Dict[str, ConsumerGroup] = {}
        self.event_id_counter = 0
    
    async def publish_event(self, event_data: Dict[str, Any], 
                           partition_key: Optional[str] = None) -> str:
        """Publish event to stream"""
        # Determine partition
        if partition_key:
            partition = hash(partition_key) % self.partition_count
        else:
            partition = self.event_id_counter % self.partition_count
        
        # Create event
        event_id = f"{self.stream_name}-{self.event_id_counter}"
        event = {
            "id": event_id,
            "partition": partition,
            "data": event_data,
            "timestamp": time.time(),
            "offset": len(self.partitions[partition])
        }
        
        # Add to partition
        self.partitions[partition].append(event)
        self.event_id_counter += 1
        
        # Notify consumer groups
        for consumer_group in self.consumer_groups.values():
            await consumer_group.notify_new_event(partition)
        
        return event_id
    
    def create_consumer_group(self, group_id: str, 
                            consumer_count: int = 1) -> 'ConsumerGroup':
        """Create consumer group for this stream"""
        consumer_group = ConsumerGroup(
            group_id=group_id,
            stream=self,
            consumer_count=consumer_count
        )
        
        self.consumer_groups[group_id] = consumer_group
        return consumer_group
    
    def get_events(self, partition: int, start_offset: int = 0, 
                  limit: int = 100) -> List[Dict]:
        """Get events from partition starting at offset"""
        partition_events = list(self.partitions[partition])
        return partition_events[start_offset:start_offset + limit]

class ConsumerGroup:
    """Consumer group for event stream processing"""
    
    def __init__(self, group_id: str, stream: EventStream, consumer_count: int):
        self.group_id = group_id
        self.stream = stream
        self.consumer_count = consumer_count
        self.partition_offsets: Dict[int, int] = {}
        self.partition_assignments: Dict[str, List[int]] = {}
        self.message_handlers: List[Callable] = []
        
        # Assign partitions to consumers
        self._assign_partitions()
    
    def _assign_partitions(self):
        """Assign stream partitions to consumers"""
        partitions_per_consumer = self.stream.partition_count // self.consumer_count
        extra_partitions = self.stream.partition_count % self.consumer_count
        
        partition_index = 0
        for consumer_id in range(self.consumer_count):
            consumer_name = f"{self.group_id}-consumer-{consumer_id}"
            
            # Assign base partitions
            partitions = list(range(
                partition_index, 
                partition_index + partitions_per_consumer
            ))
            
            # Assign extra partition if available
            if consumer_id < extra_partitions:
                partitions.append(partition_index + partitions_per_consumer)
                partition_index += partitions_per_consumer + 1
            else:
                partition_index += partitions_per_consumer
            
            self.partition_assignments[consumer_name] = partitions
            
            # Initialize offsets
            for partition in partitions:
                if partition not in self.partition_offsets:
                    self.partition_offsets[partition] = 0
    
    def add_handler(self, handler: Callable):
        """Add message handler"""
        self.message_handlers.append(handler)
    
    async def consume_events(self, consumer_id: str, batch_size: int = 10):
        """Consume events for specific consumer"""
        assigned_partitions = self.partition_assignments.get(consumer_id, [])
        
        consumed_events = []
        
        for partition in assigned_partitions:
            current_offset = self.partition_offsets[partition]
            events = self.stream.get_events(partition, current_offset, batch_size)
            
            for event in events:
                consumed_events.append(event)
                
                # Process with handlers
                for handler in self.message_handlers:
                    try:
                        await handler(event)
                    except Exception as e:
                        print(f"Event processing failed: {e}")
                
                # Update offset
                self.partition_offsets[partition] = event["offset"] + 1
        
        return consumed_events
    
    async def notify_new_event(self, partition: int):
        """Notify consumer group of new event in partition"""
        # In a real implementation, this would wake up sleeping consumers
        pass
    
    def commit_offsets(self):
        """Commit current offsets (for fault tolerance)"""
        # In a real implementation, this would persist offsets
        print(f"Committing offsets for group {self.group_id}: {self.partition_offsets}")

# Pub/Sub Pattern Implementation
class PubSubBroker:
    """Publish-Subscribe message broker"""
    
    def __init__(self):
        self.subscriptions: Dict[str, List[Callable]] = defaultdict(list)
        self.topic_patterns: Dict[str, List[Callable]] = defaultdict(list)
        self.metrics = defaultdict(int)
    
    async def publish(self, topic: str, message: Any, headers: Dict[str, str] = None):
        """Publish message to topic"""
        envelope = {
            "topic": topic,
            "message": message,
            "headers": headers or {},
            "timestamp": time.time(),
            "message_id": str(uuid.uuid4())
        }
        
        self.metrics[f"published_{topic}"] += 1
        
        # Deliver to direct subscribers
        await self._deliver_to_subscribers(topic, envelope)
        
        # Deliver to pattern subscribers
        await self._deliver_to_pattern_subscribers(topic, envelope)
    
    async def subscribe(self, topic: str, handler: Callable):
        """Subscribe to specific topic"""
        self.subscriptions[topic].append(handler)
    
    async def subscribe_pattern(self, pattern: str, handler: Callable):
        """Subscribe to topic pattern (e.g., 'orders.*')"""
        self.topic_patterns[pattern].append(handler)
    
    async def _deliver_to_subscribers(self, topic: str, envelope: Dict):
        """Deliver message to topic subscribers"""
        subscribers = self.subscriptions.get(topic, [])
        
        for handler in subscribers:
            try:
                await handler(envelope)
                self.metrics[f"delivered_{topic}"] += 1
            except Exception as e:
                print(f"Subscriber failed: {e}")
                self.metrics[f"failed_{topic}"] += 1
    
    async def _deliver_to_pattern_subscribers(self, topic: str, envelope: Dict):
        """Deliver message to pattern subscribers"""
        for pattern, handlers in self.topic_patterns.items():
            if self._topic_matches_pattern(topic, pattern):
                for handler in handlers:
                    try:
                        await handler(envelope)
                        self.metrics[f"pattern_delivered_{pattern}"] += 1
                    except Exception as e:
                        print(f"Pattern subscriber failed: {e}")
                        self.metrics[f"pattern_failed_{pattern}"] += 1
    
    def _topic_matches_pattern(self, topic: str, pattern: str) -> bool:
        """Check if topic matches pattern"""
        # Simple wildcard matching (e.g., 'orders.*' matches 'orders.created')
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            return topic.startswith(prefix)
        
        return topic == pattern

# Example Usage
async def messaging_example():
    """Demonstrate different messaging patterns"""
    
    print("=== Message Queue Example ===")
    
    # Message Queue
    queue = MessageQueue()
    
    # Publisher
    await queue.publish("orders", {"order_id": "123", "amount": 99.99}, 
                       priority=MessagePriority.HIGH)
    await queue.publish("orders", {"order_id": "124", "amount": 199.99})
    
    # Consumer
    async def order_processor(message: Message):
        print(f"Processing order: {message.payload}")
        if message.payload["amount"] > 150:
            raise Exception("High value order requires approval")
    
    await queue.subscribe("orders", order_processor)
    
    print("Queue metrics:", queue.get_metrics())
    
    print("\n=== Event Streaming Example ===")
    
    # Event Stream
    stream = EventStream("user_events", partition_count=2)
    
    # Publisher
    await stream.publish_event(
        {"user_id": "user1", "action": "login"},
        partition_key="user1"
    )
    await stream.publish_event(
        {"user_id": "user2", "action": "purchase", "amount": 50},
        partition_key="user2"  
    )
    
    # Consumer Group
    consumer_group = stream.create_consumer_group("analytics_group", consumer_count=1)
    
    async def analytics_processor(event):
        print(f"Analytics: {event['data']}")
    
    consumer_group.add_handler(analytics_processor)
    
    # Consume events
    events = await consumer_group.consume_events("analytics_group-consumer-0")
    print(f"Consumed {len(events)} events")
    
    print("\n=== Pub/Sub Example ===")
    
    # Pub/Sub
    broker = PubSubBroker()
    
    # Subscribers
    async def email_notifier(envelope):
        print(f"Sending email for: {envelope['topic']}")
    
    async def sms_notifier(envelope):
        print(f"Sending SMS for: {envelope['topic']}")
    
    await broker.subscribe("user.registered", email_notifier)
    await broker.subscribe_pattern("user.*", sms_notifier)
    
    # Publisher
    await broker.publish("user.registered", {"user_id": "new_user", "email": "user@example.com"})
    await broker.publish("user.login", {"user_id": "existing_user"})
```

---

## 3. Service Discovery

### Dynamic Service Discovery

```python
import asyncio
import json
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import time
import random

class ServiceStatus(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    STOPPING = "stopping"

@dataclass
class ServiceInstance:
    id: str
    name: str
    host: str
    port: int
    protocol: str = "http"
    status: ServiceStatus = ServiceStatus.STARTING
    metadata: Dict[str, str] = field(default_factory=dict)
    health_check_url: Optional[str] = None
    last_heartbeat: float = field(default_factory=time.time)
    registration_time: float = field(default_factory=time.time)
    tags: Set[str] = field(default_factory=set)

class ServiceRegistry:
    """Service registry with health checking and load balancing"""
    
    def __init__(self, heartbeat_interval: int = 30, health_check_interval: int = 10):
        self.services: Dict[str, Dict[str, ServiceInstance]] = {}
        self.heartbeat_interval = heartbeat_interval
        self.health_check_interval = health_check_interval
        self.watchers: Dict[str, List[callable]] = {}
        self.running = False
    
    async def register(self, service: ServiceInstance) -> bool:
        """Register service instance"""
        if service.name not in self.services:
            self.services[service.name] = {}
        
        self.services[service.name][service.id] = service
        service.status = ServiceStatus.HEALTHY
        
        print(f"Registered service: {service.name} ({service.id}) at {service.host}:{service.port}")
        
        # Notify watchers
        await self._notify_watchers(service.name, "registered", service)
        
        return True
    
    async def deregister(self, service_name: str, service_id: str) -> bool:
        """Deregister service instance"""
        if service_name in self.services and service_id in self.services[service_name]:
            service = self.services[service_name][service_id]
            service.status = ServiceStatus.STOPPING
            
            del self.services[service_name][service_id]
            
            if not self.services[service_name]:
                del self.services[service_name]
            
            print(f"Deregistered service: {service_name} ({service_id})")
            
            # Notify watchers
            await self._notify_watchers(service_name, "deregistered", service)
            
            return True
        
        return False
    
    async def discover(self, service_name: str, tags: Set[str] = None) -> List[ServiceInstance]:
        """Discover healthy service instances"""
        if service_name not in self.services:
            return []
        
        instances = []
        for instance in self.services[service_name].values():
            if instance.status == ServiceStatus.HEALTHY:
                # Filter by tags if specified
                if tags and not tags.issubset(instance.tags):
                    continue
                instances.append(instance)
        
        return instances
    
    async def heartbeat(self, service_name: str, service_id: str) -> bool:
        """Update service heartbeat"""
        if (service_name in self.services and 
            service_id in self.services[service_name]):
            
            service = self.services[service_name][service_id]
            service.last_heartbeat = time.time()
            
            if service.status == ServiceStatus.STARTING:
                service.status = ServiceStatus.HEALTHY
                await self._notify_watchers(service_name, "healthy", service)
            
            return True
        
        return False
    
    async def watch(self, service_name: str, callback: callable):
        """Watch for service changes"""
        if service_name not in self.watchers:
            self.watchers[service_name] = []
        
        self.watchers[service_name].append(callback)
    
    async def start_background_tasks(self):
        """Start background health checking and cleanup"""
        self.running = True
        
        asyncio.create_task(self._health_checker())
        asyncio.create_task(self._cleanup_stale_services())
    
    async def stop_background_tasks(self):
        """Stop background tasks"""
        self.running = False
    
    async def _health_checker(self):
        """Background health checker"""
        while self.running:
            for service_name, instances in self.services.items():
                for instance in instances.values():
                    if instance.health_check_url:
                        healthy = await self._check_service_health(instance)
                        
                        if not healthy and instance.status == ServiceStatus.HEALTHY:
                            instance.status = ServiceStatus.UNHEALTHY
                            await self._notify_watchers(service_name, "unhealthy", instance)
                        elif healthy and instance.status == ServiceStatus.UNHEALTHY:
                            instance.status = ServiceStatus.HEALTHY
                            await self._notify_watchers(service_name, "healthy", instance)
            
            await asyncio.sleep(self.health_check_interval)
    
    async def _cleanup_stale_services(self):
        """Clean up services that haven't sent heartbeats"""
        while self.running:
            current_time = time.time()
            stale_services = []
            
            for service_name, instances in self.services.items():
                for service_id, instance in instances.items():
                    if (current_time - instance.last_heartbeat > self.heartbeat_interval * 2):
                        stale_services.append((service_name, service_id))
            
            for service_name, service_id in stale_services:
                print(f"Removing stale service: {service_name} ({service_id})")
                await self.deregister(service_name, service_id)
            
            await asyncio.sleep(self.heartbeat_interval)
    
    async def _check_service_health(self, service: ServiceInstance) -> bool:
        """Check individual service health"""
        try:
            # Simulate health check HTTP call
            await asyncio.sleep(0.01)  # Simulate network delay
            
            # Simulate some services being unhealthy
            return random.random() > 0.1  # 90% healthy
            
        except Exception:
            return False
    
    async def _notify_watchers(self, service_name: str, event: str, service: ServiceInstance):
        """Notify watchers of service changes"""
        watchers = self.watchers.get(service_name, [])
        
        for watcher in watchers:
            try:
                await watcher(event, service)
            except Exception as e:
                print(f"Watcher notification failed: {e}")
    
    def get_service_stats(self) -> Dict[str, Dict]:
        """Get service registry statistics"""
        stats = {}
        
        for service_name, instances in self.services.items():
            healthy_count = sum(1 for i in instances.values() if i.status == ServiceStatus.HEALTHY)
            total_count = len(instances)
            
            stats[service_name] = {
                "total_instances": total_count,
                "healthy_instances": healthy_count,
                "unhealthy_instances": total_count - healthy_count,
                "instance_details": [
                    {
                        "id": i.id,
                        "host": i.host,
                        "port": i.port,
                        "status": i.status.value,
                        "last_heartbeat": i.last_heartbeat
                    }
                    for i in instances.values()
                ]
            }
        
        return stats

# Load Balancer with Service Discovery
class LoadBalancer:
    """Load balancer with multiple algorithms"""
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.round_robin_counters: Dict[str, int] = {}
        self.connection_counts: Dict[str, int] = {}
        self.response_times: Dict[str, List[float]] = {}
    
    async def get_instance(self, service_name: str, algorithm: str = "round_robin",
                          tags: Set[str] = None) -> Optional[ServiceInstance]:
        """Get service instance using specified load balancing algorithm"""
        instances = await self.service_registry.discover(service_name, tags)
        
        if not instances:
            return None
        
        if algorithm == "round_robin":
            return self._round_robin(service_name, instances)
        elif algorithm == "least_connections":
            return self._least_connections(instances)
        elif algorithm == "weighted_random":
            return self._weighted_random(instances)
        elif algorithm == "least_response_time":
            return self._least_response_time(instances)
        else:
            return random.choice(instances)
    
    def _round_robin(self, service_name: str, instances: List[ServiceInstance]) -> ServiceInstance:
        """Round-robin load balancing"""
        if service_name not in self.round_robin_counters:
            self.round_robin_counters[service_name] = 0
        
        index = self.round_robin_counters[service_name] % len(instances)
        self.round_robin_counters[service_name] += 1
        
        return instances[index]
    
    def _least_connections(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Least connections load balancing"""
        min_connections = float('inf')
        selected_instance = instances[0]
        
        for instance in instances:
            instance_key = f"{instance.host}:{instance.port}"
            connections = self.connection_counts.get(instance_key, 0)
            
            if connections < min_connections:
                min_connections = connections
                selected_instance = instance
        
        return selected_instance
    
    def _weighted_random(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Weighted random based on instance metadata"""
        weights = []
        
        for instance in instances:
            # Use weight from metadata, default to 1
            weight = int(instance.metadata.get("weight", "1"))
            weights.append(weight)
        
        # Weighted random selection
        total_weight = sum(weights)
        random_weight = random.uniform(0, total_weight)
        
        current_weight = 0
        for instance, weight in zip(instances, weights):
            current_weight += weight
            if random_weight <= current_weight:
                return instance
        
        return instances[-1]  # Fallback
    
    def _least_response_time(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """Least response time load balancing"""
        min_response_time = float('inf')
        selected_instance = instances[0]
        
        for instance in instances:
            instance_key = f"{instance.host}:{instance.port}"
            response_times = self.response_times.get(instance_key, [100])  # Default 100ms
            
            avg_response_time = sum(response_times[-10:]) / len(response_times[-10:])  # Last 10
            
            if avg_response_time < min_response_time:
                min_response_time = avg_response_time
                selected_instance = instance
        
        return selected_instance
    
    async def record_request_start(self, instance: ServiceInstance):
        """Record request start (for connection counting)"""
        instance_key = f"{instance.host}:{instance.port}"
        self.connection_counts[instance_key] = self.connection_counts.get(instance_key, 0) + 1
    
    async def record_request_end(self, instance: ServiceInstance, response_time: float):
        """Record request completion"""
        instance_key = f"{instance.host}:{instance.port}"
        
        # Update connection count
        self.connection_counts[instance_key] = max(0, self.connection_counts.get(instance_key, 1) - 1)
        
        # Update response times
        if instance_key not in self.response_times:
            self.response_times[instance_key] = []
        
        self.response_times[instance_key].append(response_time)
        
        # Keep only recent response times
        if len(self.response_times[instance_key]) > 50:
            self.response_times[instance_key] = self.response_times[instance_key][-50:]

# Service Discovery Client
class ServiceDiscoveryClient:
    """Client for service discovery and load balancing"""
    
    def __init__(self, registry: ServiceRegistry, load_balancer: LoadBalancer):
        self.registry = registry
        self.load_balancer = load_balancer
        self.local_cache: Dict[str, List[ServiceInstance]] = {}
        self.cache_ttl = 30  # seconds
        self.cache_timestamps: Dict[str, float] = {}
    
    async def call_service(self, service_name: str, path: str, method: str = "GET",
                          payload: Optional[Dict] = None, tags: Set[str] = None) -> Dict:
        """Make service call with automatic service discovery and load balancing"""
        
        # Get service instance
        instance = await self._get_cached_instance(service_name, tags)
        if not instance:
            raise Exception(f"No healthy instances found for service: {service_name}")
        
        # Record request start
        await self.load_balancer.record_request_start(instance)
        
        try:
            # Make actual service call
            start_time = time.time()
            result = await self._make_http_call(instance, path, method, payload)
            response_time = time.time() - start_time
            
            # Record request completion
            await self.load_balancer.record_request_end(instance, response_time)
            
            return result
            
        except Exception as e:
            # Record request completion with error
            await self.load_balancer.record_request_end(instance, 0)
            raise
    
    async def _get_cached_instance(self, service_name: str, tags: Set[str] = None) -> Optional[ServiceInstance]:
        """Get service instance with local caching"""
        cache_key = f"{service_name}:{','.join(sorted(tags or []))}"
        current_time = time.time()
        
        # Check cache validity
        if (cache_key in self.local_cache and 
            cache_key in self.cache_timestamps and
            current_time - self.cache_timestamps[cache_key] < self.cache_ttl):
            
            # Use cached instances
            cached_instances = self.local_cache[cache_key]
            if cached_instances:
                return random.choice(cached_instances)
        
        # Refresh cache
        instances = await self.registry.discover(service_name, tags)
        self.local_cache[cache_key] = instances
        self.cache_timestamps[cache_key] = current_time
        
        if not instances:
            return None
        
        # Use load balancer to select instance
        return await self.load_balancer.get_instance(service_name, "round_robin", tags)
    
    async def _make_http_call(self, instance: ServiceInstance, path: str, 
                            method: str, payload: Optional[Dict]) -> Dict:
        """Make HTTP call to service instance"""
        # Simulate HTTP call
        await asyncio.sleep(random.uniform(0.01, 0.1))  # Simulate network delay
        
        # Simulate occasional failures
        if random.random() < 0.05:  # 5% failure rate
            raise Exception("Service call failed")
        
        # Return mock response
        return {
            "status": "success",
            "instance": f"{instance.host}:{instance.port}",
            "method": method,
            "path": path,
            "payload": payload
        }

# Example Usage
async def service_discovery_example():
    """Demonstrate service discovery and load balancing"""
    
    # Setup service registry
    registry = ServiceRegistry(heartbeat_interval=10, health_check_interval=5)
    await registry.start_background_tasks()
    
    # Register multiple instances of the same service
    user_service_1 = ServiceInstance(
        id="user-service-1",
        name="user-service",
        host="10.0.1.10",
        port=8080,
        health_check_url="/health",
        tags={"version", "datacenter:us-east"},
        metadata={"weight": "3"}
    )
    
    user_service_2 = ServiceInstance(
        id="user-service-2", 
        name="user-service",
        host="10.0.1.11",
        port=8080,
        health_check_url="/health",
        tags={"version", "datacenter:us-east"},
        metadata={"weight": "2"}
    )
    
    payment_service = ServiceInstance(
        id="payment-service-1",
        name="payment-service",
        host="10.0.2.10",
        port=9090,
        health_check_url="/health",
        tags={"version", "datacenter:us-west"}
    )
    
    # Register services
    await registry.register(user_service_1)
    await registry.register(user_service_2)
    await registry.register(payment_service)
    
    # Setup load balancer
    load_balancer = LoadBalancer(registry)
    
    # Setup service discovery client
    client = ServiceDiscoveryClient(registry, load_balancer)
    
    # Watch for service changes
    async def service_watcher(event: str, service: ServiceInstance):
        print(f"Service {service.name} ({service.id}) is now {event}")
    
    await registry.watch("user-service", service_watcher)
    
    print("=== Service Discovery Demo ===")
    
    # Make service calls
    for i in range(5):
        try:
            result = await client.call_service(
                "user-service", 
                f"/users/{i}", 
                tags={"version"}
            )
            print(f"Call {i}: {result['instance']}")
        except Exception as e:
            print(f"Call {i} failed: {e}")
    
    # Send heartbeats
    await registry.heartbeat("user-service", "user-service-1")
    await registry.heartbeat("user-service", "user-service-2")
    await registry.heartbeat("payment-service", "payment-service-1")
    
    # Check service stats
    print("\nService Registry Stats:")
    stats = registry.get_service_stats()
    for service_name, service_stats in stats.items():
        print(f"  {service_name}: {service_stats['healthy_instances']}/{service_stats['total_instances']} healthy")
    
    # Simulate service going down
    await registry.deregister("user-service", "user-service-1")
    
    # Make more calls to see load balancing adjust
    print("\nAfter service deregistration:")
    for i in range(3):
        try:
            result = await client.call_service("user-service", f"/users/{i}")
            print(f"Call {i}: {result['instance']}")
        except Exception as e:
            print(f"Call {i} failed: {e}")
    
    await registry.stop_background_tasks()
```

---

## Labs and Projects

### Lab 1: API Design Comparison
Build the same API using REST, GraphQL, and gRPC, comparing performance, developer experience, and use cases.

### Lab 2: Message Queue Implementation
Implement a robust message queue with priorities, dead letter queues, and reliability features.

### Lab 3: Service Discovery System
Build a complete service discovery system with health checking, load balancing, and failure detection.

### Lab 4: Communication Patterns Analysis
Analyze different communication patterns for a microservices system, measuring latency, throughput, and reliability.

## Assessment

### Communication Architecture Project
Design and implement a comprehensive communication strategy for a distributed e-commerce platform:

1. **API Design**: RESTful APIs with proper versioning and documentation
2. **Event-Driven Communication**: Asynchronous messaging for order processing
3. **Service Discovery**: Dynamic service registration and discovery
4. **Load Balancing**: Multiple load balancing algorithms with health checking
5. **Performance Analysis**: Measure and optimize communication performance

## References

### Essential Reading
- "Building Microservices" by Sam Newman (Chapters 4-6)
- "Microservices Patterns" by Chris Richardson (Communication chapters)
- "REST in Practice" by Webber, Parastatidis, and Robinson

### Specifications and Standards
- [OpenAPI Specification](https://swagger.io/specification/)
- [GraphQL Specification](https://spec.graphql.org/)
- [gRPC Documentation](https://grpc.io/docs/)
- [CloudEvents Specification](https://cloudevents.io/)

### Tools and Frameworks
- **REST**: FastAPI, Express.js, Spring Boot
- **GraphQL**: Apollo Server, Hasura, PostGraphile
- **gRPC**: Protocol Buffers, gRPC implementations
- **Messaging**: Apache Kafka, RabbitMQ, Redis Streams

---

*Next: [Module 05 - Reliability & Resilience](../05_RELIABILITY_RESILIENCE/)*