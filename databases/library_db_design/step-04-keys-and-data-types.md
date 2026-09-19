# Step 4 — Keys & Data Types

*Series: Designing the LMS Database · Chapter 4 of 12*

---

Step 3 produced seven normalized tables, but every key was a placeholder (`book_id PK`) and not one column had a type. This is the first chapter that is genuinely **PostgreSQL-specific**: we decide what uniquely identifies each row, how that identifier is generated, and what physical type holds every value. In Step 2 terms we are crossing from the logical model toward the physical one.

> **The discipline of this step:** separate **identity** (keys) from **representation** (types), and make each call against a concrete LMS column — never by reflex. Relationships were bone (Step 3); types are skin. We add the skin now. Foreign-key *behavior* and `CHECK` *contents* are still deferred (Step 5).

---

## 4.1 Two jobs: identity and representation

Every column gets two questions answered here:

1. **Identity** — what uniquely names a row (the key), and how that identifier comes into existence.
2. **Representation** — what physical type holds the value.

We deliberately skipped both in Step 3 so that normalization wasn't muddied by `VARCHAR(255)` arguments. Now the relationships are fixed and safe to dress.

---

## 4.2 Surrogate vs. natural keys — and the ISBN trap

A **natural key** already identifies the row from the business domain (ISBN, email, barcode). A **surrogate key** is a synthetic, meaningless-by-design identifier the system invents (an integer or UUID).

ISBN *looks* like the perfect primary key for `book`. It is not:

- **Not universal** — old, rare, or self-published books have no ISBN, and a PK cannot be NULL.
- **Format drift** — ISBN-10 became ISBN-13; bind your PK to a format and the world shifts under it.
- **It mutates** — a mistyped ISBN must be corrected, but the cardinal rule of a primary key is *it never changes*, because a change cascades to every foreign key that references it.

**The discipline:** use a **surrogate PK** for stable identity and joins, and keep the natural key as a `UNIQUE` constraint so business uniqueness is still enforced and you can still look rows up by it. Best of both worlds.

Applied to the LMS:

| Table | Surrogate PK | Natural key kept as `UNIQUE` |
|---|---|---|
| `book` | `book_id` | `isbn` (nullable — not all books have one) |
| `member` | `member_id` | `email` |
| `book_copy` | `copy_id` | `barcode` |
| `author` | `author_id` | — (name isn't reliably unique) |
| `book_author` | **composite `{book_id, author_id}`** | *that pair is its natural key — no surrogate needed* |
| `loan`, `fine` | `loan_id`, `fine_id` | — (pure event records) |

The junction is the one table that *correctly* uses a composite natural key. A surrogate `book_author_id` there would be noise — the pair already identifies the row uniquely **and** doubles as the "no duplicate author on a book" guarantee.

---

## 4.3 ID-generation strategy — `BIGINT IDENTITY` vs. `UUID`

| | Auto-increment `BIGINT` | `UUID` |
|---|---|---|
| Size | 8 bytes, compact | 16 bytes |
| Index locality | Sequential → tight, cache-friendly | Random (v4) → page splits, churn |
| Generation | Needs the DB (a sequence) | Client-side, no round-trip |
| Leaks | Exposes row count & order | Opaque |
| Shines when | Single primary DB | Distributed / multi-master / offline ID creation |

For a single-database, 100-member library, **`BIGINT GENERATED ALWAYS AS IDENTITY`** is the no-regret default: compact, sequential, simple. (`SERIAL` is the legacy spelling — `IDENTITY` is the modern SQL-standard form; prefer it.) `INT` (4 bytes, ~2.1B) would technically suffice, but `BIGINT` costs almost nothing and sidesteps the classic "ran out of IDs" incident. Reach for **UUID** — specifically time-ordered **UUIDv7**, which restores index locality lost by v4 — only if this were ever sharded or generating IDs offline, which Step 12 explicitly rules out at this scale.

---

## 4.4 Type choices — the calls that actually matter

Most columns are unremarkable `TEXT`. Four decisions are not, and they are where engineers get burned:

- **Money → never floating point.** `fine.amount` must be `NUMERIC(8,2)`, never `FLOAT`/`REAL`. Binary floating point cannot represent `0.10` exactly; accumulate enough fines and you get `4.9999999`. `NUMERIC` is exact decimal. Non-negotiable for money.
- **Timestamps → `TIMESTAMPTZ`, never `TIMESTAMP`.** `loan_date`, `return_date`, `paid_date` are *instants*; store them as `TIMESTAMPTZ` (UTC underneath, rendered in any zone). Plain `TIMESTAMP` drops the zone and causes the eternal off-by-hours bugs.
- **`due_date` → `DATE`, deliberately.** The 5-day loan policy yields a *calendar deadline*, not an instant ("due on the 21st," not "due at 14:32:09"). `DATE` models that honestly and makes "days late" clean date arithmetic. (`TIMESTAMPTZ` is defensible too — the point is a *conscious* choice, not a default.)
- **Text → `TEXT`, not `VARCHAR(255)`.** In Postgres `VARCHAR(n)` is *not* faster than `TEXT`; the length cap is the only difference. Use `TEXT` for free-form fields (`title`, `name`) and `VARCHAR(n)` *only* when `n` encodes a real domain rule (`isbn VARCHAR(13)`).

---

## 4.5 Enums — three ways, and which fits

`status`, `condition`, and `membership_status` are constrained value sets. Three implementations:

| Approach | Good | Bad |
|---|---|---|
| Native `ENUM` type | Compact, type-safe | `ALTER TYPE` to evolve is painful (can't easily remove/reorder) |
| **`TEXT` + `CHECK (col IN (...))`** | Readable, evolves with a plain migration | Slightly larger storage |
| Lookup table + FK | Best when the set is large or carries its own attributes | Overkill for a fixed handful |

For the LMS the value sets are small, stable, and code-driven, so **`TEXT` + `CHECK`** wins — no `ALTER TYPE` ceremony when (say) "renewed" is added later. The actual `CHECK` clauses are written in **Step 5**; here we only commit to the approach.

---

## 4.6 Nullability is a type decision — and it carries meaning

Two NULLs in this schema are *load-bearing*, not laziness:

- **`loan.return_date IS NULL` means "still on loan."** It is how we find active loans (borrow-limit check, AP-6) and overdue loans (AP-5). The absence of a value *is* the state.
- **`fine.paid_date IS NULL` means "unpaid."** Same idea — drives AP-8.
- `book.isbn` is nullable because the natural key genuinely may not exist.

Everything else is `NOT NULL`. Naming nullability here sets up Step 5 (constraints) and Step 6 (lifecycle/state).

---

## 4.7 The schema, now with types

```sql
book(
  book_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  isbn     VARCHAR(13) UNIQUE,            -- natural key, nullable
  title    TEXT NOT NULL,
  genre    TEXT
)
author(
  author_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name      TEXT NOT NULL
)
book_author(
  book_id   BIGINT NOT NULL REFERENCES book,
  author_id BIGINT NOT NULL REFERENCES author,
  PRIMARY KEY (book_id, author_id)        -- composite natural key
)
book_copy(
  copy_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  book_id   BIGINT NOT NULL REFERENCES book,
  barcode   VARCHAR(32) UNIQUE NOT NULL,
  condition TEXT NOT NULL,                -- CHECK set -> Step 5
  status    TEXT NOT NULL                 -- CHECK set -> Step 5
)
member(
  member_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name              TEXT NOT NULL,
  email             VARCHAR(255) UNIQUE NOT NULL,
  membership_status TEXT NOT NULL
)
loan(
  loan_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  copy_id     BIGINT NOT NULL REFERENCES book_copy,
  member_id   BIGINT NOT NULL REFERENCES member,
  loan_date   TIMESTAMPTZ NOT NULL,
  due_date    DATE        NOT NULL,
  return_date TIMESTAMPTZ,                 -- NULL = still out
  status      TEXT        NOT NULL
)
fine(
  fine_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  loan_id   BIGINT NOT NULL REFERENCES loan,
  amount    NUMERIC(8,2) NOT NULL,         -- exact decimal, never FLOAT
  status    TEXT NOT NULL,
  paid_date TIMESTAMPTZ                     -- NULL = unpaid
)
```

The `REFERENCES`/`CHECK` specifics — `ON DELETE` behavior, exact enum value lists, the partial-unique "one active loan" index — are **Step 5 and Step 7**. Here the deliverable is *keys + types*.

---

## What we produced in Step 4

- A **key strategy**: surrogate `BIGINT IDENTITY` primary keys everywhere, with natural keys (`isbn`, `email`, `barcode`) preserved as `UNIQUE` — and the `book_author` junction keyed by its composite natural key.
- A reasoned **ID-generation choice** (`BIGINT IDENTITY` now; `UUIDv7` only if ever distributed).
- **Real PostgreSQL types** for every column, with the four load-bearing calls named: `NUMERIC` money, `TIMESTAMPTZ` instants, `DATE` deadline, `TEXT` over `VARCHAR(n)`.
- **Enum approach** chosen (`TEXT` + `CHECK`) and **load-bearing NULLs** identified (`return_date`, `paid_date`).

## Key takeaways (transferable)

1. **Surrogate PK for stability, natural key as `UNIQUE`.** Primary keys must never change; business identifiers (ISBN, email) do.
2. **`BIGINT IDENTITY` is the default; UUID is for distribution.** Don't pay UUID's locality cost without a distribution reason.
3. **Never store money in floating point** — `NUMERIC` always.
4. **`TIMESTAMPTZ` over `TIMESTAMP`; pick `DATE` when the fact is a calendar day.**
5. **NULL can be a designed state** — `return_date IS NULL` *is* "active loan." Name those on purpose.

## Principles in play

| Principle | How this step applied it |
|---|---|
| **Stable identity** | Surrogate keys so FKs never chase a changing business value |
| **Correctness over convenience** | `NUMERIC` for money; `TIMESTAMPTZ` for instants |
| **YAGNI / match-the-scale** | `BIGINT IDENTITY`, not UUID; `TEXT`+`CHECK`, not a lookup table |
| **Meaning in the model** | Load-bearing NULLs (`return_date`, `paid_date`) made explicit |

---

*Next — Step 5: Constraints & referential integrity. We turn the bare `REFERENCES` and the `-- CHECK set` comments into real teeth: `PRIMARY KEY`/`FOREIGN KEY` with chosen `ON DELETE` behavior, `UNIQUE`, `NOT NULL`, and `CHECK` clauses that pin the enum value sets — pushing as many invariants as possible into the database itself rather than trusting application code.*
