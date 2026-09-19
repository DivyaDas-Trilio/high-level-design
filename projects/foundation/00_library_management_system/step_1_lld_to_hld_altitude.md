# Module 00 · Step 1 — From LLD to HLD: Re-reading the Domain at Altitude

> Same system, different question. The one mental move: **stop thinking in classes and
> method calls; start thinking in services, datastores, queues, and network hops** — while
> keeping the correctness your LLD already guarantees.

## The altitude shift
| | LLD (in `lld/`) | HLD (here) |
|---|---|---|
| Core question | Is my object model correct/extensible inside one process? | Does it stay correct, available, fast across many machines + partial failure? |
| Unit of thought | Class, aggregate, method call | Service, datastore, queue, network hop |
| "Consistency" | One in-memory transaction guards an invariant | Distributed: replicas, partitions, eventual vs strong |
| Failure worried about | A bug / exception | A machine dies, a call times out, a queue backs up |
| `borrow()` flow | 3 local loads + 1 DB transaction | Maybe 3 network calls + a saga (if split) |

**Tutorial-ready model:** *LLD makes one process correct. HLD keeps correctness while adding
availability, scale, and survival-of-failure across many processes.* New forces: network
latency, partial failure, data volume, throughput, deployment.

## Continuity: DDD already drew the seams
Your Step 5 rule — *"a service boundary should fall between aggregates, never through one"* —
means your bounded contexts ARE the candidate service boundaries. Aggregates are the grain;
cuts fall along subdomains.

### Candidate services (re-reading the domain at altitude)
| Candidate service | Owns (aggregates) | HLD character |
|---|---|---|
| **Catalog** | Book | Read/search-heavy → cache + search index |
| **Inventory** | BookCopy | Write-heavy status churn → contention hot spot |
| **Membership** | Member | Low traffic, identity-adjacent |
| **Lending** | Loan | Transactional **core** — orchestrates borrow/return |
| **Fines** | Fine | Money → strong consistency, audit trail |
| **Notifications** | — (reacts to events) | Async → queue consumer |

## The strategic lens HLD adds: Core / Supporting / Generic
Decides where to spend the scaling/reliability budget:
- **Core → Lending.** The reason the system exists. Invest most (correctness of issue/return).
- **Supporting → Catalog, Membership, Fines.** Necessary, domain-specific, not crown jewels.
- **Generic → Notifications, Auth.** Buy, don't build (SendGrid, Auth0).

## What this step produces
A **context map at altitude**: the candidate services above, recognizing they currently all
live inside one modular-monolith deployable. We have NOT decided to split — that's Step 2.
Restraint is the point: most engineers split too early.

## Self-check
1. Name three *new* forces HLD must handle that LLD did not.
2. Why are bounded contexts (not aggregates) the right granularity for a service?
3. Classify each LMS subdomain as Core / Supporting / Generic — and say what that implies
   for where you'd add caches/replicas vs. buy a SaaS.
