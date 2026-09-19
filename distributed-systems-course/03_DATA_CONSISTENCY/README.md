# Module 03: Data Consistency
*Managing data consistency in distributed systems*

## Learning Objectives

By the end of this module, you will:
- Implement various consistency models and understand their trade-offs
- Design distributed transactions using 2PC and Saga patterns
- Apply conflict resolution strategies for eventually consistent systems
- Build polyglot persistence architectures with appropriate consistency guarantees
- Handle data synchronization across multiple data stores

## Topics Covered

1. **ACID vs BASE** - Different consistency models and their implications
2. **Distributed Transactions** - Two-phase commit and its alternatives
3. **Saga Patterns** - Long-running transactions in distributed systems
4. **Eventually Consistent Systems** - Designing for eventual consistency
5. **Conflict Resolution** - Handling conflicts in distributed data
6. **Database Patterns** - Polyglot persistence and data modeling

---

## 1. ACID vs BASE

### ACID Properties Deep Dive

```python
import asyncio
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import time

class TransactionState(Enum):
    ACTIVE = "active"
    COMMITTED = "committed" 
    ABORTED = "aborted"
    PREPARING = "preparing"

@dataclass
class TransactionLog:
    transaction_id: str
    operations: List[Dict[str, Any]]
    state: TransactionState
    start_time: float
    end_time: Optional[float] = None

class ACIDDatabase:
    """ACID-compliant database implementation"""
    
    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.locks: Dict[str, str] = {}  # key -> transaction_id
        self.transaction_logs: Dict[str, TransactionLog] = {}
        self.isolation_levels = {
            "READ_UNCOMMITTED": 0,
            "READ_COMMITTED": 1,
            "REPEATABLE_READ": 2,
            "SERIALIZABLE": 3
        }
    
    async def begin_transaction(self, isolation_level: str = "READ_COMMITTED") -> str:
        """Begin a new ACID transaction"""
        transaction_id = str(uuid.uuid4())
        
        transaction_log = TransactionLog(
            transaction_id=transaction_id,
            operations=[],
            state=TransactionState.ACTIVE,
            start_time=time.time()
        )
        
        self.transaction_logs[transaction_id] = transaction_log
        return transaction_id
    
    async def read(self, transaction_id: str, key: str, 
                   isolation_level: str = "READ_COMMITTED") -> Optional[Any]:
        """Read with ACID isolation guarantees"""
        transaction = self.transaction_logs.get(transaction_id)
        if not transaction or transaction.state != TransactionState.ACTIVE:
            raise ValueError("Invalid transaction")
        
        # Check isolation level requirements
        if isolation_level == "SERIALIZABLE":
            # Acquire read lock for serializable isolation
            if key in self.locks and self.locks[key] != transaction_id:
                raise Exception(f"Resource {key} locked by another transaction")
            self.locks[key] = transaction_id
        
        # Log the read operation
        transaction.operations.append({
            "type": "READ",
            "key": key,
            "timestamp": time.time(),
            "isolation_level": isolation_level
        })
        
        return self.data.get(key)
    
    async def write(self, transaction_id: str, key: str, value: Any) -> None:
        """Write with ACID durability and atomicity"""
        transaction = self.transaction_logs.get(transaction_id)
        if not transaction or transaction.state != TransactionState.ACTIVE:
            raise ValueError("Invalid transaction")
        
        # Acquire exclusive lock
        if key in self.locks and self.locks[key] != transaction_id:
            raise Exception(f"Resource {key} locked by another transaction")
        
        self.locks[key] = transaction_id
        
        # Log the write operation (don't apply yet)
        transaction.operations.append({
            "type": "WRITE",
            "key": key,
            "value": value,
            "previous_value": self.data.get(key),
            "timestamp": time.time()
        })
    
    async def commit(self, transaction_id: str) -> bool:
        """Commit transaction with ACID guarantees"""
        transaction = self.transaction_logs.get(transaction_id)
        if not transaction or transaction.state != TransactionState.ACTIVE:
            raise ValueError("Invalid transaction")
        
        try:
            # Phase 1: Prepare (validate all operations)
            transaction.state = TransactionState.PREPARING
            
            for operation in transaction.operations:
                if operation["type"] == "WRITE":
                    # Validate write operation can still be performed
                    key = operation["key"]
                    if key in self.locks and self.locks[key] != transaction_id:
                        raise Exception("Lock conflict detected")
            
            # Phase 2: Commit (apply all operations atomically)
            for operation in transaction.operations:
                if operation["type"] == "WRITE":
                    self.data[operation["key"]] = operation["value"]
            
            transaction.state = TransactionState.COMMITTED
            transaction.end_time = time.time()
            
            # Release locks
            self._release_locks(transaction_id)
            
            return True
            
        except Exception as e:
            await self.abort(transaction_id)
            raise
    
    async def abort(self, transaction_id: str) -> None:
        """Abort transaction and rollback changes"""
        transaction = self.transaction_logs.get(transaction_id)
        if not transaction:
            return
        
        transaction.state = TransactionState.ABORTED
        transaction.end_time = time.time()
        
        # Release locks
        self._release_locks(transaction_id)
    
    def _release_locks(self, transaction_id: str):
        """Release all locks held by transaction"""
        keys_to_release = [key for key, tx_id in self.locks.items() if tx_id == transaction_id]
        for key in keys_to_release:
            del self.locks[key]

# BASE Properties Implementation
class BASEDatabase:
    """Eventually consistent database following BASE principles"""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.data: Dict[str, Any] = {}
        self.vector_clock: Dict[str, int] = {node_id: 0}
        self.pending_operations: List[Dict] = []
        self.replicas: List['BASEDatabase'] = []
    
    def write(self, key: str, value: Any) -> Dict[str, Any]:
        """Write with eventual consistency (BASE)"""
        # Update vector clock
        self.vector_clock[self.node_id] += 1
        
        # Apply locally immediately (Basically Available)
        operation = {
            "type": "WRITE",
            "key": key,
            "value": value,
            "node_id": self.node_id,
            "vector_clock": self.vector_clock.copy(),
            "timestamp": time.time()
        }
        
        self.data[key] = value
        self.pending_operations.append(operation)
        
        # Asynchronously replicate to other nodes (Eventual Consistency)
        asyncio.create_task(self._replicate_operation(operation))
        
        return operation
    
    def read(self, key: str) -> Optional[Any]:
        """Read with eventual consistency"""
        # May return stale data, but system remains available
        return self.data.get(key)
    
    async def _replicate_operation(self, operation: Dict):
        """Replicate operation to other nodes (eventual consistency)"""
        for replica in self.replicas:
            try:
                await replica.receive_operation(operation)
            except Exception as e:
                # Log error but don't fail the operation
                # System remains available despite network issues
                print(f"Replication to {replica.node_id} failed: {e}")
    
    async def receive_operation(self, operation: Dict):
        """Receive operation from another node"""
        # Update vector clock
        for node, clock in operation["vector_clock"].items():
            self.vector_clock[node] = max(
                self.vector_clock.get(node, 0), 
                clock
            )
        
        # Apply operation with conflict resolution
        await self._apply_with_conflict_resolution(operation)
    
    async def _apply_with_conflict_resolution(self, operation: Dict):
        """Apply operation with last-writer-wins conflict resolution"""
        key = operation["key"]
        
        # Simple last-writer-wins based on vector clock
        current_op = self.pending_operations
        should_apply = True
        
        for pending in current_op:
            if (pending["key"] == key and 
                self._vector_clock_compare(pending["vector_clock"], operation["vector_clock"]) > 0):
                should_apply = False
                break
        
        if should_apply:
            self.data[key] = operation["value"]
            self.pending_operations.append(operation)
    
    def _vector_clock_compare(self, clock1: Dict[str, int], clock2: Dict[str, int]) -> int:
        """Compare vector clocks (-1: clock1 < clock2, 0: concurrent, 1: clock1 > clock2)"""
        clock1_greater = False
        clock2_greater = False
        
        all_nodes = set(clock1.keys()) | set(clock2.keys())
        
        for node in all_nodes:
            val1 = clock1.get(node, 0)
            val2 = clock2.get(node, 0)
            
            if val1 > val2:
                clock1_greater = True
            elif val1 < val2:
                clock2_greater = True
        
        if clock1_greater and not clock2_greater:
            return 1
        elif clock2_greater and not clock1_greater:
            return -1
        else:
            return 0  # Concurrent

# Comparison Example
async def acid_vs_base_comparison():
    """Compare ACID and BASE approaches"""
    
    print("=== ACID Database Example ===")
    acid_db = ACIDDatabase()
    
    # ACID Transaction
    tx1 = await acid_db.begin_transaction("SERIALIZABLE")
    
    try:
        await acid_db.write(tx1, "account_a", 1000)
        await acid_db.write(tx1, "account_b", 500)
        
        # All-or-nothing commit
        success = await acid_db.commit(tx1)
        print(f"ACID transaction committed: {success}")
        
    except Exception as e:
        await acid_db.abort(tx1)
        print(f"ACID transaction aborted: {e}")
    
    print("\n=== BASE Database Example ===")
    
    # BASE System
    node1 = BASEDatabase("node1")
    node2 = BASEDatabase("node2")
    node1.replicas = [node2]
    node2.replicas = [node1]
    
    # Eventually consistent writes
    op1 = node1.write("user_profile", {"name": "Alice", "age": 30})
    op2 = node2.write("user_profile", {"name": "Alice", "age": 31})  # Concurrent update
    
    print(f"Node1 data: {node1.read('user_profile')}")
    print(f"Node2 data: {node2.read('user_profile')}")
    
    # Allow replication to occur
    await asyncio.sleep(0.1)
    
    print(f"After replication:")
    print(f"Node1 data: {node1.read('user_profile')}")
    print(f"Node2 data: {node2.read('user_profile')}")
```

---

## 2. Distributed Transactions

### Two-Phase Commit Protocol

```python
import asyncio
from typing import Dict, List, Set, Optional
from enum import Enum
from dataclasses import dataclass
import time

class TransactionPhase(Enum):
    PREPARE = "prepare"
    COMMIT = "commit"
    ABORT = "abort"

class ParticipantResponse(Enum):
    PREPARED = "prepared"
    ABORTED = "aborted"
    COMMITTED = "committed"

@dataclass
class TransactionContext:
    transaction_id: str
    coordinator_id: str
    participants: Set[str]
    operations: List[Dict]
    phase: TransactionPhase
    start_time: float
    timeout: float = 30.0

class TwoPhaseCommitCoordinator:
    """Two-Phase Commit Protocol Coordinator"""
    
    def __init__(self, coordinator_id: str):
        self.coordinator_id = coordinator_id
        self.active_transactions: Dict[str, TransactionContext] = {}
        self.participants: Dict[str, 'TwoPhaseCommitParticipant'] = {}
    
    def add_participant(self, participant_id: str, participant: 'TwoPhaseCommitParticipant'):
        """Add participant to the coordinator"""
        self.participants[participant_id] = participant
    
    async def begin_distributed_transaction(self, operations: List[Dict]) -> str:
        """Begin a new distributed transaction"""
        transaction_id = str(uuid.uuid4())
        
        # Determine participants based on operations
        participants = set()
        for op in operations:
            participants.add(op["participant_id"])
        
        context = TransactionContext(
            transaction_id=transaction_id,
            coordinator_id=self.coordinator_id,
            participants=participants,
            operations=operations,
            phase=TransactionPhase.PREPARE,
            start_time=time.time()
        )
        
        self.active_transactions[transaction_id] = context
        
        # Execute two-phase commit
        try:
            success = await self._execute_two_phase_commit(context)
            return transaction_id if success else None
        except Exception as e:
            await self._abort_transaction(context)
            raise
    
    async def _execute_two_phase_commit(self, context: TransactionContext) -> bool:
        """Execute the two-phase commit protocol"""
        
        # Phase 1: Prepare
        print(f"Transaction {context.transaction_id}: Phase 1 - PREPARE")
        context.phase = TransactionPhase.PREPARE
        
        prepare_responses = await self._send_prepare_requests(context)
        
        # Check if all participants voted to commit
        all_prepared = all(
            response == ParticipantResponse.PREPARED 
            for response in prepare_responses.values()
        )
        
        if not all_prepared:
            print(f"Transaction {context.transaction_id}: Not all participants prepared, aborting")
            await self._abort_transaction(context)
            return False
        
        # Phase 2: Commit
        print(f"Transaction {context.transaction_id}: Phase 2 - COMMIT")
        context.phase = TransactionPhase.COMMIT
        
        commit_responses = await self._send_commit_requests(context)
        
        # Check if all participants committed successfully
        all_committed = all(
            response == ParticipantResponse.COMMITTED 
            for response in commit_responses.values()
        )
        
        if all_committed:
            print(f"Transaction {context.transaction_id}: Successfully committed")
            del self.active_transactions[context.transaction_id]
            return True
        else:
            print(f"Transaction {context.transaction_id}: Commit phase failed")
            return False
    
    async def _send_prepare_requests(self, context: TransactionContext) -> Dict[str, ParticipantResponse]:
        """Send prepare requests to all participants"""
        responses = {}
        tasks = []
        
        for participant_id in context.participants:
            participant = self.participants.get(participant_id)
            if participant:
                # Get operations for this participant
                participant_ops = [
                    op for op in context.operations 
                    if op["participant_id"] == participant_id
                ]
                
                task = asyncio.create_task(
                    participant.prepare(context.transaction_id, participant_ops)
                )
                tasks.append((participant_id, task))
        
        # Wait for all responses with timeout
        for participant_id, task in tasks:
            try:
                response = await asyncio.wait_for(task, timeout=context.timeout)
                responses[participant_id] = response
            except asyncio.TimeoutError:
                responses[participant_id] = ParticipantResponse.ABORTED
                print(f"Participant {participant_id} timed out during prepare phase")
            except Exception as e:
                responses[participant_id] = ParticipantResponse.ABORTED
                print(f"Participant {participant_id} error during prepare: {e}")
        
        return responses
    
    async def _send_commit_requests(self, context: TransactionContext) -> Dict[str, ParticipantResponse]:
        """Send commit requests to all participants"""
        responses = {}
        tasks = []
        
        for participant_id in context.participants:
            participant = self.participants.get(participant_id)
            if participant:
                task = asyncio.create_task(
                    participant.commit(context.transaction_id)
                )
                tasks.append((participant_id, task))
        
        # Wait for all responses
        for participant_id, task in tasks:
            try:
                response = await asyncio.wait_for(task, timeout=context.timeout)
                responses[participant_id] = response
            except Exception as e:
                responses[participant_id] = ParticipantResponse.ABORTED
                print(f"Participant {participant_id} error during commit: {e}")
        
        return responses
    
    async def _abort_transaction(self, context: TransactionContext):
        """Send abort requests to all participants"""
        context.phase = TransactionPhase.ABORT
        
        tasks = []
        for participant_id in context.participants:
            participant = self.participants.get(participant_id)
            if participant:
                task = asyncio.create_task(
                    participant.abort(context.transaction_id)
                )
                tasks.append(task)
        
        # Wait for all abort confirmations
        await asyncio.gather(*tasks, return_exceptions=True)
        
        if context.transaction_id in self.active_transactions:
            del self.active_transactions[context.transaction_id]

class TwoPhaseCommitParticipant:
    """Two-Phase Commit Protocol Participant"""
    
    def __init__(self, participant_id: str):
        self.participant_id = participant_id
        self.data: Dict[str, Any] = {}
        self.prepared_transactions: Dict[str, List[Dict]] = {}
        self.transaction_logs: Dict[str, Dict] = {}
    
    async def prepare(self, transaction_id: str, operations: List[Dict]) -> ParticipantResponse:
        """Prepare phase - validate and prepare for commit"""
        try:
            print(f"Participant {self.participant_id}: Preparing transaction {transaction_id}")
            
            # Validate all operations can be performed
            for operation in operations:
                if not self._validate_operation(operation):
                    return ParticipantResponse.ABORTED
            
            # Prepare transaction (but don't commit yet)
            self.prepared_transactions[transaction_id] = operations
            self.transaction_logs[transaction_id] = {
                "operations": operations,
                "state": "prepared",
                "timestamp": time.time()
            }
            
            print(f"Participant {self.participant_id}: Transaction {transaction_id} prepared")
            return ParticipantResponse.PREPARED
            
        except Exception as e:
            print(f"Participant {self.participant_id}: Prepare failed for {transaction_id}: {e}")
            return ParticipantResponse.ABORTED
    
    async def commit(self, transaction_id: str) -> ParticipantResponse:
        """Commit phase - apply all prepared operations"""
        try:
            if transaction_id not in self.prepared_transactions:
                return ParticipantResponse.ABORTED
            
            operations = self.prepared_transactions[transaction_id]
            
            print(f"Participant {self.participant_id}: Committing transaction {transaction_id}")
            
            # Apply all operations atomically
            for operation in operations:
                self._apply_operation(operation)
            
            # Clean up
            del self.prepared_transactions[transaction_id]
            self.transaction_logs[transaction_id]["state"] = "committed"
            
            print(f"Participant {self.participant_id}: Transaction {transaction_id} committed")
            return ParticipantResponse.COMMITTED
            
        except Exception as e:
            print(f"Participant {self.participant_id}: Commit failed for {transaction_id}: {e}")
            return ParticipantResponse.ABORTED
    
    async def abort(self, transaction_id: str) -> ParticipantResponse:
        """Abort phase - rollback prepared operations"""
        try:
            print(f"Participant {self.participant_id}: Aborting transaction {transaction_id}")
            
            # Clean up prepared transaction
            if transaction_id in self.prepared_transactions:
                del self.prepared_transactions[transaction_id]
            
            if transaction_id in self.transaction_logs:
                self.transaction_logs[transaction_id]["state"] = "aborted"
            
            print(f"Participant {self.participant_id}: Transaction {transaction_id} aborted")
            return ParticipantResponse.ABORTED
            
        except Exception as e:
            print(f"Participant {self.participant_id}: Abort failed for {transaction_id}: {e}")
            return ParticipantResponse.ABORTED
    
    def _validate_operation(self, operation: Dict) -> bool:
        """Validate that operation can be performed"""
        op_type = operation.get("type")
        key = operation.get("key")
        
        if op_type == "WRITE":
            # Check if we have required locks, resources, etc.
            return True  # Simplified validation
        elif op_type == "READ":
            return key in self.data
        
        return False
    
    def _apply_operation(self, operation: Dict):
        """Apply operation to local data"""
        op_type = operation.get("type")
        
        if op_type == "WRITE":
            self.data[operation["key"]] = operation["value"]
        elif op_type == "DELETE":
            if operation["key"] in self.data:
                del self.data[operation["key"]]

# Example: Distributed Banking Transaction
async def distributed_banking_example():
    """Example: Transfer money between accounts on different databases"""
    
    # Setup coordinator
    coordinator = TwoPhaseCommitCoordinator("bank_coordinator")
    
    # Setup participants (different bank databases)
    account_db = TwoPhaseCommitParticipant("account_db")
    audit_db = TwoPhaseCommitParticipant("audit_db")
    
    # Initialize some data
    account_db.data = {"account_123": 1000, "account_456": 500}
    audit_db.data = {}
    
    # Register participants
    coordinator.add_participant("account_db", account_db)
    coordinator.add_participant("audit_db", audit_db)
    
    # Define distributed transaction operations
    transfer_operations = [
        {
            "participant_id": "account_db",
            "type": "WRITE",
            "key": "account_123",
            "value": 800  # Debit $200
        },
        {
            "participant_id": "account_db", 
            "type": "WRITE",
            "key": "account_456",
            "value": 700  # Credit $200
        },
        {
            "participant_id": "audit_db",
            "type": "WRITE", 
            "key": f"transfer_{int(time.time())}",
            "value": {
                "from": "account_123",
                "to": "account_456", 
                "amount": 200,
                "timestamp": time.time()
            }
        }
    ]
    
    print("=== Starting Distributed Money Transfer ===")
    print(f"Before: Account 123 = {account_db.data['account_123']}, Account 456 = {account_db.data['account_456']}")
    
    # Execute distributed transaction
    transaction_id = await coordinator.begin_distributed_transaction(transfer_operations)
    
    if transaction_id:
        print(f"After: Account 123 = {account_db.data['account_123']}, Account 456 = {account_db.data['account_456']}")
        print(f"Audit log: {list(audit_db.data.keys())}")
    else:
        print("Transaction failed!")
```

---

## 3. Saga Patterns

### Orchestration-Based Saga

```python
import asyncio
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import json

class SagaStepStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"

@dataclass
class SagaStep:
    step_id: str
    service_name: str
    action: str
    compensation_action: str
    payload: Dict[str, Any]
    status: SagaStepStatus = SagaStepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class SagaDefinition:
    saga_id: str
    saga_type: str
    steps: List[SagaStep]
    timeout: float = 300.0  # 5 minutes default timeout

class SagaOrchestrator:
    """Orchestration-based saga coordinator"""
    
    def __init__(self):
        self.active_sagas: Dict[str, SagaDefinition] = {}
        self.service_clients: Dict[str, 'ServiceClient'] = {}
        self.saga_store = SagaStore()
    
    def register_service(self, service_name: str, client: 'ServiceClient'):
        """Register service client for saga execution"""
        self.service_clients[service_name] = client
    
    async def execute_saga(self, saga_definition: SagaDefinition) -> bool:
        """Execute saga with compensation on failure"""
        self.active_sagas[saga_definition.saga_id] = saga_definition
        
        try:
            print(f"Starting saga {saga_definition.saga_id} of type {saga_definition.saga_type}")
            
            # Persist saga state
            await self.saga_store.save_saga(saga_definition)
            
            # Execute all steps
            completed_steps = []
            
            for step in saga_definition.steps:
                success = await self._execute_step(step)
                
                if success:
                    completed_steps.append(step)
                    await self.saga_store.save_saga(saga_definition)
                else:
                    # Step failed - compensate all completed steps
                    print(f"Saga {saga_definition.saga_id} failed at step {step.step_id}")
                    await self._compensate_saga(completed_steps)
                    return False
            
            print(f"Saga {saga_definition.saga_id} completed successfully")
            await self.saga_store.mark_saga_completed(saga_definition.saga_id)
            return True
            
        except asyncio.TimeoutError:
            print(f"Saga {saga_definition.saga_id} timed out")
            await self._compensate_saga([s for s in saga_definition.steps if s.status == SagaStepStatus.COMPLETED])
            return False
        except Exception as e:
            print(f"Saga {saga_definition.saga_id} failed with error: {e}")
            await self._compensate_saga([s for s in saga_definition.steps if s.status == SagaStepStatus.COMPLETED])
            return False
        finally:
            if saga_definition.saga_id in self.active_sagas:
                del self.active_sagas[saga_definition.saga_id]
    
    async def _execute_step(self, step: SagaStep) -> bool:
        """Execute individual saga step with retries"""
        while step.retry_count <= step.max_retries:
            try:
                print(f"Executing step {step.step_id}: {step.service_name}.{step.action}")
                
                client = self.service_clients.get(step.service_name)
                if not client:
                    raise ValueError(f"No client registered for service {step.service_name}")
                
                result = await client.call_action(step.action, step.payload)
                
                step.status = SagaStepStatus.COMPLETED
                step.result = result
                
                print(f"Step {step.step_id} completed successfully")
                return True
                
            except Exception as e:
                step.retry_count += 1
                step.error = str(e)
                
                print(f"Step {step.step_id} failed (attempt {step.retry_count}): {e}")
                
                if step.retry_count <= step.max_retries:
                    # Exponential backoff
                    delay = 2 ** (step.retry_count - 1)
                    await asyncio.sleep(delay)
                else:
                    step.status = SagaStepStatus.FAILED
                    return False
        
        return False
    
    async def _compensate_saga(self, completed_steps: List[SagaStep]):
        """Execute compensation actions in reverse order"""
        print("Starting saga compensation")
        
        # Execute compensations in reverse order
        for step in reversed(completed_steps):
            await self._compensate_step(step)
    
    async def _compensate_step(self, step: SagaStep):
        """Execute compensation for a single step"""
        if step.status != SagaStepStatus.COMPLETED:
            return
        
        try:
            print(f"Compensating step {step.step_id}: {step.service_name}.{step.compensation_action}")
            
            client = self.service_clients.get(step.service_name)
            if not client:
                print(f"Cannot compensate step {step.step_id} - no client for {step.service_name}")
                return
            
            compensation_payload = {
                "original_payload": step.payload,
                "original_result": step.result,
                "saga_id": step.step_id
            }
            
            await client.call_action(step.compensation_action, compensation_payload)
            
            step.status = SagaStepStatus.COMPENSATED
            print(f"Step {step.step_id} compensated successfully")
            
        except Exception as e:
            print(f"Compensation failed for step {step.step_id}: {e}")
            # Log error but continue with other compensations

# Service Client for Saga
class ServiceClient:
    """Service client for saga orchestration"""
    
    def __init__(self, service_name: str, base_url: str):
        self.service_name = service_name
        self.base_url = base_url
    
    async def call_action(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Call service action"""
        # In real implementation, this would make HTTP calls
        # For demo, we simulate service calls
        
        print(f"  → Calling {self.service_name}.{action} with {payload}")
        
        # Simulate network delay
        await asyncio.sleep(0.1)
        
        # Simulate different outcomes based on action
        if action == "reserve_inventory" and payload.get("quantity", 0) > 100:
            raise Exception("Insufficient inventory")
        
        if action == "process_payment" and payload.get("amount", 0) > 10000:
            raise Exception("Payment declined - amount too high")
        
        # Return success result
        return {
            "success": True,
            "action": action,
            "service": self.service_name,
            "result_id": f"{action}_{int(time.time())}"
        }

# Saga Store for Persistence
class SagaStore:
    """Persistent store for saga state"""
    
    def __init__(self):
        self.sagas: Dict[str, Dict] = {}
    
    async def save_saga(self, saga: SagaDefinition):
        """Save saga state to persistent store"""
        saga_data = {
            "saga_id": saga.saga_id,
            "saga_type": saga.saga_type,
            "timeout": saga.timeout,
            "steps": [
                {
                    "step_id": step.step_id,
                    "service_name": step.service_name,
                    "action": step.action,
                    "compensation_action": step.compensation_action,
                    "payload": step.payload,
                    "status": step.status.value,
                    "result": step.result,
                    "error": step.error,
                    "retry_count": step.retry_count
                }
                for step in saga.steps
            ]
        }
        
        self.sagas[saga.saga_id] = saga_data
    
    async def load_saga(self, saga_id: str) -> Optional[SagaDefinition]:
        """Load saga from persistent store"""
        saga_data = self.sagas.get(saga_id)
        if not saga_data:
            return None
        
        steps = []
        for step_data in saga_data["steps"]:
            step = SagaStep(
                step_id=step_data["step_id"],
                service_name=step_data["service_name"],
                action=step_data["action"],
                compensation_action=step_data["compensation_action"],
                payload=step_data["payload"],
                status=SagaStepStatus(step_data["status"]),
                result=step_data["result"],
                error=step_data["error"],
                retry_count=step_data["retry_count"]
            )
            steps.append(step)
        
        return SagaDefinition(
            saga_id=saga_data["saga_id"],
            saga_type=saga_data["saga_type"],
            steps=steps,
            timeout=saga_data["timeout"]
        )
    
    async def mark_saga_completed(self, saga_id: str):
        """Mark saga as completed"""
        if saga_id in self.sagas:
            self.sagas[saga_id]["status"] = "completed"

# E-commerce Order Saga Example
async def ecommerce_order_saga_example():
    """Example: E-commerce order processing saga"""
    
    # Setup orchestrator
    orchestrator = SagaOrchestrator()
    
    # Register service clients
    orchestrator.register_service("inventory", ServiceClient("inventory", "http://inventory-service"))
    orchestrator.register_service("payment", ServiceClient("payment", "http://payment-service"))
    orchestrator.register_service("shipping", ServiceClient("shipping", "http://shipping-service"))
    orchestrator.register_service("order", ServiceClient("order", "http://order-service"))
    
    # Define order processing saga
    order_saga = SagaDefinition(
        saga_id=f"order_saga_{int(time.time())}",
        saga_type="order_processing",
        steps=[
            SagaStep(
                step_id="reserve_inventory",
                service_name="inventory",
                action="reserve_inventory",
                compensation_action="release_inventory",
                payload={
                    "product_id": "product_123",
                    "quantity": 2,
                    "reservation_timeout": 300
                }
            ),
            SagaStep(
                step_id="create_order",
                service_name="order",
                action="create_order",
                compensation_action="cancel_order",
                payload={
                    "customer_id": "customer_456",
                    "items": [{"product_id": "product_123", "quantity": 2}],
                    "total_amount": 199.99
                }
            ),
            SagaStep(
                step_id="process_payment",
                service_name="payment",
                action="process_payment", 
                compensation_action="refund_payment",
                payload={
                    "customer_id": "customer_456",
                    "amount": 199.99,
                    "payment_method": "credit_card"
                }
            ),
            SagaStep(
                step_id="schedule_shipping",
                service_name="shipping",
                action="schedule_shipping",
                compensation_action="cancel_shipping",
                payload={
                    "order_id": "order_789",
                    "shipping_address": {
                        "street": "123 Main St",
                        "city": "Anytown",
                        "zip": "12345"
                    }
                }
            )
        ]
    )
    
    print("=== E-commerce Order Processing Saga ===")
    success = await orchestrator.execute_saga(order_saga)
    
    print(f"Order saga completed: {success}")
    
    # Example of saga failure (high amount)
    print("\n=== Testing Saga Failure (High Amount) ===")
    high_amount_saga = SagaDefinition(
        saga_id=f"order_saga_fail_{int(time.time())}",
        saga_type="order_processing",
        steps=[
            SagaStep(
                step_id="reserve_inventory",
                service_name="inventory",
                action="reserve_inventory",
                compensation_action="release_inventory",
                payload={
                    "product_id": "expensive_product",
                    "quantity": 1
                }
            ),
            SagaStep(
                step_id="process_payment",
                service_name="payment",
                action="process_payment",
                compensation_action="refund_payment", 
                payload={
                    "customer_id": "customer_456",
                    "amount": 15000,  # This will fail
                    "payment_method": "credit_card"
                }
            )
        ]
    )
    
    success = await orchestrator.execute_saga(high_amount_saga)
    print(f"High amount saga completed: {success}")
```

---

## 4. Eventually Consistent Systems

### Conflict Resolution Strategies

```python
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json

class ConflictResolutionStrategy(Enum):
    LAST_WRITER_WINS = "last_writer_wins"
    FIRST_WRITER_WINS = "first_writer_wins"
    CUSTOM_MERGE = "custom_merge"
    MANUAL_RESOLUTION = "manual_resolution"

@dataclass
class VersionedValue:
    value: Any
    version: int
    timestamp: float
    node_id: str
    vector_clock: Dict[str, int]

class CRDTCounter:
    """Conflict-free Replicated Data Type - G-Counter (Grow-only counter)"""
    
    def __init__(self, node_id: str, nodes: List[str]):
        self.node_id = node_id
        self.counters: Dict[str, int] = {node: 0 for node in nodes}
    
    def increment(self, amount: int = 1):
        """Increment counter on this node"""
        self.counters[self.node_id] += amount
    
    def merge(self, other: 'CRDTCounter'):
        """Merge with another counter (takes maximum of each node's counter)"""
        for node in self.counters:
            if node in other.counters:
                self.counters[node] = max(self.counters[node], other.counters[node])
    
    def value(self) -> int:
        """Get current counter value"""
        return sum(self.counters.values())
    
    def __repr__(self):
        return f"CRDTCounter(node={self.node_id}, value={self.value()}, counters={self.counters})"

class CRDTSet:
    """CRDT Set - Supports add and remove operations"""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.added: Dict[str, Dict[str, float]] = {}  # element -> {node -> timestamp}
        self.removed: Dict[str, Dict[str, float]] = {}  # element -> {node -> timestamp}
    
    def add(self, element: str):
        """Add element to set"""
        if element not in self.added:
            self.added[element] = {}
        self.added[element][self.node_id] = time.time()
    
    def remove(self, element: str):
        """Remove element from set"""
        if element not in self.removed:
            self.removed[element] = {}
        self.removed[element][self.node_id] = time.time()
    
    def contains(self, element: str) -> bool:
        """Check if element is in set"""
        # Element is in set if it was added and not removed (or removed before last add)
        if element not in self.added:
            return False
        
        if element not in self.removed:
            return True
        
        # Check if any add is more recent than any remove
        latest_add = max(self.added[element].values())
        latest_remove = max(self.removed[element].values())
        
        return latest_add > latest_remove
    
    def elements(self) -> set:
        """Get all elements currently in the set"""
        result = set()
        for element in self.added:
            if self.contains(element):
                result.add(element)
        return result
    
    def merge(self, other: 'CRDTSet'):
        """Merge with another CRDT set"""
        # Merge added elements
        for element, node_timestamps in other.added.items():
            if element not in self.added:
                self.added[element] = {}
            for node, timestamp in node_timestamps.items():
                if node not in self.added[element] or timestamp > self.added[element][node]:
                    self.added[element][node] = timestamp
        
        # Merge removed elements
        for element, node_timestamps in other.removed.items():
            if element not in self.removed:
                self.removed[element] = {}
            for node, timestamp in node_timestamps.items():
                if node not in self.removed[element] or timestamp > self.removed[element][node]:
                    self.removed[element][node] = timestamp

class EventuallyConsistentDatabase:
    """Database with eventual consistency and conflict resolution"""
    
    def __init__(self, node_id: str, conflict_strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.LAST_WRITER_WINS):
        self.node_id = node_id
        self.conflict_strategy = conflict_strategy
        self.data: Dict[str, VersionedValue] = {}
        self.vector_clock: Dict[str, int] = {node_id: 0}
        self.conflict_log: List[Dict] = []
        self.replicas: List['EventuallyConsistentDatabase'] = []
    
    def write(self, key: str, value: Any) -> VersionedValue:
        """Write value with versioning"""
        # Update vector clock
        self.vector_clock[self.node_id] += 1
        
        # Create versioned value
        versioned_value = VersionedValue(
            value=value,
            version=self.vector_clock[self.node_id],
            timestamp=time.time(),
            node_id=self.node_id,
            vector_clock=self.vector_clock.copy()
        )
        
        # Handle conflict if key already exists
        if key in self.data:
            resolved_value = self._resolve_conflict(key, versioned_value, self.data[key])
            self.data[key] = resolved_value
        else:
            self.data[key] = versioned_value
        
        # Asynchronously replicate
        asyncio.create_task(self._replicate_write(key, versioned_value))
        
        return versioned_value
    
    def read(self, key: str) -> Optional[Any]:
        """Read current value"""
        versioned_value = self.data.get(key)
        return versioned_value.value if versioned_value else None
    
    async def _replicate_write(self, key: str, value: VersionedValue):
        """Replicate write to other nodes"""
        for replica in self.replicas:
            try:
                await replica.receive_write(key, value)
            except Exception as e:
                print(f"Replication to {replica.node_id} failed: {e}")
    
    async def receive_write(self, key: str, incoming_value: VersionedValue):
        """Receive write from another node"""
        # Update vector clock
        for node, clock in incoming_value.vector_clock.items():
            if node not in self.vector_clock:
                self.vector_clock[node] = 0
            self.vector_clock[node] = max(self.vector_clock[node], clock)
        
        # Handle conflict resolution
        if key in self.data:
            existing_value = self.data[key]
            resolved_value = self._resolve_conflict(key, incoming_value, existing_value)
            self.data[key] = resolved_value
        else:
            self.data[key] = incoming_value
    
    def _resolve_conflict(self, key: str, value1: VersionedValue, value2: VersionedValue) -> VersionedValue:
        """Resolve conflict between two versions"""
        
        # Log the conflict
        conflict_info = {
            "key": key,
            "timestamp": time.time(),
            "node_id": self.node_id,
            "value1": {"value": value1.value, "node": value1.node_id, "timestamp": value1.timestamp},
            "value2": {"value": value2.value, "node": value2.node_id, "timestamp": value2.timestamp},
            "strategy": self.conflict_strategy.value
        }
        self.conflict_log.append(conflict_info)
        
        if self.conflict_strategy == ConflictResolutionStrategy.LAST_WRITER_WINS:
            return value1 if value1.timestamp > value2.timestamp else value2
            
        elif self.conflict_strategy == ConflictResolutionStrategy.FIRST_WRITER_WINS:
            return value2 if value2.timestamp < value1.timestamp else value1
            
        elif self.conflict_strategy == ConflictResolutionStrategy.CUSTOM_MERGE:
            return self._custom_merge(key, value1, value2)
            
        else:  # MANUAL_RESOLUTION
            # Store both values for manual resolution
            return self._create_conflict_value(value1, value2)
    
    def _custom_merge(self, key: str, value1: VersionedValue, value2: VersionedValue) -> VersionedValue:
        """Custom merge logic for specific data types"""
        
        # Example: Merge numeric values by taking sum
        if isinstance(value1.value, (int, float)) and isinstance(value2.value, (int, float)):
            merged_value = value1.value + value2.value
            
            return VersionedValue(
                value=merged_value,
                version=max(value1.version, value2.version) + 1,
                timestamp=time.time(),
                node_id=self.node_id,
                vector_clock=self.vector_clock.copy()
            )
        
        # Example: Merge dictionaries by combining keys
        if isinstance(value1.value, dict) and isinstance(value2.value, dict):
            merged_dict = {**value2.value, **value1.value}  # value1 wins on conflicts
            
            return VersionedValue(
                value=merged_dict,
                version=max(value1.version, value2.version) + 1,
                timestamp=time.time(),
                node_id=self.node_id,
                vector_clock=self.vector_clock.copy()
            )
        
        # Default to last writer wins
        return value1 if value1.timestamp > value2.timestamp else value2
    
    def _create_conflict_value(self, value1: VersionedValue, value2: VersionedValue) -> VersionedValue:
        """Create a conflict value that requires manual resolution"""
        conflict_data = {
            "type": "conflict",
            "options": [
                {"value": value1.value, "node": value1.node_id, "timestamp": value1.timestamp},
                {"value": value2.value, "node": value2.node_id, "timestamp": value2.timestamp}
            ]
        }
        
        return VersionedValue(
            value=conflict_data,
            version=max(value1.version, value2.version) + 1,
            timestamp=time.time(),
            node_id=self.node_id,
            vector_clock=self.vector_clock.copy()
        )
    
    def get_conflicts(self) -> List[Dict]:
        """Get list of conflicts that occurred"""
        return self.conflict_log.copy()

# Shopping Cart CRDT Example
class ShoppingCartCRDT:
    """Shopping cart using CRDTs for eventual consistency"""
    
    def __init__(self, user_id: str, node_id: str):
        self.user_id = user_id
        self.node_id = node_id
        self.items = CRDTSet(node_id)  # Set of item IDs
        self.quantities = {}  # item_id -> CRDTCounter
        self.version = 0
    
    def add_item(self, item_id: str, quantity: int = 1):
        """Add item to cart"""
        self.items.add(item_id)
        
        if item_id not in self.quantities:
            # Create counter for all known nodes
            nodes = [self.node_id] + [replica.node_id for replica in getattr(self, 'replicas', [])]
            self.quantities[item_id] = CRDTCounter(self.node_id, nodes)
        
        self.quantities[item_id].increment(quantity)
        self.version += 1
    
    def remove_item(self, item_id: str):
        """Remove item from cart"""
        self.items.remove(item_id)
        self.version += 1
    
    def get_items(self) -> Dict[str, int]:
        """Get current cart items with quantities"""
        result = {}
        
        for item_id in self.items.elements():
            if item_id in self.quantities:
                quantity = self.quantities[item_id].value()
                if quantity > 0:
                    result[item_id] = quantity
        
        return result
    
    def merge(self, other: 'ShoppingCartCRDT'):
        """Merge with another cart"""
        # Merge item sets
        self.items.merge(other.items)
        
        # Merge quantity counters
        for item_id, counter in other.quantities.items():
            if item_id in self.quantities:
                self.quantities[item_id].merge(counter)
            else:
                self.quantities[item_id] = counter
    
    def __repr__(self):
        return f"ShoppingCart(user={self.user_id}, items={self.get_items()})"

# Example Usage
async def eventual_consistency_example():
    """Demonstrate eventual consistency patterns"""
    
    print("=== CRDT Counter Example ===")
    
    # Multiple nodes with CRDT counters
    nodes = ["node1", "node2", "node3"]
    counters = {node: CRDTCounter(node, nodes) for node in nodes}
    
    # Concurrent increments on different nodes
    counters["node1"].increment(5)
    counters["node2"].increment(3)
    counters["node3"].increment(2)
    
    print("Before merge:")
    for node, counter in counters.items():
        print(f"  {node}: {counter}")
    
    # Merge counters (simulate replication)
    for node in nodes:
        for other_node in nodes:
            if node != other_node:
                counters[node].merge(counters[other_node])
    
    print("\nAfter merge:")
    for node, counter in counters.items():
        print(f"  {node}: {counter}")
    
    print("\n=== Shopping Cart CRDT Example ===")
    
    # User shopping carts on different devices/nodes
    mobile_cart = ShoppingCartCRDT("user123", "mobile")
    web_cart = ShoppingCartCRDT("user123", "web")
    
    # Concurrent operations
    mobile_cart.add_item("item_A", 2)
    mobile_cart.add_item("item_B", 1)
    
    web_cart.add_item("item_A", 1)  # Concurrent addition
    web_cart.add_item("item_C", 3)
    
    print("Before sync:")
    print(f"  Mobile: {mobile_cart}")
    print(f"  Web: {web_cart}")
    
    # Sync carts
    mobile_cart.merge(web_cart)
    web_cart.merge(mobile_cart)
    
    print("\nAfter sync:")
    print(f"  Mobile: {mobile_cart}")
    print(f"  Web: {web_cart}")
    
    print("\n=== Conflict Resolution Example ===")
    
    # Setup databases with different conflict resolution strategies
    db1 = EventuallyConsistentDatabase("db1", ConflictResolutionStrategy.LAST_WRITER_WINS)
    db2 = EventuallyConsistentDatabase("db2", ConflictResolutionStrategy.CUSTOM_MERGE)
    
    db1.replicas = [db2]
    db2.replicas = [db1]
    
    # Concurrent writes to same key
    db1.write("user_profile", {"name": "Alice", "age": 30})
    await asyncio.sleep(0.01)  # Small delay
    db2.write("user_profile", {"name": "Alice", "age": 31, "city": "NYC"})
    
    # Allow replication
    await asyncio.sleep(0.1)
    
    print(f"DB1 result: {db1.read('user_profile')}")
    print(f"DB2 result: {db2.read('user_profile')}")
    
    print("\nConflict logs:")
    for i, conflict in enumerate(db1.get_conflicts() + db2.get_conflicts()):
        print(f"  Conflict {i+1}: {conflict}")
```

---

## Labs and Projects

### Lab 1: ACID vs BASE Comparison
Build and compare ACID and BASE database systems, measuring consistency guarantees vs. availability.

### Lab 2: Two-Phase Commit Implementation
Implement a complete 2PC protocol with coordinator and participant recovery.

### Lab 3: Saga Pattern Implementation
Build both orchestration and choreography-based saga systems for order processing.

### Lab 4: CRDT Implementation
Implement conflict-free replicated data types for collaborative applications.

## Assessment

### Distributed Data Management Project
Design and implement a distributed data management system for a global e-commerce platform:

1. **Consistency Requirements**: Define consistency needs for different data types
2. **Transaction Design**: Implement distributed transactions using appropriate patterns
3. **Conflict Resolution**: Handle concurrent updates with automatic conflict resolution
4. **Performance Analysis**: Measure performance trade-offs of different consistency models

## References

### Essential Reading
- "Designing Data-Intensive Applications" by Martin Kleppmann (Chapters 5-9)
- "Database Internals" by Alex Petrov
- "Distributed Systems: Concepts and Design" by Coulouris et al.

### Research Papers
- "Harvest, Yield, and Scalable Tolerant Systems" (BASE paper)
- "Consensus on Transaction Commit" (2PC analysis)
- "Sagas" (Original saga pattern paper)
- "A comprehensive study of Convergent and Commutative Replicated Data Types" (CRDTs)

---

*Next: [Module 04 - Communication Patterns](../04_COMMUNICATION_PATTERNS/)*