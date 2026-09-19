# SQLAlchemy Client-Side Features Guide

## Overview
SQLAlchemy is Python's most popular SQL toolkit and Object-Relational Mapping (ORM) library. It provides both high-level ORM capabilities and low-level database access.

## Architecture Layers

### 1. Core Layer (SQL Expression Language)
Low-level database access and SQL generation.

```python
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, select

# Engine - manages database connections
engine = create_engine("postgresql://user:pass@localhost/db")

# MetaData - catalog of database structure
metadata = MetaData()

# Table definition
users = Table('users', metadata,
    Column('id', Integer, primary_key=True),
    Column('username', String(50)),
    Column('email', String(100))
)

# SQL expression
stmt = select(users).where(users.c.username == 'john')

# Execute query
with engine.connect() as conn:
    result = conn.execute(stmt)
    for row in result:
        print(row)
```

### 2. ORM Layer
Object-relational mapping with Python classes.

```python
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(50))
    email = Column(String(100))

# Session factory
Session = sessionmaker(bind=engine)
session = Session()

# ORM queries
user = session.query(User).filter_by(username='john').first()
all_users = session.query(User).all()
```

## Key Features by Category

### 1. Database Engines & Connections

#### Engine Creation
```python
# Basic engine
engine = create_engine("sqlite:///example.db")

# PostgreSQL with connection pool
engine = create_engine(
    "postgresql://user:pass@localhost/db",
    pool_size=20,
    max_overflow=30,
    pool_recycle=3600
)

# MySQL with specific options
engine = create_engine(
    "mysql+pymysql://user:pass@localhost/db",
    connect_args={"charset": "utf8mb4"}
)
```

#### Connection Management
```python
# Direct connection
with engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM users"))

# Connection pooling (automatic)
# Engine handles connection reuse, pooling, and cleanup
```

### 2. Model Definition Features

#### Basic Model Structure
```python
class User(Base):
    __tablename__ = 'users'
    
    # Primary key
    id = Column(Integer, primary_key=True)
    
    # Basic columns with constraints
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    
    # Default values
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # String representation
    def __repr__(self):
        return f"<User(username='{self.username}')>"
```

#### Column Types & Options
```python
class Product(Base):
    __tablename__ = 'products'
    
    # Numeric types
    id = Column(Integer, primary_key=True)
    price = Column(Numeric(10, 2))  # Decimal with precision
    quantity = Column(BigInteger)
    rating = Column(Float)
    
    # String types
    name = Column(String(100))      # Variable length
    description = Column(Text)      # Unlimited text
    sku = Column(CHAR(10))         # Fixed length
    
    # Date/Time types
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_on = Column(Date)
    updated_at = Column(Time)
    
    # JSON type (PostgreSQL)
    metadata = Column(JSON)
    
    # Boolean
    is_available = Column(Boolean, default=True)
    
    # Constraints
    category = Column(String(50), nullable=False, index=True)
    unique_code = Column(String(20), unique=True)
```

### 3. Relationships

#### One-to-Many
```python
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(50))
    
    # One-to-many relationship
    posts = relationship("Post", back_populates="author")

class Post(Base):
    __tablename__ = 'posts'
    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    user_id = Column(Integer, ForeignKey('users.id'))
    
    # Many-to-one relationship
    author = relationship("User", back_populates="posts")
```

#### Many-to-Many
```python
# Association table
user_role_association = Table('user_roles', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('role_id', Integer, ForeignKey('roles.id'))
)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    
    # Many-to-many relationship
    roles = relationship("Role", secondary=user_role_association, back_populates="users")

class Role(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    
    users = relationship("User", secondary=user_role_association, back_populates="roles")
```

#### Self-Referential
```python
class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    parent_id = Column(Integer, ForeignKey('categories.id'))
    
    # Self-referential relationships
    children = relationship("Category", backref=backref('parent', remote_side=[id]))
```

### 4. Querying Features

#### Basic Queries
```python
# Get by primary key
user = session.get(User, 1)

# Simple filters
users = session.query(User).filter(User.is_active == True).all()
user = session.query(User).filter_by(username='john').first()

# Multiple conditions
active_users = session.query(User).filter(
    User.is_active == True,
    User.created_at > datetime(2024, 1, 1)
).all()
```

#### Advanced Filtering
```python
from sqlalchemy import and_, or_, not_

# Logical operators
users = session.query(User).filter(
    and_(User.is_active == True, User.email.like('%@gmail.com'))
).all()

users = session.query(User).filter(
    or_(User.username == 'admin', User.is_staff == True)
).all()

# In/Not In
user_ids = [1, 2, 3, 4]
users = session.query(User).filter(User.id.in_(user_ids)).all()

# Null checks
inactive_users = session.query(User).filter(User.last_login.is_(None)).all()

# String operations
gmail_users = session.query(User).filter(User.email.like('%@gmail.com')).all()
case_insensitive = session.query(User).filter(User.username.ilike('john')).all()

# Numeric comparisons
recent_posts = session.query(Post).filter(Post.view_count > 100).all()
```

#### Ordering and Limiting
```python
# Ordering
users = session.query(User).order_by(User.created_at.desc()).all()
users = session.query(User).order_by(User.username.asc(), User.created_at.desc()).all()

# Limiting and pagination
first_10 = session.query(User).limit(10).all()
page_2 = session.query(User).offset(20).limit(10).all()

# Distinct
unique_categories = session.query(Product.category).distinct().all()
```

#### Joins
```python
# Implicit join (through relationship)
posts_with_authors = session.query(Post).join(User).all()

# Explicit join
posts = session.query(Post, User).join(User, Post.user_id == User.id).all()

# Outer join
all_users_with_posts = session.query(User).outerjoin(Post).all()

# Join with filter
active_user_posts = session.query(Post).join(User).filter(User.is_active == True).all()
```

### 5. Aggregation & Grouping

#### Aggregate Functions
```python
from sqlalchemy import func

# Count
user_count = session.query(func.count(User.id)).scalar()
post_count = session.query(Post).count()

# Sum, Average, Min, Max
total_views = session.query(func.sum(Post.view_count)).scalar()
avg_views = session.query(func.avg(Post.view_count)).scalar()
max_price = session.query(func.max(Product.price)).scalar()

# Group by
post_counts = session.query(
    User.username, 
    func.count(Post.id).label('post_count')
).join(Post).group_by(User.username).all()

# Having clause
popular_users = session.query(
    User.username,
    func.count(Post.id).label('post_count')
).join(Post).group_by(User.username).having(
    func.count(Post.id) > 5
).all()
```

### 6. Advanced Query Features

#### Subqueries
```python
# Scalar subquery
avg_view_count = session.query(func.avg(Post.view_count)).scalar_subquery()
above_avg_posts = session.query(Post).filter(Post.view_count > avg_view_count).all()

# Correlated subquery
users_with_posts = session.query(User).filter(
    session.query(Post).filter(Post.user_id == User.id).exists()
).all()
```

#### Window Functions
```python
# Row number
ranked_posts = session.query(
    Post.title,
    func.row_number().over(
        partition_by=Post.user_id,
        order_by=Post.created_at.desc()
    ).label('rank')
).all()

# Running totals
cumulative_views = session.query(
    Post.title,
    Post.view_count,
    func.sum(Post.view_count).over(
        order_by=Post.created_at
    ).label('cumulative_views')
).all()
```

#### Common Table Expressions (CTEs)
```python
# Recursive CTE for hierarchical data
categories_cte = session.query(Category).filter(Category.parent_id.is_(None)).cte(recursive=True)

categories_alias = aliased(Category)
categories_cte = categories_cte.union_all(
    session.query(categories_alias).filter(
        categories_alias.parent_id == categories_cte.c.id
    )
)

all_categories = session.query(categories_cte).all()
```

### 7. Data Modification

#### Creating Records
```python
# Single record
user = User(username='john', email='john@example.com')
session.add(user)
session.commit()

# Multiple records
users = [
    User(username='alice', email='alice@example.com'),
    User(username='bob', email='bob@example.com')
]
session.add_all(users)
session.commit()

# Bulk insert
session.bulk_insert_mappings(User, [
    {'username': 'user1', 'email': 'user1@example.com'},
    {'username': 'user2', 'email': 'user2@example.com'}
])
```

#### Updating Records
```python
# Update single record
user = session.get(User, 1)
user.email = 'newemail@example.com'
session.commit()

# Bulk update
session.query(User).filter(User.is_active == False).update({
    'last_login': None
})
session.commit()

# Bulk update mappings
session.bulk_update_mappings(User, [
    {'id': 1, 'username': 'updated_user1'},
    {'id': 2, 'username': 'updated_user2'}
])
```

#### Deleting Records
```python
# Delete single record
user = session.get(User, 1)
session.delete(user)
session.commit()

# Bulk delete
session.query(User).filter(User.is_active == False).delete()
session.commit()
```

### 8. Transaction Management

#### Session Lifecycle
```python
# Basic session usage
session = Session()
try:
    user = User(username='john')
    session.add(user)
    session.commit()
except Exception:
    session.rollback()
    raise
finally:
    session.close()

# Context manager
with Session() as session:
    user = User(username='john')
    session.add(user)
    session.commit()
```

#### Transaction Control
```python
# Manual transaction
session.begin()
try:
    # Multiple operations
    user = User(username='john')
    session.add(user)
    
    post = Post(title='First Post', author=user)
    session.add(post)
    
    session.commit()
except Exception:
    session.rollback()
    raise

# Savepoints
session.begin()
try:
    session.add(user1)
    savepoint = session.begin_nested()  # Savepoint
    try:
        session.add(user2)
        savepoint.commit()
    except Exception:
        savepoint.rollback()
    session.commit()
except Exception:
    session.rollback()
```

### 9. Performance Features

#### Eager Loading
```python
# Joinedload - single query with JOIN
users_with_posts = session.query(User).options(
    joinedload(User.posts)
).all()

# Selectinload - separate optimized query
users_with_posts = session.query(User).options(
    selectinload(User.posts)
).all()

# Subqueryload - subquery for loading
users_with_posts = session.query(User).options(
    subqueryload(User.posts)
).all()
```

#### Query Optimization
```python
# Only load specific columns
usernames = session.query(User.username).all()

# Load specific attributes of related objects
users_with_post_titles = session.query(User).options(
    selectinload(User.posts).load_only(Post.title)
).all()

# Defer loading of large columns
users = session.query(User).options(defer(User.bio)).all()
```

### 10. Advanced Features

#### Hybrid Properties
```python
from sqlalchemy.ext.hybrid import hybrid_property

class User(Base):
    __tablename__ = 'users'
    first_name = Column(String(50))
    last_name = Column(String(50))
    
    @hybrid_property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @full_name.expression
    def full_name(cls):
        return func.concat(cls.first_name, ' ', cls.last_name)

# Usage
user = User(first_name='John', last_name='Doe')
print(user.full_name)  # "John Doe"

# In queries
users = session.query(User).filter(User.full_name == 'John Doe').all()
```

#### Event System
```python
from sqlalchemy import event

@event.listens_for(User, 'before_insert')
def set_created_at(mapper, connection, target):
    target.created_at = datetime.utcnow()

@event.listens_for(User, 'before_update')
def set_updated_at(mapper, connection, target):
    target.updated_at = datetime.utcnow()
```

#### Custom Types
```python
from sqlalchemy.types import TypeDecorator, String
import json

class JSONType(TypeDecorator):
    impl = String
    
    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return value
    
    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return value

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    preferences = Column(JSONType)
```

### 11. Connection Pooling & Configuration

#### Pool Configuration
```python
# QueuePool (default for most databases)
engine = create_engine(
    "postgresql://user:pass@localhost/db",
    pool_size=20,           # Number of connections to maintain
    max_overflow=30,        # Additional connections when needed
    pool_timeout=30,        # Seconds to wait for connection
    pool_recycle=3600,      # Recycle connections after 1 hour
    pool_pre_ping=True      # Validate connections before use
)

# StaticPool (for SQLite)
engine = create_engine(
    "sqlite:///example.db",
    poolclass=StaticPool,
    connect_args={'check_same_thread': False}
)

# NullPool (no connection pooling)
engine = create_engine(
    "postgresql://user:pass@localhost/db",
    poolclass=NullPool
)
```

### 12. Sharding & Multi-Database Support

#### Basic Sharding Setup
```python
# Multiple database engines for shards
shard_engines = {
    'shard_1': create_engine('postgresql://user:pass@shard1/db'),
    'shard_2': create_engine('postgresql://user:pass@shard2/db'),
    'shard_3': create_engine('postgresql://user:pass@shard3/db'),
}

class ShardedSession:
    def __init__(self, engines):
        self.engines = engines
        self.sessions = {
            name: sessionmaker(bind=engine)() 
            for name, engine in engines.items()
        }
    
    def get_session(self, shard_key):
        """Route to appropriate shard based on key"""
        shard_name = self._route_shard(shard_key)
        return self.sessions[shard_name]
    
    def _route_shard(self, shard_key):
        """Simple hash-based routing"""
        shard_num = hash(shard_key) % len(self.engines)
        return f'shard_{shard_num + 1}'

# Usage
sharded_session = ShardedSession(shard_engines)
user_session = sharded_session.get_session(user_id=12345)
user = user_session.query(User).filter_by(id=12345).first()
```

#### Sharding with Routing Class
```python
class DatabaseRouter:
    """Routes queries to appropriate database shards"""
    
    def __init__(self, shard_config):
        self.shards = {}
        self.session_makers = {}
        
        for shard_name, config in shard_config.items():
            engine = create_engine(config['url'], **config.get('options', {}))
            self.shards[shard_name] = engine
            self.session_makers[shard_name] = sessionmaker(bind=engine)
    
    def route_by_user_id(self, user_id):
        """Route by user ID using hash"""
        shard_num = user_id % len(self.shards)
        return list(self.shards.keys())[shard_num]
    
    def route_by_hash(self, key):
        """Route by string key hash"""
        shard_num = hash(key) % len(self.shards)
        return list(self.shards.keys())[shard_num]
    
    def route_by_range(self, value, ranges):
        """Route by value ranges"""
        for shard_name, (min_val, max_val) in ranges.items():
            if min_val <= value <= max_val:
                return shard_name
        raise ValueError(f"No shard found for value {value}")
    
    def get_session(self, shard_name):
        """Get session for specific shard"""
        return self.session_makers[shard_name]()
    
    def get_all_sessions(self):
        """Get sessions for all shards"""
        return [maker() for maker in self.session_makers.values()]

# Configuration
shard_config = {
    'users_1': {
        'url': 'postgresql://user:pass@shard1/users',
        'options': {'pool_size': 10}
    },
    'users_2': {
        'url': 'postgresql://user:pass@shard2/users', 
        'options': {'pool_size': 10}
    },
    'users_3': {
        'url': 'postgresql://user:pass@shard3/users',
        'options': {'pool_size': 10}
    }
}

router = DatabaseRouter(shard_config)
```

#### Sharded Repository Pattern
```python
class ShardedUserRepository:
    """Repository that works with sharded data"""
    
    def __init__(self, router):
        self.router = router
    
    def get_user(self, user_id):
        """Get user from appropriate shard"""
        shard_name = self.router.route_by_user_id(user_id)
        session = self.router.get_session(shard_name)
        
        try:
            return session.query(User).filter_by(id=user_id).first()
        finally:
            session.close()
    
    def create_user(self, user_data):
        """Create user in appropriate shard"""
        user_id = user_data['id']  # Assuming ID is pre-generated
        shard_name = self.router.route_by_user_id(user_id)
        session = self.router.get_session(shard_name)
        
        try:
            user = User(**user_data)
            session.add(user)
            session.commit()
            return user
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_users_by_range(self, min_id, max_id):
        """Get users across multiple shards"""
        all_users = []
        
        # Query all shards (could be optimized to only relevant shards)
        for session in self.router.get_all_sessions():
            try:
                users = session.query(User).filter(
                    User.id.between(min_id, max_id)
                ).all()
                all_users.extend(users)
            finally:
                session.close()
        
        return all_users
    
    def count_users_global(self):
        """Count users across all shards"""
        total_count = 0
        
        for session in self.router.get_all_sessions():
            try:
                count = session.query(User).count()
                total_count += count
            finally:
                session.close()
        
        return total_count

# Usage
repo = ShardedUserRepository(router)
user = repo.get_user(12345)
total_users = repo.count_users_global()
```

#### Consistent Hashing for Sharding
```python
import hashlib
import bisect

class ConsistentHashRouter:
    """Consistent hashing for better shard distribution"""
    
    def __init__(self, shard_configs, replicas=3):
        self.replicas = replicas
        self.ring = {}
        self.sorted_keys = []
        self.shards = {}
        self.session_makers = {}
        
        # Create engines and sessions
        for shard_name, config in shard_configs.items():
            engine = create_engine(config['url'])
            self.shards[shard_name] = engine
            self.session_makers[shard_name] = sessionmaker(bind=engine)
            
            # Add to consistent hash ring
            self._add_shard_to_ring(shard_name)
    
    def _add_shard_to_ring(self, shard_name):
        """Add shard to consistent hash ring"""
        for i in range(self.replicas):
            key = self._hash(f"{shard_name}:{i}")
            self.ring[key] = shard_name
            bisect.insort(self.sorted_keys, key)
    
    def _hash(self, key):
        """Hash function for consistent hashing"""
        return int(hashlib.md5(str(key).encode()).hexdigest(), 16)
    
    def get_shard(self, key):
        """Get shard for given key using consistent hashing"""
        if not self.ring:
            return None
        
        hash_key = self._hash(key)
        
        # Find the first shard clockwise from hash_key
        idx = bisect.bisect_right(self.sorted_keys, hash_key)
        if idx == len(self.sorted_keys):
            idx = 0
        
        return self.ring[self.sorted_keys[idx]]
    
    def get_session(self, key):
        """Get session for key"""
        shard_name = self.get_shard(key)
        return self.session_makers[shard_name]()
    
    def add_shard(self, shard_name, config):
        """Add new shard (for scaling)"""
        engine = create_engine(config['url'])
        self.shards[shard_name] = engine
        self.session_makers[shard_name] = sessionmaker(bind=engine)
        self._add_shard_to_ring(shard_name)
    
    def remove_shard(self, shard_name):
        """Remove shard (for maintenance)"""
        # Remove from ring
        for i in range(self.replicas):
            key = self._hash(f"{shard_name}:{i}")
            if key in self.ring:
                del self.ring[key]
                self.sorted_keys.remove(key)
        
        # Clean up connections
        if shard_name in self.shards:
            self.shards[shard_name].dispose()
            del self.shards[shard_name]
            del self.session_makers[shard_name]

# Usage
consistent_router = ConsistentHashRouter(shard_config)
session = consistent_router.get_session("user_12345")
```

#### Cross-Shard Queries and Transactions
```python
class CrossShardOperations:
    """Handle operations that span multiple shards"""
    
    def __init__(self, router):
        self.router = router
    
    def search_users_global(self, search_term, limit=100):
        """Search across all shards"""
        results = []
        
        for shard_name in self.router.shards.keys():
            session = self.router.get_session(shard_name)
            try:
                users = session.query(User).filter(
                    User.username.ilike(f"%{search_term}%")
                ).limit(limit).all()
                results.extend(users)
            finally:
                session.close()
        
        # Sort and limit final results
        results.sort(key=lambda u: u.username)
        return results[:limit]
    
    def transfer_user_to_different_shard(self, user_id, target_shard):
        """Move user data between shards (complex operation)"""
        # Get user from current shard
        source_shard = self.router.route_by_user_id(user_id)
        source_session = self.router.get_session(source_shard)
        target_session = self.router.get_session(target_shard)
        
        try:
            # Get user data
            user = source_session.query(User).filter_by(id=user_id).first()
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Copy to target shard
            user_data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                # ... other fields
            }
            new_user = User(**user_data)
            target_session.add(new_user)
            target_session.commit()
            
            # Remove from source shard
            source_session.delete(user)
            source_session.commit()
            
            return new_user
            
        except Exception:
            source_session.rollback()
            target_session.rollback()
            raise
        finally:
            source_session.close()
            target_session.close()
    
    def aggregate_stats_across_shards(self):
        """Get aggregated statistics from all shards"""
        stats = {
            'total_users': 0,
            'active_users': 0,
            'total_posts': 0
        }
        
        for shard_name in self.router.shards.keys():
            session = self.router.get_session(shard_name)
            try:
                user_count = session.query(User).count()
                active_count = session.query(User).filter(User.is_active == True).count()
                post_count = session.query(Post).count()
                
                stats['total_users'] += user_count
                stats['active_users'] += active_count
                stats['total_posts'] += post_count
                
            finally:
                session.close()
        
        return stats

# Usage
cross_shard = CrossShardOperations(router)
global_stats = cross_shard.aggregate_stats_across_shards()
search_results = cross_shard.search_users_global("john")
```

#### Sharding Best Practices with SQLAlchemy
```python
# 1. Shard key selection
def choose_shard_key():
    """Guidelines for choosing shard keys"""
    return {
        'user_id': 'Good - evenly distributed, single-entity queries',
        'timestamp': 'Bad - creates hot partitions',
        'geography': 'Good - for location-based sharding',
        'tenant_id': 'Good - for multi-tenant applications'
    }

# 2. Connection management
class ShardConnectionManager:
    """Manage connections efficiently across shards"""
    
    def __init__(self, shard_configs):
        self.engines = {}
        self.session_makers = {}
        
        for shard_name, config in shard_configs.items():
            self.engines[shard_name] = create_engine(
                config['url'],
                pool_size=config.get('pool_size', 5),
                max_overflow=config.get('max_overflow', 10),
                pool_recycle=3600
            )
            self.session_makers[shard_name] = sessionmaker(
                bind=self.engines[shard_name]
            )
    
    @contextmanager
    def get_session(self, shard_name):
        """Context manager for session handling"""
        session = self.session_makers[shard_name]()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def close_all_connections(self):
        """Cleanup all connections"""
        for engine in self.engines.values():
            engine.dispose()

# 3. Migration handling for sharded databases
class ShardMigrationManager:
    """Handle migrations across multiple shards"""
    
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager
    
    def run_migration_on_all_shards(self, migration_sql):
        """Execute migration on all shards"""
        results = {}
        
        for shard_name in self.connection_manager.engines.keys():
            try:
                with self.connection_manager.get_session(shard_name) as session:
                    session.execute(text(migration_sql))
                results[shard_name] = "Success"
            except Exception as e:
                results[shard_name] = f"Error: {str(e)}"
        
        return results
```

## Quick Reference Commands

### Common Query Patterns
```python
# Get by ID
user = session.get(User, 1)

# Count records
count = session.query(User).count()

# Check if exists
exists = session.query(User).filter(User.username == 'john').first() is not None

# Get or create
user = session.query(User).filter_by(username='john').first()
if not user:
    user = User(username='john')
    session.add(user)
    session.commit()

# Pagination
page = 1
per_page = 20
users = session.query(User).offset((page-1)*per_page).limit(per_page).all()
```

### Common Pitfalls to Avoid

1. **N+1 Query Problem**: Use eager loading
2. **Session Leaks**: Always close sessions or use context managers
3. **Large Result Sets**: Use pagination or streaming
4. **Missing Indexes**: Add indexes for filtered columns
5. **Cartesian Products**: Be careful with multiple joins

This guide covers SQLAlchemy's core features from a client perspective. Each feature can be explored in more depth as needed for specific use cases.