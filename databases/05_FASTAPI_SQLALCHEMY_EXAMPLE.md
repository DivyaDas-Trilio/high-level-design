# FastAPI + SQLAlchemy Production Example

## Complete Application Structure

This example demonstrates a production-ready FastAPI application with proper repository patterns, dependency injection, and database management.

```
app/
├── core/
│   ├── __init__.py
│   ├── config.py           # Configuration management
│   ├── database.py         # Database connection and session
│   └── security.py         # Authentication and security
├── models/
│   ├── __init__.py
│   ├── base.py            # Base model class
│   ├── user.py            # User model
│   ├── post.py            # Post model
│   └── comment.py         # Comment model
├── schemas/
│   ├── __init__.py
│   ├── user.py            # Pydantic schemas for users
│   ├── post.py            # Pydantic schemas for posts
│   └── comment.py         # Pydantic schemas for comments
├── repositories/
│   ├── __init__.py
│   ├── base.py            # Base repository
│   ├── user.py            # User repository
│   ├── post.py            # Post repository
│   └── comment.py         # Comment repository
├── services/
│   ├── __init__.py
│   ├── user.py            # User business logic
│   ├── post.py            # Post business logic
│   └── auth.py            # Authentication service
├── api/
│   ├── __init__.py
│   ├── deps.py            # Dependency injection
│   └── v1/
│       ├── __init__.py
│       ├── users.py       # User endpoints
│       ├── posts.py       # Post endpoints
│       └── auth.py        # Auth endpoints
├── tests/
│   ├── __init__.py
│   ├── conftest.py        # Test configuration
│   ├── test_repositories/
│   ├── test_services/
│   └── test_api/
├── alembic/               # Database migrations
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── main.py               # Application entry point
├── requirements.txt      # Dependencies
└── alembic.ini          # Alembic configuration
```

## Core Configuration

### app/core/config.py
```python
from pydantic import BaseSettings, PostgresDsn
from typing import Optional
import os

class Settings(BaseSettings):
    # Database
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 30
    DATABASE_POOL_RECYCLE: int = 3600
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Application
    APP_NAME: str = "Social Media API"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"
    
    # Redis Cache
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL: int = 3600
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
```

### app/core/database.py
```python
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import logging
from .config import settings

logger = logging.getLogger(__name__)

# Create engine with production settings
engine = create_engine(
    str(settings.DATABASE_URL),
    poolclass=QueuePool,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    pool_pre_ping=True,
    echo=settings.DEBUG,
    connect_args={
        "connect_timeout": 10,
        "application_name": settings.APP_NAME
    }
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Connection pool monitoring
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set connection parameters for better performance"""
    if "postgresql" in str(settings.DATABASE_URL):
        with dbapi_connection.cursor() as cursor:
            # Set timezone
            cursor.execute("SET timezone TO 'UTC'")
            # Set statement timeout
            cursor.execute("SET statement_timeout = '30s'")

def get_db() -> Session:
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_connection_info():
    """Monitor database connection pool"""
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "invalid": pool.invalid()
    }
```

## Models

### app/models/base.py
```python
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy import Column, Integer, DateTime, Boolean
from datetime import datetime

class CustomBase:
    """Base class for all models with common fields"""
    
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

Base = declarative_base(cls=CustomBase)
```

### app/models/user.py
```python
from sqlalchemy import Column, String, Boolean, Integer, Text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from werkzeug.security import generate_password_hash, check_password_hash
from .base import Base

class User(Base):
    __tablename__ = "users"
    
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    _password_hash = Column("password_hash", String(255), nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    bio = Column(Text)
    avatar_url = Column(String(255))
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    follower_count = Column(Integer, default=0, nullable=False)
    following_count = Column(Integer, default=0, nullable=False)
    
    # Relationships
    posts = relationship("Post", back_populates="author", lazy="dynamic")
    comments = relationship("Comment", back_populates="author", lazy="dynamic")
    
    # Hybrid properties
    @hybrid_property
    def password(self):
        raise AttributeError("Password is not readable")
    
    @password.setter
    def password(self, password: str):
        self._password_hash = generate_password_hash(password)
    
    def verify_password(self, password: str) -> bool:
        return check_password_hash(self._password_hash, password)
    
    @hybrid_property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"
```

### app/models/post.py
```python
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from .base import Base

class Post(Base):
    __tablename__ = "posts"
    
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    excerpt = Column(String(500))  # For list views
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    like_count = Column(Integer, default=0, nullable=False)
    comment_count = Column(Integer, default=0, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)
    is_published = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post", lazy="dynamic")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_user_created', 'user_id', 'created_at'),
        Index('idx_published_created', 'is_published', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Post(title='{self.title}', author='{self.author.username}')>"
```

## Schemas (Pydantic Models)

### app/schemas/user.py
```python
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

# Base schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    bio: Optional[str] = Field(None, max_length=500)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)

class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = None

class UserResponse(UserBase):
    id: int
    full_name: str
    is_active: bool
    is_verified: bool
    follower_count: int
    following_count: int
    created_at: datetime
    avatar_url: Optional[str] = None
    
    class Config:
        orm_mode = True

class UserList(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    size: int
    
# Authentication schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserLogin(BaseModel):
    email: EmailStr
    password: str
```

### app/schemas/post.py
```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from .user import UserResponse

class PostBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    excerpt: Optional[str] = Field(None, max_length=500)

class PostCreate(PostBase):
    is_published: bool = True

class PostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    excerpt: Optional[str] = Field(None, max_length=500)
    is_published: Optional[bool] = None

class PostResponse(PostBase):
    id: int
    user_id: int
    author: UserResponse
    like_count: int
    comment_count: int
    view_count: int
    is_published: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        orm_mode = True

class PostList(BaseModel):
    posts: List[PostResponse]
    total: int
    page: int
    size: int
```

## Repositories

### app/repositories/user.py
```python
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from ..models.user import User
from ..repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    def __init__(self, session: Session):
        super().__init__(session, User)
    
    def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email address"""
        return self.session.query(User).filter(
            and_(User.email == email, User.is_deleted == False)
        ).first()
    
    def find_by_username(self, username: str) -> Optional[User]:
        """Find user by username"""
        return self.session.query(User).filter(
            and_(User.username == username, User.is_deleted == False)
        ).first()
    
    def get_active_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get active users with pagination"""
        return self.session.query(User).filter(
            and_(User.is_active == True, User.is_deleted == False)
        ).offset(skip).limit(limit).all()
    
    def search_users(self, search_term: str, limit: int = 50) -> List[User]:
        """Search users by username, email, or full name"""
        search_filter = f"%{search_term}%"
        return self.session.query(User).filter(
            and_(
                or_(
                    User.username.ilike(search_filter),
                    User.email.ilike(search_filter),
                    func.concat(User.first_name, ' ', User.last_name).ilike(search_filter)
                ),
                User.is_deleted == False,
                User.is_active == True
            )
        ).limit(limit).all()
    
    def get_user_stats(self, user_id: int) -> dict:
        """Get user statistics"""
        user = self.get_by_id(user_id)
        if not user:
            return {}
        
        # Get post count
        post_count = self.session.query(func.count(Post.id)).filter(
            and_(Post.user_id == user_id, Post.is_deleted == False)
        ).scalar()
        
        return {
            "post_count": post_count,
            "follower_count": user.follower_count,
            "following_count": user.following_count,
            "is_verified": user.is_verified
        }
    
    def update_follower_count(self, user_id: int, delta: int) -> bool:
        """Update follower count atomically"""
        rows_affected = self.session.query(User).filter(
            User.id == user_id
        ).update({
            User.follower_count: User.follower_count + delta
        })
        return rows_affected > 0
```

### app/repositories/post.py
```python
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc, func
from ..models.post import Post
from ..models.user import User
from ..repositories.base import BaseRepository

class PostRepository(BaseRepository[Post]):
    def __init__(self, session: Session):
        super().__init__(session, Post)
    
    def get_with_author(self, post_id: int) -> Optional[Post]:
        """Get post with author information"""
        return self.session.query(Post).options(
            joinedload(Post.author)
        ).filter(
            and_(Post.id == post_id, Post.is_deleted == False)
        ).first()
    
    def get_user_posts(self, user_id: int, skip: int = 0, limit: int = 20, 
                      include_unpublished: bool = False) -> List[Post]:
        """Get posts by user with pagination"""
        query = self.session.query(Post).filter(
            and_(Post.user_id == user_id, Post.is_deleted == False)
        )
        
        if not include_unpublished:
            query = query.filter(Post.is_published == True)
        
        return query.options(
            joinedload(Post.author)
        ).order_by(desc(Post.created_at)).offset(skip).limit(limit).all()
    
    def get_published_posts(self, skip: int = 0, limit: int = 20) -> List[Post]:
        """Get published posts with authors"""
        return self.session.query(Post).options(
            joinedload(Post.author)
        ).filter(
            and_(Post.is_published == True, Post.is_deleted == False)
        ).order_by(desc(Post.created_at)).offset(skip).limit(limit).all()
    
    def search_posts(self, search_term: str, limit: int = 50) -> List[Post]:
        """Search posts by title and content"""
        search_filter = f"%{search_term}%"
        return self.session.query(Post).options(
            joinedload(Post.author)
        ).filter(
            and_(
                or_(
                    Post.title.ilike(search_filter),
                    Post.content.ilike(search_filter)
                ),
                Post.is_published == True,
                Post.is_deleted == False
            )
        ).order_by(desc(Post.created_at)).limit(limit).all()
    
    def get_trending_posts(self, days: int = 7, limit: int = 20) -> List[Post]:
        """Get trending posts based on likes and comments"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        return self.session.query(Post).options(
            joinedload(Post.author)
        ).filter(
            and_(
                Post.created_at >= cutoff_date,
                Post.is_published == True,
                Post.is_deleted == False
            )
        ).order_by(
            desc(Post.like_count + Post.comment_count)
        ).limit(limit).all()
    
    def increment_view_count(self, post_id: int) -> bool:
        """Atomically increment post view count"""
        rows_affected = self.session.query(Post).filter(
            Post.id == post_id
        ).update({
            Post.view_count: Post.view_count + 1
        })
        return rows_affected > 0
```

## Services (Business Logic)

### app/services/user.py
```python
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from ..schemas.user import UserCreate, UserUpdate, UserResponse, UserList
from ..repositories.user import UserRepository
from ..core.security import create_access_token
import logging

logger = logging.getLogger(__name__)

class UserService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = UserRepository(session)
    
    def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create new user with validation"""
        try:
            # Check if email exists
            if self.repository.find_by_email(user_data.email):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            
            # Check if username exists
            if self.repository.find_by_username(user_data.username):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
            
            # Create user entity
            from ..models.user import User
            user = User(
                username=user_data.username,
                email=user_data.email,
                password=user_data.password,  # Uses hybrid property
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                bio=user_data.bio
            )
            
            # Save to database
            created_user = self.repository.create(user)
            logger.info(f"User created: {created_user.id}")
            
            return UserResponse.from_orm(created_user)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
    
    def authenticate_user(self, email: str, password: str) -> Optional[UserResponse]:
        """Authenticate user and return user data"""
        user = self.repository.find_by_email(email)
        if user and user.verify_password(password) and user.is_active:
            return UserResponse.from_orm(user)
        return None
    
    def get_user(self, user_id: int) -> Optional[UserResponse]:
        """Get user by ID"""
        user = self.repository.get_by_id(user_id)
        if user and not user.is_deleted:
            return UserResponse.from_orm(user)
        return None
    
    def update_user(self, user_id: int, user_data: UserUpdate) -> Optional[UserResponse]:
        """Update user information"""
        try:
            # Get current user
            user = self.repository.get_by_id(user_id)
            if not user or user.is_deleted:
                return None
            
            # Update fields
            update_data = user_data.dict(exclude_unset=True)
            updated_user = self.repository.update(user_id, update_data)
            
            if updated_user:
                logger.info(f"User updated: {user_id}")
                return UserResponse.from_orm(updated_user)
            
            return None
            
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user"
            )
    
    def search_users(self, search_term: str, page: int = 1, size: int = 20) -> UserList:
        """Search users with pagination"""
        try:
            skip = (page - 1) * size
            users = self.repository.search_users(search_term, limit=size + 1)
            
            # Check if there are more results
            has_more = len(users) > size
            if has_more:
                users = users[:size]
            
            user_responses = [UserResponse.from_orm(user) for user in users]
            
            return UserList(
                users=user_responses,
                total=len(user_responses),  # In production, get actual count
                page=page,
                size=size
            )
            
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to search users"
            )
    
    def deactivate_user(self, user_id: int) -> bool:
        """Soft delete user"""
        try:
            user = self.repository.get_by_id(user_id)
            if not user:
                return False
            
            updated_user = self.repository.update(user_id, {
                "is_active": False,
                "is_deleted": True
            })
            
            if updated_user:
                logger.info(f"User deactivated: {user_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deactivating user {user_id}: {e}")
            return False
```

## API Endpoints

### app/api/deps.py
```python
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from ..core.database import get_db
from ..core.config import settings
from ..services.user import UserService
from ..schemas.user import UserResponse

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> UserResponse:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            credentials.credentials, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user_service = UserService(db)
    user = user_service.get_user(user_id)
    if user is None:
        raise credentials_exception
    
    return user

def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )
    return current_user
```

### app/api/v1/users.py
```python
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from ...core.database import get_db
from ...schemas.user import UserCreate, UserUpdate, UserResponse, UserList
from ...services.user import UserService
from ..deps import get_current_active_user

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Create new user"""
    service = UserService(db)
    return service.create_user(user_data)

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get current user profile"""
    return current_user

@router.put("/me", response_model=UserResponse)
def update_current_user(
    user_data: UserUpdate,
    current_user: UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user profile"""
    service = UserService(db)
    updated_user = service.update_user(current_user.id, user_data)
    
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return updated_user

@router.get("/{user_id}", response_model=UserResponse)
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get user by ID"""
    service = UserService(db)
    user = service.get_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

@router.get("/", response_model=UserList)
def search_users(
    search: str = Query(..., min_length=2, description="Search term"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db)
):
    """Search users"""
    service = UserService(db)
    return service.search_users(search, page, size)

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_current_user(
    current_user: UserResponse = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Deactivate current user account"""
    service = UserService(db)
    success = service.deactivate_user(current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate account"
        )
```

## Application Entry Point

### main.py
```python
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
import time
import logging
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, get_db_connection_info
from app.api.v1 import users, posts, auth
from app.models.base import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting up application...")
    
    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Social Media API with FastAPI and SQLAlchemy",
    version="1.0.0",
    debug=settings.DEBUG,
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Exception handlers
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database error occurred"}
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    db_info = get_db_connection_info()
    return {
        "status": "healthy",
        "database": {
            "connected": True,
            "pool_info": db_info
        }
    }

# Include routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(users.router, prefix=settings.API_V1_STR)
app.include_router(posts.router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
```

## Testing

### conftest.py
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.core.database import get_db
from app.models.base import Base
from main import app

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)
```

This complete example demonstrates:

1. **Proper project structure** for scalable applications
2. **Repository pattern** with dependency injection
3. **Service layer** for business logic
4. **Pydantic schemas** for data validation
5. **FastAPI integration** with proper error handling
6. **Database session management** with connection pooling
7. **Authentication and authorization** patterns
8. **Testing setup** with test database
9. **Production-ready configuration** management
10. **Monitoring and health checks**

This architecture provides a solid foundation for building scalable, maintainable APIs that staff engineers need to master.