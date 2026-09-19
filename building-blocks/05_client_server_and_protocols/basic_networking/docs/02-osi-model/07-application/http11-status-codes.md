# HTTP/1.1 — Status Codes

> **Status:** 🟡 studying · **Lens:** end-to-end + HLD interview
> **Prereqs:** [[http11-methods-idempotency]] (retries depend on both).
> **OSI layer:** Application (L7). **Concept 2 of the HTTP/1.1 essentials.**

## 1. One-liner
The **first digit** classifies the response (2 success · 3 redirect · 4 client
error · 5 server error). The HLD payoff: the code **drives retry, caching, and
failover** decisions.

## 2. The problem it solves
The client needs to know, from the response alone, what happened and what to do
next — succeed, follow a redirect, fix its request, or retry. Status codes encode
that.

## 3. Deep dive

### Families (first digit = who's at fault + retry?)
| Class | Meaning | Fault | Retry? |
|---|---|---|---|
| 1xx | Informational (rare) | — | — |
| 2xx | **Success** | — | done |
| 3xx | **Redirect** — look elsewhere | — | follow `Location` |
| 4xx | **Client error** — request is wrong | client | **No** (except 429/408) |
| 5xx | **Server error** — server failed | server | **Yes**, backoff (idempotent only) |

"4xx = client's fault, 5xx = server's fault" decides *who fixes it* and *whether
to retry*.

### Interview-critical codes
| Code | Name | Means | HLD relevance |
|---|---|---|---|
| 200 | OK | success + body | — |
| 201 | Created | POST made a resource (`Location`) | REST create |
| 204 | No Content | success, no body (e.g. DELETE) | — |
| 301 | Moved Permanently | moved for good | SEO, cached, update links |
| 302/307 | Found / Temp Redirect | temporary | 307 preserves method |
| 304 | Not Modified | "use your cache" | **caching/bandwidth** |
| 400 | Bad Request | malformed | don't retry — fix it |
| 401 | Unauthorized | **who are you?** (auth missing/bad) | authenticate |
| 403 | Forbidden | known, **not allowed** | authorization |
| 404 | Not Found | no such resource | — |
| 429 | Too Many Requests | **rate limited** | back off (`Retry-After`) |
| 500 | Internal Server Error | crash/bug | retry w/ backoff |
| 502 | Bad Gateway | proxy/LB got bad upstream reply | upstream down |
| 503 | Service Unavailable | **overloaded/down** | circuit breaker, `Retry-After` |
| 504 | Gateway Timeout | proxy/LB: upstream too slow | timeout tuning |

Distinctions interviewers probe:
- **401 vs 403:** 401 = authenticate (who are you?); 403 = authenticated but not allowed.
- **502 vs 503 vs 504:** in microservices — 502 upstream refused/garbage, 503
  overloaded/down, 504 upstream too slow. They pinpoint **where** the failure is.

### LIVE DEMOS (captured)
**A) Families** — `curl -s -o /dev/null -w %{http_code} https://httpbin.org/status/CODE`
returned real 200/201/204/301/400/401/403/404/429/500/503.

**B) Redirect chain** (`curl -sIL https://httpbin.org/redirect/2`):
```
HTTP/2 302  → location: /relative-redirect/1
HTTP/2 302  → location: /get
HTTP/2 200
```
3xx carries a `Location`; `curl -L`/browsers re-request it. 301 (permanent) is
cached & affects SEO; 302/307 aren't. Each redirect = an extra round-trip (latency).

**C) 304 Not Modified (caching bridge):**
```
1st GET → 200, etag: v7abc
2nd GET  -H 'If-None-Match: "v7abc"' → 304   (NO body re-sent)
```
Client cached with the **ETag** (version fingerprint); asks "still current?"; server
returns tiny **304** instead of the whole body → big bandwidth/latency win. Full
mechanics in the caching concept.

## 4. HLD payoff: status codes drive retry logic
```
2xx → success, done
3xx → follow Location
4xx → client error → DON'T retry (same bad request)
      └ except 429 → wait Retry-After, then retry
5xx → retry with exponential backoff + jitter
      └ ONLY if the method is idempotent (retried POST double-charges)
429/503 → honor the Retry-After header
```
- **429** = too fast → rate limiting; `Retry-After` says how long to wait.
- **503** = overloaded → circuit breakers/health checks shed load; `Retry-After`.
- **Retry storms:** everyone retrying a 5xx at once amplifies the outage → use
  **exponential backoff + jitter**.

## 5. Hands-on (visualize)
```bash
for C in 200 301 404 429 500 503; do curl -s -o /dev/null -w "$C -> %{http_code}\n" https://httpbin.org/status/$C; done
curl -sIL https://httpbin.org/redirect/2 | grep -iE '^HTTP/|^location:'    # redirect chain
curl -s -o /dev/null -w "%{http_code}\n" -H 'If-None-Match: "v7abc"' https://httpbin.org/etag/v7abc  # 304
```

## 6. Common misconceptions
- **"4xx and 5xx are both 'errors' — retry them."** No — 4xx is *your* fault
  (retrying repeats the bad request); only 5xx/429 are worth retrying.
- **"401 = 403."** 401 = not authenticated; 403 = authenticated but forbidden.
- **"Redirects are free."** Each is a full round-trip; chains add latency.
- **"200 means the app succeeded."** 200 means HTTP succeeded; the body may still
  contain an app-level error (bad API design, but common).

## 7. Diagrams needed
1. The 5 families as a decision tree (fault + retry?).
2. Retry decision flow keyed by status code (+ idempotency gate + backoff).
3. 304 conditional-GET sequence (ETag → If-None-Match → 304).

## 8. Video script outline
- **Hook** — "your service returns 503. Do you retry? What about 429? 400?"
- **Build** — families → the must-know codes → live demos (families, redirect
  chain, 304) → the retry decision table.
- **Payoff** — the code drives retry/caching/failover; retry storms → backoff+jitter.
- **Recap** — first digit = family · 4xx yours / 5xx theirs · retry 5xx/429
  (idempotent) · 304 saves bandwidth.

## 9. Brainstorm / open questions
- Rich HLD thread: retry storms, exponential backoff + jitter, circuit breakers,
  `Retry-After`, health checks (200 vs 503). Own beat?
- 304/ETag is the natural bridge into the Caching concept (#5).

## 10. References
- Live: httpbin.org/status, /redirect, /etag. MDN status codes; RFC 9110.
