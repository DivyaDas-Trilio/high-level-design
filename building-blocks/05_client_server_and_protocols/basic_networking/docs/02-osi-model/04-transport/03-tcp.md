# TCP

> **Status:** 🟡 studying
> **Prereqs:** [[00-overview]] (encapsulation), sockets/fd/buffers, the
> packet-lifecycle capstone. Head start from earlier socket deep-dives.
> **OSI layer / where it lives:** Transport (L4).
> **Est. depth:** deep — this is the reliability engine of the internet.

## 1. One-liner
TCP turns IP's **unreliable, unordered packet** service into a **reliable,
ordered, complete byte stream** between two processes — using a handshake to sync
sequence numbers, per-byte sequence numbers to order, and cumulative ACKs +
retransmission to guarantee delivery.

## 2. The problem it solves
IP (L3) only does best-effort delivery: packets can be **lost, duplicated,
reordered, or corrupted**. Most apps (HTTP, SSH, DBs) need "the bytes I sent
arrive exactly once, in order, complete." TCP provides that on top of IP, so the
app can pretend it has a clean pipe.

## 3. Deep dive — the mechanism

### How the receiver knows it's synced / ordered / complete (the core)

**"Synced" — the handshake synchronizes sequence numbers (SYN = synchronize).**
Each side picks a random **Initial Sequence Number (ISN)** and announces it:
- SYN: client → "my bytes start at **X**"
- SYN-ACK: server → "mine start at **Y**, got your X (ack=X+1)"
- ACK: client → "got your Y (ack=Y+1)"
Both now know each other's numbering origin → *synchronized*.

**"Ordered" — sequence numbers on every BYTE.**
TCP numbers every byte (not every packet). Each segment says "my bytes start at
seq N." The receiver reorders out-of-order segments via seq numbers; out-of-order
pieces wait in a **reassembly buffer** until their slot fills. The app only ever
sees an in-order stream.

**"Nothing lost" — cumulative ACK + retransmission.**
Receiver sends cumulative ACKs: "ACK=N" = *"I have everything up to N−1; send N."*
```
Sender: seq1(1–1000)  seq1001(1001–2000 LOST)  seq2001(2001–3000)
recv seq1     → ACK 1001
recv seq2001  → buffer it, ACK 1001 AGAIN   ← duplicate ACK = "gap! I need 1001"
```
- A **gap in seq numbers** = the receiver knows a packet is missing.
- **3 duplicate ACKs** → sender does **fast retransmit** of the missing bytes.
- **No ACK within timeout (RTO)** → sender retransmits anyway.
- Receiver advances its ACK only when data is **contiguous** → nothing skipped.
The sender keeps unacked data buffered precisely so it can resend.

**"No more coming" — TWO levels (TCP is a byte STREAM, no message boundaries):**
1. End of the whole connection → **FIN** (carries a seq number) = "no bytes after
   this." TCP guarantees you have everything up to the FIN.
2. End of one message on a reused (keep-alive) connection → the **application**
   delimits it: HTTP `Content-Length` (read exactly N body bytes) or
   `Transfer-Encoding: chunked` (zero-size chunk = done). *This is why the
   stage1 TODO-7 body-framing mattered.* TCP frames nothing; HTTP frames messages.

### Connection lifecycle
- **Born:** 3-way handshake (`connect()`/`accept()`), states → **ESTABLISHED**.
- **Data:** bytes flow via socket Send-Q/Recv-Q; seq/ack keep it reliable.
- **Dies:** 4-way close (FIN/ACK/FIN/ACK) → FIN_WAIT / CLOSE_WAIT / LAST_ACK /
  **TIME_WAIT** (~2×MSL) → CLOSED. See the packet-lifecycle capstone.

### Flow control (the sliding window)
Protects a **slow receiver** from a **fast sender**. The receiver's `Recv-Q` is
fixed-size and only drains when the app `read()`s. If the sender outruns it,
bytes overflow and drop. Fix: the receiver advertises its free space.

- Every ACK carries a **Window** field = the **receive window `rwnd`** = "free
  bytes in my Recv-Q right now."
- Rule: **sender's in-flight (unacked) bytes ≤ `rwnd`.**
- **Sliding window** — as ACKs arrive (app drained the buffer), the window's left
  edge advances → opens room on the right → more data becomes sendable:
  ```
  [== ACKed ==][== sent, unACKed (≤ rwnd) ==][== may send ==][== blocked ==]
               ^ last ACK                    ^ last ACK + rwnd
  ```
- **Zero window:** Recv-Q full → `rwnd=0` → sender STOPS; sends periodic **window
  probes**; receiver sends a **window update** when the app frees space.
- **This is what `await writer.drain()` waits on.** `write()` fills your Send-Q;
  the kernel drains it only as fast as the receiver's window allows; if the
  receiver is slow, your Send-Q fills and `drain()` blocks. Flow control is
  **why "write" can block** — backpressure from a slow consumer.
- **Flow vs congestion:** flow control protects the *receiver's buffer* (`rwnd`);
  congestion control protects the *network* (`cwnd`). Sender limit =
  `min(rwnd, cwnd)`.

### Congestion control (protect the network)
Protects the **shared network** (routers/links between the hosts), not the
receiver. Flow control alone can't — it says nothing about a congested router
three hops away. If every sender blasts: router queues overflow → drops →
everyone retransmits → more traffic → **congestion collapse** (happened in 1986).
Fix: senders voluntarily moderate.

- **The challenge:** nobody advertises the network's capacity (no field). The
  sender must **infer** it. Signal: **packet loss = a router queue overflowed =
  congestion.** (Modern algos also use rising **delay** as an earlier signal.)
- **`cwnd`** — a second window the **sender invents** = its guess of what the
  network can absorb. Real limit = **`min(rwnd, cwnd)`** (receiver vs network).
- **Algorithm (Reno/NewReno):**
  - **Slow start** — start small, **double `cwnd` every RTT** (exponential; probes
    fast despite the name) until `ssthresh`.
  - **Congestion avoidance** — then grow **+1 per RTT** (linear; creep near the limit).
  - **On 3 duplicate ACKs** (mild) → **halve `cwnd`**, continue (fast recovery).
  - **On timeout** (severe) → `cwnd` → minimum, restart slow start.
- **AIMD** (Additive Increase, Multiplicative Decrease): gentle up (+1/RTT), hard
  cut (×0.5 on loss). The asymmetry makes competing flows **converge to fair,
  equal shares** with no coordinator.
- **Loss does double duty:** 3-dup-ACK / timeout trigger BOTH retransmission
  (reliability) AND `cwnd` shrink (congestion). One event, two reactions.
- **Consequence you feel:** every new connection starts in slow start → can't use
  full bandwidth immediately → *why* **HTTP keep-alive / connection reuse** and
  **HTTP/2 multiplexing over one connection** matter (avoid paying slow-start
  repeatedly); motivates **HTTP/3/QUIC** 0-RTT.
- **Modern:** **CUBIC** (Linux default, high-BDP curve), **BBR** (models
  bandwidth×delay instead of waiting for loss).

### What TCP costs (to expand → motivates UDP / QUIC)
- Handshake latency; **head-of-line blocking** (one lost segment stalls all later
  bytes); per-connection state. Motivates [[04-udp]] and later QUIC/HTTP3.

## 4. Mental model / analogy
Sending a long letter as numbered pages. Numbered pages = seq numbers (reader
reorders). "Got pages up to 12, send 13" = cumulative ACK. A missing page → reader
keeps asking for it → you resend. "The End" on the last page = FIN. How the reader
knows one *chapter* ends (vs the whole book) = the chapter heading = the app's
Content-Length.

## 5. Hands-on (what to show on screen)
```bash
# Watch seq/ack, flags, window on a real connection:
sudo tcpdump -i lo0 -n 'tcp port 8000'          # against miniapi/stage1_server.py
# Look for: [S] SYN, [S.] SYN-ACK, [.] ACK, [P.] data, [F.] FIN; seq/ack numbers.
netstat -an -p tcp | grep 8000                   # states: LISTEN/ESTABLISHED/TIME_WAIT
# Force retransmission visibility: throttle/drop with `dnctl`/`pfctl` (advanced).
```

## 6. Common misconceptions
- **"TCP sends packets."** TCP sends a **byte stream**; segments are just how it's
  chunked. It numbers *bytes*, not packets.
- **"TCP knows where my message ends."** No — it's a stream. Message boundaries are
  the app's job (Content-Length/chunked/close).
- **"An ACK means the app received it."** ACK means the *kernel/TCP* received it and
  buffered it — the app may not have `read()` it yet.
- **"The handshake sends data."** SYN/SYN-ACK/ACK carry no app data; they sync seq
  numbers. Data flows after ESTABLISHED. (Exception: TCP Fast Open.)
- **"Flow control = congestion control."** Flow = don't overrun the *receiver*;
  congestion = don't overrun the *network*.

## 7. Diagrams needed
1. **Handshake** — SYN/SYN-ACK/ACK with ISN exchange (the "sync").
2. **Seq/ACK with a loss** — the duplicate-ACK → fast-retransmit sequence.
3. **Byte stream vs segments** — one stream numbered per byte, sliced into segments.
4. **State machine** — CLOSED → LISTEN/SYN_SENT → ESTABLISHED → …→ TIME_WAIT.
5. **Window** — receiver buffer filling/draining (flow control).

## 8. Video script outline
- **Hook (0:00)** — "IP loses, reorders, and duplicates packets. So how does your
  file download arrive perfect? TCP."
- **Build** — the problem (IP is unreliable) → handshake syncs seq numbers →
  per-byte seq = ordering → cumulative ACK + retransmit = completeness → FIN vs
  Content-Length = "done" → (then) window = flow control.
- **Payoff** — the loss-and-recovery animation; the app got a perfect stream.
- **Recap (3 bullets)** — sync (handshake) · order (seq numbers) · guarantee
  (ACK + retransmit); message end = app's job.

## 9. Brainstorm / open questions
- Great motivating question that led here: *"how does the destination know all
  packets are ordered and none are left?"* — open the video on exactly that.
- Depth to schedule: RTO timers, sliding window details, congestion control
  (slow start / AIMD), head-of-line blocking → sets up HTTP/2 & HTTP/3.
- Strong contrast episode: TCP vs [[04-udp]] side by side.

## 10. References
- Packet-lifecycle capstone: `docs/05-packet-lifecycle/packet-lifecycle-end-to-end.md`
- RFC 9293 (TCP); Kurose & Ross ch. 3 (reliable data transfer, TCP).
- Beej's Guide to Network Programming (sockets side).
