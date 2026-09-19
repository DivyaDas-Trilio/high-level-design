# Chapter 3 — REST That Survives Production

*Building Blocks · Topic 05 (Client–Server & Protocols) · Chapter 3 of 9*

> **Assumed, not re-taught:** HTTP methods, safe vs idempotent semantics, the status-code
> families and the retry decision table are already written up in
> [`basic_networking/.../http11-methods-idempotency.md`](basic_networking/docs/02-osi-model/07-application/http11-methods-idempotency.md)
> and [`.../http11-status-codes.md`](basic_networking/docs/02-osi-model/07-application/http11-status-codes.md).
>
> This chapter is about the four things that decide whether an API is still workable at ten
> million users: **how you paginate, what you return when half of it failed, how idempotency
> is actually implemented, and how you change a contract you cannot redeploy the other side
> of.** None of these are REST-style questions. All of them are why APIs become unfixable.

---

## 3.1 The problem

Nobody's API dies of bad naming. They die of decisions that were free at 100 users and are
unpayable at 10 million:

```http
GET /api/getOrders?user_id=8412&page=5000&per_page=20&include_total=true
```

```json
200 OK
{
  "orders": [ … 20 items … ],
  "total": 4821993,
  "recommendations": [],
  "status": "ok"
}
```

Six failures are already load-bearing here, and every one of them is now a migration rather
than a fix:

| What you see | What it costs you later |
|---|---|
| `page=5000` | The database scans and discards 100,000 rows per request — **and the results are wrong** under concurrent writes |
| `include_total=true` | `COUNT(*)` over ~5M filtered rows on every page load |
| `user_id=8412` | Sequential primary key: enumerable, and welded to one database's identity scheme |
| `recommendations: []` | The recommendations service timed out. The client cannot tell that from "no recommendations." |
| `200 OK` + `"status": "ok"` | Two sources of truth for success. Clients will branch on the wrong one |
| `getOrders` | Cosmetic. Genuinely the least of the problems |

That ranking is the point of the chapter. The verb-in-the-URL is the thing code reviews catch;
the pagination strategy is the thing that pages you at 3am and cannot be changed without
breaking every client.

## 3.2 Resource modelling: and where the rule should be broken

Resources over RPC is a good default. It is also over-applied by people who have never had to
authorize or audit the result.

### The state-machine test

Two ways to cancel an order:

```http
PATCH /orders/8412          {"status": "cancelled"}     ← the client picks the transition
POST  /orders/8412/cancel   {"reason": "customer_req"}  ← the server owns legal transitions
```

The first is "more RESTful" and worse in four concrete ways:

1. **It invites illegal transitions.** `shipped → cancelled`? `cancelled → pending`? The client
   now proposes state changes and the server must validate every pair — a matrix that grows
   quadratically and is easy to leave a hole in.
2. **Authorization gets harder.** "Who may cancel an order" is one clean rule. "Who may PATCH
   which values of which field" is a policy engine.
3. **Auditing loses intent.** `POST /cancel` with a reason records *why*. A status write
   records only *what*.
4. **It cannot carry side-effect parameters.** Cancelling needs a reason, a refund decision, a
   notification flag. Those aren't properties of the order.

> **Model the state machine, not the table.** If a field's transitions are constrained, do not
> expose it as writable — expose the transitions as operations. Actions are not a REST
> violation; they are how you keep an invariant in one place.

The same reasoning legitimises the other classic escape hatches: search (`POST /search` with a
body, because query strings have length limits and search isn't a resource), batch operations,
and anything genuinely procedural. Resource-shaped where the data is resource-shaped;
operations where the domain has operations.

### Identifiers: never expose the primary key

```
/users/8412        ← sequential integer PK
/users/01HQ3M...   ← ULID / UUIDv7 (RFC 9562)
```

Three separate problems with the first, and the third is the one people miss:

1. **Enumeration.** `8412` tells an attacker that `8411` and `8413` exist. It also leaks your
   growth rate — competitors have measured signup volume by watching sequential IDs.
2. **Coupling to one database's identity.** You cannot shard, merge tenants, or migrate to a
   new store without either rewriting IDs (breaking every client and every stored reference)
   or maintaining a translation table forever.
3. **It forecloses on cursor pagination.** A *time-ordered* opaque ID (UUIDv7, ULID) doubles as
   a stable sort key. A random UUIDv4 does not, and a sequential int ties you to the DB.
   §3.3 depends on this choice, which is why it has to be made on day one.

### Chattiness is an API design problem, not a network problem

Chapter 1's lever 4: a mobile screen firing 8 sequential calls at 200 ms RTT spends 1.6
seconds in round-trips, and no infrastructure change fixes it. The API-side answers are
compound resources (`GET /orders/8412?include=items,customer,shipment`), purpose-built
endpoints for specific screens, and — when the combinations explode — the client specifying
its own shape, which is Chapter 5's GraphQL.

Pick one deliberately. The failure mode is having all three, inconsistently.

## 3.3 Pagination: the decision that cannot be undone

This is the section that earns the chapter. Nothing else in an API is so cheap to get wrong and
so expensive to change.

### Offset pagination is O(offset), not O(limit)

```sql
SELECT * FROM orders WHERE user_id = $1
ORDER BY created_at DESC
LIMIT 20 OFFSET 100000;
```

The database cannot skip to row 100,000. It walks the index, produces 100,020 rows, discards
100,000, and returns 20. The cost of a page is proportional to **how deep it is**, not how big
it is:

| Offset | Rows touched | Illustrative latency |
|---:|---:|---:|
| 0 | 20 | ~1 ms |
| 1,000 | 1,020 | ~5 ms |
| 100,000 | 100,020 | ~200 ms |
| 1,000,000 | 1,000,020 | ~2 s (or a timeout) |

Two consequences that follow immediately:

- **Deep pagination is a DoS vector.** `?page=500000` is a cheap request that buys an expensive
  query. Unbounded offset on a public endpoint is an open invitation, and it is a favourite in
  security reviews.
- **Your p99 is defined by your deepest paginator**, not your typical one. One crawler walking
  to page 40,000 sets the tail latency everyone else's dashboards show.

### And it is *incorrect*, which is the part people skip

Performance is the famous problem. Correctness is the disqualifying one.

Offsets address positions in a result set that is **shifting underneath the client**:

```
t=0   client reads page 1 (rows 1–20 by created_at DESC)
t=1   three new orders are created
t=2   client reads page 2 (OFFSET 20)
      → rows that were 18,19,20 have shifted to 21,22,23
      → the client sees them AGAIN (duplicates)
      → and never sees what got pushed past its window (skips)
```

On a feed, "new items keep arriving at the top" is the *normal* case, so offset pagination is
permanently wrong on exactly the workload people most often use it for. Duplicated and missing
items in a paginated export is a data-integrity bug that will be reported as "the report is
wrong" and take a week to trace back to the API.

### Cursor (keyset) pagination

```sql
SELECT * FROM orders
WHERE user_id = $1
  AND (created_at, id) < ($2, $3)      -- the cursor: last row of the previous page
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

`O(limit)`, an index seek rather than a scan, constant cost at any depth, and **stable under
concurrent writes** — the cursor names a *row*, not a position, so newly inserted rows cannot
shift it.

**The tiebreaker is not optional, and it is what interviewers probe.** `created_at` alone is not
unique — two orders created in the same millisecond straddle a page boundary and one of them is
silently dropped forever. The sort key must be a tuple ending in something unique, and the
index must match it:

```sql
CREATE INDEX idx_orders_user_created ON orders (user_id, created_at DESC, id DESC);
```

If the ORDER BY and the index disagree on direction or column order, you are back to a sort of
the whole partition and the whole exercise was pointless.

### Make cursors opaque, always

```
"next_cursor": "eyJ2IjoxLCJjIjoiMjAyNi0wOS0wOVQxMDoxNTowMFoiLCJpIjoiMDFIUTNNIn0"
```

Base64 of `{"v":1,"c":"2026-09-09T10:15:00Z","i":"01HQ3M"}`. Not for secrecy — for freedom.
The moment you expose `?after_created_at=…&after_id=…`, clients parse it, construct it, and
store it, and you can never change your sort key again. The `v` field is what lets you migrate
cursor formats without breaking in-flight pagination.

Sign it if a forged cursor could leak data across tenants — it is user-controlled input that
goes into a WHERE clause.

### Total counts are a scalability trap

`COUNT(*)` over a large filtered set is `O(n)` and cannot be indexed away in the general case.
"Showing 1–20 of 4,821,993" costs more than the page itself.

| Option | When |
|---|---|
| **Omit it** | Feeds, timelines, search — nobody needed the number, a designer assumed it |
| **Cap it** — "10,000+" | UIs that want a sense of scale. Count `LIMIT 10001` and say "+" |
| **Approximate** — `reltuples`, HLL | Dashboards, analytics; document that it's an estimate |
| **Precompute** — counter table | Genuinely required exact counts on hot paths; now you own invalidation |

The honest trade: cursor pagination gives up "jump to page 500" and cheap totals. For feeds and
timelines that is free — nobody jumps to page 500 of a feed. For an admin table with page
numbers, you either keep offset (bounded to a few hundred pages, with a hard cap) or change the
UI. **Deciding this from the access pattern instead of the default is the whole skill.**

| | Offset | Cursor / keyset |
|---|---|---|
| Cost of page *n* | O(offset) | **O(limit)** |
| Correct under writes | **No** — dupes and skips | **Yes** |
| Jump to arbitrary page | Yes | No |
| Cheap total count | No (separate COUNT) | No |
| Works across shards | Badly | With a global sort key or per-shard cursors |
| Right for | Bounded admin tables | **Feeds, exports, APIs, anything large** |

Sharding note, because it comes up: a cursor over a sharded dataset needs either a globally
ordered sort key (time-ordered IDs — hence §3.2) or a composite cursor carrying a position per
shard, with a merge at the API layer. Picking random UUIDs as your PK in year one is what makes
this impossible in year three. Topics 01 and 09 return to it.

## 3.4 Partial failure: never return 200 for an incomplete answer

`GET /dashboard` fans out to four services. The recommendations service times out. What do you
return?

The tempting answer — 200 with `"recommendations": []` — is the worst available option, because
**the client cannot distinguish "we failed" from "there are none."** So it caches the empty
list, or renders "no recommendations for you," or worse, writes it back. A silent partial
success corrupts client state; a loud failure does not.

> **The rule: a response the client cannot tell apart from a complete one must not be a 200.**

Three defensible designs:

**1. Fail the whole request** — correct when the parts are not independently useful. Simple,
honest, and often right. Return 503 with `Retry-After`.

**2. Explicit degradation** — return the data you have, and say what is missing:

```json
200 OK
{
  "orders": [ … ],
  "recommendations": null,
  "_partial": [
    { "field": "recommendations", "reason": "upstream_timeout", "retryable": true }
  ]
}
```

`null` (unknown) is not `[]` (known empty) — that distinction is the entire mechanism, and it
only works if you are disciplined about it everywhere.

**3. Per-item status for batch endpoints** — a batch of 100 where 3 fail is not one outcome:

```json
{
  "results": [
    { "index": 0, "status": 201, "id": "01HQ3M…" },
    { "index": 1, "status": 409, "error": { "code": "duplicate_email" } },
    { "index": 2, "status": 201, "id": "01HQ3N…" }
  ]
}
```

Return `200` (the batch operation succeeded; the items have individual outcomes) rather than
reaching for `207 Multi-Status` — 207 is WebDAV (RFC 4918) and most clients and proxies have
no idea what to do with it. And each item needs its own idempotency treatment, or a retry of
the batch re-executes the 97 that worked.

### Deadline propagation

Chapter 1 established that timeouts must shrink as you descend the call stack. The mechanism
for enforcing it is passing the **remaining budget** downstream, not a fixed per-hop timeout:

```
client        deadline = 2000 ms
 └─ gateway   spent 50 ms  → passes "1950 ms remaining"
     └─ svc-A spent 200 ms → passes "1750 ms remaining"
         └─ svc-B sees 1750 ms and knows not to start a 3-second query
```

gRPC has this natively (`grpc-timeout`); over REST you carry a header. Without it, every hop
optimistically starts work on a request whose client gave up long ago — which is how an
overloaded system spends 100% of its capacity producing responses that nobody reads, and
cannot recover without shedding load. **Deadline propagation is the difference between a
system that degrades and one that collapses.**

### Errors need a machine-readable code

Adopt **RFC 9457 Problem Details** (formerly RFC 7807) or something isomorphic:

```json
409 Conflict
Content-Type: application/problem+json
{
  "type": "https://api.example.com/problems/insufficient-funds",
  "title": "Insufficient funds",
  "status": 409,
  "detail": "Account 01HQ3M has 420 USD; the transfer requires 500 USD.",
  "instance": "/transfers/01HQ8P",
  "code": "insufficient_funds",
  "balance": "420.00"
}
```

The non-negotiable part: **a stable machine-readable `code`, separate from the human message.**
The instant a client branches on `detail`, that prose is a public API and you can never
reword it — including fixing a typo, or translating it.

## 3.5 Idempotency, actually implemented

`basic_networking` establishes *why* idempotency keys exist. Here is what it takes to make one
correct, because the naive version has three bugs.

```http
POST /payments
Idempotency-Key: 7c9e6679-7425-40de-944b-e07fc1f90ae7
{"amount": "500.00", "currency": "USD", "to": "01HQ3M"}
```

### The dedup record must store the response

```
key → (request_fingerprint, status_code, response_body, created_at, state)
```

Storing only "seen this key" is the classic bug: the retry gets a 200 with an empty body, or a
409, and the client — which never received the first response — still does not know the payment
id. **You must replay the original response**, byte for byte.

### Fingerprint the request body

Same key, different body, is a client bug — and if you ignore it you return the *first*
payment's response for a *second*, different payment. The client believes a $2,000 transfer
succeeded when a $500 one did.

```
same key + same fingerprint  → replay the stored response
same key + different body    → 422 Unprocessable Entity ("key reused with different payload")
```

### Two concurrent requests with the same key

The genuinely hard case, and the one interviews go to. Double-click, or a client retrying on a
timeout while the first request is still running. A check-then-act read is a race — both see
"no record" and both charge.

You need atomic claim-or-lose, at the database:

```sql
INSERT INTO idempotency_keys (key, fingerprint, state)
VALUES ($1, $2, 'in_progress')
ON CONFLICT (key) DO NOTHING
RETURNING key;
```

No row returned means somebody else owns it. Then: return **409** with `Retry-After: 1` if
their attempt is still `in_progress`, or replay the stored response if it has completed. A
unique constraint is your lock — cheaper, more reliable, and less to go wrong than a
distributed lock (Topic 15 covers why reaching for Redlock here would be the wrong instinct).

### Where it lives, and why not the gateway

Tempting to put dedup in the API gateway. Wrong, and the reason is the useful part:

> **The dedup record and the side effect must commit in the same transaction.** Otherwise you
> get the dual-write problem: charge succeeds, dedup write fails, retry charges again. A
> gateway cannot participate in your database transaction.

So it lives in the service, in the same database as the effect. When the effect *isn't* in your
database — an external payment processor — you are in genuine dual-write territory and need the
outbox pattern (Topics 03 and 14).

### The remaining details

- **Scope keys per (client, endpoint).** A global namespace lets tenant A's UUID collide with
  tenant B's, and lets a client accidentally replay a response across endpoints.
- **TTL.** 24 hours is the industry norm (Stripe's). Long enough to cover any retry policy,
  short enough to bound storage. Document what happens after: the key is forgotten and a replay
  executes again.
- **Who generates it.** The client — it must be stable across *its* retries, so the server
  cannot mint it.

## 3.6 Evolving a contract you cannot redeploy

The constraint that makes API design hard: a mobile app from two years ago is still installed,
still calling, and you cannot force an upgrade. Web you can redeploy; internal services you can
coordinate; mobile and third-party integrations you cannot.

### The compatibility matrix

> **You may add. You may not remove, and you may not change meaning.**

| Change | Compatible? | Why |
|---|---|---|
| Add an optional response field | ✅ | Old clients ignore unknown fields — *if* their parser is lenient |
| Add an optional request field with a default | ✅ | Old clients omit it |
| Add a new endpoint | ✅ | |
| **Add a value to a response enum** | ⚠️ **usually breaks** | Clients switching exhaustively hit the default branch — or crash |
| Make an optional request field required | ❌ | Old clients omit it |
| Tighten validation | ❌ | Payloads that worked now 400 |
| Change a default value | ❌ | Silent behaviour change for clients relying on it |
| Rename a field | ❌ | Removal plus addition |
| Change a type (`"5"` → `5`) | ❌ | Even int → string breaks strict parsers |
| Change pagination style | ❌ | Stored cursors and page loops break |

**The enum row is the one that bites people who thought they were being careful.** Adding
`order.status = "partially_refunded"` is additive by every intuition and breaks any client with
an exhaustive switch or a strict deserialiser. Two defences: document at v1 that clients **must
tolerate unknown enum values** (making it part of the contract, so breakage is their bug), and
prefer open string sets over closed enums for anything that might grow.

### Versioning, and the liability of versions

Path versioning (`/v1/`, `/v2/`) is the pragmatic default: visible in logs, routable at the
load balancer, trivially cacheable, obvious in a bug report. Header and media-type versioning
are more "correct" and harder to debug and cache. Not worth the fight.

The part that actually matters:

> **Every version you ship is a code path you maintain forever.** Two versions is not twice the
> work — it is twice the surface for every future change, every security fix, and every
> migration. Aim for one, plus additive evolution.

### Deprecation as a process, not an announcement

Nobody migrates because you sent an email. What works, in order:

1. **Instrument usage per client per version.** You cannot deprecate what you cannot measure.
   Most organisations cannot answer "does anyone still call v1?", which is why v1 is immortal.
2. **Signal it in the protocol** — a `Deprecation` header, and `Sunset` (RFC 8594) carrying the
   date it stops working. Machine-readable, so client telemetry can surface it.
3. **Contact the top callers directly.** The distribution is always long-tailed: five clients
   are 95% of the traffic.
4. **Brownouts.** Return 410 Gone for the deprecated endpoint for 1 minute, then 5, then an
   hour, on an announced schedule. Deliberately breaking it briefly is the only thing that
   reliably gets it onto someone's sprint. Ugly, effective, and standard practice at scale.
5. **Then remove it.**

### Field-level telemetry, and contract tests

Two practices that decide whether step 1 is even possible:

- **Log which fields clients actually read.** Trivial for GraphQL (the query says so), harder
  for REST — you get there via sparse-fieldset params (`?fields=`), or by shipping a field and
  watching for complaints, which is not a strategy. Without this, "is anyone using
  `legacy_address`?" is unanswerable and the field is permanent.
- **Consumer-driven contract testing** (Pact and friends): each consumer publishes the subset
  of the contract it depends on; the provider's CI verifies all of them before merge. This
  converts "we didn't know anyone parsed that" from a production incident into a failed build —
  which is the entire value proposition.

## 3.7 Collections at scale: filtering, sorting, sparse fields

Two failure modes worth naming, both of which start as a helpful feature request.

**Unbounded filter and sort combinations are unindexable.** "Let clients filter on any field
and sort by any field" is `n × m` query shapes, and you cannot index them all — so most
requests become sequential scans, discovered when one customer's dashboard takes the database
down. **Whitelist** the filterable and sortable fields, and make each one's index a deliberate
decision traceable to an access pattern. (This is exactly the discipline in
[`library_db_design` step 8](../../databases/library_db_design/step-08-indexing-strategy.md):
every index justified by a named access pattern, and the discipline of *refusing* the others.)

**Rate limit by cost, not by count.** A `GET /orders/{id}` and a `POST /search` with a
seven-way filter are not the same request, and giving them the same bucket means either the
cheap endpoint is throttled pointlessly or the expensive one is unprotected. Weight requests by
expected cost. Topic 08 builds this out properly.

## 3.8 Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Page 5,000 times out; p99 owned by one crawler | Offset pagination | Cursor pagination; hard-cap any remaining offsets |
| Export has duplicate and missing rows | Offset pagination under concurrent writes | Cursor pagination — this is a correctness fix, not a perf one |
| Pagination silently drops rows at page boundaries | No unique tiebreaker in the sort key | Sort on `(ts, id)`; index must match order and direction |
| Cannot change the sort key ever | Cursors exposed as readable parameters | Opaque, versioned cursors |
| Every page load is slow, not just deep ones | Unconditional `COUNT(*)` | Drop it, cap it, or approximate it |
| Client caches an empty list that was really a failure | 200 with `[]` on partial failure | `null` + explicit `_partial`; never 200 for an indistinguishable response |
| Overloaded system never recovers | No deadline propagation; work continues after clients gave up | Pass remaining budget per hop; shed on expiry |
| Retried batch re-executes the items that succeeded | Idempotency at batch level only | Per-item idempotency keys |
| Double charge on double-click | Check-then-act on the idempotency key | `INSERT … ON CONFLICT DO NOTHING`; 409 while in progress |
| Retry returns 200 with no payment id | Dedup stored the key but not the response | Store and replay the full original response |
| Wrong response returned for a different payload | No request fingerprint | Fingerprint the body; 422 on mismatch |
| Charge succeeded, dedup lost, retry charged again | Dedup outside the effect's transaction | Same transaction; outbox if the effect is external |
| Old mobile clients crash after a "safe" release | New enum value | Document unknown-value tolerance; prefer open string sets |
| v1 is immortal | No per-client version telemetry | Instrument, `Sunset`, contact top callers, brownout |
| One customer's dashboard takes down the DB | Unbounded filter/sort combinations | Whitelist; index per named access pattern |

## 3.9 FAANG interview angle

### The question they actually ask

"Design the API for a user's activity feed."

Ninety percent of answers produce `GET /feed?page=1&limit=20` and move on. That single choice
is the whole signal, and a staff-level answer volunteers the reasoning before being asked:

> "I'd use cursor pagination, not offset. Offset is O(offset) — page 5,000 makes the database
> produce and discard 100,000 rows, and deep pagination becomes a cheap DoS. But the
> disqualifying problem is correctness: a feed has items arriving at the top constantly, so
> offsets address positions in a shifting result set and clients get duplicates and skips.
>
> So the cursor is a tuple — `(created_at, id)` — because `created_at` alone isn't unique and
> ties would silently drop rows at page boundaries. Index is `(user_id, created_at DESC, id
> DESC)` to match the ORDER BY exactly. I'd return it base64-encoded and versioned so I can
> change the sort key later without breaking in-flight clients.
>
> I'd also drop the total count — `COUNT(*)` over the feed is O(n) and nobody scrolling a feed
> needs it. And I'd want time-ordered IDs, ULID or UUIDv7, both so the cursor works and so we
> aren't welded to one database's sequence when we shard."

That answer demonstrates cost analysis, a correctness argument, the tiebreaker detail, index
alignment, forward compatibility, and a foreseen scaling constraint — from one endpoint.

### The probes

| Probe | What they want |
|---|---|
| "Why is page 5,000 slow?" | O(offset): produce-and-discard. And the correctness bug matters more |
| "Sort by `created_at` only — what breaks?" | Same-timestamp ties straddle page boundaries; rows silently dropped |
| "Client wants page numbers" | Bounded admin table → capped offset. Feed → change the UI. Decide from the access pattern |
| "Cursor across 16 shards?" | Global time-ordered sort key, or composite per-shard cursor + merge |
| "One of four downstreams timed out — what do you return?" | Never 200-with-`[]`. `null` + explicit partial, or fail whole. The client must be able to tell |
| "Prevent a double charge on retry" | Idempotency key + fingerprint + `ON CONFLICT DO NOTHING` + store/replay the response + same transaction as the effect |
| "Two identical requests arrive simultaneously" | The race. Unique constraint as the lock; 409 while in progress |
| "Why not put dedup in the gateway?" | It can't join the effect's transaction → dual-write → double charge |
| "How do you remove a response field?" | You can't, until you can measure who reads it. Telemetry → `Sunset` → contact top callers → brownout |
| "Is adding an enum value backwards-compatible?" | Usually **no**. Exhaustive switches and strict parsers break |
| "System is overloaded and won't recover" | No deadline propagation — capacity spent on abandoned requests |

### Red flags

- **Offset pagination for a feed**, with no mention of correctness.
- **Returning a total count unconditionally.**
- **200 for a partial failure** — the single most consequential mistake on this list, because it
  corrupts client state instead of surfacing.
- **`PATCH /orders/{id} {status}`** for a constrained state machine.
- **Sequential integer IDs in public URLs.**
- **Bumping to `/v2/` for an additive change** — betrays not knowing what actually breaks.
- **"Idempotency keys"** as a two-word answer with no fingerprint, no concurrency story, and no
  transaction boundary.

---

## What we produced in Chapter 3

1. **A ranking of API mistakes by cost to fix** — pagination and partial-failure semantics
   dominate; verb-in-URL is cosmetic.
2. **The state-machine test** for when an action endpoint beats a resource PATCH: illegal
   transitions, authorization, audit intent, side-effect parameters.
3. **The offset-vs-cursor analysis**, including the correctness argument that matters more than
   the performance one, the mandatory tiebreaker, index alignment, and opaque versioned cursors.
4. **Total counts as a scalability trap**, with four defensible options.
5. **The partial-failure rule** — never 200 for a response indistinguishable from complete —
   plus `null` vs `[]`, per-item batch status, and deadline propagation.
6. **A correct idempotency implementation**: store the response, fingerprint the body, atomic
   claim via unique constraint, same transaction as the effect, scoped keys, 24h TTL.
7. **The compatibility matrix**, with the enum trap called out, and deprecation as a five-step
   process ending in brownouts.

## Key takeaways (transferable)

1. **The expensive mistakes are semantic, not stylistic.** Nobody's API died of `getOrders`.
2. **Offset pagination's fatal flaw is correctness, not speed.** It addresses positions in a
   result set that moves.
3. **A cursor must name a row, not a position** — and needs a unique tiebreaker, or it silently
   drops data at page boundaries.
4. **Opaque means changeable.** Anything you expose in a readable format, clients will parse,
   and you will never change it. That applies to cursors, IDs, and error strings alike.
5. **`null` is not `[]`.** Unknown and known-empty must be distinguishable, or clients cache
   your outages as facts.
6. **Never return success for a response the client cannot tell apart from a complete one.**
7. **Deadline propagation is what separates degrading from collapsing** — without it, a loaded
   system spends all its capacity on requests nobody is waiting for.
8. **Idempotency means storing and replaying the response**, not remembering the key; and the
   dedup record must commit with the effect or you have rebuilt the double-charge bug.
9. **A unique constraint is usually a better lock than a lock.** Reach for the database's
   atomicity before reaching for coordination.
10. **You can add; you cannot remove or change meaning** — and "additive" enum values are the
    exception that catches careful people.
11. **You cannot deprecate what you cannot measure.** Per-client, per-version, per-field
    telemetry is the prerequisite; everything else is an email nobody reads.

## Principles in play

| Principle | How this chapter applied it |
|---|---|
| **Access patterns before interface** | Pagination style chosen from the read pattern (feed vs admin table), not from a default |
| **One source of truth** | `200` + `"status":"ok"` gave clients two places to check success; the state machine kept transitions in one place |
| **Make the illegal unrepresentable** | Action endpoints instead of a writable `status`, so illegal transitions cannot be expressed |
| **Correctness before performance** | Offset pagination is rejected primarily for producing wrong results, and only secondarily for being slow |
| **Prefer the database's atomicity** | `INSERT … ON CONFLICT` as the idempotency lock rather than distributed coordination |
| **Commit the record with the effect** | Dedup in the same transaction — the dual-write problem is why the gateway is the wrong home |
| **Opaque by default** | Cursors, identifiers, and error codes designed for future change rather than present convenience |
| **Bound the work a client can request** | Capped offsets, whitelisted filters, cost-weighted limits — all bounding server work per unit of client effort *(Ch. 2)* |
| **Timeouts shrink down the stack** *(Ch. 1)* | Implemented concretely as deadline propagation carrying the remaining budget |
| **You cannot manage what you do not measure** | Version and field telemetry as the precondition for any deprecation |

---

*Next — Chapter 4: gRPC & Protocol Buffers. The IDL and wire format, the four streaming modes,
deadlines as a first-class concept, schema evolution rules that are genuinely stricter than
REST's — and load balancing gRPC, which is where Chapter 2's law comes due.*
