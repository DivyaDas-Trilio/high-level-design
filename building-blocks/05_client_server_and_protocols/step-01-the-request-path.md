# Chapter 1 — The Request Path: What Actually Happens Between a Tap and a Response

*Building Blocks · Topic 05 (Client–Server & Protocols) · Chapter 1 of 9*

> Almost every candidate can say "the client sends an HTTP request to the server." Almost none
> can say **what that costs**. This chapter turns the request path into a *budget* — a
> millisecond figure per layer — because the budget is what turns "add a CDN" from a buzzword
> into a defensible decision.
>
> **This chapter assumes the mechanism, it does not teach it.** How the handshake actually
> synchronises sequence numbers, how cumulative ACKs and fast retransmit work, how the sliding
> window produces backpressure — that is written up at byte level in
> [`basic_networking/.../03-tcp.md`](basic_networking/docs/02-osi-model/04-transport/03-tcp.md), and the
> socket/fd/Send-Q side of this same path is in
> [`.../packet-lifecycle-end-to-end.md`](basic_networking/docs/05-packet-lifecycle/packet-lifecycle-end-to-end.md).
> Read those for *how it works*. This chapter is *what it costs, and what you do about it*.

---

## 1.1 The problem

You own the "like" endpoint of a photo app. It is a single `POST /posts/{id}/likes` that writes
one row. Your dashboards say the server handles it in **12 ms p50**. Support tickets from India
say liking a photo takes **"almost a second."**

Both are true. The 12 ms is real; it is also about 1.5% of what the user experiences. Everything
else happens on the request path, in layers your APM never instrumented, and no amount of
optimising that one INSERT will move it.

Two engineers respond to this ticket:

- The junior one profiles the handler, adds an index, and reports a 12 ms → 9 ms win. The
  tickets keep coming.
- The staff engineer draws the path, assigns a number to every hop, finds that **four network
  round-trips at ~200 ms each** are the bill, and proposes terminating TLS at an edge PoP in
  Mumbai. The tickets stop.

The difference is not intelligence. It is that the second engineer had a *model of the path*.
Building that model is the whole job of this chapter.

## 1.2 Example first: cost the path before theorising

User in Bangalore. Origin servers in AWS `us-east-1` (Ashburn, Virginia). Cold app start, so
nothing is cached or pooled. HTTPS with TLS 1.2, HTTP/1.1.

| # | Phase | What it is | Cost |
|---:|---|---|---:|
| 1 | DNS | Resolve `api.photoapp.com` → IP | ~60 ms |
| 2 | TCP handshake | SYN → SYN-ACK → ACK | 1 RTT = ~200 ms |
| 3 | TLS handshake | ClientHello … Finished (TLS 1.2) | 2 RTT = ~400 ms |
| 4 | Request → first byte | Send request, server works, first byte back | 1 RTT + 12 ms = ~212 ms |
| 5 | Response body | 400-byte JSON — fits in one packet | ~0 ms |
| | **Total** | | **≈ 872 ms** |

**Read the table again and notice what dominates.** The server is 12 ms out of 872 — *1.4%*.
Four round-trips are 800 ms — *92%*. This request is not slow because of compute, or the
database, or the JSON serialiser. It is slow because it crossed a planet four times before
delivering 400 bytes.

That reframing is the single most valuable thing in this chapter. Latency problems live in one
of exactly three buckets, and the fix for each is unrelated to the others:

| Bucket | Bound by | Symptom | Fix family |
|---|---|---|---|
| **RTT-bound** | Round-trips × distance | Small payloads still slow. p50 ≈ p99 | Fewer round-trips; shorter distance; reuse connections |
| **Bandwidth-bound** | Bytes ÷ throughput (and slow start) | Large payloads slow, small ones fine | Compress; shrink payload; cache at edge |
| **Compute-bound** | Server work | Slow regardless of location; p99 ≫ p50 | Index, cache, parallelise, queue it |

Our "like" endpoint is RTT-bound. Optimising the INSERT was working the wrong bucket.

## 1.3 RTT is physics, not engineering

The number that governs the whole table is round-trip time, and it has a floor set by the speed
of light in glass.

Light in vacuum: 299,792 km/s. In single-mode fibre the refractive index is ≈ 1.47, so signals
propagate at roughly **200,000 km/s** — about ⅔ of *c*.

Bangalore → Ashburn is ~13,600 km great-circle. But fibre does not follow great circles; it
follows cable landing stations, terrestrial rights-of-way, and peering points. A realistic
**path multiplier is 1.4–1.6×**, so call it ~20,000 km of glass.

```
one-way  = 20,000 km ÷ 200,000 km/s = 100 ms
RTT      = 200 ms
```

Add per-hop router serialisation and queueing and the measured figure lands at **180–210 ms**.
You cannot engineer this away. You can only *avoid paying it*.

Reference RTTs worth memorising — interviewers love that you know these cold:

| Path | RTT |
|---|---:|
| Same host (loopback) | ~0.05 ms |
| Same rack / same AZ | 0.1 – 0.5 ms |
| Cross-AZ, same region | 0.5 – 2 ms |
| `us-east-1` ↔ `us-west-2` | 60 – 70 ms |
| `us-east-1` ↔ `eu-west-1` | 70 – 80 ms |
| `us-east-1` ↔ `ap-south-1` (Mumbai) | 180 – 200 ms |
| `us-east-1` ↔ `ap-southeast-2` (Sydney) | 200 – 230 ms |
| Mobile 4G first hop (radio) | 30 – 60 ms |
| Mobile 5G first hop | 10 – 30 ms |
| Home broadband first hop | 5 – 15 ms |

Two consequences that shape architecture:

1. **Cross-region synchronous calls are a design smell.** One synchronous hop from Virginia to
   Mumbai spends 200 ms of your budget. Two of them, chained, spend 400 ms. If your service
   graph has a cross-region edge on the critical path, that is a finding, not a detail.
2. **Mobile users start 30–60 ms behind.** The radio leg is added to *every* round-trip, so a
   4-round-trip cold start on 4G costs 120–240 ms *extra*. Reducing round-trips helps mobile
   users disproportionately — which is exactly why Google pushed QUIC.

## 1.4 Phase 1 — DNS

Before any packet reaches your server, the client must turn a name into an address.

### The resolution chain

```
   app ──▶ stub resolver (OS)                    [cache? done: ~0 ms]
             │
             ▼
        recursive resolver (ISP / 8.8.8.8 / 1.1.1.1)   [cache? done: 5–30 ms]
             │  cache miss → walks the hierarchy
             ├──▶ root  (".")            → "ask .com"        1 RTT
             ├──▶ TLD   (".com")         → "ask ns1.photoapp" 1 RTT
             └──▶ authoritative          → A 203.0.113.10     1 RTT
```

There are **four caches** in that picture, and each has its own TTL: the app/browser cache, the
OS stub cache, the recursive resolver's cache, and (for CNAME chains) intermediate records.

Cost in practice:

| Case | Cost |
|---|---:|
| Warm — cached in the app or OS | ~0 ms |
| Warm at the recursive resolver | 5 – 30 ms |
| Cold, full recursion | 3 RTTs to *different* servers — 60 – 200 ms |
| Cold with a CNAME chain (`api` → `elb` → `cdn`) | Each link may cost its own lookup — 100 – 400 ms |

**Production nugget:** long CNAME chains are a silent cold-start tax. `api.photoapp.com` →
`photoapp-alb-123.us-east-1.elb.amazonaws.com` → an internal record is three resolutions on a
cold client. Flatten what you can (ALIAS/ANAME records at the apex resolve server-side).

### TTL is an architectural knob, not a config detail

TTL buys you a trade between **failover speed** and **DNS load / latency**:

| TTL | Failover speed | Cost |
|---|---|---|
| 30–60 s | Fast — DNS becomes a usable failover mechanism | High query volume; more cold lookups |
| 300 s (5 min) | The common default; ~5 min of blackholing after a failover | Balanced |
| 86,400 s (1 day) | Effectively no DNS failover | Cheapest, fastest for clients |

And the honest caveat every interviewer wants to hear: **clients lie about TTL.** Java's
default `InetAddress` cache historically pinned resolutions for the JVM's lifetime; many HTTP
clients and connection pools resolve once at pool creation and never again. So:

> **DNS is a poor failover mechanism and a good *placement* mechanism.** Use it to decide
> *which region* a user goes to. Use health-checked load balancers and anycast — not TTL
> expiry — to route around a dead server.

### DNS as a load balancer

Three real techniques you should be able to name and distinguish:

- **Round-robin A records** — return several IPs, let the client pick. Zero health awareness;
  a dead IP keeps getting handed out until you edit the zone. Crude but free.
- **GeoDNS / latency-based routing** — the authoritative server inspects the *resolver's*
  source IP (or the EDNS Client Subnet extension) and answers with the nearest region. This is
  how Route 53 latency routing and multi-region active-active placement work. Weakness: it sees
  the resolver, not the user — a Bangalore user on a resolver homed in Singapore gets Singapore.
- **Anycast** — the same IP is advertised from many locations via BGP; the *network* delivers
  you to the topologically nearest one. No DNS involvement in the routing decision at all. This
  is how 1.1.1.1 and modern CDNs and DDoS scrubbing work. Strongest of the three, and the reason
  CDN PoPs can be 5 ms away.

### DNS as a failure domain

Dyn, October 2016: a DDoS against a single managed DNS provider took Twitter, GitHub, Reddit,
Spotify and Netflix off the internet *while every one of their servers was healthy*. The lesson
is structural: **DNS is a hard dependency with no fallback path.** If it is down, your
perfectly healthy fleet is unreachable. Mitigation is delegation to two independent providers
(two sets of NS records), which is cheap and which most teams still do not do.

Note also **negative caching**: an `NXDOMAIN` is cached too (governed by the SOA minimum TTL).
Typo a hostname in a deploy, fix it 10 seconds later, and clients can keep failing for minutes.

## 1.5 Phase 2 — TCP

The name resolved. Now a connection.

### The handshake costs one RTT before a single application byte moves

```
client                                server
  │────────── SYN  (seq=x) ──────────▶│
  │◀───── SYN-ACK (seq=y, ack=x+1) ───│
  │────────── ACK  (ack=y+1) ─────────▶│   ← app data may ride along with this ACK
  ▼                                    ▼
                1 RTT spent
```

**TCP Fast Open** (TFO) lets a returning client send data *in the SYN* using a cached cookie,
saving that RTT. It is real and rarely usable: middleboxes strip unknown TCP options, so
support is patchy. Mention it as a known option; do not build a design on it. QUIC solved this
properly by moving the handshake to UDP — mechanism in
[`.../http3-quic.md`](basic_networking/docs/02-osi-model/07-application/http3-quic.md).

### Slow start: bandwidth is not available immediately

A fresh TCP connection does not know the path's capacity, so it probes. The initial congestion
window (`initcwnd`) on Linux has been **10 segments** since 2.6.39. With a 1460-byte MSS
(1500 MTU − 20 IP − 20 TCP), that is **~14.6 KB in the first flight**. Then the window doubles
every RTT.

Cumulative bytes deliverable after *n* RTTs, from a cold connection:

| RTTs | cwnd (segments) | Cumulative delivered |
|---:|---:|---:|
| 1 | 10 | 14.6 KB |
| 2 | 20 | 43.8 KB |
| 3 | 40 | 102 KB |
| 4 | 80 | 219 KB |
| 5 | 160 | 452 KB |

This is where the **"first 14 KB" rule** comes from: if your critical-path HTML fits in the
initial window, it arrives in one round-trip. At 15 KB it takes two — a 100% latency increase
for one extra kilobyte. Same physics governs API responses: a 40 KB JSON payload to Bangalore
costs 3 RTTs ≈ 600 ms of *pure window growth*, no matter how fat the pipe is.

**Bandwidth-delay product** makes this concrete. To saturate a 100 Mbps path with a 200 ms RTT
you need 100 Mbps × 0.2 s ÷ 8 = **2.5 MB in flight**. That requires both endpoints' socket
buffers to allow a 2.5 MB window. Default buffers on many systems do not — which is why a
"gigabit" transatlantic link delivers 20 Mbps per stream and why bulk cross-region transfer
tools open many parallel connections.

### Congestion control: CUBIC vs BBR

- **CUBIC** (Linux default) is loss-based: it grows until a packet drops, then backs off.
  Cheap, fair, and pathological on links with random (non-congestive) loss — mobile and
  long-haul — where it interprets radio loss as congestion and collapses throughput.
- **BBR** (Google, 2016) models the bottleneck bandwidth and RTT directly and paces to that
  estimate, largely ignoring loss. On lossy long-haul paths it commonly delivers **2–25×**
  CUBIC's throughput. It is a one-line change (`net.ipv4.tcp_congestion_control=bbr`) and one
  of the highest-leverage knobs available for cross-region and mobile traffic.

This is a legitimately strong thing to raise in an interview: "before I add a CDN, I'd check
whether the origin is on CUBIC — on a 200 ms lossy path, BBR is free throughput."

### Connection reuse is the highest-leverage lever you own

Everything above — handshake RTT, TLS handshake, slow start — is paid **per connection**. Reuse
the connection and it is paid **once** instead of per request.

| | New connection each request | Reused (keep-alive) |
|---|---:|---:|
| DNS | 0–60 ms | 0 |
| TCP | 200 ms | 0 |
| TLS 1.2 | 400 ms | 0 |
| Request/response | 212 ms | 212 ms |
| **Total** | **~872 ms** | **~212 ms** |

**4× faster, zero code change to the handler.** HTTP/1.1 defaults to `Connection: keep-alive`;
browsers open ~6 connections per origin and hold them. The failures happen server-to-server,
where people construct a new HTTP client per call. In Python, `requests.get(...)` in a loop
opens a fresh connection every time; `session = requests.Session()` reuses. Same story for Go's
`http.DefaultClient` vs a tuned `Transport`, and for every JDBC pool.

**Sizing a connection pool — use Little's Law.** `L = λW`: in-flight requests = arrival rate ×
service time.

```
1,000 rps × 50 ms service time = 1,000 × 0.05 = 50 concurrent in flight
→ pool must be ≥ 50, or requests queue behind connection acquisition
```

A too-small pool produces the most misdiagnosed incident in distributed systems: latency
climbs, the downstream service looks innocent (its own metrics are fine), and the queueing is
invisible because it happens *before* the request is instrumented.

### The bookkeeping that bites at scale

- **TIME_WAIT** — the side that closes actively holds the socket for 2×MSL = **60 s** on Linux
  (MSL is hardcoded at 30 s; there is no tunable). At high connection churn, a client can
  exhaust its ephemeral port range (default `32768–60999`, ~28,000 ports) and start failing to
  connect while looking completely idle. `tcp_tw_reuse` helps for outbound; the real fix is
  keep-alive so you are not churning connections.
- **Ephemeral port exhaustion is per-destination-tuple**, so a single client hammering one
  `(dst IP, dst port)` hits it far sooner than the raw port count suggests.
- **Nagle + delayed ACK** interaction: Nagle withholds a small segment waiting for more data;
  the peer's delayed-ACK withholds the ACK waiting for data to piggyback on. They deadlock each
  other for up to ~40 ms. Classic cause of "why does this tiny RPC take exactly 40 ms?"
  `TCP_NODELAY` disables Nagle and is the right default for request/response protocols.

## 1.6 Phase 3 — TLS

### TLS 1.2 costs two round-trips; TLS 1.3 costs one

```
TLS 1.2 (2 RTT)                        TLS 1.3 (1 RTT)
  ClientHello              ──▶           ClientHello + key_share  ──▶
              ◀── ServerHello, Cert,               ◀── ServerHello + key_share,
                  ServerKeyExchange, Done              {Cert, Finished}
  ClientKeyExchange,                     {Finished} + application data ──▶
  ChangeCipherSpec, Finished ──▶
              ◀── ChangeCipherSpec,
                  Finished
  application data         ──▶
```

TLS 1.3 achieved this by making the client *guess* the key-exchange group and send its
`key_share` in the very first message. If it guesses wrong there is a `HelloRetryRequest` and
you are back to 2 RTTs — rare in practice, since X25519 is universally supported.

**Cumulative saving on our Bangalore path: 200 ms per new connection, from a version bump.**
Verify what you actually negotiate; plenty of production LBs are still configured for 1.2.

### Resumption and 0-RTT

- **Session resumption** (session IDs, or stateless **session tickets**) skips the certificate
  and key exchange: 1 RTT in TLS 1.2, and in TLS 1.3 enables **0-RTT** — application data rides
  in the *first* message.
- **0-RTT has a real correctness caveat**, and knowing it is a differentiator: 0-RTT data is
  **replayable** by an attacker who captures it, because the server has no fresh nonce from the
  client yet. Therefore 0-RTT is safe only for **idempotent** requests. Never accept a
  non-idempotent `POST` over 0-RTT. This is the first appearance of idempotency in this course;
  it will not be the last (Topic 14).

### The parts that cost you without appearing in an RTT count

- **Certificate chain size.** The chain is sent in the handshake, inside the first congestion
  window. A bloated chain (extra intermediates, a 4096-bit RSA leaf) can push the handshake
  past `initcwnd` and add a whole RTT. ECDSA certificates are ~⅓ the size of RSA and faster to
  verify — a free win.
- **OCSP.** Naïve revocation checking makes the *client* fetch OCSP status from the CA — an
  extra DNS + TCP + TLS + request to a third party, on your critical path, with the CA's
  availability now in your dependency graph. **OCSP stapling** has your server include a
  CA-signed status in the handshake, eliminating it. Enable it.
- **SNI** — Server Name Indication puts the hostname in the ClientHello so one IP can host many
  certificates. It is *plaintext*, which is why it is a censorship and traffic-analysis vector,
  and why Encrypted Client Hello (ECH) exists.
- **ALPN** — Application-Layer Protocol Negotiation also rides in the ClientHello, and it is
  how `h2` gets chosen. This is the mechanical reason HTTP/2 requires TLS in every real
  deployment: the negotiation lives in the TLS handshake.
- **Handshake CPU.** The asymmetric crypto in a handshake costs 1–3 ms of CPU, versus
  microseconds for bulk symmetric encryption afterwards. A fleet doing 10,000 new
  handshakes/second is spending real cores on it — another argument for keep-alive, and the
  reason TLS termination is a distinct scaling concern.

### Where you terminate TLS is an architectural decision

| Termination point | You get | You give up |
|---|---|---|
| **At the origin LB** | Simplest; encrypted end to end | Client pays full-distance handshake RTTs |
| **At an edge PoP** | Handshakes complete in ~5 ms; edge→origin connection is pre-warmed | Traffic is decrypted at the edge; you must trust the provider |
| **Edge + re-encrypt to origin** | Both, at the cost of a second TLS session | More CPU, more moving parts |
| **mTLS between services** | Cryptographic service identity, not just IP-based trust | Certificate lifecycle management (this is what a service mesh automates — Topic 16) |

## 1.7 Phase 4 — HTTP, briefly

The protocol mechanics are already covered at depth next door — keep-alive, HTTP-level
head-of-line blocking with timed demos, HTTP/2 frames/streams/multiplexing, and QUIC's
per-stream ordering — in
[`.../http11-connection-mechanics-hol.md`](basic_networking/docs/02-osi-model/07-application/http11-connection-mechanics-hol.md)
and [`.../http3-quic.md`](basic_networking/docs/02-osi-model/07-application/http3-quic.md). Chapter 2 picks up
the part those don't cover: what h2 and h3 do to your *load balancers and gateways*. Here is
only what completes the budget.

HTTP/1.1 sends one request per connection at a time. A response must complete before the next
request on that connection starts — **head-of-line blocking**. Browsers work around it by
opening ~6 connections per origin, which is why HTTP/1.1 sites shard assets across
`img1.example.com`, `img2.example.com` (domain sharding) — and why that trick becomes an
*anti-pattern* under HTTP/2, which multiplexes everything over one connection.

Pipelining (sending request 2 before response 1 arrives) was specified, is broken by
intermediaries, and is disabled in every major browser. Do not propose it.

For the budget, the one thing that matters: **on a warm connection, a request/response costs
1 RTT + server time.** Nothing more.

## 1.8 The server side of the 12 ms

"The server handles it in 12 ms" is itself an aggregate hiding hops that each add latency *and*
a failure domain:

```
edge/CDN ──▶ L4 LB ──▶ L7 LB / ingress ──▶ API gateway ──▶ service ──▶ cache ──▶ DB
   5 ms      0.2 ms        0.5 ms            1–3 ms         app       0.5 ms   1–10 ms
```

A realistic 200 ms end-user budget, allocated:

| Component | Budget | Notes |
|---|---:|---|
| DNS (mostly warm) | 5 ms | Amortised across requests |
| TCP + TLS (mostly reused) | 10 ms | Amortised — this is why reuse matters |
| Client → edge network | 20 ms | Radio + first hops |
| Edge → origin network | 80 ms | The irreducible geography |
| LB + gateway hops | 5 ms | Each hop is also a failure domain |
| Auth check | 3 ms | Must be cached; a remote call here is fatal |
| Application logic | 15 ms | |
| Database / cache | 20 ms | Includes at least one round-trip to the datastore |
| Serialisation + response | 12 ms | |
| **Headroom for p99** | **30 ms** | Budget it explicitly or p99 will take it anyway |
| **Total** | **200 ms** | |

Two habits to take from this table. First, **give every hop a number** — the exercise itself
finds the problem. Second, **budget headroom explicitly**: a design that sums to exactly the
target has no p99.

## 1.9 Adding it up: four scenarios, same endpoint

Same 400-byte `POST`, same 12 ms handler, four deployment realities.

| Scenario | DNS | TCP | TLS | Req/Resp | **Total** |
|---|---:|---:|---:|---:|---:|
| **A.** Cold, HTTP/1.1, TLS 1.2, direct to Virginia | 60 | 200 | 400 | 212 | **872 ms** |
| **B.** Cold, TLS 1.3, direct to Virginia | 60 | 200 | 200 | 212 | **672 ms** |
| **C.** Cold, TLS 1.3, edge PoP in Mumbai (5 ms away), pre-warmed edge→origin | 20 | 5 | 5 | 212 + 5 | **247 ms** |
| **D.** Warm connection to that edge | 0 | 0 | 0 | 217 | **217 ms** |
| **E.** As D, but the response is cacheable at the edge | 0 | 0 | 0 | 7 | **7 ms** |

Sit with row **C** for a moment, because it contains the insight most people miss.

> Scenario C caches **nothing**. The request still travels to Virginia and still runs the same
> handler. Yet it is **3.5× faster than A** — purely because DNS, the TCP handshake, and the
> TLS handshake now complete against a server 5 ms away, and the edge→origin connection was
> already established and already past slow start.
>
> **A CDN's biggest win for dynamic, uncacheable content is not caching. It is moving the
> handshakes close to the user.** Say that in an interview and you have separated yourself from
> everyone who thinks a CDN is "for images".

Row **E** is the caching win on top, and it is an order of magnitude again — which is why
"which parts of this response are cacheable, and for how long?" is one of the highest-value
questions in any design discussion.

### The warm-connection caveat (do not skip this)

Everything in row C rests on the handshakes being *paid*. If the client already holds a warm,
pooled connection, those round-trips are already amortised to zero — and **edge termination
buys you almost nothing**, because what remains is the *data* round-trip to the origin, and
moving the TLS handshake does not move the data.

So the edge argument applies to clients that keep opening new connections — browsers, mobile
apps, anything behind NAT timeouts — and *not* to a warm server-to-server pool. Diagnose which
you have before proposing it:

| Situation | What's left to win | The actual fix |
|---|---|---|
| Cold / churning connections (browsers, mobile) | 3 of 4 round-trips | Edge termination, TLS 1.3, 0-RTT |
| Warm pooled connections, far origin | Only the data round-trip | Move the data closer (regional replica), or cache it |
| Warm pooled, near origin | Nothing — you are at the floor | Look at round-trips *per user action*, or at compute |

One non-obvious exception: even with warm connections and zero caching, a CDN's **private
backbone** often beats the public-internet path by 20–40% on route quality alone. That is a
real win, and the one nobody cites.

**The diagnostic move that generates all of this:** when two populations of users see different
latency for identical code, *the explanation must be a variable that differs between them*.
Subtract server time from each, and see whether what remains is exactly one round-trip. If it
is, nothing is broken — you are looking at geography, and there is no bug to find.

## 1.10 The five levers

Every latency optimisation in distributed systems is one of these. Once you see the path as a
budget, they are exhaustive.

| Lever | Mechanism | Typical win |
|---|---|---|
| **1. Reduce round-trips** | TLS 1.3 (−1 RTT), HTTP/3 (−1 RTT), 0-RTT resumption, fit critical data in the first 14 KB | 200–400 ms per new connection |
| **2. Reduce distance** | Edge termination, regional deployment, anycast, GeoDNS | Turns a 200 ms RTT into 5 ms |
| **3. Reuse connections** | Keep-alive, connection pools sized by Little's Law, HTTP/2 multiplexing | 4× on cold-start-heavy traffic |
| **4. Reduce round-trips *per user action*** | Batch endpoints, GraphQL/BFF aggregation, avoid chatty client APIs | Linear in the number of calls removed |
| **5. Move work off the path** | Cache, queue, precompute, respond `202 Accepted` | Bounded only by what must be synchronous |

Lever 4 deserves emphasis because it is the one that is *your* fault rather than the network's.
A mobile screen that fires 8 sequential API calls on a 200 ms RTT spends 1.6 seconds in
round-trips alone. No infrastructure change fixes a chatty API — that is a contract problem,
and it is why Topic 05 continues into GraphQL, BFF, and gateway aggregation.

## 1.11 Failure modes: reading the layer from the symptom

Each layer fails with a distinct signature. Being able to name the layer from the symptom is
the difference between a 5-minute diagnosis and a 2-hour one.

| Layer | Failure | Client symptom | Timing tell |
|---|---|---|---|
| DNS | `NXDOMAIN` | "Could not resolve host" | Instant, and *sticky* — negative caching keeps it failing after you fix it |
| DNS | `SERVFAIL` / resolver down | Same message | Hangs ~5 s per attempt, then fails |
| DNS | Stale record after failover | Traffic to a dead IP; some users fine, others not | Clears on TTL expiry, unevenly |
| TCP | `RST` — nothing listening | "Connection refused" | **Fast** (~1 RTT). Fast failure = the host is up, the port is not |
| TCP | SYN silently dropped (firewall / security group) | "Connection timed out" | **Slow** — Linux retries `tcp_syn_retries=6`, ~127 s. Slow failure = packets are being blackholed |
| TCP | Ephemeral ports exhausted | Intermittent connect failures on a client that looks idle | Correlates with connection churn, not with load |
| TLS | Certificate expired | "Certificate has expired" | Fails at handshake; affects 100% of clients at once, at a timestamp |
| TLS | Hostname mismatch | "Certificate name does not match" | Deterministic per hostname |
| TLS | No shared cipher / version | "Handshake failure" | Old clients break while new ones work — the tell for a TLS-policy change |
| TLS | Missing SNI (old client, multi-tenant IP) | Wrong certificate served | Only affects legacy clients |
| HTTP | `502 Bad Gateway` | LB reached, upstream unreachable/spoke garbage | Fast |
| HTTP | `503 Service Unavailable` | No healthy upstream, or shed by design | Fast — often health checks failing |
| HTTP | `504 Gateway Timeout` | Upstream accepted and never answered | Exactly at the LB's timeout value — a suspiciously round number is the tell |
| HTTP | `499` (nginx) | *Client* gave up first | Your timeout budget is inverted: client timeout < server latency |

**The two rules embedded in that table**, worth internalising:

1. **Fast failure vs slow failure tells you *where*.** A refused connection is a *reachable*
   host — routing and firewalls are fine, the process is not. A timeout means packets are
   disappearing — suspect firewalls, security groups, and routing, not the application.
2. **A response code that appears at a round number** (exactly 30.0 s, exactly 60.0 s) is a
   *timeout*, not a computation. Find whose timeout it is.

### Measuring it yourself

`curl` exposes every phase boundary. The gotcha that trips everyone: **these values are
cumulative from the start**, not per-phase — you must subtract.

```bash
cat > /tmp/curl-format.txt <<'FMT'
  dns_lookup:  %{time_namelookup}s
  tcp_connect: %{time_connect}s
  tls_done:    %{time_appconnect}s
  ttfb:        %{time_starttransfer}s
  total:       %{time_total}s
FMT

curl -w "@/tmp/curl-format.txt" -o /dev/null -s https://api.github.com
```

Derive the real per-phase costs:

```
DNS        = time_namelookup
TCP        = time_connect      - time_namelookup
TLS        = time_appconnect   - time_connect
server     = time_starttransfer- time_appconnect     ← 1 RTT + server think time
download   = time_total        - time_starttransfer
```

Then isolate layers one at a time:

```bash
dig +trace api.github.com                    # watch the full recursion, see every TTL
dig @1.1.1.1 api.github.com +short           # bypass your resolver — is the problem local?
mtr -rwc 100 api.github.com                  # per-hop loss and latency; find where RTT jumps
nc -zv api.github.com 443                    # TCP only: refused (fast) vs timeout (slow)?
openssl s_client -connect api.github.com:443 -servername api.github.com </dev/null
                                             # cert chain, negotiated version, ALPN
curl -sv --http1.1 https://api.github.com 2>&1 | grep -E 'ALPN|SSL connection|HTTP/'
ss -s                                        # socket summary — TIME_WAIT count, port pressure
ss -tan state time-wait | wc -l              # how bad is the churn?
```

Run the `curl` command against a nearby host and a far one and *watch the RTT-bound phases
scale with distance while the download phase does not.* That single observation is what turns
this chapter from information into intuition.

## 1.12 FAANG interview angle

### The question

"Walk me through what happens when you type a URL into a browser and press enter."

It is asked constantly, and it is not a trivia question — it is a **calibration** question. The
interviewer is measuring depth of model, not recall of steps.

### The three answer tiers

**Junior:** "DNS resolves the domain, the browser sends an HTTP request, the server responds,
the browser renders it." Correct and unscored.

**Senior:** the same, plus the TCP handshake, TLS, keep-alive, and caching layers. Named
mechanisms. Solid, hireable.

**Staff:** all of that **with numbers attached, and a conclusion drawn from them.** The move
that distinguishes it:

> "Let me put a budget on it, because that determines what's worth fixing. Assume the user is
> in Bangalore and the origin is in `us-east-1` — that's a ~200 ms RTT, set by the speed of
> light in fibre, so it's a floor, not a target. Cold: DNS ~60 ms, TCP one RTT, TLS 1.2 two
> RTTs, then a round-trip for the request. That's ~870 ms for a 400-byte response where the
> server spent 12 ms. So this is RTT-bound, not compute-bound, and I'd ignore the handler
> entirely.
>
> Three fixes, in order of leverage. Keep-alive removes three of the four round-trips for every
> request after the first — 872 down to ~212 ms, no code change. TLS 1.3 removes one RTT from
> the cold path. And terminating TLS at an edge PoP makes the remaining handshakes 5 ms instead
> of 200 ms — note that this helps even though the content isn't cacheable, which is the part
> people miss about CDNs.
>
> Then I'd check whether the client makes one call or eight, because eight sequential calls at
> 200 ms is 1.6 seconds that no infrastructure change will fix."

That answer demonstrates a costed model, correct bucket identification, ranked interventions,
and a non-obvious insight. It also invites the follow-ups you want.

### The probes, and what they are testing

| Probe | What they want to hear |
|---|---|
| "Why is TLS 1.3 faster?" | The client sends `key_share` in the ClientHello and guesses the group — 2 RTT → 1 RTT. Bonus: `HelloRetryRequest` on a wrong guess |
| "What is 0-RTT and why is it dangerous?" | Data in the first flight; **replayable**, so idempotent requests only |
| "Response is 200 KB and slow — same fix?" | No. Different bucket: bandwidth- and slow-start-bound. 3–4 RTTs of window growth. Compress, shrink, cache at edge |
| "Why 6 connections per origin?" | HTTP/1.1 head-of-line blocking; and why domain sharding becomes an anti-pattern under HTTP/2 |
| "How would you fail over between regions?" | DNS is *placement*, not failover — clients ignore TTLs. Use anycast + health-checked LBs. Cite Dyn 2016 for DNS as a single point of failure |
| "Sizing a connection pool?" | Little's Law: `L = λW`. 1,000 rps × 50 ms = 50 in flight, so ≥ 50 |
| "Every RPC takes exactly 40 ms. Why?" | Nagle + delayed-ACK interaction. `TCP_NODELAY` |
| "Client says timeout, server logs show success" | Timeout budget inverted (client < server), or a `499`. Timeouts must decrease as you go *down* the call stack |
| "Cross-region synchronous call — problem?" | Yes: 200 ms of budget plus a second region's availability multiplied into yours. Make it async or replicate the data |

### Red flags — say any of these and you lose the point

- **"Just add a CDN"** with no statement of what is cacheable and no number attached.
- **Optimising the compute** when the numbers say the path is RTT-bound.
- **"DNS failover handles that"** — betrays not knowing that clients cache past TTL.
- **Ignoring mobile**: the radio leg adds 30–60 ms to *every* round-trip.
- **No numbers at all.** A design conversation without arithmetic is a preference, not a design.
- **A budget that sums exactly to the SLO**, with no headroom for p99.

---

## What we produced in Chapter 1

1. **A costed model of the request path** — DNS, TCP, TLS, HTTP — denominated in RTTs rather
   than vibes.
2. **The three latency buckets** (RTT-bound / bandwidth-bound / compute-bound) and the rule
   that each has an unrelated fix family.
3. **A reference RTT table** from loopback to Sydney, and the fibre arithmetic that generates it.
4. **The five levers** — the exhaustive set of latency interventions.
5. **A per-layer failure-signature table**, plus the fast-failure/slow-failure and
   round-number-timeout diagnostic rules.
6. **A measurement recipe** (`curl -w`, `dig +trace`, `mtr`, `openssl s_client`, `ss`) that
   makes all of the above observable rather than theoretical.

## Key takeaways (transferable)

1. **RTT is physics.** ~200,000 km/s in glass, ×1.4–1.6 path multiplier. You never optimise a
   round-trip; you only avoid paying for it.
2. **Count round-trips before counting milliseconds of compute.** For small payloads, the
   handshakes *are* the latency.
3. **Connection reuse is the cheapest 4× in distributed systems.** Every per-connection cost
   becomes amortised the moment you pool.
4. **Bandwidth is not available immediately.** `initcwnd` = 10 segments ≈ 14.6 KB, doubling per
   RTT. Payload size buys round-trips whether you like it or not.
5. **Moving the handshake close to the user beats making the server faster** — for
   uncacheable content too.
6. **Fast failure means reachable; slow failure means blackholed.** This one heuristic resolves
   a large fraction of connectivity incidents.
7. **DNS is placement, not failover.** Clients cache past your TTL, and DNS itself is an
   unfallbacked hard dependency.
8. **Timeouts must shrink as you descend the call stack.** Otherwise the client gives up while
   the server is still working, and you burn capacity producing responses nobody reads.
9. **Round-trips per user action is a contract problem, not a network problem.** Eight
   sequential calls cannot be fixed with infrastructure.
10. **0-RTT requires idempotency.** The first appearance of a constraint that will recur through
    queues, retries, and payments.

## Principles in play

| Principle | How this chapter applied it |
|---|---|
| **Put a number on every hop** | An 872 ms path where the server was 12 ms — the arithmetic located the problem, not intuition |
| **Name the bottleneck before choosing the tool** | RTT-bound vs bandwidth-bound vs compute-bound; the wrong bucket means the wrong fix |
| **Amortise fixed costs** | Handshake and slow-start costs are per-connection, so pooling converts them from per-request to negligible |
| **Physics is a constraint, not a target** | Speed of light in fibre sets a floor; architecture routes around floors rather than attacking them |
| **Every hop is also a failure domain** | The LB/gateway/mesh hops each added latency *and* a way to fail; both were budgeted |
| **Prefer the free win first** | BBR, TLS 1.3, keep-alive and `TCP_NODELAY` are config changes; they precede any new infrastructure |
| **Design for the p99, budget the headroom** | A budget summing exactly to the SLO has already failed |
| **Safety constraints propagate upward** | 0-RTT's replay risk forces idempotency into the API contract |

---

*Next — Chapter 2: what h2 and h3 do to your infrastructure. HPACK/QPACK, where you terminate
which protocol, and the one nobody sees coming — **HTTP/2 multiplexing breaks connection-level
load balancing**, because one long-lived connection pins to a single backend.*
