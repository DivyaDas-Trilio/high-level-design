# Library Management System - Domain-Driven Database Design

## Phase 1: Domain Analysis & Modeling

### 1. Domain Identification

#### Core Domains (Business-Critical)
- **Circulation Management** - The heart of library operations (borrowing, returning)
- **Catalog Management** - Managing library collections

#### Supporting Domains
- **Member Management** - User registration and profiles
- **Inventory Management** - Physical book tracking
- **Notification System** - Alerts and communications

#### Generic Domains
- **Authentication & Authorization** - User access control
- **Reporting & Analytics** - Usage statistics

### 2. Bounded Contexts

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Circulation   │    │    Catalog      │    │    Member       │
│    Context      │    │    Context      │    │   Context       │
│                 │    │                 │    │                 │
│ - Loans         │    │ - Books         │    │ - Members       │
│ - Reservations  │    │ - Authors       │    │ - Memberships   │
│ - Renewals      │    │ - Categories    │    │ - Profiles      │
│ - Returns       │    │ - Copies        │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 3. Aggregates & Entities

#### Catalog Context
```python
# Aggregate: Book
class Book:  # Aggregate Root
    def __init__(self, isbn, title, authors, publication_info):
        self.book_id = BookId(uuid4())
        self.isbn = ISBN(isbn)
        self.title = title
        self.authors = authors  # List of Author entities
        self.publication_info = publication_info
        self.categories = []
        self.copies = []  # List of BookCopy entities
    
    def add_copy(self, copy_info):
        copy = BookCopy(self.book_id, copy_info)
        self.copies.append(copy)
        return copy

class Author:  # Entity
    def __init__(self, name, biography=None):
        self.author_id = AuthorId(uuid4())
        self.name = name
        self.biography = biography

class BookCopy:  # Entity  
    def __init__(self, book_id, location):
        self.copy_id = CopyId(uuid4())
        self.book_id = book_id
        self.barcode = Barcode(generate_barcode())
        self.location = location
        self.condition = BookCondition.NEW
        self.status = CopyStatus.AVAILABLE
```

#### Member Context
```python
# Aggregate: Member
class Member:  # Aggregate Root
    def __init__(self, email, name, contact_info):
        self.member_id = MemberId(uuid4())
        self.email = Email(email)
        self.personal_info = PersonalInfo(name, contact_info)
        self.membership = Membership()
        self.borrowing_history = []
    
    def can_borrow(self, book_copy):
        return (self.membership.is_active() and 
                self.membership.has_borrowing_capacity() and
                not self.has_overdue_books())

class Membership:  # Entity
    def __init__(self):
        self.membership_id = MembershipId(uuid4())
        self.type = MembershipType.STANDARD
        self.start_date = datetime.now()
        self.expiry_date = self.start_date + timedelta(days=365)
        self.max_books = 5
        self.current_loans = 0
```

#### Circulation Context
```python
# Aggregate: Loan
class Loan:  # Aggregate Root
    def __init__(self, member_id, copy_id, loan_period_days=14):
        self.loan_id = LoanId(uuid4())
        self.member_id = member_id
        self.copy_id = copy_id
        self.loan_date = datetime.now()
        self.due_date = self.loan_date + timedelta(days=loan_period_days)
        self.status = LoanStatus.ACTIVE
        self.renewals = []
        self.return_info = None
    
    def renew(self, additional_days=14):
        if self.can_renew():
            renewal = LoanRenewal(self.loan_id, additional_days)
            self.renewals.append(renewal)
            self.due_date += timedelta(days=additional_days)
            return True
        return False
    
    def return_book(self, return_condition):
        self.return_info = ReturnInfo(datetime.now(), return_condition)
        self.status = LoanStatus.RETURNED
        
    def calculate_fine(self):
        if self.is_overdue():
            days_overdue = (datetime.now() - self.due_date).days
            return Fine(days_overdue * FINE_PER_DAY)
        return None

class Reservation:  # Aggregate Root
    def __init__(self, member_id, book_id):
        self.reservation_id = ReservationId(uuid4())
        self.member_id = member_id
        self.book_id = book_id
        self.reservation_date = datetime.now()
        self.expiry_date = self.reservation_date + timedelta(days=7)
        self.status = ReservationStatus.PENDING
```

## Phase 2: Database Schema Design

### 1. Aggregate-to-Table Mapping

#### Strategy: One Aggregate Root = One Primary Table + Related Tables

```sql
-- Catalog Context Tables
CREATE TABLE books (
    book_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    isbn VARCHAR(13) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    subtitle VARCHAR(500),
    publication_date DATE,
    publisher VARCHAR(200),
    language VARCHAR(50) DEFAULT 'English',
    pages INTEGER,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_isbn_format CHECK (isbn ~ '^\d{13}$'),
    CONSTRAINT chk_pages_positive CHECK (pages > 0)
);

-- Many-to-many: Books and Authors
CREATE TABLE authors (
    author_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    biography TEXT,
    birth_date DATE,
    nationality VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE book_authors (
    book_id UUID REFERENCES books(book_id) ON DELETE CASCADE,
    author_id UUID REFERENCES authors(author_id) ON DELETE CASCADE,
    author_order INTEGER DEFAULT 1,
    role VARCHAR(50) DEFAULT 'author', -- author, editor, translator
    PRIMARY KEY (book_id, author_id)
);

-- Book Categories
CREATE TABLE categories (
    category_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    parent_category_id UUID REFERENCES categories(category_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE book_categories (
    book_id UUID REFERENCES books(book_id) ON DELETE CASCADE,
    category_id UUID REFERENCES categories(category_id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, category_id)
);

-- Physical Copies (Inventory)
CREATE TABLE book_copies (
    copy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id UUID NOT NULL REFERENCES books(book_id) ON DELETE CASCADE,
    barcode VARCHAR(50) UNIQUE NOT NULL,
    location VARCHAR(100), -- shelf location
    condition VARCHAR(20) DEFAULT 'good',
    status VARCHAR(20) DEFAULT 'available',
    acquisition_date DATE DEFAULT CURRENT_DATE,
    acquisition_price DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_condition CHECK (condition IN ('excellent', 'good', 'fair', 'poor', 'damaged')),
    CONSTRAINT chk_status CHECK (status IN ('available', 'borrowed', 'reserved', 'maintenance', 'lost'))
);

-- Member Context Tables
CREATE TABLE members (
    member_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    date_of_birth DATE,
    address JSONB, -- Flexible address structure
    emergency_contact JSONB,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active',
    notes TEXT,
    
    CONSTRAINT chk_email_format CHECK (email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    CONSTRAINT chk_member_status CHECK (status IN ('active', 'suspended', 'inactive', 'blacklisted'))
);

CREATE TABLE memberships (
    membership_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id UUID NOT NULL REFERENCES members(member_id) ON DELETE CASCADE,
    membership_type VARCHAR(20) DEFAULT 'standard',
    start_date DATE DEFAULT CURRENT_DATE,
    expiry_date DATE NOT NULL,
    max_books INTEGER DEFAULT 5,
    max_renewal_days INTEGER DEFAULT 14,
    fine_limit DECIMAL(10,2) DEFAULT 50.00,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_membership_type CHECK (membership_type IN ('student', 'standard', 'premium', 'faculty')),
    CONSTRAINT chk_membership_status CHECK (status IN ('active', 'expired', 'suspended')),
    CONSTRAINT chk_expiry_after_start CHECK (expiry_date > start_date)
);

-- Circulation Context Tables  
CREATE TABLE loans (
    loan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id UUID NOT NULL REFERENCES members(member_id),
    copy_id UUID NOT NULL REFERENCES book_copies(copy_id),
    loan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_date TIMESTAMP NOT NULL,
    return_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active',
    renewal_count INTEGER DEFAULT 0,
    fine_amount DECIMAL(10,2) DEFAULT 0.00,
    notes TEXT,
    
    CONSTRAINT chk_loan_status CHECK (status IN ('active', 'returned', 'overdue', 'lost')),
    CONSTRAINT chk_due_after_loan CHECK (due_date > loan_date),
    CONSTRAINT chk_return_after_loan CHECK (return_date IS NULL OR return_date >= loan_date)
);

CREATE TABLE loan_renewals (
    renewal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL REFERENCES loans(loan_id) ON DELETE CASCADE,
    renewal_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    previous_due_date TIMESTAMP NOT NULL,
    new_due_date TIMESTAMP NOT NULL,
    renewed_by VARCHAR(100), -- staff member or system
    
    CONSTRAINT chk_new_due_after_previous CHECK (new_due_date > previous_due_date)
);

CREATE TABLE reservations (
    reservation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id UUID NOT NULL REFERENCES members(member_id),
    book_id UUID NOT NULL REFERENCES books(book_id),
    reservation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry_date TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    fulfilled_date TIMESTAMP,
    copy_id UUID REFERENCES book_copies(copy_id), -- when fulfilled
    
    CONSTRAINT chk_reservation_status CHECK (status IN ('active', 'fulfilled', 'expired', 'cancelled')),
    CONSTRAINT chk_expiry_after_reservation CHECK (expiry_date > reservation_date)
);

CREATE TABLE fines (
    fine_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL REFERENCES loans(loan_id),
    member_id UUID NOT NULL REFERENCES members(member_id),
    fine_type VARCHAR(50) NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    description TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_date TIMESTAMP,
    paid_date TIMESTAMP,
    status VARCHAR(20) DEFAULT 'outstanding',
    
    CONSTRAINT chk_fine_type CHECK (fine_type IN ('overdue', 'damage', 'lost_book', 'administrative')),
    CONSTRAINT chk_fine_status CHECK (status IN ('outstanding', 'paid', 'waived')),
    CONSTRAINT chk_amount_positive CHECK (amount >= 0)
);
```

### 2. Indexing Strategy

```sql
-- Primary lookup indexes
CREATE INDEX idx_books_isbn ON books(isbn);
CREATE INDEX idx_books_title ON books(title);
CREATE INDEX idx_book_copies_barcode ON book_copies(barcode);
CREATE INDEX idx_members_email ON members(email);

-- Frequently joined indexes
CREATE INDEX idx_book_copies_book_id ON book_copies(book_id);
CREATE INDEX idx_loans_member_id ON loans(member_id);
CREATE INDEX idx_loans_copy_id ON loans(copy_id);
CREATE INDEX idx_reservations_member_id ON reservations(member_id);
CREATE INDEX idx_reservations_book_id ON reservations(book_id);

-- Query performance indexes
CREATE INDEX idx_loans_status_due_date ON loans(status, due_date);
CREATE INDEX idx_book_copies_status ON book_copies(status);
CREATE INDEX idx_reservations_status_expiry ON reservations(status, expiry_date);

-- Composite indexes for common queries
CREATE INDEX idx_loans_member_status ON loans(member_id, status);
CREATE INDEX idx_book_search ON books(title, isbn);

-- Full-text search index
CREATE INDEX idx_books_fts ON books USING GIN(
    to_tsvector('english', title || ' ' || COALESCE(subtitle, '') || ' ' || COALESCE(description, ''))
);

-- JSON indexes for flexible data
CREATE INDEX idx_members_address ON members USING GIN(address);
```

### 3. Domain Logic in Database

#### Triggers for Business Rules
```sql
-- Update book copy status when loaned
CREATE OR REPLACE FUNCTION update_copy_status_on_loan()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'active' AND OLD.status IS DISTINCT FROM 'active' THEN
        UPDATE book_copies 
        SET status = 'borrowed', updated_at = CURRENT_TIMESTAMP
        WHERE copy_id = NEW.copy_id;
    ELSIF NEW.status = 'returned' AND OLD.status = 'active' THEN
        UPDATE book_copies 
        SET status = 'available', updated_at = CURRENT_TIMESTAMP
        WHERE copy_id = NEW.copy_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_loan_copy_status
    AFTER INSERT OR UPDATE ON loans
    FOR EACH ROW
    EXECUTE FUNCTION update_copy_status_on_loan();

-- Calculate fines for overdue books
CREATE OR REPLACE FUNCTION calculate_overdue_fines()
RETURNS TRIGGER AS $$
DECLARE
    days_overdue INTEGER;
    fine_per_day DECIMAL(5,2) := 1.00;
    calculated_fine DECIMAL(10,2);
BEGIN
    IF NEW.status = 'overdue' THEN
        days_overdue := EXTRACT(days FROM (CURRENT_TIMESTAMP - NEW.due_date));
        calculated_fine := days_overdue * fine_per_day;
        
        INSERT INTO fines (loan_id, member_id, fine_type, amount, description)
        VALUES (
            NEW.loan_id,
            NEW.member_id,
            'overdue',
            calculated_fine,
            'Overdue fine for ' || days_overdue || ' days'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_overdue_fine_calculation
    AFTER UPDATE ON loans
    FOR EACH ROW
    WHEN (NEW.status = 'overdue' AND OLD.status != 'overdue')
    EXECUTE FUNCTION calculate_overdue_fines();
```

## Phase 3: Repository Pattern Implementation

### 1. SQLAlchemy Models

```python
# models/catalog.py
from sqlalchemy import Column, String, Integer, Date, Text, DECIMAL, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from uuid import uuid4

Base = declarative_base()

class Book(Base):
    __tablename__ = 'books'
    
    book_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    isbn = Column(String(13), unique=True, nullable=False)
    title = Column(String(500), nullable=False)
    subtitle = Column(String(500))
    publication_date = Column(Date)
    publisher = Column(String(200))
    language = Column(String(50), default='English')
    pages = Column(Integer)
    description = Column(Text)
    
    # Relationships
    authors = relationship("Author", secondary="book_authors", back_populates="books")
    categories = relationship("Category", secondary="book_categories", back_populates="books")
    copies = relationship("BookCopy", back_populates="book")
    reservations = relationship("Reservation", back_populates="book")

class BookCopy(Base):
    __tablename__ = 'book_copies'
    
    copy_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    book_id = Column(UUID(as_uuid=True), ForeignKey('books.book_id'), nullable=False)
    barcode = Column(String(50), unique=True, nullable=False)
    location = Column(String(100))
    condition = Column(String(20), default='good')
    status = Column(String(20), default='available')
    acquisition_date = Column(Date)
    acquisition_price = Column(DECIMAL(10, 2))
    
    # Relationships
    book = relationship("Book", back_populates="copies")
    loans = relationship("Loan", back_populates="copy")

class Member(Base):
    __tablename__ = 'members'
    
    member_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20))
    date_of_birth = Column(Date)
    address = Column(JSONB)
    emergency_contact = Column(JSONB)
    status = Column(String(20), default='active')
    
    # Relationships
    membership = relationship("Membership", back_populates="member", uselist=False)
    loans = relationship("Loan", back_populates="member")
    reservations = relationship("Reservation", back_populates="member")
    fines = relationship("Fine", back_populates="member")

class Loan(Base):
    __tablename__ = 'loans'
    
    loan_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    member_id = Column(UUID(as_uuid=True), ForeignKey('members.member_id'), nullable=False)
    copy_id = Column(UUID(as_uuid=True), ForeignKey('book_copies.copy_id'), nullable=False)
    loan_date = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime, nullable=False)
    return_date = Column(DateTime)
    status = Column(String(20), default='active')
    renewal_count = Column(Integer, default=0)
    fine_amount = Column(DECIMAL(10, 2), default=0.00)
    
    # Relationships
    member = relationship("Member", back_populates="loans")
    copy = relationship("BookCopy", back_populates="loans")
    renewals = relationship("LoanRenewal", back_populates="loan")
    fines = relationship("Fine", back_populates="loan")
```

### 2. Repository Implementation

```python
# repositories/catalog_repository.py
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from models.catalog import Book, BookCopy, Author

class CatalogRepository:
    def __init__(self, session: Session):
        self.session = session
    
    def find_book_by_isbn(self, isbn: str) -> Optional[Book]:
        """Find book by ISBN"""
        return self.session.query(Book).filter(Book.isbn == isbn).first()
    
    def search_books(self, query: str, limit: int = 50) -> List[Book]:
        """Search books by title, author, or ISBN"""
        return self.session.query(Book).options(
            joinedload(Book.authors),
            joinedload(Book.categories)
        ).join(Book.authors).filter(
            or_(
                Book.title.ilike(f"%{query}%"),
                Book.isbn.like(f"%{query}%"),
                Author.first_name.ilike(f"%{query}%"),
                Author.last_name.ilike(f"%{query}%")
            )
        ).limit(limit).all()
    
    def find_available_copies(self, book_id: str) -> List[BookCopy]:
        """Find available copies of a book"""
        return self.session.query(BookCopy).filter(
            and_(
                BookCopy.book_id == book_id,
                BookCopy.status == 'available'
            )
        ).all()
    
    def get_books_by_category(self, category_name: str) -> List[Book]:
        """Get books by category"""
        return self.session.query(Book).join(Book.categories).filter(
            Category.name == category_name
        ).all()

# repositories/circulation_repository.py
class CirculationRepository:
    def __init__(self, session: Session):
        self.session = session
    
    def create_loan(self, loan: Loan) -> Loan:
        """Create a new loan"""
        self.session.add(loan)
        self.session.commit()
        self.session.refresh(loan)
        return loan
    
    def find_active_loans_by_member(self, member_id: str) -> List[Loan]:
        """Find all active loans for a member"""
        return self.session.query(Loan).options(
            joinedload(Loan.copy).joinedload(BookCopy.book)
        ).filter(
            and_(
                Loan.member_id == member_id,
                Loan.status == 'active'
            )
        ).all()
    
    def find_overdue_loans(self) -> List[Loan]:
        """Find all overdue loans"""
        return self.session.query(Loan).filter(
            and_(
                Loan.status == 'active',
                Loan.due_date < func.now()
            )
        ).all()
    
    def return_book(self, loan_id: str, return_date: datetime) -> bool:
        """Process book return"""
        loan = self.session.query(Loan).filter(Loan.loan_id == loan_id).first()
        if loan:
            loan.return_date = return_date
            loan.status = 'returned'
            
            # Update copy status
            copy = loan.copy
            copy.status = 'available'
            
            self.session.commit()
            return True
        return False
```

### 3. Service Layer

```python
# services/circulation_service.py
from datetime import datetime, timedelta
from typing import Optional
from repositories.circulation_repository import CirculationRepository
from repositories.catalog_repository import CatalogRepository
from repositories.member_repository import MemberRepository

class CirculationService:
    def __init__(self, circulation_repo: CirculationRepository, 
                 catalog_repo: CatalogRepository,
                 member_repo: MemberRepository):
        self.circulation_repo = circulation_repo
        self.catalog_repo = catalog_repo
        self.member_repo = member_repo
    
    def borrow_book(self, member_id: str, copy_id: str, 
                   loan_period_days: int = 14) -> Optional[Loan]:
        """Process book borrowing"""
        
        # Validate member can borrow
        member = self.member_repo.get_member(member_id)
        if not member or not member.can_borrow():
            raise ValueError("Member cannot borrow books")
        
        # Check if copy is available
        copy = self.catalog_repo.get_copy(copy_id)
        if not copy or copy.status != 'available':
            raise ValueError("Book copy is not available")
        
        # Create loan
        due_date = datetime.now() + timedelta(days=loan_period_days)
        loan = Loan(
            member_id=member_id,
            copy_id=copy_id,
            due_date=due_date
        )
        
        return self.circulation_repo.create_loan(loan)
    
    def renew_loan(self, loan_id: str, additional_days: int = 14) -> bool:
        """Renew a loan"""
        loan = self.circulation_repo.get_loan(loan_id)
        
        if not loan or not loan.can_renew():
            return False
        
        # Check if book is reserved by another member
        reservations = self.circulation_repo.get_active_reservations_for_book(
            loan.copy.book_id
        )
        if reservations:
            return False  # Cannot renew if book is reserved
        
        loan.due_date += timedelta(days=additional_days)
        loan.renewal_count += 1
        
        self.circulation_repo.save(loan)
        return True
    
    def calculate_fine(self, loan: Loan) -> float:
        """Calculate fine for overdue loan"""
        if loan.due_date < datetime.now():
            days_overdue = (datetime.now() - loan.due_date).days
            return days_overdue * 1.00  # $1 per day
        return 0.0
```

## Phase 4: Scaling Strategies

### 1. Horizontal Partitioning

#### Time-based Partitioning for Loans
```sql
-- Partition loans by year
CREATE TABLE loans_2024 PARTITION OF loans
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

CREATE TABLE loans_2025 PARTITION OF loans  
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

-- Archive old loans
CREATE TABLE archived_loans (LIKE loans INCLUDING ALL);
```

#### Member-based Sharding
```python
class ShardedMemberRepository:
    def __init__(self, shard_configs):
        self.shards = {}
        for shard_id, config in shard_configs.items():
            engine = create_engine(config['url'])
            self.shards[shard_id] = sessionmaker(bind=engine)
    
    def get_shard_for_member(self, member_id: str) -> str:
        # Hash-based sharding
        return f"shard_{hash(member_id) % len(self.shards)}"
    
    def get_member(self, member_id: str) -> Optional[Member]:
        shard = self.get_shard_for_member(member_id)
        session = self.shards[shard]()
        try:
            return session.query(Member).filter(Member.member_id == member_id).first()
        finally:
            session.close()
```

### 2. Read Replica Strategy

```python
class ScalableLibraryService:
    def __init__(self, write_db_url: str, read_db_urls: List[str]):
        self.write_engine = create_engine(write_db_url)
        self.read_engines = [create_engine(url) for url in read_db_urls]
        self.current_read_engine = 0
    
    def get_write_session(self):
        return sessionmaker(bind=self.write_engine)()
    
    def get_read_session(self):
        # Round-robin across read replicas
        engine = self.read_engines[self.current_read_engine]
        self.current_read_engine = (self.current_read_engine + 1) % len(self.read_engines)
        return sessionmaker(bind=engine)()
    
    def search_catalog(self, query: str):
        # Use read replica for searches
        with self.get_read_session() as session:
            repo = CatalogRepository(session)
            return repo.search_books(query)
    
    def borrow_book(self, member_id: str, copy_id: str):
        # Use write database for transactions
        with self.get_write_session() as session:
            service = CirculationService(
                CirculationRepository(session),
                CatalogRepository(session),
                MemberRepository(session)
            )
            return service.borrow_book(member_id, copy_id)
```

### 3. Caching Strategy

```python
import redis
from typing import Optional, List

class CachedCatalogService:
    def __init__(self, catalog_repo: CatalogRepository, redis_client: redis.Redis):
        self.catalog_repo = catalog_repo
        self.cache = redis_client
        self.cache_ttl = 3600  # 1 hour
    
    def get_book_by_isbn(self, isbn: str) -> Optional[Book]:
        # Try cache first
        cache_key = f"book:isbn:{isbn}"
        cached_book = self.cache.get(cache_key)
        
        if cached_book:
            return json.loads(cached_book)
        
        # Cache miss - fetch from database
        book = self.catalog_repo.find_book_by_isbn(isbn)
        if book:
            # Cache the result
            self.cache.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(book, default=str)
            )
        
        return book
    
    def search_books(self, query: str) -> List[Book]:
        cache_key = f"search:books:{hash(query)}"
        cached_results = self.cache.get(cache_key)
        
        if cached_results:
            return json.loads(cached_results)
        
        books = self.catalog_repo.search_books(query)
        self.cache.setex(
            cache_key,
            self.cache_ttl,
            json.dumps(books, default=str)
        )
        
        return books
```

### 4. Event-Driven Architecture

```python
# events/domain_events.py
class BookBorrowedEvent:
    def __init__(self, loan_id: str, member_id: str, book_id: str, due_date: datetime):
        self.loan_id = loan_id
        self.member_id = member_id
        self.book_id = book_id
        self.due_date = due_date
        self.timestamp = datetime.utcnow()

class BookReturnedEvent:
    def __init__(self, loan_id: str, member_id: str, book_id: str, return_date: datetime):
        self.loan_id = loan_id
        self.member_id = member_id
        self.book_id = book_id
        self.return_date = return_date
        self.timestamp = datetime.utcnow()

# Event handlers for notifications, analytics, etc.
class NotificationEventHandler:
    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service
    
    async def handle_book_borrowed(self, event: BookBorrowedEvent):
        # Send welcome email with due date
        await self.notification_service.send_loan_confirmation(
            event.member_id,
            event.book_id,
            event.due_date
        )
    
    async def handle_book_overdue(self, event: BookOverdueEvent):
        # Send overdue notice
        await self.notification_service.send_overdue_notice(
            event.member_id,
            event.loan_id
        )
```

This comprehensive design follows DDD principles and provides a clear path from domain modeling to scalable database implementation.