# Module 3: Health Checks & Service Discovery
## Building Resilient Load Balancing with Intelligent Service Management

### Learning Objectives
- Master active and passive health checking strategies
- Implement circuit breaker patterns for fault tolerance
- Integrate with service discovery systems (Consul, etcd, Kubernetes)
- Design automated failover and recovery mechanisms
- Build health check systems that scale with your infrastructure

---

## 3.1 Understanding Health Checks

### 3.1.1 Why Health Checks Matter

Health checks are the nervous system of your load balancing infrastructure. They determine:
- **Service Availability**: Which servers can handle requests
- **Performance Degradation**: When servers are struggling but not failed
- **Maintenance Windows**: Graceful removal from rotation
- **Auto-scaling Decisions**: When to add/remove capacity

#### The Cost of Poor Health Checking

```
Without proper health checks:
Client → Load Balancer → Failed Server → 500 Error
                    → Failed Server → 500 Error  
                    → Failed Server → 500 Error

With health checks:
Client → Load Balancer → Healthy Server → Success
                    ↓ (Failed servers removed)
                   Monitoring System → Alert
```

### 3.1.2 Health Check Types

#### Layer 3/4 Health Checks (TCP/UDP)
**Mechanism**: Test network connectivity
```bash
# Simple TCP health check
nc -z server.example.com 80 && echo "UP" || echo "DOWN"

# With timeout
timeout 3 nc -z server.example.com 80
```

**Pros**:
- Fast and lightweight
- Protocol-agnostic
- Minimal server resources

**Cons**:
- Only tests network connectivity
- Doesn't verify application health
- Can't detect application-level issues

#### Layer 7 Health Checks (HTTP/HTTPS)
**Mechanism**: Test application-specific endpoints
```bash
# HTTP health check with expected response
curl -f -m 5 http://server.example.com/health
```

**Pros**:
- Tests actual application functionality
- Can verify dependencies (database, cache, etc.)
- Provides detailed health information

**Cons**:
- Higher overhead
- Application must implement health endpoints
- Potential security considerations

---

## 3.2 Active vs Passive Health Checking

### 3.2.1 Active Health Checks

**Definition**: Proactively send requests to test server health.

```python
# Active health check implementation
import asyncio
import aiohttp
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

class HealthStatus(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"

@dataclass
class HealthCheckConfig:
    interval: int = 30  # seconds
    timeout: int = 5    # seconds
    retries: int = 3
    failure_threshold: int = 3
    success_threshold: int = 2
    degraded_threshold_ms: int = 1000

@dataclass
class ServerHealth:
    status: HealthStatus = HealthStatus.UNKNOWN
    last_check: float = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    response_time_ms: float = 0
    error_message: Optional[str] = None
    check_count: int = 0

class ActiveHealthChecker:
    """
    Comprehensive active health checker supporting multiple protocols
    and sophisticated health determination logic.
    """
    
    def __init__(self, config: HealthCheckConfig = None):
        self.config = config or HealthCheckConfig()
        self.server_health: Dict[str, ServerHealth] = {}
        self.running = False
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def start(self):
        """Start the health checking service."""
        if self.running:
            return
            
        self.running = True
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )
        
        # Start health check loop
        asyncio.create_task(self._health_check_loop())
    
    async def stop(self):
        """Stop the health checking service."""
        self.running = False
        if self.session:
            await self.session.close()
    
    async def add_server(self, server_id: str, health_url: str, 
                        expected_status: int = 200, expected_content: str = None):
        """Add a server for health monitoring."""
        self.server_health[server_id] = {
            'health': ServerHealth(),
            'url': health_url,
            'expected_status': expected_status,
            'expected_content': expected_content
        }
    
    async def remove_server(self, server_id: str):
        """Remove a server from health monitoring."""
        self.server_health.pop(server_id, None)
    
    async def _health_check_loop(self):
        """Main health checking loop."""
        while self.running:
            start_time = time.time()
            
            # Check all servers concurrently
            tasks = []
            for server_id in list(self.server_health.keys()):
                task = asyncio.create_task(self._check_server_health(server_id))
                tasks.append(task)
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Calculate sleep time to maintain interval
            elapsed = time.time() - start_time
            sleep_time = max(0, self.config.interval - elapsed)
            await asyncio.sleep(sleep_time)
    
    async def _check_server_health(self, server_id: str):
        """Check health of a single server with retries."""
        server_config = self.server_health.get(server_id)
        if not server_config:
            return
        
        health = server_config['health']
        health.check_count += 1
        
        # Perform health check with retries
        success = False
        last_error = None
        response_time = float('inf')
        
        for attempt in range(self.config.retries):
            try:
                start_time = time.time()
                
                async with self.session.get(server_config['url']) as response:
                    response_time = (time.time() - start_time) * 1000  # ms
                    
                    # Check status code
                    if response.status != server_config['expected_status']:
                        raise Exception(f"Unexpected status: {response.status}")
                    
                    # Check content if specified
                    if server_config['expected_content']:
                        content = await response.text()
                        if server_config['expected_content'] not in content:
                            raise Exception("Expected content not found")
                
                success = True
                break
                
            except Exception as e:
                last_error = str(e)
                if attempt < self.config.retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))  # Backoff
        
        # Update health status
        await self._update_health_status(server_id, success, response_time, last_error)
    
    async def _update_health_status(self, server_id: str, success: bool, 
                                  response_time: float, error: Optional[str]):
        """Update server health status based on check result."""
        health = self.server_health[server_id]['health']
        health.last_check = time.time()
        health.response_time_ms = response_time if success else 0
        health.error_message = error if not success else None
        
        if success:
            health.consecutive_failures = 0
            health.consecutive_successes += 1
            
            # Determine if healthy or degraded based on response time
            if response_time > self.config.degraded_threshold_ms:
                new_status = HealthStatus.DEGRADED
            elif health.consecutive_successes >= self.config.success_threshold:
                new_status = HealthStatus.HEALTHY
            else:
                new_status = health.status  # Keep current status
                
        else:
            health.consecutive_successes = 0
            health.consecutive_failures += 1
            
            if health.consecutive_failures >= self.config.failure_threshold:
                new_status = HealthStatus.UNHEALTHY
            else:
                new_status = health.status  # Keep current status
        
        # Update status and log changes
        if new_status != health.status:
            old_status = health.status
            health.status = new_status
            await self._on_status_change(server_id, old_status, new_status)
    
    async def _on_status_change(self, server_id: str, old_status: HealthStatus, 
                              new_status: HealthStatus):
        """Handle server status changes."""
        print(f"Server {server_id} status: {old_status.value} → {new_status.value}")
        
        # Here you would typically:
        # - Update load balancer configuration
        # - Send alerts/notifications
        # - Log to monitoring systems
        # - Trigger auto-scaling actions
    
    def get_healthy_servers(self) -> List[str]:
        """Get list of currently healthy servers."""
        return [
            server_id for server_id, config in self.server_health.items()
            if config['health'].status == HealthStatus.HEALTHY
        ]
    
    def get_server_metrics(self) -> Dict[str, Dict]:
        """Get comprehensive health metrics for all servers."""
        metrics = {}
        for server_id, config in self.server_health.items():
            health = config['health']
            metrics[server_id] = {
                'status': health.status.value,
                'last_check': health.last_check,
                'consecutive_failures': health.consecutive_failures,
                'consecutive_successes': health.consecutive_successes,
                'response_time_ms': health.response_time_ms,
                'error_message': health.error_message,
                'check_count': health.check_count,
                'uptime_percentage': self._calculate_uptime(health)
            }
        return metrics
    
    def _calculate_uptime(self, health: ServerHealth) -> float:
        """Calculate uptime percentage (simplified)."""
        if health.check_count == 0:
            return 0.0
        
        # Simple calculation based on recent checks
        success_count = health.check_count - health.consecutive_failures
        return (success_count / health.check_count) * 100
```

### 3.2.2 Passive Health Checks

**Definition**: Monitor actual request traffic to detect failures.

```python
# Passive health check implementation
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Deque
import threading

@dataclass
class PassiveHealthConfig:
    window_size: int = 100  # Number of requests to track
    failure_threshold: float = 0.5  # 50% failure rate
    min_requests: int = 10  # Minimum requests before making decisions
    recovery_requests: int = 5  # Successful requests needed for recovery

@dataclass
class RequestResult:
    timestamp: float
    success: bool
    response_time_ms: float
    status_code: int = 0
    error: Optional[str] = None

@dataclass
class PassiveHealthMetrics:
    recent_requests: Deque[RequestResult] = field(default_factory=deque)
    total_requests: int = 0
    total_failures: int = 0
    is_healthy: bool = True
    last_failure_time: float = 0
    last_success_time: float = 0
    
    def __post_init__(self):
        if not isinstance(self.recent_requests, deque):
            self.recent_requests = deque(maxlen=100)

class PassiveHealthChecker:
    """
    Passive health checker that monitors actual request traffic
    to determine server health without additional overhead.
    """
    
    def __init__(self, config: PassiveHealthConfig = None):
        self.config = config or PassiveHealthConfig()
        self.server_metrics: Dict[str, PassiveHealthMetrics] = {}
        self.lock = threading.RLock()
    
    def add_server(self, server_id: str):
        """Add a server for passive monitoring."""
        with self.lock:
            self.server_metrics[server_id] = PassiveHealthMetrics()
            self.server_metrics[server_id].recent_requests = deque(
                maxlen=self.config.window_size
            )
    
    def remove_server(self, server_id: str):
        """Remove a server from passive monitoring."""
        with self.lock:
            self.server_metrics.pop(server_id, None)
    
    def record_request(self, server_id: str, success: bool, 
                      response_time_ms: float, status_code: int = 0, 
                      error: Optional[str] = None):
        """Record the result of a request for passive monitoring."""
        with self.lock:
            metrics = self.server_metrics.get(server_id)
            if not metrics:
                return
            
            # Record request
            request = RequestResult(
                timestamp=time.time(),
                success=success,
                response_time_ms=response_time_ms,
                status_code=status_code,
                error=error
            )
            
            metrics.recent_requests.append(request)
            metrics.total_requests += 1
            
            if success:
                metrics.last_success_time = time.time()
            else:
                metrics.total_failures += 1
                metrics.last_failure_time = time.time()
            
            # Update health status
            self._update_health_status(server_id, metrics)
    
    def _update_health_status(self, server_id: str, metrics: PassiveHealthMetrics):
        """Update health status based on recent request patterns."""
        recent_requests = list(metrics.recent_requests)
        
        if len(recent_requests) < self.config.min_requests:
            return  # Not enough data
        
        # Calculate failure rate
        failures = sum(1 for req in recent_requests if not req.success)
        failure_rate = failures / len(recent_requests)
        
        old_health = metrics.is_healthy
        
        if metrics.is_healthy:
            # Currently healthy - check if we should mark as unhealthy
            if failure_rate >= self.config.failure_threshold:
                metrics.is_healthy = False
                self._on_health_change(server_id, True, False, failure_rate)
        else:
            # Currently unhealthy - check if we should mark as healthy
            recent_successes = sum(1 for req in recent_requests[-self.config.recovery_requests:] 
                                 if req.success)
            if recent_successes >= self.config.recovery_requests:
                metrics.is_healthy = True
                self._on_health_change(server_id, False, True, failure_rate)
    
    def _on_health_change(self, server_id: str, was_healthy: bool, 
                         is_healthy: bool, failure_rate: float):
        """Handle health status changes."""
        status = "healthy" if is_healthy else "unhealthy"
        print(f"Server {server_id} marked as {status} (failure rate: {failure_rate:.2%})")
    
    def get_healthy_servers(self) -> List[str]:
        """Get list of currently healthy servers."""
        with self.lock:
            return [
                server_id for server_id, metrics in self.server_metrics.items()
                if metrics.is_healthy
            ]
    
    def get_server_metrics(self) -> Dict[str, Dict]:
        """Get comprehensive passive health metrics."""
        with self.lock:
            result = {}
            for server_id, metrics in self.server_metrics.items():
                recent = list(metrics.recent_requests)
                
                result[server_id] = {
                    'is_healthy': metrics.is_healthy,
                    'total_requests': metrics.total_requests,
                    'total_failures': metrics.total_failures,
                    'failure_rate': metrics.total_failures / max(1, metrics.total_requests),
                    'recent_failure_rate': self._calculate_recent_failure_rate(recent),
                    'average_response_time': self._calculate_avg_response_time(recent),
                    'last_success_time': metrics.last_success_time,
                    'last_failure_time': metrics.last_failure_time,
                    'recent_requests_count': len(recent)
                }
            
            return result
    
    def _calculate_recent_failure_rate(self, requests: List[RequestResult]) -> float:
        """Calculate failure rate for recent requests."""
        if not requests:
            return 0.0
        
        failures = sum(1 for req in requests if not req.success)
        return failures / len(requests)
    
    def _calculate_avg_response_time(self, requests: List[RequestResult]) -> float:
        """Calculate average response time for recent requests."""
        if not requests:
            return 0.0
        
        successful_requests = [req for req in requests if req.success]
        if not successful_requests:
            return 0.0
        
        total_time = sum(req.response_time_ms for req in successful_requests)
        return total_time / len(successful_requests)
```

---

## 3.3 Circuit Breaker Pattern

### 3.3.1 Understanding Circuit Breakers

Circuit breakers prevent cascading failures by stopping requests to failing services.

**States**:
1. **CLOSED**: Normal operation, requests flow through
2. **OPEN**: Service is failing, requests immediately fail
3. **HALF_OPEN**: Testing if service has recovered

```python
# Circuit breaker implementation
import time
import threading
from enum import Enum
from dataclasses import dataclass
from typing import Callable, Any, Optional

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5      # Failures before opening
    recovery_timeout: int = 60      # Seconds before trying half-open
    success_threshold: int = 3      # Successes needed to close
    request_timeout: int = 10       # Timeout for individual requests
    slow_call_threshold: float = 5.0  # Seconds for slow call

class CircuitBreakerException(Exception):
    """Exception raised when circuit breaker is open."""
    pass

class CircuitBreaker:
    """
    Sophisticated circuit breaker implementation with multiple failure modes
    and comprehensive monitoring.
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        # State management
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.last_success_time = 0
        self.lock = threading.RLock()
        
        # Metrics
        self.total_calls = 0
        self.total_failures = 0
        self.total_timeouts = 0
        self.total_slow_calls = 0
        
        # Callbacks
        self.on_state_change: Optional[Callable] = None
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with circuit breaker protection."""
        with self.lock:
            self.total_calls += 1
            
            # Check if circuit is open
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    self.total_failures += 1
                    raise CircuitBreakerException(f"Circuit breaker {self.name} is OPEN")
            
            # Execute the function
            start_time = time.time()
            try:
                # Add timeout protection
                result = self._execute_with_timeout(func, *args, **kwargs)
                execution_time = time.time() - start_time
                
                # Check for slow calls
                if execution_time > self.config.slow_call_threshold:
                    self.total_slow_calls += 1
                    self._record_failure()  # Treat slow calls as failures
                else:
                    self._record_success()
                
                return result
                
            except Exception as e:
                self.total_failures += 1
                execution_time = time.time() - start_time
                
                # Check if it was a timeout
                if execution_time >= self.config.request_timeout:
                    self.total_timeouts += 1
                
                self._record_failure()
                raise e
    
    def _execute_with_timeout(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with timeout protection."""
        # In a real implementation, you might use more sophisticated
        # timeout mechanisms like asyncio.wait_for or signal.alarm
        
        # For this example, we'll just execute directly
        # In production, consider using concurrent.futures with timeout
        return func(*args, **kwargs)
    
    def _record_success(self):
        """Record a successful call."""
        self.last_success_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    def _record_failure(self):
        """Record a failed call."""
        self.last_failure_time = time.time()
        self.failure_count += 1
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self._transition_to_open()
        elif self.state == CircuitState.HALF_OPEN:
            self._transition_to_open()
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        return (time.time() - self.last_failure_time) >= self.config.recovery_timeout
    
    def _transition_to_open(self):
        """Transition to OPEN state."""
        old_state = self.state
        self.state = CircuitState.OPEN
        self.failure_count = 0
        self.success_count = 0
        self._notify_state_change(old_state, CircuitState.OPEN)
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        old_state = self.state
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        self._notify_state_change(old_state, CircuitState.HALF_OPEN)
    
    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self._notify_state_change(old_state, CircuitState.CLOSED)
    
    def _notify_state_change(self, old_state: CircuitState, new_state: CircuitState):
        """Notify about state changes."""
        print(f"Circuit breaker {self.name}: {old_state.value} → {new_state.value}")
        
        if self.on_state_change:
            try:
                self.on_state_change(self.name, old_state, new_state)
            except Exception as e:
                print(f"Error in state change callback: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive circuit breaker metrics."""
        with self.lock:
            return {
                'name': self.name,
                'state': self.state.value,
                'total_calls': self.total_calls,
                'total_failures': self.total_failures,
                'total_timeouts': self.total_timeouts,
                'total_slow_calls': self.total_slow_calls,
                'failure_rate': self.total_failures / max(1, self.total_calls),
                'current_failure_count': self.failure_count,
                'current_success_count': self.success_count,
                'last_failure_time': self.last_failure_time,
                'last_success_time': self.last_success_time,
                'config': {
                    'failure_threshold': self.config.failure_threshold,
                    'recovery_timeout': self.config.recovery_timeout,
                    'success_threshold': self.config.success_threshold,
                    'slow_call_threshold': self.config.slow_call_threshold
                }
            }
    
    def force_open(self):
        """Manually force circuit breaker to OPEN state."""
        with self.lock:
            old_state = self.state
            self._transition_to_open()
    
    def force_closed(self):
        """Manually force circuit breaker to CLOSED state."""
        with self.lock:
            old_state = self.state
            self._transition_to_closed()
    
    def reset(self):
        """Reset circuit breaker to initial state."""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.total_calls = 0
            self.total_failures = 0
            self.total_timeouts = 0
            self.total_slow_calls = 0

# Circuit breaker manager for multiple services
class CircuitBreakerManager:
    """Manage multiple circuit breakers for different services."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.global_config = CircuitBreakerConfig()
    
    def get_circuit_breaker(self, name: str, 
                          config: CircuitBreakerConfig = None) -> CircuitBreaker:
        """Get or create a circuit breaker for a service."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(
                name, config or self.global_config
            )
        return self.circuit_breakers[name]
    
    def call_with_circuit_breaker(self, service_name: str, func: Callable, 
                                *args, **kwargs) -> Any:
        """Execute a function with circuit breaker protection."""
        circuit_breaker = self.get_circuit_breaker(service_name)
        return circuit_breaker.call(func, *args, **kwargs)
    
    def get_all_metrics(self) -> Dict[str, Dict]:
        """Get metrics for all circuit breakers."""
        return {name: cb.get_metrics() for name, cb in self.circuit_breakers.items()}
    
    def reset_all(self):
        """Reset all circuit breakers."""
        for cb in self.circuit_breakers.values():
            cb.reset()

# Example usage with load balancer integration
class CircuitBreakerLoadBalancer:
    """Load balancer with integrated circuit breaker protection."""
    
    def __init__(self, servers: List[str]):
        self.servers = servers
        self.circuit_manager = CircuitBreakerManager()
        self.current_server = 0
        
    def get_server(self) -> Optional[str]:
        """Get next available server, skipping those with open circuit breakers."""
        attempts = 0
        
        while attempts < len(self.servers):
            server = self.servers[self.current_server]
            circuit_breaker = self.circuit_manager.get_circuit_breaker(server)
            
            # Check if circuit breaker allows requests
            if circuit_breaker.state != CircuitState.OPEN:
                return server
            
            # Move to next server
            self.current_server = (self.current_server + 1) % len(self.servers)
            attempts += 1
        
        # All servers have open circuit breakers
        return None
    
    def call_server(self, server: str, func: Callable, *args, **kwargs):
        """Call a server function with circuit breaker protection."""
        return self.circuit_manager.call_with_circuit_breaker(
            server, func, *args, **kwargs
        )
```

---

## 3.4 Service Discovery Integration

### 3.4.1 Service Discovery Patterns

Service discovery enables dynamic server registration and discovery, essential for microservices and cloud-native applications.

```python
# Service discovery integration
import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Set, Optional, Callable
import time

@dataclass
class ServiceInstance:
    id: str
    host: str
    port: int
    metadata: Dict[str, str] = None
    health_check_url: Optional[str] = None
    tags: List[str] = None
    registered_at: float = 0
    last_heartbeat: float = 0
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.tags is None:
            self.tags = []
        if self.registered_at == 0:
            self.registered_at = time.time()

class ServiceDiscoveryProvider(ABC):
    """Abstract base for service discovery providers."""
    
    @abstractmethod
    async def register_service(self, service_name: str, instance: ServiceInstance):
        """Register a service instance."""
        pass
    
    @abstractmethod
    async def deregister_service(self, service_name: str, instance_id: str):
        """Deregister a service instance."""
        pass
    
    @abstractmethod
    async def discover_services(self, service_name: str) -> List[ServiceInstance]:
        """Discover instances of a service."""
        pass
    
    @abstractmethod
    async def watch_service(self, service_name: str, 
                          callback: Callable[[List[ServiceInstance]], None]):
        """Watch for changes to a service."""
        pass

class ConsulServiceDiscovery(ServiceDiscoveryProvider):
    """Consul-based service discovery implementation."""
    
    def __init__(self, consul_host: str = "localhost", consul_port: int = 8500):
        self.consul_host = consul_host
        self.consul_port = consul_port
        self.base_url = f"http://{consul_host}:{consul_port}/v1"
        
        # For demo purposes, we'll use a simple in-memory store
        # In production, this would use the actual Consul API
        self.services: Dict[str, Dict[str, ServiceInstance]] = {}
        self.watchers: Dict[str, List[Callable]] = {}
    
    async def register_service(self, service_name: str, instance: ServiceInstance):
        """Register a service instance with Consul."""
        if service_name not in self.services:
            self.services[service_name] = {}
        
        self.services[service_name][instance.id] = instance
        
        # Create health check if URL provided
        if instance.health_check_url:
            await self._register_health_check(service_name, instance)
        
        # Notify watchers
        await self._notify_watchers(service_name)
    
    async def deregister_service(self, service_name: str, instance_id: str):
        """Deregister a service instance from Consul."""
        if service_name in self.services:
            self.services[service_name].pop(instance_id, None)
            
            # Clean up empty service entries
            if not self.services[service_name]:
                del self.services[service_name]
        
        # Notify watchers
        await self._notify_watchers(service_name)
    
    async def discover_services(self, service_name: str) -> List[ServiceInstance]:
        """Discover healthy instances of a service."""
        instances = self.services.get(service_name, {})
        
        # Filter for healthy instances
        healthy_instances = []
        for instance in instances.values():
            if await self._is_instance_healthy(instance):
                healthy_instances.append(instance)
        
        return healthy_instances
    
    async def watch_service(self, service_name: str, 
                          callback: Callable[[List[ServiceInstance]], None]):
        """Watch for changes to a service."""
        if service_name not in self.watchers:
            self.watchers[service_name] = []
        
        self.watchers[service_name].append(callback)
        
        # Send initial state
        instances = await self.discover_services(service_name)
        callback(instances)
    
    async def _register_health_check(self, service_name: str, instance: ServiceInstance):
        """Register health check with Consul."""
        # In real implementation, this would register with Consul's health check system
        print(f"Health check registered for {service_name}:{instance.id}")
    
    async def _is_instance_healthy(self, instance: ServiceInstance) -> bool:
        """Check if an instance is healthy."""
        # Simplified health check - in production, this would query Consul
        current_time = time.time()
        heartbeat_timeout = 60  # seconds
        
        return (current_time - instance.last_heartbeat) < heartbeat_timeout
    
    async def _notify_watchers(self, service_name: str):
        """Notify all watchers of service changes."""
        if service_name in self.watchers:
            instances = await self.discover_services(service_name)
            for callback in self.watchers[service_name]:
                try:
                    callback(instances)
                except Exception as e:
                    print(f"Error notifying watcher: {e}")

class KubernetesServiceDiscovery(ServiceDiscoveryProvider):
    """Kubernetes-based service discovery using endpoints."""
    
    def __init__(self, namespace: str = "default"):
        self.namespace = namespace
        # In production, this would use kubernetes client library
        self.services: Dict[str, Dict[str, ServiceInstance]] = {}
        self.watchers: Dict[str, List[Callable]] = {}
    
    async def register_service(self, service_name: str, instance: ServiceInstance):
        """Register service (typically handled by k8s automatically)."""
        if service_name not in self.services:
            self.services[service_name] = {}
        
        self.services[service_name][instance.id] = instance
        await self._notify_watchers(service_name)
    
    async def deregister_service(self, service_name: str, instance_id: str):
        """Deregister service (typically handled by k8s automatically)."""
        if service_name in self.services:
            self.services[service_name].pop(instance_id, None)
        
        await self._notify_watchers(service_name)
    
    async def discover_services(self, service_name: str) -> List[ServiceInstance]:
        """Discover service instances from Kubernetes endpoints."""
        # In production, this would query k8s API for endpoints
        instances = self.services.get(service_name, {})
        return list(instances.values())
    
    async def watch_service(self, service_name: str, 
                          callback: Callable[[List[ServiceInstance]], None]):
        """Watch service endpoints using Kubernetes watch API."""
        if service_name not in self.watchers:
            self.watchers[service_name] = []
        
        self.watchers[service_name].append(callback)
        
        # Send initial state
        instances = await self.discover_services(service_name)
        callback(instances)
    
    async def _notify_watchers(self, service_name: str):
        """Notify watchers of service changes."""
        if service_name in self.watchers:
            instances = await self.discover_services(service_name)
            for callback in self.watchers[service_name]:
                try:
                    callback(instances)
                except Exception as e:
                    print(f"Error notifying watcher: {e}")

# Load balancer with service discovery integration
class ServiceDiscoveryLoadBalancer:
    """
    Load balancer that automatically discovers and manages backend servers
    using service discovery.
    """
    
    def __init__(self, service_name: str, discovery_provider: ServiceDiscoveryProvider):
        self.service_name = service_name
        self.discovery = discovery_provider
        self.current_instances: List[ServiceInstance] = []
        self.current_index = 0
        
        # Health checking
        self.health_checker = ActiveHealthChecker()
        
        # Start service watching
        asyncio.create_task(self._start_service_watching())
    
    async def _start_service_watching(self):
        """Start watching for service changes."""
        await self.discovery.watch_service(
            self.service_name, 
            self._on_service_change
        )
        
        await self.health_checker.start()
    
    def _on_service_change(self, instances: List[ServiceInstance]):
        """Handle service instance changes."""
        print(f"Service {self.service_name} instances updated: {len(instances)} instances")
        
        # Update instance list
        old_instances = {inst.id: inst for inst in self.current_instances}
        new_instances = {inst.id: inst for inst in instances}
        
        # Remove instances that are no longer available
        for instance_id in old_instances:
            if instance_id not in new_instances:
                asyncio.create_task(
                    self.health_checker.remove_server(instance_id)
                )
                print(f"Removed instance {instance_id}")
        
        # Add new instances
        for instance_id, instance in new_instances.items():
            if instance_id not in old_instances:
                asyncio.create_task(
                    self._add_instance_to_health_checker(instance)
                )
                print(f"Added instance {instance_id}")
        
        self.current_instances = instances
    
    async def _add_instance_to_health_checker(self, instance: ServiceInstance):
        """Add instance to health checker."""
        health_url = instance.health_check_url
        if not health_url:
            # Create default health check URL
            health_url = f"http://{instance.host}:{instance.port}/health"
        
        await self.health_checker.add_server(
            instance.id,
            health_url
        )
    
    def get_server(self) -> Optional[ServiceInstance]:
        """Get next available healthy server."""
        healthy_servers = self.health_checker.get_healthy_servers()
        
        if not healthy_servers:
            return None
        
        # Simple round-robin among healthy servers
        healthy_instances = [
            inst for inst in self.current_instances 
            if inst.id in healthy_servers
        ]
        
        if not healthy_instances:
            return None
        
        instance = healthy_instances[self.current_index % len(healthy_instances)]
        self.current_index += 1
        
        return instance
    
    def get_server_by_tags(self, required_tags: List[str]) -> Optional[ServiceInstance]:
        """Get server that matches specific tags."""
        healthy_servers = self.health_checker.get_healthy_servers()
        
        candidates = []
        for instance in self.current_instances:
            if (instance.id in healthy_servers and 
                all(tag in instance.tags for tag in required_tags)):
                candidates.append(instance)
        
        if not candidates:
            return None
        
        return candidates[self.current_index % len(candidates)]
    
    def get_metrics(self) -> Dict:
        """Get load balancer and health metrics."""
        health_metrics = self.health_checker.get_server_metrics()
        
        return {
            'service_name': self.service_name,
            'total_instances': len(self.current_instances),
            'healthy_instances': len(self.health_checker.get_healthy_servers()),
            'instance_details': [
                {
                    'id': inst.id,
                    'host': inst.host,
                    'port': inst.port,
                    'tags': inst.tags,
                    'metadata': inst.metadata,
                    'health': health_metrics.get(inst.id, {})
                }
                for inst in self.current_instances
            ]
        }

# Example configuration and usage
async def demo_service_discovery():
    """Demonstrate service discovery integration."""
    
    # Create service discovery provider
    consul = ConsulServiceDiscovery()
    
    # Register some services
    api_service_1 = ServiceInstance(
        id="api-1",
        host="10.0.1.10",
        port=8080,
        health_check_url="http://10.0.1.10:8080/health",
        tags=["api", "v1", "production"],
        metadata={"version": "1.2.3", "region": "us-east-1"}
    )
    
    api_service_2 = ServiceInstance(
        id="api-2",
        host="10.0.1.11",
        port=8080,
        health_check_url="http://10.0.1.11:8080/health",
        tags=["api", "v1", "production"],
        metadata={"version": "1.2.3", "region": "us-east-1"}
    )
    
    await consul.register_service("user-api", api_service_1)
    await consul.register_service("user-api", api_service_2)
    
    # Create load balancer with service discovery
    lb = ServiceDiscoveryLoadBalancer("user-api", consul)
    
    # Give some time for service discovery
    await asyncio.sleep(2)
    
    # Get servers
    for i in range(10):
        server = lb.get_server()
        if server:
            print(f"Request {i+1} -> {server.host}:{server.port}")
        else:
            print(f"Request {i+1} -> No available servers")
    
    # Get metrics
    metrics = lb.get_metrics()
    print(f"\nLoad balancer metrics:")
    print(json.dumps(metrics, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(demo_service_discovery())
```

---

## 3.5 Automated Failover Strategies

### 3.5.1 Multi-layer Failover

```python
# Automated failover implementation
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable
import asyncio
import time

class FailoverStrategy(Enum):
    IMMEDIATE = "immediate"           # Fail immediately to backup
    RETRY_THEN_FAILOVER = "retry"    # Retry N times then failover
    CIRCUIT_BREAKER = "circuit"      # Use circuit breaker logic
    GRACEFUL_DEGRADATION = "graceful" # Reduce load before failover

@dataclass
class FailoverConfig:
    strategy: FailoverStrategy = FailoverStrategy.RETRY_THEN_FAILOVER
    retry_count: int = 3
    retry_delay: float = 1.0
    backup_servers: List[str] = None
    degradation_threshold: float = 0.8  # 80% failure rate triggers degradation
    recovery_time: int = 300  # Seconds to wait before trying primary again

class AutomatedFailoverManager:
    """
    Comprehensive failover manager supporting multiple strategies
    and automated recovery.
    """
    
    def __init__(self, config: FailoverConfig = None):
        self.config = config or FailoverConfig()
        self.primary_servers: List[str] = []
        self.backup_servers: List[str] = self.config.backup_servers or []
        
        # State tracking
        self.failed_servers: Set[str] = set()
        self.degraded_servers: Set[str] = set()
        self.server_metrics: Dict[str, Dict] = {}
        
        # Circuit breakers for each server
        self.circuit_breakers = CircuitBreakerManager()
        
        # Recovery tasks
        self.recovery_tasks: Dict[str, asyncio.Task] = {}
    
    def set_primary_servers(self, servers: List[str]):
        """Set the list of primary servers."""
        self.primary_servers = servers
        
        # Initialize metrics for all servers
        for server in servers:
            if server not in self.server_metrics:
                self.server_metrics[server] = {
                    'total_requests': 0,
                    'failed_requests': 0,
                    'last_failure_time': 0,
                    'consecutive_failures': 0,
                    'is_degraded': False
                }
    
    def add_backup_servers(self, servers: List[str]):
        """Add backup servers."""
        self.backup_servers.extend(servers)
    
    async def execute_request(self, request_func: Callable, *args, **kwargs):
        """
        Execute a request with automated failover logic.
        """
        # Try primary servers first
        for server in self._get_available_primary_servers():
            try:
                if self.config.strategy == FailoverStrategy.CIRCUIT_BREAKER:
                    return await self._execute_with_circuit_breaker(
                        server, request_func, *args, **kwargs
                    )
                elif self.config.strategy == FailoverStrategy.RETRY_THEN_FAILOVER:
                    return await self._execute_with_retries(
                        server, request_func, *args, **kwargs
                    )
                elif self.config.strategy == FailoverStrategy.GRACEFUL_DEGRADATION:
                    return await self._execute_with_degradation(
                        server, request_func, *args, **kwargs
                    )
                else:  # IMMEDIATE
                    return await self._execute_immediate(
                        server, request_func, *args, **kwargs
                    )
                    
            except Exception as e:
                await self._handle_server_failure(server, e)
                continue
        
        # Try backup servers
        for server in self.backup_servers:
            if server not in self.failed_servers:
                try:
                    return await self._execute_immediate(
                        server, request_func, *args, **kwargs
                    )
                except Exception as e:
                    await self._handle_server_failure(server, e)
                    continue
        
        # All servers failed
        raise Exception("All primary and backup servers unavailable")
    
    async def _execute_with_circuit_breaker(self, server: str, request_func: Callable, 
                                          *args, **kwargs):
        """Execute request using circuit breaker pattern."""
        return await self.circuit_breakers.call_with_circuit_breaker(
            server, request_func, *args, **kwargs
        )
    
    async def _execute_with_retries(self, server: str, request_func: Callable, 
                                  *args, **kwargs):
        """Execute request with retry logic."""
        last_exception = None
        
        for attempt in range(self.config.retry_count + 1):
            try:
                return await request_func(server, *args, **kwargs)
            except Exception as e:
                last_exception = e
                await self._record_request_failure(server)
                
                if attempt < self.config.retry_count:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                else:
                    raise last_exception
    
    async def _execute_with_degradation(self, server: str, request_func: Callable, 
                                       *args, **kwargs):
        """Execute request with graceful degradation."""
        metrics = self.server_metrics.get(server, {})
        
        # Check if server should be degraded
        if self._should_degrade_server(server):
            if server not in self.degraded_servers:
                self.degraded_servers.add(server)
                print(f"Server {server} degraded due to high failure rate")
            
            # Reduce load on degraded server (implement load reduction logic)
            await asyncio.sleep(0.1)  # Simulate load reduction
        
        return await request_func(server, *args, **kwargs)
    
    async def _execute_immediate(self, server: str, request_func: Callable, 
                               *args, **kwargs):
        """Execute request with immediate failover on failure."""
        result = await request_func(server, *args, **kwargs)
        await self._record_request_success(server)
        return result
    
    def _get_available_primary_servers(self) -> List[str]:
        """Get list of available primary servers."""
        return [s for s in self.primary_servers if s not in self.failed_servers]
    
    def _should_degrade_server(self, server: str) -> bool:
        """Check if server should be degraded based on metrics."""
        metrics = self.server_metrics.get(server, {})
        total_requests = metrics.get('total_requests', 0)
        
        if total_requests < 10:  # Not enough data
            return False
        
        failed_requests = metrics.get('failed_requests', 0)
        failure_rate = failed_requests / total_requests
        
        return failure_rate >= self.config.degradation_threshold
    
    async def _handle_server_failure(self, server: str, exception: Exception):
        """Handle server failure and initiate recovery if needed."""
        await self._record_request_failure(server)
        
        metrics = self.server_metrics[server]
        metrics['consecutive_failures'] += 1
        
        # Mark server as failed if too many consecutive failures
        if metrics['consecutive_failures'] >= 3:
            self.failed_servers.add(server)
            print(f"Server {server} marked as failed: {exception}")
            
            # Start recovery task
            await self._start_recovery_task(server)
    
    async def _record_request_success(self, server: str):
        """Record a successful request."""
        metrics = self.server_metrics[server]
        metrics['total_requests'] += 1
        metrics['consecutive_failures'] = 0
        
        # Remove from degraded if it was degraded
        if server in self.degraded_servers:
            self.degraded_servers.discard(server)
    
    async def _record_request_failure(self, server: str):
        """Record a failed request."""
        metrics = self.server_metrics[server]
        metrics['total_requests'] += 1
        metrics['failed_requests'] += 1
        metrics['last_failure_time'] = time.time()
    
    async def _start_recovery_task(self, server: str):
        """Start automated recovery task for failed server."""
        if server in self.recovery_tasks:
            return  # Recovery already in progress
        
        self.recovery_tasks[server] = asyncio.create_task(
            self._recovery_loop(server)
        )
    
    async def _recovery_loop(self, server: str):
        """Recovery loop for failed server."""
        while server in self.failed_servers:
            await asyncio.sleep(self.config.recovery_time)
            
            try:
                # Test server health
                if await self._test_server_health(server):
                    self.failed_servers.discard(server)
                    self.degraded_servers.discard(server)
                    
                    # Reset metrics
                    metrics = self.server_metrics[server]
                    metrics['consecutive_failures'] = 0
                    
                    print(f"Server {server} recovered and back in rotation")
                    break
                    
            except Exception as e:
                print(f"Server {server} still unhealthy: {e}")
        
        # Clean up recovery task
        self.recovery_tasks.pop(server, None)
    
    async def _test_server_health(self, server: str) -> bool:
        """Test if server is healthy."""
        # Implement actual health check logic
        # For demo, we'll simulate a health check
        await asyncio.sleep(0.1)
        return True  # Assume server recovered
    
    def get_failover_metrics(self) -> Dict:
        """Get comprehensive failover metrics."""
        return {
            'primary_servers': self.primary_servers,
            'backup_servers': self.backup_servers,
            'failed_servers': list(self.failed_servers),
            'degraded_servers': list(self.degraded_servers),
            'server_metrics': self.server_metrics,
            'active_recovery_tasks': list(self.recovery_tasks.keys()),
            'circuit_breaker_metrics': self.circuit_breakers.get_all_metrics()
        }

# Integration with load balancer
class FailoverAwareLoadBalancer:
    """Load balancer with integrated automated failover."""
    
    def __init__(self, primary_servers: List[str], backup_servers: List[str] = None):
        self.failover_manager = AutomatedFailoverManager(
            FailoverConfig(
                strategy=FailoverStrategy.CIRCUIT_BREAKER,
                backup_servers=backup_servers or []
            )
        )
        self.failover_manager.set_primary_servers(primary_servers)
    
    async def make_request(self, request_data: Dict) -> Dict:
        """Make a request with automatic failover."""
        
        def request_func(server: str, data: Dict) -> Dict:
            # Simulate request to server
            print(f"Making request to {server}")
            
            # Simulate occasional failures for demo
            import random
            if random.random() < 0.1:  # 10% failure rate
                raise Exception(f"Simulated failure on {server}")
            
            return {"server": server, "response": "success", "data": data}
        
        return await self.failover_manager.execute_request(
            request_func, request_data
        )
    
    def get_status(self) -> Dict:
        """Get load balancer status."""
        return self.failover_manager.get_failover_metrics()

# Demo usage
async def demo_automated_failover():
    """Demonstrate automated failover capabilities."""
    
    lb = FailoverAwareLoadBalancer(
        primary_servers=["server1", "server2", "server3"],
        backup_servers=["backup1", "backup2"]
    )
    
    # Make requests to see failover in action
    for i in range(20):
        try:
            result = await lb.make_request({"request_id": i})
            print(f"Request {i}: {result}")
        except Exception as e:
            print(f"Request {i} failed: {e}")
        
        await asyncio.sleep(1)
    
    # Print final status
    print("\nFinal Status:")
    print(json.dumps(lb.get_status(), indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(demo_automated_failover())
```

---

## Module Assessment

### Practical Exercise

**Scenario**: Design a health checking and service discovery system for a microservices platform with:
- 50+ microservices
- Services deployed across multiple regions
- Kubernetes orchestration
- Need for zero-downtime deployments

**Deliverables**:
1. Health check strategy for different service types
2. Service discovery architecture
3. Circuit breaker configuration
4. Automated failover implementation
5. Monitoring and alerting strategy

### Knowledge Check

1. **Compare active vs passive health checks**: When would you use each approach?

2. **Circuit breaker tuning**: How would you determine optimal thresholds for a high-traffic API?

3. **Service discovery**: Compare the trade-offs between push-based and pull-based service discovery.

4. **Failover strategies**: Design a multi-region failover strategy for a global application.

---

## Next Module Preview
**Module 4: Advanced Load Balancer Features**
- SSL termination and end-to-end encryption
- Rate limiting and traffic shaping
- Request routing and content-based load balancing
- WebSocket and long-lived connection handling

---

## Key Takeaways

1. **Health checks are critical** for maintaining service availability and user experience
2. **Active and passive approaches** each have their place in a comprehensive monitoring strategy
3. **Circuit breakers** prevent cascading failures and enable graceful degradation
4. **Service discovery** enables dynamic, cloud-native architectures
5. **Automated failover** reduces MTTR and improves system resilience

These concepts form the foundation for building truly resilient distributed systems that can handle real-world failure scenarios gracefully.