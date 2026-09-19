# Step 8 — Indexing Strategy

*Series: Designing the LMS Database · Chapter 8 of 12*

---

Step 1 told us this workload is **read-heavy** — search and availability dominate — and the write paths are now correct (Step 7). Step 8 collects the read dividend by adding indexes, under one rule that keeps an index list from metastasizing into a write-killing swamp: **no index without a Step-1 access pattern to justify it.**

> **The discipline of this step:** an index is a bet that read savings beat the write tax. The AP-1…AP-11 table is the only thing allowed to settle a bet. Inventory what the constraints already gave you for free, add only what a query needs, and treat *refusing* an index as a real design decision.

---

## 8.1 What an index is, and what it actually costs

A B-tree index is a separate, sorted structure mapping a column's values to row locations — turning an O(n) sequential scan into an O(log n) lookup. That's the upside. The downside is non-negotiable and is the whole reason indexing is a *strategy*, not "index everything":

> **An index speeds up reads on its column and slows down _every_ write to the table** — each `INSERT`/`UPDATE`/`DELETE` must maintain every index — plus disk and planner overhead.

So every index is a *bet*: "this column is read often enough that the read savings beat the write tax."

**An honesty note for our scale:** at 500 books and 100 members, PostgreSQL will often sequential-scan and finish in microseconds regardless — most of these indexes won't *matter* operationally. We design them anyway because the **method** transfers to the table with 50 million rows. Flagged below where an index is method-not-need.

---

## 8.2 The indexes you already have — for free

Before adding anything, inventory what the constraints already bought. Each is a working B-tree:

| Source | Index | Also serves |
|---|---|---|
| every `PRIMARY KEY` | unique index on the PK | all PK lookups & joins |
| `UNIQUE` (Step 5) | `book.isbn`, `member.email`, `book_copy.barcode` | lookup-by-natural-key |
| partial unique (Step 7) | `one_active_loan_per_copy` on `loan(copy_id) WHERE return_date IS NULL` | **AP-4 return** — "find the active loan for this copy" comes free |

That last one is the payoff: an index built for *correctness* (one active loan per copy) is *also* the exact index AP-4's return path needs. Good schema decisions compound.

---

## 8.3 The gotcha that bites everyone: Postgres does **not** index foreign keys

The single most common real-world indexing miss:

> **PostgreSQL automatically indexes the _referenced_ (parent PK) side of a foreign key, but NOT the referencing (child) column.**

So `loan.member_id`, `loan.copy_id`, `book_copy.book_id`, `fine.loan_id`, and `book_author.author_id` are **un-indexed by default** — though they're exactly the columns we join and filter on. Worse, a missing FK index slows the *parent* too: deleting/updating a parent under `RESTRICT` (Step 5) must scan the child table to check references. FK columns that are queried need explicit indexes — which drives much of the list below.

---

## 8.4 Walking the access patterns (the only justification that counts)

| AP | Query shape | Index decision |
|---|---|---|
| **AP-1** search title | `title LIKE 'foo%'`, `ORDER BY title` | `book(title)` — B-tree serves **prefix** + sort |
| **AP-1** search author | join via `book_author`, filter `author.name` | `author(name)` + **`book_author(author_id)`** (reverse of PK) |
| **AP-1** search genre | `genre = ?` | **reject** standalone index — low selectivity; planner scans |
| **AP-2** availability | `count(*) WHERE book_id=? AND status='AVAILABLE'` | **`book_copy(book_id, status)`** composite |
| **AP-3** pick a copy | `WHERE book_id=? AND status='AVAILABLE'` | *(same composite as AP-2 — reused)* |
| **AP-4** return | find active loan for copy | *(free — `one_active_loan_per_copy`, Step 7)* |
| **AP-5** overdue batch | `WHERE return_date IS NULL AND due_date < today` | **`loan(due_date) WHERE return_date IS NULL`** (partial) |
| **AP-6** member's active loans / borrow-limit | `WHERE member_id=? AND return_date IS NULL` | **`loan(member_id) WHERE return_date IS NULL`** (partial) |
| **AP-8** outstanding fines | join `member→loan→fine`, `paid_date IS NULL` | **`fine(loan_id)`** (FK index for the join) |
| AP-9/10/11 | rare admin writes | **no new index** — PK/unique suffice |

Three deserve a closer look.

---

## 8.5 Three indexes worth understanding deeply

**The junction reverse index — `book_author(author_id)`.** The composite PK is `(book_id, author_id)`. A B-tree on `(a, b)` can filter by `a` or `(a,b)`, but **not by `b` alone** — a B-tree is only useful from its leading column. "Find all books by this author" filters by `author_id` (the *second* column), so it can't use the PK index at all. The fix is the standard junction pattern: **PK `(book_id, author_id)` + a second index `(author_id)`**, making both directions of the M:N fast.

**Partial indexes that mirror the query — `loan(...) WHERE return_date IS NULL`.** Both AP-5 (overdue) and AP-6 (member's active loans) only care about *active* loans. A partial index indexes **only those rows**, so it's tiny (most loans are historically returned) and the planner uses it exactly when the query's `WHERE` matches the index's `WHERE`. Same partial-index idea as Step 7, now for *speed* instead of *correctness*. AP-6 is doubly justified: Step 1 flagged it on the **write** critical path (the borrow-limit count of Step 7), so this index accelerates a hot write, not just a screen.

**Composite column order — `book_copy(book_id, status)`.** The rule: **equality columns first, then range/sort.** `book_id` is a high-selectivity equality filter → it leads; `status` follows. The same index serves AP-2's count *and* AP-3's copy-pick, and since both needed columns live in the index, the count can be an **index-only scan** (never touching the heap). (`INCLUDE (...)` can attach payload columns for index-only scans without making them part of the key — noted, not needed here.)

---

## 8.6 Text search: when B-tree isn't enough (AP-1 scaling note)

A B-tree on `title` handles `LIKE 'foo%'` (prefix) and sorting — but **not** `ILIKE '%foo%'` (substring/fuzzy), because a B-tree can't seek to a match not anchored at the start. When real search matters you escalate:

- **`pg_trgm` + GIN index** — trigram matching for fuzzy/substring `ILIKE`.
- **`tsvector` + GIN** — full-text search (stemming, ranking).

At 500 books this is overkill — a plain scan finds "Gatsby" instantly — so we **note** it as the scale-up path and don't build it. (Consistent with the series: name the fork, don't pay for it.)

---

## 8.7 The discipline of refusing

Indexes we deliberately *don't* create, and why:

- **`book(genre)` alone** — low cardinality; the planner scans rather than uses it. (Earns its place only inside a composite if a real multi-column query appears.)
- **`membership_status`, any `status`-only index** — low selectivity + rarely the sole filter.
- **Anything touched only by writes** — pure tax, zero read benefit.

Every rejected index is a write that stays fast. *Not* indexing is a design decision too.

---

## 8.8 The justified index set

```sql
-- Free (already exist): all PKs, UNIQUE(isbn/email/barcode), one_active_loan_per_copy

CREATE INDEX ON book (title);                                       -- AP-1 prefix + sort
CREATE INDEX ON author (name);                                      -- AP-1 author search
CREATE INDEX ON book_author (author_id);                           -- AP-1 books-by-author (reverse of PK)
CREATE INDEX ON book_copy (book_id, status);                       -- AP-2 availability, AP-3 pick
CREATE INDEX ON loan (member_id) WHERE return_date IS NULL;        -- AP-6 + Step-7 borrow-limit
CREATE INDEX ON loan (due_date)  WHERE return_date IS NULL;        -- AP-5 overdue batch
CREATE INDEX ON fine (loan_id);                                    -- AP-8 join + FK-delete perf
```

Eight indexes, every one traceable to a row in the AP table. That traceability *is* the strategy.

---

## What we produced in Step 8

- An **index inventory** separating what the constraints gave for free (PKs, uniques, the Step-7 partial unique) from what queries newly require.
- A **justified index set** of eight indexes, each mapped to a specific AP-1…AP-11 access pattern.
- The **FK-not-indexed gotcha** surfaced and addressed; the **junction reverse index**, **partial query-mirroring indexes**, and **composite column ordering** explained.
- An explicit **refusal list** (genre-alone, status-only) and a deferred scale-up path (trigram/full-text search), keeping write cost down.

## Key takeaways (transferable)

1. **Every index is a read/write trade.** Justify each by an access pattern; refusing one is also a decision.
2. **Postgres doesn't index FK child columns** — add them yourself for joins *and* parent-delete performance.
3. **Partial indexes that mirror a query's `WHERE`** are small and exact — ideal for "active loans."
4. **Composite order = equality first, then range/sort**, and a covering index enables index-only scans.
5. **B-tree only seeks from the leading column** — hence the junction reverse index, and why substring search needs trigram/full-text.

## Principles in play

| Principle | How this step applied it |
|---|---|
| **Workload-driven design** | Every index maps to an AP-1…AP-11 entry; no speculative indexes |
| **Reuse over addition** | Step 7's correctness index doubles as AP-4's read index |
| **Match the scale** | Trigram/FTS named but deferred; "method, not need" stated honestly |
| **Know the engine** | FK-not-indexed gotcha; leading-column rule; partial & covering indexes |

---

*Next — Step 9: Denormalization & performance. The mirror image of Step 3. We revisit the counters we refused to store — `available_count`, a member's outstanding-fine total — and ask when measurement justifies breaking 3NF on purpose: materialized views, maintained-in-transaction caches, and the rule that a denormalized value must be updated in the same transaction as its source of truth (the promise made back in Step 1).*
