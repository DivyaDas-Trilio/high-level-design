# HTTP/1.1 — Methods, Idempotency & Safety

> **Status:** 🟡 studying · **Lens:** end-to-end + HLD interview
> **Prereqs:** [[00-overview]], HTTP fundamentals (request/response anatomy).
> **OSI layer:** Application (L7). **Concept 1 of the HTTP/1.1 essentials.**

## 1. One-liner
The **method** is the action verb in the request line (GET/POST/PUT/PATCH/DELETE…);
**safe** = read-only, **idempotent** = repeating it leaves the same end state. The
HLD payoff: you can safely **retry** idempotent ops (GET/PUT/DELETE) but not POST.

## 2. The problem it solves
Networks drop requests/responses → clients, load balancers, and service meshes
**retry**. Which operations are safe to retry? That question is answered entirely
by safe/idempotent semantics.

## 3. Deep dive

### Methods table (know safe/idempotent cold)
| Method | Purpose | Safe | Idempotent | Cacheable |
|---|---|:--:|:--:|:--:|
| GET | read a resource | ✅ | ✅ | ✅ |
| HEAD | read headers only (no body) | ✅ | ✅ | ✅ |
| OPTIONS | ask what's allowed (`Allow` header) | ✅ | ✅ | ❌ |
| PUT | create/**replace** at a known URI | ❌ | ✅ | ❌ |
| DELETE | remove a resource | ❌ | ✅ | ❌ |
| POST | create/submit (server picks URI) | ❌ | ❌ | ❌ |
| PATCH | **partial** update | ❌ | ⚠️ not guaranteed | ❌ |

- **Safe** = no side effects (read-only). Free to prefetch/cache/retry.
- **Idempotent** = once or N times → **same server state**. (safe ⊂ idempotent;
  PUT/DELETE are idempotent but not safe — they change state, just repeatably.)
- **405 Method Not Allowed** + `Allow:` header = server rejecting the method and
  listing valid ones (your `stage4_router.py`'s "path ok, method wrong → 405").

### Idempotency by example
- PUT `/users/42 {name:X}` ×5 → name still `X`. Same end state. ✅
- DELETE `/users/42` ×5 → gone after 1st; rest 404 but state ("gone") identical. ✅
- POST `/users {name:X}` ×5 → **5 users created**. ❌
- PATCH `/acct {balance:+10}` ×5 → +50. ❌ (depends on the patch)

### LIVE DEMO (captured) — the `count` proves it
Stateful server (`scratchpad/idempotency_demo.py`), same request sent twice:
```
POST /users {alice}  -> {"created_id":1,"count":1}
POST /users {alice}  -> {"created_id":2,"count":2}   ← count GROWS: 2 users. NOT idempotent
PUT  /users/99 {bob} -> {"put_id":"99","count":3}
PUT  /users/99 {bob} -> {"put_id":"99","count":3}    ← count STABLE: 1 user 99. Idempotent
DELETE /users/99     -> {"deleted":true, "count":2}
DELETE /users/99     -> {"deleted":false,"count":2}  ← 404 but end state SAME. Idempotent
```
`count` grows on repeated POST, stays flat on repeated PUT/DELETE — that's
idempotency you can see.

## 4. Why HLD interviews obsess over this: retries
A request can succeed on the server but the **response** get lost → the client
retries. If the op is **non-idempotent**, the retry **duplicates the effect**:
- Retry GET/PUT/DELETE → harmless (same end state). ✅ auto-retry OK.
- Retry POST `/charge {$100}` → **double charge.** ❌ never blindly retry.

→ LBs/clients auto-retry **idempotent methods only**.

### The pattern: Idempotency Keys (make POST retry-safe)
Client sends `Idempotency-Key: <uuid>`; server records it; a retry with the
**same key** returns the **original result** instead of re-executing. Stripe/PayPal
do this for payments. *This is the answer to "how do you prevent double-charging
on retries?"*

### Other ripples
- **Caching:** only **safe** methods (GET/HEAD) are cacheable.
- **REST/API design:** CRUD → Create=POST, Read=GET, Update=PUT/PATCH, Delete=DELETE.

## 5. Hands-on (visualize)
```bash
# method is the request-line verb (httpbin echoes it):
for M in GET POST PUT DELETE PATCH; do curl -s -X $M https://httpbin.org/anything | grep '"method"'; done
# 405 + Allow header:
curl -s -i -X POST https://httpbin.org/get | grep -iE '^HTTP/|^allow:'
# idempotency with real state:
python3 scratchpad/idempotency_demo.py &     # POST twice vs PUT/DELETE twice → watch `count`
```

## 6. Common misconceptions
- **"Idempotent = safe."** No — PUT/DELETE change state (not safe) but are
  idempotent (repeatable, same end state).
- **"Idempotent means same response every time."** No — it's same **end state**;
  DELETE returns 200 then 404, still idempotent.
- **"POST is for updates."** POST = create/submit (non-idempotent); use PUT/PATCH
  to update.
- **"It's safe to retry any failed request."** Only idempotent ones — retrying a
  POST can double-charge.

## 7. Diagrams needed
1. Methods table with safe/idempotent/cacheable columns.
2. The retry-duplication timeline: POST + lost response + retry → 2 charges;
   with idempotency key → 1 charge.
3. `count` bar growing on POST vs flat on PUT/DELETE (from the demo).

## 8. Video script outline
- **Hook** — "your payment timed out. The client retries. Did you just get charged
  twice?"
- **Build** — methods as verbs (live echo) → safe vs idempotent → the live `count`
  demo → retries → idempotency keys.
- **Payoff** — POST isn't idempotent → that's why idempotency keys exist.
- **Recap** — method = verb · safe=read-only · idempotent=same end state · retry
  idempotent only.

## 9. Brainstorm / open questions
- Rich HLD thread: idempotency keys, at-least-once vs exactly-once delivery,
  retry storms + backoff + jitter. Worth its own deep beat?
- The `count` demo is the killer visual — center the video on it.

## 10. References
- Live demo: `scratchpad/idempotency_demo.py`; httpbin.org/anything.
- MDN HTTP methods; Stripe idempotency-keys docs; RFC 9110 (HTTP semantics).
