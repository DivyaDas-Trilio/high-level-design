# Module 00 · Step 2 — Monolith First: When LMS Should *Not* Be Distributed

> A judgment step, not a drawing step. Step 1 found 6 *candidate* services. The mid-level
> instinct is to split them into 6 microservices immediately. That instinct is wrong, and
> knowing *why* is the lesson. **Distribution buys independence, not scale — and you pay for
> it in network failure, distributed transactions, and ops overhead.**

## First, prove it with numbers
LLD non-functionals: 100 members, 500 books.
```
Copies ≈ 500 × 5 = 2,500.  Members = 100.
Borrow/return ≈ 3×/week/member → 300/week = 0.0005 ops/sec (~zero).
Peak: a few ops/sec.  Data: a few thousand rows × ~1KB ≈ single-digit MB (fits in RAM).
```
One small Postgres on one box handles this with ~4 orders of magnitude of headroom, for
years. **There is no scaling problem to solve.** Distribution solves problems we don't have.

## The cost of distribution (paid the instant you split)
| You lose (free in a monolith) | Because… |
|---|---|
| The local ACID transaction | `borrow()` was one transaction; split Member/Inventory/Loan → **distributed saga** + compensations |
| Reliability | In-process calls never half-fail; network calls time out / retry / duplicate → handle partial failure everywhere |
| Latency | In-process ≈ ns; network hop ≈ 0.5ms+ each; borrow becomes 3 round-trips |
| Simple debugging | One stack trace → distributed tracing |
| Easy consistency | One DB always consistent → eventual consistency, duplication, sync |
| Operational simplicity | 1 deploy/log/dashboard → N each + discovery + gateway |

**Tutorial-ready model:** *Microservices buy independence (deploy, scale, failure, team
ownership), not scale. You pay in network failure + distributed transactions + ops. Only
buy independence when you actually need it.*

## Signals that WOULD justify splitting (memorize)
1. **Independent scaling** — one part needs far more resources than the rest.
2. **Independent deploy cadence / team autonomy** (Conway's Law).
3. **Fault isolation** — a crash in one part must not kill the core.
4. **Different storage/tech needs** — search index vs strict relational audit store.
5. **Different data lifecycle / compliance** — e.g. payment data retention/security.

For LMS: none are true → stay monolith.

## Verdict: a MODULAR MONOLITH (the smart middle ground)
One deployable, but bounded contexts kept as internal modules:
```
┌──────────── Library (one deployable) ────────────┐
│ [Catalog][Inventory][Membership][Lending][Fines] │  modules, not services
│  each: own package + own tables; talk via         │
│  interfaces + in-process domain events            │
│              one shared database                   │
└───────────────────────────────────────────────────┘
```
Best of both: monolith simplicity now, clean seams so extraction is cheap later. Aggregates
already reference each other **by ID** (Step 5 rule) → modules are already loosely coupled →
later extraction is a small change, not a rewrite. This is the **Strangler Fig** path:
start monolith, extract a service only when a real signal fires.

## Anti-pattern to name out loud: the DISTRIBUTED MONOLITH
Services that are still chatty + tightly coupled + share a DB + deploy together = worst of
both worlds (network pain AND coupling). Naming this is a senior signal.

## If forced to extract the first service later (classic follow-up)
1. **Notifications** — async, generic, fault-isolated, no shared transaction → easiest/safest first.
2. **Catalog/Search** — independent read scaling, wants a different store (search index).
3. **Lending stays last** — transactional heart; splitting it is most expensive (sagas).

## Self-check
1. Give the back-of-envelope that proves LMS needs no distribution.
2. List 3 things you lose the moment you split a monolith.
3. Name the 5 signals that justify a split — which (if any) apply to LMS?
4. What is a "distributed monolith" and why is it the worst outcome?
5. If LMS grew 1000×, which service would you extract first and why?
