# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`library_db_design/` is a **single, ordered teaching series** — "Designing the LMS Database, step by step" — that turns the Library Management System requirements into a relational schema, one chapter at a time, writing the *reasoning* down as it goes. It is documentation, not a buildable app: no build/lint/test system, no `CREATE TABLE` script yet (that arrives at Step 10). The deliverable is the Markdown.

It sits inside the larger `/databases/` curriculum (see `../CLAUDE.md`) but is its own thing: where the numbered `01_`–`08_` modules in the parent are topic explainers, this directory is a *narrative build* of one schema for one fixed problem.

The problem is deliberately small and fixed (`README.md`): one library, ~100 members, ~500 books, one branch, borrow limit 2, 5-day loan, ₹5/day fine, no renewals. The smallness is the point — every chapter matches the design to that scale and explicitly *refuses* sharding/replication/denormalization the scale doesn't earn.

## Structure

- **`README.md`** is the index and the spec. Its roadmap table lists all 13 planned steps with a Status column (`✅ done` / `⬅️ next` / `pending`). This is the source of truth for what exists and what's next — update it in the same change that adds or finishes a chapter, including the "Series status" footer line.
- **`step-NN-<slug>.md`** — one file per chapter, zero-padded. Currently Steps 1–2 exist; Step 3 (Logical model & normalization) is next.
- The series is **strictly sequential** — each chapter opens by recalling what the previous produced and ends by teeing up the next. A new chapter slots into the existing numeric sequence; don't write Step 5 before Step 3.

## Chapter format (follow it when adding/editing a step)

Every step file uses the same skeleton, and matching it is what keeps the series coherent:

1. Title `# Step N — <Name>` and a `*Series: Designing the LMS Database · Chapter N of 12*` subtitle.
2. A framing hook tying the DB concept to its LLD analogue ("access patterns before tables" mirrors "language before classes").
3. Numbered subsections `N.1`, `N.2`, … : a little theory → applied to the LMS → *why each decision* → trade-offs named out loud.
4. **`## What we produced in Step N`** — concrete artifacts.
5. **`## Key takeaways (transferable)`** — numbered, generalizable beyond the LMS.
6. **`## Principles in play`** — a two-column table (Principle | How this step applied it).
7. A closing `*Next — Step N+1: …*` italic teaser.

## Conventions specific to this series

- **Reference dialect is PostgreSQL.** Flag MySQL/SQLite differences inline only where they actually matter.
- **Altitude: staff-engineer reasoning, not syntax.** The recurring move is to surface the decision *behind* a choice — invariant vs. cardinality, source-of-truth vs. derived value, YAGNI vs. premature denormalization. When in doubt, explain the trade-off, don't just state the answer.
- **Recurring spine, keep it consistent:** access-patterns-before-tables; one source of truth (availability is a *query* over `BookCopy.status`, never a stored `available_count`); don't store derivable data unless the input is volatile (`due_date`) or measurement demands a cache.
- **Crow's-foot ER notation**; diagrams are given in **both** Mermaid (renders on GitHub) and an ASCII fallback for the terminal.
- "Scale forks" (decisions the requirements leave open, e.g. Author as M:N vs. a text column) are written as explicit one-liners so they're conscious choices, not silent assumptions.

## Cross-references

- The series is framed as the DB companion to an LLD/DDD series, linked as `../../../lld/library_management_system_v2/…`. **That path does not resolve in this checkout** (there is no `lld/` under `high-level-design/`). Treat those links as pointers to a sibling repo/series, not local files — don't assume you can read them, and don't "fix" them into broken local paths.
- Step 13 is the declared seam back to that LLD series (SQLAlchemy models + Repository pattern). Keep schema decisions here compatible with a persistence-ignorant domain layer.
