# Topic 05 — Client–Server Model & Communication Protocols

*Teaching order: **1 of 19**. Syllabus number: 5.*

> **Why this is first.** Every other building block is a box on the request path. A cache is
> "don't traverse the path". A CDN is "shorten the path". A load balancer is "fan the path
> out". A queue is "take this off the path". You cannot reason about *any* of them — or about
> a latency budget, which is the thing interviewers actually probe — until you know what the
> path costs, layer by layer, in milliseconds.

## Chapter roadmap

| Ch. | Chapter | What you walk away with | Status |
|---:|---|---|---|
| 1 | [The request path: tap → response](step-01-the-request-path.md) | DNS/TCP/TLS/HTTP costed in RTTs; the latency budget; the five levers; per-layer failure signatures | 🟡 doc written, drilled Q1 only |
| 2 | [What h2/h3 do to your infrastructure](step-02-what-h2-h3-do-to-infrastructure.md) | Why an L4 LB becomes a sticky router; HPACK as per-connection state; Rapid Reset; two-level flow control; GOAWAY; the per-hop protocol table | 🟡 doc written |
| 3 | [REST that survives production](step-03-rest-that-survives-production.md) | Offset vs cursor pagination (correctness, not just speed); partial failure & deadline propagation; idempotency implemented properly; the compatibility matrix | 🟡 doc written |
| 4 | [HTTP caching & conditional requests](step-04-http-caching-and-conditional-requests.md) | The four caches on the path; `(objects × PoPs) ÷ TTL`; expiration vs validation; `Vary` cardinality; the authenticated-caching data leak; invalidation ranked; edge stampede | 🟡 doc written |
| 5 | Asynchronous API surfaces | `202` + status resources, polling vs webhooks vs SSE, webhook signing & replay, delivery guarantees, presigned uploads | ⬅️ next |
| 6 | gRPC & Protocol Buffers | IDL, wire format, streaming modes, deadlines, load balancing gRPC — where Ch. 2's law comes due | pending |
| 7 | GraphQL | Schema/resolvers, the N+1 problem, DataLoader, persisted queries, federation, why caching gets hard | pending |
| 8 | The decision: REST vs gRPC vs GraphQL vs WebSocket | A defensible matrix, not a preference | pending |
| 9 | API Gateway | Auth, rate limiting, routing, aggregation, BFF, CORS, and what belongs *out* of the gateway | pending |
| 10 | Auth **and object-level authorization** | Sessions vs JWT (and revocation), OAuth2/OIDC, mTLS, service identity — plus BOLA/IDOR, the #1 real API vulnerability | pending |
| 11 | Versioning, deprecation, contract testing | Evolving an API nobody can redeploy for you (partly covered in Ch. 3) | pending |

## Prerequisite reading in `basic_networking/`

The **mechanism** of these protocols is already written up, at depth, in the sibling
video-teaching course — with live `nghttp` frame traces and timed HoL demos. This topic does
not restate it; it assumes it and works at design altitude instead.

| Read this first | Covers |
|---|---|
| [`basic_networking/docs/02-osi-model/04-transport/03-tcp.md`](basic_networking/docs/02-osi-model/04-transport/03-tcp.md) | Handshake, seq/ACK, fast retransmit, sliding window, AIMD, CUBIC/BBR |
| [`.../04-udp.md`](basic_networking/docs/02-osi-model/04-transport/04-udp.md) | The two axes: reliability × framing |
| [`.../07-application/http11-connection-mechanics-hol.md`](basic_networking/docs/02-osi-model/07-application/http11-connection-mechanics-hol.md) | Keep-alive, HTTP-level HoL, the 6-connection hack, HTTP/2 frames/streams/multiplexing |
| [`.../07-application/http3-quic.md`](basic_networking/docs/02-osi-model/07-application/http3-quic.md) | TCP-level HoL, QUIC per-stream ordering, 1-RTT/0-RTT, connection migration, `Alt-Svc` |
| [`.../07-application/http11-methods-idempotency.md`](basic_networking/docs/02-osi-model/07-application/http11-methods-idempotency.md) | Safe/idempotent semantics, idempotency keys — Chapter 3 builds on this |
| [`.../07-application/http11-status-codes.md`](basic_networking/docs/02-osi-model/07-application/http11-status-codes.md) | Status families, the retry decision table |
| [`.../07-application/http11-statelessness-scaling.md`](basic_networking/docs/02-osi-model/07-application/http11-statelessness-scaling.md) | Stateless web tier, sticky vs Redis vs JWT — Chapter 8 builds on this |
| [`basic_networking/docs/05-packet-lifecycle/packet-lifecycle-end-to-end.md`](basic_networking/docs/05-packet-lifecycle/packet-lifecycle-end-to-end.md) | The socket/fd/Send-Q/Recv-Q half of Chapter 1's request path |

## Lab (built once, at the end of the topic)

`lab/` — stand up two services behind one gateway: a REST edge and a gRPC internal hop, fully
instrumented so you can *measure* every phase from Chapter 1 and watch the numbers move as you
switch protocol, enable keep-alive, and terminate TLS at the edge.

## Revision card

*Filled in as chapters land — this becomes the one page you reread before an interview.*

- **RTT is physics, not engineering.** ~200 ms Bangalore↔Virginia is a floor. You cannot
  optimise it, only avoid paying it. (Ch. 1)
- **Small responses are RTT-bound; large ones are bandwidth- and slow-start-bound.** The fix
  differs completely. (Ch. 1)
- **Check for the free cache before designing a paid one** — HTTP caching works at four
  layers from one header. Origin load is `(objects × PoPs) ÷ TTL`, so it scales with **PoP
  count, not traffic** — which is what origin shields are for. (Ch. 4)
- **A TTL is a promise you cannot retract.** You can purge a CDN; you can never purge a
  browser. The only reliable invalidation is changing the URL. (Ch. 4)
- **Shared caches key on URL, and identity isn't in the URL** — so `public` on a per-user
  response is a cross-user data leak that looks harmless in review. (Ch. 4)
- **`Vary` is a cardinality multiplier**; `no-cache` means *may store, must revalidate*, not
  *don't cache*. (Ch. 4)
- **A CDN's biggest win for *dynamic* content is not caching** — it's terminating TCP/TLS
  near the user so the handshake round-trips get cheap. **But only for cold connections** —
  against a warm pooled connection that win is already banked. (Ch. 1)
- **When two user populations see different latency for identical code, the cause must be a
  variable that differs between them.** Subtract server time; if what's left is exactly one
  RTT, nothing is broken — you're looking at geography. (Ch. 1)
- **An L4 load balancer balances connections, not requests** — so its granularity is the
  lifetime of a connection, and HTTP/2 makes connections immortal. Whether it bites depends
  on the clients-to-backends ratio. (Ch. 2)
- **Multiplexing decoupled requests from connections**, and every control built on counting
  connections — rate limits, autoscaling, DDoS defence — silently stopped bounding anything.
  Rapid Reset was the bill. (Ch. 2)
- **Protocol choice is per-hop, not per-organisation.** (Ch. 2)
- **Offset pagination's fatal flaw is correctness, not speed** — it addresses positions in a
  result set that shifts under concurrent writes, so clients get duplicates and skips. A
  cursor names a *row*, and needs a unique tiebreaker or it silently drops data at page
  boundaries. (Ch. 3)
- **Never return 200 for a response the client cannot tell apart from a complete one.**
  `null` (unknown) is not `[]` (known empty) — otherwise clients cache your outages as facts.
  (Ch. 3)
- **Idempotency means storing and replaying the response**, not remembering the key — and the
  dedup record must commit in the same transaction as the effect, which is why it can't live
  in the gateway. (Ch. 3)
- **You can add; you cannot remove or change meaning** — and adding an enum value is the
  "additive" change that breaks careful people. (Ch. 3)

---

*Next — Chapter 2: HTTP/1.1 vs HTTP/2 vs HTTP/3.*
