# UDP

> **Status:** 🟡 studying
> **Prereqs:** [[03-tcp]] (defined by contrast), [[00-overview]].
> **OSI layer / where it lives:** Transport (L4).
> **Est. depth:** medium — mostly "what TCP does that this doesn't."

## 1. One-liner
UDP = **IP + ports + a checksum, nothing else** — does the transport layer's
Job 1 (deliver to the right *process* via ports) and a corruption check, then
gets out of the way. None of TCP's reliability (Job 2). Fire-and-forget datagrams.

## 2. The problem it solves
Not every app wants TCP's reliability-at-the-cost-of-latency. Some need **low
latency** (loss is tolerable) or want to **build their own** transport. UDP is
the minimal option: process addressing + integrity check, zero overhead beyond that.

## 3. Deep dive — the mechanism

### The header (8 bytes) vs TCP (20+)
```
UDP:  Source Port | Dest Port | Length | Checksum      (8 bytes)
TCP:  + Seq | Ack | Flags | Window | ... (all reliability machinery)
```
UDP keeps only **ports** (demux to a process), **length**, **checksum** (bad → drop).

### What UDP does NOT do (all of TCP)
- ❌ handshake / connection (just send; no setup RTT, no state)
- ❌ sequence numbers → no ordering
- ❌ ACKs / retransmission → lost datagrams are gone
- ❌ flow control (no `rwnd`) · ❌ congestion control (no `cwnd`)
Datagrams may be lost, duplicated, reordered, or dropped-if-corrupt. Any
guarantee the app needs, the **app** must implement.

### The other big difference: message-oriented, not stream
| | TCP | UDP |
|---|---|---|
| model | **byte stream** (no boundaries) | **datagrams** (discrete messages) |
| one `send` | bytes into a stream | **one self-contained message** |
| boundaries | lost → app must frame (Content-Length) | **preserved** (1 `sendto` = 1 `recvfrom`) |

UDP hands you message boundaries for free — no `Content-Length` framing needed
per datagram. (Caveat: datagrams > MTU get IP-fragmented; lose one fragment →
lose the whole datagram, so keep them small.)
**Two axes of difference:** reliability (TCP yes/UDP no) AND framing
(TCP stream / UDP message).

### Connectionless socket API
- TCP: `connect` / `bind→listen→accept`, then `read`/`write` on a connected socket.
- UDP: `socket → sendto(data, addr)` / `recvfrom()` — address per message; no
  `accept`, no handshake. (`connect()` on UDP just sets a default peer.)

## 4. When to use it (and why)
- **DNS** — one tiny req/resp; a TCP handshake would cost more than the query.
- **DHCP** — no IP yet; connectionless/broadcast fits.
- **Real-time media (voice/video)** — a lost frame is better **skipped** than
  delayed; TCP would stall retransmitting stale data (head-of-line blocking).
- **Gaming** — want the *latest* state; a resent stale update is useless.
- **QUIC / HTTP/3** — runs on UDP and **reimplements** reliability/ordering/
  congestion in user space to escape TCP's limits (no kernel HoL, faster
  evolution, 0-RTT). UDP = a blank canvas (just ports) to build a new transport on.

### Decision
Need every byte, in order, guaranteed, and can tolerate handshake+retransmit
latency → **TCP**. Latency-critical / loss-tolerant / rolling your own → **UDP**.

## 5. Hands-on
```bash
# DNS is UDP — watch a query/response on port 53:
sudo tcpdump -i any -n 'udp port 53' &
dig example.com
# Send a raw datagram:
echo "hi" | nc -u -w1 127.0.0.1 9999      # -u = UDP
```

## 6. Common misconceptions
- **"UDP = broken TCP."** No — it's a *different tool*: message-oriented, minimal,
  for when latency/self-control beats guarantees.
- **"UDP has no boundaries like TCP."** Opposite — UDP **preserves** message
  boundaries; TCP is the boundary-less stream.
- **"UDP is always faster."** Lower overhead, but no congestion control means it
  can *cause* congestion; not a free lunch at scale.
- **"UDP and ICMP/ping are the same kind of thing."** Both connectionless, but
  ICMP is **L3, no ports**; UDP is **L4, with ports**.

## 7. Diagrams needed
1. UDP vs TCP header side by side (8 vs 20+ bytes).
2. Stream vs datagram (boundaries preserved vs not).
3. The two-axis map: reliability × framing.

## 8. Video script outline
- **Hook** — "TCP guarantees delivery. So why does your video call use something
  that doesn't?"
- **Build** — the 8-byte header → what it drops (all of TCP) → datagram vs stream
  → the use cases (media/DNS/gaming/QUIC).
- **Payoff** — the decision framework; QUIC building its own transport on UDP.
- **Recap** — ports + checksum only · no guarantees · message-oriented · choose
  it for latency or to build your own.

## 9. Brainstorm / open questions
- Lead with the **two axes** (reliability × framing) — cleaner than "UDP =
  unreliable TCP."
- Ties forward: DNS/DHCP (app topics) use UDP; QUIC/HTTP3 builds on it.

## 10. References
- RFC 768 (UDP); Kurose & Ross ch. 3.
- [[03-tcp]] for the contrast; [[04-udp]] use cases feed the DNS/DHCP topics.
