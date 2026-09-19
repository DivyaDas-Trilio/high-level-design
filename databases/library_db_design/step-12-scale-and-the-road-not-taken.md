# Step 12 — Scale & the Road Not Taken

*Series: Designing the LMS Database · Chapter 12 of 12 (schema arc)*

---

Every chapter has quietly said "not at this scale" — no availability counter (Step 9), no audit tables (Step 6), no full-text search (Step 8). This chapter collects those refusals and defends them in one place, because recognizing the scale you *don't* have is the discipline that prevents the most expensive mistakes in our field.

> **The discipline of this step:** map every scaling technique to the specific load signal that would justify it, measure that signal against our actual numbers, and refuse what the numbers don't demand — while writing down the trigger that would change the answer. A refusal isn't "never"; it's "not until."

---

## 12.1 The skill is refusing scale you don't have

Every scaling technique trades simplicity for capacity *and* introduces new failure modes — replication lag, cache invalidation, lost cross-shard transactions. Adopting one before the load demands it is premature optimization at the *architecture* level, and architecture is far costlier to unwind than a slow query.

The concrete numbers: ~500 books × a few copies ≈ a couple thousand `book_copy` rows, 100 members, a few hundred loans a year. The **entire dataset fits in RAM many times over**, and peak traffic is a handful of queries per second. **One modest PostgreSQL instance serves this with years of headroom.** With that established, here are the big guns — each mapped to the signal that justifies it, and why we don't fire it.

---

## 12.2 Climb the ladder in order

Before *any* distribution, the cheap rungs:

**tune queries/indexes (done, Step 8) → bigger box (vertical) → connection pooling (PgBouncer) → read replicas → caching → partitioning → sharding.**

Each rung is cheaper and less invasive than the next, and **most applications never reach the top two.** Vertical scaling plus a replica carries you astonishingly far. The mistake is jumping to sharding because it sounds impressive.

---

## 12.3 The techniques, the signal, and the verdict

| Technique | What it does | Load signal that justifies it | LMS verdict |
|---|---|---|---|
| **Read replicas** | streaming read-only copies; reads → replicas | read QPS exceeds one node | **No** — a handful of QPS |
| **Caching (Redis)** | hot read results in memory | same expensive read repeated, DB read-bound | **No** — reads already index-only & in-RAM |
| **Partitioning** | split one huge table (e.g. `loan` by year) within one DB | a single table at 10⁸–10⁹ rows | **No** — `loan` grows ~hundreds/year |
| **Sharding** | split data across servers by a shard key | write/size beyond one primary's ceiling | **No** — single branch, tiny dataset |
| **NoSQL** | document/KV/graph store | non-relational model or relaxed-consistency mega-scale | **No** — deeply relational with hard invariants |

Each row deserves its trap named.

**Read replicas → replication lag.** Replicas are *eventually* consistent. The classic bug: a member issues a copy, immediately re-reads availability from a lagging replica, and sees it still "available." That "read-your-writes" violation forces routing complexity (read-after-write from the primary, sticky sessions). Not worth it for our load.

**Caching → invalidation.** Cache invalidation is famously one of the hard problems. You'd add a whole staleness-bug surface to speed up reads that already return in microseconds. The DB at this size *is* its own cache — it's all in RAM anyway.

**Partitioning → premature complexity.** It shines for time-series at hundreds of millions of rows (prune scans, drop old partitions cheaply). `loan` is our only growth table, and it'd take **decades** to get there.

**Sharding → the most expensive move in databases.** You lose cross-shard transactions, cross-shard joins, global uniqueness, and cross-shard referential integrity — the *exact* guarantees Steps 5–7 leaned on for the borrow-limit and one-active-loan invariants. ACID gets replaced by sagas/2PC; a bad shard-key choice is near-fatal. Sharding a 100-member library would be malpractice. (The natural shard key would be *branch* — and there is one branch.)

**NoSQL → throwing away your correctness.** The LMS is the textbook relational model: clear entities, clear relationships, and hard invariants that constraints enforce *beautifully*. Going document-store would push borrow-limit and one-active-loan back into racy application code — undoing Step 7 entirely. Wrong tool for this shape.

---

## 12.4 The one honest exception: HA is not scaling

The requirements *do* state **24/7 uptime** — a real obligation. But high availability is a **reliability** concern, not a *throughput* one, and crucially **it doesn't change the data model.** You satisfy it with infrastructure:

- a **managed Postgres** service (RDS / Cloud SQL) with **multi-AZ automated failover**, point-in-time backups, and a hot standby.

That standby looks like "a replica," but its job is *failover*, not read-scaling — and you buy it off the shelf rather than designing for it. So the single defensible scaling-adjacent investment here is **managed HA**, and it leaves Steps 3–11 completely untouched. (This is where the parent curriculum's *03_REPLICATION_AND_HA* module picks up.)

---

## 12.5 Write down the triggers (so the deferral stays conscious)

A refusal isn't "never" — it's "not until." Recording the trip-wires turns YAGNI into a decision you can revisit:

- **Multi-branch chain (thousands of branches)** → multi-tenancy, possibly branch-based sharding.
- **Catalog into the millions + heavy fuzzy search** → Postgres full-text/trigram (Step 8's deferred path), maybe a dedicated search index — *polyglot as a complement, not a replacement.*
- **Read QPS beyond one node** → read replicas (with read-your-writes handling).
- **`loan` into 100M+ rows** → range-partition by year.

None of these is foreseeable for a single 100-member library — which is exactly why the answer today is *one well-designed Postgres instance, managed for HA, and nothing more.*

---

## What we produced in Step 12

- A **mapped refusal** of read replicas, caching, partitioning, sharding, and NoSQL — each against its justifying load signal and our real numbers.
- The **scaling ladder** (tune → vertical → pool → replicas → cache → partition → shard) and the insight that most systems stop on the lower rungs.
- The distinction that **HA ≠ scaling**: the 24/7 requirement is met by managed failover infrastructure, with zero schema impact.
- **Documented trigger conditions** so every deferral remains a conscious, revisitable decision rather than an oversight.

## Key takeaways (transferable)

1. **Recognizing absent scale is a senior skill.** Premature distribution is architectural over-engineering — the costliest kind to reverse.
2. **Climb the ladder in order** — tune, vertical, pool, replicas, cache, partition, shard. Most systems stop early.
3. **Every scaling tool adds a failure mode** — lag, invalidation, lost transactions. The trade is never free.
4. **Sharding/NoSQL would destroy the invariants Steps 5–7 built** — don't trade correctness for capacity you don't need.
5. **HA ≠ scaling.** The 24/7 requirement is met with managed failover, not a schema change.

## Principles in play

| Principle | How this step applied it |
|---|---|
| **YAGNI at architecture scale** | Every distribution technique refused against real numbers |
| **Match the design to the scale** | One Postgres node sized to a dataset that fits in RAM |
| **Preserve correctness** | Rejected shard/NoSQL precisely because they'd break ACID invariants |
| **Conscious deferral** | Trigger conditions documented, so "not yet" is revisitable |

---

*Next — Step 13: ORM models & the Repository pattern. The schema arc is complete; the final chapter is the seam back to the LLD series. We map these tables to SQLAlchemy 2.0 models, define repository **interfaces** in the domain and implementations in infrastructure, and translate the issue/return transactions (Step 7) into repository methods — wiring the persistence-ignorant domain to the physical schema, one repository per aggregate root.*
