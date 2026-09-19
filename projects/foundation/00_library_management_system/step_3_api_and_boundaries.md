# Module 00 · Step 3 — API & Service Boundaries

> Turn bounded contexts into CONTRACTS. Design each module's public interface as if it were
> a network API — even in-process — so the seam can be extracted into a real service later
> (Strangler Fig) with zero redesign. You're designing the dotted lines between modules.
> DDD name for this surface: the **Published Language** (small, stable, public; hides the
> rich internal aggregate model — outsiders touch the contract, never your aggregates).

## Two kinds of API (don't conflate)
1. **Public/external** — clients (member app, librarian console) → via **API gateway**
   (auth, rate limit, routing). Use **REST/JSON** (universal).
2. **Internal** — module↔module / service↔service. Borrow flow: **Lending** calls
   **Inventory** + **Membership**. Favor **gRPC** internally (fast, typed, contract-first).

## Design principles (FAANG asks these)
- **Resource-oriented, not RPC** — model nouns (`/books`,`/loans`), verbs via HTTP methods.
- **Action-vs-resource tension** — "borrow" is a verb, but borrowing = creating a Loan →
  `POST /loans`. Return = state transition → `POST /loans/{id}/return`. Action sub-resource
  is the accepted escape hatch when an op isn't pure CRUD.
- **Idempotency** — GET/PUT/DELETE idempotent; POST not. Borrow is a POST that must not
  double-apply on retry → require **`Idempotency-Key` header**.
- **Pagination + filtering** on every list (search, overdue) — never unbounded.
- **Consistent errors + status codes** — 409 Conflict (copy unavailable), 422 (limit exceeded).
- **Versioning** (`/v1/...`) from day one — published contracts are forever.

## API surface by bounded context

### Catalog (Book) — read/search heavy
```
GET    /v1/books?title=&author=&genre=&page=&size=   # search (paginated)
GET    /v1/books/{bookId}
POST   /v1/books            # admin add
PATCH  /v1/books/{bookId}   # admin update
DELETE /v1/books/{bookId}   # admin remove
```
### Inventory (BookCopy) — write-heavy
```
GET    /v1/books/{bookId}/copies                    # availability
POST   /v1/books/{bookId}/copies                    # admin add copies
PATCH  /v1/copies/{copyId} {status: DAMAGED|LOST}   # librarian mark
# internal-only: reserveCopy(copyId) / releaseCopy(copyId)  ← Lending saga
```
### Membership (Member)
```
POST   /v1/members
GET    /v1/members/{memberId}
DELETE /v1/members/{memberId}
```
### Lending (Loan) — transactional core
```
POST   /v1/loans {memberId, copyId} + Idempotency-Key   # BORROW = create loan
POST   /v1/loans/{loanId}/return                         # RETURN = state transition
GET    /v1/loans?status=OVERDUE&page=                    # overdue list (UC-5)
GET    /v1/members/{memberId}/loans
```
### Fines (Fine) — money, strong consistency
```
GET    /v1/members/{memberId}/fines
POST   /v1/fines/{fineId}/payment {amount} + Idempotency-Key
```

## borrow() across boundaries (orchestration)
```
Client → POST /v1/loans {memberId, copyId}   (gateway → Lending)
  Lending orchestrates:
    1. Membership.getActiveLoanCount(memberId)  → enforce ≤ 2
    2. Inventory.reserveCopy(copyId)            → 409 if not AVAILABLE
    3. create Loan (due = +5 days)
    4. on failure → compensate: releaseCopy     ← saga
  → 201 Created { loanId, dueDate }
```
Monolith today: steps 1–3 are in-process calls in ONE DB transaction (atomic, trivial). The
contract is drawn as if remote, so extracting Inventory/Membership later doesn't change the
borrow endpoint — only the call mechanism. That's the payoff of designing boundaries now.

## Async boundary
**Notifications** has NO sync API — it subscribes to domain events (`LoanOverdue`,
`BookReturned`). Keeps it fault-isolated (can be down without blocking borrow). → Step 5.

## Self-check
1. Why design module APIs as contracts even in a monolith?
2. Borrow is conceptually a verb — how do you model it RESTfully, and why?
3. Why does borrow need an Idempotency-Key but a GET search does not?
4. Which status code for "copy not available" vs "member over loan limit"?
5. Why does Notifications get events instead of a synchronous endpoint?
