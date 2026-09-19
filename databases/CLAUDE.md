# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

This is the `/databases/` area of the `high-level-design/` learning repository (which itself sits under the larger workspace described in `../../CLAUDE.md`). It is a **documentation/curriculum repository, not a buildable application** — there is no build, lint, or test system here, no `package.json`/`requirements.txt`/`Makefile`. The deliverable is the Markdown itself.

The content is a self-paced curriculum on database design, scalability, ORMs, and distributed systems, aimed at staff/senior-staff engineer level. Code (Python with SQLAlchemy/FastAPI, and SQL) lives *inside* the Markdown as illustrative fenced examples — it is meant to be read and copied, not executed from files in the tree.

## Structure and conventions

- **Numbered modules `01_`–`08_`** form an ordered learning path (fundamentals → scalability → replication/HA → ORM patterns → FastAPI app → advanced ORM → distributed systems → cloud-native). Treat the number prefix as a deliberate sequence; new modules should slot into that ordering.
- **Topic guides** (un-numbered): `DATABASE_LEARNING_PATH.md` (curriculum index with checkboxes), `SQLALCHEMY_CLIENT_GUIDE.md`, `ESSENTIAL_SQL_QUERIES.md`, `QUICK_REFERENCE.md`, `HANDS_ON_PROJECT.md`, `LIBRARY_MANAGEMENT_SYSTEM_DESIGN.md`.
- **`relational_db/` and `non_relational_db/`** are placeholder dirs for hands-on implementation examples; currently near-empty.
- Docs cross-reference each other with relative Markdown links (e.g. `[01_ACID_AND_FUNDAMENTALS.md](01_ACID_AND_FUNDAMENTALS.md)`). When renaming, moving, or adding a doc, update both `DATABASE_LEARNING_PATH.md` and the parent **`../README.md`**, which is the human-facing index for the whole `high-level-design` repo — these are the two places that go stale.
- Code fences are predominantly ```python and ```sql; keep examples runnable-by-copy and consistent with the SQLAlchemy 2.0 / FastAPI / repository-pattern style already used across `04_`–`06_`.

## Working here

- Most tasks are writing/editing prose and embedded examples — no commands to run to "verify" beyond Markdown rendering. If you want to sanity-check an embedded Python snippet, extract it and run `python3` ad hoc; SQLite examples use the stdlib `sqlite3` module.
- Keep the staff-engineer altitude: emphasize trade-offs (consistency vs. availability, normalization vs. denormalization, sync vs. async) over toy syntax, matching the existing tone.

## Known stray artifact

`relational_db/sqlite3/:memory` is an actual SQLite database file accidentally created by passing `:memory` (missing the trailing colon) instead of the in-memory sentinel `:memory:` to a SQLite connect call. It is git-staged but not intended content — flag it / remove it rather than treating it as a real fixture.
