# Chapter 2 — What HTTP/2 and HTTP/3 Do to Your Infrastructure

*Building Blocks · Topic 05 (Client–Server & Protocols) · Chapter 2 of 9*

> **This chapter does not teach the protocols.** Frames, streams, multiplexing, head-of-line
> blocking at both layers, HPACK's existence, QUIC's per-stream ordering — all of that is
> already written up at byte level, with live `nghttp` traces, in
> [`basic_networking/.../http11-connection-mechanics-hol.md`](basic_networking/docs/02-osi-model/07-application/http11-connection-mechanics-hol.md)
> and [`.../http3-quic.md`](basic_networking/docs/02-osi-model/07-application/http3-quic.md).
> Read those first.
>
> This chapter is the part those docs don't cover, and the part that actually shows up in
> design reviews and incidents: **multiplexing silently redefined what a "connection" is, and
> every piece of infrastructure that was built around the old definition broke.** Load
> balancers, rate limiters, autoscalers, connection-count dashboards, DDoS defences. None of
> them were wrong. The unit underneath them changed.

---

## 2.1 The problem

You enable HTTP/2 on your ingress. Latency improves — the demo was real, the page loads
faster, everyone is pleased.

A week later you are looking at five identical backend pods:

```
pod-a   CPU 91%   ██████████████████░░
pod-b   CPU 88%   █████████████████░░░
pod-c   CPU 14%   ███░░░░░░░░░░░░░░░░░
pod-d   CPU 11%   ██░░░░░░░░░░░░░░░░░░
pod-e   CPU  9%   ██░░░░░░░░░░░░░░░░░░
```

Two pods are melting. Three are idle. The autoscaler, watching average CPU, adds a sixth pod —
which receives **no traffic at all** and drags the average *down*, so the autoscaler is now
actively making things worse. Health checks all pass. No code changed. Rolling the pods
redistributes the pain to a different two.

Nothing is broken. Your load balancer is doing exactly what it was built to do, and HTTP/2
made that the wrong thing.

## 2.2 Example first: watch the unit of load balancing change

An L4 load balancer makes its decision **once, at connection establishment**. After that,
every byte on that connection goes to the backend it chose, for as long as the connection
lives. That was always true. It only became a problem when connections started living forever
and carrying everything.

**Scenario A — HTTP/1.1, browser traffic, 5 backends**

```
1,000 users × ~6 connections/origin = ~6,000 connections
connections churn constantly (page loads, NAT timeouts, keep-alive expiry)
→ the LB makes ~6,000 balancing decisions, continuously refreshed
→ backends land within a few percent of each other
```

Balancing works. Not because the LB is clever, but because it got *thousands of independent
decisions* and the law of large numbers did the rest.

**Scenario B — same thing, HTTP/2**

```
1,000 users × 1 connection = 1,000 connections
→ 1,000 decisions over 5 backends = 200 each. Still fine!
```

Still fine — because there are still many clients. **The number of clients is doing all the
work here**, and that is the trap: h2 looks safe in the browser-facing case, so people
conclude it is safe everywhere.

**Scenario C — the one that bites: few clients, many requests**

This is *every internal service*, every gRPC hop, every API gateway tier.

| Setup | Connections | Backends | Result |
|---|---:|---:|---|
| Service A (6 pods) → Service B (20 pods), h2 | 6 | 20 | **14 pods receive zero traffic** |
| Gateway tier (10 instances) → API (50 pods), h2, pooled | 10 | 50 | 40 pods idle; 10 pods take 100% |
| Batch job (1 client) → sharded service (12 pods) | 1 | 12 | 1 pod takes everything |
| Same as row 1 but HTTP/1.1 with a 100-conn pool | 600 | 20 | ~30 each — even |

Row 1 is worth sitting with. Service A has six pods, each opens **one** h2 connection to
Service B, and multiplexes its entire request stream over it. Six connections cannot cover
twenty backends. You scaled Service B to twenty pods and bought capacity on fourteen machines
that will never see a request.

And the last row shows the uncomfortable punchline: **the "obsolete" protocol balanced better.**
HTTP/1.1's inefficiency — many connections, constant churn — was accidentally feeding the load
balancer the decisions it needed.

## 2.3 The mechanism: granularity of balancing = lifetime of a connection

State it as a law, because everything else in this chapter follows from it:

> **An L4 load balancer balances connections, not requests. So its effective granularity is
> the lifetime of a connection. Multiplexing makes connections immortal, which turns your
> load balancer into a sticky router.**

Trace what each protocol hands the LB:

| Protocol | Connection lifetime | Requests per connection | Decisions the LB gets |
|---|---|---:|---|
| HTTP/1.0 | one request | 1 | one per request — perfect granularity, terrible efficiency |
| HTTP/1.1 keep-alive | seconds to minutes | tens, serially | frequent, self-refreshing |
| HTTP/2 | hours to days | **unbounded, concurrent** | **one, then blind** |
| gRPC (mandates h2) | process lifetime | unbounded; streams can last hours | one, then blind |
| HTTP/3 | survives IP changes (Connection ID) | unbounded | one, and now it can *migrate* |

Three things compounded to make this bite now rather than in 2015:

1. **h2 removed the reason to churn connections.** The whole point was to stop paying
   handshakes, so clients hold one connection open indefinitely. The efficiency *is* the
   problem.
2. **gRPC made it mandatory.** gRPC requires HTTP/2 — you cannot opt out — and gRPC channels
   are long-lived by design. Every microservice architecture that adopted gRPC adopted this
   problem, usually without noticing.
3. **Backends became numerous and short-lived.** Five VMs behind an LB tolerated coarse
   balancing. Fifty pods that reschedule constantly do not: a new pod joining the fleet
   receives traffic **only when someone opens a new connection**, and under h2 nobody does.

That last point deserves a name, because it is the failure mode people hit at 3am:

> **Under h2 with an L4 LB, scaling out does nothing.** New capacity gets no traffic until
> connections are re-established. Your autoscaler adds pods; your hot pods stay hot.

## 2.4 The fixes, ranked

### 1. Terminate HTTP/2 at an L7 proxy and balance per request *(the correct default)*

The proxy accepts the client's h2 connection, parses frames, and routes **each stream
independently** to a backend — usually over its own pool of connections. Granularity returns
to per-request, which is what you actually wanted.

```
                       ┌─ pod-a
client ══h2══ [Envoy] ─┼─ pod-b     one client connection in,
   (1 conn,      L7    ├─ pod-c     each STREAM balanced separately
   many streams)       ├─ pod-d
                       └─ pod-e
```

Envoy, nginx, HAProxy in HTTP mode, AWS ALB, and every service-mesh sidecar do this. The cost
is real and worth stating out loud: TLS termination plus HTTP parsing CPU, **+0.5–2 ms** of
latency, and one more hop that can fail. You are buying correct balancing with a hop.

While you are there, **change the algorithm too.** Round-robin was tuned for a world of
short-lived connections where a bad assignment self-corrected in seconds. With long-lived
streams, prefer **least-request** or **P2C (power of two choices)** — sample two backends, send
to the one with fewer outstanding requests. It costs nothing and it corrects continuously
instead of hoping.

### 2. Cap connection lifetime, so the LB gets new decisions

If you must keep an L4 path, force periodic reconnection:

| Knob | Where | Typical |
|---|---|---|
| `max_connection_duration` | Envoy | 30 s – 5 min |
| `max_requests_per_connection` | Envoy | 1,000 – 10,000 |
| `GRPC_ARG_MAX_CONNECTION_AGE_MS` (+ `_GRACE_MS`) | gRPC server | 30 s + 10 s grace |
| `keepalive_time` | nginx ≥ 1.19.10 | 1 h default — usually far too long |

**Add jitter, or you have built a thundering herd.** Every connection opened at deploy time
expires at the same instant, all clients reconnect simultaneously, and you get a synchronised
handshake storm every N minutes — a self-inflicted outage on a timer. gRPC's grace period
exists for exactly this; use it, and randomise the age by ±20%.

This is a mitigation, not a fix: between reconnects you are still imbalanced, so you are
trading average skew against reconnect cost.

### 3. Client-side load balancing

Skip the proxy: let the client discover every backend and choose per request. gRPC does this
natively (`round_robin`, or xDS-driven policies); it opens a **subchannel** per backend and
balances across them.

```
              ┌──── pod-a
client ───────┼──── pod-b     client holds N connections,
(knows all    ├──── pod-c     picks per request. No proxy hop.
 backends)    └──── pod-d
```

Best latency — no extra hop — but you have moved the problem: every client now needs service
discovery, health state, and policy configuration pushed to it. **That distribution problem is
what a service mesh and the xDS protocol exist to solve** (Topic 16). Choosing this without a
control plane means hand-rolling one.

### 4. Look-aside load balancing

The client asks a balancer service "which backend?", then connects directly. gRPC-LB / the
lookaside pattern. Keeps policy centralised without putting a proxy in the data path. Fewer
implementations, more moving parts; worth knowing the name.

### 5. Deliberately open more connections

Configure a small pool of h2 connections per client — say 4 or 8 — instead of one. The LB gets
several decisions per client, and skew falls roughly as you would expect from sampling. Crude,
cheap, and often enough for an internal service. You are intentionally giving back some of
h2's efficiency to buy balancing.

## 2.5 HPACK: per-connection shared state, and a security surface

### Why it exists

HTTP/1.1 sends headers as plaintext on every request, and they are almost entirely identical
request to request: `User-Agent`, `Accept`, `Cookie`, `Authorization`. Typically **500–800
bytes**. A page pulling 100 resources ships 50–80 KB of near-duplicate text — which, from
Chapter 1, is several round-trips of slow-start window on a distant client.

HPACK reduces repeat headers to a handful of bytes using three mechanisms: a **static table**
of 61 predefined common entries, a **dynamic table** built from headers actually seen on this
connection, and **Huffman coding** for literal values.

### The consequence that matters for infrastructure

> **The dynamic table is per-connection mutable state that both endpoints must keep
> synchronised.**

Two things follow, and both are operational:

**Memory scales with connections, not requests.** Each direction maintains its own table,
default 4,096 bytes (`SETTINGS_HEADER_TABLE_SIZE`). A proxy holding 100,000 h2 connections:

```
100,000 conns × 2 directions × 4 KB = 800 MB   ← header tables alone
plus: per-connection h2 state machine, per-stream flow-control windows,
      per-stream buffers × concurrent streams
```

HTTP/2 reduces *file descriptor* pressure — one fd where you had six — and **increases memory
per connection**. If your capacity model was "fds are the limit," it is now wrong in both
directions. Re-derive it.

**Compression is an attack surface.** A decompression ratio you do not control is a weapon:

- **The HPACK bomb** — small compressed input expanding to enormous header sets. Mitigation is
  `SETTINGS_MAX_HEADER_LIST_SIZE` and hard caps in the proxy. Never leave header size
  unbounded.
- **The 2019 HTTP/2 DoS family (CVE-2019-9511 … 9518)** — eight CVEs disclosed together, all
  variants of "make the server do unbounded work per unit of client effort": Data Dribble,
  Ping Flood, Reset Flood, Settings Flood, Empty Frame Flood, Internal Data Buffering. Every
  major implementation was affected. The shared root cause: **a request stopped being a
  connection, so per-connection accounting stopped bounding work.**

### QPACK, and why it is not just HPACK-for-h3

HTTP/3 needs header compression too, but QUIC delivers streams **independently and out of
order** — which breaks HPACK's core assumption that both sides see the same sequence of
updates. QPACK solves it by splitting into a dedicated encoder stream and decoder stream, and
by letting the encoder *choose not to* reference very recent table entries.

That choice is the design lesson: **QPACK deliberately compresses worse in order to avoid
reintroducing head-of-line blocking on the header stream.** After all the work HTTP/3 did to
eliminate HoL, it would be absurd to smuggle it back in via compression. Worth having as an
example of a protocol trading efficiency for the property it actually cared about.

## 2.6 Rapid Reset: the whole chapter in one CVE

October 2023, **CVE-2023-44487**. The largest DDoS attacks recorded at the time — **398 million
requests/second** at Google, 201M at Cloudflare, 155M at AWS.

The attack is three lines:

```
open stream  → send HEADERS → immediately send RST_STREAM
repeat, thousands of times per second, over ONE connection
```

`SETTINGS_MAX_CONCURRENT_STREAMS` was supposed to bound this. It bounds *concurrent* streams —
and a stream you reset immediately is never concurrent. It is closed before the limit can see
it. Meanwhile the server has already done the expensive part: allocated stream state, decoded
HPACK headers, dispatched to the application, and torn it all down.

So a single TCP connection could drive an unbounded request rate, and:

- **connection-count rate limits** saw one connection
- **connections-per-IP limits** saw one connection
- **L4 DDoS defences** saw a trickle of traffic
- **your dashboards** showed normal connection counts and a burning fleet

The fix is to make resets themselves a metered resource — count RST_STREAM per connection, cap
the rate, and close connections that abuse it.

> **Say the general lesson out loud, because it is the transferable one:** multiplexing
> decoupled *requests* from *connections*, and every control you had built on connection
> counting silently stopped bounding anything. Rapid Reset was not an HTTP/2 bug. It was the
> bill for a redefinition that arrived years earlier, and it is the same redefinition that
> broke your load balancer in §2.1.

## 2.7 The other things that quietly broke

### Flow control now exists at two levels

HTTP/2 has a **connection-level** window *and* a **per-stream** window, both defaulting to
**65,535 bytes**. Both must have room, or data stops.

Apply Chapter 1's bandwidth-delay product:

```
65,535 bytes ÷ 0.2 s RTT = 327 KB/s ≈ 2.6 Mbps per stream
```

That is the ceiling until windows grow — and it is the answer to the recurring bug report
**"HTTP/2 made our large downloads slower than HTTP/1.1."** HTTP/1.1 had no application-layer
window at all; TCP's window grew freely. h2 added a second, smaller, application-level window
on top, and nobody tuned it.

| Knob | Default | Raise it for |
|---|---|---|
| `SETTINGS_INITIAL_WINDOW_SIZE` | 65,535 | large responses over high-RTT paths |
| Envoy `initial_stream_window_size` | 64 KB | ↑ to 1–16 MB for bulk transfer |
| Envoy `initial_connection_window_size` | 64 KB | must exceed stream window × concurrency |
| `SETTINGS_MAX_FRAME_SIZE` | 16,384 | rarely; affects chunking granularity |

The trap: raising the *stream* window while leaving the *connection* window at 64 KB fixes
nothing — the connection window becomes the bottleneck for all streams together.

### Blast radius per connection is now N requests

Under HTTP/1.1, a connection failing killed one in-flight request. Under h2, it kills every
stream on that connection — potentially hundreds. Which makes one frame you probably ignore
load-bearing:

**GOAWAY** is h2's graceful-shutdown protocol. A server shutting down sends GOAWAY carrying the
last stream ID it will process; the client must retry anything above that ID elsewhere.

> **If your client does not handle GOAWAY, every deployment drops requests.** Not "may" —
> every rolling restart, on every pod, forever, silently, showing up as a small unexplained
> error-rate bump during deploys that everyone learns to ignore.

Retries need rethinking for the same reason: a retry on the *same* connection reaches the
*same* backend. Retrying into the failure is not a retry. Your policy must force a new
connection or delegate to an L7 proxy that can re-route.

### Metrics and autoscaling stop meaning what they meant

| Signal | Under HTTP/1.1 | Under HTTP/2 |
|---|---|---|
| Active connections | decent proxy for load | **decorrelated from load** |
| Connections per IP | a usable rate limit | one connection, unbounded requests |
| fd count / `ulimit -n` | often the binding constraint | falls ~6× |
| Memory per connection | small | h2 state + HPACK tables + per-stream windows |
| Access logs | one line ≈ one connection | must instrument **per stream** |

Anything autoscaling on connection count is now wrong. Scale on requests-in-flight, CPU, or
queue depth.

## 2.8 Where to terminate which protocol

The decision, hop by hop. This table is the practical output of the chapter:

| Hop | Use | Why |
|---|---|---|
| **Client → edge** | **h3, with h2 fallback** | Browsers and mobile open fresh connections and change networks — exactly where QUIC's 1-RTT handshake and connection migration pay. Fallback is mandatory, not optional. |
| **Edge → origin** | **h1.1 with a large keep-alive pool, or h2 through an L7 proxy** | Plain h2 over an L4 path buys you §2.1. Many pooled h1.1 connections balance *better* and the handshake cost is amortised anyway. |
| **Service → service (gRPC)** | **h2, mandatory** — with client-side LB or a mesh | You have no choice about h2; you do have a choice about balancing. Make it. |
| **Service → service (REST)** | h1.1 pooled is fine | h2's multiplexing wins little when the client is a pool, and it costs you balancing. |
| **Anything → origin over h3** | **no** | h3 is a client-to-edge protocol. Inside your network you control the paths, RTT is sub-millisecond, and you gain nothing for real operational cost. |

Two practical constraints on that first row:

- **h2 requires TLS in practice.** Negotiation happens via **ALPN inside the TLS handshake**
  (Chapter 1, §1.6). Cleartext `h2c` exists, needs prior knowledge or an Upgrade dance, and no
  browser supports it. Inside a mesh with mTLS this is moot.
- **h3 is discovered, not negotiated.** The first connection is TCP, so the server advertises
  `Alt-Svc: h3=":443"; ma=86400` and the client tries UDP *next time*. Set `ma` conservatively:
  a long `ma` cached against a network that blocks UDP means a fallback penalty on every first
  request for a day.

And an inversion worth stating, because it is a live source of bad advice:

> **Domain sharding and aggressive asset concatenation were HTTP/1.1 workarounds. Under h2/h3
> they are actively harmful** — sharding defeats multiplexing and multiplies handshakes;
> concatenation destroys caching granularity. If a "web performance best practice" predates
> 2016, check whether it is now an anti-pattern.

## 2.9 Operating h3: what actually changes

Everything about QUIC that makes it good for clients makes it awkward for infrastructure.

**Connection ID routing, or migration breaks.** Your L4 LB and ECMP hashing route by 4-tuple.
QUIC connections *deliberately survive* an IP change — that is the migration feature — so after
a client moves from Wi-Fi to cellular, its packets hash to a **different backend**, which holds
none of its state. The fix is Connection-ID-aware routing: encode routing information *into*
the Connection ID so the fabric can steer migrated packets to the right box. Google and
Cloudflare do this; most off-the-shelf L4 gear does not. **If you deploy h3 without it, you
have shipped a feature that breaks on the exact event it was built for.**

**CPU cost is real.** Congestion control and crypto run in user space rather than the kernel.
Historically ~2× the CPU per byte versus kernel TLS over TCP; closing with UDP GSO and
offloads, but budget for it rather than assuming parity.

**UDP/443 gets blocked.** Enterprise networks, some mobile carriers, and captive portals drop
or throttle it. Your h2 fallback is a production path, not a safety net.

**Load balancer support is the gate.** As a concrete example, CloudFront speaks h3 while ALB
does not — so "enable h3" is often an edge-tier decision you cannot push inward.

**You lose network-level observability, by design.** QUIC encrypts the transport header —
sequence numbers included. Passive network monitoring that read TCP state off the wire goes
blind. This is intentional anti-ossification, and it means the visibility must move into the
endpoints (which is where Topic 17's tracing story starts to matter).

## 2.10 Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Identical pods, wildly uneven CPU; autoscaler thrashing | L4 balancing long-lived h2 connections | L7 per-request balancing; `max_connection_duration` + jitter |
| Scaling out changes nothing | New pods get no traffic without new connections | Same as above |
| Huge request rate, normal connection count, fleet on fire | Rapid Reset (CVE-2023-44487) | Meter RST_STREAM per connection; close abusers |
| Large downloads slower on h2 than h1.1 | 64 KB stream/connection windows | Raise both windows; connection > stream × concurrency |
| Small error-rate bump on every deploy | Client ignoring GOAWAY | Handle GOAWAY; retry streams above the last-processed ID |
| Retries fail identically to the original | Retry reused the same connection → same backend | Force new connection, or retry at the L7 proxy |
| Proxy OOM after enabling h2 | HPACK tables + per-stream state × connections | Cap header list size; re-derive memory per connection |
| First request slow, every time, on one network | Cached `Alt-Svc` for h3 where UDP is blocked | Lower `ma`; verify fallback |
| h3 connections break when users change network | 4-tuple routing instead of Connection ID | CID-aware routing, or don't ship h3 |

### Seeing it yourself

```bash
# Confirm what you actually negotiated (ALPN), not what you configured:
openssl s_client -alpn h2 -connect example.com:443 -servername example.com </dev/null 2>&1 \
  | grep -i 'ALPN protocol'

# Is h3 advertised, and for how long?
curl -sI https://cloudflare.com | grep -i alt-svc

# Watch stream IDs multiplexing on ONE connection:
nghttp -vn https://example.com/ https://example.com/ 2>&1 | grep -E 'stream_id|SETTINGS'

# The settings the peer actually sent (windows, max streams, header table):
nghttp -vn https://example.com/ 2>&1 | grep -A8 'SETTINGS frame'

# Prove the imbalance in your own cluster — request counts per pod, not connections:
kubectl top pods -l app=your-svc            # then compare against
# per-pod request rate from your metrics; if CPU is skewed and RPS is skewed
# the same way while connections are few, you have found §2.1.
```

## 2.11 FAANG interview angle

### The flagship question

"You enabled HTTP/2 on your ingress and now one backend is hot while others are idle. Why?"

This is asked because it separates people who have *read* about HTTP/2 from people who have
*operated* it. The answer must contain the law from §2.3:

> "An L4 load balancer balances connections, not requests, so its granularity is the lifetime
> of a connection. HTTP/2 made connections long-lived and unbounded, so the LB makes one
> decision per client and is then blind. With many clients the law of large numbers hides it;
> with few clients — which is every internal service and every gRPC hop — six connections
> cannot cover twenty backends, so fourteen sit idle. Worse, scaling out doesn't help, because
> new pods only get traffic when someone opens a new connection and nobody does.
>
> The fix is per-request balancing at an L7 proxy, plus least-request or P2C instead of
> round-robin since a bad assignment now persists. If I have to keep an L4 path, I'd cap
> connection duration with jitter — without jitter you've built a synchronised reconnect
> storm. Long term, client-side balancing via xDS removes the hop, but then you need a control
> plane to distribute endpoints and health."

### The probes

| Probe | What they want |
|---|---|
| "How do you load balance gRPC?" | You *can't* at L4 — gRPC mandates h2 and channels are long-lived. L7 per-request, or client-side LB with a control plane, plus `MAX_CONNECTION_AGE` + grace |
| "Why is h2 slower for our 50 MB downloads?" | Two-level flow control, 64 KB defaults; BDP arithmetic; raise connection window too, not just stream |
| "How did Rapid Reset work?" | Reset streams never count as concurrent; multiplexing decoupled requests from connections, so connection-based limits bounded nothing |
| "Should we run h3 to the origin?" | No. Client-to-edge protocol; sub-ms internal RTT, no migration need, real CPU and routing cost |
| "What breaks when you enable h3 at the edge?" | 4-tuple routing vs Connection ID migration; UDP blocking; CPU; loss of passive network observability |
| "We're at our fd limit — will h2 help?" | Yes, ~6× fewer fds — but memory per connection rises. Re-derive the capacity model in both directions |
| "Why does our error rate blip on every deploy?" | GOAWAY not handled; streams above the last-processed ID never retried |
| "Should we shard assets across subdomains?" | That's an h1.1 workaround; under h2 it defeats multiplexing and multiplies handshakes |

### Red flags

- **"HTTP/2 is faster, we should enable it everywhere."** Everywhere includes the L4 path where
  it breaks balancing. Protocol choice is per-hop.
- **Proposing domain sharding** — dates you to 2014.
- **Assuming the L4 LB still works.** The single most common miss.
- **Treating h3 as "h2 but faster"** rather than a different transport with different
  operational requirements.
- **No mention of the client count.** Whether h2 imbalance bites depends entirely on
  clients-vs-backends; an answer that doesn't ask for that ratio hasn't understood it.

---

## What we produced in Chapter 2

1. **The law:** L4 balancing granularity = connection lifetime; multiplexing makes an L4 load
   balancer a sticky router.
2. **The clients-vs-backends ratio** as the predictor of whether h2 imbalance bites — and why
   internal services and gRPC always lose that ratio.
3. **Five ranked fixes** with their real costs: L7 per-request (a hop), capped connection age
   (needs jitter), client-side LB (needs a control plane), look-aside, more connections.
4. **HPACK as per-connection state** — a memory model that scales with connections, and a
   compression attack surface.
5. **Rapid Reset as the general lesson**, not a trivia CVE: connection-based controls stopped
   bounding work the moment requests stopped being connections.
6. **Two-level flow control** and the BDP arithmetic behind "h2 made downloads slower."
7. **GOAWAY** as the difference between clean deploys and a permanent unexplained error blip.
8. **A per-hop protocol decision table**, including the two places h3 does not belong.

## Key takeaways (transferable)

1. **When a protocol changes what a "unit" means, every control built on the old unit breaks
   silently.** Requests stopped equalling connections; balancing, rate limiting, autoscaling,
   and DDoS defence all quietly stopped working. Nothing errored.
2. **Efficiency and observability trade against each other.** Long-lived connections are
   efficient *because* they hide per-request structure — which is exactly what your
   infrastructure needed to see.
3. **Load balancing granularity is a property of connection lifetime, not of the algorithm.**
   No amount of round-robin cleverness fixes one decision.
4. **The old, "worse" protocol was doing you an accidental favour.** HTTP/1.1's churn fed the
   balancer. Be suspicious when an efficiency win removes a source of randomness you were
   depending on.
5. **Every "reconnect periodically" mitigation needs jitter.** Synchronised expiry is a
   thundering herd on a timer.
6. **Protocol choice is per-hop, not per-organisation.** h3 at the edge, h2 with L7 balancing
   internally, h1.1 pooled where it's simpler.
7. **A limit that counts the wrong noun is not a limit.** `MAX_CONCURRENT_STREAMS` was a real
   limit that bounded nothing an attacker cared about.
8. **Yesterday's best practice is tomorrow's anti-pattern when the substrate changes.** Domain
   sharding and concatenation were correct, then harmful, with no announcement.

## Principles in play

| Principle | How this chapter applied it |
|---|---|
| **Name the unit before trusting the metric** | "Connections" stopped proxying for "load"; every dashboard built on it lied without erroring |
| **Every hop is a decision point** | Protocol chosen per hop — client→edge, edge→origin, service→service — not once globally |
| **Efficiency gains have hidden dependents** | Removing handshake churn removed the balancer's supply of decisions |
| **Bound work per unit of client effort** | Rapid Reset: unbounded server work per connection because the accounting noun was wrong |
| **Physics is a constraint, not a target** *(Ch. 1)* | Reappeared as BDP: a 64 KB window over 200 ms RTT caps a stream at 2.6 Mbps regardless of bandwidth |
| **Prefer the free win first** *(Ch. 1)* | Switching round-robin → least-request/P2C costs nothing and corrects continuously |
| **Design for the failure that the feature implies** | h3's migration feature *requires* Connection-ID routing; shipping without it breaks on the event it was built for |
| **Graceful shutdown is part of the protocol** | GOAWAY is not optional politeness; ignoring it drops requests on every deploy |

---

*Next — Chapter 3: REST that survives production. Resource modelling, status codes that mean
something operationally, pagination that doesn't fall apart at page 10,000, and partial
failure — building on the methods/idempotency and status-code groundwork already written in
`basic_networking`.*
