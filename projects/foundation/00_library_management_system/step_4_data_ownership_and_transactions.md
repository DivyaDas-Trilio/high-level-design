# Module 00 · Step 4 — Data Ownership, SQL Choice & Cross-Service Transactions

> Where most "microservices" secretly fail: they split the code but share the database.
> HLD altitude only — which module owns which data, what DB, how consistency works across
> boundaries. NOT column types/indexes/migrations (that's LLD: see lld step-18).

## Principle 1: the database is the tightest coupling
**Each module owns its data exclusively; others touch it only via its API.** Share a table
and two modules are welded — can't change schema, scale, or deploy one without the other.
= database-per-service (microservices) / schema-per-module (modular monolith).

**Anti-pattern: the SHARED DATABASE** — services reaching into each other's tables
("integration through the database"). Recreates monolith coupling + network failure = worst
of both (data-layer cousin of the distributed monolith).

## Ownership map (mirrors the aggregates 1:1)
| Module | Owns | Notes |
|---|---|---|
| Catalog | `books` | + search index read model (later) |
| Inventory | `book_copies` | high write churn |
| Membership | `members` | |
| Lending | `loans` | core |
| Fines | `fines` | money → strict consistency/audit |
| Notifications | (none) | reacts to events |

## Principle 2: referential integrity changes at the boundary
- Monolith (one DB): FK `loans.copy_id → book_copies.id` works; DB enforces integrity free.
- Split (DB-per-service): that FK is impossible (different DBs). Reference **by ID**, accept
  integrity is now your job (dangling refs, eventual consistency).
- This is WHY the Step-5 aggregate rule ("reference by ID, not object") mattered — it
  pre-shaped the model for a split. By-ID design = database-per-service, one altitude down.

## SQL vs NoSQL — from requirements, not fashion
| Signal | LMS | Implication |
|---|---|---|
| Relational data (members↔loans↔fines↔copies↔books) | yes | relational |
| ACID transactions (borrow, pay fine) | yes | relational |
| Joins (overdue + member info) | yes | relational |
| Massive write volume / horizontal scale | no (~0 QPS) | NoSQL advantage irrelevant |
| Flexible/evolving schema | no | — |

**Verdict: PostgreSQL.** NoSQL would lose transactions/joins to buy unneeded scale. Only
non-relational fit: **Catalog search** → Elasticsearch as a **read model** fed from `books`
(not source of truth).

## Cross-service transactions: 2PC vs Saga (the decision)
`borrow()` touches Membership + Inventory + Lending data. Keep it consistent how?

| Scenario | Mechanism | Verdict |
|---|---|---|
| Monolith (today) | one DB → **one local ACID transaction** | ✅ what LMS uses — atomic, simple, free |
| Split + strong consistency | **2PC** (coordinator locks all DBs, commits together) | ❌ slow, locks, fragile, low availability |
| Split + eventual consistency | **Saga** (local txns + compensations) | ✅ industry default IF you must split |

**Decision framework:** *Can the operation's data live in one service's DB? → local
transaction, always prefer.* Only when it MUST span services: 2PC for strong consistency
(rare, tolerate availability hit), Saga for availability (common, tolerate brief
inconsistency repaired by compensations).

**Closes Step 2's loop:** at LMS scale `borrow()` is ONE local transaction — no saga, no
2PC, no distributed anything. The saga talk only becomes real IF a split is forced. Keeping
borrow's data in one DB is the single strongest argument for the modular monolith.

## Flag for Step 5: the dual-write problem
When split: "commit local txn AND publish event" = two writes; crash between → divergence.
Fix = **Outbox pattern** (write event into own DB in the same txn, publish async). Built in
Step 5.

## Self-check
1. Why is a shared database the tightest possible coupling?
2. What happens to a foreign key when its two tables move to different services?
3. Justify SQL over NoSQL for LMS using requirements (not preference).
4. Give the framework for choosing local-txn vs 2PC vs saga.
5. At LMS scale, how many distributed transactions does borrow need? Why does that argue
   for the monolith?
