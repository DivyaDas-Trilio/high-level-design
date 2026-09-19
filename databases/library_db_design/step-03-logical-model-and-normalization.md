# Step 3 — Logical Model & Normalization

*Series: Designing the LMS Database · Chapter 3 of 12*

---

Step 2 drew the *shape* — entities and the exact cardinality of each relationship. Step 3 turns that shape into **actual tables with actual columns**, and proves — not asserts — that every fact lives in exactly one place. The proof tool is **normalization**. This is the same move your LLD series made going from a conceptual class map to concrete classes with fields: the relationships were already decided; now we give them structure.

> **The discipline of this step:** decide *what columns live in what tables* and drive each table through 1NF→2NF→3NF against a **concrete LMS violation** — not the textbook abstraction. Still **no data types** (Step 4) and **no indexes** (Step 8). Types are skin; we're setting bone.

---

## 3.1 The three levels — where we are now

| Level | Answers | Contains |
|---|---|---|
| Conceptual (Step 2) | *What exists & how does it relate?* | Entities, relationships, cardinality |
| **Logical (this step)** | *What does each table look like, normalized?* | **Tables, columns, keys, normal forms — engine-agnostic** |
| Physical (Step 10) | *How does it run on Postgres?* | Types, indexes, `CREATE TABLE`, storage |

We're in the middle. The output is a set of normalized, still-engine-agnostic tables. `book_id PK` here is a **conceptual role**, not a chosen type — surrogate-vs-natural and `BIGINT` vs `UUID` are Step 4.

---

## 3.2 Why normalize? The three anomalies

Normalization is not ceremony — it exists to kill three concrete bugs that redundancy causes. Picture the lazy "one big table" design where each loan row also carries the member's name/email and the book's title and authors:

- **Update anomaly** — a member changes her email. It's duplicated across 40 loan rows; you must update all 40. Miss one → two "truths," drift. (Step 1's *single source of truth*, now with teeth.)
- **Insertion anomaly** — you can't catalog an author until they've written a book, because the author only exists *inside* a book row.
- **Deletion anomaly** — you delete the last book by an author and the author vanishes entirely, even though you wanted to keep them.

Normalization is the disciplined removal of the redundancy that causes these. It's driven by **functional dependencies** — "given X, is Y completely determined?" `member_id → email` (one member, one email). Each normal form is a progressively stricter rule about which dependencies are allowed to live in a single table.

---

## 3.3 First Normal Form (1NF) — atomic values, no repeating groups

**Rule:** every cell holds one value; no lists, no repeating columns.

Our violation is **authors**. The tempting design:

```text
book(book_id, isbn, title, authors)
   (1, "978-...", "Design Patterns", "Gamma, Helm, Johnson, Vlissides")
```

That `authors` cell is a list — not atomic. You can't index it, can't query "all books by Helm" without `LIKE '%Helm%'` (which also matches "Helmsley"), can't enforce that an author exists. **1NF says: get the repeating group out of the row.** That single decision is what forces an `author` entity into existence — exactly the Book↔Author M:N we deferred in Step 2.

---

## 3.4 Second Normal Form (2NF) — no partial dependency on a composite key

**Rule:** (assuming 1NF) no non-key column may depend on only *part* of a composite key. 2NF only bites when you have a **composite primary key** — which is precisely the junction table 1NF just created.

Resolving the M:N gives us a junction:

```text
book_author(book_id, author_id)        -- composite PK {book_id, author_id}
```

Now imagine someone "helpfully" adds the author's name to it:

```text
book_author(book_id, author_id, author_name)   -- VIOLATION
```

`author_name` depends only on `author_id` — *part* of the key, not the whole key. That's a partial dependency → 2NF violation, and it reintroduces the update anomaly (rename an author = update every junction row). **Fix:** `author_name` belongs in `author`, keyed by the whole of *its* key. The junction stays pure — just the two foreign keys, nothing else.

---

## 3.5 Third Normal Form (3NF) — no transitive dependency

**Rule:** (assuming 2NF) no non-key column may depend on *another non-key column*. Every non-key fact depends on **the key, the whole key, and nothing but the key.**

Our violation is the convenience-denormalized `loan`:

```text
loan(loan_id, copy_id, member_id, member_email, loan_date, due_date, ...)
```

`member_email` depends on `member_id`, which is itself a non-key column — a **transitive dependency** (`loan_id → member_id → member_email`). Update anomaly again. **Fix:** `loan` keeps only `member_id` (the FK); the email lives once, in `member`. To show an email beside a loan, you *join* — you don't *store*.

> For most business schemas, **3NF is where you stop.** BCNF/4NF/5NF exist and matter for exotic overlapping-key situations, but chasing them for this 100-member library is over-engineering.

---

## 3.6 Settling the two open forks from Step 2

Normalization doesn't just produce tables — it *answers* the questions we deliberately left open:

**Genre — stays an attribute.** Requirements only filter *by* genre (AP-1); there are no genre facts to store beyond the label. A `genre` column on `book` is 3NF-clean (one genre per book is a simple dependency). Promoting it to a `category` table + junction is a one-migration change *if* multi-category search ever appears. KISS wins.

**Member→Fine direct link — 3NF makes the call for us.** In Step 2 we flagged "should `fine` carry `member_id` directly, or reach it via `loan`?" Watch: a fine arises from a loan, and a loan already owns its member. So `fine_id → loan_id → member_id` — putting `member_id` on `fine` is a **transitive dependency, a textbook 3NF violation.** So the normalized answer is **no direct link.** `fine` references `loan`; "total outstanding for a member" (AP-8) becomes a three-table join (`member → loan → fine`), trivial at this scale. *If* profiling ever shows it hot, adding the redundant `member_id` is a deliberate, measured denormalization — that's Step 9's job, made consciously, not by accident now.

---

## 3.7 The resulting logical schema

Every decision together — columns only, **no types yet**, keys as conceptual roles:

```text
book         (book_id PK, isbn, title, genre)
author       (author_id PK, name)
book_author  (book_id FK→book, author_id FK→author,  PK {book_id, author_id})
book_copy    (copy_id PK, book_id FK→book, barcode, condition, status)
member       (member_id PK, name, email, membership_status)
loan         (loan_id PK, copy_id FK→book_copy, member_id FK→member,
              loan_date, due_date, return_date, status)
fine         (fine_id PK, loan_id FK→loan, amount, status, paid_date)
```

Seven tables. Trace the Step-1 access patterns through them and they all resolve cleanly — AP-2 (availability) is a `COUNT` over `book_copy.status`; AP-8 (outstanding) is the `member→loan→fine` join we just justified. Every fact sits in exactly one place.

---

## What we produced in Step 3

- A **normalized logical schema** of seven engine-agnostic tables, derived from the Step-2 ER model.
- The Book↔Author M:N **resolved** into an `author` table plus a `book_author` junction (1NF→2NF in action).
- Two Step-2 forks **closed by normalization itself**: genre stays an attribute; `fine` gets *no* direct `member_id` (it would be a 3NF violation).
- The keystone: every non-key fact depends on **the key, the whole key, and nothing but the key** — drift has nowhere to live.

## Key takeaways (transferable)

1. **Normalize to kill anomalies, not to score points.** Update/insert/delete anomalies are the *why*; normal forms are the *how*.
2. **1NF forces M:N resolution.** A repeating group (authors) can't be atomic, so it becomes its own table + junction.
3. **2NF is a junction-table concern** — partial dependencies only exist when there's a composite key.
4. **3NF = "the key, the whole key, and nothing but the key."** Transitive dependencies (a member's email on a loan) are the common real-world slip.
5. **Normalization resolves design forks objectively** — it told us *not* to put `member_id` on `fine`. Denormalization is a later, measured exception, never the default.

## Principles in play

| Principle | How this step applied it |
|---|---|
| **Single Source of Truth** | Each fact (email, author name) lives in one table; joins, not copies |
| **YAGNI / KISS** | Genre stays an attribute; stop at 3NF, no BCNF chasing |
| **Normalization discipline** | 1NF→2NF→3NF walked explicitly, each against a concrete LMS violation |
| **Measure before optimizing** | Refused the `fine.member_id` shortcut; deferred to Step 9 *if* profiling demands |

---

*Next — Step 4: Keys & data types. `book_id PK` stops being a placeholder: we decide surrogate (`BIGINT`/`UUID`) vs natural (ISBN) keys, choose an ID-generation strategy, and pin real PostgreSQL types onto every column. This is where the logical schema starts becoming physical.*
