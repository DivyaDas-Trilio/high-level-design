# HLD Building Blocks — the course

> Every high-level design you will ever be asked for is **assembled from a small toolbox**.
> This track walks that toolbox one block at a time, at the depth where you can both pass a
> FAANG interview *and* ship the thing in production.
>
> The discipline that matters: **a block is never learned in isolation from the
> non-functional requirement that summons it.** Read-heavy → cache + replicas. Spiky →
> queue. Huge → shard. You design by matching *requirements → blocks*, never by sprinkling
> in impressive-sounding tech. `../concepts/building_blocks.md` is that mapping on one page;
> this directory is the deep dive behind every row of it.

## How this course is organised

- **18 topics**, numbered to match the source syllabus (`01_database` … `18_bloom_filters`),
  so the tree maps 1:1 to the course outline.
- **Taught in dependency order, not numeric order** — see the roadmap below. Directory
  numbers are the *syllabus* index; the `Order` column is the *teaching* index.
- Each topic directory holds its own `README.md` (chapter roadmap + status + revision card),
  its `step-NN-<slug>.md` chapters, and one `lab/` — a substantial hands-on build.
- **~125 chapters total.** One per sitting. We advance when you say **"next"**.

## Chapter anatomy

Every chapter follows the same skeleton, because the repetition is what builds the reflex:

| Section | What it does |
|---|---|
| **The problem** | A concrete system that is failing *right now* — the block earns its existence |
| **Example first** | A real product, real numbers, before any theory |
| **Mechanism** | How it actually works *internally* — data structures, not API surface |
| **Trade-offs & failure modes** | Named out loud. What this block costs you, and how it breaks |
| **Production reality** | The knobs, real latency/throughput figures, what breaks at scale |
| **FAANG interview angle** | How it gets asked, the follow-up probes, red-flag answers |
| **Key takeaways** | Transferable beyond this block |
| **Principles in play** | Two-column table: principle → how this chapter applied it |

## Roadmap

| Order | # | Topic | Ch. | Why here in the sequence | Status |
|---:|---:|---|---:|---|---|
| 1 | [05](05_client_server_and_protocols/) | **Client–Server & Protocols** | 11 | The request path frames every other block. You cannot reason about latency, caching, or load balancing without it | 🔵 in progress |
| 2 | 04 | Load Balancers | 7 | First box the request meets. HAProxy/Nginx internals, L4 vs L7, global LB | pending |
| 3 | 08 | Rate Limiting | 7 | Lives at the edge you just built. All five algorithms, then distributed enforcement | pending |
| 4 | 01.1 | Relational / MySQL | 7 | The default datastore. Engine internals, B+trees, MVCC, sharding | pending |
| 5 | 09 | Consistent Hashing | 4 | The primitive that makes sharding and distributed caches possible | pending |
| 6 | 10 | Replication & Consistency | 9 | CAP/PACELC, quorums, Raft. The hardest topic; everything distributed leans on it | pending |
| 7 | 18 | Bloom Filters | 4 | Pulled early: it's a component *inside* the LSM engines we meet next | pending |
| 8 | 01.2 | Non-Relational (Redis, DynamoDB, Cassandra, MongoDB, ES) | 7 | Now they land properly — Dynamo and Cassandra *are* consistent hashing + quorum replication | pending |
| 9 | 02 | Caching (Redis & Memcached internals) | 8 | Patterns, eviction, stampedes, hot keys, the Facebook memcache paper | pending |
| 10 | 03 | Messaging Queues (RabbitMQ, Kafka) | 9 | Decoupling in time. Delivery semantics, partitions, the outbox pattern | pending |
| 11 | 06 | Storages (Ceph, S3, ext4, CephFS) | 7 | Block vs file vs object, CRUSH, erasure coding — unusually deep, it's your day job | pending |
| 12 | 07 | CDN | 5 | Object storage + the RTT physics from Topic 05 = why the edge exists | pending |
| 13 | 11 | Search / Inverted Indexes | 6 | Lucene segments, BM25, Elasticsearch architecture, autocomplete | pending |
| 14 | 12 | Notification Systems | 5 | First composite system: queues + fan-out + push + preferences | pending |
| 15 | 13 | Real-Time Communications | 5 | WebSockets, a million connections, presence, chat end-to-end | pending |
| 16 | 14 | Data Duplication & Idempotency | 5 | The bill that at-least-once delivery leaves you | pending |
| 17 | 15 | Distributed Locks | 5 | Redlock and its critique, fencing tokens, and when *not* to need a lock | pending |
| 18 | 16 | Service Discovery & Coordination | 5 | etcd/Consul/K8s, service mesh, xDS | pending |
| 19 | 17 | Monitoring, Logging, Metrics | 6 | How you know any of the above is working. SLI/SLO/error budgets | pending |

*Legend: ✅ done · 🔵 in progress · pending*

## The application track

Blocks learned in isolation are inert. Every ~4 topics, they get composed into a full design
in [`../projects/`](../projects/) — which is exactly the interview motion: enumerate the
non-functional requirements, then pull only the blocks each one demands.

| After topics | Compose them into |
|---|---|
| 05, 04, 08 | `projects/foundation/01_url_shortener` (steps 3–6) — API, edge, rate limiting |
| 01, 09, 10, 18 | A sharded, replicated datastore design |
| 02, 03 | `projects/intermediate/` — a read-heavy feed |
| 06, 07, 11 | A media/upload + search platform |
| 12, 13, 14, 15, 16, 17 | `projects/advanced/` — chat + notifications, operated |

## Prior material in this repo

These predate the track and are **broad survey docs, not deep dives** — treated as
supplementary reading, cross-linked from the chapters that supersede them:

| Existing | Relates to |
|---|---|
| [`../databases/`](../databases/) `01_`–`08_` | Topics 01, 10 |
| [`../databases/library_db_design/`](../databases/library_db_design/) — 13 chapters, deep, **at the bar** | Topic 01.1. The relational chapters here deliberately skip schema design and go at engine internals instead |
| [`../message_queues/`](../message_queues/) incl. `RABBITMQ_DEEP_DIVE.md` | Topic 03 |
| [`../loadbalancer/`](../loadbalancer/) modules + labs | Topic 04 |
| [`../distributed-systems-course/`](../distributed-systems-course/) | Topics 10, 16, 17 |
| [`../concepts/`](../concepts/) — `building_blocks.md`, `scaling_playbook.md`, `sagas_and_2pc.md` | The index and the composition rules |

---

*Course status: Topic 05 (Client–Server & Protocols) — Chapters 1–4 docs written (topic expanded 9 → 11: HTTP caching and async API surfaces inserted); neither yet
worked through or drilled. A chapter counts as done when it has been discussed,
pressure-tested, and its open questions closed — not when the file exists.*
