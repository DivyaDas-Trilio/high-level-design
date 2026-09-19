# HLD Building Blocks — Master Index

> Every HLD is assembled from this small toolbox (~20 blocks). Master these and you can
> compose any system. **Never memorize a block without its "problem it solves"** — each one
> exists to satisfy a non-functional requirement. You design by matching *requirements →
> blocks*, never by sprinkling in impressive-sounding tech.
>
> Deep dives happen *in context* — the "Deep-dived in" column links each block to the module
> where we study it against a real problem. (Filled in as we go.)

## 1. Traffic & entry (getting the request in)
| Block | Problem it solves | Deep-dived in |
|---|---|---|
| DNS | Map name → IP; route users to nearest region | — |
| Load balancer | Spread traffic across servers; hide dead ones | — |
| API gateway | One entry: auth, rate limit, routing, SSL termination | — |
| CDN | Serve cacheable content from the edge → low latency, less origin load | 07 Netflix |
| Protocols (REST / gRPC / WebSocket) | REST=simple; gRPC=fast internal; WebSocket=real-time push | 04 Chat |

## 2. Compute (doing the work)
| Block | Problem it solves | Deep-dived in |
|---|---|---|
| Stateless app servers | Horizontal scaling — add boxes, no sticky session | — |
| Microservices vs monolith | Independent scale/deploy vs simplicity | 00 LMS (step 2) |

## 3. Caching (avoid repeating expensive work)
| Block | Problem it solves | Deep-dived in |
|---|---|---|
| Client / browser cache | Don't even make the request | — |
| Distributed cache (Redis/Memcached) | Absorb read-heavy load off the DB | 01 TinyURL, 08 dist. cache |
| Cache patterns (cache-aside, write-through) + eviction (LRU/LFU) + TTL | Keep the cache correct and fresh | 01 TinyURL, 08 dist. cache |

## 4. Storage & databases (keeping the data)
| Block | Problem it solves | Deep-dived in |
|---|---|---|
| SQL (relational) | Strong consistency, transactions, joins | 00 LMS, 01 TinyURL |
| NoSQL (KV, document, wide-column, graph) | Scale + flexible schema when no joins/ACID needed | 03 Twitter |
| Blob / object store (S3) | Big files: images, video, backups | 07 Netflix, 10 Dropbox |
| Search index (Elasticsearch) | Full-text search the DB can't do well | 00 LMS (Catalog) |
| Time-series DB | Metrics/events at high write volume | 09 ad aggregator |

## 5. Data distribution (when one machine isn't enough)
| Block | Problem it solves | Deep-dived in |
|---|---|---|
| Replication (leader-follower) | Availability + read scaling + durability | 00 LMS, 03 Twitter |
| Sharding / partitioning | Split data across machines | 01 TinyURL |
| Consistent hashing | Add/remove nodes without reshuffling everything | 08 dist. cache |

## 6. Async & messaging (decouple in time)
| Block | Problem it solves | Deep-dived in |
|---|---|---|
| Message queue (SQS/RabbitMQ) | Smooth spikes, retry, decouple producer/consumer | 00 LMS (notifications) |
| Pub/Sub & event streaming (Kafka) | Fan-out to many consumers; replayable log | 09 ad aggregator |
| Task / worker queue | Offload slow work (email, image resize) off request path | 05 Uber |

## 7. Coordination & consistency (the hard distributed stuff)
| Block | Problem it solves | Deep-dived in |
|---|---|---|
| Consensus (Raft/Paxos) | Agree on one value despite failures (leader election, config) | 08 dist. cache |
| Distributed lock / coordination (ZooKeeper, etcd) | Only-one-does-this-at-a-time across machines | 01 TinyURL (key gen) |
| Consistency models (CAP, PACELC, strong vs eventual) | The fundamental trade-off — articulate every time | 06 Google Docs |

## 8. Reliability & scale patterns (surviving reality)
| Block | Problem it solves | Deep-dived in |
|---|---|---|
| Rate limiter | Protect system from abuse/overload | 02 rate limiter |
| Circuit breaker / retry / timeout | Stop cascading failures when a dependency dies | — |
| Idempotency | Safe retries — the "exactly once" illusion | 09 ad aggregator |
| Bloom filter | Cheaply answer "definitely not present" before an expensive lookup | 01 TinyURL |
| Backpressure | Don't let a fast producer drown a slow consumer | 09 ad aggregator |

## 9. Observability (knowing what's happening)
| Block | Problem it solves | Deep-dived in |
|---|---|---|
| Logging, metrics, tracing | Debug + alert across many services | — |
| Health checks | Let the LB route around sick instances | — |

---

## How to use this index
1. **In an interview / design:** list the non-functional requirements first, then pull only
   the blocks each one demands. Read-heavy → cache + replicas. HA → replication + LB.
   Spiky/decoupled → queue. Huge data → shard.
2. **While learning:** each time a module deep-dives a block, fill the "Deep-dived in" link
   and add a one-line "what I learned" so this becomes your personal revision sheet.

> **The mapping that matters:** non-functional requirement → building block. Memorize *that
> relationship*, not the blocks in isolation.
