# Designing the LMS Database — step by step

> A from-scratch walkthrough that turns the Library Management System requirements into a **relational schema**, applying normalization, keys, constraints, indexing, and transactions *only where they earn their place* — and writing the reasoning down as we go.

This is the **database** companion to the LLD/DDD series in
[`../../../lld/library_management_system_v2/docs/`](../../../lld/library_management_system_v2/docs/).
Same problem, same [`REQUIREMENTS.md`](../../../lld/library_management_system_v2/REQUIREMENTS.md),
same glossary — but where the LLD series produces *domain classes*, this series produces a *schema*.

## The problem

A single library, ~100 members, ~500 books, one branch, 24/7 uptime. Borrow limit 2 books,
5-day loan, ₹5/day fine, no renewals, lost/damaged copies hidden from members but visible to librarians.
Scale is deliberately modest — so we match the design to it (no sharding, no premature denormalization).

## The method (roadmap)

| Step | Chapter | What we produce | Status |
|---|---|---|---|
| 1 | [Data requirements & access patterns](step-01-data-and-access-patterns.md) | Data inventory + the query workload the schema must serve | ✅ done |
| 2 | [Conceptual model (ER)](step-02-conceptual-er-model.md) | Entities, relationships, cardinalities — engine-agnostic ER diagram | ✅ done |
| 3 | [Logical model & normalization](step-03-logical-model-and-normalization.md) | Tables, columns, 1NF→3NF, resolving many-to-many | ✅ done |
| 4 | [Keys & data types](step-04-keys-and-data-types.md) | Surrogate vs natural keys, type choices, ID strategy | ✅ done |
| 5 | [Constraints & referential integrity](step-05-constraints-and-referential-integrity.md) | PK/FK, `UNIQUE`, `CHECK`, `NOT NULL`, `ON DELETE`, enums | ✅ done |
| 6 | [State, lifecycle & history](step-06-state-lifecycle-and-history.md) | status columns, soft-delete, audit/history tables | ✅ done |
| 7 | [Enforcing invariants in the DB](step-07-enforcing-invariants-under-concurrency.md) | borrow-limit & availability under concurrency; transactions vs constraints vs app | ✅ done |
| 8 | [Indexing strategy](step-08-indexing-strategy.md) | every index justified by a Step-1 access pattern | ✅ done |
| 9 | [Denormalization & performance](step-09-denormalization-and-performance.md) | computed availability counts — when breaking 3NF is correct | ✅ done |
| 10 | [Physical schema (DDL)](step-10-physical-schema-ddl.md) | the actual `CREATE TABLE` script | ✅ done |
| 11 | [Migrations & evolution](step-11-migrations-and-evolution.md) | Alembic / versioning / zero-downtime changes | ✅ done |
| 12 | [Scale & the road not taken](step-12-scale-and-the-road-not-taken.md) | when replicas/sharding/NoSQL — and why **not** here | ✅ done |
| 13 | **[ORM models & the Repository pattern](step-13-orm-models-and-repository-pattern.md)** (LLD integration) | SQLAlchemy models, repository *interfaces* in the domain, implementations in infra, domain↔row mapping | ✅ done |

> **Step 13 is the seam to the LLD series.** The DB series (Steps 1–12) defines the schema; the LLD series defines the pure-Python domain classes; Step 13 wires them together with one repository per aggregate root — the same "persistence-ignorant ports" as LLD Step 10.

## Guiding principles

- **Access patterns before tables.** The query workload is the spec; the schema is its implementation.
- **One source of truth.** Every fact lives in exactly one place; everything else is a query against it.
- **Don't store what you can derive** — unless the input is volatile or measurement demands a cache.
- **Match the design to the scale.** No distributed systems for a 100-member library.

## Conventions

- Reference dialect: **PostgreSQL**. MySQL/SQLite deltas are flagged inline where they matter.
- Each chapter is self-contained: a little theory → applied to the LMS → *why* each decision → key takeaways → principles-in-play table.

---

*Series status: ✅ complete — all 13 steps written. From access patterns (Step 1) to the ORM/Repository seam (Step 13).*
