# 00 — Library Management System (the LLD ↔ HLD Bridge)

> This module is special. It does **not** re-teach the LMS design — you already built a
> full DDD model in `lld/library_management_system_v2`. It teaches the skill almost nobody
> does: **seeing the same system at two altitudes** and mapping LLD → HLD end to end.

## Why LMS is here as Module 00
LMS is a *weak pure-HLD problem* (low scale). Its value is the **bridge**: you own the LLD,
so it's the perfect place to learn how a clean object model becomes a deployable distributed
system — and what *new* problems appear at the network boundary.

## The bridge (LLD concept → HLD concept)
| Your LLD (`lld/`) | Becomes in HLD |
|---|---|
| Bounded contexts (Catalog, Lending, Membership, Fines, Notifications) | **Candidate service boundaries** |
| Aggregates (Book, BookCopy, Member, Loan, Fine) | **Data ownership** — which service owns which DB |
| Repository interfaces | **Actual databases + the API in front of them** |
| Domain events (BookReturned, LoanOverdue) | **Message-queue / event-bus topics** |
| In-process method calls | **Network calls (REST/gRPC) — now with latency & failure** |
| One in-memory transaction | **Distributed consistency / sagas** |

## Step plan
- [x] step_1 — From LLD to HLD: re-reading the domain at altitude
- [ ] step_2 — Monolith first: when LMS should NOT be distributed (senior judgment)
- [ ] step_3 — API & service boundaries
- [ ] step_4 — Data ownership, SQL choice, cross-service transactions
- [ ] step_5 — Events & async (domain events → queue)
- [ ] step_6 — Scaling & deep dive: cache, replicas, search, failure modes

> Pace: one step at a time. Advance when the user says **"next"**.
> Source of truth for the domain: `lld/library_management_system_v2/docs/`.
