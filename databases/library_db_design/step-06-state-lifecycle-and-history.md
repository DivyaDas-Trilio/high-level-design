# Step 6 — State, Lifecycle & History

*Series: Designing the LMS Database · Chapter 6 of 12*

---

Step 5 ended owing two debts: a `status`-vs-timestamp redundancy flagged twice, and the soft-delete pattern that `RESTRICT` quietly forced on us. Step 6 pays both, and then asks the larger question underneath them — *how much of the past must this schema remember?* Every answer here comes from one Step-1 test: **don't store what you can derive, unless the input is volatile or measurement demands a cache.**

> **The discipline of this step:** treat "store a `status` column" as a claim that must be *earned*, not a default; and treat "delete a row" as a privilege the schema's own integrity rules may refuse you. State is stored only when nothing else already implies it; history is kept only where an access pattern needs it.

---

## 6.1 Two questions about every piece of state

State management is two questions wearing one coat:

1. **Should this state be stored at all, or derived?** — the redundancy debt.
2. **How much of the *past* must we keep?** — history.

Both fall to the same Step-1 rule. We take them in order.

---

## 6.2 Resolving the redundancy: which `status` columns earn their place?

The test for any `status` column: **does it hold a fact not already derivable from other stored columns?** Run all three of ours through it.

**`loan.status` — fails.** Its reachable states are fully determined by columns we already store:

- `ACTIVE` = `return_date IS NULL`
- `RETURNED` = `return_date IS NOT NULL`
- `OVERDUE` = `return_date IS NULL AND due_date < today` — and "today" is the *volatile, write-free input* Step 1 said must **never** be stored.

So `loan.status` is pure shadow. **Drop it** and derive via a view:

```sql
CREATE VIEW loan_status AS
SELECT loan_id, copy_id, member_id, loan_date, due_date, return_date,
  CASE
    WHEN return_date IS NOT NULL THEN 'RETURNED'
    WHEN due_date < CURRENT_DATE THEN 'OVERDUE'
    ELSE 'ACTIVE'
  END AS status
FROM loan;
```

Why a view and not a Postgres `GENERATED` column? Generated columns must be **immutable**, and `OVERDUE` depends on `CURRENT_DATE`. The active/returned split *could* be generated, but overdue can't — so the whole thing lives in a view.

**`fine.status` — fails too.** `PAID` = `paid_date IS NOT NULL`, `UNPAID` = `paid_date IS NULL`. Drop it; derive the same way.

**`book_copy.status` — passes, and this is the crucial contrast.** Its states are `AVAILABLE / LOANED / LOST / DAMAGED`. `LOST` and `DAMAGED` are **independent facts a librarian sets** (AP-11) — *not* derivable from any timestamp. (`LOANED` is *almost* derivable from "has an active loan," but lost/damaged aren't, so the column must stay to hold those.) `book_copy.status` is real lifecycle state; it earns its place.

> **The transferable rule: a `status` column is legitimate only when it records a fact nothing else stores.** When it merely mirrors a nullable timestamp, it's a second source of truth waiting to drift — derive it. Not all status columns are bad; only the redundant ones.

---

## 6.3 Soft-delete — the consequence of `RESTRICT`

Step 5's `RESTRICT` policies mean you **cannot** `DELETE` a member or book that has history. So AP-9/AP-10 ("remove a book / member") can't be hard deletes. The answer is **soft-delete**: mark the row inactive, keep it for history.

Two encodings, and we already own one:

- **`member`** — `membership_status` already has `'CANCELLED'`. That *is* the soft-delete. "Removing" a member = `UPDATE member SET membership_status = 'CANCELLED'`. No new column — the lifecycle enum does double duty.
- **`book`** — has no such column, so add one. Prefer a nullable **`deleted_at TIMESTAMPTZ`** (`NULL` = live) over a bare boolean: same cost, but it also records *when*, consistent with our timestamp-as-state pattern.

**The soft-delete tax — name it honestly.** Every read now must remember `WHERE deleted_at IS NULL` (or `membership_status <> 'CANCELLED'`). Forget it once and you leak deleted data into a UI. Two mitigations:

- **Filtered views** as the default read surface, so callers can't forget:
  ```sql
  CREATE VIEW active_book AS SELECT * FROM book WHERE deleted_at IS NULL;
  ```
- **Partial unique indexes** when a natural key should free up on delete:
  ```sql
  CREATE UNIQUE INDEX ON member (email) WHERE membership_status <> 'CANCELLED';
  ```
  This lets a cancelled member's email be reused, where a plain `UNIQUE` would block re-registration forever.

AP-11's visibility rule (hide lost/damaged copies from members, show to librarians) is *the same pattern* — a per-actor filtered view:

```sql
CREATE VIEW member_visible_copy AS
SELECT * FROM book_copy WHERE status IN ('AVAILABLE','LOANED');  -- hide LOST/DAMAGED
```

---

## 6.4 How much history? — let access patterns decide

Three escalating levels of history-keeping:

| Level | What it keeps | Cost |
|---|---|---|
| **Current-state columns** | Only the latest value | Cheapest; loses *when/who* it changed |
| **Soft-delete + timestamps** | Existence + some timing (`deleted_at`, `return_date`) | One column, one filter |
| **Audit / history table** | Every change as a row | Extra writes, triggers, complexity |

The insight for the LMS: **the `loan` table *is* the history.** Each row is an append-on-issue, update-once-on-return record of a borrowing event — and `RESTRICT` guarantees it's never deleted. It is effectively an **immutable ledger** of who-borrowed-what-when. No separate audit table is needed for borrowing history, because the operational table already *is* that history.

Do we need a general audit trail ("who marked this copy lost, and when")? **The requirements never ask** → YAGNI. When *would* you? Compliance, disputes, "who changed what" mandates — then you'd add `*_history` tables fed by triggers, or reach for temporal-table patterns. Flag it; don't pay for it now.

---

## 6.5 Schema deltas from this step

- **Drop** `loan.status` and `fine.status` → replace with the derived views above.
- **Keep** `book_copy.status` (holds non-derivable `LOST`/`DAMAGED`).
- **Add** `book.deleted_at TIMESTAMPTZ` (NULL = live); reuse `member.membership_status` for member soft-delete.
- **Add views**: `loan_status`, a `fine` status view, `active_book`, `member_visible_copy`.
- **No audit tables** — the `loan` ledger is the history the requirements need.

---

## What we produced in Step 6

- A **resolved redundancy**: `loan.status` and `fine.status` dropped and derived in views; `book_copy.status` kept because it stores non-derivable facts.
- A **soft-delete design** driven by Step 5's `RESTRICT`: `member` reuses `membership_status`, `book` gains `deleted_at`, plus the partial-unique-index trick for key reuse.
- The **soft-delete tax** named, with default-filtering views (`active_book`, `member_visible_copy`) as the mitigation — the same mechanism that implements AP-11's visibility rule.
- A **history decision**: the `loan` table is the immutable ledger; no audit tables added, because no access pattern demands them.

## Key takeaways (transferable)

1. **A `status` column earns its place only if it stores a non-derivable fact.** `loan`/`fine` status shadowed timestamps (dropped); `book_copy` status holds real state (kept).
2. **Derive volatile state in a view, not a column** — `OVERDUE` depends on today, so it can't even be a generated column.
3. **`RESTRICT` ⇒ soft-delete.** Mark inactive (`deleted_at` / status), never hard-delete history.
4. **Soft-delete has a tax**: every read must filter. Pay it with default views and partial unique indexes.
5. **Your operational table is often already the history.** `loan` is an immutable ledger — don't build an audit table the access patterns don't demand.

## Principles in play

| Principle | How this step applied it |
|---|---|
| **Single Source of Truth** | Killed `status` columns that mirrored timestamps |
| **Don't store derivable state** | `OVERDUE` derived in a view, never persisted |
| **History is sacred** | Soft-delete + the `loan` ledger preserve the past |
| **YAGNI / match-the-scale** | No audit tables; reused `membership_status` instead of new columns |

---

*Next — Step 7: Enforcing invariants under concurrency. We finally tackle the cross-row rules a `CHECK` couldn't express — "max 2 active loans per member" and "one active loan per copy" — under simultaneous requests. Transactions, isolation levels, the partial unique index, and `SELECT … FOR UPDATE` vs advisory locks: where the issue/return paths (AP-3/AP-4) become correct under race conditions, not just on paper.*
