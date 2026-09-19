# Step 1 — Data Requirements & Access Patterns

*Series: Designing the LMS Database · Chapter 1 of 12*

---

In LLD, the first thing you produced was *language*, not `class Book:`. Database design has the exact same trap with a different name: the mistake is typing `CREATE TABLE` first. **The first thing you produce is the list of questions the database must answer** — the *access patterns*. A schema is nothing more than optimized storage for a known query workload. You cannot choose keys, indexes, or denormalizations sensibly without knowing the queries first.

> **The one mindset shift for this whole series:** in application design, behavior drives structure. In database design, **the query workload drives structure.** Access patterns before tables.

We'll do three things:

1. Inventory the **durable data** — what state must outlive a restart.
2. Enumerate the **access patterns** — every read and write, tagged.
3. Find the keystone DB insight the whole schema hinges on.

---

## 1.1 Data inventory — what must we actually persist?

We already have the glossary from the LLD Step 1 (Book, BookCopy, Member, Loan, Fine). But a domain concept and a *stored* fact aren't the same thing. The first DB discipline is separating **durable state** (must be saved) from **derived/transient values** (can be computed on demand).

**What a data inventory actually is.** In plain terms, it answers one question: *what facts must this system remember after the power goes off?* A running program holds tons of state in memory — the logged-in user, a half-built search result, loop counters — and almost all of it is disposable; it gets rebuilt next run. The data inventory is the small subset that is **not** disposable: the facts that, if lost, the business genuinely breaks (a member's name; that copy #7 is on loan; that a ₹15 fine is unpaid). The hard part isn't listing facts — it's the *separating*: deciding, per fact, "do I **store** this or **derive** it?" That judgment is the real skill.

**How to derive the inventory from requirements** — a repeatable procedure:

1. **Pull out the nouns.** Underline every noun in the requirements that has a life of its own → these are your candidate things-to-remember (Book, BookCopy, Member, Loan, Fine). (Nouns → entities; verbs → access patterns. You're quietly sorting the requirements into two piles.)
2. **List each noun's attributes.** What must you *know* about a Book to do the job? title, ISBN, author(s), genre.
3. **Apply the store-or-derive filter** to every attribute, three questions in order:
   - *Can I compute it from facts I already store?* If yes → candidate to **derive** ("is it available" = count of AVAILABLE copies).
   - *Does it change on its own with the passage of time, no write involved?* If yes → you **must** derive it ("is it overdue" = `due_date < today`; today moves by itself).
   - *Is it derivable, BUT its input can change and I'd lose history?* If yes → **store it anyway** (the exception: `due_date` freezes the policy as it was at issue time).
4. **Write the two-column table** (store vs. derive). That's the deliverable below.

**The one test that captures it all:** for any fact, ask *"if I store this, is there any other place in my system that already knows it?"* If **yes**, you have two sources of truth → they will drift → **derive** it from the one true place. If **no**, this is the only place the fact lives → **store** it. (`available_count` fails the test — the copies' statuses already know availability. `due_date` passes it — once frozen, the loan row is the only place that remembers what the rule was at issue time.)

| Concept | Durable facts we must store | Derived / not stored (computed) |
|---|---|---|
| **Book** (title) | title, ISBN, author(s), genre | — |
| **BookCopy** | which Book it belongs to, barcode, condition, **status** (available/loaned/lost/damaged) | "is this copy available" (read from status) |
| **Member** | name, email, membership status | "how many books does she have out" (count of active loans) |
| **Loan** | which copy, which member, loan date, **due date**, return date, status | "is this overdue" (due_date < today **and** not returned) |
| **Fine** | which loan/member, amount, **paid/unpaid** status, paid date | "total outstanding for member" (sum of unpaid) |

Two judgement calls worth naming, because they're the kind of decision interviewers probe:

- **Why store `due_date` if it's just `loan_date + 5 days`?** Because the rule is a *policy that can change*. If you compute it on the fly from today's policy, every historical loan silently re-dates itself when the rule changes from 5 to 7 days. We persist the due date that was true **at issue time**. (Storing a derivable value *because the input can change* is a real exception to "don't store derived data.")
- **Why is "overdue" *not* stored?** Because it depends on `today`, which changes every day with zero writes. Anything that changes purely with the passage of time must be computed, never stored.

---

## 1.2 Access patterns — the query workload

Now the core deliverable. We walk every user story in `REQUIREMENTS.md` and turn it into a concrete database operation, tagged with read/write, who triggers it, and how hot it is. **This table is what we'll point back to in Steps 8 and 9 to justify (or refuse) every index and denormalization.**

| # | Access pattern (the question) | R/W | Driven by | Frequency |
|---|---|---|---|---|
| AP-1 | Search books by title / author / genre | **R** | Member US-6 | **Hot** |
| AP-2 | Is *this title* available? (any copy free) | **R** | Member/Librarian US-1 | **Hot** |
| AP-3 | Issue a copy to a member | **W** | Member US-7 / Librarian | medium, **transactional** |
| AP-4 | Return a copy | **W** | Member US-8 | medium, transactional |
| AP-5 | List all loans whose due date has passed | **R** | Librarian US-2 | daily batch |
| AP-6 | A member's currently-borrowed copies | **R** | Member / borrow-limit check | medium |
| AP-7 | Compute & record a fine on late return | **W** | Librarian US-3 | medium |
| AP-8 | Pay a fine | **W** | Member US-9 | low |
| AP-9 | Add / remove / update book or copy quantity | **W** | Admin US-4 | rare |
| AP-10 | Add / remove a member | **W** | Admin US-5 | rare |
| AP-11 | Mark a copy lost/damaged; hide from members, show to librarian | **W + R** | Librarian US-10, Rule #6 | rare |

A few things this table immediately tells us, for free:

- **It's read-heavy.** Search and availability (AP-1, AP-2) dominate traffic; the writes are infrequent and individually small. That biases us toward indexing reads well and not over-engineering write throughput.
- **Two patterns are transactional and multi-row** (AP-3 issue, AP-4 return). Those are where invariants live and where Step 7 (concurrency) will focus.
- **AP-6 is doing double duty** — it's both a member-facing screen *and* the input to the borrow-limit rule ("max 2 books"). That tells us the "active loans for a member" query is on the critical path of a write, not just a display. Worth remembering at indexing time.
- **AP-11 encodes a visibility rule** (Rule #6): the *same* copy data is filtered differently per actor. That's a `WHERE status NOT IN (...)` for members vs no filter for librarians — a query concern, not a separate table.

> **Teaching point.** Notice we never wrote a table definition. We wrote *questions*. A schema that can't answer AP-5 cheaply is a bad schema no matter how clean it looks — and you only know AP-5 exists because you enumerated it. This is the database equivalent of "hunt for the concept the requirements quietly depend on."

---

## 1.3 The keystone DB insight: **availability is a derived query, not a stored truth**

The LLD Step 1 had a keystone: *Book ≠ BookCopy*. The database has its own keystone, and it falls right out of that same split:

> **"Is this book available?" is the answer to a query, not the value of a column.**

The tempting beginner design is a column `Book.available_count INT` that you increment on return and decrement on issue. It's seductive because AP-2 becomes a one-column read. But it's a **second source of truth for a fact already owned by `BookCopy.status`** — and two sources of truth always drift. One crashed transaction, one bug in a return path, and `available_count` says 3 while only 2 copies are actually free. Now which one is right?

The disciplined decision:

- **Source of truth = `BookCopy.status`.** Availability is *defined as* `COUNT(copies WHERE status = 'AVAILABLE')`.
- We answer AP-2 with that query. **If and only if** profiling later proves it too slow (it won't, at 500 books), we add a *cached* count — and we maintain it inside the same transaction that changes a copy's status, so it can't drift (that's Step 9's denormalization discussion).

```sql
-- AP-2, the honest version. One source of truth.
SELECT COUNT(*) > 0 AS is_available
FROM book_copy
WHERE book_id = :book_id
  AND status = 'AVAILABLE';
```

> **The transferable lesson:** don't store what you can derive — *unless* the input itself is volatile (like `due_date`'s policy) or you've measured a real performance need. Premature denormalization is the database version of premature optimization, and it's paid for in data-corruption bugs, which are the worst kind.

---

## 1.4 Where access patterns lead next — SQL vs NoSQL

A natural HLD question: *once I have the access patterns, do I now pick SQL or NoSQL?* Almost. The access-pattern table is a **necessary input to that choice, but not the only one.** An architect weighs **four** inputs, and the engine falls out of all four together:

1. **Access patterns** — *few, well-known point-lookups* sit comfortably in NoSQL (you design the table to serve exactly those). *Many, varied, or unpredictable* patterns — especially ones that join entities — want **SQL**, because the relational engine answers questions you didn't design for. The core asymmetry: **SQL is flexible about queries but rigid about scale; NoSQL is rigid about queries but flexible about scale.**
2. **Data shape & relationships** — heavily relational, integrity-critical data (our Loan → Copy → Book, Loan → Member, Fine → Loan) → **SQL**. Self-contained documents or wide/sparse/time-series data → **NoSQL** (document or columnar).
3. **Consistency needs** — hard invariants and multi-row transactions (money, inventory, "never lend a 3rd book") → **SQL** (or NewSQL like Spanner/CockroachDB when scale is *also* required). Tolerant of eventual consistency for massive scale (likes, feeds, view counts) → **NoSQL**.
4. **Scale estimation** — if it fits on one beefy node plus replicas for the next few years, the answer is **SQL by default**; don't distribute what fits. Only when writes/storage exceed a single node, or sharding must be first-class, does NoSQL (or sharded/NewSQL) earn its place.

Two honest nuances that keep this from being a naive pipeline:

- **Scale is often the *first* gate, not access patterns.** The seasoned first question is "does this fit on one Postgres box?" If yes — and it usually does — it's **SQL by default**, and the access patterns mostly inform *indexing*, not engine choice. The AP table earns its keep most when scale forces you off a single node and you must decide *how* to distribute.
- **The inputs interact; you iterate.** A pattern SQL handles beautifully on one node can become a cross-shard join at scale — at which point access-patterns + scale *together* push you to denormalize into a document store. It's a loop over the four inputs, not a strict sequence.

Run all four on the LMS and the verdict is unanimous:

| Input | LMS reading | Vote |
|---|---|---|
| Access patterns | 11 varied patterns, some joins (loan→copy→book), some ad-hoc reports | SQL |
| Data shape | Heavily relational, integrity-critical | SQL |
| Consistency | Borrow-limit + availability are hard invariants needing transactions | SQL |
| Scale | 100 members, 500 books — fits on a phone | SQL |

**→ PostgreSQL.** This is *why* the whole series is relational; Step 12 revisits the "road not taken" (replicas/sharding/NoSQL) and explains why the scale never earns it.

> **Reality check.** "FAANG = NoSQL" is a myth: Meta's social graph is a sharded MySQL fleet (TAO), Google's transactional core is Spanner (SQL semantics), Amazon runs both DynamoDB *and* large Aurora/RDS. The default for a new transactional service is still relational, because correctness is cheaper to get right there. And real systems are **polyglot** — orders in SQL (ACID), catalog in a document store, the feed in Cassandra, sessions in Redis. The question is never "SQL or NoSQL for my company"; it's "which store for *this* access-pattern set." The one-liner: **SQL until scale or data-shape forces you off it — and the access-pattern table is what tells you whether you've been forced, and if so, how to lay out the NoSQL table.**

---

## What we produced in Step 1

- A **data inventory** that separates durable state from derived values — and two reasoned exceptions (`due_date` is stored; "overdue" is not).
- An **access-pattern table (AP-1…AP-11)** — the query workload that will justify every later structural decision.
- The keystone insight: **availability is a query over `BookCopy.status`, not a maintained column** — one source of truth.

No tables yet, and that's correct — exactly as no code was written in the LLD Step 1.

## Key takeaways (transferable)

1. **Access patterns before tables.** The workload is the spec; the schema is its implementation.
2. **Separate durable state from derived values** — but know the two exceptions: persist a derivable value when its *input is volatile*, or when measurement demands a cache.
3. **One source of truth.** Every fact lives in exactly one place; everything else is a query against it. Drift is the enemy.
4. **Tag reads vs writes early.** Read-heavy vs write-heavy changes which decisions matter later.

## Principles in play

| Principle | How this step applied it |
|---|---|
| **Single Source of Truth** | Availability derives from `BookCopy.status`; no parallel `available_count` to drift. |
| **YAGNI / KISS** | Refused a denormalized counter until measurement justifies it. |
| **Workload-driven design** | The AP table is the spec the physical schema will be judged against. |
| **Normalization mindset** (sets up Step 3) | "Don't store what you can derive" is the seed of normal forms. |

---

*Next — Step 2: the Conceptual (ER) model. We'll take these concepts and draw the entities, relationships, and exact cardinalities (one Book → many Copies; one Member → many Loans; one Loan → exactly one Copy), engine-agnostic, before any column types. That diagram is the bridge from the domain model to a logical schema.*
