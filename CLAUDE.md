# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`high-level-design/` is a **documentation/curriculum repository, not a buildable application**. There is no build, lint, or test system at any level — no `Makefile`, `package.json`, `pyproject.toml`, or `requirements.txt`. The deliverable is the Markdown. Code (Python, SQL, YAML, nginx/HAProxy config) lives *inside* fenced blocks as illustrative examples meant to be read and copied.

It sits under the larger workspace described in `../CLAUDE.md`. Target altitude throughout: **staff/principal engineer** — the recurring move is to surface the trade-off behind a decision (consistency vs. availability, normalization vs. denormalization, monolith vs. split) rather than state syntax.

## The three content genres

Nearly every task is writing or extending one of three shapes. Identify which before editing — they have different conventions and different doc templates.

**A. Reference curricula** — topic explainers, ordered by an `NN_` numeric prefix, indexed by a `README.md` table with duration/difficulty columns:

- `databases/` — ACID → scalability → replication → ORM patterns → FastAPI → distributed systems → cloud-native (`01_`–`08_`), plus un-numbered guides (`QUICK_REFERENCE.md`, `ESSENTIAL_SQL_QUERIES.md`, `SQLALCHEMY_CLIENT_GUIDE.md`). Has its own `CLAUDE.md`.
- `message_queues/` — event-driven architecture; `RABBITMQ_DEEP_DIVE.md` is the largest doc in the repo (~8.5k lines).
- `distributed-systems-course/` — 10 module directories, each holding a single `README.md`.
- `loadbalancer/` — `modules/` (theory) + `labs/` (hands-on) + `resources/`.
- `concepts/` — short cross-cutting indexes (`building_blocks.md`, `scaling_playbook.md`, `sagas_and_2pc.md`) that link *into* the deep dives. `building_blocks.md` has a "Deep-dived in" column filled in as modules land; keep it current when a block gets covered.

**B. Step-by-step teaching series** — one narrative build of one problem, one chapter per file, **strictly sequential**. Each chapter recalls what the previous produced and tees up the next; don't write Step 5 before Step 3.

- `databases/library_db_design/` — `step-NN-<slug>.md` (hyphens, zero-padded). LMS requirements → relational schema, 13 steps, complete. Has its own `CLAUDE.md` with the chapter skeleton.
- `projects/foundation/00_library_management_system/` — `step_N_<slug>.md` (underscores, unpadded). The LLD→HLD bridge: same LMS domain re-read at HLD altitude.
- `projects/foundation/01_url_shortener/` — same naming; follows an explicit 6-step spine (requirements → estimation → API → data model → high-level → deep dive).
- `building-blocks/` — the 18-topic HLD block course (`NN_<topic>/` keeping *syllabus* numbers, taught in a dependency order set by the roadmap table, `step-NN-<slug>.md` chapters, one `lab/` per topic). `building-blocks/README.md` is the status source of truth.

**C. Video-teaching courses** — the same material aimed at being *taught on camera*, so every doc carries diagram and script sections that the other two genres don't have.

- `building-blocks/05_client_server_and_protocols/basic_networking/` — networking fundamentals down to the mechanism (bytes, header fields, state machines, syscalls). Every topic doc follows `docs/_TEMPLATE.md`: one-liner → problem it solves → deep-dive mechanism → mental model → hands-on commands → misconceptions → **diagrams needed** → **video script outline** (hook/build/payoff/recap) → **brainstorm / open questions** → references, with a status/prereqs/OSI-layer blockquote at the top and wiki-style `[[links]]` between topics. `PROGRESS.md` is the status tracker (🔲 / 🟡 / 🎥 / ✅) and carries a dated session log; `ROADMAP.md` holds three candidate orders with one marked ACTIVE. `labs/` are Packet Tracer + host-tool walkthroughs; `scripts/` holds runnable demo servers. Roughly a third of the topic docs are filled; the rest are still bare copies of the template (a 50-line file is an untouched stub).

**Genres B and C overlap in subject but not in altitude.** `basic_networking/` teaches the *mechanism*; the `building-blocks/` chapters teach the *design trade-off with numbers*. It now lives **inside** Topic 05 rather than at the repo root, so cross-links from those chapters are `basic_networking/docs/…` (same directory), not `../../`. When both cover a topic, cross-link rather than restate.

**Filename style differs between the two series styles** (`step-01-` vs `step_1_`). Match the directory you are in; do not normalize across them.

## Working conventions

- **Pace is user-driven.** The project READMEs state it explicitly: *"one step at a time. We advance when you say **next**."* Write one step per turn, then stop. Do not run ahead and generate the remaining chapters.
- **README index tables are the status source of truth.** Every series README carries a roadmap table or a `- [x]/- [ ]` checklist. Update it — and any "Series status" footer — in the *same change* that adds or finishes a chapter. These and `../README.md` are what go stale.
- **Diagrams** are given in both Mermaid (renders on GitHub) and an ASCII fallback for the terminal.
- **PostgreSQL** is the reference SQL dialect; MySQL/SQLite deltas are flagged inline only where they matter.
- **Match the design to the scale.** The LMS problem is deliberately tiny (~100 members, ~500 books, one branch) and the docs explicitly *refuse* sharding/replication/denormalization the scale doesn't earn. Don't add impressive-sounding tech that no requirement asked for.
- **Cross-repo links to `../../../lld/library_management_system_v2/…` do not resolve in this checkout.** They point at a sibling series in the workspace. Treat them as external pointers — don't try to read them and don't "fix" them into broken local paths.

## The only executable code

`caches/redis/python-impl/` — a small `redis-py` scratchpad (`redis_client.py`) plus a Dynaconf config layer (`config.py`, `settings.yaml`, gitignored `.secrets.yaml`). Run ad hoc:

```bash
python3 caches/redis/python-impl/redis_client.py   # needs a reachable Redis
```

Caveats before touching it: the Redis host/port are hardcoded in `redis_client.py` (the `config.py` import is commented out), `config.py` has a live `pdb.set_trace()` in it, and `lrange(name=session, ...)` references the imported `requests.session` rather than the string `"session"` — it is a broken experiment, not a reference implementation. `caches/redis/java-impl/` is an empty placeholder.

For sanity-checking a snippet embedded in a doc, extract it and run `python3` ad hoc; SQLite examples use the stdlib `sqlite3` module.

## Known stale content and stray artifacts

Several indexes over-promise. Verify before linking to or relying on them:

- **`README.md` (root)** lists a `networking/` section, but those files (`socket_server.py`, `socket_client.py`, `sniff.py`, TLS certs) are deleted in the working tree and not yet committed. Its `databases/…` link prefixes are also relative to the repo root.
- **`databases/README.md`** is a near-copy of the root README, so its `databases/…`-prefixed links are broken from inside `databases/`.
- **`message_queues/README.md`** tabulates modules `03_`–`08_`; only `01_` and `02_` exist.
- **`distributed-systems-course/README.md`** lists module 07 as *Security*, but the directory is `07_SYSTEM_BUILDING_BLOCKS/`; `08_PERFORMANCE_SCALABILITY/` is empty.
- **`databases/library_db_design/CLAUDE.md`** says only Steps 1–2 exist; all 13 are written. Fix it if you touch that directory.
- Empty placeholder dirs: `databases/non_relational_db/`, `databases/relational_db/mysql/`, `projects/intermediate/`, `projects/advanced/`, `loadbalancer/projects/`, `loadbalancer/resources/{config,monitoring}-templates/`, `loadbalancer/resources/{testing-guides,troubleshooting}/`.
- **`databases/relational_db/sqlite3/:memory`** is a real SQLite file created by passing `:memory` (missing the trailing colon) instead of `:memory:`. It is git-staged but not intended content — remove it rather than treating it as a fixture.
- `.DS_Store` is tracked in git and shows as modified; leave it alone unless asked.

## Nested guidance

`databases/CLAUDE.md` and `databases/library_db_design/CLAUDE.md` carry area-specific detail (module ordering, the required chapter skeleton, the recurring "one source of truth" spine). Read the closest one before editing in those trees.
