# Step 10 — The Physical Schema (DDL)

*Series: Designing the LMS Database · Chapter 10 of 12*

---

This is the convergence chapter. No new theory — every decision from Steps 3–9 assembles into a single PostgreSQL script you could pipe into `psql`. But "assemble" undersells it: writing the whole schema in one file forces you to see it *together* for the first time, and seeing it together is a design review that catches what the chapter-by-chapter view hid.

> **The discipline of this step:** treat assembly as a review, not transcription. Create objects in dependency order, wrap the creation in a single transaction, and enforce in DDL every invariant earlier chapters only *described*. The deliverable is the artifact the whole series has been building toward.

---

## 10.1 Assembly is a design review

Putting it all in one place surfaced two issues immediately.

**Gap 1 — `fine.loan_id` must be `UNIQUE`.** Step 2 decided Loan→Fine is **1:0..1** ("at most one fine per loan"). Nine chapters later that invariant was *described* but never *enforced* — nothing stopped two fine rows pointing at one loan. The DDL is where it becomes real: `loan_id BIGINT NOT NULL UNIQUE`. This is precisely why you assemble — invariants stated in prose quietly fail to become constraints.

**Gap 2 — a planned index is now redundant.** Step 8 planned `CREATE INDEX ON fine(loan_id)` for AP-8's join. But making `loan_id` `UNIQUE` (Gap 1) *creates that index automatically*. Keeping both would mean a duplicate index taxing every write, so the standalone index drops from the final set. Decisions interact; only assembly reveals it.

---

## 10.2 Dependency order — the one mechanical rule

A `REFERENCES book(book_id)` requires `book` to already exist, so objects are created in **topological order**, parents before children:

```
book, author  →  book_author, book_copy  →  member  →  loan  →  fine
```

The alternative — create all tables, then `ALTER TABLE … ADD CONSTRAINT` the FKs afterward — is what migration tools often generate to dodge ordering and circular references. We have no cycles, so straight dependency order is cleanest.

---

## 10.3 One transaction, all-or-nothing

A subtle PostgreSQL gift: **DDL is transactional.** Wrap the script in `BEGIN; … COMMIT;` and a failure on object #15 rolls back the first 14 — you never get a half-built schema. (Oracle and MySQL auto-commit each DDL statement; this is a real Postgres advantage worth using.)

---

## 10.4 The schema

```sql
-- =====================================================================
-- Library Management System — Physical Schema (PostgreSQL)
-- Assembled from Steps 3–9. Created in dependency order, one transaction.
-- =====================================================================
BEGIN;

-- ---------- Core catalog ----------

CREATE TABLE book (
    book_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    isbn       VARCHAR(13) UNIQUE,                       -- natural key, nullable (Step 4)
    title      TEXT NOT NULL,
    genre      TEXT,
    deleted_at TIMESTAMPTZ                               -- NULL = live; soft-delete (Step 6)
);

CREATE TABLE author (
    author_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name      TEXT NOT NULL
);

CREATE TABLE book_author (                              -- M:N junction (Step 3)
    book_id   BIGINT NOT NULL REFERENCES book(book_id)     ON DELETE CASCADE,
    author_id BIGINT NOT NULL REFERENCES author(author_id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, author_id)
);

CREATE TABLE book_copy (
    copy_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    book_id   BIGINT NOT NULL REFERENCES book(book_id) ON DELETE RESTRICT,
    barcode   VARCHAR(32) NOT NULL UNIQUE,
    condition TEXT NOT NULL CHECK (condition IN ('NEW','GOOD','WORN','DAMAGED')),
    status    TEXT NOT NULL DEFAULT 'AVAILABLE'
              CHECK (status IN ('AVAILABLE','LOANED','LOST','DAMAGED'))   -- real lifecycle (Step 6)
);

-- ---------- People ----------

CREATE TABLE member (
    member_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name              TEXT NOT NULL,
    email             VARCHAR(255) NOT NULL,
    membership_status TEXT NOT NULL DEFAULT 'ACTIVE'
                      CHECK (membership_status IN ('ACTIVE','SUSPENDED','CANCELLED'))  -- soft-delete via CANCELLED
);

-- email unique only among non-cancelled members → frees the address on cancel (Step 6)
CREATE UNIQUE INDEX member_email_active_uq
    ON member (email) WHERE membership_status <> 'CANCELLED';

-- ---------- Transactions (the immutable ledger) ----------

CREATE TABLE loan (
    loan_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    copy_id     BIGINT NOT NULL REFERENCES book_copy(copy_id) ON DELETE RESTRICT,
    member_id   BIGINT NOT NULL REFERENCES member(member_id)  ON DELETE RESTRICT,
    loan_date   TIMESTAMPTZ NOT NULL DEFAULT now(),
    due_date    DATE        NOT NULL,
    return_date TIMESTAMPTZ,                             -- NULL = still out (Step 6)
    CHECK (return_date IS NULL OR return_date >= loan_date),
    CHECK (due_date >= loan_date::date)
);

CREATE TABLE fine (
    fine_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    loan_id   BIGINT NOT NULL UNIQUE REFERENCES loan(loan_id) ON DELETE RESTRICT,  -- UNIQUE = 1:0..1 (Gap 1)
    amount    NUMERIC(8,2) NOT NULL CHECK (amount >= 0),   -- exact decimal money (Step 4)
    paid_date TIMESTAMPTZ                                  -- NULL = unpaid (Step 6)
);

-- ---------- Invariant index (Step 7) ----------

CREATE UNIQUE INDEX one_active_loan_per_copy             -- B1: at most one active loan per copy
    ON loan (copy_id) WHERE return_date IS NULL;

-- ---------- Read indexes (Step 8) ----------

CREATE INDEX book_title_idx          ON book (title);                                -- AP-1
CREATE INDEX author_name_idx         ON author (name);                              -- AP-1
CREATE INDEX book_author_author_idx  ON book_author (author_id);                    -- AP-1 (reverse of PK)
CREATE INDEX book_copy_book_status_idx ON book_copy (book_id, status);              -- AP-2 / AP-3
CREATE INDEX loan_member_active_idx  ON loan (member_id) WHERE return_date IS NULL; -- AP-6 + borrow-limit
CREATE INDEX loan_due_active_idx     ON loan (due_date)  WHERE return_date IS NULL; -- AP-5
-- NB: fine(loan_id) index intentionally omitted — the UNIQUE above already provides it (Gap 2)

-- ---------- Derived-state & visibility views (Step 6) ----------

CREATE VIEW loan_status AS
SELECT loan_id, copy_id, member_id, loan_date, due_date, return_date,
       CASE WHEN return_date IS NOT NULL    THEN 'RETURNED'
            WHEN due_date < CURRENT_DATE     THEN 'OVERDUE'
            ELSE 'ACTIVE' END AS status
FROM loan;

CREATE VIEW fine_status AS
SELECT fine_id, loan_id, amount, paid_date,
       CASE WHEN paid_date IS NOT NULL THEN 'PAID' ELSE 'UNPAID' END AS status
FROM fine;

CREATE VIEW active_book AS
SELECT * FROM book WHERE deleted_at IS NULL;

CREATE VIEW member_visible_copy AS                       -- AP-11 visibility rule
SELECT * FROM book_copy WHERE status IN ('AVAILABLE','LOANED');

COMMIT;
```

---

## 10.5 What this script deliberately leaves out

- **The issue/return transactions (Step 7)** aren't here — those are *application* logic (`FOR UPDATE`, count, insert), not schema. DDL defines structure; the locking dance lives in the app/repository layer (Step 13).
- **No `DROP`s, no `IF NOT EXISTS`.** This is the from-zero creation script. Evolving an *existing* database safely — additive changes, backfills, zero-downtime — is **Step 11 (migrations)**. A raw `CREATE` script and a migration are different artifacts for different moments.
- **No seed data.** Schema only.

---

## What we produced in Step 10

- The **complete, runnable PostgreSQL schema** — seven tables, the partial unique invariant index, the justified read indexes, and the derived-state/visibility views — in dependency order inside one transaction.
- Two **assembly-caught fixes**: `fine.loan_id` made `UNIQUE` to enforce the 1:0..1 rule, and the now-redundant `fine(loan_id)` index removed.
- A clear boundary statement of what DDL is *not*: no app-side transaction logic, no migrations, no seed data.

## Key takeaways (transferable)

1. **Assembling the full DDL is a review pass** — it catches invariants described but never enforced, and now-redundant indexes.
2. **Create in dependency order**; parents before children, or add FKs by `ALTER` afterward.
3. **PostgreSQL DDL is transactional** — wrap creation in `BEGIN…COMMIT` for all-or-nothing.
4. **A `UNIQUE` constraint brings its own index** — don't also hand-create one on the same column.
5. **DDL is structure, not behavior** — concurrency logic (Step 7) and evolution (Step 11) are separate artifacts.

## Principles in play

| Principle | How this step applied it |
|---|---|
| **Convergence over novelty** | Every prior decision realized in one runnable artifact |
| **Invariants enforced, not described** | The 1:0..1 rule became `UNIQUE`, not a comment |
| **No redundant cost** | Dropped the index the `UNIQUE` already supplies |
| **Right artifact for the moment** | `CREATE` script now; migrations (Step 11) for evolution |

---

*Next — Step 11: Migrations & evolution. The schema above is the from-zero state; real databases change while live. We cover versioned migrations (Alembic), the additive expand/contract pattern for zero-downtime changes, why every migration needs a tested rollback, and how a destructive change (dropping a column, adding a `NOT NULL`) is staged so it never locks a production table or loses data.*
