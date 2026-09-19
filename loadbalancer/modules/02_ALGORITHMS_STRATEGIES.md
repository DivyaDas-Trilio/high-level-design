# Module 2: Load Balancing Algorithms & Strategies
## Mastering Traffic Distribution Logic for Optimal Performance

### Learning Objectives
- Understand core load balancing algorithms and their trade-offs
- Implement consistent hashing for stateful services
- Design session affinity mechanisms
- Choose optimal algorithms for specific use cases
- Implement custom load balancing logic

---

## 2.1 Core Load Balancing Algorithms

### 2.1.1 Round Robin

**Mechanism**: Distributes requests sequentially across servers in rotation.

```python
class RoundRobinBalancer:
    def __init__(self, servers):
        self.servers = servers
        self.current = 0
    
    def get_server(self):
        server = self.servers[self.current]
        self.current = (self.current + 1) % len(self.servers)
        return server
```

#### Characteristics:
- **Simplicity**: Easy to implement and understand
- **Fairness**: Equal distribution over time
- **Stateless**: No server performance consideration

#### Best Use Cases:
- ✅ Homogeneous servers with identical capacity
- ✅ Stateless applications
- ✅ Predictable, uniform request processing time

#### Limitations:
- ❌ Ignores server capacity differences
- ❌ No consideration for current load
- ❌ Poor performance with heterogeneous servers

### 2.1.2 Weighted Round Robin

**Mechanism**: Assigns weights to servers based on capacity, distributing requests proportionally.

```python
class WeightedRoundRobinBalancer:
    def __init__(self, servers_with_weights):
        self.servers = []
        for server, weight in servers_with_weights:
            self.servers.extend([server] * weight)
        self.current = 0
    
    def get_server(self):
        server = self.servers[self.current]
        self.current = (self.current + 1) % len(self.servers)
        return server
```

#### Configuration Example:
```yaml
servers:
  - server1: weight=3  # High-performance server
  - server2: weight=2  # Medium-performance server  
  - server3: weight=1  # Lower-performance server
```

#### Best Use Cases:
- ✅ Heterogeneous server hardware
- ✅ Known server capacity differences
- ✅ Cost optimization (balance load vs. server costs)

### 2.1.3 Least Connections

**Mechanism**: Routes requests to server with fewest active connections.

```python
class LeastConnectionsBalancer:
    def __init__(self, servers):
        self.servers = {server: 0 for server in servers}
    
    def get_server(self):
        return min(self.servers, key=self.servers.get)
    
    def connection_opened(self, server):
        self.servers[server] += 1
    
    def connection_closed(self, server):
        self.servers[server] -= 1
```

#### Characteristics:
- **Dynamic**: Adapts to real-time server load
- **Stateful**: Requires connection tracking
- **Responsive**: Handles varying request processing times

#### Best Use Cases:
- ✅ Variable request processing time
- ✅ Long-lived connections
- ✅ Real-time applications (chat, gaming)

#### Implementation Considerations:
```python
# Production implementation with thread safety
import threading

class ThreadSafeLeastConnections:
    def __init__(self, servers):
        self.servers = {server: 0 for server in servers}
        self.lock = threading.Lock()
    
    def get_server(self):
        with self.lock:
            return min(self.servers, key=self.servers.get)
    
    def update_connection(self, server, delta):
        with self.lock:
            self.servers[server] += delta
```

### 2.1.4 Weighted Least Connections

**Mechanism**: Combines least connections with server weights.

```python
class WeightedLeastConnectionsBalancer:
    def __init__(self, servers_with_weights):
        self.servers = {}
        for server, weight in servers_with_weights:
            self.servers[server] = {'weight': weight, 'connections': 0}
    
    def get_server(self):
        def score(server_info):
            return server_info['connections'] / server_info['weight']
        
        return min(self.servers, key=lambda s: score(self.servers[s]))
```

---

## 2.2 Hash-based Algorithms

### 2.2.1 IP Hash

**Mechanism**: Hash client IP to consistently route to same server.

```python
import hashlib

class IPHashBalancer:
    def __init__(self, servers):
        self.servers = servers
    
    def get_server(self, client_ip):
        hash_value = int(hashlib.md5(client_ip.encode()).hexdigest(), 16)
        return self.servers[hash_value % len(self.servers)]
```

#### Best Use Cases:
- ✅ Session affinity requirements
- ✅ Caching optimization
- ✅ Stateful applications

#### Limitations:
- ❌ Uneven distribution with limited client IPs
- ❌ Poor performance when servers added/removed
- ❌ NAT/proxy scenarios create hotspots

### 2.2.2 Consistent Hashing

**Mechanism**: Maps both clients and servers to points on a hash ring, ensuring minimal redistribution when topology changes.

```python
import hashlib
import bisect

class ConsistentHashBalancer:
    def __init__(self, servers, replicas=150):
        self.replicas = replicas
        self.ring = {}
        self.sorted_keys = []
        
        for server in servers:
            self.add_server(server)
    
    def _hash(self, key):
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
    
    def add_server(self, server):
        for i in range(self.replicas):
            key = self._hash(f"{server}:{i}")
            self.ring[key] = server
            bisect.insort(self.sorted_keys, key)
    
    def remove_server(self, server):
        for i in range(self.replicas):
            key = self._hash(f"{server}:{i}")
            del self.ring[key]
            self.sorted_keys.remove(key)
    
    def get_server(self, key):
        if not self.ring:
            return None
        
        hash_value = self._hash(str(key))
        idx = bisect.bisect_right(self.sorted_keys, hash_value)
        
        # Wrap around to first server if beyond the end
        if idx == len(self.sorted_keys):
            idx = 0
        
        return self.ring[self.sorted_keys[idx]]
```

#### Advantages of Consistent Hashing:
1. **Minimal Redistribution**: Only ~1/n keys move when adding/removing servers
2. **Hotspot Mitigation**: Virtual nodes (replicas) ensure even distribution
3. **Scalability**: Efficient addition/removal of nodes

#### Real-world Example - Redis Cluster:
```python
class RedisConsistentHash:
    def __init__(self, redis_nodes):
        self.hash_ring = ConsistentHashBalancer(redis_nodes, replicas=160)
    
    def get_redis_node(self, key):
        return self.hash_ring.get_server(key)
    
    def set(self, key, value):
        node = self.get_redis_node(key)
        return node.set(key, value)
    
    def get(self, key):
        node = self.get_redis_node(key)
        return node.get(key)
```

---

## 2.3 Advanced Algorithms

### 2.3.1 Least Response Time

**Mechanism**: Routes to server with fastest average response time.

```python
import time
from collections import defaultdict, deque

class LeastResponseTimeBalancer:
    def __init__(self, servers, window_size=100):
        self.servers = servers
        self.response_times = {server: deque(maxlen=window_size) 
                             for server in servers}
        self.active_requests = defaultdict(dict)  # {server: {request_id: start_time}}
    
    def get_server(self):
        def avg_response_time(server):
            times = self.response_times[server]
            return sum(times) / len(times) if times else float('inf')
        
        return min(self.servers, key=avg_response_time)
    
    def start_request(self, server, request_id):
        self.active_requests[server][request_id] = time.time()
    
    def end_request(self, server, request_id):
        start_time = self.active_requests[server].pop(request_id, None)
        if start_time:
            response_time = time.time() - start_time
            self.response_times[server].append(response_time)
```

### 2.3.2 Resource-based Load Balancing

**Mechanism**: Routes based on real-time server resource utilization.

```python
import psutil

class ResourceBasedBalancer:
    def __init__(self, servers):
        self.servers = servers
    
    def get_server_load(self, server):
        # This would typically be retrieved via monitoring system
        # For demo, using local system metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory_percent = psutil.virtual_memory().percent
        
        # Composite load score (0-100, lower is better)
        return (cpu_percent * 0.7) + (memory_percent * 0.3)
    
    def get_server(self):
        server_loads = {server: self.get_server_load(server) 
                       for server in self.servers}
        return min(server_loads, key=server_loads.get)
```

### 2.3.3 Geographic Load Balancing

**Mechanism**: Routes traffic based on client geographic location.

```python
import geoip2.database

class GeographicBalancer:
    def __init__(self, region_servers):
        self.region_servers = region_servers  # {'us-east': [...], 'eu-west': [...]}
        self.geoip_reader = geoip2.database.Reader('GeoLite2-City.mmdb')
    
    def get_region(self, client_ip):
        try:
            response = self.geoip_reader.city(client_ip)
            continent = response.continent.code
            country = response.country.iso_code
            
            # Route to appropriate region
            if continent == 'NA':
                return 'us-east' if country == 'US' else 'us-west'
            elif continent == 'EU':
                return 'eu-west'
            elif continent == 'AS':
                return 'ap-southeast'
            else:
                return 'us-east'  # default
        except:
            return 'us-east'  # fallback
    
    def get_server(self, client_ip):
        region = self.get_region(client_ip)
        servers = self.region_servers.get(region, self.region_servers['us-east'])
        
        # Use round-robin within region
        return RoundRobinBalancer(servers).get_server()
```

---

## 2.4 Session Affinity & Sticky Sessions

### 2.4.1 Cookie-based Affinity

```nginx
# Nginx configuration for sticky sessions
upstream backend {
    ip_hash;  # Simple IP-based affinity
    server 192.168.1.10:8080;
    server 192.168.1.11:8080;
    server 192.168.1.12:8080;
}

# More advanced cookie-based stickiness
upstream backend_sticky {
    hash $cookie_sessionid consistent;
    server 192.168.1.10:8080;
    server 192.168.1.11:8080;
    server 192.168.1.12:8080;
}
```

### 2.4.2 Application-controlled Session Management

```python
class SessionAwareBalancer:
    def __init__(self, servers):
        self.servers = servers
        self.session_map = {}  # {session_id: server}
        self.base_balancer = RoundRobinBalancer(servers)
    
    def get_server(self, session_id=None):
        if session_id and session_id in self.session_map:
            return self.session_map[session_id]
        
        # New session - assign to least loaded server
        server = self.base_balancer.get_server()
        if session_id:
            self.session_map[session_id] = server
        
        return server
    
    def remove_session(self, session_id):
        self.session_map.pop(session_id, None)
```

---

## 2.5 Algorithm Selection Framework

### Decision Matrix

| Algorithm | Consistency | Performance | Complexity | Best For |
|-----------|-------------|-------------|------------|----------|
| Round Robin | Medium | High | Low | Homogeneous servers |
| Weighted RR | Medium | High | Low | Heterogeneous capacity |
| Least Connections | High | Medium | Medium | Variable processing time |
| Consistent Hash | Very High | Medium | High | Caching, stateful services |
| Resource-based | Very High | Low | Very High | Dynamic environments |
| Geographic | High | Medium | Medium | Global applications |

### Performance Characteristics

```python
# Benchmark different algorithms
import time
import random
from concurrent.futures import ThreadPoolExecutor

class LoadBalancerBenchmark:
    def __init__(self):
        self.servers = ['server1', 'server2', 'server3', 'server4']
    
    def benchmark_algorithm(self, balancer, num_requests=10000):
        start_time = time.time()
        
        def make_request():
            server = balancer.get_server()
            # Simulate request processing
            time.sleep(random.uniform(0.001, 0.01))
            return server
        
        with ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(lambda _: make_request(), 
                                      range(num_requests)))
        
        end_time = time.time()
        
        # Calculate distribution
        distribution = {}
        for server in results:
            distribution[server] = distribution.get(server, 0) + 1
        
        return {
            'duration': end_time - start_time,
            'requests_per_second': num_requests / (end_time - start_time),
            'distribution': distribution
        }
```

---

## 2.6 Real-world Implementation Patterns

### 2.6.1 Multi-tier Load Balancing

```python
class MultiTierBalancer:
    def __init__(self):
        # Global tier: Geographic distribution
        self.global_tier = GeographicBalancer({
            'us-east': ['us-east-lb1', 'us-east-lb2'],
            'eu-west': ['eu-west-lb1', 'eu-west-lb2']
        })
        
        # Regional tier: Application-specific routing
        self.regional_tiers = {
            'us-east-lb1': {
                'api': WeightedRoundRobinBalancer([('api-1', 3), ('api-2', 2)]),
                'web': RoundRobinBalancer(['web-1', 'web-2', 'web-3'])
            }
        }
    
    def route_request(self, client_ip, service_type):
        # Step 1: Geographic routing
        regional_lb = self.global_tier.get_server(client_ip)
        
        # Step 2: Service-specific routing
        service_balancer = self.regional_tiers[regional_lb][service_type]
        
        # Step 3: Final server selection
        return service_balancer.get_server()
```

### 2.6.2 Adaptive Load Balancing

```python
class AdaptiveBalancer:
    def __init__(self, servers):
        self.algorithms = {
            'round_robin': RoundRobinBalancer(servers),
            'least_connections': LeastConnectionsBalancer(servers),
            'resource_based': ResourceBasedBalancer(servers)
        }
        self.current_algorithm = 'round_robin'
        self.performance_metrics = defaultdict(list)
    
    def adapt_algorithm(self):
        # Switch algorithm based on performance metrics
        if self.avg_response_time() > 200:  # ms
            self.current_algorithm = 'least_connections'
        elif self.cpu_utilization() > 80:  # %
            self.current_algorithm = 'resource_based'
        else:
            self.current_algorithm = 'round_robin'
    
    def get_server(self):
        self.adapt_algorithm()
        return self.algorithms[self.current_algorithm].get_server()
```

---

## 2.7 Common Pitfalls and Solutions

### ❌ Pitfall: Hash Ring Imbalance
**Problem**: Poor key distribution causes hotspots
**Solution**: Increase virtual nodes (replicas)

```python
# Bad: Too few replicas
balancer = ConsistentHashBalancer(servers, replicas=3)

# Good: Sufficient replicas for even distribution
balancer = ConsistentHashBalancer(servers, replicas=150)
```

### ❌ Pitfall: Thundering Herd
**Problem**: All connections go to newly added server
**Solution**: Gradual traffic ramp-up

```python
class GradualRampBalancer:
    def __init__(self, servers):
        self.servers = {}
        for server in servers:
            self.servers[server] = {'weight': 1.0, 'ramp_factor': 1.0}
    
    def add_server(self, server, ramp_duration=300):  # 5 minutes
        self.servers[server] = {
            'weight': 1.0,
            'ramp_factor': 0.1,  # Start with 10% traffic
            'ramp_start': time.time(),
            'ramp_duration': ramp_duration
        }
    
    def update_ramp_factors(self):
        current_time = time.time()
        for server, config in self.servers.items():
            if 'ramp_start' in config:
                elapsed = current_time - config['ramp_start']
                if elapsed < config['ramp_duration']:
                    config['ramp_factor'] = 0.1 + 0.9 * (elapsed / config['ramp_duration'])
                else:
                    config['ramp_factor'] = 1.0
                    del config['ramp_start']
```

### ❌ Pitfall: Session Affinity Brittleness
**Problem**: Server failure breaks all sessions
**Solution**: Implement session replication or external session store

```python
class ResilientSessionBalancer:
    def __init__(self, servers, session_store):
        self.servers = servers
        self.session_store = session_store  # Redis, database, etc.
        self.primary_balancer = ConsistentHashBalancer(servers)
        self.backup_balancer = RoundRobinBalancer(servers)
    
    def get_server(self, session_id):
        # Try primary server assignment
        primary_server = self.primary_balancer.get_server(session_id)
        
        if self.is_server_healthy(primary_server):
            return primary_server
        
        # Fallback to backup assignment and migrate session
        backup_server = self.backup_balancer.get_server()
        self.migrate_session(session_id, primary_server, backup_server)
        return backup_server
```

---

## Lab Exercise: Implementing Consistent Hashing

### Objective
Build a production-ready consistent hashing implementation with virtual nodes and test its distribution properties.

### Requirements
1. Implement consistent hashing with configurable virtual nodes
2. Support dynamic server addition/removal
3. Measure key redistribution when topology changes
4. Compare with simple hash-based distribution

### Lab Steps
See [../labs/lab02_consistent_hashing.md](../labs/lab02_consistent_hashing.md)

---

## Module Assessment

### Scenario-based Questions

1. **E-commerce Platform**: You're designing load balancing for an e-commerce site with:
   - Shopping cart sessions that must be maintained
   - Product catalog that's heavily cached
   - Search API with variable processing times
   - Payment processing requiring PCI compliance
   
   Which algorithms would you use for each service and why?

2. **Gaming Platform**: Design load balancing for a real-time multiplayer game with:
   - 100K concurrent players
   - Room-based gameplay (players must stay in same room)
   - Global player base across 5 continents
   - Frequent server deployments
   
   Propose a complete load balancing strategy.

3. **Microservices Migration**: Your company is migrating from a monolith to microservices:
   - 50 different services with varying resource requirements
   - Legacy services with session state
   - New services designed to be stateless
   - Need gradual migration strategy
   
   Design a load balancing evolution plan.

### Practical Implementation
Build a load balancer simulator that:
- Implements 5 different algorithms
- Simulates server failures and recoveries
- Measures performance under different load patterns
- Provides real-time metrics dashboard

---

## Next Module Preview
**Module 3: Health Checks & Service Discovery**
- Active vs passive health monitoring
- Circuit breaker patterns
- Integration with service discovery systems
- Automated failover strategies

---

## Advanced Reading

### Research Papers
- "Consistent Hashing and Random Trees" (Karger et al., 1997)
- "The Power of Two Choices in Randomized Load Balancing" (Azar et al., 1999)
- "Join-Idle-Queue: A Novel Load Balancing Algorithm" (Lu et al., 2011)

### Industry Case Studies
- [Discord: How We Scaled Our Load Balancer to Handle 2.8 Million Concurrent Voice Users](https://blog.discord.com/how-discord-handles-two-and-half-million-concurrent-voice-users-using-webrtc-ce01c3187429)
- [Uber: Introducing Domain-Oriented Microservice Architecture](https://eng.uber.com/microservice-architecture/)
- [Netflix: Zuul - Gateway Service](https://netflixtechblog.com/zuul-2-the-netflix-journey-to-asynchronous-non-blocking-systems-45947377fb5c)

### Open Source Implementations
- [HAProxy - The Reliable, High Performance TCP/HTTP Load Balancer](https://www.haproxy.org/)
- [Envoy Proxy - Cloud Native High-Performance Edge/Middle/Service Proxy](https://www.envoyproxy.io/)
- [Kong - Cloud Connectivity Platform](https://konghq.com/)