# Step 13 — ORM Models & the Repository Pattern

*Series: Designing the LMS Database · Chapter 13 of 13 — series finale (LLD integration)*

---

The schema arc is complete: we can create it (Step 10), evolve it (Step 11), and we've justified not scaling it (Step 12). This final chapter is different in kind — it's the **seam back to the LLD series**. The DB series produced a *schema*; the LLD series produced *pure-Python domain classes*. Step 13 wires them together without letting either leak into the other.

> **The discipline of this step:** keep the domain ignorant of persistence. The domain declares repository *interfaces*; infrastructure implements them with SQLAlchemy. SQL and locking live in adapters; rules and invariants live in the domain; the database remains the last line of defense. The dependency arrow points inward, always.

---

## 13.1 The seam: two models that must not bleed into each other

Two models are in play, and the art is keeping them apart:

- **The domain model** (LLD series): pure-Python classes with *behavior* and *invariants*, and **zero** knowledge of databases.
- **The persistence model** (this series): SQLAlchemy classes that map rows.

The **Repository pattern** is the seam, built on **dependency inversion**: the *domain* declares repository **interfaces** (ports); *infrastructure* provides SQLAlchemy **implementations** (adapters). Infra depends on the domain, never the reverse — the domain never imports `sqlalchemy`. That is what lets you unit-test the domain against an in-memory fake repository and swap the database without touching a business rule.

---

## 13.2 SQLAlchemy 2.0 models (the persistence model)

Typed, declarative, mapping the Step-10 tables one-to-one:

```python
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import ForeignKey, Numeric, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase): ...

class BookModel(Base):
    __tablename__ = "book"
    book_id:    Mapped[int]            = mapped_column(primary_key=True)
    isbn:       Mapped[str | None]     = mapped_column(unique=True)
    title:      Mapped[str]            = mapped_column(Text)
    genre:      Mapped[str | None]     = mapped_column(Text)
    deleted_at: Mapped[datetime | None]
    copies:     Mapped[list["BookCopyModel"]] = relationship(back_populates="book")
    authors:    Mapped[list["AuthorModel"]]   = relationship(secondary="book_author")

class BookCopyModel(Base):
    __tablename__ = "book_copy"
    copy_id:   Mapped[int] = mapped_column(primary_key=True)
    book_id:   Mapped[int] = mapped_column(ForeignKey("book.book_id"))
    barcode:   Mapped[str]
    condition: Mapped[str]
    status:    Mapped[str] = mapped_column(default="AVAILABLE")
    book:      Mapped["BookModel"] = relationship(back_populates="copies")

class LoanModel(Base):
    __tablename__ = "loan"
    loan_id:     Mapped[int] = mapped_column(primary_key=True)
    copy_id:     Mapped[int] = mapped_column(ForeignKey("book_copy.copy_id"))
    member_id:   Mapped[int] = mapped_column(ForeignKey("member.member_id"))
    loan_date:   Mapped[datetime]
    due_date:    Mapped[date]
    return_date: Mapped[datetime | None]

class FineModel(Base):
    __tablename__ = "fine"
    fine_id:   Mapped[int]            = mapped_column(primary_key=True)
    loan_id:   Mapped[int]            = mapped_column(ForeignKey("loan.loan_id"), unique=True)  # 1:0..1
    amount:    Mapped[Decimal]        = mapped_column(Numeric(8, 2))   # Decimal, never float
    paid_date: Mapped[datetime | None]
```

The types carry Step 4's decisions into Python: `Numeric(8,2)` ↔ `Decimal` (never `float` for money), `TIMESTAMPTZ` ↔ `datetime`, `DATE` ↔ `date`, and `fine.loan_id` is `unique=True` to honor the 1:0..1 rule Step 10 caught.

> **Purity fork worth naming:** above, the SQLAlchemy class *is* the persistence model and you map to/from domain objects in the repository. The stricter alternative is SQLAlchemy's **imperative (classical) mapping**, which maps your *pure* domain classes onto `Table()` objects so the domain stays import-free. At this scale either is fine; the purist hexagonal route is imperative mapping, the one most faithful to "the LLD series built pure domain classes."

---

## 13.3 One repository per *aggregate root* — not per table

The biggest decision here, and the one most often gotten wrong: **a repository is per aggregate root, not per table.** An *aggregate* is a cluster of objects treated as one consistency unit, entered only through its **root**:

| Aggregate root | Contains | Repository? |
|---|---|---|
| **Book** | `Book` + its `BookCopy`s + authors | ✅ `BookRepository` |
| **Member** | `Member` | ✅ `MemberRepository` |
| **Loan** | `Loan` + its `Fine` (1:0..1) | ✅ `LoanRepository` |
| BookCopy | — accessed *through* `Book` | ❌ no separate repo |
| Fine | — accessed *through* `Loan` | ❌ no separate repo |

So there is **no `BookCopyRepository` and no `FineRepository`** — a copy is loaded and saved via its `Book`, a fine via its `Loan`. The aggregate boundary *is* the transactional/consistency boundary, which is exactly why it maps so cleanly onto the Step-7 invariants.

---

## 13.4 The port (domain) and the adapter (infra)

```python
# domain/ports.py  — pure: no SQLAlchemy import anywhere
from typing import Protocol
class LoanRepository(Protocol):
    def add(self, loan: Loan) -> None: ...
    def count_active_for_member(self, member_id: int) -> int: ...
    def active_loan_for_copy(self, copy_id: int) -> Loan | None: ...
```

```python
# infrastructure/sqlalchemy_repos.py  — the adapter
from sqlalchemy import select, func
class SqlAlchemyLoanRepository:                 # structurally satisfies LoanRepository
    def __init__(self, session): self._s = session
    def add(self, loan): self._s.add(to_model(loan))
    def count_active_for_member(self, member_id):
        return self._s.scalar(
            select(func.count()).select_from(LoanModel)
            .where(LoanModel.member_id == member_id, LoanModel.return_date.is_(None)))
```

The domain depends only on the `Protocol`; the SQL lives entirely in the adapter.

---

## 13.5 Where Step 7's transaction goes: the Unit of Work

The issue operation (AP-3) spans *two* aggregates — it creates a `Loan` **and** flips a `BookCopy.status`. That coordination is an **application service** wrapped in a **Unit of Work** (one transaction across repositories). The key realization: **SQLAlchemy's `Session` already _is_ a Unit of Work** (plus an Identity Map), so the UoW is a thin wrapper over `session.begin()`.

```python
class IssueBookService:
    def __init__(self, uow): self._uow = uow

    def issue(self, member_id: int, book_id: int) -> Loan:
        with self._uow:                                        # one DB transaction
            member = self._uow.members.get_for_update(member_id)        # Step 7: lock member row
            if member.status != "ACTIVE":
                raise MembershipInactive
            if self._uow.loans.count_active_for_member(member_id) >= 2: # Step 7: borrow-limit B2
                raise BorrowLimitExceeded
            copy = self._uow.books.pick_available_copy_for_update(book_id)  # FOR UPDATE SKIP LOCKED
            if copy is None:
                raise NoCopyAvailable
            loan = Loan.issue(copy, member)                    # DOMAIN decides the rule (due_date = +5d)
            copy.mark_loaned()                                 # domain state change
            self._uow.loans.add(loan)                          # partial unique index = B1 backstop
            self._uow.commit()
            return loan
```

How the responsibilities split is the whole series converging:

- **The domain** owns the *rules*: `Loan.issue` computes the due date; `copy.mark_loaned()` enforces valid copy transitions.
- **The repository/UoW** owns *persistence and locking*: `get_for_update` is where Step 7's `FOR UPDATE` lives; `pick_available_copy_for_update` is the `FOR UPDATE SKIP LOCKED`. SQL stays out of the domain, but the domain's *intent* (serialize per member) is honored in infra.
- **The database** is the final backstop: the partial unique index makes B1 unrepresentable no matter what the code does.

---

## 13.6 The synthesis: where every invariant lives now

The series' payoff — defense in depth, each invariant enforced at the right layer(s):

| Invariant | Domain | Repository / UoW | Database |
|---|---|---|---|
| `amount >= 0`, enum values | — | — | **`CHECK`** (Step 5) |
| referential integrity | — | — | **`FOREIGN KEY`** (Step 5) |
| one active loan / copy (B1) | guard in `mark_loaned` | — | **partial unique index** (Step 7) ← last line |
| borrow-limit ≤ 2 (B2) | rule in service | **`FOR UPDATE` + count** (Step 7) | — |
| availability = copies' status | `Book.is_available` | updated in same txn | source of truth (Step 1) |
| due date = loan + 5d | **`Loan.issue`** | persisted | stored value (Step 1/4) |

The database is the last line of defense; the domain is the first; the repository/Unit-of-Work is the transaction boundary that makes them cooperate. That layering is the whole point of the series.

---

## What we produced in Step 13

- **SQLAlchemy 2.0 models** mapping all seven tables, carrying Step-4 types into Python (`Decimal` money, `datetime`/`date`, the 1:0..1 `unique` on `fine.loan_id`).
- The **Repository pattern** as a dependency-inverted seam: ports in the domain, SQLAlchemy adapters in infrastructure — **one repository per aggregate root** (Book, Member, Loan), not per table.
- The Step-7 issue transaction expressed as an **application service over a Unit of Work**, with locking in the adapter and rules in the domain — and the recognition that SQLAlchemy's `Session` *is* the Unit of Work.
- A **synthesis table** placing every invariant from the whole series at the layer(s) that enforce it — defense in depth, domain-first and DB-last.

## Key takeaways (transferable)

1. **Repository = port in the domain, adapter in infra.** The domain never imports the ORM; dependency points inward.
2. **One repository per aggregate root, not per table.** Copies go through `Book`, fines through `Loan`.
3. **The Unit of Work is the transaction boundary** — and SQLAlchemy's `Session` already implements it.
4. **Locking is an infra concern, the rule is a domain concern.** `FOR UPDATE` lives in the repo; "max 2" lives in the service/domain.
5. **Invariants are defended in depth** — domain first, DB last — and a good schema makes the worst outcomes *unrepresentable*.

## Principles in play

| Principle | How this step applied it |
|---|---|
| **Dependency inversion** | Domain defines repository interfaces; infra implements them |
| **Aggregate as consistency boundary** | Repos per root; cross-aggregate issue wrapped in one UoW |
| **Persistence ignorance** | Pure domain; SQL and locking confined to adapters |
| **Defense in depth** | Step-7 invariants enforced across domain, UoW, and DB together |

---

## 🎓 Series complete

Thirteen chapters, from **a list of questions** (Step 1) to **a runnable, race-proof, evolvable schema wired to a clean domain** (Step 13) — and at no point did we type `CREATE TABLE` before we'd earned it. The spine that held throughout:

- **Access patterns before tables** — the workload is the spec.
- **One source of truth** — every fact in exactly one place; derive the rest.
- **Don't store what you can derive** — unless the input is volatile or measurement demands a cache.
- **Match the design to the scale** — and refuse, consciously, the scale you don't have.
- **Push every invariant to the layer that can guarantee it** — domain first, database last.

*This completes the "Designing the LMS Database" series. The schema (Steps 1–12) defines persistence; this chapter (Step 13) is the seam to the LLD/DDD domain model — the same persistence-ignorant ports as LLD Step 10.*
