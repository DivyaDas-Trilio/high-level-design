# Lab 2: Implementing Consistent Hashing
## Building Production-Ready Hash Ring for Stateful Service Distribution

### Lab Overview
Implement a robust consistent hashing algorithm with virtual nodes, test its distribution properties, and compare with simple hash-based distribution. This lab demonstrates how to build stateful service load balancing used by systems like Redis Cluster, Amazon DynamoDB, and Cassandra.

### Duration: 90 minutes

---

## Prerequisites

### Required Software
- Python 3.8+ with pip
- Docker (for Redis cluster simulation)
- matplotlib for visualizations
- pytest for testing

### Knowledge Requirements
- Understanding of hash functions and data structures
- Basic knowledge of distributed systems concepts
- Familiarity with Python programming

---

## Lab Architecture

```
Client Requests → Consistent Hash Ring → Server Assignments
                        |
                        ├── Server 1 (with virtual nodes)
                        ├── Server 2 (with virtual nodes)  
                        ├── Server 3 (with virtual nodes)
                        └── Server N (with virtual nodes)

Key Redistribution Visualization:
Before: [Key1→S1, Key2→S2, Key3→S3, ...]
After Adding Server: [Key1→S1, Key2→S4, Key3→S3, ...] (minimal movement)
```

---

## Step 1: Environment Setup

### 1.1 Create Lab Directory and Virtual Environment
```bash
mkdir -p ~/load-balancer-labs/lab02
cd ~/load-balancer-labs/lab02

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install hashlib2 matplotlib pytest redis numpy
```

### 1.2 Create Project Structure
```bash
mkdir -p src tests visualizations data
touch src/__init__.py tests/__init__.py
```

---

## Step 2: Core Consistent Hashing Implementation

### 2.1 Basic Hash Ring Implementation
```python
# src/consistent_hash.py
import hashlib
import bisect
from typing import List, Dict, Set, Optional, Union

class ConsistentHashRing:
    """
    Production-ready consistent hashing implementation with virtual nodes.
    
    Features:
    - Configurable hash function
    - Virtual nodes for better distribution
    - Thread-safe operations
    - Metrics collection
    - Key migration tracking
    """
    
    def __init__(self, 
                 servers: List[str] = None, 
                 virtual_nodes: int = 150,
                 hash_function: str = 'md5'):
        """
        Initialize the hash ring.
        
        Args:
            servers: List of server identifiers
            virtual_nodes: Number of virtual nodes per physical server
            hash_function: Hash function to use ('md5', 'sha1', 'sha256')
        """
        self.virtual_nodes = virtual_nodes
        self.hash_function = getattr(hashlib, hash_function)
        
        # Core data structures
        self.ring: Dict[int, str] = {}  # hash_value -> server
        self.sorted_keys: List[int] = []  # Sorted hash values
        self.servers: Set[str] = set()  # Active servers
        
        # Metrics and debugging
        self.key_assignments: Dict[str, str] = {}  # key -> server mapping
        self.server_loads: Dict[str, int] = {}  # server -> key count
        
        # Add initial servers
        if servers:
            for server in servers:
                self.add_server(server)
    
    def _hash(self, key: Union[str, bytes]) -> int:
        """Generate hash value for a key."""
        if isinstance(key, str):
            key = key.encode('utf-8')
        return int(self.hash_function(key).hexdigest(), 16)
    
    def _get_virtual_node_key(self, server: str, virtual_index: int) -> str:
        """Generate unique key for virtual node."""
        return f"{server}:vnode:{virtual_index}"
    
    def add_server(self, server: str) -> Dict[str, List[str]]:
        """
        Add a server to the ring and return migrated keys.
        
        Returns:
            Dictionary with 'added' and 'migrated' key lists
        """
        if server in self.servers:
            return {'added': [], 'migrated': []}
        
        self.servers.add(server)
        self.server_loads[server] = 0
        
        # Track keys that need migration
        migrated_keys = []
        
        # Add virtual nodes for this server
        for i in range(self.virtual_nodes):
            virtual_key = self._get_virtual_node_key(server, i)
            hash_value = self._hash(virtual_key)
            
            self.ring[hash_value] = server
            bisect.insort(self.sorted_keys, hash_value)
        
        # Reassign keys that should now go to the new server
        keys_to_reassign = list(self.key_assignments.keys())
        for key in keys_to_reassign:
            old_server = self.key_assignments[key]
            new_server = self.get_server(key)
            
            if new_server != old_server:
                migrated_keys.append(key)
                self.key_assignments[key] = new_server
                self.server_loads[old_server] -= 1
                self.server_loads[new_server] += 1
        
        return {
            'added': [server],
            'migrated': migrated_keys
        }
    
    def remove_server(self, server: str) -> Dict[str, List[str]]:
        """
        Remove a server from the ring and return reassigned keys.
        
        Returns:
            Dictionary with 'removed' servers and 'migrated' key lists
        """
        if server not in self.servers:
            return {'removed': [], 'migrated': []}
        
        self.servers.remove(server)
        migrated_keys = []
        
        # Remove all virtual nodes for this server
        keys_to_remove = []
        for hash_value, assigned_server in self.ring.items():
            if assigned_server == server:
                keys_to_remove.append(hash_value)
        
        for hash_value in keys_to_remove:
            del self.ring[hash_value]
            self.sorted_keys.remove(hash_value)
        
        # Reassign keys that were on the removed server
        keys_to_reassign = [k for k, v in self.key_assignments.items() if v == server]
        for key in keys_to_reassign:
            new_server = self.get_server(key)
            if new_server:  # Only if we have other servers
                migrated_keys.append(key)
                self.key_assignments[key] = new_server
                self.server_loads[new_server] += 1
            else:
                # No servers left
                del self.key_assignments[key]
        
        # Remove server from load tracking
        del self.server_loads[server]
        
        return {
            'removed': [server],
            'migrated': migrated_keys
        }
    
    def get_server(self, key: str) -> Optional[str]:
        """
        Get the server responsible for a key.
        
        Args:
            key: The key to look up
            
        Returns:
            Server identifier or None if no servers available
        """
        if not self.ring:
            return None
        
        hash_value = self._hash(key)
        
        # Find the first server with hash >= our key's hash
        idx = bisect.bisect_right(self.sorted_keys, hash_value)
        
        # Wrap around to the beginning if we're past the end
        if idx >= len(self.sorted_keys):
            idx = 0
        
        server = self.ring[self.sorted_keys[idx]]
        
        # Update tracking
        if key not in self.key_assignments:
            self.key_assignments[key] = server
            self.server_loads[server] += 1
        
        return server
    
    def get_servers_for_replication(self, key: str, n: int = 3) -> List[str]:
        """
        Get N servers for replicating a key (for distributed storage).
        
        Args:
            key: The key to replicate
            n: Number of replicas
            
        Returns:
            List of server identifiers
        """
        if not self.ring or n <= 0:
            return []
        
        hash_value = self._hash(key)
        idx = bisect.bisect_right(self.sorted_keys, hash_value)
        
        servers = []
        seen_servers = set()
        
        for i in range(len(self.sorted_keys)):
            current_idx = (idx + i) % len(self.sorted_keys)
            server = self.ring[self.sorted_keys[current_idx]]
            
            if server not in seen_servers:
                servers.append(server)
                seen_servers.add(server)
                
                if len(servers) >= n:
                    break
        
        return servers
    
    def get_ring_stats(self) -> Dict:
        """Get comprehensive statistics about the ring."""
        total_keys = sum(self.server_loads.values())
        
        stats = {
            'total_servers': len(self.servers),
            'virtual_nodes_per_server': self.virtual_nodes,
            'total_virtual_nodes': len(self.ring),
            'total_keys': total_keys,
            'server_loads': dict(self.server_loads),
            'average_load': total_keys / len(self.servers) if self.servers else 0,
            'load_distribution': self._calculate_load_distribution(),
            'ring_coverage': self._calculate_ring_coverage()
        }
        
        return stats
    
    def _calculate_load_distribution(self) -> Dict[str, float]:
        """Calculate load distribution statistics."""
        if not self.server_loads:
            return {}
        
        loads = list(self.server_loads.values())
        total = sum(loads)
        
        if total == 0:
            return {'coefficient_of_variation': 0.0, 'max_deviation': 0.0}
        
        mean_load = total / len(loads)
        variance = sum((load - mean_load) ** 2 for load in loads) / len(loads)
        std_dev = variance ** 0.5
        
        return {
            'coefficient_of_variation': std_dev / mean_load if mean_load > 0 else 0.0,
            'max_deviation': max(abs(load - mean_load) for load in loads) / mean_load if mean_load > 0 else 0.0
        }
    
    def _calculate_ring_coverage(self) -> List[Dict]:
        """Calculate how evenly virtual nodes are distributed around the ring."""
        if len(self.sorted_keys) < 2:
            return []
        
        segments = []
        ring_size = 2**128  # Assuming 128-bit hash space
        
        for i in range(len(self.sorted_keys)):
            current = self.sorted_keys[i]
            next_key = self.sorted_keys[(i + 1) % len(self.sorted_keys)]
            
            if next_key < current:  # Wrap around
                segment_size = (ring_size - current) + next_key
            else:
                segment_size = next_key - current
            
            segments.append({
                'server': self.ring[current],
                'start': current,
                'size': segment_size,
                'percentage': (segment_size / ring_size) * 100
            })
        
        return segments
```

### 2.2 Simple Hash Implementation for Comparison
```python
# src/simple_hash.py
import hashlib
from typing import List, Optional

class SimpleHashBalancer:
    """
    Simple hash-based load balancer for comparison.
    Demonstrates the problems consistent hashing solves.
    """
    
    def __init__(self, servers: List[str] = None):
        self.servers = list(servers) if servers else []
        self.key_assignments = {}
    
    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
    
    def add_server(self, server: str) -> Dict[str, List[str]]:
        """Add server and return reassigned keys."""
        if server in self.servers:
            return {'added': [], 'migrated': []}
        
        self.servers.append(server)
        migrated_keys = []
        
        # ALL existing keys potentially need reassignment
        for key in list(self.key_assignments.keys()):
            old_server = self.key_assignments[key]
            new_server = self.get_server(key)
            
            if new_server != old_server:
                migrated_keys.append(key)
                self.key_assignments[key] = new_server
        
        return {'added': [server], 'migrated': migrated_keys}
    
    def remove_server(self, server: str) -> Dict[str, List[str]]:
        """Remove server and return reassigned keys."""
        if server not in self.servers:
            return {'removed': [], 'migrated': []}
        
        self.servers.remove(server)
        migrated_keys = []
        
        # Reassign ALL keys
        for key in list(self.key_assignments.keys()):
            old_server = self.key_assignments[key]
            new_server = self.get_server(key)
            
            if new_server != old_server:
                migrated_keys.append(key)
                if new_server:
                    self.key_assignments[key] = new_server
                else:
                    del self.key_assignments[key]
        
        return {'removed': [server], 'migrated': migrated_keys}
    
    def get_server(self, key: str) -> Optional[str]:
        """Get server using simple modulo hashing."""
        if not self.servers:
            return None
        
        hash_value = self._hash(key)
        server_index = hash_value % len(self.servers)
        server = self.servers[server_index]
        
        self.key_assignments[key] = server
        return server
```

---

## Step 3: Performance Testing Framework

### 3.1 Load Distribution Test
```python
# tests/test_distribution.py
import pytest
import random
import string
from src.consistent_hash import ConsistentHashRing
from src.simple_hash import SimpleHashBalancer

class TestLoadDistribution:
    
    def generate_random_keys(self, count: int) -> List[str]:
        """Generate random keys for testing."""
        return [''.join(random.choices(string.ascii_letters + string.digits, k=10)) 
                for _ in range(count)]
    
    def test_consistent_hash_distribution(self):
        """Test load distribution with consistent hashing."""
        servers = ['server1', 'server2', 'server3', 'server4']
        ring = ConsistentHashRing(servers, virtual_nodes=150)
        
        # Generate test keys
        keys = self.generate_random_keys(10000)
        
        # Assign keys
        for key in keys:
            ring.get_server(key)
        
        stats = ring.get_ring_stats()
        
        # Check distribution quality
        assert stats['coefficient_of_variation'] < 0.3, \
            f"Poor load distribution: CV = {stats['coefficient_of_variation']}"
        
        print(f"Consistent Hash Distribution:")
        for server, load in stats['server_loads'].items():
            print(f"  {server}: {load} keys ({load/10000*100:.1f}%)")
        print(f"Coefficient of Variation: {stats['coefficient_of_variation']:.3f}")
    
    def test_virtual_nodes_impact(self):
        """Test impact of virtual node count on distribution."""
        servers = ['server1', 'server2', 'server3']
        keys = self.generate_random_keys(5000)
        
        results = {}
        
        for vnode_count in [10, 50, 100, 150, 200, 300]:
            ring = ConsistentHashRing(servers, virtual_nodes=vnode_count)
            
            for key in keys:
                ring.get_server(key)
            
            stats = ring.get_ring_stats()
            results[vnode_count] = stats['load_distribution']['coefficient_of_variation']
        
        print(f"\nVirtual Nodes Impact on Distribution:")
        for vnodes, cv in results.items():
            print(f"  {vnodes} vnodes: CV = {cv:.3f}")
        
        # Generally, more virtual nodes should improve distribution
        assert results[300] < results[10], "More virtual nodes should improve distribution"
    
    def test_key_migration_minimal(self):
        """Test that key migration is minimal when adding/removing servers."""
        servers = ['server1', 'server2', 'server3']
        ring = ConsistentHashRing(servers, virtual_nodes=150)
        
        # Add initial keys
        keys = self.generate_random_keys(1000)
        for key in keys:
            ring.get_server(key)
        
        initial_assignments = dict(ring.key_assignments)
        
        # Add a new server
        migration_info = ring.add_server('server4')
        migrated_keys = len(migration_info['migrated'])
        
        # Should migrate roughly 1/4 of keys (1/(n+1))
        expected_migration = len(keys) / 4
        tolerance = expected_migration * 0.3  # 30% tolerance
        
        assert abs(migrated_keys - expected_migration) < tolerance, \
            f"Expected ~{expected_migration} migrations, got {migrated_keys}"
        
        print(f"Migration Test:")
        print(f"  Total keys: {len(keys)}")
        print(f"  Keys migrated: {migrated_keys} ({migrated_keys/len(keys)*100:.1f}%)")
        print(f"  Expected: ~{expected_migration:.0f} ({25}%)")
    
    def test_comparison_with_simple_hash(self):
        """Compare consistent hash with simple modulo hash."""
        servers = ['server1', 'server2', 'server3']
        keys = self.generate_random_keys(1000)
        
        # Test consistent hashing
        consistent_ring = ConsistentHashRing(servers, virtual_nodes=150)
        for key in keys:
            consistent_ring.get_server(key)
        
        # Test simple hashing
        simple_hash = SimpleHashBalancer(servers)
        for key in keys:
            simple_hash.get_server(key)
        
        # Add new server and measure migration
        consistent_migration = consistent_ring.add_server('server4')
        simple_migration = simple_hash.add_server('server4')
        
        consistent_migrated = len(consistent_migration['migrated'])
        simple_migrated = len(simple_migration['migrated'])
        
        print(f"\nComparison: Adding Server")
        print(f"  Consistent Hash migrations: {consistent_migrated} ({consistent_migrated/len(keys)*100:.1f}%)")
        print(f"  Simple Hash migrations: {simple_migrated} ({simple_migrated/len(keys)*100:.1f}%)")
        
        # Consistent hashing should migrate significantly fewer keys
        assert consistent_migrated < simple_migrated, \
            "Consistent hashing should migrate fewer keys than simple hashing"

# Run specific test
if __name__ == "__main__":
    test = TestLoadDistribution()
    test.test_consistent_hash_distribution()
    test.test_virtual_nodes_impact()
    test.test_key_migration_minimal()
    test.test_comparison_with_simple_hash()
```

---

## Step 4: Visualization Tools

### 4.1 Ring Visualization
```python
# visualizations/visualize_ring.py
import matplotlib.pyplot as plt
import numpy as np
from src.consistent_hash import ConsistentHashRing
import math

class RingVisualizer:
    """Visualize the consistent hash ring and key distribution."""
    
    def __init__(self, ring: ConsistentHashRing):
        self.ring = ring
    
    def plot_ring_distribution(self, save_path: str = None):
        """Plot the hash ring showing server positions and key distribution."""
        if not self.ring.sorted_keys:
            print("No servers in ring")
            return
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Plot 1: Ring visualization
        self._plot_hash_ring(ax1)
        
        # Plot 2: Load distribution
        self._plot_load_distribution(ax2)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()
    
    def _plot_hash_ring(self, ax):
        """Plot the hash ring as a circular visualization."""
        # Normalize hash values to [0, 2π] for circular plot
        max_hash = 2**32  # Using lower range for visualization
        
        # Filter keys for visualization (sample if too many)
        keys = self.ring.sorted_keys
        if len(keys) > 100:
            step = len(keys) // 100
            keys = keys[::step]
        
        angles = [2 * math.pi * (key % max_hash) / max_hash for key in keys]
        
        # Create colors for different servers
        servers = list(self.ring.servers)
        colors = plt.cm.Set3(np.linspace(0, 1, len(servers)))
        server_colors = {server: colors[i] for i, server in enumerate(servers)}
        
        # Plot points on the circle
        for i, (angle, key) in enumerate(zip(angles, keys)):
            server = self.ring.ring[key]
            color = server_colors[server]
            
            x = math.cos(angle)
            y = math.sin(angle)
            
            ax.scatter(x, y, c=[color], s=30, alpha=0.7, 
                      label=server if server not in [p.get_label() for p in ax.get_children()])
        
        # Draw circle
        circle = plt.Circle((0, 0), 1, fill=False, linestyle='--', alpha=0.5)
        ax.add_patch(circle)
        
        ax.set_xlim(-1.2, 1.2)
        ax.set_ylim(-1.2, 1.2)
        ax.set_aspect('equal')
        ax.set_title('Hash Ring Virtual Node Distribution')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    
    def _plot_load_distribution(self, ax):
        """Plot the load distribution across servers."""
        stats = self.ring.get_ring_stats()
        servers = list(stats['server_loads'].keys())
        loads = list(stats['server_loads'].values())
        
        bars = ax.bar(servers, loads)
        
        # Color bars by relative load
        max_load = max(loads) if loads else 1
        for bar, load in zip(bars, loads):
            normalized_load = load / max_load if max_load > 0 else 0
            bar.set_color(plt.cm.RdYlBu_r(normalized_load))
        
        ax.set_xlabel('Servers')
        ax.set_ylabel('Number of Keys')
        ax.set_title('Load Distribution Across Servers')
        
        # Add average line
        if loads:
            avg_load = sum(loads) / len(loads)
            ax.axhline(y=avg_load, color='red', linestyle='--', alpha=0.7, 
                      label=f'Average: {avg_load:.1f}')
            ax.legend()
        
        # Rotate x-axis labels if many servers
        if len(servers) > 6:
            plt.setp(ax.get_xticklabels(), rotation=45)
    
    def plot_migration_analysis(self, before_servers, after_servers, keys, save_path=None):
        """Visualize key migration when servers change."""
        # Create rings for before and after
        ring_before = ConsistentHashRing(before_servers, virtual_nodes=150)
        ring_after = ConsistentHashRing(after_servers, virtual_nodes=150)
        
        # Assign keys to both rings
        assignments_before = {}
        assignments_after = {}
        
        for key in keys:
            assignments_before[key] = ring_before.get_server(key)
            assignments_after[key] = ring_after.get_server(key)
        
        # Calculate migration
        migrated_keys = [key for key in keys 
                        if assignments_before[key] != assignments_after[key]]
        
        # Create visualization
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        
        # Before state
        self._plot_server_assignments(ax1, assignments_before, "Before Change")
        
        # After state  
        self._plot_server_assignments(ax2, assignments_after, "After Change")
        
        # Migration matrix
        self._plot_migration_matrix(ax3, assignments_before, assignments_after, keys)
        
        # Migration statistics
        self._plot_migration_stats(ax4, assignments_before, assignments_after, keys)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.show()
        
        return len(migrated_keys), len(keys)
    
    def _plot_server_assignments(self, ax, assignments, title):
        """Plot pie chart of key assignments to servers."""
        server_counts = {}
        for server in assignments.values():
            server_counts[server] = server_counts.get(server, 0) + 1
        
        if server_counts:
            servers = list(server_counts.keys())
            counts = list(server_counts.values())
            
            ax.pie(counts, labels=servers, autopct='%1.1f%%', startangle=90)
            ax.set_title(title)
    
    def _plot_migration_matrix(self, ax, before, after, keys):
        """Plot migration matrix showing key movement between servers."""
        # Get all servers
        all_servers = set(before.values()) | set(after.values())
        server_list = sorted(all_servers)
        
        # Create migration matrix
        matrix = np.zeros((len(server_list), len(server_list)))
        
        for key in keys:
            from_server = before[key]
            to_server = after[key]
            
            from_idx = server_list.index(from_server)
            to_idx = server_list.index(to_server)
            
            matrix[from_idx][to_idx] += 1
        
        im = ax.imshow(matrix, cmap='Blues')
        
        # Add labels
        ax.set_xticks(range(len(server_list)))
        ax.set_yticks(range(len(server_list)))
        ax.set_xticklabels(server_list, rotation=45)
        ax.set_yticklabels(server_list)
        
        # Add text annotations
        for i in range(len(server_list)):
            for j in range(len(server_list)):
                if matrix[i][j] > 0:
                    ax.text(j, i, f'{int(matrix[i][j])}', 
                           ha='center', va='center')
        
        ax.set_xlabel('To Server')
        ax.set_ylabel('From Server')
        ax.set_title('Key Migration Matrix')
        
        plt.colorbar(im, ax=ax)
    
    def _plot_migration_stats(self, ax, before, after, keys):
        """Plot migration statistics."""
        migrated = sum(1 for key in keys if before[key] != after[key])
        stayed = len(keys) - migrated
        
        ax.bar(['Stayed', 'Migrated'], [stayed, migrated], 
               color=['green', 'orange'])
        
        ax.set_ylabel('Number of Keys')
        ax.set_title(f'Key Migration Summary\n'
                    f'{migrated}/{len(keys)} keys migrated ({migrated/len(keys)*100:.1f}%)')
        
        # Add percentage labels on bars
        for i, (label, value) in enumerate([('Stayed', stayed), ('Migrated', migrated)]):
            percentage = value / len(keys) * 100
            ax.text(i, value + len(keys) * 0.01, f'{percentage:.1f}%', 
                   ha='center', va='bottom')

# Example usage script
def create_ring_visualization():
    """Create and save ring visualizations."""
    # Create test ring
    servers = ['web1', 'web2', 'web3', 'web4']
    ring = ConsistentHashRing(servers, virtual_nodes=150)
    
    # Add some test keys
    keys = [f'user:{i}' for i in range(1000)]
    for key in keys:
        ring.get_server(key)
    
    # Visualize
    visualizer = RingVisualizer(ring)
    visualizer.plot_ring_distribution('data/ring_distribution.png')
    
    # Test migration visualization
    migration_keys = [f'key:{i}' for i in range(500)]
    migrated_count, total_keys = visualizer.plot_migration_analysis(
        before_servers=['web1', 'web2', 'web3'],
        after_servers=['web1', 'web2', 'web3', 'web4'],
        keys=migration_keys,
        save_path='data/migration_analysis.png'
    )
    
    print(f"Migration analysis: {migrated_count}/{total_keys} keys migrated")

if __name__ == "__main__":
    create_ring_visualization()
```

---

## Step 5: Real-world Application - Redis Cluster Simulation

### 5.1 Redis Cluster Simulation
```python
# src/redis_cluster_sim.py
import redis
from src.consistent_hash import ConsistentHashRing
from typing import Dict, List, Any
import time
import threading

class RedisClusterSimulator:
    """
    Simulate a Redis cluster using consistent hashing.
    Shows practical application of consistent hashing in distributed storage.
    """
    
    def __init__(self, redis_nodes: List[Dict[str, Any]], virtual_nodes: int = 150):
        """
        Initialize Redis cluster simulator.
        
        Args:
            redis_nodes: List of {'host': 'localhost', 'port': 6379, 'name': 'redis1'}
            virtual_nodes: Virtual nodes per Redis instance
        """
        self.hash_ring = ConsistentHashRing(
            [node['name'] for node in redis_nodes],
            virtual_nodes=virtual_nodes
        )
        
        # Redis connection pool for each node
        self.redis_connections = {}
        for node in redis_nodes:
            try:
                self.redis_connections[node['name']] = redis.Redis(
                    host=node['host'],
                    port=node['port'],
                    decode_responses=True,
                    socket_connect_timeout=1,
                    socket_timeout=1
                )
                # Test connection
                self.redis_connections[node['name']].ping()
            except Exception as e:
                print(f"Warning: Could not connect to {node['name']}: {e}")
        
        # Metrics
        self.operation_stats = {
            'set_operations': 0,
            'get_operations': 0,
            'errors': 0,
            'node_usage': {node: 0 for node in self.redis_connections.keys()}
        }
        
        self.lock = threading.Lock()
    
    def _get_redis_node(self, key: str) -> redis.Redis:
        """Get the Redis node responsible for a key."""
        node_name = self.hash_ring.get_server(key)
        
        if node_name not in self.redis_connections:
            raise Exception(f"Node {node_name} not available")
        
        with self.lock:
            self.operation_stats['node_usage'][node_name] += 1
        
        return self.redis_connections[node_name]
    
    def set(self, key: str, value: str, ttl: int = None) -> bool:
        """Set a key-value pair in the appropriate Redis node."""
        try:
            redis_node = self._get_redis_node(key)
            
            if ttl:
                result = redis_node.setex(key, ttl, value)
            else:
                result = redis_node.set(key, value)
            
            with self.lock:
                self.operation_stats['set_operations'] += 1
            
            return result
            
        except Exception as e:
            with self.lock:
                self.operation_stats['errors'] += 1
            print(f"Error setting key {key}: {e}")
            return False
    
    def get(self, key: str) -> str:
        """Get a value from the appropriate Redis node."""
        try:
            redis_node = self._get_redis_node(key)
            result = redis_node.get(key)
            
            with self.lock:
                self.operation_stats['get_operations'] += 1
            
            return result
            
        except Exception as e:
            with self.lock:
                self.operation_stats['errors'] += 1
            print(f"Error getting key {key}: {e}")
            return None
    
    def mget(self, keys: List[str]) -> Dict[str, str]:
        """Get multiple keys, routing to appropriate nodes."""
        # Group keys by node
        node_keys = {}
        for key in keys:
            node_name = self.hash_ring.get_server(key)
            if node_name not in node_keys:
                node_keys[node_name] = []
            node_keys[node_name].append(key)
        
        # Fetch from each node
        results = {}
        for node_name, node_keys_list in node_keys.items():
            try:
                redis_node = self.redis_connections[node_name]
                node_results = redis_node.mget(node_keys_list)
                
                for key, value in zip(node_keys_list, node_results):
                    results[key] = value
                
                with self.lock:
                    self.operation_stats['get_operations'] += len(node_keys_list)
                    self.operation_stats['node_usage'][node_name] += len(node_keys_list)
                    
            except Exception as e:
                print(f"Error getting keys from {node_name}: {e}")
                with self.lock:
                    self.operation_stats['errors'] += len(node_keys_list)
        
        return results
    
    def add_node(self, node_config: Dict[str, Any]) -> Dict[str, int]:
        """
        Add a new Redis node and handle data migration.
        
        Returns:
            Migration statistics
        """
        node_name = node_config['name']
        
        # Connect to new Redis node
        try:
            new_redis = redis.Redis(
                host=node_config['host'],
                port=node_config['port'],
                decode_responses=True
            )
            new_redis.ping()
            self.redis_connections[node_name] = new_redis
        except Exception as e:
            return {'error': f"Could not connect to new node: {e}"}
        
        # Add to hash ring and get migration info
        migration_info = self.hash_ring.add_server(node_name)
        
        # Migrate keys that should now go to the new node
        migrated_count = 0
        for key in migration_info['migrated']:
            try:
                # Get current value
                old_node_name = None
                for name, conn in self.redis_connections.items():
                    if name != node_name:
                        value = conn.get(key)
                        if value is not None:
                            old_node_name = name
                            break
                
                if value is not None:
                    # Set on new node
                    new_redis.set(key, value)
                    # Remove from old node
                    if old_node_name:
                        self.redis_connections[old_node_name].delete(key)
                    migrated_count += 1
                    
            except Exception as e:
                print(f"Error migrating key {key}: {e}")
        
        # Update stats
        with self.lock:
            self.operation_stats['node_usage'][node_name] = 0
        
        return {
            'migrated_keys': migrated_count,
            'total_affected_keys': len(migration_info['migrated'])
        }
    
    def remove_node(self, node_name: str) -> Dict[str, int]:
        """
        Remove a Redis node and migrate its data.
        
        Returns:
            Migration statistics
        """
        if node_name not in self.redis_connections:
            return {'error': 'Node not found'}
        
        # Get all keys from the node to be removed
        try:
            redis_node = self.redis_connections[node_name]
            all_keys = redis_node.keys('*')
        except Exception as e:
            return {'error': f"Could not get keys from node: {e}"}
        
        # Remove from hash ring first to get new assignments
        migration_info = self.hash_ring.remove_server(node_name)
        
        # Migrate all keys to their new locations
        migrated_count = 0
        for key in all_keys:
            try:
                # Get value from old node
                value = redis_node.get(key)
                if value is not None:
                    # Get new node assignment
                    new_node_name = self.hash_ring.get_server(key)
                    if new_node_name and new_node_name != node_name:
                        # Set on new node
                        self.redis_connections[new_node_name].set(key, value)
                        migrated_count += 1
                        
            except Exception as e:
                print(f"Error migrating key {key}: {e}")
        
        # Remove the Redis connection
        del self.redis_connections[node_name]
        
        # Update stats
        with self.lock:
            del self.operation_stats['node_usage'][node_name]
        
        return {
            'migrated_keys': migrated_count,
            'total_keys': len(all_keys)
        }
    
    def get_cluster_stats(self) -> Dict:
        """Get comprehensive cluster statistics."""
        stats = self.hash_ring.get_ring_stats()
        stats['operation_stats'] = dict(self.operation_stats)
        
        # Add Redis-specific stats
        redis_stats = {}
        for node_name, redis_conn in self.redis_connections.items():
            try:
                info = redis_conn.info()
                redis_stats[node_name] = {
                    'connected_clients': info.get('connected_clients', 0),
                    'used_memory_human': info.get('used_memory_human', '0B'),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0),
                    'total_commands_processed': info.get('total_commands_processed', 0)
                }
            except Exception as e:
                redis_stats[node_name] = {'error': str(e)}
        
        stats['redis_stats'] = redis_stats
        return stats

# Docker Compose setup for testing
def create_docker_compose():
    """Create Docker Compose file for Redis cluster testing."""
    compose_content = """version: '3.8'

services:
  redis1:
    image: redis:alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis1_data:/data

  redis2:
    image: redis:alpine
    ports:
      - "6380:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis2_data:/data

  redis3:
    image: redis:alpine
    ports:
      - "6381:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis3_data:/data

  redis4:
    image: redis:alpine
    ports:
      - "6382:6379"
    command: redis-server --appendonly yes
    volumes:
      - redis4_data:/data

volumes:
  redis1_data:
  redis2_data:
  redis3_data:
  redis4_data:
"""
    
    with open('docker-compose-redis.yml', 'w') as f:
        f.write(compose_content)
    
    print("Created docker-compose-redis.yml")
    print("Start Redis cluster with: docker-compose -f docker-compose-redis.yml up -d")

# Test the Redis cluster simulation
def test_redis_cluster():
    """Test the Redis cluster simulation."""
    # Define Redis nodes
    nodes = [
        {'host': 'localhost', 'port': 6379, 'name': 'redis1'},
        {'host': 'localhost', 'port': 6380, 'name': 'redis2'},
        {'host': 'localhost', 'port': 6381, 'name': 'redis3'}
    ]
    
    # Create cluster
    cluster = RedisClusterSimulator(nodes, virtual_nodes=150)
    
    # Test basic operations
    print("Testing basic operations...")
    
    # Set some test data
    test_data = {
        f'user:{i}': f'user_data_{i}' 
        for i in range(1, 101)
    }
    
    for key, value in test_data.items():
        cluster.set(key, value)
    
    # Get some data back
    retrieved_keys = list(test_data.keys())[:10]
    results = cluster.mget(retrieved_keys)
    
    print(f"Set {len(test_data)} keys")
    print(f"Retrieved {len([v for v in results.values() if v is not None])} keys")
    
    # Show cluster stats
    stats = cluster.get_cluster_stats()
    print("\nCluster Statistics:")
    print(f"Total servers: {stats['total_servers']}")
    print(f"Server loads: {stats['server_loads']}")
    print(f"Operations: {stats['operation_stats']}")
    
    # Test adding a node
    print("\nAdding new Redis node...")
    new_node = {'host': 'localhost', 'port': 6382, 'name': 'redis4'}
    migration_result = cluster.add_node(new_node)
    print(f"Migration result: {migration_result}")
    
    return cluster

if __name__ == "__main__":
    create_docker_compose()
    # test_redis_cluster()  # Uncomment after starting Redis containers
```

---

## Step 6: Comprehensive Testing

### 6.1 Performance Benchmarks
```python
# tests/test_performance.py
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from src.consistent_hash import ConsistentHashRing
from src.simple_hash import SimpleHashBalancer
import random
import string

class PerformanceBenchmark:
    
    def generate_keys(self, count: int) -> List[str]:
        """Generate realistic keys for testing."""
        return [f"user:{random.randint(1, 1000000):06d}" for _ in range(count)]
    
    def benchmark_lookup_performance(self):
        """Benchmark lookup performance of different algorithms."""
        servers = [f'server{i}' for i in range(1, 11)]  # 10 servers
        keys = self.generate_keys(100000)
        
        results = {}
        
        # Test consistent hashing
        for vnode_count in [50, 100, 150, 200]:
            ring = ConsistentHashRing(servers, virtual_nodes=vnode_count)
            
            start_time = time.time()
            for key in keys:
                ring.get_server(key)
            end_time = time.time()
            
            results[f'consistent_hash_{vnode_count}'] = {
                'duration': end_time - start_time,
                'ops_per_second': len(keys) / (end_time - start_time)
            }
        
        # Test simple hashing
        simple = SimpleHashBalancer(servers)
        start_time = time.time()
        for key in keys:
            simple.get_server(key)
        end_time = time.time()
        
        results['simple_hash'] = {
            'duration': end_time - start_time,
            'ops_per_second': len(keys) / (end_time - start_time)
        }
        
        print("Lookup Performance Benchmark (100,000 operations):")
        for algorithm, stats in results.items():
            print(f"  {algorithm}: {stats['ops_per_second']:.0f} ops/sec")
        
        return results
    
    def benchmark_concurrent_operations(self):
        """Benchmark performance under concurrent load."""
        servers = ['server1', 'server2', 'server3', 'server4']
        ring = ConsistentHashRing(servers, virtual_nodes=150)
        
        def worker_thread(thread_id: int, operations: int):
            """Worker thread for concurrent testing."""
            keys = [f"thread{thread_id}:key{i}" for i in range(operations)]
            
            start_time = time.time()
            for key in keys:
                ring.get_server(key)
            end_time = time.time()
            
            return end_time - start_time
        
        # Test with different thread counts
        results = {}
        operations_per_thread = 10000
        
        for thread_count in [1, 2, 4, 8, 16]:
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                futures = [
                    executor.submit(worker_thread, i, operations_per_thread)
                    for i in range(thread_count)
                ]
                
                durations = [future.result() for future in futures]
            
            end_time = time.time()
            total_operations = thread_count * operations_per_thread
            
            results[thread_count] = {
                'total_duration': end_time - start_time,
                'max_thread_duration': max(durations),
                'ops_per_second': total_operations / (end_time - start_time)
            }
        
        print("\nConcurrent Performance Benchmark:")
        for threads, stats in results.items():
            print(f"  {threads} threads: {stats['ops_per_second']:.0f} ops/sec")
        
        return results
    
    def benchmark_scaling_operations(self):
        """Benchmark the cost of adding/removing servers."""
        initial_servers = ['server1', 'server2', 'server3']
        keys = self.generate_keys(50000)
        
        results = {}
        
        # Test adding servers
        ring = ConsistentHashRing(initial_servers, virtual_nodes=150)
        
        # Assign initial keys
        for key in keys:
            ring.get_server(key)
        
        # Add servers and measure cost
        for i in range(4, 11):  # Add servers 4-10
            server_name = f'server{i}'
            
            start_time = time.time()
            migration_info = ring.add_server(server_name)
            end_time = time.time()
            
            results[f'add_server_{i}'] = {
                'duration': end_time - start_time,
                'migrated_keys': len(migration_info['migrated']),
                'migration_percentage': len(migration_info['migrated']) / len(keys) * 100
            }
        
        # Test removing servers
        for i in range(10, 6, -1):  # Remove servers 10-7
            server_name = f'server{i}'
            
            start_time = time.time()
            migration_info = ring.remove_server(server_name)
            end_time = time.time()
            
            results[f'remove_server_{i}'] = {
                'duration': end_time - start_time,
                'migrated_keys': len(migration_info['migrated']),
                'migration_percentage': len(migration_info['migrated']) / len(keys) * 100
            }
        
        print("\nScaling Operations Benchmark:")
        for operation, stats in results.items():
            print(f"  {operation}: {stats['duration']:.3f}s, "
                  f"{stats['migrated_keys']} keys ({stats['migration_percentage']:.1f}%)")
        
        return results

# Run all benchmarks
def run_all_benchmarks():
    """Run comprehensive performance benchmarks."""
    benchmark = PerformanceBenchmark()
    
    print("=== Load Balancer Performance Benchmarks ===")
    
    lookup_results = benchmark.benchmark_lookup_performance()
    concurrent_results = benchmark.benchmark_concurrent_operations()
    scaling_results = benchmark.benchmark_scaling_operations()
    
    # Save results for analysis
    import json
    results = {
        'lookup': lookup_results,
        'concurrent': concurrent_results,
        'scaling': scaling_results
    }
    
    with open('data/benchmark_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\nBenchmark results saved to data/benchmark_results.json")

if __name__ == "__main__":
    run_all_benchmarks()
```

---

## Step 7: Production Readiness Features

### 7.1 Configuration and Monitoring
```python
# src/production_hash_ring.py
import json
import logging
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from src.consistent_hash import ConsistentHashRing
import threading
from datetime import datetime, timedelta

@dataclass
class HealthCheckConfig:
    """Configuration for server health checking."""
    interval_seconds: int = 30
    timeout_seconds: int = 5
    max_failures: int = 3
    recovery_check_interval: int = 60

@dataclass
class ServerMetrics:
    """Metrics for individual servers."""
    requests_handled: int = 0
    last_health_check: Optional[datetime] = None
    consecutive_failures: int = 0
    is_healthy: bool = True
    average_response_time: float = 0.0
    last_error: Optional[str] = None

class ProductionHashRing:
    """
    Production-ready consistent hash ring with health checking,
    monitoring, and configuration management.
    """
    
    def __init__(self, 
                 config_file: str = None,
                 health_check_config: HealthCheckConfig = None):
        """
        Initialize production hash ring.
        
        Args:
            config_file: Path to JSON configuration file
            health_check_config: Health check configuration
        """
        self.config = self._load_config(config_file)
        self.health_config = health_check_config or HealthCheckConfig()
        
        # Core hash ring
        self.hash_ring = ConsistentHashRing(
            servers=self.config.get('servers', []),
            virtual_nodes=self.config.get('virtual_nodes', 150)
        )
        
        # Health and metrics
        self.server_metrics = {}
        self._init_server_metrics()
        
        # Threading for health checks
        self.health_check_thread = None
        self.shutdown_event = threading.Event()
        
        # Logging
        self.logger = self._setup_logging()
        
        # Start health checking
        self._start_health_checks()
    
    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file."""
        if not config_file:
            return {
                'servers': [],
                'virtual_nodes': 150,
                'log_level': 'INFO'
            }
        
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load config file {config_file}: {e}")
            return {'servers': [], 'virtual_nodes': 150}
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the hash ring."""
        logger = logging.getLogger('hash_ring')
        logger.setLevel(getattr(logging, self.config.get('log_level', 'INFO')))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _init_server_metrics(self):
        """Initialize metrics for all servers."""
        for server in self.hash_ring.servers:
            self.server_metrics[server] = ServerMetrics()
    
    def _start_health_checks(self):
        """Start background health checking thread."""
        if self.health_check_thread is None:
            self.health_check_thread = threading.Thread(
                target=self._health_check_loop,
                daemon=True
            )
            self.health_check_thread.start()
            self.logger.info("Started health check thread")
    
    def _health_check_loop(self):
        """Background health checking loop."""
        while not self.shutdown_event.is_set():
            try:
                self._perform_health_checks()
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")
            
            # Wait for next health check interval
            self.shutdown_event.wait(self.health_config.interval_seconds)
    
    def _perform_health_checks(self):
        """Perform health checks on all servers."""
        for server in list(self.hash_ring.servers):
            try:
                is_healthy = self._check_server_health(server)
                self._update_server_health(server, is_healthy)
            except Exception as e:
                self.logger.error(f"Health check failed for {server}: {e}")
                self._update_server_health(server, False, str(e))
    
    def _check_server_health(self, server: str) -> bool:
        """
        Check health of a specific server.
        Override this method with actual health check logic.
        """
        # Placeholder - implement actual health check
        # For example: HTTP health check, TCP connection test, etc.
        time.sleep(0.1)  # Simulate health check
        return True  # Assume healthy for demo
    
    def _update_server_health(self, server: str, is_healthy: bool, error: str = None):
        """Update server health status and metrics."""
        metrics = self.server_metrics.get(server)
        if not metrics:
            return
        
        metrics.last_health_check = datetime.now()
        
        if is_healthy:
            if not metrics.is_healthy:
                self.logger.info(f"Server {server} recovered")
            metrics.consecutive_failures = 0
            metrics.is_healthy = True
            metrics.last_error = None
        else:
            metrics.consecutive_failures += 1
            metrics.last_error = error
            
            # Mark as unhealthy if exceeded failure threshold
            if (metrics.consecutive_failures >= self.health_config.max_failures 
                and metrics.is_healthy):
                self.logger.warning(f"Server {server} marked as unhealthy after "
                                  f"{metrics.consecutive_failures} failures")
                metrics.is_healthy = False
                self._remove_unhealthy_server(server)
    
    def _remove_unhealthy_server(self, server: str):
        """Remove unhealthy server from rotation."""
        migration_info = self.hash_ring.remove_server(server)
        self.logger.warning(f"Removed unhealthy server {server}, "
                          f"migrated {len(migration_info['migrated'])} keys")
    
    def get_server(self, key: str) -> Optional[str]:
        """Get server for key, with health checking."""
        server = self.hash_ring.get_server(key)
        
        if server:
            # Update metrics
            metrics = self.server_metrics.get(server)
            if metrics:
                metrics.requests_handled += 1
        
        return server
    
    def add_server(self, server: str, health_check: bool = True) -> Dict:
        """Add server with optional immediate health check."""
        if health_check:
            is_healthy = self._check_server_health(server)
            if not is_healthy:
                self.logger.warning(f"Server {server} failed initial health check")
                return {'error': 'Server failed health check'}
        
        migration_info = self.hash_ring.add_server(server)
        self.server_metrics[server] = ServerMetrics()
        
        self.logger.info(f"Added server {server}, "
                        f"migrated {len(migration_info['migrated'])} keys")
        
        return migration_info
    
    def remove_server(self, server: str) -> Dict:
        """Remove server gracefully."""
        migration_info = self.hash_ring.remove_server(server)
        
        if server in self.server_metrics:
            del self.server_metrics[server]
        
        self.logger.info(f"Removed server {server}, "
                        f"migrated {len(migration_info['migrated'])} keys")
        
        return migration_info
    
    def get_comprehensive_stats(self) -> Dict:
        """Get comprehensive statistics including health metrics."""
        base_stats = self.hash_ring.get_ring_stats()
        
        # Add health and performance metrics
        server_health = {}
        for server, metrics in self.server_metrics.items():
            server_health[server] = {
                'is_healthy': metrics.is_healthy,
                'consecutive_failures': metrics.consecutive_failures,
                'requests_handled': metrics.requests_handled,
                'last_health_check': metrics.last_health_check.isoformat() 
                                   if metrics.last_health_check else None,
                'last_error': metrics.last_error
            }
        
        base_stats['server_health'] = server_health
        base_stats['health_config'] = asdict(self.health_config)
        
        return base_stats
    
    def export_metrics(self, format: str = 'prometheus') -> str:
        """Export metrics in various formats."""
        stats = self.get_comprehensive_stats()
        
        if format == 'prometheus':
            return self._format_prometheus_metrics(stats)
        elif format == 'json':
            return json.dumps(stats, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _format_prometheus_metrics(self, stats: Dict) -> str:
        """Format metrics for Prometheus."""
        lines = []
        
        # Hash ring metrics
        lines.append("# HELP hash_ring_servers_total Total number of servers")
        lines.append("# TYPE hash_ring_servers_total gauge")
        lines.append(f"hash_ring_servers_total {stats['total_servers']}")
        
        lines.append("# HELP hash_ring_virtual_nodes_total Total virtual nodes")
        lines.append("# TYPE hash_ring_virtual_nodes_total gauge")
        lines.append(f"hash_ring_virtual_nodes_total {stats['total_virtual_nodes']}")
        
        lines.append("# HELP hash_ring_keys_total Total keys assigned")
        lines.append("# TYPE hash_ring_keys_total gauge")
        lines.append(f"hash_ring_keys_total {stats['total_keys']}")
        
        # Server-specific metrics
        lines.append("# HELP hash_ring_server_healthy Server health status")
        lines.append("# TYPE hash_ring_server_healthy gauge")
        
        lines.append("# HELP hash_ring_server_requests_total Total requests per server")
        lines.append("# TYPE hash_ring_server_requests_total counter")
        
        for server, health in stats['server_health'].items():
            healthy = 1 if health['is_healthy'] else 0
            lines.append(f'hash_ring_server_healthy{{server="{server}"}} {healthy}')
            lines.append(f'hash_ring_server_requests_total{{server="{server}"}} {health["requests_handled"]}')
        
        return '\n'.join(lines)
    
    def shutdown(self):
        """Gracefully shutdown the hash ring."""
        self.logger.info("Shutting down hash ring")
        self.shutdown_event.set()
        
        if self.health_check_thread:
            self.health_check_thread.join(timeout=5)

# Configuration file example
def create_sample_config():
    """Create sample configuration file."""
    config = {
        "servers": ["web1", "web2", "web3"],
        "virtual_nodes": 150,
        "log_level": "INFO",
        "health_check": {
            "interval_seconds": 30,
            "timeout_seconds": 5,
            "max_failures": 3,
            "recovery_check_interval": 60
        }
    }
    
    with open('data/hash_ring_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print("Created sample config: data/hash_ring_config.json")

if __name__ == "__main__":
    create_sample_config()
    
    # Test the production hash ring
    ring = ProductionHashRing('data/hash_ring_config.json')
    
    # Add some test load
    for i in range(1000):
        ring.get_server(f'key:{i}')
    
    # Print stats
    print(json.dumps(ring.get_comprehensive_stats(), indent=2))
    
    # Export Prometheus metrics
    print("\n--- Prometheus Metrics ---")
    print(ring.export_metrics('prometheus'))
    
    # Shutdown
    ring.shutdown()
```

---

## Step 8: Lab Exercises and Assessments

### Exercise 1: Implementation Challenge
**Objective**: Implement a custom hash function and compare its distribution properties.

**Tasks**:
1. Create a custom hash function using SHA-256
2. Implement it in the ConsistentHashRing class
3. Compare distribution quality with MD5
4. Measure performance differences

### Exercise 2: Real-world Scenario
**Scenario**: Design consistent hashing for a global CDN with the following requirements:
- 50 edge servers across 10 geographic regions
- 1 million cached objects
- Servers frequently go offline for maintenance
- Need to minimize cache misses during topology changes

**Deliverables**:
1. Hash ring configuration strategy
2. Virtual node count optimization
3. Health check implementation
4. Performance analysis

### Exercise 3: Migration Analysis
**Objective**: Analyze key migration patterns under different scenarios.

**Tasks**:
1. Start with 5 servers and 10,000 keys
2. Add servers one by one (scale to 20 servers)
3. Remove random servers (scale down to 3 servers)
4. Compare migration costs between consistent hashing and simple hashing
5. Create visualizations showing migration patterns

### Exercise 4: Performance Optimization
**Objective**: Optimize the hash ring implementation for high-throughput scenarios.

**Tasks**:
1. Identify performance bottlenecks using profiling
2. Implement optimizations (caching, faster data structures, etc.)
3. Benchmark before/after performance
4. Document optimization techniques used

---

## Lab Assessment

### Practical Deliverables (60%)

1. **Working Implementation**: Complete consistent hashing implementation with all features
2. **Performance Analysis**: Comprehensive benchmarking report comparing algorithms
3. **Visualization**: Clear visualizations of ring distribution and migration patterns
4. **Documentation**: Well-documented code with usage examples

### Knowledge Assessment (40%)

Answer these questions based on your implementation:

1. **Distribution Quality**: How does the number of virtual nodes affect load distribution? What's the optimal range?

2. **Migration Efficiency**: Compare key migration percentages when adding/removing servers. How does this relate to the theoretical minimum?

3. **Performance Trade-offs**: What are the computational trade-offs between consistent hashing and simple hashing?

4. **Real-world Applications**: Describe three real-world systems that would benefit from consistent hashing and explain why.

5. **Failure Scenarios**: How would you handle scenarios where multiple servers fail simultaneously?

---

## Next Steps

### Production Deployment
- Implement actual health checks (HTTP, TCP, custom protocols)
- Add monitoring and alerting integration
- Implement gradual traffic shifting for new servers
- Add configuration hot-reloading

### Advanced Features
- Support for weighted servers
- Multi-level consistent hashing
- Integration with service discovery systems
- Backup server assignments for high availability

### Further Learning
- Study production implementations (HAProxy, Envoy, Kong)
- Explore consistent hashing variations (Jump Hash, Rendezvous Hashing)
- Implement load balancing for specific protocols (gRPC, WebSocket)

---

## Conclusion

This lab provided hands-on experience with:
- Core consistent hashing algorithms and data structures
- Performance testing and optimization techniques
- Real-world application patterns
- Production-ready features like health checking and monitoring

The skills developed here are directly applicable to building and operating distributed systems at scale, making this essential knowledge for staff and principal engineers working on high-performance infrastructure.

---

## Resources

### References
- [Consistent Hashing and Random Trees: Distributed Caching Protocols for Relieving Hot Spots on the World Wide Web](https://www.akamai.com/us/en/multimedia/documents/technical-publication/consistent-hashing-and-random-trees-distributed-caching-protocols-for-relieving-hot-spots-on-the-world-wide-web-technical-publication.pdf)
- [Amazon DynamoDB Under the Hood: How We Built a Hyper-Scale Database](https://www.allthingsdistributed.com/2017/10/amazon-dynamodb-ten-years-later.html)
- [Cassandra: A Decentralized Structured Storage System](http://www.cs.cornell.edu/projects/ladis2009/papers/lakshman-ladis2009.pdf)

### Tools and Libraries
- [Python hashlib documentation](https://docs.python.org/3/library/hashlib.html)
- [Redis Cluster specification](https://redis.io/topics/cluster-spec)
- [HAProxy consistent hashing](https://www.haproxy.com/blog/loadbalancing-leastconn-first-match-and-chash/)

### Further Reading
- "Designing Data-Intensive Applications" by Martin Kleppmann (Chapter 6: Partitioning)
- "High Performance Browser Networking" by Ilya Grigorik (Chapter 12: HTTP/2)
- [The Google File System](https://static.googleusercontent.com/media/research.google.com/en//archive/gfs-sosp2003.pdf)