# HTTP/1.1 — Statelessness → Horizontal Scaling ⭐

> **Status:** 🟡 studying · **Lens:** end-to-end + HLD interview (heavyweight)
> **Prereqs:** HTTP fundamentals; ties to [[http11-methods-idempotency]] (retries).
> **OSI layer:** Application (L7). **Concept 3 of the HTTP/1.1 essentials.**

## 1. One-liner
HTTP is **stateless** — the server keeps no memory between requests; the client
carries any continuity (cookie/token). That lets **any server handle any
request**, which is the foundation of horizontal scaling.

## 2. The problem it solves
Web tiers must scale to many servers and survive failures. If a server held each
client's state in memory, clients would be pinned to servers → no free scaling.
Statelessness removes that coupling.

## 3. Deep dive

### What statelessness means
Each request is **self-contained** — must carry everything the server needs. The
server treats request #2 as a stranger unless #2 re-proves identity. Continuity
is the **client's** job (send a cookie/token every request).

### LIVE DEMO (captured) — the server forgets
```
1) curl httpbin.org/cookies            -> {"cookies": {}}          (no memory of you)
2) curl -i .../cookies/set/session/u42abc -> set-cookie: session=u42abc
3) curl -b "session=u42abc" .../cookies -> {"cookies":{"session":"u42abc"}}  (recognized)
4) curl .../cookies (no cookie)         -> {"cookies": {}}          (forgotten again)
```
Identical requests differ only in what the **client** carried. Server remembered
nothing.

### Why it's THE scaling concept
Because no server holds per-client state → **any server can handle any request**:
```
                 ┌── Server A (stateless)
Client ── LB ────┼── Server B (stateless)     any request → any server
                 └── Server C (stateless)
```
- **Add capacity:** new server serves anyone immediately.
- **Survive failure:** server dies → LB routes elsewhere, nothing lost.
- **Autoscale** freely; **retries** (from #1/#2) can hit a different server and work.

Contrast — **stateful** servers pin a client to the one holding its memory: that
server dies → logged out; load can't rebalance. Statefulness kills horizontal scaling.

### Real apps need state — where does it go? (the HLD decision)
Statelessness ≠ no state — the state just doesn't live in **server memory**.

| Approach | State lives | Servers stateless? | Scaling | Trade-off |
|---|---|:--:|---|---|
| **Sticky sessions** (affinity) | server local memory, client **pinned** by LB | ❌ | poor | server death loses session; uneven load |
| **Shared store** (Redis) | external store; session-ID cookie | ✅ | good | extra infra; lookup per request |
| **Stateless token (JWT)** | inside the signed token (client) | ✅ | best | hard to revoke; size; expiry handling |

- **Sticky:** LB routes a client to the same server every time. Simple but
  re-introduces statefulness → anti-pattern at scale.
- **Shared store:** session data in **Redis**, client holds a **session-ID cookie**
  (the `session=u42abc` from the demo); any server looks it up → stays stateless.
- **JWT:** token **contains** signed identity/claims; server just **verifies the
  signature** — no lookup, no shared store. Fully stateless; revoke via short
  expiry + refresh tokens / denylist.

## 4. HLD framing
> HTTP stateless → any server handles any request → horizontal scaling +
> resilience + free load balancing. Keep it that way by pushing session state to
> a **shared store (Redis)** or a **signed token (JWT)**, never server memory.
> Sticky sessions "work" but sacrifice scalability.

"How do you scale the web tier?" → make servers stateless, put session state in
Redis/JWT, LB in front, add/remove servers freely.

## 5. Hands-on (visualize)
```bash
curl -s https://httpbin.org/cookies                              # {} — no memory
curl -s -i https://httpbin.org/cookies/set/session/u42abc | grep -i set-cookie
curl -s -b "session=u42abc" https://httpbin.org/cookies          # recognized
curl -s https://httpbin.org/cookies                              # {} again — forgotten
# cookie jar = what a browser does automatically:
curl -s -c jar.txt https://httpbin.org/cookies/set/a/1 >/dev/null; curl -s -b jar.txt https://httpbin.org/cookies
```

## 6. Common misconceptions
- **"Stateless = no state anywhere."** No — state moves to the client (token) or a
  shared store (Redis); just not server memory.
- **"Cookies make HTTP stateful."** HTTP stays stateless; the cookie is client-
  carried state layered on top.
- **"Sticky sessions are fine."** They pin clients to servers → lose most scaling/
  resilience benefits.
- **"JWT can be revoked like a session."** Not easily — it's self-contained; needs
  short expiry + refresh/denylist.

## 7. Diagrams needed
1. Stateless servers behind an LB — any request → any server.
2. Stateful (pinned) vs stateless — what breaks when a server dies.
3. Three session strategies compared (sticky / Redis / JWT).

## 8. Video script outline
- **Hook** — "the server you talked to just died. Why are you still logged in?"
- **Build** — the demo (server forgets) → statelessness → any-server-any-request →
  horizontal scaling → where state goes (sticky/Redis/JWT).
- **Payoff** — statelessness is what makes the web tier scale & survive failure.
- **Recap** — server forgets · client carries state · any server any request ·
  Redis/JWT not server memory.

## 9. Brainstorm / open questions
- Deep HLD thread: token revocation, refresh tokens, session invalidation, JWT
  size vs opaque tokens, where Redis sits (its own scaling). Own beat?
- Ties up to load balancing (L7 version of the router you built) and retries.

## 10. References
- Live: httpbin.org/cookies. MDN cookies; JWT.io; "12-factor app" (statelessness).
