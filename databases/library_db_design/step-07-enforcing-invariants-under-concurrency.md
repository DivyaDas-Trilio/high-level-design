# Step 7 — Enforcing Invariants Under Concurrency

*Series: Designing the LMS Database · Chapter 7 of 12*

---

Every chapter so far quietly assumed a single writer. Step 7 drops that assumption — and the two invariants Step 5 parked because a `CHECK` couldn't see other rows turn out to break in ways single-threaded reasoning never reveals. This is the hardest chapter in the series and the one that separates a schema that's correct *on paper* from one that's correct *in production*.

> **The discipline of this step:** assume two requests hit the same data at the same instant, and prove the invariant still holds. Prefer a declarative constraint that makes the bad state unrepresentable; fall back to the narrowest lock that serializes the conflict; reserve `SERIALIZABLE` for when neither fits.

---

## 7.1 The two invariants a `CHECK` couldn't reach

Step 5 parked two rules because a `CHECK` sees only its own row:

- **B1 — one active loan per copy.** At most one `loan` row per `copy_id` with `return_date IS NULL`.
- **B2 — borrow-limit.** A member may hold at most **2** active loans.

Both are **cross-row** invariants — they constrain a *set* of rows, not a single one — and both break under concurrency.

---

## 7.2 The race: why "check, then act" is a bug

Here is the issue path (AP-3) written the obvious way:

```sql
-- Request: issue a copy of book 42 to member 7
SELECT count(*) FROM loan WHERE member_id = 7 AND return_date IS NULL;  -- returns 1, "1 < 2 OK"
INSERT INTO loan (copy_id, member_id, ...) VALUES (...);                -- now member has 2
```

Run **two** of these at the same instant for member 7, who currently has 1 active loan:

| Time | Txn A | Txn B |
|---|---|---|
| t1 | `COUNT → 1` ("OK, 1<2") | |
| t2 | | `COUNT → 1` ("OK, 1<2") |
| t3 | `INSERT` loan | |
| t4 | | `INSERT` loan |
| t5 | commit | commit |

Member 7 now has **3** active loans. Neither transaction did anything wrong *individually* — each read a true value and acted on it. The bug is that read and write weren't atomic *with respect to each other*. This is the classic **write skew**: two transactions each read a set, each write a row that invalidates the other's read. The same race issues the *last available copy* to two members at once.

> **The trap to unlearn: wrapping this in `BEGIN … COMMIT` does not fix it.** A transaction gives atomicity and *some* isolation — but PostgreSQL's default `READ COMMITTED` still lets both transactions miss each other's uncommitted inserts. Transactions are necessary, not sufficient. You need the right isolation *or* the right lock.

---

## 7.3 Isolation levels — what each actually prevents

| Level | Stops | Still allows |
|---|---|---|
| `READ COMMITTED` *(PG default)* | dirty reads | non-repeatable reads, phantoms, **write skew** |
| `REPEATABLE READ` *(PG = snapshot)* | + non-repeatable reads, phantoms | **write skew** |
| `SERIALIZABLE` *(PG = SSI)* | **everything**, incl. write skew | (nothing — aborts a conflicting txn instead) |

The borrow-limit race is write skew, so only `SERIALIZABLE` defeats it *by isolation alone* — and even then by **aborting** one transaction with a serialization error the app must **catch and retry**. That's one of two real solutions.

---

## 7.4 Solution 1 — make B1 structurally impossible (partial unique index)

For "one active loan per copy," no locking or special isolation is needed. Make the violating state *unrepresentable*:

```sql
CREATE UNIQUE INDEX one_active_loan_per_copy
ON loan (copy_id)
WHERE return_date IS NULL;
```

A **partial unique index**: uniqueness enforced *only over active loans*. A copy can appear in many historical (returned) loans, but in **at most one** active loan — ever, no matter how writes race. Two concurrent issues targeting the same copy → one commits, the other gets a unique-violation and rolls back. **The storage layer itself is the enforcement.** A declarative constraint always beats procedural locking when the rule is "at most one."

Why partial? A plain `UNIQUE(copy_id)` would forbid a copy from ever being loaned twice. The `WHERE return_date IS NULL` is what makes it "one *active*," and exactly why returning (setting `return_date`) frees the copy for a new loan.

---

## 7.5 Solution 2 — serialize B2 with a row lock

The borrow-limit is a **count** ("at most 2"), which a unique index can't express (unique = at most *one*). Two robust options:

1. **`SERIALIZABLE` + retry** — correct and general, but every issue transaction needs a retry loop, and it's heavier.
2. **Lock the member row** — targeted, simpler, the right call here.

The trick for option 2: **materialize the conflict onto a single lockable row.** All racing transactions concern *one member*, who has *one row*. Lock it first:

```sql
SELECT membership_status FROM member WHERE member_id = 7 FOR UPDATE;
```

Any concurrent issue for member 7 now **blocks** until the first commits — then reads a count that *includes* the first insert. The check-and-act is serialized **per member, not globally**: a `FOR UPDATE` row lock means issues for *different* members never wait on each other. Maximum safety, minimal contention.

---

## 7.6 The correct issue transaction (AP-3)

```sql
BEGIN;

-- (1) Serialize concurrent issues for THIS member by locking the member row
SELECT membership_status
FROM member WHERE member_id = :member_id
FOR UPDATE;
-- app: reject unless membership_status = 'ACTIVE'

-- (2) Borrow-limit B2 — safe now: we hold the member lock
SELECT count(*) FROM loan
WHERE member_id = :member_id AND return_date IS NULL;
-- app: reject if count >= 2

-- (3) Grab ONE available copy, locking it; SKIP LOCKED lets parallel
--     issues of the same title pick *different* copies without blocking
SELECT copy_id FROM book_copy
WHERE book_id = :book_id AND status = 'AVAILABLE'
FOR UPDATE SKIP LOCKED
LIMIT 1;
-- app: reject if no row (no copy available)

-- (4) Create the loan; the partial unique index is the B1 backstop
INSERT INTO loan (copy_id, member_id, loan_date, due_date)
VALUES (:copy_id, :member_id, now(), (now() + interval '5 days')::date);

-- (5) Keep availability (Step 1's source of truth) in sync, atomically
UPDATE book_copy SET status = 'LOANED' WHERE copy_id = :copy_id;

COMMIT;
```

Two details worth lingering on:

- **`FOR UPDATE SKIP LOCKED`** on the copy selection: ten people borrowing the same popular title each grab a *different* free copy concurrently, skipping copies another transaction is mid-issuing — no blocking, no double-issue.
- **Step 1's source of truth holds.** `book_copy.status` (availability) and the `loan` ledger are updated in the *same* transaction, so they can never disagree — the "maintain the cache inside the transaction that changes the truth" rule promised back in Step 1.

---

## 7.7 The correct return transaction (AP-4)

```sql
BEGIN;

-- Close the active loan (return_date set ⇒ partial unique index frees the copy)
UPDATE loan SET return_date = now()
WHERE copy_id = :copy_id AND return_date IS NULL
RETURNING loan_id, member_id, due_date;

-- Compute the fine in the SAME transaction if overdue (AP-7): ₹5/day late
INSERT INTO fine (loan_id, amount)
SELECT :loan_id, (CURRENT_DATE - :due_date) * 5
WHERE CURRENT_DATE > :due_date;

UPDATE book_copy SET status = 'AVAILABLE' WHERE copy_id = :copy_id;

COMMIT;
```

Setting `return_date` is what *releases* the copy from the partial unique index — the same row that enforced "one active loan" now permits the next one. Return and fine are one atomic unit: you never get a returned copy with a missing fine, or vice versa.

---

## 7.8 Where to enforce — completing Step 5's table

| Invariant | Mechanism | Why |
|---|---|---|
| one active loan / copy (B1) | **partial unique index** | "at most one" → make it unrepresentable |
| borrow-limit ≤ 2 (B2) | **row lock (`FOR UPDATE`) + count in txn** | a count needs serialized check-and-act |
| availability in sync | **same transaction** as the loan write | one source of truth, never drifts |
| pick a free copy | **`FOR UPDATE SKIP LOCKED`** | concurrency without double-issue |

The meta-rule: **prefer a declarative constraint (B1); fall back to the narrowest possible lock (B2); reserve `SERIALIZABLE` for when neither fits.**

---

## What we produced in Step 7

- The cross-row invariants from Step 5 made **correct under concurrency**: B1 via a **partial unique index**, B2 via a **per-member `FOR UPDATE` row lock** plus an in-transaction count.
- A worked diagnosis of the **write-skew race** and why `BEGIN…COMMIT` under `READ COMMITTED` does not fix it.
- The full **issue (AP-3)** and **return (AP-4)** transactions, with `FOR UPDATE SKIP LOCKED` for contention-free copy selection and availability kept in sync atomically.
- A meta-rule for cross-row invariants: declarative constraint → narrow lock → `SERIALIZABLE`, in that order of preference.

## Key takeaways (transferable)

1. **"Check, then act" is a race.** Reading a value and acting on it isn't atomic unless you make it so.
2. **A transaction alone isn't enough** — `READ COMMITTED` still allows write skew. Choose isolation *or* locking deliberately.
3. **"At most one" → partial unique index.** Push the invariant into storage; it can't be raced.
4. **"At most N" → serialize on a lockable row.** Lock the member, count, act — per-key, so unrelated writes don't contend.
5. **`FOR UPDATE SKIP LOCKED`** turns "pick an available resource" into a safe, high-concurrency operation.

## Principles in play

| Principle | How this step applied it |
|---|---|
| **Correctness under concurrency** | Both cross-row invariants hold under simultaneous writes |
| **Declarative over procedural** | B1 as a partial unique index, not application locking |
| **Single Source of Truth** | `book_copy.status` updated in the same txn as the loan — no drift |
| **Least contention** | Per-member row lock & `SKIP LOCKED`, not a global lock or blanket `SERIALIZABLE` |

---

*Next — Step 8: Indexing strategy. With reads (AP-1, AP-2) dominating the workload and the write paths now correct, we add indexes — but every one must be justified by a Step-1 access pattern. We'll cover B-tree vs the partial and composite indexes we've already started using, the cost indexes impose on writes, and why the foreign keys and the `one_active_loan_per_copy` index are already doing double duty.*
