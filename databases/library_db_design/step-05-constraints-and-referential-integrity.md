# Step 5 — Constraints & Referential Integrity

*Series: Designing the LMS Database · Chapter 5 of 12*

---

Step 4 gave every column a key and a type — the schema can now be created. But it can still *hold* nonsense: a fine of −₹50, a loan returned before it was issued, a copy whose `status` is `'banana'`, a loan pointing at a member who was deleted. Step 5 makes that nonsense **impossible** by pushing invariants into the database itself.

> **The discipline of this step:** for every rule, ask *"can the database enforce this, and should it?"* Push down everything it can express as a declarative constraint; reserve the application layer for cross-aggregate policy and friendly messaging. Cross-row invariants that a `CHECK` can't express are named and deferred to Step 7 — knowing a tool's limit is part of using it.

---

## 5.1 The core principle: the database is the last line of defense

Application-layer validation only protects the *one path that goes through the application*. Data, however, is written by many hands: a future second service, an admin running `psql`, a bulk import, a buggy code path, two requests racing. **A database constraint is a guarantee that holds no matter who writes.** Application code can be bypassed; a `CHECK` cannot.

So it is never "DB *or* app" — it is both, for different reasons:

- **App validation = UX.** Early, friendly, "that email's taken" *before* the round-trip.
- **DB constraint = correctness.** The guarantee that the invariant is actually true, always.

The cost is real and worth naming: constraints surface as raw exceptions (uglier than curated app errors), and they make bulk loads and some migrations stricter. For genuine invariants, that rigidity is the *point*.

SQL gives us five tools: `PRIMARY KEY`, `FOREIGN KEY` (+ `ON DELETE`), `UNIQUE`, `NOT NULL`, `CHECK`.

---

## 5.2 `NOT NULL` and `UNIQUE` — codifying Step 4's decisions

`NOT NULL` is a one-word statement that "this fact must exist." We named the load-bearing NULLs in Step 4, so this just makes the negatives explicit: `loan.member_id NOT NULL` (a loan to nobody is nonsense, Step 2), while `loan.return_date` *stays* nullable because `NULL` *is* the "still out" state.

`UNIQUE` enforces business identity beyond the surrogate PK:

| Column | Why |
|---|---|
| `book.isbn` | no two books share an ISBN |
| `member.email` | one account per email |
| `book_copy.barcode` | physical barcodes are unique |

One subtlety worth internalizing: **`UNIQUE` on a nullable column allows many NULLs** — Postgres treats NULLs as distinct. That is *exactly* right for `isbn`: many books with no ISBN are fine, but those that have one can't collide. (PostgreSQL 15+ offers `UNIQUE NULLS NOT DISTINCT` for the opposite behavior.)

---

## 5.3 `CHECK` — pinning value sets and ranges (single-row only)

First, the enum sets deferred from Step 4 become `CHECK`s:

```sql
status    TEXT NOT NULL CHECK (status IN ('AVAILABLE','LOANED','LOST','DAMAGED'))   -- book_copy
condition TEXT NOT NULL CHECK (condition IN ('NEW','GOOD','WORN','DAMAGED'))        -- book_copy
```

Then range and cross-column rules:

```sql
amount NUMERIC(8,2) NOT NULL CHECK (amount >= 0)                       -- no negative fines
CHECK (return_date IS NULL OR return_date >= loan_date)               -- can't return before borrowing
```

**The hard limit to remember: a `CHECK` sees only its own row.** It cannot reference other rows or other tables. So two real invariants are *not* `CHECK`able:

- "a member may hold **at most 2 active loans**" (counts other `loan` rows),
- "at most **one active loan per copy**" (counts other `loan` rows).

Those are cross-row invariants → they belong to **Step 7** (transactions + a partial unique index). Knowing *what a `CHECK` can't do* is as important as what it can.

> **A redundancy smell surfaces here.** Going to write `CHECK (loan.status IN (...))`, you hit a wall: `ACTIVE` vs `RETURNED` is already encoded by `return_date IS NULL`, and `OVERDUE` is *derived from today* — which Step 1's keystone says we must **never store**. So `loan.status` (and likewise `fine.status` shadowing `paid_date`) carries no fact its timestamp doesn't already carry. At minimum the `CHECK` must forbid `'OVERDUE'` as a stored value. Whether these status columns should exist *at all* is exactly the lifecycle question **Step 6** resolves — flagged here, not silently kept.

---

## 5.4 Foreign keys & `ON DELETE` — the meatiest decision

Every FK needs a delete policy, and the choice encodes a business rule. The options: `RESTRICT` (block the delete), `CASCADE` (delete the children too), `SET NULL`, `NO ACTION` (the default).

Walk each FK and a clear pattern emerges:

| Foreign key | Policy | Why |
|---|---|---|
| `book_copy.book_id → book` | **RESTRICT** | Don't delete a title that has physical copies |
| `loan.copy_id → book_copy` | **RESTRICT** | A copy with loan history must never be orphaned |
| `loan.member_id → member` | **RESTRICT** | Preserve a member's loan/fine history |
| `fine.loan_id → loan` | **RESTRICT** | A fine without its loan is meaningless |
| `book_author.book_id → book` | **CASCADE** | The link is meaningless without the book |
| `book_author.author_id → author` | **CASCADE** | Same — pure association, safe to remove |

> **The transferable insight: history-bearing references get `RESTRICT`; pure associative links get `CASCADE`.** A junction row is just "these two relate" — delete it freely with its parent. A loan is a *historical fact* — never let it dangle or vanish.

This has a direct consequence that sets up the next chapter: `RESTRICT` means you **literally cannot `DELETE` a member who has ever borrowed a book**. So how is AP-10 ("remove a member") satisfied? You *don't* hard-delete — you **deactivate** (`membership_status = 'CANCELLED'`). That is the **soft-delete** pattern, the heart of **Step 6**.

One more callback: we need `ON UPDATE CASCADE` nowhere, because our PKs are **surrogate and immutable** (Step 4). Keys that never change can't trigger update cascades — a quiet dividend of choosing surrogate keys.

---

## 5.5 Where to enforce — a decision rule

| Invariant kind | Enforce in… | Example |
|---|---|---|
| Single-row value / range | **DB `CHECK`** | `amount >= 0` |
| Set membership | **DB `CHECK`** | `status IN (...)` |
| Referential integrity | **DB `FOREIGN KEY`** | loan → member |
| Uniqueness | **DB `UNIQUE`** | `email` |
| Cross-row / cross-aggregate policy | **app + DB safety net** (Step 7) | borrow-limit, one-active-loan |

Push everything the DB *can* express down into the DB; reserve the app layer for cross-aggregate policy and friendly messaging — and even then, back it with a DB-level guard wherever one exists.

---

## 5.6 Representative DDL (constraints in place)

```sql
CREATE TABLE book_copy (
  copy_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  book_id   BIGINT NOT NULL REFERENCES book(book_id) ON DELETE RESTRICT,
  barcode   VARCHAR(32) NOT NULL UNIQUE,
  condition TEXT NOT NULL CHECK (condition IN ('NEW','GOOD','WORN','DAMAGED')),
  status    TEXT NOT NULL DEFAULT 'AVAILABLE'
            CHECK (status IN ('AVAILABLE','LOANED','LOST','DAMAGED'))
);

CREATE TABLE loan (
  loan_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  copy_id     BIGINT NOT NULL REFERENCES book_copy(copy_id) ON DELETE RESTRICT,
  member_id   BIGINT NOT NULL REFERENCES member(member_id) ON DELETE RESTRICT,
  loan_date   TIMESTAMPTZ NOT NULL DEFAULT now(),
  due_date    DATE NOT NULL,
  return_date TIMESTAMPTZ,
  CHECK (return_date IS NULL OR return_date >= loan_date),
  CHECK (due_date >= loan_date::date)
);

CREATE TABLE book_author (
  book_id   BIGINT NOT NULL REFERENCES book(book_id)     ON DELETE CASCADE,
  author_id BIGINT NOT NULL REFERENCES author(author_id) ON DELETE CASCADE,
  PRIMARY KEY (book_id, author_id)
);
```

The "one active loan per copy" partial unique index belongs with concurrency, so it lands in **Step 7**, not here. This still isn't the final consolidated script — that is **Step 10**.

---

## What we produced in Step 5

- A full **constraint layer**: `NOT NULL`/`UNIQUE` codifying Step 4's nullability and natural keys; `CHECK`s pinning enum sets and value ranges.
- A reasoned **`ON DELETE` policy for every foreign key**, crystallized into one rule: **`RESTRICT` history, `CASCADE` associations.**
- A **decision rule** for DB-vs-app enforcement, and an explicit list of the cross-row invariants a `CHECK` *cannot* express (deferred to Step 7).
- Two flags forward: `RESTRICT` forces the **soft-delete** pattern (Step 6), and the `status`-shadows-timestamp redundancy is teed up for Step 6.

## Key takeaways (transferable)

1. **The DB is the last line of defense.** App checks are for UX; constraints are the guarantee, because they can't be bypassed.
2. **`CHECK` is single-row only.** Cross-row invariants (counts, "one active") need Step 7, not a `CHECK`.
3. **`ON DELETE`: `RESTRICT` history, `CASCADE` associations.** Never let a historical fact dangle or vanish.
4. **`RESTRICT` forces soft-delete.** If you can't delete a member, you deactivate one — that's Step 6.
5. **Surrogate keys mean no `ON UPDATE CASCADE`.** Immutable PKs pay off again.

## Principles in play

| Principle | How this step applied it |
|---|---|
| **Correctness at the lowest layer** | Invariants enforced in the DB, not just trusted to app code |
| **Single Source of Truth** | `CHECK` exposed `status` columns shadowing timestamps (→ Step 6) |
| **History is sacred** | `RESTRICT` on every history-bearing FK; nothing orphaned |
| **Know the tool's limits** | `CHECK` can't see other rows → cross-row rules deferred to Step 7 |

---

*Next — Step 6: State, lifecycle & history. We resolve the `status`-vs-timestamp redundancy flagged twice now, implement soft-delete (the consequence of `RESTRICT`), and decide how much history the schema must keep — status columns, soft-delete flags, and audit/history tables, each justified by an access pattern rather than added by reflex.*
