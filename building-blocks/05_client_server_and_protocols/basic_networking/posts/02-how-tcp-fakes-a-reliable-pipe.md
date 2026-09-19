# How TCP Fakes a Reliable Pipe

### IP loses packets, duplicates them, and delivers them out of order. Your file download arrives perfect anyway. Here's the machinery — and the price you pay for it.

---

In the [last post](#) we followed a `curl` request from a URL string to a byte queue on a server. We treated one part as a black box: the bit where bytes reliably arrive, in order, complete.

That's TCP, and it's worth opening up — because everything underneath it is genuinely unreliable, and the illusion it maintains has costs that show up in your latency graphs.

## The problem TCP exists to solve

The layer below TCP is IP, and IP promises almost nothing. It is **best-effort delivery**:

- Packets get **lost** — a router's queue overflows, a link flaps
- Packets arrive **out of order** — two packets can take different paths
- Packets get **duplicated** — a retransmission crosses paths with the original
- Packets get **corrupted** — checksums catch it, then they're dropped

Yet you download a 2 GB file and every byte is correct, in the right position. TCP builds that guarantee on top of a network that offers none of it.

It does this with four mechanisms. They're each simple; the interesting part is what each one *costs*.

---

## 1. "Synced" — the handshake exchanges starting numbers

The famous three-way handshake is usually explained as "establishing a connection." That's true but unhelpfully vague. What it actually does is **agree on where counting starts.**

Each side picks a random **Initial Sequence Number** and tells the other:

```
client ──── SYN, seq=X ─────────▶      "my bytes start at X"
       ◀─── SYN-ACK, seq=Y, ack=X+1 ── "mine start at Y, and I got your X"
       ──── ACK, ack=Y+1 ───────▶      "got your Y"
```

That's what the S in SYN means: **synchronize**. Not "connect" — *synchronize sequence numbers.* After this, both sides know each other's numbering origin, and every byte that follows has an unambiguous position.

**The cost:** one full round-trip before a single byte of your data moves. On a link with 200 ms RTT — say Bangalore to Virginia — that's 200 ms spent before "hello" can leave. Add TLS on top and you're at 600 ms before the request is even sent.

This is why connection reuse matters so much. HTTP keep-alive exists precisely to avoid paying this again.

---

## 2. "Ordered" — every *byte* is numbered, not every packet

This is the detail that makes TCP click, and it's frequently taught wrong.

**TCP does not number packets. It numbers bytes.**

A TCP connection is a single continuous byte stream. Byte 1, byte 2, byte 3... up to 4 billion (then it wraps). Segments are just how the stream gets chopped for transmission, and each segment's header says "my bytes start at sequence number N."

So the receiver can always reconstruct the correct order, regardless of what arrives when:

```
sent:      [seq 1: bytes 1-1000] [seq 1001: bytes 1001-2000] [seq 2001: bytes 2001-3000]
arrived:   [seq 2001] ... [seq 1] ... [seq 1001]      ← scrambled by the network
delivered: bytes 1 ... 3000 in perfect order          ← the app sees this
```

Out-of-order segments go into a **reassembly buffer** and wait there until the gap fills.

**The consequence people miss:** because TCP is a byte stream with no message boundaries, **TCP cannot tell your application where one message ends and the next begins.** That's not a limitation — it's the design. Message framing is the application's job, which is exactly why HTTP needs `Content-Length` or `Transfer-Encoding: chunked`.

If you've ever written a socket server and been surprised that one `read()` returned half a message — or two messages stuck together — this is why. The stream has no seams.

---

## 3. "Nothing lost" — cumulative ACKs and retransmission

The receiver continuously reports its progress with **cumulative acknowledgements**. `ACK = N` means: *"I have every byte up to N−1. Send me N."*

That single rule is remarkably powerful, because a gap is self-announcing:

```
sender:  seq 1    (bytes 1–1000)        ──▶  received ✓
         seq 1001 (bytes 1001–2000)     ──▶  LOST
         seq 2001 (bytes 2001–3000)     ──▶  received ✓

receiver: got 1     → "ACK 1001"   (I have everything up to 1000)
          got 2001  → "ACK 1001"   ← AGAIN. A duplicate ACK.
```

The receiver *has* bytes 2001–3000. It buffers them. But it cannot say "ACK 3001," because that would claim it has 1001–2000, which it doesn't. So it repeats "ACK 1001."

**A duplicate ACK is the receiver saying: I'm still missing something.** Two mechanisms act on that:

- **Three duplicate ACKs** → the sender does a **fast retransmit** of the missing bytes immediately, without waiting for a timer.
- **No ACK at all within the retransmission timeout (RTO)** → the sender retransmits anyway. This is the slow path, and it's a cliff: RTO is typically hundreds of milliseconds to seconds.

Because the sender must be able to resend anything unacknowledged, **it keeps a copy of all unacked data in its Send-Q.** That's not just a transmit buffer; it's a retransmission buffer.

---

## 4. "No more coming" — and this one has two answers

How does a receiver know the data is finished? TCP answers this at only one level:

**Level 1 — the connection is done.** A `FIN` flag carries a sequence number, so it's positioned exactly in the stream. Everything before it is guaranteed delivered. `FIN` means "no bytes after this."

**Level 2 — this *message* is done.** TCP has nothing to say here. It's a byte stream.

On a keep-alive HTTP connection, the connection stays open across many requests — so `FIN` can't delimit them. The application must:

```http
Content-Length: 1847              ← read exactly 1847 more bytes
```
or
```http
Transfer-Encoding: chunked        ← read chunks until one has size 0
```

**TCP frames nothing. HTTP frames messages.** Two different jobs, and confusing them is the source of a whole genre of bugs.

---

## The price: head-of-line blocking

Here's where the illusion costs you something real.

TCP promises the application an **in-order byte stream**. To keep that promise, it **will not deliver any byte until all earlier bytes have arrived.**

```
Packet 1: bytes 1–1000     ✓ arrived
Packet 2: bytes 1001–2000  ✗ LOST
Packet 3: bytes 2001–3000  ✓ ARRIVED

Recv-Q:  [1–1000 ✓][   GAP   ][2001–3000 HELD HOSTAGE]
                                        ▲
                     physically in memory, perfectly intact,
                     undeliverable until packet 2 is retransmitted
```

Bytes 2001–3000 made it. They're sitting in the server's RAM. The application cannot have them, because handing them over would break ordering.

That's **head-of-line blocking**, and it is the direct cost of TCP's central promise.

### Why this became a big deal

Under HTTP/1.1, one connection carried one request at a time, so a stall only affected that request. Fine.

Then HTTP/2 arrived and multiplexed many independent streams over a single TCP connection — a real improvement, since it eliminated *HTTP-level* head-of-line blocking (a slow response no longer blocks the requests queued behind it).

But all those streams still ride one TCP connection. **TCP doesn't know streams exist.** So one lost packet belonging to stream A stalls the delivery of stream B, stream C, and everything else — even though their data arrived perfectly.

You cannot fix this *within* TCP. The ordered-byte-stream guarantee is the cause.

**So HTTP/3 left TCP.** It runs on QUIC over UDP, reimplementing reliability, ordering, and congestion control in user space — but tracking ordering **per stream**. A lost packet now stalls only the stream it belonged to. Everything else is delivered immediately.

That's the whole reason QUIC exists. Not "UDP is faster" — UDP is a blank canvas that let them rebuild the ordering rules.

---

## Two more mechanisms you'll meet in production

### Flow control — don't drown the receiver

The receiver's Recv-Q is finite, and it only drains when the application calls `read()`. A fast sender could easily overrun a slow reader.

So every ACK carries a **window** field: *"I have this many bytes of free space right now."*

```
[==== ACKed ====][==== sent, unACKed ====][== may send ==][== blocked ==]
                 ▲                                        ▲
              last ACK                          last ACK + window
```

The rule: **unacknowledged bytes in flight ≤ the receiver's advertised window.** As the app reads and frees space, the window reopens and the sender may continue. If the app stops reading entirely, the window hits **zero** and the sender stops dead, sending periodic probes until space appears.

**This is why a write can block.** If you've used async Python, `await writer.drain()` is waiting on exactly this — the receiver is slow, your Send-Q is full, and backpressure has propagated all the way back to your code.

### Congestion control — don't drown the network

Flow control protects the receiver's buffer. It says nothing about a congested router three hops away, which is a different problem and once nearly killed the internet (the congestion collapse of 1986).

The difficulty: **nobody advertises the network's capacity.** There's no field for it. The sender has to *infer* it, and the signal it uses is **packet loss** — a dropped packet implies a queue overflowed somewhere.

So the sender maintains a second, self-invented limit, the **congestion window**, and the real send limit is `min(receiver window, congestion window)`.

The classic algorithm:

- **Slow start** — begin small, **double** the window every round-trip. (Exponential. The name is misleading.)
- **Congestion avoidance** — past a threshold, grow by one segment per round-trip. Creep carefully.
- **Three duplicate ACKs** (mild signal) — halve the window, keep going.
- **Timeout** (severe signal) — collapse to minimum, restart slow start.

That asymmetry — gentle additive increase, harsh multiplicative decrease — is what makes competing flows converge on a fair share of a link with no coordinator anywhere. It's a genuinely beautiful piece of distributed systems design hiding inside a protocol from 1981.

**And note that loss does double duty:** a lost packet triggers *both* a retransmission (reliability) *and* a window reduction (congestion control). One event, two independent reactions.

### The part that shows up in your latency graphs

Slow start means **a new connection cannot use your bandwidth immediately.** On Linux the initial window is 10 segments ≈ **14.6 KB**:

| Round-trips | Cumulative data deliverable |
|---:|---:|
| 1 | 14.6 KB |
| 2 | 43.8 KB |
| 3 | 102 KB |
| 4 | 219 KB |

At 200 ms RTT, a 100 KB response needs **three round-trips of window growth** — 600 ms — no matter how fat the pipe is. Upgrading a 1 Gbps link to 10 Gbps changes this number not at all.

This is where the "keep your critical response under 14 KB" advice comes from. And it's another argument for connection reuse: a warm connection has already grown its window; a new one starts from scratch every time.

---

## What you actually get for all this

TCP gives your application a clean abstraction: write bytes here, the same bytes appear there, in order, exactly once. It is a genuinely excellent abstraction, and it is a *lie* maintained by a lot of machinery.

The price list:

| What you get | What it costs |
|---|---|
| Synchronized sequence numbers | 1 RTT before any data |
| Perfect ordering | **head-of-line blocking** — one loss stalls everything behind it |
| Guaranteed delivery | buffering unacked data; retransmission delays on a lost packet |
| A safe network | slow start — bandwidth isn't available immediately |
| A protected receiver | writes can block (backpressure) |

Every one of those costs is why a modern alternative exists. UDP drops the whole package when you'd rather lose a video frame than wait for it. QUIC keeps the guarantees but reorganizes them per-stream so a single loss can't stall everything.

Knowing the price list is what lets you choose.

---

*Next: the bytes have arrived in Recv-Q — but the server application is fast asleep, and nothing anywhere is polling. So who wakes it up? (Spoiler: the answer is a hardware interrupt, and there's no loop involved.)*
