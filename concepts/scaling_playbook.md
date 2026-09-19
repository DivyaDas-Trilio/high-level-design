# The Scaling Playbook — How Step 5 Actually Makes a System Scalable

> Step 5 ("high-level design") is really TWO activities: (A) construct the baseline diagram,
> then (B) apply the scaling playbook — which bleeds into the Step 6 deep dive.
>
> **Master mental model:** *Scaling is iterative bottleneck removal. Each technique fixes the
> current bottleneck and reveals the next. You never apply all of them — only the next one
> your numbers demand.*

## Phase A — Construct the baseline (sub-steps to draw the boxes)
1. **List components** from the API + data model: clients, app service(s), datastore(s).
2. **Draw the write path** for the primary use case: client → service → DB.
3. **Draw the read path separately** — read and write paths scale differently.
4. **Add the entry layer:** DNS → load balancer → (API gateway).
5. **Mark where state lives** — state is the enemy of horizontal scaling; find it now.
Start with the simplest thing that works (one server), then evolve via Phase B.

## Phase B — The Scaling Playbook (1 server → millions, in bottleneck order)
| # | Sub-step | Bottleneck it removes | New bottleneck it reveals |
|---|---|---|---|
| 1 | Single server (app+DB) | — | resource contention; 1 failure = total outage |
| 2 | Split tiers (app ⟂ DB) | resource contention | each tier still a single box |
| 3 | Horizontal-scale app (LB + N stateless servers) | app CPU limit; availability | DB becomes bottleneck; where's session state? |
| 4 | Make services stateless (sessions → Redis) | sticky-session problem | (enables #3 to truly scale) |
| 5 | Add cache (cache-aside) for hot reads | repeated expensive DB reads | cache invalidation, hot keys |
| 6 | DB read replicas (leader-follower) | read load on primary; read availability | replication lag (eventual consistency) |
| 7 | CDN for static/cacheable content | latency + origin bandwidth | only helps cacheable data |
| 8 | Shard / partition the DB | write throughput + storage limit of 1 node | cross-shard queries, rebalancing, hot shards |
| 9 | Async + message queue for slow work | slow ops blocking the request path | eventual consistency, backlog, ordering |
| 10 | Specialized stores (search/blob/time-series) | one DB can't do everything well | more systems to sync |
| 11 | Multi-region / geo-routing | global latency + regional DR | cross-region consistency, data residency |
| 12 | Autoscaling + observability | manual capacity, blind spots | cost, complexity |

## The 5 dimensions of "scalable" (match technique to dimension)
"Scale" is not one thing — name the dimension, then pick:
| Dimension | Primary techniques |
|---|---|
| More reads | cache, read replicas, CDN |
| More writes | sharding, async/queue, batching, write-back |
| More data | partitioning, tiered/cold storage, archival |
| More users globally | multi-region, geo-routing, edge |
| Higher availability | redundancy, replication, failover, multiple AZs |

## Principles underneath every sub-step
1. **Scale out, not up.** Vertical hits a ceiling + price cliff; horizontal scales ~linearly
   and adds redundancy.
2. **Statelessness is the enabler.** You can only horizontally scale what holds no local
   state → push state to a shared store/DB. (#4 unlocks #3.)
3. **Cache the reads, queue the writes** — highest-leverage moves for the two hardest dimensions.
4. **Remove one bottleneck at a time, driven by numbers** — don't shard a DB serving 10 QPS.
5. **Every fix has a cost** — replication→lag, sharding→cross-shard queries, async→eventual
   consistency. Naming the NEW problem each fix introduces is the Step-6 deep-dive skill.

## Tutorial-ready punchline
*Step 5A draws the simplest correct system. Step 5B/6 evolves it by repeatedly asking
"what breaks at 10×?" and applying the one technique that fixes it — then asking again.*
That narrated loop is what a scalable-systems interview actually measures.

## Tie-back to the modules
- **Module 00 LMS** stops at sub-step ~2 (no scale pressure — that IS the lesson).
- **Module 01 TinyURL** marches through 3 → 5 → 6 → 8 (LB, cache, replicas, sharding)
  because its numbers demand it — you'll feel each bottleneck appear.

## Self-check
1. Why must read and write paths be drawn separately?
2. Why does "make services stateless" (#4) have to come before app servers truly scale (#3)?
3. For each of the 5 dimensions, name its primary technique.
4. Replication, sharding, and async each introduce a new problem — name all three.
5. A DB serving 10 QPS is slow. Is sharding the right fix? Why/why not?
