# Python ORM & Repository Patterns for Staff Engineers

## ORM Landscape Overview

### Popular Python ORMs Comparison

| ORM | Strengths | Weaknesses | Best For |
|-----|-----------|------------|----------|
| **SQLAlchemy** | Most powerful, flexible, mature | Complex, steep learning curve | Complex applications, high performance |
| **Django ORM** | Simple, integrated, good defaults | Less flexible, Django-specific | Django applications, rapid development |
| **Tortoise ORM** | Async-first, FastAPI friendly | Newer ecosystem, fewer features | Async applications, microservices |
| **Peewee** | Lightweight, simple API | Limited scalability features | Small to medium applications |
| **SQLModel** | Type hints, FastAPI integration | Very new, limited ecosystem | Modern async APIs with type safety |

## SQLAlchemy Deep Dive

### Core vs ORM Layer
```python
# Core Layer - SQL Expression Language
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, text

engine = create_engine("postgresql://user:pass@localhost/db")
metadata = MetaData()

users = Table('users', metadata,
    Column('id', Integer, primary_key=True),
    Column('username', String(50)),
    Column('email', String(100))
)

# Raw SQL with Core
with engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM users WHERE id = :user_id"), 
                         {"user_id": 123})
    user = result.fetchone()
```

```python
# ORM Layer - Object-Relational Mapping
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    posts = relationship("Post", back_populates="author", lazy="dynamic")
    
    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"

class Post(Base):
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(Text)
    user_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    author = relationship("User", back_populates="posts")
```

### Advanced SQLAlchemy Features

#### Polymorphic Inheritance
```python
class Employee(Base):
    __tablename__ = 'employees'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    type = Column(String(50))
    
    __mapper_args__ = {
        'polymorphic_identity': 'employee',
        'polymorphic_on': type
    }

class Engineer(Employee):
    __tablename__ = 'engineers'
    
    id = Column(Integer, ForeignKey('employees.id'), primary_key=True)
    programming_language = Column(String(50))
    
    __mapper_args__ = {
        'polymorphic_identity': 'engineer'
    }

class Manager(Employee):
    __tablename__ = 'managers'
    
    id = Column(Integer, ForeignKey('employees.id'), primary_key=True)
    team_size = Column(Integer)
    
    __mapper_args__ = {
        'polymorphic_identity': 'manager'
    }
```

#### Hybrid Properties
```python
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import func

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    first_name = Column(String(50))
    last_name = Column(String(50))
    _password_hash = Column('password_hash', String(255))
    
    @hybrid_property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @full_name.expression
    def full_name(cls):
        return func.concat(cls.first_name, ' ', cls.last_name)
    
    @hybrid_property
    def password(self):
        raise AttributeError('Password is not readable')
    
    @password.setter
    def password(self, password):
        self._password_hash = generate_password_hash(password)
    
    def verify_password(self, password):
        return check_password_hash(self._password_hash, password)

# Usage
# Query with hybrid property
users = session.query(User).filter(User.full_name == "John Doe").all()
```

## Repository Pattern Implementation

### Base Repository Interface
```python
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List, Any, Dict
from sqlalchemy.orm import Session

T = TypeVar('T')

class IRepository(ABC, Generic[T]):
    """Generic repository interface"""
    
    @abstractmethod
    def get_by_id(self, id: Any) -> Optional[T]:
        pass
    
    @abstractmethod
    def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        pass
    
    @abstractmethod
    def create(self, obj: T) -> T:
        pass
    
    @abstractmethod
    def update(self, id: Any, obj_data: Dict[str, Any]) -> Optional[T]:
        pass
    
    @abstractmethod
    def delete(self, id: Any) -> bool:
        pass
    
    @abstractmethod
    def find_by(self, **kwargs) -> List[T]:
        pass
```

### SQLAlchemy Repository Implementation
```python
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)

class SQLAlchemyRepository(IRepository[T]):
    """SQLAlchemy implementation of repository pattern"""
    
    def __init__(self, session: Session, model_class: type):
        self.session = session
        self.model_class = model_class
    
    def get_by_id(self, id: Any) -> Optional[T]:
        """Get entity by ID"""
        try:
            return self.session.query(self.model_class).filter(
                self.model_class.id == id
            ).first()
        except Exception as e:
            logger.error(f"Error fetching {self.model_class.__name__} by ID {id}: {e}")
            raise
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Get all entities with pagination"""
        try:
            return self.session.query(self.model_class).offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"Error fetching all {self.model_class.__name__}: {e}")
            raise
    
    def create(self, obj: T) -> T:
        """Create new entity"""
        try:
            self.session.add(obj)
            self.session.commit()
            self.session.refresh(obj)
            return obj
        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"Integrity error creating {self.model_class.__name__}: {e}")
            raise ValueError("Entity with this data already exists")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating {self.model_class.__name__}: {e}")
            raise
    
    def update(self, id: Any, obj_data: Dict[str, Any]) -> Optional[T]:
        """Update entity by ID"""
        try:
            entity = self.get_by_id(id)
            if not entity:
                return None
            
            for key, value in obj_data.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            
            self.session.commit()
            self.session.refresh(entity)
            return entity
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating {self.model_class.__name__} {id}: {e}")
            raise
    
    def delete(self, id: Any) -> bool:
        """Delete entity by ID"""
        try:
            entity = self.get_by_id(id)
            if not entity:
                return False
            
            self.session.delete(entity)
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error deleting {self.model_class.__name__} {id}: {e}")
            raise
    
    def find_by(self, **kwargs) -> List[T]:
        """Find entities by attributes"""
        try:
            query = self.session.query(self.model_class)
            for key, value in kwargs.items():
                if hasattr(self.model_class, key):
                    query = query.filter(getattr(self.model_class, key) == value)
            return query.all()
        except Exception as e:
            logger.error(f"Error finding {self.model_class.__name__} by {kwargs}: {e}")
            raise

# Specialized repositories
class UserRepository(SQLAlchemyRepository[User]):
    """User-specific repository with custom methods"""
    
    def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email"""
        return self.session.query(User).filter(User.email == email).first()
    
    def find_by_username(self, username: str) -> Optional[User]:
        """Find user by username"""
        return self.session.query(User).filter(User.username == username).first()
    
    def get_active_users(self, limit: int = 100) -> List[User]:
        """Get active users"""
        return self.session.query(User).filter(
            User.is_active == True
        ).limit(limit).all()
    
    def search_users(self, search_term: str, limit: int = 50) -> List[User]:
        """Search users by username or email"""
        return self.session.query(User).filter(
            or_(
                User.username.ilike(f"%{search_term}%"),
                User.email.ilike(f"%{search_term}%")
            )
        ).limit(limit).all()
```

## Unit of Work Pattern

```python
from contextlib import contextmanager
from typing import Dict, Type

class UnitOfWork:
    """Unit of Work pattern for managing transactions"""
    
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._repositories: Dict[str, Any] = {}
    
    def __enter__(self):
        self.session = self.session_factory()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.rollback()
        self.session.close()
    
    def commit(self):
        """Commit the transaction"""
        self.session.commit()
    
    def rollback(self):
        """Rollback the transaction"""
        self.session.rollback()
    
    def get_repository(self, repo_class: Type, model_class: Type):
        """Get or create repository instance"""
        repo_key = f"{repo_class.__name__}_{model_class.__name__}"
        
        if repo_key not in self._repositories:
            self._repositories[repo_key] = repo_class(self.session, model_class)
        
        return self._repositories[repo_key]

# Usage example
def transfer_money(from_user_id: int, to_user_id: int, amount: float):
    """Transfer money between users using Unit of Work"""
    
    with UnitOfWork(session_factory) as uow:
        user_repo = uow.get_repository(UserRepository, User)
        account_repo = uow.get_repository(AccountRepository, Account)
        transaction_repo = uow.get_repository(TransactionRepository, Transaction)
        
        # Get users and accounts
        from_user = user_repo.get_by_id(from_user_id)
        to_user = user_repo.get_by_id(to_user_id)
        
        if not from_user or not to_user:
            raise ValueError("User not found")
        
        from_account = account_repo.find_by(user_id=from_user_id)[0]
        to_account = account_repo.find_by(user_id=to_user_id)[0]
        
        # Validate balance
        if from_account.balance < amount:
            raise ValueError("Insufficient balance")
        
        # Update balances
        from_account.balance -= amount
        to_account.balance += amount
        
        # Create transaction record
        transaction = Transaction(
            from_account_id=from_account.id,
            to_account_id=to_account.id,
            amount=amount,
            type='transfer'
        )
        transaction_repo.create(transaction)
        
        # Commit all changes
        uow.commit()
```

## Service Layer Pattern

```python
from typing import Optional, List
from dataclasses import dataclass

@dataclass
class CreateUserDTO:
    username: str
    email: str
    password: str
    full_name: Optional[str] = None

@dataclass
class UserResponseDTO:
    id: int
    username: str
    email: str
    full_name: Optional[str]
    created_at: datetime

class UserService:
    """Service layer for user operations"""
    
    def __init__(self, session_factory):
        self.session_factory = session_factory
    
    def create_user(self, user_data: CreateUserDTO) -> UserResponseDTO:
        """Create new user with validation"""
        
        with UnitOfWork(self.session_factory) as uow:
            user_repo = uow.get_repository(UserRepository, User)
            
            # Validate unique constraints
            if user_repo.find_by_email(user_data.email):
                raise ValueError("Email already exists")
            
            if user_repo.find_by_username(user_data.username):
                raise ValueError("Username already exists")
            
            # Create user entity
            user = User(
                username=user_data.username,
                email=user_data.email,
                password=user_data.password,  # Uses hybrid property
                full_name=user_data.full_name
            )
            
            # Save to database
            created_user = user_repo.create(user)
            uow.commit()
            
            # Return DTO
            return UserResponseDTO(
                id=created_user.id,
                username=created_user.username,
                email=created_user.email,
                full_name=created_user.full_name,
                created_at=created_user.created_at
            )
    
    def get_user(self, user_id: int) -> Optional[UserResponseDTO]:
        """Get user by ID"""
        
        with UnitOfWork(self.session_factory) as uow:
            user_repo = uow.get_repository(UserRepository, User)
            user = user_repo.get_by_id(user_id)
            
            if not user:
                return None
            
            return UserResponseDTO(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                created_at=user.created_at
            )
    
    def search_users(self, search_term: str, limit: int = 50) -> List[UserResponseDTO]:
        """Search users"""
        
        with UnitOfWork(self.session_factory) as uow:
            user_repo = uow.get_repository(UserRepository, User)
            users = user_repo.search_users(search_term, limit)
            
            return [
                UserResponseDTO(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    full_name=user.full_name,
                    created_at=user.created_at
                )
                for user in users
            ]
```

## Async ORM Patterns

### SQLAlchemy Async (2.0+)
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import asyncio

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)

# Async repository
class AsyncUserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID asynchronously"""
        result = await self.session.get(User, user_id)
        return result
    
    async def create(self, user: User) -> User:
        """Create user asynchronously"""
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
    
    async def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email"""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

# Async service
class AsyncUserService:
    def __init__(self, session_factory: async_sessionmaker):
        self.session_factory = session_factory
    
    async def create_user(self, username: str, email: str) -> User:
        """Create user with async session management"""
        async with self.session_factory() as session:
            repo = AsyncUserRepository(session)
            
            # Check if user exists
            existing_user = await repo.find_by_email(email)
            if existing_user:
                raise ValueError("Email already exists")
            
            # Create new user
            user = User(username=username, email=email)
            return await repo.create(user)

# Usage
async def main():
    engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    service = AsyncUserService(async_session)
    user = await service.create_user("john_doe", "john@example.com")
    print(f"Created user: {user.id}")

# Run async code
asyncio.run(main())
```

### Tortoise ORM (Django-like Async ORM)
```python
from tortoise.models import Model
from tortoise import fields
from tortoise.contrib.pydantic import pydantic_model_creator
from typing import List

class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    email = fields.CharField(max_length=100, unique=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    
    posts: fields.ReverseRelation["Post"]
    
    class Meta:
        table = "users"

class Post(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=200)
    content = fields.TextField()
    author = fields.ForeignKeyField("models.User", related_name="posts")
    created_at = fields.DatetimeField(auto_now_add=True)

# Pydantic models for serialization
UserOut = pydantic_model_creator(User, name="UserOut")
PostOut = pydantic_model_creator(Post, name="PostOut")

# Repository with Tortoise
class TortoiseUserRepository:
    async def create_user(self, username: str, email: str) -> User:
        """Create user with Tortoise ORM"""
        user = await User.create(username=username, email=email)
        return user
    
    async def get_by_id(self, user_id: int) -> User:
        """Get user by ID with related data"""
        return await User.get(id=user_id).prefetch_related("posts")
    
    async def get_users_with_posts(self, limit: int = 10) -> List[User]:
        """Get users with their posts"""
        return await User.all().prefetch_related("posts").limit(limit)
    
    async def search_users(self, search_term: str) -> List[User]:
        """Search users by username or email"""
        return await User.filter(
            Q(username__icontains=search_term) | Q(email__icontains=search_term)
        )
```

## Performance Optimization

### Query Optimization
```python
# N+1 Query Problem and Solutions
class PostRepository:
    def __init__(self, session: Session):
        self.session = session
    
    # BAD: N+1 query problem
    def get_posts_with_authors_bad(self) -> List[Post]:
        posts = self.session.query(Post).all()  # 1 query
        for post in posts:
            print(post.author.username)  # N queries (one for each post)
        return posts
    
    # GOOD: Eager loading with joinedload
    def get_posts_with_authors_good(self) -> List[Post]:
        return self.session.query(Post).options(
            joinedload(Post.author)  # Single JOIN query
        ).all()
    
    # GOOD: Eager loading with selectinload (separate query)
    def get_posts_with_authors_selectin(self) -> List[Post]:
        return self.session.query(Post).options(
            selectinload(Post.author)  # Two queries total
        ).all()
    
    # GOOD: Explicit join for filtering
    def get_posts_by_active_authors(self) -> List[Post]:
        return self.session.query(Post).join(User).filter(
            User.is_active == True
        ).all()
```

### Connection Pooling
```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

# Production-ready engine configuration
engine = create_engine(
    "postgresql://user:pass@localhost/db",
    poolclass=QueuePool,
    pool_size=20,          # Number of connections to maintain
    max_overflow=30,       # Additional connections when pool is full
    pool_recycle=3600,     # Recycle connections every hour
    pool_pre_ping=True,    # Validate connections before use
    echo=False,            # Set to True for query logging in dev
    connect_args={
        "connect_timeout": 10,
        "application_name": "myapp_db"
    }
)

# Monitor connection pool
@contextmanager
def get_db_session():
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# Pool monitoring
def monitor_connection_pool():
    pool = engine.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "invalid": pool.invalid()
    }
```

### Bulk Operations
```python
class BulkOperations:
    def __init__(self, session: Session):
        self.session = session
    
    def bulk_insert_users(self, user_data: List[Dict]) -> None:
        """Bulk insert users efficiently"""
        # Using bulk_insert_mappings (fastest for many records)
        self.session.bulk_insert_mappings(User, user_data)
        self.session.commit()
    
    def bulk_update_users(self, updates: List[Dict]) -> None:
        """Bulk update users"""
        # Updates must include the primary key
        self.session.bulk_update_mappings(User, updates)
        self.session.commit()
    
    def bulk_delete_inactive_users(self) -> int:
        """Bulk delete inactive users"""
        deleted_count = self.session.query(User).filter(
            User.last_login < datetime.now() - timedelta(days=365)
        ).delete(synchronize_session=False)
        self.session.commit()
        return deleted_count
    
    async def async_bulk_operations(self, user_data: List[Dict]):
        """Async bulk operations"""
        async with AsyncSession(engine) as session:
            # Create user objects
            users = [User(**data) for data in user_data]
            
            # Add all at once
            session.add_all(users)
            await session.commit()
```

## Testing Patterns

### Repository Testing
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock

@pytest.fixture
def db_session():
    """In-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    session.close()

@pytest.fixture
def user_repository(db_session):
    return UserRepository(db_session, User)

class TestUserRepository:
    def test_create_user(self, user_repository):
        """Test user creation"""
        user = User(username="testuser", email="test@example.com")
        created_user = user_repository.create(user)
        
        assert created_user.id is not None
        assert created_user.username == "testuser"
        assert created_user.email == "test@example.com"
    
    def test_get_user_by_id(self, user_repository):
        """Test get user by ID"""
        # Create user first
        user = User(username="testuser", email="test@example.com")
        created_user = user_repository.create(user)
        
        # Retrieve user
        retrieved_user = user_repository.get_by_id(created_user.id)
        
        assert retrieved_user is not None
        assert retrieved_user.username == "testuser"
    
    def test_user_not_found(self, user_repository):
        """Test user not found scenario"""
        user = user_repository.get_by_id(999)
        assert user is None
    
    def test_find_by_email(self, user_repository):
        """Test find user by email"""
        user = User(username="testuser", email="test@example.com")
        user_repository.create(user)
        
        found_user = user_repository.find_by_email("test@example.com")
        assert found_user is not None
        assert found_user.username == "testuser"

# Service layer testing with mocks
class TestUserService:
    @pytest.fixture
    def mock_session_factory(self):
        return Mock()
    
    @pytest.fixture
    def user_service(self, mock_session_factory):
        return UserService(mock_session_factory)
    
    def test_create_user_success(self, user_service, mock_session_factory):
        """Test successful user creation"""
        # Setup mocks
        mock_uow = Mock()
        mock_repo = Mock()
        mock_session_factory.return_value.__enter__.return_value = mock_uow
        mock_uow.get_repository.return_value = mock_repo
        
        # Configure mock behavior
        mock_repo.find_by_email.return_value = None
        mock_repo.find_by_username.return_value = None
        mock_created_user = User(id=1, username="test", email="test@example.com")
        mock_repo.create.return_value = mock_created_user
        
        # Test
        user_data = CreateUserDTO(
            username="test",
            email="test@example.com",
            password="password123"
        )
        
        result = user_service.create_user(user_data)
        
        # Assertions
        assert result.id == 1
        assert result.username == "test"
        mock_repo.create.assert_called_once()
```

## Migration Strategies

### Alembic Configuration
```python
# alembic/env.py
from alembic import context
from sqlalchemy import engine_from_config, pool
from myapp.models import Base

# Add model imports
from myapp.models.user import User
from myapp.models.post import Post

target_metadata = Base.metadata

def run_migrations_online():
    """Run migrations in 'online' mode with real database"""
    connectable = engine_from_config(
        context.config.get_section(context.config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,         # Detect column type changes
            compare_server_default=True,  # Detect default value changes
        )

        with context.begin_transaction():
            context.run_migrations()

# Safe migration patterns
class SafeMigrationPatterns:
    """Examples of safe database migrations"""
    
    def add_nullable_column(self):
        """Safe: Adding nullable column"""
        op.add_column('users', 
            sa.Column('phone_number', sa.String(20), nullable=True))
    
    def add_column_with_default(self):
        """Safe: Adding column with default value"""
        op.add_column('users',
            sa.Column('is_verified', sa.Boolean(), 
                     nullable=False, server_default='false'))
    
    def add_index(self):
        """Safe: Adding index (can be done concurrently)"""
        op.create_index('ix_users_email', 'users', ['email'], 
                       postgresql_concurrently=True)
    
    def rename_column_safely(self):
        """Safe approach: Add new column, copy data, remove old"""
        # Step 1: Add new column
        op.add_column('users', 
            sa.Column('full_name', sa.String(100), nullable=True))
        
        # Step 2: Copy data (in separate migration)
        # UPDATE users SET full_name = first_name || ' ' || last_name
        
        # Step 3: Remove old columns (in separate migration)
        # op.drop_column('users', 'first_name')
        # op.drop_column('users', 'last_name')
```

## Best Practices Summary

### Repository Pattern Best Practices
1. **Keep repositories focused**: One entity per repository
2. **Abstract database details**: Repository should hide ORM specifics
3. **Use dependency injection**: Pass session/connection to repositories
4. **Handle errors gracefully**: Log errors and raise appropriate exceptions
5. **Implement proper pagination**: Don't load all records at once

### Performance Best Practices
1. **Use connection pooling**: Configure appropriate pool sizes
2. **Eager load relationships**: Avoid N+1 query problems
3. **Implement query optimization**: Use indexes and query analysis
4. **Use bulk operations**: For large data operations
5. **Monitor query performance**: Track slow queries and optimize

### Testing Best Practices
1. **Test repositories in isolation**: Use in-memory database or mocks
2. **Test service layer separately**: Mock repository dependencies
3. **Use fixtures**: Consistent test data setup
4. **Test error scenarios**: Validation failures, constraint violations
5. **Integration tests**: Test real database interactions

### Code Organization
```
project/
├── models/
│   ├── __init__.py
│   ├── base.py          # Base model class
│   ├── user.py          # User model
│   └── post.py          # Post model
├── repositories/
│   ├── __init__.py
│   ├── base.py          # Base repository interface
│   ├── user.py          # User repository
│   └── post.py          # Post repository
├── services/
│   ├── __init__.py
│   ├── user.py          # User service layer
│   └── post.py          # Post service layer
├── schemas/
│   ├── __init__.py
│   ├── user.py          # Pydantic schemas/DTOs
│   └── post.py          # Pydantic schemas/DTOs
└── tests/
    ├── repositories/    # Repository tests
    └── services/        # Service tests
```

This comprehensive ORM guide provides the foundation for building maintainable, scalable data access layers that staff engineers need to master.