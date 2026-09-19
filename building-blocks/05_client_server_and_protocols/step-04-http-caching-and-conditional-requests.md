# Chapter 4 — HTTP Caching & Conditional Requests

*Building Blocks · Topic 05 (Client–Server & Protocols) · Chapter 4 of 11*

> **Scope.** This is caching *in the protocol* — the four caches already sitting on your request
> path, driven by response headers you are probably not setting. It is not Redis, eviction
> policies, or cache-aside patterns; those are **Topic 02**, and they are a *different* cache
> that you write code to use. The distinction matters because the free one is usually bigger,
> and teams reach for the expensive one first.
>
> Read alongside Chapter 1 (RTT physics — caching is lever 5, "move work off the path") and
> [`basic_networking/.../http11-status-codes.md`](basic_networking/docs/02-osi-model/07-application/http11-status-codes.md)
> for the 304 mechanics. The reference RFCs are **9111** (HTTP Caching) and **9110** (semantics).

---

## 4.1 The problem

A product API. **50,000 rps**, and 95% of it is for the same ~200 popular products. The
database sits at 80% CPU. The proposal on the table is a Redis cluster: three nodes, a
cache-aside layer in every service, a new failure domain, and two sprints.

Nobody has checked whether the response is *already* cacheable. It is. The fix is one header,
zero new infrastructure, and it removes ~99% of origin traffic — arithmetic in §4.2.

Now the other failure, from a team that *did* add caching:

```http
Cache-Control: public, max-age=300
```

…on `GET /me/orders`. It went through a shared CDN. Users started seeing **each other's
orders**. The cache keys on URL; the identity was in a header that isn't part of the key; and
`public` explicitly told the shared cache it was allowed.

Both failures — the untaken free win and the data leak — come from the same gap: not knowing
what the caches on the path key on and obey. That is the whole chapter.

## 4.2 Example first: you already have four caches

Every HTTP response passes through up to four caches. You do not install them. You only get to
tell them what to do.

```
client ──▶ browser cache ──▶ CDN / edge ──▶ reverse proxy ──▶ your app ──▶ DB
           (private)         (shared)       (shared)          (Topic 02)
```

| Cache | Shared? | Can you purge it? | TTL scale | Blast radius of a mistake |
|---|---|---|---|---|
| Browser / client | private, per user | **No. Never.** | seconds → a year | Stuck until TTL expires. Unrecoverable |
| CDN / edge | **shared across all users** | Yes, seconds–tens of seconds | seconds → days | **Cross-user data leak** if keyed wrong |
| Reverse proxy (nginx, Varnish) | shared | Yes, fast | seconds → hours | Same as CDN, smaller footprint |
| Application (Redis) | you decide | Yes, instantly | anything | Contained — it's your code |

> **HTTP caching is the only cache you get at four layers simultaneously from one header — and
> the blast radius is asymmetric.** You can fix Redis in a deploy. You cannot reach into a
> browser cache, ever. So the header is a promise you cannot retract, and it is worth more
> care than a `SET` call.

### The origin-load arithmetic, and the multiplier people miss

Naive model: 50,000 rps × 5% miss rate = 2,500 rps to origin. Wrong in both directions, and
the real model is more useful:

```
origin_rps  ≈  (distinct cacheable objects × PoPs that hold them) ÷ TTL_seconds
```

Each edge location caches independently, so each one fetches each object once per TTL:

```
200 objects × 50 PoPs ÷ 60 s  =  167 rps to origin
```

**50,000 → 167. A 99.7% reduction, from `Cache-Control: s-maxage=60`.**

But read the formula again: origin load is driven by **PoP count**, not by user traffic. Doubling
your traffic changes nothing; adding 50 more PoPs doubles your origin load. That is
counter-intuitive and it is why **tiered caching / origin shield** exists (§4.8) — insert a
regional tier so the multiplier becomes shields, not edges:

```
200 objects × 4 shields ÷ 60 s  =  13 rps
```

Compare that to two sprints of Redis work. **Check whether the response is HTTP-cacheable
before designing a cache.** This is the highest return-on-effort work available in most
read-heavy APIs, and it is routinely skipped because it isn't a project.

## 4.3 Two models of freshness

HTTP gives you two independent mechanisms. Most people know one and half of the other.

### Expiration — "don't ask, just serve"

```http
Cache-Control: max-age=300
```

The cache serves from storage for 300 seconds **without contacting your origin at all**. Zero
latency, zero origin load. The cost: for those 300 seconds you have no control. You cannot
un-publish, correct, or take back the response.

### Validation — "ask, but cheaply"

```http
# first response
200 OK
ETag: "v7-8412"
Cache-Control: max-age=0, must-revalidate

# next request
GET /products/8412
If-None-Match: "v7-8412"

# response
304 Not Modified          ← no body
```

Still a full round-trip (so you still pay Chapter 1's RTT), but the body isn't transferred. On
a 200 KB response over a distant link that is the difference between 600 ms and 200 ms.

**The caveat nobody states, and it is the important one:**

> **A 304 saves bandwidth. It only saves *compute* if your ETag is cheaper to produce than the
> body.**

If your ETag is a hash of the rendered response, you ran every query and serialised everything
to discover you could have sent 304. You saved the network and nothing else. To make
validation save real work, derive the ETag from a **cheap version marker**:

- the row's `updated_at` or a `version` counter — one indexed lookup
- a per-entity version bumped on write (`product:8412:v` in Redis)
- an aggregate version for collections — `MAX(updated_at)` over the page, if indexed

### They compose

```http
Cache-Control: max-age=60, must-revalidate
ETag: "v7-8412"
```

Free for 60 seconds; after that, validate — and a 304 refreshes freshness for another 60. This
is the sensible default for most read APIs: bounded staleness, cheap refresh.

## 4.4 The directives that matter

Precise semantics, because two of these are the source of most caching bugs:

| Directive | Means |
|---|---|
| `max-age=N` | Fresh for N seconds — in **both** private and shared caches |
| `s-maxage=N` | Fresh for N seconds in **shared caches only**; overrides `max-age` there |
| `private` | Browser may store; **shared caches must not.** The correctness directive for authenticated APIs |
| `public` | Shared caches may store it **even when they otherwise wouldn't** — e.g. despite an `Authorization` header |
| `no-cache` | **May store, must revalidate before every use.** Does *not* mean "don't cache" |
| `no-store` | Do not write it anywhere. For secrets and PII |
| `must-revalidate` | Once stale, never serve without validating — no serving stale on error |
| `immutable` | Do not revalidate even on an explicit reload. Only for content-addressed URLs |
| `stale-while-revalidate=N` | Serve stale up to N s **while refreshing in the background** (RFC 5861) |
| `stale-if-error=N` | Serve stale up to N s **if the origin is failing** (RFC 5861) |

### `no-cache` is the most misnamed thing in HTTP

`no-cache` means *store it, but check with me before using it.* `no-store` means *don't write
it down.* Reaching for `no-cache` to protect a sensitive response leaves it on disk in every
proxy on the path. This is a reliable interview probe precisely because so many people have it
backwards.

### The two combinations worth memorising

```http
Cache-Control: max-age=0, s-maxage=300
```
Don't cache in the browser (so a reload is always current), but cache at the CDN for 5 minutes.
The workhorse for HTML and public API responses.

```http
Cache-Control: public, max-age=31536000, immutable
```
One year, never revalidate. **Only** valid for a content-addressed URL (`/app.a3f9c1.js`) —
where the URL changes when the content does, so it can never be wrong. §4.7.

### Two more headers you need for debugging

- **`Age`** — how many seconds a shared cache has held this response. `Age: 240` with
  `s-maxage=300` means 60 seconds of freshness left.
- **`X-Cache: HIT|MISS`** (non-standard, near-universal) — vendor-specific but the first thing
  to check. If you can't see hit/miss per request, you cannot tune anything.

### If you send no `Cache-Control` at all, you are not safe

Caches may apply **heuristic freshness** (RFC 9111): given a `Last-Modified` and no explicit
directive, a common heuristic is 10% of the age since last modification. A resource modified 10
days ago may be cached for a day.

> **"I didn't set a caching header" does not mean "not cached."** It means you delegated the
> decision. Be explicit on every response — including the ones you don't want cached.

## 4.5 `Vary`: how hit rates silently go to zero

The cache key is:

```
method + URL + the VALUES of every header named in Vary
```

So `Vary` multiplies your cache entries by the *cardinality* of those headers. That cardinality
is the entire story:

| `Vary` value | Distinct variants | Effect on hit rate |
|---|---:|---|
| `Accept-Encoding` | ~3 (gzip, br, none) | Negligible. Necessary and correct |
| `Accept-Language` | ~20 | Noticeable but manageable |
| `Authorization` | one per token | Per-user caching — you almost certainly wanted `private` |
| `User-Agent` | **thousands** | **Hit rate ≈ 0.** The classic disaster |
| `Cookie` | ~one per user | Effectively uncacheable |

`Vary: User-Agent` is the famous one: someone wants to serve mobile and desktop variants, and
User-Agent has thousands of distinct values in the wild, so every user gets their own cache
entry and the CDN becomes an expensive pass-through that still bills you.

`Vary: Cookie` is the *common* one, because frameworks add it automatically the moment you touch
the session. Your API becomes uncacheable and nothing in your code says so.

### The fix: normalise before the cache key

Collapse high-cardinality inputs into low-cardinality ones at the edge:

```
User-Agent: <thousands of strings>   →   device = mobile | tablet | desktop     (3)
Accept-Language: <hundreds>          →   lang = en | fr | de | …                (supported set)
Cookie: <everything>                 →   allowlist only the cookies that change the response
```

Every CDN exposes cache-key control for this — custom cache keys, cookie allowlists,
header normalisation. It converts "uncacheable" into "cacheable with 3 variants."

### The same failure via query parameters

```
/products/8412?utm_source=twitter&utm_campaign=spring
/products/8412?utm_source=email
/products/8412
```

Three cache entries for one resource, because the URL is part of the key. Marketing parameters,
tracking IDs, and client-added cache-busters fragment your cache without changing a byte of the
response.

**Allowlist the query parameters that participate in the cache key** and strip the rest. Also
worth normalising: parameter *order* (`?a=1&b=2` vs `?b=2&a=1`) is two keys in most caches.

## 4.6 Authenticated responses: where caching becomes a security problem

This is the section that turns a performance topic into an incident.

A shared cache keys on **URL**. Identity lives in the `Authorization` header or a cookie —
which is **not in the key** unless you put it there. So:

```http
GET /me/orders
Cache-Control: public, max-age=300     ← catastrophic
```

User A's orders are stored under the key `/me/orders`, and user B requesting the same URL gets
a cache hit. This is OWASP-grade, it has taken down real companies' trust, and the header
reads as innocuous in a diff.

### The rules

1. **Anything user-specific gets `private`.** Non-negotiable default.
2. **Anything sensitive gets `no-store`** — tokens, payment details, PII. Not `no-cache`.
3. **Never rely on `Authorization` to implicitly prevent shared caching.** Behaviour varies by
   implementation, and `public` explicitly overrides it. Be explicit.
4. **Strip `Set-Cookie` from anything cacheable.** A cached response carrying `Set-Cookie` hands
   one user's session to everyone who hits that entry. Some CDNs refuse to cache these; do not
   depend on that.
5. **If you must cache per-user at the edge, identity must be *in* the cache key** — and then
   your hit rate is per-user, so first ask whether it earns the risk. Usually it doesn't.

### The architectural answer: split by cacheability, not by resource

A product page is 90% identical for everyone and 10% personal (your cart count, your
recommendations). Cached as one response, the 10% makes the 90% private.

```
GET /products/8412            → public,  s-maxage=300   ← shared, high hit rate
GET /me/cart-summary          → private, max-age=0      ← tiny, per-user
```

Compose them in the client, or at the edge (edge-side includes / edge functions). This is the
**personalisation-versus-cacheability** trade, and naming it explicitly is what separates a
design from a guess: *every personalised field you fold into a shared response drags the whole
response into the private tier.*

## 4.7 Invalidation: you mostly can't, so design around it

> **A TTL is a promise you cannot retract.** Once a browser holds `max-age=86400`, that
> response is authoritative for a day and nothing you deploy changes it.

Three real strategies, in order of reliability:

### 1. Change the URL (the only invalidation that always works)

```
/static/app.a3f9c1.js     Cache-Control: public, max-age=31536000, immutable
```

The URL is derived from the content, so it *cannot* be stale — new content is a new URL, and
the old entry is simply never requested again. Instant, global, works on browsers you cannot
reach.

The pattern generalises beyond assets: version the URL of anything you want long-lived and
replaceable. If you can express "which version" in the URL, you have solved invalidation.

### 2. Purge by tag (the good CDN mechanism)

Tag each response with the entities it depends on; on write, purge by tag:

```http
# response
Surrogate-Key: product-8412 category-shoes price-list-eu

# on write, one call purges every cached response touching that product —
# the detail page, the category listing, the search results, the sitemap
PURGE key=product-8412
```

This is what lets you run **long TTLs with correct data**, which is the combination you
actually want. Fastly calls them Surrogate Keys, Cloudflare calls them Cache Tags. Without
tags you are stuck purging URLs individually and you will always miss one — typically the
listing page that embeds the object you just changed.

### 3. Purge by URL / prefix / everything

- **By URL** — fast and exact, but you must enumerate every URL the change affects.
- **By prefix or wildcard** — slower, coarse.
- **Purge-all** — nuclear. Every edge misses simultaneously and your origin takes the full
  §4.8 stampede. It is a valid emergency lever and a terrible routine practice.

### Two constraints to state out loud

- **Purge is not instant.** Seconds to tens of seconds to propagate globally. Any "we'll purge
  on write" design has a window; size it and decide if it's acceptable.
- **Browsers cannot be purged.** Whatever you tell a client is final for its TTL. Keep browser
  TTLs short (`max-age=0, s-maxage=N`) unless the URL is content-addressed.

### The decision table

| Content | TTL | Invalidation | Why |
|---|---|---|---|
| Content-hashed assets | 1 year, `immutable` | URL change | Cannot be wrong by construction |
| Reference data (categories, config) | minutes–hours at edge | tag purge | Changes rarely, read constantly |
| Product / price data | 30–300 s at edge + `swr` | tag purge | Bounded staleness is a business decision — go ask |
| Feeds, personalised | `private`, 0–30 s | expiry only | Per-user; not worth edge complexity |
| Anything sensitive | `no-store` | n/a | |

Note the third row: **"how stale can this be?" is a product question, not an engineering one.**
Prices might tolerate 30 seconds; inventory counts might not. Ask, get a number, encode the
number. Guessing is how you end up selling out-of-stock items.

## 4.8 Stampede at the edge

A hot object's TTL expires. Every concurrent request for it misses at once.

```
50,000 rps on one hot object, TTL expires
→ without protection: 50,000 origin requests inside the miss window
→ origin falls over
→ nothing repopulates the cache
→ the retries make it worse
```

This is the same thundering-herd shape as Topic 02's cache stampede, one layer up. Four fixes,
and the first is a single header:

**1. `stale-while-revalidate` — the single best fix**

```http
Cache-Control: s-maxage=60, stale-while-revalidate=600
```

After 60 seconds the object is stale but still served *instantly* while one background request
refreshes it. Nobody ever waits on a cache miss for a popular object, and origin sees one
request instead of 50,000. Pair it with `stale-if-error=86400` and you also get free
availability: your origin can be down for a day and popular content keeps serving.

**2. Request coalescing** — the cache sends **one** request to origin and satisfies all waiters
from it. nginx: `proxy_cache_lock on;`. Varnish and most CDNs do it by default. **Verify
yours does** — the difference between coalescing and not is three orders of magnitude of
origin load on a hot key.

**3. TTL jitter** — if 10,000 objects were populated by the same deploy or crawl, they expire in
the same second. Randomise: `s-maxage = base ± 10%`. Same lesson as Chapter 2's connection-age
jitter, and the same failure if you skip it.

**4. Tiered caching / origin shield** — edges miss to a regional shield; only the shield misses
to origin. This is the fix for §4.2's PoP multiplier: `(objects × PoPs)/TTL` becomes
`(objects × shields)/TTL`. Usually a checkbox, frequently left off.

## 4.9 What's actually cacheable in an API

The framework, by response type:

| Response type | Directive | Notes |
|---|---|---|
| Content-hashed static | `public, max-age=31536000, immutable` | The easy win. Do it first |
| Public reference data | `public, s-maxage=3600, stale-while-revalidate=86400` | + tag purge |
| Public, changing (products, prices) | `public, s-maxage=60, swr=600` | Staleness budget from product |
| Search — head of distribution | `public, s-maxage=60` | Cache popular queries only; long-tail queries pollute the cache with entries read once |
| Collection page 1 | `public, s-maxage=30` | Page 1 is the overwhelming majority of requests |
| Collection, deep pages | rarely worth caching | Long tail; and per Ch. 3, deep offsets shouldn't exist |
| Personalised (feed, recs) | `private, max-age=0` or split per §4.6 | |
| Authenticated user data | `private, max-age=0` | `no-store` if sensitive |
| Mutation responses | `no-store` | And the mutation should purge related tags |

Two practical notes from that table:

- **Cache only the head of a search distribution.** Long-tail queries are requested once, so
  caching them fills the cache with entries that will never hit and evicts things that would
  have. Cacheability should follow request frequency, not endpoint identity.
- **Page 1 is most of your pagination traffic** (Chapter 3). Caching page 1 aggressively and
  ignoring the rest captures nearly all the benefit for almost none of the complexity.

### And the mechanical reason safe methods matter

A `GET` that has a side effect — increments a view counter, extends a session, writes an audit
row — **will be served from cache and stop having that effect.** Not occasionally: for the
whole TTL, at every layer, invisibly.

This is why safe methods are a real constraint rather than REST etiquette. The caches on the
path are *entitled* to assume GET is side-effect free, and they will act on that assumption.
(See
[`basic_networking/.../http11-methods-idempotency.md`](basic_networking/docs/02-osi-model/07-application/http11-methods-idempotency.md)
for the semantics; this is the consequence.)

## 4.10 Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Users see each other's data | `public` on a per-user response through a shared cache | `private`; audit every cacheable response for identity dependence |
| A user's session works for someone else | `Set-Cookie` in a cached response | Strip `Set-Cookie` from cacheable responses |
| CDN hit rate ~0, bills unchanged | `Vary: User-Agent` or `Vary: Cookie` | Normalise to low-cardinality values at the edge |
| Hit rate drops after a marketing launch | `utm_*` params fragmenting the key | Query-param allowlist in the cache key |
| Sensitive data found in a proxy cache | `no-cache` used where `no-store` was meant | `no-store` |
| Stale content served days after a fix | Long `max-age` reached browsers | `max-age=0, s-maxage=N`; content-addressed URLs for long TTLs |
| Origin collapses when a hot object expires | Stampede, no coalescing | `stale-while-revalidate`; enable request coalescing; jitter |
| Origin load scales with PoP count, not traffic | No tiered caching | Origin shield |
| Origin collapses right after a purge-all | Every edge misses simultaneously | Purge by tag, never all |
| 304s everywhere, DB load unchanged | ETag computed from the full rendered body | Derive ETag from a cheap version marker |
| View counts stopped incrementing | Side-effecting GET now served from cache | Move the effect off GET |
| Cached responses appear despite no headers | Heuristic freshness | Set `Cache-Control` explicitly on every response |
| Listing page shows a stale product after an edit | Purged the detail URL, not the pages embedding it | Tag-based purge |

### Seeing it yourself

```bash
# What is the origin actually saying about caching?
curl -sI https://example.com/api/products/8412 \
  | grep -iE 'cache-control|etag|age|vary|x-cache|last-modified'

# Prove a 304: fetch, capture the ETag, re-request conditionally
ETAG=$(curl -sI https://example.com/ | grep -i '^etag:' | tr -d '\r' | cut -d' ' -f2)
curl -s -o /dev/null -w '%{http_code} %{size_download} bytes\n' \
     -H "If-None-Match: $ETAG" https://example.com/
# expect: 304 0 bytes   ← the body never crossed the network

# Watch Age climb across repeated requests (proof it's a shared-cache hit)
for i in 1 2 3; do curl -sI https://example.com/ | grep -iE '^age:|^x-cache:'; sleep 2; done

# Measure the win: cache-buster (forced miss) vs cached
curl -s -o /dev/null -w 'MISS %{time_total}s\n' "https://example.com/?bust=$$"
curl -s -o /dev/null -w 'HIT  %{time_total}s\n' "https://example.com/"

# Find your own uncacheable responses — the audit that finds the free win
#   grep your handlers for responses with no Cache-Control at all,
#   then check which of those are (a) GET, (b) not user-specific.
```

## 4.11 FAANG interview angle

### The question

"This read-heavy API is overloading the database. How do you fix it?"

The expected answer is "add a cache," and nearly everyone gives it — usually with a Redis
diagram. The staff-level answer starts one step earlier:

> "Before adding infrastructure I'd check what's already cacheable at the HTTP layer, because
> that's free and it operates at four levels. If it's 200 hot products with a 60-second
> staleness budget, `s-maxage=60` at the CDN takes origin from 50,000 rps to roughly 200
> objects × 50 PoPs ÷ 60 s ≈ 167 rps. That's 99.7% for one header.
>
> Note the origin load scales with **PoP count**, not user traffic — so I'd turn on an origin
> shield and get it to ~13 rps. And I'd add `stale-while-revalidate` so a hot object expiring
> doesn't send 50,000 concurrent misses at the origin, plus `stale-if-error` for free
> availability.
>
> Two things I'd need before shipping it. First, from product: how stale can this be? That
> number is the TTL, and it's a business decision, not mine. Second, an audit that none of
> these responses are user-specific — a `public` on a per-user response through a shared cache
> is a cross-user data leak, and the header looks harmless in review.
>
> Redis is still worth it for the parts that *aren't* HTTP-cacheable — personalised responses,
> and computed data shared across endpoints. But I'd do the free 99% first."

That answer shows arithmetic, a non-obvious scaling insight, stampede awareness, a security
instinct, and correct sequencing of cheap-before-expensive.

### The probes

| Probe | What they want |
|---|---|
| "`no-cache` vs `no-store`?" | `no-cache` = **may store, must revalidate**. `no-store` = don't write it down. Constantly confused |
| "`max-age` vs `s-maxage`?" | Shared-cache-only override; `max-age=0, s-maxage=300` is the workhorse |
| "We set `Vary: User-Agent` and hit rate went to zero" | Cardinality: thousands of variants. Normalise to `device` |
| "Does a 304 reduce database load?" | **Only if the ETag is cheaper than the body.** Otherwise bandwidth only |
| "How do you invalidate a CDN?" | Mostly you don't — you version the URL, or tag+purge. Purge isn't instant; browsers can't be purged at all |
| "Users saw each other's data. What happened?" | `public` on a per-user response; shared cache keys on URL, identity isn't in the key |
| "Hot object expires and the origin dies" | `stale-while-revalidate` + request coalescing + TTL jitter + shield |
| "Nothing is cached and no headers are set — safe?" | No. Heuristic freshness. Be explicit always |
| "Cache a personalised product page?" | Split it — shared 90% public, per-user 10% private, composed at edge or client |
| "Why must GET be side-effect free?" | Caches are entitled to assume it and will serve from cache, silently killing the effect |

### Red flags

- **Reaching for Redis before checking HTTP cacheability.** The single most common miss, and it
  costs two sprints to learn.
- **`Cache-Control: no-cache`** believing it prevents storage.
- **Caching authenticated responses in a shared cache** without identity in the key.
- **Purge-all as a routine strategy.**
- **Picking a TTL without asking what the staleness budget is.** It's a product decision;
  inventing it is how you sell out-of-stock inventory.
- **No mention of stampede.** Caching without stampede protection moves the outage rather than
  preventing it.

---

## What we produced in Chapter 4

1. **The four caches already on your path**, what each keys on, and the asymmetry that matters:
   you can purge a CDN, you can never purge a browser.
2. **The origin-load formula** — `(objects × PoPs) ÷ TTL` — and the counter-intuitive finding
   that origin load scales with PoP count, not traffic, which is what motivates origin shields.
3. **Expiration vs validation**, and the caveat that a 304 saves bandwidth but only saves
   compute when the ETag is cheaper than the body.
4. **Precise directive semantics**, with `no-cache` vs `no-store` and the `max-age=0,
   s-maxage=N` workhorse.
5. **`Vary` as a cardinality problem**, plus the query-parameter version, and normalisation as
   the fix.
6. **The authenticated-caching failure mode** as a security bug, and personalisation-versus-
   cacheability as an explicit architectural split.
7. **Invalidation ranked by reliability** — URL change > tag purge > URL purge > purge-all — and
   the fact that a TTL is unretractable.
8. **Edge stampede** and its four fixes, one of which is a single header.
9. **A cacheability framework by response type**, including caching only the head of a search
   distribution and only page 1 of a collection.

## Key takeaways (transferable)

1. **Check for the free cache before designing a paid one.** HTTP caching operates at four
   layers from one header; Redis is code, infrastructure, and a failure domain.
2. **A TTL is a promise you cannot retract.** Long TTLs are only safe on URLs that cannot go
   stale — which means content-addressed ones.
3. **Invalidation you can rely on is a URL change.** Everything else is best-effort with a
   propagation window.
4. **Shared caches key on URL; identity does not live in the URL.** Every caching decision on an
   authenticated endpoint is a security decision.
5. **`Vary` is a cardinality multiplier.** Normalise high-cardinality inputs to small sets
   *before* the cache key, or accept a hit rate of zero.
6. **Silence is a choice.** No `Cache-Control` delegates the decision to heuristics.
7. **Staleness budgets are product decisions.** Ask for the number; don't invent it.
8. **Caching without stampede protection relocates the outage.** The moment content is popular
   enough to be worth caching, it is popular enough to herd.
9. **Personalisation is contagious.** One per-user field drags an entire response into the
   private tier — so split by cacheability, not by resource.
10. **Cacheability should follow request frequency, not endpoint identity.** Cache the head of
    the distribution; the long tail pollutes.

## Principles in play

| Principle | How this chapter applied it |
|---|---|
| **Move work off the path** *(Ch. 1, lever 5)* | Caching is the purest form: the request never reaches the origin |
| **Prefer the free win first** *(Ch. 1)* | One header before a Redis cluster; measure before building |
| **Put a number on every hop** *(Ch. 1)* | `(objects × PoPs) ÷ TTL` turned "add a CDN" into 50,000 → 167 → 13 rps |
| **Bound the blast radius of a mistake** | Browser TTLs kept short precisely because they are unrecoverable |
| **Make the illegal unrepresentable** *(Ch. 3)* | Content-addressed URLs cannot serve stale content — correctness by construction, not by discipline |
| **Correctness before performance** *(Ch. 3)* | `private` is decided before any TTL is tuned |
| **Add jitter to anything synchronised** *(Ch. 2)* | TTL jitter, for the same reason as connection-age jitter |
| **Every efficiency gain has hidden dependents** *(Ch. 2)* | Caching a GET silently removes its side effects |
| **Ask for the requirement instead of inventing it** | The staleness budget comes from product; the TTL merely encodes it |

---

*Next — Chapter 5: asynchronous API surfaces. `202 Accepted` with a status resource, polling vs
webhooks vs SSE, webhook signing and replay protection, delivery guarantees you can and cannot
make, and presigned uploads so file bytes never traverse your API.*
