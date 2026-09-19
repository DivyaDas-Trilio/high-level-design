# Step 11 — Migrations & Evolution

*Series: Designing the LMS Database · Chapter 11 of 12*

---

Step 10 produced the schema from zero — but you run a from-zero script exactly *once*. After that the database is live and full of data, and every change must happen *underneath* running traffic without losing a row or dropping a request. This chapter is about evolving a schema that can't be taken offline.

> **The discipline of this step:** treat schema as versioned code, and assume every change runs on a large, live table while old and new application code execute side by side. A change is safe only if it neither locks the table for long nor breaks a half-deployed fleet — and breaking changes are split into additive steps until that's true.

---

## 11.1 Why migrations exist: schema is versioned code

The Step-10 script runs once, on an empty database. Every change after that is a **migration**: a small, ordered, reviewable, reversible unit of schema change tracked in version control *and* in the database itself.

The thing never to do is run an ad-hoc `ALTER TABLE` on production — no history, no rollback, no review, and **environment drift** as dev/staging/prod silently diverge until a deploy explodes. A migration tool gives instead:

- an **ordered chain** of changes (each knows its predecessor),
- an **up** (apply) and **down** (revert) for each,
- a record *in the DB* of which have run (idempotent, resumable),
- identical application everywhere.

The Step-10 DDL becomes **migration 0001** — the baseline. Everything after is incremental.

---

## 11.2 Alembic — the SQLAlchemy-ecosystem tool

Each migration is a Python file with a `revision`, a `down_revision` (the two form a linked chain), and `upgrade()`/`downgrade()`:

```python
# alembic/versions/0002_add_member_phone.py
revision = "0002"
down_revision = "0001"

def upgrade():
    op.add_column("member", sa.Column("phone", sa.Text(), nullable=True))

def downgrade():
    op.drop_column("member", "phone")
```

`alembic upgrade head` runs all pending migrations; `alembic downgrade -1` reverts the last; the current revision lives in an `alembic_version` table. **Autogenerate** (`alembic revision --autogenerate`) diffs your SQLAlchemy models against the live DB — a big time-saver, but it must be **reviewed**: it misses renames (sees drop + add → data loss!), data migrations, server defaults, and `CONCURRENTLY`.

---

## 11.3 The two ways a naive migration hurts you

On an empty dev DB any migration is instant. On a live, populated, large table a careless one causes an **outage**, in one of two ways:

1. **It locks the table.** Some DDL takes an `ACCESS EXCLUSIVE` lock and/or rewrites every row — blocking all reads and writes for the duration. On a big table, a multi-minute outage.
2. **It breaks the running app.** During a rolling deploy, *old and new code run simultaneously*. A change the old code can't tolerate (or that new code needs before it's applied) breaks one of them mid-rollout.

Common dangerous operations and their safe Postgres stagings:

| Naive op | Why it hurts | Safe staging |
|---|---|---|
| `ADD COLUMN ... NOT NULL` (no default) | rewrite/lock; old code can't supply it | add **nullable** → backfill → add `NOT NULL` via `CHECK ... NOT VALID` then `VALIDATE` |
| `DROP COLUMN` | old code still reads it | stop using in code (deploy) → drop **later** |
| `CREATE INDEX` | locks out writes while building | **`CREATE INDEX CONCURRENTLY`** (no write lock; can't run inside a txn) |
| `ADD FOREIGN KEY` | validating existing rows locks | `ADD CONSTRAINT ... NOT VALID` (fast) → `VALIDATE CONSTRAINT` (light lock) separately |
| rename / change type | breaks old code + may rewrite | **expand/contract** (below) |
| `SET NOT NULL` on existing col | full scan + lock | `CHECK (col IS NOT NULL) NOT VALID` → `VALIDATE` → `SET NOT NULL` (PG12+ reuses the proof, skips the scan) |

---

## 11.4 Expand / Contract — the zero-downtime recipe

Any *breaking* change is split into non-breaking steps across multiple deploys, so the system is consistent at every moment — even with old and new code running at once. Four phases:

1. **Expand** — add the new structure, purely additive (new nullable column / new table). Old and new code both still work.
2. **Migrate** — dual-write (app writes both old and new) and **backfill** existing rows.
3. **Switch** — move reads to the new structure; deploy code that uses it.
4. **Contract** — once nothing touches the old structure, remove it.

Concrete LMS example — splitting `member.name` into `first_name` / `last_name`:

| Phase | Action | Old code | New code |
|---|---|---|---|
| Expand | add `first_name`, `last_name` (nullable) | ✅ uses `name` | ✅ |
| Migrate | backfill from `name`; app dual-writes all three | ✅ | ✅ |
| Switch | deploy code reading `first_name`/`last_name` | — | ✅ |
| Contract | `DROP COLUMN name` | gone | ✅ |

No single step breaks a half-deployed fleet. That is the entire point.

---

## 11.5 Backfills run in batches

The backfill in phase 2 is **not** `UPDATE member SET ...` in one statement — on a large table that locks millions of rows, bloats the WAL, and holds one giant transaction open. Loop in **bounded batches** (by id range), committing each, with a small throttle:

```sql
-- repeat until no rows remain
UPDATE member SET first_name = split_part(name,' ',1)
WHERE member_id BETWEEN :lo AND :hi AND first_name IS NULL;
```

(At 100 members this is one trivial statement — but the batched habit is what saves you at 100 million.)

---

## 11.6 Rollback discipline — and its honest limit

Every migration gets a tested `downgrade()` — CI should run `upgrade → downgrade → upgrade` to prove it round-trips. But be honest about the limit: **a downgrade can restore structure, not data.** A `downgrade()` for `DROP COLUMN` can re-add the column, but the values are gone.

So the real safety net is **staging, not reversal**: expand/contract delays the destructive `contract` until you're confident, and you take a backup before any irreversible step. Downgrades shine in dev/CI; in production, destructive changes are usually fixed *forward*, and the discipline is to not do the destructive thing until nothing depends on the old shape.

---

## 11.7 At our scale — institutionalize the workflow, not the paranoia

At 100 members none of the locking matters — every migration is instant. The point of adopting Alembic, expand/contract, batched backfills, and tested downgrades *now* is that they are **process habits**: cheap to establish on a small DB, invaluable and hard to retrofit once the data is large and uptime is real. Start as you mean to scale.

---

## What we produced in Step 11

- The **migration discipline**: schema as versioned, ordered, reversible code; the Step-10 DDL reframed as migration 0001.
- An **Alembic** mental model (revision chain, up/down, autogenerate's caveats).
- A table of **dangerous operations and their lock-safe stagings** (`CONCURRENTLY`, `NOT VALID`/`VALIDATE`, nullable-then-backfill).
- The **expand/contract** pattern worked through on a real LMS change, plus **batched backfills** and an honest account of rollback's limits.

## Key takeaways (transferable)

1. **Never hand-edit production schema.** Versioned, ordered, reversible migrations or nothing.
2. **A live migration can lock the table or break half-deployed code** — the two failure modes to design against.
3. **Expand/contract** turns any breaking change into additive steps that are safe at every moment of a rollout.
4. **`CREATE INDEX CONCURRENTLY`, `ADD CONSTRAINT … NOT VALID` → `VALIDATE`** are the lock-avoiding forms of common ops.
5. **Downgrades restore structure, not data** — safety comes from staging and backups, not from trusting reversal.

## Principles in play

| Principle | How this step applied it |
|---|---|
| **Schema is code** | Versioned, reviewed, reproducible migrations; Step-10 DDL = migration 0001 |
| **Safe under rollout** | Expand/contract keeps old + new code consistent simultaneously |
| **Avoid the lock** | Concurrent index builds, `NOT VALID`/`VALIDATE`, batched backfills |
| **Start as you mean to scale** | Adopt the workflow at 100 rows so it's ready at 100M |

---

*Next — Step 12: Scale & the road not taken. We close the schema arc by justifying everything we deliberately did **not** build — read replicas, sharding, partitioning, caching, NoSQL — mapping each to the load it answers and showing why none is warranted at 100 members. The discipline of refusing scale you don't have is the counterpart to every YAGNI call the series has made.*
