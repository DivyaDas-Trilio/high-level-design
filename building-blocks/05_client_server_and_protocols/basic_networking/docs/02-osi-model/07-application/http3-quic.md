# HTTP/3 & QUIC

> **Status:** 🟡 studying · **Lens:** end-to-end + HLD interview
> **Prereqs:** [[03-tcp]] (in-order delivery, retransmit, congestion), [[04-udp]],
> [[http11-connection-mechanics-hol]] (HTTP/2 frames/streams; TCP-level HoL).
> **OSI layer:** L7 over QUIC (a new L4) over UDP. **Concludes the HoL story.**

## 1. One-liner
HTTP/3 replaces TCP with **QUIC over UDP** — QUIC reimplements TCP's reliability
in **user space** but tracks ordering **per-stream**, so a lost packet stalls only
its own stream (killing TCP-level HoL). It also folds TLS into a **1-RTT/0-RTT**
handshake and supports **connection migration**.

## 2. The problem it solves (all rooted in TCP)
HTTP/2 fixed HTTP-level HoL but three problems remained, all from TCP:
1. **TCP-level HoL** — all streams share one TCP connection; TCP is a single
   ordered byte stream → one lost packet stalls **every** stream until retransmit.
2. **Handshake latency** — TCP handshake **then** TLS handshake = 2–3 RTTs.
3. **Connections die on network change** — a TCP conn = the 4-tuple; change IP
   (Wi-Fi→cellular) and it breaks.
You can't fix TCP-level HoL *on* TCP — its ordered-stream nature is the cause.

## 3. Deep dive

### Why one TCP loss stalls everything (the mechanism)
TCP promises the app an **in-order byte stream**, so the receiver **won't deliver
any byte until all earlier bytes arrive**.
```
Packet1: 1–1000 ✓   Packet2: 1001–2000 LOST   Packet3: 2001–3000 ✓ (arrived!)
Recv-Q:  [1–1000 ✓][ GAP ][2001–3000 ✓]   ← 2001–3000 HELD, undeliverable
```
2001–3000 physically arrived but is held hostage behind the gap until packet 2 is
retransmitted. In HTTP/2 those held bytes are often a **different stream** — but
TCP doesn't know streams, so stream B waits for stream A's loss = **TCP-level HoL**.

### What QUIC is
A new transport protocol on **UDP**, in **user space**, that **reimplements TCP's
machinery** — reliability (seq/ack/retransmit), ordering, flow control (windows),
congestion control (slow start/AIMD) — with two changes:
- **streams are first-class at the transport layer** (QUIC knows stream IDs; TCP didn't)
- **TLS 1.3 is built in** (always encrypted, integrated into the handshake)
HTTP/3 = HTTP semantics over QUIC.

### How QUIC fixes each problem
1. **TCP-level HoL → gone (per-stream ordering).** QUIC orders per stream. A lost
   packet stalls only the stream(s) it carried; other streams' arrived data is
   delivered immediately. (Packets still drop and still retransmit — but no
   cross-stream blocking.)
2. **Handshake → 1-RTT / 0-RTT.** QUIC merges transport + TLS handshake into one
   exchange (1 RTT to a new server vs TCP's ~3). Resumption → **0-RTT** (send data
   in the first packet).
3. **Connection migration.** A QUIC connection is identified by a **Connection ID**,
   not the 4-tuple → survives an IP change (Wi-Fi→cellular). TCP would die.

### Why UDP (not a brand-new protocol)?
- **Ossification:** middleboxes (routers/firewalls/NATs) only reliably pass TCP
  and UDP → a new L4 protocol would be blocked. UDP is the escape hatch.
- **User space = fast evolution:** QUIC ships in the app/library (browser/server),
  not the kernel → improves via app updates, not OS updates. (Same deployability
  story as HTTP/2: upgrade endpoints, leave the network alone.)

### How HTTP/3 is discovered — `Alt-Svc` (live artifact)
Bootstrapping puzzle: the first connection is TCP, so QUIC can't be ALPN-negotiated
up front. Instead:
```
alt-svc: h3=":443"; ma=86400     ← captured live from Cloudflare
```
1. First request over **HTTP/2 (TCP)**.
2. Server sends **`Alt-Svc: h3=":443"`** = "I also speak h3 on UDP:443; remember for
   `ma` seconds."
3. Client then tries **HTTP/3 over UDP** for later requests to that origin.

### The complete HoL story
```
HTTP/1.1  serial on TCP            → HTTP-level HoL   (hack: 6 connections)
HTTP/2    multiplex on 1 TCP conn  → HTTP-level FIXED, TCP-level HoL remains
HTTP/3    QUIC/UDP, per-stream     → BOTH fixed + 1-RTT handshake + migration
```

### Trade-offs
- CPU: user-space congestion control costs more than kernel TCP (improving).
- Some networks throttle/block UDP → falls back to h2/TCP.
- Newer, but widely deployed (Google, Cloudflare, Meta, most browsers).

## 4. Mental model / analogy
HTTP/2 = many conversations sharing one **single-file line** — if the person at the
front trips (lost packet), everyone behind stops. HTTP/3 = each conversation gets
its **own lane**; one person tripping doesn't stop the others.

## 5. Hands-on (visualize)
```bash
curl --version | grep -i HTTP3                  # is curl built with h3? (often not)
curl -sI https://www.cloudflare.com/ | grep -i alt-svc   # h3 advertised via Alt-Svc
# curl --http3 https://cloudflare.com           # needs an h3-capable curl build
```
`curl` here lacks HTTP/3 (no HTTP3 in Features). To capture QUIC: build curl with
ngtcp2/quiche, or use browser devtools (Protocol column shows "h3").

## 6. Common misconceptions
- **"QUIC prevents packet loss."** No — packets still drop and retransmit; QUIC
  prevents one loss from blocking *other* streams.
- **"HTTP/3 is just HTTP/2 on UDP."** It's HTTP over a new transport (QUIC) with
  per-stream delivery, integrated TLS, and migration.
- **"UDP means unreliable HTTP/3."** QUIC rebuilds reliability on top of UDP.
- **"HTTP/3 negotiates via ALPN like h2."** First contact is TCP; discovery is via
  `Alt-Svc` (then ALPN over QUIC on the UDP connection).

## 7. Diagrams needed
1. The Recv-Q gap: held bytes behind a lost packet (TCP) vs per-stream (QUIC).
2. Handshake RTTs: TCP+TLS (2–3) vs QUIC (1, or 0 on resume).
3. Connection migration: Connection ID survives an IP change.
4. Alt-Svc discovery flow (h2/TCP → Alt-Svc → h3/UDP).

## 8. Video script outline
- **Hook** — "HTTP/2 gave us independent streams — so why does one lost packet
  still freeze the whole page?"
- **Build** — TCP in-order delivery → the Recv-Q gap → TCP-level HoL → QUIC
  per-stream on UDP → 1-RTT handshake → migration → Alt-Svc discovery.
- **Payoff** — same loss, only one stream lags; the HoL story is finally complete.
- **Recap** — QUIC/UDP · per-stream ordering · 1-RTT+migration · UDP for
  middleboxes + user-space evolution.

## 9. Brainstorm / open questions
- QUIC's own internals (QUIC packets vs QUIC frames vs HTTP/3 frames; QPACK vs
  HPACK) — a deeper beat if wanted.
- Packet-loss simulation (`dnctl`/`pfctl`) to *watch* TCP HoL stall vs QUIC.
- Ties back: everything learned in [[03-tcp]] reappears inside QUIC (per-stream).

## 10. References
- RFC 9000 (QUIC), RFC 9114 (HTTP/3); "HTTP/3 explained" (Daniel Stenberg);
  Cloudflare/Google QUIC blogs.
