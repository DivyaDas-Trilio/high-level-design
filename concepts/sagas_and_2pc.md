# Sagas & 2-Phase Commit (intuition pass)

> Introduced here when `borrow()` first needs it (Module 00 Step 2). DECISION + DESIGN
> deep-dive happens in Module 00 Step 4 (cross-service transactions) and Step 5 (events).

## The problem
In a monolith, `borrow()` is one ACID transaction — the DB guarantees atomicity (all-or-
nothing) for free:
```
BEGIN; check member<2 loans; mark copy ISSUED; create Loan; COMMIT
```
Split into services (Membership / Inventory / Lending), each with its OWN database, and that
single transaction is gone. No `BEGIN..COMMIT` across separate DBs over the network.

## Option A — 2-Phase Commit (2PC) / distributed transaction
A coordinator asks all participants to "prepare" (lock + vote), then "commit" together.
- ✅ Keeps STRONG consistency.
- ❌ Slow, holds locks, fragile: if coordinator/participant dies mid-way, everyone stays
  locked → low availability. Rarely used at scale.

## Option B — Saga (the industry default)
A sequence of LOCAL transactions, one per service, each with a COMPENSATING transaction
that undoes it. If a later step fails, run compensations backward → logical rollback.
Trades atomicity for **eventual consistency**.

### borrow() as a saga
```
1. Inventory.reserveCopy(copy)    comp → Inventory.releaseCopy(copy)
2. Lending.createLoan(m, copy)    comp → Lending.cancelLoan(loan)
3. Membership.incrementCount(m)   comp → Membership.decrementCount(m)
```
Step 3 fails → cancel loan, release copy → as if borrow never happened.

### Two coordination styles
| | Choreography | Orchestration |
|---|---|---|
| How | each service emits event, next reacts; no central brain | central orchestrator calls each step + tracks state |
| Good for | few steps, loose coupling | complex/many-step flows |
| Downside | logic scattered, hard to see whole flow | orchestrator is a piece to maintain |

## Catches (senior signals)
1. Compensations are NEW actions, not true rollbacks (can't un-send an email → send a correction).
2. No isolation — others can see half-done state mid-saga → use semantic locks / status flags (RESERVED).
3. Every step must be IDEMPOTENT — retries after timeouts must be safe.

## Tutorial-ready model
2PC keeps strong consistency by holding locks (low availability). A saga keeps availability
by accepting temporary inconsistency it later repairs with compensations (eventual
consistency). **It's the CAP trade-off made concrete.** All this complexity is the bill for
splitting `borrow()` across services — which is exactly why "monolith first" wins until a
real signal forces the split.

## Where deep-dived
- Decision (2PC vs saga): Module 00 Step 4.
- Saga orchestration vs choreography (build): Module 00 Step 5.
- Idempotency / exactly-once: Module 09 (ad click aggregator).
- CAP / strong vs eventual theory: Module 06 (Google Docs).
