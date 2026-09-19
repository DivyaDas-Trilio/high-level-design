# Step 9 — Denormalization & Performance

*Series: Designing the LMS Database · Chapter 9 of 12*

---

This chapter is the deliberate mirror of Step 3. There, normalization put every fact in exactly one place. Here we ask the opposite question — *when is breaking that rule the correct engineering decision?* — and answer it the only honest way: with evidence, not instinct. The punchline for this particular system is "denormalize nothing," but the value is in **why**, and in knowing exactly how you'd do it the day a profiler tells you to.

> **The discipline of this step:** a denormalization must be justified by a *number* — a volatile input or a measured bottleneck — and, if taken, the cached value must be maintained in the same transaction as its source of truth. Absent the number, the correct answer is "no," and "I measured it and it's already fast" is the most common correct answer.

---

## 9.1 Denormalization is the exception — and it needs a number

Normalization (Step 3) gave every fact one home. **Denormalization** deliberately stores a redundant or derived value to make reads faster — creating a *second source of truth that can drift*. You buy read speed with write complexity and a standing correctness risk.

Step 1 gave the only two triggers that justify it:

1. the input is **volatile** (why we stored `due_date`), or
2. **measurement** proves a real performance need.

What's *not* on that list: "it seems like it'd be faster." Denormalization without a measured bottleneck is premature optimization paid for in data-corruption bugs — the worst kind. The senior move here is mostly to say "no" — while knowing exactly how to say "yes," and what it costs.

---

## 9.2 Candidate 1 — `book.available_count` (the counter Step 1 forbade)

AP-2 ("is this title available?") is our hottest read. The tempting denormalization is a maintained `available_count` column so the answer is one column read. Evaluate it honestly:

- The truthful query is `count(*) FROM book_copy WHERE book_id=? AND status='AVAILABLE'`.
- After Step 8 we have `book_copy(book_id, status)` — so this is an **index-only scan over a handful of rows**. Microseconds, and it stays fast far beyond 500 books.

**Verdict: refuse.** No measured need; the indexed count already wins. But understand the cost we'd take on if we added it anyway:

- **It must be maintained in the Step-7 transactions.** Issue decrements, return increments, lost/damaged decrements — each `UPDATE book SET available_count = available_count - 1` inside the *same* transaction that flips `book_copy.status`.
- **It manufactures write contention.** Today, issuing two *different* copies of a popular book touches two different `book_copy` rows — no conflict. With the counter, every issue of *any* copy of that book locks the **one** `book` row. We'd trade a cheap read for a serialization hotspot on exactly the popular titles that get borrowed most. The cure is worse than the disease.

---

## 9.3 Candidate 2 — a member's outstanding-fine total (AP-8)

AP-8 ("total outstanding for a member") is `SUM(fine.amount) WHERE … paid_date IS NULL` across the `member→loan→fine` join. Tempting to cache as `member.outstanding_balance`.

But AP-8 is tagged **low frequency** (Step 1), and the join is over tiny tables with the `fine(loan_id)` index from Step 8. A rare, cheap query is the *worst* denormalization candidate — all drift risk, no meaningful speedup. **Verdict: refuse.** (If this total moved onto a hot, every-page-load dashboard, the calculus would change — frequency is the deciding variable.)

---

## 9.4 The toolbox — for when measurement *does* justify it

Know these four, and exactly when each fits:

| Technique | Freshness | Cost | Use when |
|---|---|---|---|
| **Plain `VIEW`** | always fresh | recomputed each call, no storage | query reuse (Step 6) — *not* denormalization |
| **Maintained counter/aggregate column** | always fresh | write contention + drift risk + code on every write path | hot read that must be real-time exact |
| **Trigger-maintained aggregate** | always fresh | hidden logic, still contention — but *can't be bypassed* | same, when multiple writers must not forget it |
| **`MATERIALIZED VIEW`** | **stale until `REFRESH`** | refresh recomputes the whole thing (`REFRESH … CONCURRENTLY` avoids locking) | expensive **read-mostly** aggregates/reports where staleness is acceptable |

The sharp distinction to carry: **a materialized view is fast but stale; a counter column is fresh but contended.** Pick by whether the value tolerates staleness. Availability *cannot* (it's a transactional invariant) → a materialized view would be exactly wrong for it. A "books borrowed this month" reporting dashboard *can* → a materialized view is exactly right.

---

## 9.5 The ironclad rule (the promise from Step 1)

> **If you denormalize, the cached value must be updated in the _same transaction_ that changes its source of truth.**

The Step-7 issue/return transactions are the natural home — they already touch `book_copy.status`, so an `available_count` would be updated *right there*, atomically, and could never drift. A denormalized value maintained *outside* its source transaction **will** drift, and a drifting cache is worse than a slow query because it is **silently wrong**.

Belt-and-suspenders even then: a periodic **reconciliation job** that recomputes the aggregate from source rows and corrects drift. If you can't tolerate writing that job, you can't tolerate the denormalization.

---

## 9.6 Verdict for the LMS: denormalize nothing (yet)

Both candidates refused — the indexed count is cheap (C1), AP-8 is rare (C2). At this scale denormalization is pure downside. We record the *trigger conditions* for revisiting, so it stays a measured decision rather than a forgotten one:

- `available_count`: revisit only if AP-2 becomes a **profiled** bottleneck at much larger scale *and* the index-only count is proven insufficient.
- outstanding balance: revisit only if it moves onto a **hot per-request** path.

That's the whole lesson: justify a denormalization with a *number*, and "I measured it and it's already fast" is usually the right finding.

---

## What we produced in Step 9

- A reasoned **refusal of both denormalization candidates** (`available_count`, member balance), each rejected on evidence — an index already serves AP-2; AP-8 is rare.
- The hidden cost of counters made explicit: **write contention** funneled onto a single hot row.
- A **toolbox** (plain view, counter column, trigger-maintained aggregate, materialized view) mapped to the freshness-vs-contention trade-off.
- The **in-transaction maintenance rule** plus reconciliation job, and **documented trigger conditions** for revisiting — keeping denormalization a measured, reversible decision.

## Key takeaways (transferable)

1. **Denormalize only on a volatile input or a measured bottleneck** — never on a hunch.
2. **An index often beats a counter** — we refused `available_count` because `book_copy(book_id,status)` already makes AP-2 an index-only scan.
3. **Counters create write contention** — they funnel many independent writes onto one row; weigh that against the read win.
4. **Materialized view = fast-but-stale; counter = fresh-but-contended.** Choose by staleness tolerance; never cache a transactional invariant in a materialized view.
5. **A cache must be maintained in its source's transaction**, plus a reconciliation job — or it drifts and lies.

## Principles in play

| Principle | How this step applied it |
|---|---|
| **Measure before optimizing** | Both denormalizations refused on evidence, not vibes |
| **Single Source of Truth** | Any cache maintained in-transaction with its source; reconciliation as backstop |
| **Right tool for staleness** | View vs. materialized view vs. counter chosen by freshness need |
| **YAGNI / match the scale** | Nothing denormalized at 500 books; trigger conditions documented for later |

---

*Next — Step 10: The physical schema (DDL). Every decision from Steps 3–9 converges into one runnable PostgreSQL script — `CREATE TABLE`s with their types, constraints, and `ON DELETE` rules; the views from Step 6; the indexes from Step 8; and the partial unique index from Step 7 — assembled in dependency order, the artifact the whole series has been building toward.*
