# Module 01: Distributed Systems Fundamentals
*Building the theoretical foundation*

## Learning Objectives

By the end of this module, you will:
- Understand the fundamental challenges of distributed systems
- Master the CAP theorem and its practical implications  
- Implement different consistency models
- Work with logical time and event ordering
- Apply consensus algorithms in practice

## Topics Covered

1. **What Makes Systems Distributed** - The fundamental challenges
2. **CAP Theorem** - Choose two: Consistency, Availability, Partition tolerance
3. **Consistency Models** - From strong to eventual consistency
4. **Time and Ordering** - Logical clocks and event causality
5. **Consensus Algorithms** - Raft and practical consensus
6. **Failure Models** - Understanding what can go wrong

---

## 1. What Makes Systems Distributed

### Definition
A distributed system is one where components on networked computers communicate and coordinate their actions by passing messages.

### Key Characteristics
- **No shared memory**: Components communicate via message passing
- **Concurrent execution**: Multiple components run simultaneously  
- **Independent failures**: Parts of the system can fail independently
- **Network partitions**: Components may be unable to communicate

### The Fallacies of Distributed Computing
1. The network is reliable
2. Latency is zero  
3. Bandwidth is infinite
4. The network is secure
5. Topology doesn't change
6. There is one administrator
7. Transport cost is zero
8. The network is homogeneous

### Why Distributed Systems Are Hard

```python
# Example: Simple vs Distributed Counter
class LocalCounter:
    def __init__(self):
        self.value = 0
    
    def increment(self):
        self.value += 1  # Atomic operation
        return self.value

class DistributedCounter:
    def __init__(self, node_id, peers):
        self.node_id = node_id
        self.peers = peers
        self.local_value = 0
    
    async def increment(self):
        # Challenge: How do we coordinate across nodes?
        # 1. Network delays
        # 2. Partial failures  
        # 3. Message ordering
        # 4. Consensus requirements
        
        # Naive approach (BROKEN):
        current = await self.get_global_value()
        new_value = current + 1
        await self.set_global_value(new_value)
        # Race conditions galore!
        
        return new_value
```

---

## 2. CAP Theorem

### Statement
In any distributed system, you can guarantee at most two of:
- **Consistency**: All nodes see the same data simultaneously
- **Availability**: The system remains operational  
- **Partition tolerance**: The system continues despite network failures

### Practical Implications

```python
from enum import Enum
from typing import Dict, Optional

class CAPChoice(Enum):
    CP = "consistency_partition_tolerance"  # Sacrifice availability
    AP = "availability_partition_tolerance"  # Sacrifice consistency  
    CA = "consistency_availability"         # Sacrifice partition tolerance (impractical)

# CP System Example: Traditional RDBMS with ACID
class CPDatabase:
    """Chooses Consistency + Partition tolerance, sacrifices Availability"""
    
    def __init__(self):
        self.data: Dict[str, str] = {}
        self.is_master = True
        self.replicas_available = True
    
    def write(self, key: str, value: str) -> bool:
        if not self.replicas_available:
            # Sacrifice availability to maintain consistency
            raise UnavailableError("Cannot write - replicas unreachable")
        
        # Ensure all replicas get the write before confirming
        success = self._replicate_to_all(key, value)
        if success:
            self.data[key] = value
            return True
        else:
            raise ConsistencyError("Could not maintain consistency")
    
    def read(self, key: str) -> str:
        if not self.replicas_available:
            raise UnavailableError("Cannot read - consistency cannot be guaranteed")
        return self.data.get(key, "")

# AP System Example: DNS, Web caches
class APDatabase:
    """Chooses Availability + Partition tolerance, sacrifices Consistency"""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.data: Dict[str, str] = {}
        self.vector_clock: Dict[str, int] = {}
    
    def write(self, key: str, value: str) -> bool:
        # Always accept writes, even during partitions
        self.data[key] = value
        self.vector_clock[self.node_id] = self.vector_clock.get(self.node_id, 0) + 1
        
        # Best-effort replication (don't wait for confirmation)
        self._async_replicate(key, value)
        return True
    
    def read(self, key: str) -> str:
        # Always serve reads, even if potentially stale
        return self.data.get(key, "")
```

### Real-World Examples

| System | CAP Choice | Trade-offs |
|--------|------------|------------|
| **Traditional RDBMS** | CP | High consistency, may become unavailable during partitions |
| **DNS** | AP | High availability, eventual consistency (TTL-based) |
| **Amazon DynamoDB** | AP* | Eventually consistent, highly available (*CP with strong consistency option) |
| **Google Spanner** | CP | Strong consistency, global availability through specialized hardware |
| **Cassandra** | AP (tunable) | Configurable consistency levels |

---

## 3. Consistency Models

### Strong Consistency
All nodes see the same data at the same time.

```python
import threading
import time
from typing import Any

class StronglyConsistentStore:
    """All reads return the most recent write"""
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._version = 0
    
    def write(self, key: str, value: Any) -> int:
        with self._lock:
            self._data[key] = value
            self._version += 1
            # In distributed version, would wait for all replicas
            # to confirm before returning
            return self._version
    
    def read(self, key: str) -> Any:
        with self._lock:
            # In distributed version, would ensure reading from 
            # most up-to-date replica
            return self._data.get(key)
```

### Eventual Consistency
The system will become consistent over time, but intermediate states may differ.

```python
import asyncio
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class Update:
    key: str
    value: Any
    timestamp: float
    node_id: str

class EventuallyConsistentStore:
    """Guarantees convergence, not immediate consistency"""
    
    def __init__(self, node_id: str, peers: List[str]):
        self.node_id = node_id
        self.peers = peers
        self._data: Dict[str, Any] = {}
        self._pending_updates: List[Update] = []
    
    def write(self, key: str, value: Any) -> bool:
        # Immediately accept write
        update = Update(key, value, time.time(), self.node_id)
        self._apply_update(update)
        
        # Asynchronously propagate to peers
        asyncio.create_task(self._propagate_update(update))
        return True
    
    def read(self, key: str) -> Any:
        # May return stale data
        return self._data.get(key)
    
    def _apply_update(self, update: Update):
        # Last-writer-wins conflict resolution
        current_time = self._get_timestamp(update.key)
        if update.timestamp > current_time:
            self._data[update.key] = update.value
    
    async def _propagate_update(self, update: Update):
        for peer in self.peers:
            try:
                await self._send_to_peer(peer, update)
            except NetworkError:
                # Store for later retry
                self._pending_updates.append(update)
```

### Causal Consistency
Causally related events are seen in the same order by all nodes.

```python
from typing import Dict, Tuple

class VectorClock:
    """Implements vector clocks for causal ordering"""
    
    def __init__(self, node_id: str, nodes: List[str]):
        self.node_id = node_id
        self.nodes = nodes
        self.clock: Dict[str, int] = {node: 0 for node in nodes}
    
    def tick(self) -> Dict[str, int]:
        """Increment local clock"""
        self.clock[self.node_id] += 1
        return self.clock.copy()
    
    def update(self, other_clock: Dict[str, int]) -> Dict[str, int]:
        """Update clock when receiving message"""
        for node in self.nodes:
            if node == self.node_id:
                self.clock[node] += 1
            else:
                self.clock[node] = max(self.clock[node], other_clock.get(node, 0))
        return self.clock.copy()
    
    def compare(self, other_clock: Dict[str, int]) -> str:
        """Compare two vector clocks"""
        self_greater = False
        other_greater = False
        
        for node in self.nodes:
            self_val = self.clock.get(node, 0)
            other_val = other_clock.get(node, 0)
            
            if self_val > other_val:
                self_greater = True
            elif self_val < other_val:
                other_greater = True
        
        if self_greater and not other_greater:
            return "before"  # self happens before other
        elif other_greater and not self_greater:
            return "after"   # self happens after other
        elif not self_greater and not other_greater:
            return "equal"   # concurrent events
        else:
            return "concurrent"  # incomparable

class CausallyConsistentStore:
    """Ensures causal order is preserved"""
    
    def __init__(self, node_id: str, nodes: List[str]):
        self.node_id = node_id
        self._data: Dict[str, Any] = {}
        self._vector_clock = VectorClock(node_id, nodes)
        self._message_buffer: List[Tuple[Update, Dict[str, int]]] = []
    
    def write(self, key: str, value: Any) -> Dict[str, int]:
        # Create update with current vector clock
        clock = self._vector_clock.tick()
        update = Update(key, value, time.time(), self.node_id)
        
        self._apply_update(update, clock)
        return clock
    
    def receive_update(self, update: Update, sender_clock: Dict[str, int]):
        """Process update from another node"""
        # Check if we can apply immediately or need to buffer
        if self._can_apply_immediately(sender_clock):
            self._vector_clock.update(sender_clock)
            self._apply_update(update, sender_clock)
            self._try_apply_buffered()
        else:
            self._message_buffer.append((update, sender_clock))
    
    def _can_apply_immediately(self, sender_clock: Dict[str, int]) -> bool:
        """Check if update preserves causal order"""
        for node, timestamp in sender_clock.items():
            if node != self.node_id:
                if timestamp > self._vector_clock.clock.get(node, 0) + 1:
                    return False
        return True
```

---

## 4. Time and Ordering

### The Problem with Physical Time

```python
import time
import random

# Physical clocks can drift and be unreliable
class UnreliablePhysicalClock:
    def __init__(self, drift_rate=0.1):
        self.drift_rate = drift_rate
        self.start_time = time.time()
        self.accumulated_drift = 0
    
    def now(self) -> float:
        elapsed = time.time() - self.start_time
        # Simulate clock drift
        self.accumulated_drift += elapsed * self.drift_rate * random.uniform(-1, 1)
        return time.time() + self.accumulated_drift

# Events can appear out of order!
def demonstrate_clock_issues():
    clock1 = UnreliablePhysicalClock(drift_rate=0.01)
    clock2 = UnreliablePhysicalClock(drift_rate=-0.02)
    
    # Event on node 1
    event1_time = clock1.now()
    print(f"Event 1: {event1_time}")
    
    time.sleep(0.1)  # Event 2 happens AFTER event 1
    
    # Event on node 2  
    event2_time = clock2.now()
    print(f"Event 2: {event2_time}")
    
    # But due to clock drift, event2_time might be less than event1_time!
    print(f"Event 2 appears to happen before Event 1: {event2_time < event1_time}")
```

### Lamport Logical Clocks

```python
class LamportClock:
    """Implements Lamport's logical clock algorithm"""
    
    def __init__(self):
        self.time = 0
    
    def tick(self) -> int:
        """Increment clock for local event"""
        self.time += 1
        return self.time
    
    def update(self, received_time: int) -> int:
        """Update clock when receiving message"""
        self.time = max(self.time, received_time) + 1
        return self.time

@dataclass
class Message:
    content: str
    lamport_time: int
    sender: str

class LamportNode:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.clock = LamportClock()
        self.message_log: List[Message] = []
    
    def send_message(self, content: str, recipient: 'LamportNode'):
        # Increment clock for send event
        send_time = self.clock.tick()
        message = Message(content, send_time, self.node_id)
        
        # Simulate network delay
        asyncio.create_task(self._deliver_message(message, recipient))
        
        print(f"{self.node_id} sends at time {send_time}: {content}")
    
    def receive_message(self, message: Message):
        # Update clock with received timestamp
        receive_time = self.clock.update(message.lamport_time)
        self.message_log.append(message)
        
        print(f"{self.node_id} receives at time {receive_time}: {message.content} (sent at {message.lamport_time})")
    
    async def _deliver_message(self, message: Message, recipient: 'LamportNode'):
        # Simulate network delay
        await asyncio.sleep(random.uniform(0.1, 0.5))
        recipient.receive_message(message)

# Example usage
async def lamport_example():
    node_a = LamportNode("A")
    node_b = LamportNode("B")
    node_c = LamportNode("C")
    
    # Events happen in this order:
    node_a.send_message("Hello from A", node_b)
    node_b.send_message("Hello from B", node_c)  
    node_c.send_message("Hello from C", node_a)
    
    await asyncio.sleep(1)  # Wait for message delivery
    
    # Now we can order events by Lamport timestamp
    all_messages = node_a.message_log + node_b.message_log + node_c.message_log
    all_messages.sort(key=lambda m: (m.lamport_time, m.sender))
    
    print("\nGlobal message ordering:")
    for msg in all_messages:
        print(f"Time {msg.lamport_time}: {msg.sender} -> {msg.content}")
```

---

## 5. Consensus Algorithms

### The Consensus Problem
Get multiple nodes to agree on a single value, even with failures.

### Raft Consensus Algorithm

```python
import random
import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict

class NodeState(Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"

@dataclass
class LogEntry:
    term: int
    index: int
    command: str

@dataclass
class RequestVoteArgs:
    term: int
    candidate_id: str
    last_log_index: int
    last_log_term: int

@dataclass
class RequestVoteReply:
    term: int
    vote_granted: bool

@dataclass
class AppendEntriesArgs:
    term: int
    leader_id: str
    prev_log_index: int
    prev_log_term: int
    entries: List[LogEntry]
    leader_commit: int

@dataclass
class AppendEntriesReply:
    term: int
    success: bool

class RaftNode:
    """Simplified Raft consensus implementation"""
    
    def __init__(self, node_id: str, peers: List[str]):
        self.node_id = node_id
        self.peers = peers
        
        # Persistent state
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.log: List[LogEntry] = [LogEntry(0, 0, "")]  # 1-indexed
        
        # Volatile state
        self.commit_index = 0
        self.last_applied = 0
        self.state = NodeState.FOLLOWER
        
        # Leader state
        self.next_index: Dict[str, int] = {}
        self.match_index: Dict[str, int] = {}
        
        # Timing
        self.last_heartbeat = time.time()
        self.election_timeout = random.uniform(150, 300)  # ms
        self.heartbeat_interval = 50  # ms
    
    async def start(self):
        """Main node loop"""
        while True:
            if self.state == NodeState.LEADER:
                await self._send_heartbeats()
                await asyncio.sleep(self.heartbeat_interval / 1000)
            else:
                # Check for election timeout
                if time.time() - self.last_heartbeat > self.election_timeout / 1000:
                    await self._start_election()
                await asyncio.sleep(10 / 1000)  # Check every 10ms
    
    async def _start_election(self):
        """Start leader election"""
        self.state = NodeState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.last_heartbeat = time.time()
        
        print(f"Node {self.node_id} starting election for term {self.current_term}")
        
        # Request votes from all peers
        votes_received = 1  # Vote for self
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term if self.log else 0
        
        vote_args = RequestVoteArgs(
            self.current_term, 
            self.node_id,
            last_log_index,
            last_log_term
        )
        
        for peer in self.peers:
            try:
                reply = await self._request_vote(peer, vote_args)
                if reply.vote_granted:
                    votes_received += 1
                elif reply.term > self.current_term:
                    self._become_follower(reply.term)
                    return
            except Exception:
                continue  # Peer unavailable
        
        # Check if won election
        if votes_received > len(self.peers) // 2:
            self._become_leader()
        else:
            self._become_follower(self.current_term)
    
    def _become_leader(self):
        """Become leader after winning election"""
        self.state = NodeState.LEADER
        print(f"Node {self.node_id} became leader for term {self.current_term}")
        
        # Initialize leader state
        last_log_index = len(self.log) - 1
        for peer in self.peers:
            self.next_index[peer] = last_log_index + 1
            self.match_index[peer] = 0
    
    def _become_follower(self, term: int):
        """Become follower"""
        self.state = NodeState.FOLLOWER
        self.current_term = term
        self.voted_for = None
        self.last_heartbeat = time.time()
    
    async def _send_heartbeats(self):
        """Send heartbeat to all followers"""
        for peer in self.peers:
            try:
                prev_log_index = self.next_index[peer] - 1
                prev_log_term = self.log[prev_log_index].term if prev_log_index > 0 else 0
                
                args = AppendEntriesArgs(
                    self.current_term,
                    self.node_id,
                    prev_log_index,
                    prev_log_term,
                    [],  # Heartbeat - no entries
                    self.commit_index
                )
                
                reply = await self._append_entries(peer, args)
                if reply.term > self.current_term:
                    self._become_follower(reply.term)
                    return
                    
            except Exception:
                continue  # Peer unavailable
    
    async def append_entry(self, command: str) -> bool:
        """Add new entry to log (leader only)"""
        if self.state != NodeState.LEADER:
            return False
        
        # Add to local log
        entry = LogEntry(self.current_term, len(self.log), command)
        self.log.append(entry)
        
        print(f"Leader {self.node_id} appending: {command}")
        
        # Replicate to followers
        replicated_count = 1  # Self
        
        for peer in self.peers:
            try:
                if await self._replicate_to_peer(peer):
                    replicated_count += 1
            except Exception:
                continue
        
        # Commit if majority replicated
        if replicated_count > len(self.peers) // 2:
            self.commit_index = len(self.log) - 1
            print(f"Entry committed: {command}")
            return True
        
        return False
    
    async def _replicate_to_peer(self, peer: str) -> bool:
        """Replicate log entries to a specific peer"""
        while True:
            prev_log_index = self.next_index[peer] - 1
            prev_log_term = self.log[prev_log_index].term if prev_log_index > 0 else 0
            
            entries = self.log[self.next_index[peer]:]
            
            args = AppendEntriesArgs(
                self.current_term,
                self.node_id, 
                prev_log_index,
                prev_log_term,
                entries,
                self.commit_index
            )
            
            reply = await self._append_entries(peer, args)
            
            if reply.success:
                self.next_index[peer] = len(self.log)
                self.match_index[peer] = len(self.log) - 1
                return True
            else:
                if reply.term > self.current_term:
                    self._become_follower(reply.term)
                    return False
                
                # Decrement and retry
                self.next_index[peer] -= 1
                if self.next_index[peer] <= 0:
                    self.next_index[peer] = 1
    
    async def handle_request_vote(self, args: RequestVoteArgs) -> RequestVoteReply:
        """Handle vote request from candidate"""
        if args.term > self.current_term:
            self._become_follower(args.term)
        
        vote_granted = False
        
        if (args.term == self.current_term and 
            (self.voted_for is None or self.voted_for == args.candidate_id) and
            self._log_up_to_date(args.last_log_index, args.last_log_term)):
            
            self.voted_for = args.candidate_id
            vote_granted = True
            self.last_heartbeat = time.time()  # Reset election timeout
        
        return RequestVoteReply(self.current_term, vote_granted)
    
    async def handle_append_entries(self, args: AppendEntriesArgs) -> AppendEntriesReply:
        """Handle append entries RPC"""
        if args.term > self.current_term:
            self._become_follower(args.term)
        
        self.last_heartbeat = time.time()  # Reset election timeout
        
        # Reply false if term < currentTerm
        if args.term < self.current_term:
            return AppendEntriesReply(self.current_term, False)
        
        # Reply false if log doesn't contain an entry at prevLogIndex
        if (args.prev_log_index > 0 and 
            (len(self.log) <= args.prev_log_index or 
             self.log[args.prev_log_index].term != args.prev_log_term)):
            return AppendEntriesReply(self.current_term, False)
        
        # Append new entries
        if args.entries:
            # Delete conflicting entries and append new ones
            self.log = self.log[:args.prev_log_index + 1]
            self.log.extend(args.entries)
        
        # Update commit index
        if args.leader_commit > self.commit_index:
            self.commit_index = min(args.leader_commit, len(self.log) - 1)
        
        return AppendEntriesReply(self.current_term, True)
    
    def _log_up_to_date(self, candidate_last_index: int, candidate_last_term: int) -> bool:
        """Check if candidate's log is at least as up-to-date as ours"""
        last_index = len(self.log) - 1
        last_term = self.log[last_index].term if self.log else 0
        
        if candidate_last_term > last_term:
            return True
        elif candidate_last_term == last_term and candidate_last_index >= last_index:
            return True
        else:
            return False
```

---

## 6. Failure Models

### Types of Failures

```python
from abc import ABC, abstractmethod
import random

class FailureModel(ABC):
    @abstractmethod
    def should_fail(self) -> bool:
        pass

class CrashFailure(FailureModel):
    """Node stops functioning (fail-stop)"""
    def __init__(self, probability=0.01):
        self.probability = probability
        self.crashed = False
    
    def should_fail(self) -> bool:
        if not self.crashed and random.random() < self.probability:
            self.crashed = True
            return True
        return self.crashed

class ByzantineFailure(FailureModel):
    """Node behaves arbitrarily (worst case)"""
    def __init__(self, probability=0.01):
        self.probability = probability
    
    def should_fail(self) -> bool:
        return random.random() < self.probability
    
    def corrupt_message(self, message: str) -> str:
        if self.should_fail():
            # Byzantine node might lie about data
            return f"CORRUPTED_{message}"
        return message

class NetworkPartition(FailureModel):
    """Network splits, preventing communication"""
    def __init__(self, probability=0.005):
        self.probability = probability
        self.partitioned = False
        self.partition_duration = 0
    
    def should_fail(self) -> bool:
        if not self.partitioned and random.random() < self.probability:
            self.partitioned = True
            self.partition_duration = random.randint(5, 20)  # seconds
        elif self.partitioned:
            self.partition_duration -= 1
            if self.partition_duration <= 0:
                self.partitioned = False
        
        return self.partitioned

# Failure-aware system design
class ResilientSystem:
    def __init__(self, failure_models: List[FailureModel]):
        self.failure_models = failure_models
        self.retry_count = 0
        self.max_retries = 3
    
    async def send_message(self, message: str, destination: str) -> bool:
        """Send message with failure handling"""
        for _ in range(self.max_retries):
            try:
                # Check for failures
                for failure_model in self.failure_models:
                    if isinstance(failure_model, CrashFailure) and failure_model.should_fail():
                        raise CrashError("Node crashed")
                    elif isinstance(failure_model, NetworkPartition) and failure_model.should_fail():
                        raise NetworkError("Network partition")
                    elif isinstance(failure_model, ByzantineFailure):
                        message = failure_model.corrupt_message(message)
                
                # Simulate actual send
                await self._actually_send(message, destination)
                return True
                
            except (NetworkError, CrashError) as e:
                print(f"Send failed: {e}")
                await asyncio.sleep(2 ** self.retry_count)  # Exponential backoff
                self.retry_count += 1
        
        return False  # Failed after all retries
```

---

## Labs and Exercises

### Lab 1: Implement Vector Clocks
Build a complete vector clock implementation and demonstrate causality tracking.

### Lab 2: CAP Theorem Simulation
Create systems that demonstrate different CAP choices and their trade-offs.

### Lab 3: Raft Consensus
Extend the Raft implementation to handle more edge cases and failure scenarios.

### Lab 4: Consistency Models
Implement and compare different consistency models with real examples.

## Assessment Questions

1. **Scenario**: You're designing a global chat application. Analyze the CAP theorem trade-offs for:
   - Message delivery guarantees
   - User presence information  
   - Message ordering across continents

2. **Implementation**: Build a distributed counter that maintains strong consistency using consensus.

3. **Analysis**: Given a sequence of events with Lamport timestamps, determine their causal relationships.

## References

### Essential Papers
- [Time, Clocks, and the Ordering of Events in a Distributed System](https://lamport.azurewebsites.net/pubs/time-clocks.pdf) - Leslie Lamport
- [The Byzantine Generals Problem](https://lamport.azurewebsites.net/pubs/byz.pdf) - Lamport, Shostak, Pease
- [In Search of an Understandable Consensus Algorithm](https://raft.github.io/raft.pdf) - Ongaro & Ousterhout

### Books
- "Distributed Systems: Principles and Paradigms" - Tanenbaum & Van Steen
- "Distributed Algorithms" - Nancy Lynch

### Online Resources
- [Raft Visualization](http://thesecretlivesofdata.com/raft/)
- [CAP Theorem Explained](https://www.ibm.com/cloud/learn/cap-theorem)

---

*Next: [Module 02 - Architecture Patterns](../02_ARCHITECTURE_PATTERNS/)*