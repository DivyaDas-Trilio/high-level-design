# HTTP Connection Mechanics & Head-of-Line Blocking (→ HTTP/2 fix) ⭐

> **Status:** 🟡 studying · **Lens:** end-to-end + HLD interview (heavyweight)
> **Prereqs:** [[03-tcp]] (handshake, slow start, TCP ordered stream), fd/sockets.
> **OSI layer:** L7 over L4. **Concept 4 of the HTTP/1.1 essentials** (+ the HTTP/2 fix).
> **Ties to:** [[02-http-1-2-3]] (evolution overview), `labs/04-connection-mechanics.md`.

## 1. One-liner
HTTP/1.1 reuses one TCP connection (keep-alive) but serves requests **serially**,
so a slow response **head-of-line-blocks** the rest; browsers hack around it with
~6 connections. **HTTP/2 fixes it** by chopping messages into **frames**, labeling
each with a **stream ID**, and **multiplexing** many streams over one connection.

## 2. The problem it solves
Web pages need many resources at once. HTTP/1.1's serial-per-connection model
makes them queue (slow). The fix (6 connections) is costly in handshakes,
slow-starts, and fds. HTTP/2 gets concurrency over one connection.

## 3. Deep dive

### HTTP/1.1 connection mechanics
- **HTTP/1.0:** new TCP connection per request → pays handshake + TLS + slow start
  every time.
- **HTTP/1.1 keep-alive (default):** reuse **one** connection for many
  **sequential** requests → amortize setup, keep `cwnd` warm.
- **Serial rule:** one request→response at a time per connection. A message is
  **atomic on the wire** — it hogs the connection start-to-finish.

### Head-of-line (HoL) blocking — two layers
| Layer | What blocks | Fixed in |
|---|---|---|
| **HTTP-level** | slow response blocks requests behind it on the connection | **HTTP/2** |
| **TCP-level** | one lost packet stalls all streams (TCP = single ordered stream) | **HTTP/3** (QUIC/UDP) |

**LIVE DEMO — HTTP-level HoL (captured):** three `/delay/2` requests:
```
one reused connection (serial):   ~7.6s      ← HoL: they queue
three separate connections:       ~3.0s      ← overlap (browser's 6-conn trick)
HTTP/2, one connection (-Z):      ~3.8s      ← multiplexed, no 6-conn hack
```

### The HTTP/1.1 workarounds (hacks, not fixes)
- **Pipelining** — send many requests without waiting, but responses return
  **in order** → HoL remains; buggy → browsers disabled it.
- **~6 parallel connections per origin** — real concurrency, but 6× handshakes/
  slow-starts/fds.
- **Domain sharding** — assets across subdomains to exceed 6. Obsolete post-HTTP/2.

### HLD angles
- **Connections = fds.** Each connection = an fd (+ buffers) on client, LB, server.
  Keep-alive holds them open → too many idle → **fd/memory exhaustion**
  (`ulimit -n`, the **C10k problem**). Verify: `lsof -nP -iTCP:PORT | wc -l`.
- **Keep-alive timeout tuning** — hold idle conns (reuse) vs free them (resources).
- **Connection pooling** — services keep a warm pool of downstream connections.

## 4. How HTTP/2 fixes HTTP-level HoL — frames, streams, multiplexing

**Frame** = a small binary chunk of a message. Every frame has a **9-byte header**:
```
Length (3B) | Type (1B: HEADERS/DATA/SETTINGS/…) | Flags (1B) | Stream ID (4B) | Payload
```
- **Length** → receiver knows exactly where the frame ends (no delimiters).
- **Stream ID** → the label saying which message this frame belongs to.

**Stream** = one request/response exchange, identified by a stream ID. Client
requests = **odd** IDs (1,3,5…), server push = **even**, **0** = connection-level
(SETTINGS/WINDOW_UPDATE). Many streams coexist on one connection.

**Multiplexing** = interleaving frames from many streams on one connection; the
receiver sorts them back into messages by stream ID.

### How a message becomes frames (the breakdown)
Sender: pick next odd stream ID → headers → **HEADERS frame** (HPACK-compressed;
overflow → CONTINUATION) → body cut into ≤ `SETTINGS_MAX_FRAME_SIZE` (default
16 KB) chunks → **DATA frames** → set **END_STREAM** flag (0x1) on the last.
Receiver: read 9-byte header {Length,Type,Flags,StreamID} → read Length bytes →
route by Stream ID (HEADERS→HPACK-decode; DATA→append to body) → END_STREAM =
message complete. Interleaved frames reassemble correctly because each is
self-describing (length + stream ID).

**LIVE DEMO — body chopped into DATA frames** (`nghttp -vn .../bytes/50000`):
```
recv DATA <length=8192, stream_id=1>  (×several, summing to 50000)
recv DATA <length=0, flags=0x01, stream_id=1>   ← END_STREAM
```

**LIVE DEMO — multiplexing beats HoL** (`nghttp -vn /delay/1 /get`):
```
[0.7] send HEADERS stream_id=1   (slow) ┐ both sent at the same instant
[0.7] send HEADERS stream_id=3   (fast) ┘
[0.9] recv HEADERS/DATA stream_id=3      ← FAST returns FIRST (out of order!)
[2.0] recv HEADERS/DATA stream_id=1      ← slow returns later, never blocked the fast one
```
The fast request (stream 3) finished while the slow (stream 1) was still pending —
HTTP-level HoL gone. `stream_id` is what lets responses return out of order.

### Where this logic lives (crucial)
- **Endpoints only:** framing/streams/multiplexing/HPACK are **user-space L7**
  code in the HTTP/2 client & server libraries (e.g. nghttp2), **on top of the
  kernel's plain TCP byte stream** (kernel knows nothing about frames).
- **Negotiated:** via **ALPN** in the TLS handshake (`h2`), with **HTTP/1.1
  fallback**; then SETTINGS frames exchange parameters.
- **Network is oblivious:** routers/switches/L4 LBs just forward TCP bytes — only
  endpoints parse frames. *That's why HTTP/2 only needed endpoint upgrades, not
  kernel/router changes.* (An **L7** proxy that terminates HTTP does parse it —
  it's acting as an endpoint.)

### Still remaining: TCP-level HoL → HTTP/3
HTTP/2's streams still ride ONE TCP connection; TCP is a single ordered stream,
so one lost packet stalls ALL streams. HTTP/3 moves to **QUIC over UDP** with
**per-stream** ordering → a loss blocks only its own stream. (Also user-space,
so same deployability story.)

## 5. Hands-on (visualize)
```bash
# keep-alive reuse:
curl -v http://localhost:8010/fast http://localhost:8010/fast 2>&1 | grep -iE 'Connected|Re-using'
# HoL: serial (one conn) vs parallel:
time curl -s -o /dev/null localhost:8010/slow localhost:8010/slow localhost:8010/slow
time ( curl -s -o /dev/null localhost:8010/slow & curl -s -o /dev/null localhost:8010/slow & curl -s -o /dev/null localhost:8010/slow & wait )
# HTTP/2 streams & frames:
curl -v --http2 -Z https://httpbin.org/get https://httpbin.org/get 2>&1 | grep -E 'OPENED stream|Re-using'
nghttp -vn https://httpbin.org/get                      # frame trace (HEADERS/DATA/SETTINGS)
nghttp -vn https://httpbin.org/delay/1 https://httpbin.org/get | grep -E 'HEADERS frame|DATA frame'
nghttp -vn https://httpbin.org/bytes/50000 | grep 'DATA frame'   # body chopped
# connections = fds:
lsof -nP -iTCP:8010
```
(local server: `basic_networking/scripts/hol_demo_server.py`)

## 6. Common misconceptions
- **"Keep-alive = concurrent."** No — one connection is still serial; keep-alive
  just reuses it sequentially.
- **"Pipelining fixed HoL."** No — responses stay in order; it was disabled.
- **"HTTP/2 uses many connections."** Opposite — ONE connection, many streams.
- **"A message breaks into streams."** A message = ONE stream, broken into FRAMES.
- **"The kernel/routers understand HTTP/2."** No — endpoints (user-space libs) do;
  the network forwards TCP bytes.
- **"HTTP/2 removed all HoL."** Only HTTP-level; TCP-level HoL remains (→ HTTP/3).

## 7. Diagrams needed
1. Single-lane belt (HTTP/1.1, whole messages) vs interleaved boxes (HTTP/2 frames).
2. The 9-byte frame header fields.
3. Timeline: fast stream 3 overtaking slow stream 1 (from the nghttp demo).
4. Where framing lives: endpoints (user space) vs oblivious network.

## 8. Video script outline
- **Hook** — "your page loads 50 files over one connection. Why is HTTP/1.1 slow?"
- **Build** — keep-alive → serial → HoL (6s vs 2s demo) → 6-connection hack →
  HTTP/2 frames/streams/multiplexing → the stream-3-overtakes-stream-1 trace →
  where it lives (endpoints, user space).
- **Payoff** — one connection, many interleaved streams, fast beats slow → HoL gone.
- **Recap** — keep-alive reuses · serial = HoL · frames+streamID+multiplexing = fix ·
  endpoints only.

## 9. Brainstorm / open questions
- HPACK (header compression) deserves its own beat (interview-relevant).
- TCP-level HoL → HTTP/3/QUIC as the follow-on.
- C10k / connection pooling is a rich HLD sub-thread.

## 10. References
- Labs: `labs/04-connection-mechanics.md`; scripts/hol_demo_server.py.
- RFC 9113 (HTTP/2); nghttp2.org docs; "High Performance Browser Networking" (Grigorik).
