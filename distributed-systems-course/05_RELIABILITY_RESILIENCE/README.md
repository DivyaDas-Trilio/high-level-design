# Module 05: Reliability & Resilience
*Building fault-tolerant distributed systems*

## Learning Objectives

By the end of this module, you will:
- Implement comprehensive failure handling patterns (circuit breakers, bulkheads, timeouts)
- Design systems for graceful degradation and fault isolation
- Apply chaos engineering principles to validate system resilience
- Build retry mechanisms with proper backoff strategies
- Design for different types of failures and their blast radius

## Topics Covered

1. **Failure Models & Fault Tolerance** - Understanding what can go wrong
2. **Circuit Breaker Pattern** - Preventing cascade failures
3. **Bulkhead Pattern** - Fault isolation strategies
4. **Retry & Backoff** - Smart retry mechanisms
5. **Graceful Degradation** - Maintaining service during failures
6. **Chaos Engineering** - Proactive resilience testing

---

## 1. Failure Models & Fault Tolerance

### Types of Failures in Distributed Systems

```python
from abc import ABC, abstractmethod
from enum import Enum
import asyncio
import random
import time
from typing import List, Dict, Any, Optional

class FailureType(Enum):
    CRASH = "crash"                    # Node stops responding
    OMISSION = "omission"              # Messages are lost
    TIMING = "timing"                  # Operations take too long
    RESPONSE = "response"              # Incorrect responses
    ARBITRARY = "arbitrary"            # Byzantine failures
    PARTITION = "partition"            # Network splits

class FailureDetector:
    """Detects various types of failures"""
    
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self.node_status: Dict[str, Dict] = {}
        self.last_heartbeat: Dict[str, float] = {}
    
    async def monitor_node(self, node_id: str, health_check_func):
        """Monitor node health with timeout detection"""
        while True:
            try:
                start_time = time.time()
                
                # Perform health check
                health_result = await asyncio.wait_for(
                    health_check_func(), 
                    timeout=self.timeout
                )
                
                response_time = time.time() - start_time
                
                # Update node status
                self.node_status[node_id] = {
                    "status": "healthy",
                    "last_check": time.time(),
                    "response_time": response_time,
                    "consecutive_failures": 0
                }
                
                self.last_heartbeat[node_id] = time.time()
                
            except asyncio.TimeoutError:
                self._handle_timeout_failure(node_id)
            except ConnectionError:
                self._handle_connection_failure(node_id)
            except Exception as e:
                self._handle_unknown_failure(node_id, e)
            
            await asyncio.sleep(10)  # Check every 10 seconds
    
    def _handle_timeout_failure(self, node_id: str):
        """Handle timeout failures (slow responses)"""
        status = self.node_status.get(node_id, {})
        status.update({
            "status": "slow",
            "failure_type": FailureType.TIMING,
            "consecutive_failures": status.get("consecutive_failures", 0) + 1,
            "last_failure": time.time()
        })
        self.node_status[node_id] = status
    
    def _handle_connection_failure(self, node_id: str):
        """Handle connection failures (crash/omission)"""
        status = self.node_status.get(node_id, {})
        status.update({
            "status": "unreachable",
            "failure_type": FailureType.CRASH,
            "consecutive_failures": status.get("consecutive_failures", 0) + 1,
            "last_failure": time.time()
        })
        self.node_status[node_id] = status
    
    def is_node_healthy(self, node_id: str) -> bool:
        """Check if node is considered healthy"""
        if node_id not in self.node_status:
            return False
        
        status = self.node_status[node_id]
        
        # Node is unhealthy if:
        # 1. Too many consecutive failures
        # 2. No heartbeat for too long
        # 3. Consistently slow responses
        
        if status.get("consecutive_failures", 0) > 3:
            return False
        
        last_heartbeat = self.last_heartbeat.get(node_id, 0)
        if time.time() - last_heartbeat > self.timeout * 2:
            return False
        
        return status.get("status") == "healthy"

# Fault-Tolerant Service Client
class FaultTolerantServiceClient:
    """Service client with comprehensive fault handling"""
    
    def __init__(self, service_name: str, endpoints: List[str]):
        self.service_name = service_name
        self.endpoints = endpoints
        self.failure_detector = FailureDetector()
        self.circuit_breaker = CircuitBreaker(service_name)
        self.bulkhead = Bulkhead(max_concurrent=50)
        
        # Start monitoring endpoints
        for i, endpoint in enumerate(endpoints):
            asyncio.create_task(
                self.failure_detector.monitor_node(
                    f"{service_name}-{i}",
                    lambda: self._health_check(endpoint)
                )
            )
    
    async def call(self, method: str, path: str, **kwargs) -> Any:
        """Make fault-tolerant service call"""
        
        # 1. Check circuit breaker
        if self.circuit_breaker.state == "OPEN":
            raise ServiceUnavailableError(f"Circuit breaker open for {self.service_name}")
        
        # 2. Acquire bulkhead permit
        async with self.bulkhead.acquire():
            # 3. Select healthy endpoint
            endpoint = self._select_healthy_endpoint()
            if not endpoint:
                raise ServiceUnavailableError(f"No healthy endpoints for {self.service_name}")
            
            # 4. Make call with retry logic
            return await self._call_with_retry(endpoint, method, path, **kwargs)
    
    def _select_healthy_endpoint(self) -> Optional[str]:
        """Select a healthy endpoint using round-robin among healthy nodes"""
        healthy_endpoints = []
        
        for i, endpoint in enumerate(endpoints):
            node_id = f"{self.service_name}-{i}"
            if self.failure_detector.is_node_healthy(node_id):
                healthy_endpoints.append(endpoint)
        
        if not healthy_endpoints:
            # Fallback: try any endpoint if none marked healthy
            return random.choice(self.endpoints) if self.endpoints else None
        
        return random.choice(healthy_endpoints)
    
    async def _call_with_retry(self, endpoint: str, method: str, path: str, **kwargs):
        """Make call with exponential backoff retry"""
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries + 1):
            try:
                # Use timeout to detect slow responses
                async with aiohttp.ClientSession() as session:
                    async with session.request(
                        method, f"{endpoint}{path}", 
                        timeout=aiohttp.ClientTimeout(total=10),
                        **kwargs
                    ) as response:
                        
                        if response.status >= 500:
                            # Server error - retry
                            raise ServerError(f"Server error: {response.status}")
                        elif response.status >= 400:
                            # Client error - don't retry
                            raise ClientError(f"Client error: {response.status}")
                        
                        self.circuit_breaker.record_success()
                        return await response.json()
                        
            except (ServerError, asyncio.TimeoutError, aiohttp.ClientError) as e:
                self.circuit_breaker.record_failure()
                
                if attempt == max_retries:
                    # Final attempt failed
                    raise ServiceCallError(f"Service call failed after {max_retries} retries: {e}")
                
                # Exponential backoff with jitter
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(delay)
            
            except ClientError:
                # Don't retry client errors
                raise
    
    async def _health_check(self, endpoint: str) -> Dict:
        """Perform health check on endpoint"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{endpoint}/health", timeout=5) as response:
                return await response.json()
```

---

## 2. Circuit Breaker Pattern

### Advanced Circuit Breaker Implementation

```python
import asyncio
import time
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Callable, Any

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open" # Testing recovery

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5          # Failures before opening
    timeout: float = 60.0               # Time before trying half-open
    success_threshold: int = 3          # Successes to close from half-open
    volume_threshold: int = 10          # Minimum requests before evaluation
    error_percentage: float = 50.0      # Error percentage threshold

class CircuitBreakerMetrics:
    """Tracks circuit breaker metrics"""
    
    def __init__(self, window_size: int = 60):
        self.window_size = window_size
        self.requests: List[float] = []
        self.failures: List[float] = []
        self.successes: List[float] = []
    
    def record_request(self, timestamp: float):
        self._cleanup_old_entries(timestamp)
        self.requests.append(timestamp)
    
    def record_success(self, timestamp: float):
        self._cleanup_old_entries(timestamp)
        self.successes.append(timestamp)
    
    def record_failure(self, timestamp: float):
        self._cleanup_old_entries(timestamp)
        self.failures.append(timestamp)
    
    def _cleanup_old_entries(self, current_time: float):
        cutoff = current_time - self.window_size
        self.requests = [t for t in self.requests if t > cutoff]
        self.failures = [t for t in self.failures if t > cutoff]
        self.successes = [t for t in self.successes if t > cutoff]
    
    @property
    def total_requests(self) -> int:
        return len(self.requests)
    
    @property
    def total_failures(self) -> int:
        return len(self.failures)
    
    @property
    def failure_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.total_failures / self.total_requests) * 100

class AdvancedCircuitBreaker:
    """Production-ready circuit breaker with comprehensive features"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.metrics = CircuitBreakerMetrics()
        
        # State tracking
        self.last_failure_time = 0.0
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        
        # Callbacks
        self.state_change_listeners: List[Callable] = []
    
    def add_state_change_listener(self, callback: Callable):
        """Add callback for state changes"""
        self.state_change_listeners.append(callback)
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker"""
        now = time.time()
        self.metrics.record_request(now)
        
        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time >= self.config.timeout:
                self._transition_to_half_open()
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._record_success(now)
            return result
            
        except Exception as e:
            self._record_failure(now)
            raise
    
    def _record_success(self, timestamp: float):
        """Record successful call"""
        self.metrics.record_success(timestamp)
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        
        if self.state == CircuitState.HALF_OPEN:
            if self.consecutive_successes >= self.config.success_threshold:
                self._transition_to_closed()
    
    def _record_failure(self, timestamp: float):
        """Record failed call"""
        self.metrics.record_failure(timestamp)
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = timestamp
        
        if self.state == CircuitState.CLOSED:
            self._evaluate_threshold()
        elif self.state == CircuitState.HALF_OPEN:
            self._transition_to_open()
    
    def _evaluate_threshold(self):
        """Evaluate if circuit should open"""
        # Check volume threshold
        if self.metrics.total_requests < self.config.volume_threshold:
            return
        
        # Check failure conditions
        should_open = (
            self.consecutive_failures >= self.config.failure_threshold or
            self.metrics.failure_rate >= self.config.error_percentage
        )
        
        if should_open:
            self._transition_to_open()
    
    def _transition_to_open(self):
        """Transition to OPEN state"""
        old_state = self.state
        self.state = CircuitState.OPEN
        self.last_failure_time = time.time()
        self._notify_state_change(old_state, self.state)
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state"""
        old_state = self.state
        self.state = CircuitState.HALF_OPEN
        self.consecutive_successes = 0
        self._notify_state_change(old_state, self.state)
    
    def _transition_to_closed(self):
        """Transition to CLOSED state"""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self._notify_state_change(old_state, self.state)
    
    def _notify_state_change(self, old_state: CircuitState, new_state: CircuitState):
        """Notify listeners of state change"""
        for listener in self.state_change_listeners:
            try:
                listener(self.name, old_state, new_state)
            except Exception as e:
                # Don't let listener errors affect circuit breaker
                logging.error(f"Circuit breaker state change listener failed: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current circuit breaker metrics"""
        return {
            "name": self.name,
            "state": self.state.value,
            "total_requests": self.metrics.total_requests,
            "total_failures": self.metrics.total_failures,
            "failure_rate": self.metrics.failure_rate,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes
        }

# Circuit Breaker Factory
class CircuitBreakerFactory:
    """Factory for managing circuit breakers"""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, AdvancedCircuitBreaker] = {}
        self.default_config = CircuitBreakerConfig()
    
    def get_circuit_breaker(self, name: str, config: CircuitBreakerConfig = None) -> AdvancedCircuitBreaker:
        """Get or create circuit breaker"""
        if name not in self.circuit_breakers:
            cb_config = config or self.default_config
            cb = AdvancedCircuitBreaker(name, cb_config)
            
            # Add monitoring
            cb.add_state_change_listener(self._log_state_change)
            
            self.circuit_breakers[name] = cb
        
        return self.circuit_breakers[name]
    
    def _log_state_change(self, name: str, old_state: CircuitState, new_state: CircuitState):
        """Log circuit breaker state changes"""
        logging.warning(f"Circuit breaker {name} changed from {old_state.value} to {new_state.value}")
    
    def get_all_metrics(self) -> List[Dict[str, Any]]:
        """Get metrics for all circuit breakers"""
        return [cb.get_metrics() for cb in self.circuit_breakers.values()]

# Usage Example with Service Client
class ResilientServiceClient:
    """Service client with circuit breaker protection"""
    
    def __init__(self, service_name: str, base_url: str):
        self.service_name = service_name
        self.base_url = base_url
        self.circuit_breaker_factory = CircuitBreakerFactory()
    
    async def get(self, path: str, **kwargs) -> Dict:
        """GET request with circuit breaker"""
        cb = self.circuit_breaker_factory.get_circuit_breaker(
            f"{self.service_name}_get",
            CircuitBreakerConfig(failure_threshold=3, timeout=30)
        )
        
        return await cb.call(self._make_get_request, path, **kwargs)
    
    async def post(self, path: str, **kwargs) -> Dict:
        """POST request with circuit breaker"""
        cb = self.circuit_breaker_factory.get_circuit_breaker(
            f"{self.service_name}_post",
            CircuitBreakerConfig(failure_threshold=5, timeout=60)
        )
        
        return await cb.call(self._make_post_request, path, **kwargs)
    
    async def _make_get_request(self, path: str, **kwargs) -> Dict:
        """Actual GET request implementation"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}{path}", **kwargs) as response:
                if response.status >= 400:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status
                    )
                return await response.json()
    
    async def _make_post_request(self, path: str, **kwargs) -> Dict:
        """Actual POST request implementation"""
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}{path}", **kwargs) as response:
                if response.status >= 400:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status
                    )
                return await response.json()
```

---

## 3. Bulkhead Pattern

### Resource Isolation Implementation

```python
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass
import time

@dataclass
class BulkheadConfig:
    max_concurrent_requests: int = 10
    max_wait_time: float = 30.0
    queue_size: int = 100

class Bulkhead:
    """Implements bulkhead pattern for resource isolation"""
    
    def __init__(self, name: str, config: BulkheadConfig):
        self.name = name
        self.config = config
        self.semaphore = asyncio.Semaphore(config.max_concurrent_requests)
        self.queue = asyncio.Queue(maxsize=config.queue_size)
        self.active_requests = 0
        self.total_requests = 0
        self.rejected_requests = 0
        self.timeout_requests = 0
    
    async def execute(self, func, *args, **kwargs):
        """Execute function within bulkhead constraints"""
        self.total_requests += 1
        
        try:
            # Try to acquire permit with timeout
            await asyncio.wait_for(
                self.semaphore.acquire(), 
                timeout=self.config.max_wait_time
            )
            
            self.active_requests += 1
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                self.active_requests -= 1
                self.semaphore.release()
                
        except asyncio.TimeoutError:
            self.timeout_requests += 1
            self.rejected_requests += 1
            raise BulkheadTimeoutError(f"Bulkhead {self.name} timeout")
        except:
            self.rejected_requests += 1
            raise
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get bulkhead metrics"""
        return {
            "name": self.name,
            "active_requests": self.active_requests,
            "total_requests": self.total_requests,
            "rejected_requests": self.rejected_requests,
            "timeout_requests": self.timeout_requests,
            "utilization": self.active_requests / self.config.max_concurrent_requests
        }

# Thread Pool Bulkhead (for CPU-intensive tasks)
import concurrent.futures
from threading import Semaphore

class ThreadPoolBulkhead:
    """Bulkhead using thread pool for CPU-bound tasks"""
    
    def __init__(self, name: str, max_workers: int = 5):
        self.name = name
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.semaphore = Semaphore(max_workers)
        self.active_tasks = 0
        self.total_tasks = 0
    
    async def execute(self, func, *args, **kwargs):
        """Execute CPU-intensive function in thread pool"""
        if not self.semaphore.acquire(blocking=False):
            raise BulkheadExhaustionError(f"Thread pool {self.name} exhausted")
        
        self.active_tasks += 1
        self.total_tasks += 1
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(self.executor, func, *args, **kwargs)
            return result
        finally:
            self.active_tasks -= 1
            self.semaphore.release()

# Service-Level Bulkheads
class ServiceBulkheads:
    """Manages bulkheads for different service types"""
    
    def __init__(self):
        self.bulkheads: Dict[str, Bulkhead] = {}
        
        # Configure bulkheads for different service types
        self._setup_default_bulkheads()
    
    def _setup_default_bulkheads(self):
        """Setup default bulkheads for common service types"""
        
        # Critical services - more resources
        self.bulkheads["user_service"] = Bulkhead(
            "user_service",
            BulkheadConfig(max_concurrent_requests=20, max_wait_time=10)
        )
        
        self.bulkheads["payment_service"] = Bulkhead(
            "payment_service", 
            BulkheadConfig(max_concurrent_requests=15, max_wait_time=30)
        )
        
        # Less critical services - fewer resources
        self.bulkheads["recommendation_service"] = Bulkhead(
            "recommendation_service",
            BulkheadConfig(max_concurrent_requests=5, max_wait_time=5)
        )
        
        self.bulkheads["analytics_service"] = Bulkhead(
            "analytics_service",
            BulkheadConfig(max_concurrent_requests=3, max_wait_time=2)
        )
    
    async def execute(self, service_name: str, func, *args, **kwargs):
        """Execute function using appropriate bulkhead"""
        if service_name not in self.bulkheads:
            # Default bulkhead for unknown services
            self.bulkheads[service_name] = Bulkhead(
                service_name,
                BulkheadConfig(max_concurrent_requests=5, max_wait_time=10)
            )
        
        bulkhead = self.bulkheads[service_name]
        return await bulkhead.execute(func, *args, **kwargs)
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all bulkheads"""
        return {name: bulkhead.get_metrics() for name, bulkhead in self.bulkheads.items()}

# Application with Bulkheads
class OrderService:
    """Order service with bulkhead isolation"""
    
    def __init__(self):
        self.bulkheads = ServiceBulkheads()
        self.user_client = ServiceClient("user_service")
        self.payment_client = ServiceClient("payment_service")
        self.inventory_client = ServiceClient("inventory_service")
        self.notification_client = ServiceClient("notification_service")
    
    async def create_order(self, order_data: Dict) -> Dict:
        """Create order with bulkhead protection"""
        try:
            # User validation - critical, gets priority resources
            user = await self.bulkheads.execute(
                "user_service",
                self.user_client.get_user,
                order_data["user_id"]
            )
            
            # Inventory check - critical for order fulfillment
            inventory = await self.bulkheads.execute(
                "inventory_service", 
                self.inventory_client.check_availability,
                order_data["items"]
            )
            
            # Payment processing - critical, gets dedicated resources
            payment_result = await self.bulkheads.execute(
                "payment_service",
                self.payment_client.process_payment,
                order_data["payment_info"]
            )
            
            # Create order record
            order = self._create_order_record(order_data, user, payment_result)
            
            # Send notification - non-critical, limited resources
            # If this fails, order still succeeds
            try:
                await self.bulkheads.execute(
                    "notification_service",
                    self.notification_client.send_order_confirmation,
                    order["order_id"]
                )
            except BulkheadTimeoutError:
                # Log but don't fail the order
                logging.warning(f"Failed to send notification for order {order['order_id']}")
            
            return order
            
        except BulkheadTimeoutError as e:
            # Specific handling for bulkhead exhaustion
            raise ServiceOverloadedError(f"Service temporarily overloaded: {e}")

# Database Connection Bulkheads
class DatabaseBulkhead:
    """Bulkhead for database connections"""
    
    def __init__(self, pool_size: int = 20):
        self.read_pool = Bulkhead(
            "db_read", 
            BulkheadConfig(max_concurrent_requests=pool_size // 2)
        )
        self.write_pool = Bulkhead(
            "db_write",
            BulkheadConfig(max_concurrent_requests=pool_size // 4)
        )
        self.analytics_pool = Bulkhead(
            "db_analytics", 
            BulkheadConfig(max_concurrent_requests=pool_size // 4, max_wait_time=60)
        )
    
    async def execute_read(self, query_func, *args, **kwargs):
        """Execute read query through read pool"""
        return await self.read_pool.execute(query_func, *args, **kwargs)
    
    async def execute_write(self, query_func, *args, **kwargs):
        """Execute write query through write pool"""  
        return await self.write_pool.execute(query_func, *args, **kwargs)
    
    async def execute_analytics(self, query_func, *args, **kwargs):
        """Execute analytics query through analytics pool"""
        return await self.analytics_pool.execute(query_func, *args, **kwargs)
```

---

## 4. Retry & Backoff Strategies

### Intelligent Retry Implementation

```python
import random
import math
import asyncio
from typing import List, Type, Callable, Any
from dataclasses import dataclass

@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter_range: float = 0.1
    retryable_exceptions: List[Type[Exception]] = None

class RetryStrategy:
    """Base class for retry strategies"""
    
    def get_delay(self, attempt: int, base_delay: float) -> float:
        raise NotImplementedError

class ExponentialBackoffStrategy(RetryStrategy):
    """Exponential backoff with jitter"""
    
    def __init__(self, multiplier: float = 2.0, max_delay: float = 60.0, jitter_range: float = 0.1):
        self.multiplier = multiplier
        self.max_delay = max_delay
        self.jitter_range = jitter_range
    
    def get_delay(self, attempt: int, base_delay: float) -> float:
        # Exponential backoff
        delay = base_delay * (self.multiplier ** (attempt - 1))
        delay = min(delay, self.max_delay)
        
        # Add jitter to prevent thundering herd
        jitter = delay * self.jitter_range * random.uniform(-1, 1)
        return max(0, delay + jitter)

class LinearBackoffStrategy(RetryStrategy):
    """Linear backoff strategy"""
    
    def __init__(self, increment: float = 1.0, max_delay: float = 60.0):
        self.increment = increment
        self.max_delay = max_delay
    
    def get_delay(self, attempt: int, base_delay: float) -> float:
        delay = base_delay + (self.increment * (attempt - 1))
        return min(delay, self.max_delay)

class FixedDelayStrategy(RetryStrategy):
    """Fixed delay between retries"""
    
    def get_delay(self, attempt: int, base_delay: float) -> float:
        return base_delay

# Advanced Retry Decorator
def retry_with_strategy(config: RetryConfig, strategy: RetryStrategy = None):
    """Decorator for adding retry logic to functions"""
    
    if strategy is None:
        strategy = ExponentialBackoffStrategy()
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            retryable_exceptions = config.retryable_exceptions or [Exception]
            last_exception = None
            
            for attempt in range(1, config.max_attempts + 1):
                try:
                    result = await func(*args, **kwargs)
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    # Check if exception is retryable
                    if not any(isinstance(e, exc_type) for exc_type in retryable_exceptions):
                        raise  # Don't retry non-retryable exceptions
                    
                    if attempt == config.max_attempts:
                        # Final attempt failed
                        raise
                    
                    # Calculate delay and wait
                    delay = strategy.get_delay(attempt, config.base_delay)
                    await asyncio.sleep(delay)
            
            # This shouldn't be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator

# Conditional Retry Logic
class ConditionalRetry:
    """Retry with conditions based on exception type and context"""
    
    def __init__(self):
        self.retry_conditions: Dict[Type[Exception], Callable] = {}
        self.global_strategy = ExponentialBackoffStrategy()
        self.strategy_per_exception: Dict[Type[Exception], RetryStrategy] = {}
    
    def add_retry_condition(self, exception_type: Type[Exception], 
                          condition_func: Callable, strategy: RetryStrategy = None):
        """Add retry condition for specific exception type"""
        self.retry_conditions[exception_type] = condition_func
        if strategy:
            self.strategy_per_exception[exception_type] = strategy
    
    async def execute(self, func, max_attempts: int = 3, base_delay: float = 1.0):
        """Execute function with conditional retry logic"""
        last_exception = None
        
        for attempt in range(1, max_attempts + 1):
            try:
                result = await func()
                return result
                
            except Exception as e:
                last_exception = e
                exception_type = type(e)
                
                # Check if we should retry this exception
                should_retry = False
                strategy = self.global_strategy
                
                for exc_type, condition in self.retry_conditions.items():
                    if isinstance(e, exc_type):
                        should_retry = condition(e, attempt)
                        strategy = self.strategy_per_exception.get(exc_type, self.global_strategy)
                        break
                
                if not should_retry or attempt == max_attempts:
                    raise
                
                # Wait before retry
                delay = strategy.get_delay(attempt, base_delay)
                await asyncio.sleep(delay)
        
        raise last_exception

# Service Client with Smart Retries
class SmartRetryServiceClient:
    """Service client with intelligent retry logic"""
    
    def __init__(self, service_name: str, base_url: str):
        self.service_name = service_name
        self.base_url = base_url
        self.conditional_retry = ConditionalRetry()
        self._setup_retry_conditions()
    
    def _setup_retry_conditions(self):
        """Configure retry conditions for different exception types"""
        
        # Network errors - always retry
        self.conditional_retry.add_retry_condition(
            aiohttp.ClientConnectionError,
            lambda e, attempt: True,
            ExponentialBackoffStrategy(max_delay=30)
        )
        
        # Timeout errors - retry with longer delays
        self.conditional_retry.add_retry_condition(
            asyncio.TimeoutError,
            lambda e, attempt: attempt <= 2,
            ExponentialBackoffStrategy(multiplier=3, max_delay=60)
        )
        
        # Server errors (5xx) - retry with backoff
        self.conditional_retry.add_retry_condition(
            aiohttp.ClientResponseError,
            lambda e, attempt: e.status >= 500 and attempt <= 3,
            ExponentialBackoffStrategy()
        )
        
        # Rate limiting (429) - retry with longer delays
        self.conditional_retry.add_retry_condition(
            aiohttp.ClientResponseError,
            lambda e, attempt: e.status == 429 and attempt <= 5,
            LinearBackoffStrategy(increment=2, max_delay=120)
        )
    
    async def call(self, method: str, path: str, **kwargs) -> Any:
        """Make service call with smart retry logic"""
        
        async def make_request():
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method, f"{self.base_url}{path}",
                    timeout=aiohttp.ClientTimeout(total=30),
                    **kwargs
                ) as response:
                    if response.status >= 400:
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status
                        )
                    return await response.json()
        
        return await self.conditional_retry.execute(make_request, max_attempts=5)

# Retry Budget Pattern
class RetryBudget:
    """Implements retry budget to prevent retry storms"""
    
    def __init__(self, initial_budget: int = 100, refill_rate: float = 10.0):
        self.initial_budget = initial_budget
        self.current_budget = initial_budget
        self.refill_rate = refill_rate  # tokens per second
        self.last_refill = time.time()
        self.lock = asyncio.Lock()
    
    async def can_retry(self, cost: int = 1) -> bool:
        """Check if retry is allowed based on budget"""
        async with self.lock:
            await self._refill_budget()
            
            if self.current_budget >= cost:
                self.current_budget -= cost
                return True
            return False
    
    async def _refill_budget(self):
        """Refill retry budget based on time passed"""
        now = time.time()
        time_passed = now - self.last_refill
        refill_amount = time_passed * self.refill_rate
        
        self.current_budget = min(
            self.initial_budget,
            self.current_budget + refill_amount
        )
        self.last_refill = now
    
    def get_budget_info(self) -> Dict[str, float]:
        """Get current budget information"""
        return {
            "current_budget": self.current_budget,
            "initial_budget": self.initial_budget,
            "utilization": (self.initial_budget - self.current_budget) / self.initial_budget
        }

# Example Usage in Service
class OrderServiceWithRetries:
    """Order service with comprehensive retry strategies"""
    
    def __init__(self):
        self.payment_client = SmartRetryServiceClient("payment", "http://payment-service")
        self.inventory_client = SmartRetryServiceClient("inventory", "http://inventory-service") 
        self.retry_budget = RetryBudget(initial_budget=50, refill_rate=5)
    
    @retry_with_strategy(
        RetryConfig(
            max_attempts=3,
            base_delay=0.5,
            retryable_exceptions=[aiohttp.ClientError, asyncio.TimeoutError]
        ),
        ExponentialBackoffStrategy(max_delay=10)
    )
    async def process_payment(self, payment_data: Dict) -> Dict:
        """Process payment with retry logic"""
        if not await self.retry_budget.can_retry():
            raise ServiceOverloadedError("Retry budget exhausted")
        
        return await self.payment_client.call("POST", "/charge", json=payment_data)
    
    async def place_order(self, order_data: Dict) -> Dict:
        """Place order with coordinated retries"""
        try:
            # Reserve inventory (fast operation, fewer retries)
            inventory_reservation = await self.inventory_client.call(
                "POST", "/reserve", json=order_data["items"]
            )
            
            # Process payment (more complex, more retries allowed)
            payment_result = await self.process_payment(order_data["payment"])
            
            # Confirm order
            return await self._create_order(order_data, inventory_reservation, payment_result)
            
        except Exception as e:
            # Compensate on failure
            if 'inventory_reservation' in locals():
                await self._release_inventory(inventory_reservation["reservation_id"])
            raise
```

---

## 5. Graceful Degradation

### Graceful Degradation Patterns

```python
from typing import Any, Dict, Optional, Callable, List
import asyncio
from enum import Enum

class ServiceLevel(Enum):
    FULL = "full"
    DEGRADED = "degraded"  
    MINIMAL = "minimal"
    UNAVAILABLE = "unavailable"

class FeatureFlag:
    """Feature flag for graceful degradation"""
    
    def __init__(self, name: str, default_enabled: bool = True):
        self.name = name
        self.enabled = default_enabled
        self.degradation_level = ServiceLevel.FULL
        
    def is_enabled(self, service_level: ServiceLevel = ServiceLevel.FULL) -> bool:
        """Check if feature is enabled at given service level"""
        if not self.enabled:
            return False
            
        level_hierarchy = {
            ServiceLevel.FULL: 4,
            ServiceLevel.DEGRADED: 3,
            ServiceLevel.MINIMAL: 2,
            ServiceLevel.UNAVAILABLE: 1
        }
        
        return level_hierarchy[service_level] >= level_hierarchy[self.degradation_level]

class ServiceHealthMonitor:
    """Monitors service health and adjusts service levels"""
    
    def __init__(self):
        self.service_levels: Dict[str, ServiceLevel] = {}
        self.health_scores: Dict[str, float] = {}
        self.feature_flags: Dict[str, FeatureFlag] = {}
        
    def set_service_level(self, service_name: str, level: ServiceLevel):
        """Set service level for a service"""
        self.service_levels[service_name] = level
        self._adjust_feature_flags(service_name, level)
        
    def _adjust_feature_flags(self, service_name: str, level: ServiceLevel):
        """Adjust feature flags based on service level"""
        degradation_map = {
            ServiceLevel.FULL: [],
            ServiceLevel.DEGRADED: ["recommendations", "analytics"],
            ServiceLevel.MINIMAL: ["recommendations", "analytics", "notifications", "search"],
            ServiceLevel.UNAVAILABLE: ["recommendations", "analytics", "notifications", "search", "reviews"]
        }
        
        features_to_disable = degradation_map.get(level, [])
        
        for feature_name in features_to_disable:
            if feature_name in self.feature_flags:
                self.feature_flags[feature_name].enabled = False
                
    def get_service_level(self, service_name: str) -> ServiceLevel:
        """Get current service level"""
        return self.service_levels.get(service_name, ServiceLevel.FULL)
        
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if feature is currently enabled"""
        flag = self.feature_flags.get(feature_name)
        if not flag:
            return True  # Default to enabled if no flag exists
        return flag.is_enabled()

class DegradationStrategies:
    """Collection of degradation strategies"""
    
    @staticmethod
    async def fallback_to_cache(primary_func: Callable, cache_func: Callable, 
                               cache_ttl: int = 300) -> Any:
        """Fallback to cached data if primary source fails"""
        try:
            return await primary_func()
        except Exception:
            cached_result = await cache_func()
            if cached_result:
                return cached_result
            raise ServiceUnavailableError("Primary and cache both unavailable")
    
    @staticmethod
    async def fallback_to_static_data(primary_func: Callable, 
                                    static_data: Any) -> Any:
        """Fallback to static/default data"""
        try:
            return await primary_func()
        except Exception:
            return static_data
    
    @staticmethod
    async def skip_non_essential(essential_func: Callable, 
                               non_essential_funcs: List[Callable],
                               service_monitor: ServiceHealthMonitor) -> Any:
        """Skip non-essential operations during degradation"""
        # Always execute essential function
        result = await essential_func()
        
        # Execute non-essential functions only if service level allows
        if service_monitor.get_service_level("current") == ServiceLevel.FULL:
            for func in non_essential_funcs:
                try:
                    await func()
                except Exception as e:
                    # Log but don't fail the request
                    logging.warning(f"Non-essential operation failed: {e}")
        
        return result

class ProductService:
    """Product service with graceful degradation"""
    
    def __init__(self):
        self.health_monitor = ServiceHealthMonitor()
        self.cache = RedisCache()
        self.database = Database()
        self.recommendation_service = RecommendationServiceClient()
        self.review_service = ReviewServiceClient()
        
        # Setup feature flags
        self.health_monitor.feature_flags["recommendations"] = FeatureFlag("recommendations")
        self.health_monitor.feature_flags["reviews"] = FeatureFlag("reviews")
        self.health_monitor.feature_flags["analytics"] = FeatureFlag("analytics")
    
    async def get_product_details(self, product_id: str) -> Dict[str, Any]:
        """Get product details with graceful degradation"""
        
        # Core product info - always required
        async def get_core_product():
            return await self.database.get_product(product_id)
        
        # Use fallback to cache for core product data
        product = await DegradationStrategies.fallback_to_cache(
            get_core_product,
            lambda: self.cache.get(f"product:{product_id}"),
            cache_ttl=3600
        )
        
        result = {"product": product}
        
        # Add non-essential data based on service level
        non_essential_operations = []
        
        if self.health_monitor.is_feature_enabled("recommendations"):
            non_essential_operations.append(
                self._add_recommendations(result, product_id)
            )
        
        if self.health_monitor.is_feature_enabled("reviews"):
            non_essential_operations.append(
                self._add_reviews(result, product_id)
            )
        
        if self.health_monitor.is_feature_enabled("analytics"):
            non_essential_operations.append(
                self._add_analytics(result, product_id)
            )
        
        # Execute non-essential operations
        await DegradationStrategies.skip_non_essential(
            lambda: asyncio.sleep(0),  # No-op essential function
            non_essential_operations,
            self.health_monitor
        )
        
        return result
    
    async def _add_recommendations(self, result: Dict, product_id: str):
        """Add product recommendations"""
        try:
            recommendations = await self.recommendation_service.get_recommendations(product_id)
            result["recommendations"] = recommendations
        except Exception:
            # Fallback to popular products
            result["recommendations"] = await self._get_popular_products()
    
    async def _add_reviews(self, result: Dict, product_id: str):
        """Add product reviews"""
        try:
            reviews = await self.review_service.get_reviews(product_id)
            result["reviews"] = reviews
        except Exception:
            # Graceful degradation - show cached summary
            cached_summary = await self.cache.get(f"reviews_summary:{product_id}")
            if cached_summary:
                result["reviews_summary"] = cached_summary
    
    async def _add_analytics(self, result: Dict, product_id: str):
        """Add analytics data"""
        try:
            # Record view event for analytics
            await self.analytics_service.record_view(product_id)
        except Exception:
            # Analytics failure shouldn't affect user experience
            pass
    
    async def _get_popular_products(self) -> List[Dict]:
        """Fallback: get popular products from cache"""
        return await DegradationStrategies.fallback_to_static_data(
            lambda: self.cache.get("popular_products"),
            [{"id": "default", "name": "Featured Product"}]
        )

# Circuit Breaker with Degradation
class DegradedCircuitBreaker(AdvancedCircuitBreaker):
    """Circuit breaker that triggers graceful degradation"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig, 
                 degradation_callback: Callable = None):
        super().__init__(name, config)
        self.degradation_callback = degradation_callback
        
    def _transition_to_open(self):
        """Transition to OPEN and trigger degradation"""
        super()._transition_to_open()
        
        if self.degradation_callback:
            try:
                self.degradation_callback(self.name, "degraded")
            except Exception as e:
                logging.error(f"Degradation callback failed: {e}")
    
    def _transition_to_closed(self):
        """Transition to CLOSED and restore full functionality"""
        super()._transition_to_closed()
        
        if self.degradation_callback:
            try:
                self.degradation_callback(self.name, "restored")
            except Exception as e:
                logging.error(f"Restoration callback failed: {e}")

# E-commerce Service with Comprehensive Degradation
class ECommerceService:
    """E-commerce service with multiple degradation levels"""
    
    def __init__(self):
        self.health_monitor = ServiceHealthMonitor()
        self.setup_degradation_monitoring()
        
        # Service clients with degraded circuit breakers
        self.payment_service = self._create_degraded_client("payment")
        self.inventory_service = self._create_degraded_client("inventory")
        self.recommendation_service = self._create_degraded_client("recommendation")
    
    def setup_degradation_monitoring(self):
        """Setup health monitoring and degradation triggers"""
        
        # Monitor system resources
        asyncio.create_task(self._monitor_system_health())
        
        # Setup feature flags with degradation levels
        self.health_monitor.feature_flags.update({
            "personalization": FeatureFlag("personalization", True),
            "recommendations": FeatureFlag("recommendations", True),
            "real_time_inventory": FeatureFlag("real_time_inventory", True),
            "complex_pricing": FeatureFlag("complex_pricing", True),
        })
    
    def _create_degraded_client(self, service_name: str) -> ResilientServiceClient:
        """Create service client with degradation callback"""
        
        def degradation_callback(name: str, action: str):
            if action == "degraded":
                self.health_monitor.set_service_level(service_name, ServiceLevel.DEGRADED)
            elif action == "restored":
                self.health_monitor.set_service_level(service_name, ServiceLevel.FULL)
        
        client = ResilientServiceClient(service_name, f"http://{service_name}-service")
        client.circuit_breaker = DegradedCircuitBreaker(
            service_name, 
            CircuitBreakerConfig(), 
            degradation_callback
        )
        
        return client
    
    async def place_order(self, order_data: Dict) -> Dict[str, Any]:
        """Place order with multiple degradation levels"""
        
        result = {"order_id": str(uuid.uuid4()), "status": "processing"}
        
        try:
            # Essential: Create order record
            await self._create_order_record(result["order_id"], order_data)
            
            # Essential: Process payment (with degraded options)
            payment_result = await self._process_payment_with_degradation(order_data["payment"])
            result["payment"] = payment_result
            
            # Semi-essential: Inventory management
            if self.health_monitor.is_feature_enabled("real_time_inventory"):
                try:
                    await self.inventory_service.call("POST", "/reserve", json=order_data["items"])
                    result["inventory_reserved"] = True
                except Exception:
                    # Fallback: Optimistic inventory (process later)
                    result["inventory_reserved"] = False
                    result["inventory_status"] = "will_be_processed"
            
            # Non-essential: Recommendations for upsell
            if self.health_monitor.is_feature_enabled("recommendations"):
                try:
                    recommendations = await self.recommendation_service.call(
                        "GET", f"/upsell/{order_data['user_id']}"
                    )
                    result["upsell_recommendations"] = recommendations
                except Exception:
                    pass  # Skip recommendations on failure
            
            result["status"] = "confirmed"
            return result
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            raise
    
    async def _process_payment_with_degradation(self, payment_data: Dict) -> Dict:
        """Process payment with degradation options"""
        
        if self.health_monitor.get_service_level("payment") == ServiceLevel.FULL:
            # Full processing with all features
            return await self.payment_service.call("POST", "/charge", json=payment_data)
        
        elif self.health_monitor.get_service_level("payment") == ServiceLevel.DEGRADED:
            # Simplified processing
            simplified_payment = {
                "amount": payment_data["amount"],
                "currency": payment_data.get("currency", "USD"),
                "method": payment_data.get("method", "card")
            }
            return await self.payment_service.call("POST", "/simple_charge", json=simplified_payment)
        
        else:
            # Minimal: Store for later processing
            return {
                "status": "deferred",
                "message": "Payment will be processed when service is restored"
            }
    
    async def _monitor_system_health(self):
        """Monitor system health and adjust service levels"""
        while True:
            try:
                # Check CPU, memory, network latency, etc.
                system_metrics = await self._get_system_metrics()
                
                if system_metrics["cpu_usage"] > 80:
                    self.health_monitor.set_service_level("current", ServiceLevel.DEGRADED)
                elif system_metrics["cpu_usage"] > 95:
                    self.health_monitor.set_service_level("current", ServiceLevel.MINIMAL)
                else:
                    self.health_monitor.set_service_level("current", ServiceLevel.FULL)
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logging.error(f"Health monitoring failed: {e}")
                await asyncio.sleep(30)
```

---

## 6. Chaos Engineering

### Chaos Engineering Framework

```python
import random
import asyncio
from typing import List, Dict, Any, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class ChaosType(Enum):
    LATENCY = "latency"
    FAILURE = "failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    NETWORK_PARTITION = "network_partition"
    DATA_CORRUPTION = "data_corruption"

@dataclass
class ChaosExperiment:
    name: str
    description: str
    chaos_type: ChaosType
    target_services: List[str]
    blast_radius: str  # "single_instance", "service", "region"
    probability: float  # 0.0 to 1.0
    duration: int  # seconds
    enabled: bool = True
    steady_state_hypothesis: str = ""
    
class ChaosAction(ABC):
    """Base class for chaos actions"""
    
    @abstractmethod
    async def apply(self, target: str) -> Dict[str, Any]:
        """Apply chaos to target"""
        pass
    
    @abstractmethod
    async def rollback(self, target: str, action_result: Dict[str, Any]):
        """Rollback chaos action"""
        pass

class LatencyInjection(ChaosAction):
    """Inject network latency"""
    
    def __init__(self, min_delay: float, max_delay: float):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.original_delays = {}
    
    async def apply(self, target: str) -> Dict[str, Any]:
        delay = random.uniform(self.min_delay, self.max_delay)
        
        # Store original delay for rollback
        self.original_delays[target] = 0  # Assume no original delay
        
        # Apply delay to service calls
        await self._inject_delay(target, delay)
        
        return {"delay_injected": delay, "target": target}
    
    async def rollback(self, target: str, action_result: Dict[str, Any]):
        await self._remove_delay(target)
    
    async def _inject_delay(self, target: str, delay: float):
        """Inject delay into service calls"""
        # This would integrate with your service mesh or load balancer
        # For example, with Istio:
        # kubectl apply -f latency-injection-virtualservice.yaml
        pass
    
    async def _remove_delay(self, target: str):
        """Remove injected delay"""
        pass

class ServiceFailure(ChaosAction):
    """Simulate service failures"""
    
    def __init__(self, failure_rate: float):
        self.failure_rate = failure_rate
        self.affected_instances = {}
    
    async def apply(self, target: str) -> Dict[str, Any]:
        # Randomly select instances to fail
        instances = await self._get_service_instances(target)
        num_to_fail = int(len(instances) * self.failure_rate)
        instances_to_fail = random.sample(instances, num_to_fail)
        
        self.affected_instances[target] = instances_to_fail
        
        for instance in instances_to_fail:
            await self._stop_instance(instance)
        
        return {"instances_failed": len(instances_to_fail), "total_instances": len(instances)}
    
    async def rollback(self, target: str, action_result: Dict[str, Any]):
        instances = self.affected_instances.get(target, [])
        for instance in instances:
            await self._restart_instance(instance)
    
    async def _get_service_instances(self, service_name: str) -> List[str]:
        """Get list of service instances"""
        # This would query Kubernetes or service registry
        return [f"{service_name}-instance-{i}" for i in range(3)]
    
    async def _stop_instance(self, instance: str):
        """Stop service instance"""
        # kubectl delete pod {instance}
        pass
    
    async def _restart_instance(self, instance: str):
        """Restart service instance"""
        # kubectl scale deployment {service} --replicas=desired_count
        pass

class ResourceExhaustion(ChaosAction):
    """Exhaust system resources (CPU, memory, disk)"""
    
    def __init__(self, resource_type: str, consumption_percentage: float):
        self.resource_type = resource_type
        self.consumption_percentage = consumption_percentage
        self.stress_processes = {}
    
    async def apply(self, target: str) -> Dict[str, Any]:
        if self.resource_type == "cpu":
            process_id = await self._start_cpu_stress(target)
        elif self.resource_type == "memory":
            process_id = await self._start_memory_stress(target)
        elif self.resource_type == "disk":
            process_id = await self._start_disk_stress(target)
        else:
            raise ValueError(f"Unknown resource type: {self.resource_type}")
        
        self.stress_processes[target] = process_id
        
        return {"resource": self.resource_type, "consumption": self.consumption_percentage}
    
    async def rollback(self, target: str, action_result: Dict[str, Any]):
        process_id = self.stress_processes.get(target)
        if process_id:
            await self._stop_stress_process(process_id)
    
    async def _start_cpu_stress(self, target: str) -> str:
        """Start CPU stress test"""
        # Use stress-ng or similar tool
        # stress-ng --cpu 4 --timeout 300s
        return "cpu_stress_process_id"
    
    async def _start_memory_stress(self, target: str) -> str:
        """Start memory stress test"""
        # stress-ng --vm 2 --vm-bytes 1G --timeout 300s
        return "memory_stress_process_id"
    
    async def _start_disk_stress(self, target: str) -> str:
        """Start disk I/O stress test"""
        # stress-ng --hdd 1 --hdd-bytes 1G --timeout 300s
        return "disk_stress_process_id"
    
    async def _stop_stress_process(self, process_id: str):
        """Stop stress process"""
        # kill process
        pass

class ChaosOrchestrator:
    """Orchestrates chaos experiments"""
    
    def __init__(self):
        self.experiments: Dict[str, ChaosExperiment] = {}
        self.actions: Dict[ChaosType, ChaosAction] = {}
        self.active_experiments: Dict[str, Dict] = {}
        self.metrics_collector = MetricsCollector()
        
        self._register_actions()
    
    def _register_actions(self):
        """Register available chaos actions"""
        self.actions[ChaosType.LATENCY] = LatencyInjection(0.1, 2.0)
        self.actions[ChaosType.FAILURE] = ServiceFailure(0.3)
        self.actions[ChaosType.RESOURCE_EXHAUSTION] = ResourceExhaustion("cpu", 80.0)
    
    def register_experiment(self, experiment: ChaosExperiment):
        """Register a new chaos experiment"""
        self.experiments[experiment.name] = experiment
    
    async def run_experiment(self, experiment_name: str) -> Dict[str, Any]:
        """Run a specific chaos experiment"""
        if experiment_name not in self.experiments:
            raise ValueError(f"Experiment {experiment_name} not found")
        
        experiment = self.experiments[experiment_name]
        if not experiment.enabled:
            return {"status": "skipped", "reason": "experiment disabled"}
        
        # Check if experiment should run (probability)
        if random.random() > experiment.probability:
            return {"status": "skipped", "reason": "probability not met"}
        
        print(f"Starting chaos experiment: {experiment.name}")
        
        try:
            # Collect baseline metrics
            baseline_metrics = await self.metrics_collector.collect_baseline(
                experiment.target_services
            )
            
            # Apply chaos
            chaos_action = self.actions[experiment.chaos_type]
            action_results = {}
            
            for target in experiment.target_services:
                action_result = await chaos_action.apply(target)
                action_results[target] = action_result
            
            # Store experiment state
            self.active_experiments[experiment_name] = {
                "experiment": experiment,
                "action_results": action_results,
                "start_time": time.time(),
                "baseline_metrics": baseline_metrics
            }
            
            # Wait for duration
            await asyncio.sleep(experiment.duration)
            
            # Collect metrics during chaos
            chaos_metrics = await self.metrics_collector.collect_metrics(
                experiment.target_services
            )
            
            # Rollback chaos
            for target in experiment.target_services:
                await chaos_action.rollback(target, action_results[target])
            
            # Collect recovery metrics
            await asyncio.sleep(60)  # Wait for recovery
            recovery_metrics = await self.metrics_collector.collect_metrics(
                experiment.target_services
            )
            
            # Analyze results
            analysis = await self._analyze_experiment_results(
                experiment, baseline_metrics, chaos_metrics, recovery_metrics
            )
            
            return {
                "status": "completed",
                "experiment": experiment.name,
                "baseline_metrics": baseline_metrics,
                "chaos_metrics": chaos_metrics,
                "recovery_metrics": recovery_metrics,
                "analysis": analysis
            }
            
        except Exception as e:
            # Emergency rollback
            await self._emergency_rollback(experiment_name)
            return {"status": "failed", "error": str(e)}
        
        finally:
            # Cleanup
            if experiment_name in self.active_experiments:
                del self.active_experiments[experiment_name]
    
    async def _analyze_experiment_results(self, experiment: ChaosExperiment,
                                        baseline: Dict, chaos: Dict, recovery: Dict) -> Dict:
        """Analyze experiment results"""
        analysis = {
            "steady_state_maintained": True,
            "recovery_time_seconds": 0,
            "issues_found": []
        }
        
        # Check if steady state hypothesis holds
        for service in experiment.target_services:
            baseline_success_rate = baseline.get(service, {}).get("success_rate", 0)
            chaos_success_rate = chaos.get(service, {}).get("success_rate", 0)
            
            # If success rate drops below acceptable threshold
            if chaos_success_rate < baseline_success_rate * 0.9:  # 10% degradation allowed
                analysis["steady_state_maintained"] = False
                analysis["issues_found"].append(
                    f"Service {service} success rate dropped from "
                    f"{baseline_success_rate:.2%} to {chaos_success_rate:.2%}"
                )
        
        # Calculate recovery time
        for service in experiment.target_services:
            recovery_success_rate = recovery.get(service, {}).get("success_rate", 0)
            baseline_success_rate = baseline.get(service, {}).get("success_rate", 0)
            
            if recovery_success_rate >= baseline_success_rate * 0.95:  # 95% recovery
                analysis["recovery_time_seconds"] = 60  # Our wait time
            else:
                analysis["recovery_time_seconds"] = -1  # Not recovered
                analysis["issues_found"].append(
                    f"Service {service} did not fully recover"
                )
        
        return analysis
    
    async def _emergency_rollback(self, experiment_name: str):
        """Emergency rollback of chaos experiment"""
        if experiment_name not in self.active_experiments:
            return
        
        experiment_data = self.active_experiments[experiment_name]
        experiment = experiment_data["experiment"]
        action_results = experiment_data["action_results"]
        
        chaos_action = self.actions[experiment.chaos_type]
        
        for target in experiment.target_services:
            try:
                await chaos_action.rollback(target, action_results[target])
            except Exception as e:
                logging.error(f"Emergency rollback failed for {target}: {e}")

class MetricsCollector:
    """Collects system metrics for chaos experiments"""
    
    async def collect_baseline(self, services: List[str]) -> Dict[str, Dict[str, float]]:
        """Collect baseline metrics before chaos"""
        metrics = {}
        
        for service in services:
            metrics[service] = await self._collect_service_metrics(service)
        
        return metrics
    
    async def collect_metrics(self, services: List[str]) -> Dict[str, Dict[str, float]]:
        """Collect current metrics"""
        return await self.collect_baseline(services)  # Same implementation
    
    async def _collect_service_metrics(self, service: str) -> Dict[str, float]:
        """Collect metrics for a specific service"""
        # This would integrate with your monitoring system (Prometheus, etc.)
        return {
            "success_rate": random.uniform(0.95, 0.99),  # Simulated
            "latency_p99": random.uniform(100, 300),     # ms
            "throughput": random.uniform(1000, 2000),    # req/s
            "cpu_usage": random.uniform(30, 70),         # %
            "memory_usage": random.uniform(40, 80)       # %
        }

# Chaos Engineering Scheduler
class ChaosScheduler:
    """Schedules and runs chaos experiments"""
    
    def __init__(self, orchestrator: ChaosOrchestrator):
        self.orchestrator = orchestrator
        self.schedule: Dict[str, Dict] = {}
        self.running = False
    
    def schedule_experiment(self, experiment_name: str, cron_expression: str):
        """Schedule experiment with cron-like expression"""
        self.schedule[experiment_name] = {
            "cron": cron_expression,
            "next_run": self._calculate_next_run(cron_expression)
        }
    
    async def start_scheduler(self):
        """Start the chaos scheduler"""
        self.running = True
        
        while self.running:
            current_time = time.time()
            
            for experiment_name, schedule_info in self.schedule.items():
                if current_time >= schedule_info["next_run"]:
                    # Run experiment
                    try:
                        result = await self.orchestrator.run_experiment(experiment_name)
                        logging.info(f"Scheduled chaos experiment {experiment_name}: {result['status']}")
                    except Exception as e:
                        logging.error(f"Scheduled chaos experiment {experiment_name} failed: {e}")
                    
                    # Calculate next run
                    schedule_info["next_run"] = self._calculate_next_run(schedule_info["cron"])
            
            await asyncio.sleep(60)  # Check every minute
    
    def stop_scheduler(self):
        """Stop the chaos scheduler"""
        self.running = False
    
    def _calculate_next_run(self, cron_expression: str) -> float:
        """Calculate next run time from cron expression"""
        # Simplified implementation - in practice, use croniter or similar
        return time.time() + 3600  # Run every hour for demo

# Example Usage
async def setup_chaos_engineering():
    """Setup chaos engineering for e-commerce system"""
    
    orchestrator = ChaosOrchestrator()
    
    # Define chaos experiments
    experiments = [
        ChaosExperiment(
            name="payment_service_latency",
            description="Inject latency into payment service to test timeout handling",
            chaos_type=ChaosType.LATENCY,
            target_services=["payment-service"],
            blast_radius="service",
            probability=0.1,  # 10% chance to run
            duration=300,     # 5 minutes
            steady_state_hypothesis="Order completion rate should stay above 95%"
        ),
        ChaosExperiment(
            name="inventory_service_failure",
            description="Kill inventory service instances to test fault tolerance",
            chaos_type=ChaosType.FAILURE,
            target_services=["inventory-service"],
            blast_radius="service",
            probability=0.05,  # 5% chance to run
            duration=180,      # 3 minutes
            steady_state_hypothesis="Orders should fallback to optimistic inventory"
        ),
        ChaosExperiment(
            name="database_cpu_exhaustion",
            description="Exhaust database CPU to test performance degradation",
            chaos_type=ChaosType.RESOURCE_EXHAUSTION,
            target_services=["postgres-primary"],
            blast_radius="single_instance",
            probability=0.02,  # 2% chance to run
            duration=120,      # 2 minutes
            steady_state_hypothesis="Read replicas should handle increased load"
        )
    ]
    
    # Register experiments
    for experiment in experiments:
        orchestrator.register_experiment(experiment)
    
    # Setup scheduler
    scheduler = ChaosScheduler(orchestrator)
    scheduler.schedule_experiment("payment_service_latency", "0 */4 * * *")  # Every 4 hours
    scheduler.schedule_experiment("inventory_service_failure", "0 2 * * 1")  # Monday 2 AM
    scheduler.schedule_experiment("database_cpu_exhaustion", "0 3 * * 6")    # Saturday 3 AM
    
    # Start scheduler
    await scheduler.start_scheduler()

# Example: Manual chaos experiment
async def run_manual_chaos_test():
    """Run a manual chaos engineering test"""
    
    orchestrator = ChaosOrchestrator()
    
    experiment = ChaosExperiment(
        name="manual_test",
        description="Manual test of order service resilience",
        chaos_type=ChaosType.LATENCY,
        target_services=["order-service"],
        blast_radius="service", 
        probability=1.0,  # Always run
        duration=60       # 1 minute
    )
    
    orchestrator.register_experiment(experiment)
    result = await orchestrator.run_experiment("manual_test")
    
    print(f"Chaos experiment result: {result}")
    
    if not result["analysis"]["steady_state_maintained"]:
        print("⚠️  Issues found:")
        for issue in result["analysis"]["issues_found"]:
            print(f"   - {issue}")
    else:
        print("✅ System maintained steady state during chaos")
```

---

## Labs and Projects

### Lab 1: Circuit Breaker Implementation
Build a comprehensive circuit breaker library with monitoring and metrics.

### Lab 2: Bulkhead Pattern
Implement resource isolation for a multi-tenant application.

### Lab 3: Graceful Degradation
Design a service that gracefully degrades functionality during failures.

### Lab 4: Chaos Engineering
Set up automated chaos experiments for your microservices architecture.

## Assessment

### Resilience Architecture Review
Design and implement a resilience strategy for a distributed e-commerce platform including:

1. **Failure Analysis**: Identify potential failure modes and their impact
2. **Pattern Implementation**: Apply appropriate resilience patterns
3. **Monitoring**: Set up observability for resilience mechanisms
4. **Testing**: Design and execute chaos experiments
5. **Documentation**: Create runbooks for incident response

## References

### Essential Reading
- "Release It!" by Michael Nygard
- "Chaos Engineering" by Casey Rosenthal
- "The Site Reliability Workbook" by Google SRE Team

### Tools and Frameworks
- [Chaos Monkey](https://github.com/Netflix/chaosmonkey) - Netflix's chaos engineering tool
- [Litmus](https://litmuschaos.io/) - Kubernetes-native chaos engineering
- [Hystrix](https://github.com/Netflix/Hystrix) - Circuit breaker library

---

*Next: [Module 06 - Observability](../06_OBSERVABILITY/)*