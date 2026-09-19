# Advanced ORM Patterns for Staff Engineers

## Database Connection Management

### Connection Pool Optimization
```python
from sqlalchemy import create_engine, event
from sqlalchemy.pool import QueuePool, StaticPool
import logging

logger = logging.getLogger(__name__)

class DatabaseConnectionManager:
    """Advanced connection management for different environments"""
    
    @staticmethod
    def create_production_engine(database_url: str, **kwargs):
        """Production engine with optimized settings"""
        return create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=20,               # Base connections
            max_overflow=30,            # Additional connections
            pool_recycle=3600,          # Recycle every hour
            pool_pre_ping=True,         # Validate connections
            pool_timeout=30,            # Wait time for connection
            connect_args={
                "connect_timeout": 10,
                "application_name": kwargs.get("app_name", "myapp"),
                "sslmode": "require" if "postgres" in database_url else None
            },
            **kwargs
        )
    
    @staticmethod
    def create_read_replica_engine(database_url: str, **kwargs):
        """Read replica with different pool settings"""
        return create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=10,               # Fewer base connections
            max_overflow=20,            # Read-heavy workload
            pool_recycle=1800,          # More frequent recycle
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": 5,   # Faster timeout for reads
                "application_name": f"{kwargs.get('app_name', 'myapp')}_readonly",
            },
            **kwargs
        )

# Connection monitoring
@event.listens_for(QueuePool, "connect")
def set_connection_settings(dbapi_connection, connection_record):
    """Set connection-level settings"""
    if hasattr(dbapi_connection, 'cursor'):
        with dbapi_connection.cursor() as cursor:
            # PostgreSQL specific optimizations
            cursor.execute("SET statement_timeout = '30s'")
            cursor.execute("SET lock_timeout = '10s'")
            cursor.execute("SET idle_in_transaction_session_timeout = '60s'")

@event.listens_for(QueuePool, "checkout")
def track_connection_checkout(dbapi_connection, connection_record, connection_proxy):
    logger.debug(f"Connection checked out: {id(dbapi_connection)}")

@event.listens_for(QueuePool, "checkin")
def track_connection_checkin(dbapi_connection, connection_record):
    logger.debug(f"Connection checked in: {id(dbapi_connection)}")
```

### Multi-Database Setup (Master-Slave)
```python
from enum import Enum
from contextvars import ContextVar
from typing import Optional

class DatabaseRole(Enum):
    MASTER = "master"
    SLAVE = "slave"

# Context variable to track read/write preference
db_role_context: ContextVar[DatabaseRole] = ContextVar('db_role', default=DatabaseRole.MASTER)

class MultiDatabaseSession:
    """Session manager for master-slave setup"""
    
    def __init__(self, master_engine, slave_engines: list):
        self.master_engine = master_engine
        self.slave_engines = slave_engines
        self.current_slave = 0
        
        self.master_session_maker = sessionmaker(bind=master_engine)
        self.slave_session_makers = [
            sessionmaker(bind=engine) for engine in slave_engines
        ]
    
    def get_session(self, role: Optional[DatabaseRole] = None) -> Session:
        """Get session based on role"""
        role = role or db_role_context.get()
        
        if role == DatabaseRole.MASTER or not self.slave_engines:
            return self.master_session_maker()
        
        # Round-robin slave selection
        slave_maker = self.slave_session_makers[self.current_slave]
        self.current_slave = (self.current_slave + 1) % len(self.slave_session_makers)
        return slave_maker()

# Context managers for explicit role selection
@contextmanager
def use_master_db():
    """Force use of master database"""
    token = db_role_context.set(DatabaseRole.MASTER)
    try:
        yield
    finally:
        db_role_context.reset(token)

@contextmanager
def use_slave_db():
    """Force use of slave database"""
    token = db_role_context.set(DatabaseRole.SLAVE)
    try:
        yield
    finally:
        db_role_context.reset(token)

# Repository with read/write splitting
class ReadWriteSplitRepository(BaseRepository[T]):
    """Repository that automatically splits read/write operations"""
    
    def __init__(self, db_manager: MultiDatabaseSession, model_class: type):
        self.db_manager = db_manager
        self.model_class = model_class
    
    def _get_read_session(self):
        return self.db_manager.get_session(DatabaseRole.SLAVE)
    
    def _get_write_session(self):
        return self.db_manager.get_session(DatabaseRole.MASTER)
    
    def get_by_id(self, id: Any) -> Optional[T]:
        """Read from slave"""
        with self._get_read_session() as session:
            return session.query(self.model_class).filter(
                self.model_class.id == id
            ).first()
    
    def create(self, obj: T) -> T:
        """Write to master"""
        with self._get_write_session() as session:
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return obj
    
    def find_complex_query(self, **filters) -> List[T]:
        """Complex read query - use slave"""
        with self._get_read_session() as session:
            query = session.query(self.model_class)
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    query = query.filter(getattr(self.model_class, key) == value)
            return query.all()
```

## Advanced Query Patterns

### Query Builder Pattern
```python
from typing import Type, List, Optional, Callable
from sqlalchemy.orm import Query
from sqlalchemy import and_, or_, func

class QueryBuilder:
    """Fluent query builder for complex queries"""
    
    def __init__(self, session: Session, model_class: Type):
        self.session = session
        self.model_class = model_class
        self.query = session.query(model_class)
        self._joins = set()
    
    def filter_by(self, **kwargs) -> 'QueryBuilder':
        """Add filter conditions"""
        conditions = []
        for key, value in kwargs.items():
            if hasattr(self.model_class, key):
                if isinstance(value, list):
                    conditions.append(getattr(self.model_class, key).in_(value))
                else:
                    conditions.append(getattr(self.model_class, key) == value)
        
        if conditions:
            self.query = self.query.filter(and_(*conditions))
        return self
    
    def filter_by_range(self, field: str, min_val=None, max_val=None) -> 'QueryBuilder':
        """Add range filter"""
        if hasattr(self.model_class, field):
            attr = getattr(self.model_class, field)
            conditions = []
            if min_val is not None:
                conditions.append(attr >= min_val)
            if max_val is not None:
                conditions.append(attr <= max_val)
            
            if conditions:
                self.query = self.query.filter(and_(*conditions))
        return self
    
    def search(self, field: str, term: str) -> 'QueryBuilder':
        """Add search filter"""
        if hasattr(self.model_class, field):
            attr = getattr(self.model_class, field)
            self.query = self.query.filter(attr.ilike(f"%{term}%"))
        return self
    
    def join_if_needed(self, relationship_attr: str) -> 'QueryBuilder':
        """Join relationship only if not already joined"""
        if relationship_attr not in self._joins:
            if hasattr(self.model_class, relationship_attr):
                rel = getattr(self.model_class, relationship_attr)
                self.query = self.query.join(rel)
                self._joins.add(relationship_attr)
        return self
    
    def order_by_field(self, field: str, desc: bool = False) -> 'QueryBuilder':
        """Add ordering"""
        if hasattr(self.model_class, field):
            attr = getattr(self.model_class, field)
            if desc:
                self.query = self.query.order_by(attr.desc())
            else:
                self.query = self.query.order_by(attr)
        return self
    
    def paginate(self, page: int, per_page: int) -> 'QueryBuilder':
        """Add pagination"""
        offset = (page - 1) * per_page
        self.query = self.query.offset(offset).limit(per_page)
        return self
    
    def with_stats(self, stat_fields: List[str]) -> 'QueryBuilder':
        """Add aggregate statistics"""
        for field in stat_fields:
            if hasattr(self.model_class, field):
                attr = getattr(self.model_class, field)
                self.query = self.query.add_column(func.count(attr).label(f"{field}_count"))
        return self
    
    def build(self) -> Query:
        """Get the final query"""
        return self.query
    
    def all(self) -> List:
        """Execute and return all results"""
        return self.query.all()
    
    def first(self) -> Optional:
        """Execute and return first result"""
        return self.query.first()
    
    def count(self) -> int:
        """Get count of results"""
        return self.query.count()

# Usage example
def search_posts_advanced(
    session: Session,
    title_search: str = None,
    author_ids: List[int] = None,
    date_from: datetime = None,
    date_to: datetime = None,
    is_published: bool = True,
    page: int = 1,
    per_page: int = 20
) -> List[Post]:
    """Advanced post search using query builder"""
    
    builder = QueryBuilder(session, Post)
    
    if title_search:
        builder.search("title", title_search)
    
    if author_ids:
        builder.filter_by(user_id=author_ids)
    
    if date_from or date_to:
        builder.filter_by_range("created_at", date_from, date_to)
    
    return (builder
            .filter_by(is_published=is_published, is_deleted=False)
            .join_if_needed("author")
            .order_by_field("created_at", desc=True)
            .paginate(page, per_page)
            .all())
```

### Dynamic Query Generation
```python
from typing import Dict, Any, List
from sqlalchemy import text
from dataclasses import dataclass

@dataclass
class FilterCriteria:
    field: str
    operator: str  # eq, ne, gt, gte, lt, lte, in, like, between
    value: Any
    join_with: str = "AND"  # AND, OR

class DynamicQueryRepository:
    """Repository with dynamic query generation"""
    
    def __init__(self, session: Session, model_class: Type):
        self.session = session
        self.model_class = model_class
    
    def build_dynamic_query(self, filters: List[FilterCriteria]) -> Query:
        """Build query from filter criteria"""
        query = self.session.query(self.model_class)
        
        if not filters:
            return query
        
        conditions = []
        for filter_criteria in filters:
            condition = self._build_condition(filter_criteria)
            if condition is not None:
                conditions.append(condition)
        
        if conditions:
            # Combine conditions (simplified - in practice, handle OR logic)
            query = query.filter(and_(*conditions))
        
        return query
    
    def _build_condition(self, criteria: FilterCriteria):
        """Build individual condition from criteria"""
        if not hasattr(self.model_class, criteria.field):
            return None
        
        field = getattr(self.model_class, criteria.field)
        
        if criteria.operator == "eq":
            return field == criteria.value
        elif criteria.operator == "ne":
            return field != criteria.value
        elif criteria.operator == "gt":
            return field > criteria.value
        elif criteria.operator == "gte":
            return field >= criteria.value
        elif criteria.operator == "lt":
            return field < criteria.value
        elif criteria.operator == "lte":
            return field <= criteria.value
        elif criteria.operator == "in":
            return field.in_(criteria.value)
        elif criteria.operator == "like":
            return field.ilike(f"%{criteria.value}%")
        elif criteria.operator == "between":
            if isinstance(criteria.value, (list, tuple)) and len(criteria.value) == 2:
                return field.between(criteria.value[0], criteria.value[1])
        
        return None
    
    def search_by_criteria(
        self, 
        filters: List[FilterCriteria],
        order_by: str = None,
        desc: bool = False,
        limit: int = None
    ) -> List:
        """Search using dynamic criteria"""
        query = self.build_dynamic_query(filters)
        
        if order_by and hasattr(self.model_class, order_by):
            field = getattr(self.model_class, order_by)
            if desc:
                query = query.order_by(field.desc())
            else:
                query = query.order_by(field)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()

# Usage example
def search_users_dynamic(session: Session, search_params: Dict[str, Any]) -> List[User]:
    """Search users with dynamic filters"""
    repo = DynamicQueryRepository(session, User)
    
    filters = []
    
    # Build filters from search params
    if "username" in search_params:
        filters.append(FilterCriteria("username", "like", search_params["username"]))
    
    if "is_active" in search_params:
        filters.append(FilterCriteria("is_active", "eq", search_params["is_active"]))
    
    if "created_after" in search_params:
        filters.append(FilterCriteria("created_at", "gte", search_params["created_after"]))
    
    if "follower_count_min" in search_params:
        filters.append(FilterCriteria("follower_count", "gte", search_params["follower_count_min"]))
    
    return repo.search_by_criteria(
        filters,
        order_by=search_params.get("order_by", "created_at"),
        desc=search_params.get("desc", True),
        limit=search_params.get("limit", 100)
    )
```

## Performance Optimization Patterns

### Query Result Caching
```python
import hashlib
import json
import redis
from typing import Optional, Any, Callable
from functools import wraps

class QueryCache:
    """Redis-based query result caching"""
    
    def __init__(self, redis_client: redis.Redis, default_ttl: int = 3600):
        self.redis_client = redis_client
        self.default_ttl = default_ttl
    
    def _generate_cache_key(self, query_str: str, params: dict) -> str:
        """Generate cache key from query and parameters"""
        cache_data = {
            "query": query_str,
            "params": sorted(params.items()) if params else []
        }
        cache_string = json.dumps(cache_data, sort_keys=True)
        return f"query_cache:{hashlib.md5(cache_string.encode()).hexdigest()}"
    
    def get_cached_result(self, query_str: str, params: dict = None) -> Optional[Any]:
        """Get cached query result"""
        cache_key = self._generate_cache_key(query_str, params or {})
        cached_data = self.redis_client.get(cache_key)
        
        if cached_data:
            return json.loads(cached_data)
        return None
    
    def cache_result(self, query_str: str, result: Any, params: dict = None, ttl: int = None):
        """Cache query result"""
        cache_key = self._generate_cache_key(query_str, params or {})
        cache_ttl = ttl or self.default_ttl
        
        # Serialize result (in production, use more sophisticated serialization)
        serialized_result = json.dumps(result, default=str)
        self.redis_client.setex(cache_key, cache_ttl, serialized_result)
    
    def invalidate_pattern(self, pattern: str):
        """Invalidate cache keys matching pattern"""
        keys = self.redis_client.keys(f"query_cache:*{pattern}*")
        if keys:
            self.redis_client.delete(*keys)

def cached_query(cache: QueryCache, ttl: int = None, invalidation_tags: List[str] = None):
    """Decorator for caching query results"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and args
            func_name = f"{func.__module__}.{func.__name__}"
            cache_params = {
                "args": args,
                "kwargs": kwargs
            }
            
            # Try to get from cache
            cached_result = cache.get_cached_result(func_name, cache_params)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.cache_result(func_name, result, cache_params, ttl)
            
            return result
        
        wrapper.invalidation_tags = invalidation_tags or []
        return wrapper
    
    return decorator

# Usage in repository
class CachedUserRepository(UserRepository):
    """User repository with caching"""
    
    def __init__(self, session: Session, cache: QueryCache):
        super().__init__(session)
        self.cache = cache
    
    @cached_query(cache, ttl=1800, invalidation_tags=["user"])
    def get_user_profile(self, user_id: int) -> dict:
        """Get user profile with caching"""
        user = self.get_by_id(user_id)
        if not user:
            return {}
        
        stats = self.get_user_stats(user_id)
        return {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "follower_count": user.follower_count,
            "post_count": stats.get("post_count", 0),
            "is_verified": user.is_verified
        }
    
    def update_user(self, user_id: int, data: dict) -> Optional[User]:
        """Update user and invalidate cache"""
        result = super().update(user_id, data)
        if result:
            # Invalidate user-related caches
            self.cache.invalidate_pattern(f"user")
        return result
```

### Batch Loading Pattern
```python
from typing import Dict, List, Set
from collections import defaultdict
import asyncio

class BatchLoader:
    """Batch loader to solve N+1 query problems"""
    
    def __init__(self, session: Session):
        self.session = session
        self._pending_loads: Dict[str, Set[Any]] = defaultdict(set)
        self._load_functions: Dict[str, Callable] = {}
    
    def register_loader(self, name: str, load_function: Callable):
        """Register a batch load function"""
        self._load_functions[name] = load_function
    
    def add_to_batch(self, loader_name: str, key: Any):
        """Add key to pending batch"""
        self._pending_loads[loader_name].add(key)
    
    def execute_batches(self) -> Dict[str, Dict[Any, Any]]:
        """Execute all pending batch loads"""
        results = {}
        
        for loader_name, keys in self._pending_loads.items():
            if keys and loader_name in self._load_functions:
                load_func = self._load_functions[loader_name]
                batch_results = load_func(list(keys))
                results[loader_name] = batch_results
        
        # Clear pending loads
        self._pending_loads.clear()
        return results

class BatchUserRepository:
    """Repository with batch loading capabilities"""
    
    def __init__(self, session: Session):
        self.session = session
        self.batch_loader = BatchLoader(session)
        self._setup_loaders()
    
    def _setup_loaders(self):
        """Setup batch loading functions"""
        self.batch_loader.register_loader("users", self._batch_load_users)
        self.batch_loader.register_loader("user_posts", self._batch_load_user_posts)
        self.batch_loader.register_loader("user_stats", self._batch_load_user_stats)
    
    def _batch_load_users(self, user_ids: List[int]) -> Dict[int, User]:
        """Batch load users by IDs"""
        users = self.session.query(User).filter(User.id.in_(user_ids)).all()
        return {user.id: user for user in users}
    
    def _batch_load_user_posts(self, user_ids: List[int]) -> Dict[int, List[Post]]:
        """Batch load posts for multiple users"""
        posts = self.session.query(Post).filter(
            and_(Post.user_id.in_(user_ids), Post.is_deleted == False)
        ).all()
        
        result = defaultdict(list)
        for post in posts:
            result[post.user_id].append(post)
        return dict(result)
    
    def _batch_load_user_stats(self, user_ids: List[int]) -> Dict[int, dict]:
        """Batch load statistics for multiple users"""
        # Get post counts
        post_counts = self.session.query(
            Post.user_id,
            func.count(Post.id).label("post_count")
        ).filter(
            and_(Post.user_id.in_(user_ids), Post.is_deleted == False)
        ).group_by(Post.user_id).all()
        
        stats = {}
        for user_id, count in post_counts:
            stats[user_id] = {"post_count": count}
        
        # Fill in missing users
        for user_id in user_ids:
            if user_id not in stats:
                stats[user_id] = {"post_count": 0}
        
        return stats
    
    def get_users_with_data(self, user_ids: List[int]) -> List[dict]:
        """Get users with posts and stats in single batch"""
        # Add to batch
        for user_id in user_ids:
            self.batch_loader.add_to_batch("users", user_id)
            self.batch_loader.add_to_batch("user_posts", user_id)
            self.batch_loader.add_to_batch("user_stats", user_id)
        
        # Execute all batches
        batch_results = self.batch_loader.execute_batches()
        
        users_data = batch_results.get("users", {})
        posts_data = batch_results.get("user_posts", {})
        stats_data = batch_results.get("user_stats", {})
        
        # Combine results
        result = []
        for user_id in user_ids:
            if user_id in users_data:
                user = users_data[user_id]
                result.append({
                    "user": user,
                    "posts": posts_data.get(user_id, []),
                    "stats": stats_data.get(user_id, {})
                })
        
        return result
```

## Transaction Management Patterns

### Saga Pattern Implementation
```python
from typing import List, Callable, Any, Dict
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class SagaStepStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"

@dataclass
class SagaStep:
    name: str
    action: Callable
    compensation: Callable
    status: SagaStepStatus = SagaStepStatus.PENDING
    result: Any = None
    error: Exception = None

class Saga:
    """Saga pattern implementation for distributed transactions"""
    
    def __init__(self, name: str):
        self.name = name
        self.steps: List[SagaStep] = []
        self.executed_steps: List[SagaStep] = []
    
    def add_step(self, name: str, action: Callable, compensation: Callable) -> 'Saga':
        """Add step to saga"""
        step = SagaStep(name=name, action=action, compensation=compensation)
        self.steps.append(step)
        return self
    
    def execute(self) -> bool:
        """Execute saga steps"""
        try:
            # Execute all steps
            for step in self.steps:
                logger.info(f"Executing saga step: {step.name}")
                
                try:
                    step.result = step.action()
                    step.status = SagaStepStatus.COMPLETED
                    self.executed_steps.append(step)
                    logger.info(f"Saga step completed: {step.name}")
                
                except Exception as e:
                    step.error = e
                    step.status = SagaStepStatus.FAILED
                    logger.error(f"Saga step failed: {step.name}, error: {e}")
                    
                    # Compensate already executed steps
                    self._compensate()
                    return False
            
            logger.info(f"Saga completed successfully: {self.name}")
            return True
        
        except Exception as e:
            logger.error(f"Saga execution failed: {self.name}, error: {e}")
            self._compensate()
            return False
    
    def _compensate(self):
        """Execute compensation for completed steps in reverse order"""
        logger.info(f"Starting compensation for saga: {self.name}")
        
        # Reverse order compensation
        for step in reversed(self.executed_steps):
            if step.status == SagaStepStatus.COMPLETED:
                try:
                    logger.info(f"Compensating step: {step.name}")
                    step.compensation()
                    step.status = SagaStepStatus.COMPENSATED
                    logger.info(f"Step compensated: {step.name}")
                
                except Exception as e:
                    logger.error(f"Compensation failed for step: {step.name}, error: {e}")

# Example: User registration saga
class UserRegistrationSaga:
    """Saga for user registration process"""
    
    def __init__(self, session_factory):
        self.session_factory = session_factory
    
    def create_user_account(self, user_data: dict) -> dict:
        """Create user account step"""
        with UnitOfWork(self.session_factory) as uow:
            user_repo = uow.get_repository(UserRepository, User)
            
            user = User(**user_data)
            created_user = user_repo.create(user)
            uow.commit()
            
            return {"user_id": created_user.id}
    
    def compensate_user_account(self, result: dict):
        """Compensate user account creation"""
        if result and "user_id" in result:
            with UnitOfWork(self.session_factory) as uow:
                user_repo = uow.get_repository(UserRepository, User)
                user_repo.delete(result["user_id"])
                uow.commit()
    
    def send_welcome_email(self, result: dict) -> dict:
        """Send welcome email step"""
        # Simulate email sending
        logger.info(f"Sending welcome email to user: {result['user_id']}")
        return {"email_sent": True}
    
    def compensate_welcome_email(self, result: dict):
        """Compensate welcome email (mark as cancelled)"""
        logger.info("Welcome email compensation - marking as cancelled")
    
    def create_user_profile(self, result: dict) -> dict:
        """Create user profile step"""
        with UnitOfWork(self.session_factory) as uow:
            # Create profile record
            profile_data = {
                "user_id": result["user_id"],
                "status": "active",
                "preferences": {}
            }
            logger.info(f"Creating user profile: {profile_data}")
            return {"profile_created": True}
    
    def compensate_user_profile(self, result: dict):
        """Compensate user profile creation"""
        logger.info("User profile compensation - deleting profile")
    
    def execute_registration(self, user_data: dict) -> bool:
        """Execute complete user registration saga"""
        saga = Saga("user_registration")
        
        # Build saga chain with closure to capture context
        user_result = {}
        
        def create_user():
            user_result.update(self.create_user_account(user_data))
            return user_result
        
        def compensate_user():
            self.compensate_user_account(user_result)
        
        def send_email():
            return self.send_welcome_email(user_result)
        
        def compensate_email():
            self.compensate_welcome_email(user_result)
        
        def create_profile():
            return self.create_user_profile(user_result)
        
        def compensate_profile():
            self.compensate_user_profile(user_result)
        
        # Add steps to saga
        saga.add_step("create_user", create_user, compensate_user)
        saga.add_step("send_email", send_email, compensate_email)
        saga.add_step("create_profile", create_profile, compensate_profile)
        
        return saga.execute()
```

### Optimistic Locking Pattern
```python
from sqlalchemy import Column, Integer
from sqlalchemy.orm.exc import StaleDataError

class VersionedModel:
    """Base class for models with optimistic locking"""
    
    version = Column(Integer, default=1, nullable=False)
    
    def increment_version(self):
        """Increment version for optimistic locking"""
        self.version += 1

class OptimisticLockingRepository(BaseRepository[T]):
    """Repository with optimistic locking support"""
    
    def update_with_version_check(self, id: Any, data: dict, expected_version: int) -> Optional[T]:
        """Update with optimistic locking"""
        try:
            # Get current entity
            entity = self.get_by_id(id)
            if not entity:
                return None
            
            # Check version
            if entity.version != expected_version:
                raise StaleDataError(
                    f"Entity version mismatch. Expected: {expected_version}, "
                    f"Current: {entity.version}"
                )
            
            # Update data
            for key, value in data.items():
                if hasattr(entity, key) and key != "version":
                    setattr(entity, key, value)
            
            # Increment version
            entity.increment_version()
            
            self.session.commit()
            self.session.refresh(entity)
            return entity
        
        except StaleDataError:
            self.session.rollback()
            raise
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating entity {id}: {e}")
            raise

# Service layer with retry logic for optimistic locking
class VersionedUserService:
    """User service with optimistic locking and retry"""
    
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.max_retries = 3
    
    def update_user_with_retry(self, user_id: int, data: dict, expected_version: int) -> UserResponse:
        """Update user with optimistic locking and retry"""
        for attempt in range(self.max_retries):
            try:
                with UnitOfWork(self.session_factory) as uow:
                    repo = OptimisticLockingRepository(uow.session, User)
                    
                    updated_user = repo.update_with_version_check(
                        user_id, data, expected_version
                    )
                    
                    if not updated_user:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="User not found"
                        )
                    
                    uow.commit()
                    return UserResponse.from_orm(updated_user)
            
            except StaleDataError:
                if attempt == self.max_retries - 1:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Update conflict. Please refresh and try again."
                    )
                
                # Wait and retry with fresh version
                time.sleep(0.1 * (2 ** attempt))  # Exponential backoff
                
                # Get fresh version
                with UnitOfWork(self.session_factory) as uow:
                    repo = BaseRepository(uow.session, User)
                    fresh_user = repo.get_by_id(user_id)
                    if fresh_user:
                        expected_version = fresh_user.version
```

These advanced patterns provide staff engineers with sophisticated tools for building robust, scalable applications that handle complex data access scenarios effectively.