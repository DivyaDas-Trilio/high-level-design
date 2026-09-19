# Request Lifecycle in uvicorn — Above the Socket, Step by Step

> **Status:** 🟡 studying (companion capstone — picks up where the packet lifecycle stops)
> **Prereqs:** [[packet-lifecycle-end-to-end]] (phases A–G, the socket boundary),
> [[03-tcp]] (handshake, Recv-Q, flow control), [[http11-connection-mechanics-hol]].
> **OSI layer / where it lives:** **L7 and the user/kernel boundary.** The packet-lifecycle
> doc ends at *"the kernel owns L4→L1; L7 is your app"* — **this doc is that L7 half.**
> **Est. depth:** deep. Built by tracing one `curl` and correcting every assumption out loud.

## 1. One-liner
`curl` → kernel does the handshake by itself → bytes land in a connected socket's Recv-Q →
the **kernel interrupts and wakes** a sleeping event loop → uvicorn `accept()`s, parses the byte
stream with httptools, builds a **`scope` dict**, schedules a **Task**, and calls
`app(scope, receive, send)` — and everything from there is your Python.

## 2. The problem it solves
`tcpdump` shows the wire. `netstat`/`lsof` show the sockets. **Neither shows what happens
between "bytes are in Recv-Q" and "my handler runs."** That gap is where the event loop,
kqueue, the parser, and the ASGI contract live — and it is where every "why is my FastAPI slow"
question is actually answered.

---

## 3. Deep dive — the trace, step by step

Format: **the claim** as stated while reasoning it out, then **what's actually true**. The
corrections are the valuable part; they are the mental model being repaired in real time.

### PHASE 0 — Before anything: the server starts

#### Step 0.1 — "Running uvicorn creates an event loop which generates the fd that accepts connections"

**Correction — inverted order, and two different objects.** The loop does not create sockets.

```
1. asyncio.run(main())        → creates the EVENT LOOP (which itself opens a KQUEUE fd → fd 3)
2. socket() → bind() → listen(backlog)   → creates the LISTENING SOCKET fd   ← syscalls
3. the loop REGISTERS that fd with its kqueue
4. the loop sleeps in kevent()
```

The socket is a **kernel** object made by syscalls. The loop is a **user-space** scheduler that
watches it. The loop is handed sockets; it doesn't make them.

`asyncio.start_server(handle_client, HOST, PORT)` does steps 2–3 in one call — it is exactly
what uvicorn does, via a different asyncio API:

| Streams API (what you'd write) | Protocol API (what uvicorn uses) |
|---|---|
| `asyncio.start_server(cb, host, port)` | `loop.create_server(lambda: HttpToolsProtocol(...), ...)` |
| `handle_client(reader, writer)` — a coroutine per connection | a `HttpToolsProtocol` **instance** per connection |
| `data = await reader.read(n)` — **you pull** | `def data_received(self, data)` — **the loop pushes** |
| `writer.write(b)` / `await writer.drain()` | `transport.write(b)` / `pause_writing()` |

Streams park a coroutine on every read; protocols get called the instant bytes arrive. Push is
cheaper, which is why a server uses it.

#### Step 0.2 — What exists now, before any client

```bash
lsof -nP -iTCP:8000
# Python 16411 ... 10u IPv4 ... TCP 192.168.1.41:8000 (LISTEN)
```

**One socket, fd 10.** Zero would mean it never bound; two would appear with
`--host localhost`, which resolves to both `127.0.0.1` and `::1` (one socket per family).

Also created but invisible to `lsof`: the **accept queue** (`listen(fd, backlog)`;
uvicorn's `--backlog`, default 2048). When it fills, the kernel **silently drops SYNs** — no
RST — so clients hang and time out rather than being refused.

And the process is **blocked in `kqueue()`**, zero CPU, one thread.

> **Binding gotcha:** bound to `192.168.1.41`, `curl 127.0.0.1:8000` gets *connection refused*.
> A socket bound to one address accepts only on that address. "Running" ≠ "reachable."

---

### PHASE A — The client builds and sends

#### Step A.1 — "curl creates headers and body"

**Two corrections.**
1. **URL parsing comes first.** `http://host:port/path?query` → scheme, host, port, path. The
   request line and the `Host:` header are *derived* from it.
2. **No body unless you asked for one.** A plain `curl` is a GET with headers only. `-d`/`-F`
   add a body — and then also `Content-Length` or `Transfer-Encoding`.

At this point everything is **in curl's memory**. No socket, no DNS, nothing on the wire.

#### Step A.2 — "curl has socket-connect logic, maybe urllib3"

**`urllib3` is wrong** — that is a Python library (what `requests` uses). curl is C, built on
**libcurl**. And **DNS is missing**: you normally pass a hostname, so `getaddrinfo()` runs first.
(Typing a raw IP skips it — which is why the lab was instant.)

```
getaddrinfo("host")   →  IP
socket()              →  fd, state CLOSED, no port yet
connect(fd, ip:port)  →  kernel picks an ephemeral source port, sends SYN
```

#### Step A.3 — "connect internally does the 3-way handshake and a queue is formed"

**Right in effect — but curl does not perform the handshake, it asks the kernel to.** curl
blocks in the syscall until ESTABLISHED.

**"A queue" is three queues.** On the server:

```
SYN arrives           → SYN queue (half-open)        state SYN_RCVD
final ACK arrives     → moves to the ACCEPT QUEUE    state ESTABLISHED
                      → waits there for accept()
```

and **Send-Q / Recv-Q are created on both sides** for the connected socket.

| After `connect()` returns | Client | Server |
|---|:--:|:--:|
| connected socket + Send-Q/Recv-Q | ✅ | ✅ (kernel-owned) |
| the *application* has an fd for it | ✅ | ❌ — not until `accept()` |
| entry in the accept queue | — | ✅ |

*(The SYN-queue/accept-queue split is why SYN floods work — they fill the first with half-opens.)*

#### Step A.4 — "data is pushed onto the fd by the client"

**`write(fd, …)` copies bytes into the socket's Send-Q. It does not put them on the wire.**
The kernel transmits when it can, governed by `min(rwnd, cwnd)`.

- **`write()` returning means "copied into Send-Q"** — not delivered, not ACKed, not read.
- **Send-Q full → `write()` blocks** (or `EAGAIN`). That is the backpressure path.

What gets written is one flat byte stream; **TCP frames nothing**:

```
GET /orders/42 HTTP/1.1\r\nHost: …\r\nUser-Agent: curl/8.7.1\r\n\r\n[body]
```

#### Step A.5 — "the kernel segments the data and sends packets to the server NIC"

**Segmentation: right** — by **MSS** (≈ MTU − 40 = 1460). *(NICs often do TSO/GSO: the kernel
hands down one buffer, the NIC slices it.)*

**"to the server NIC": wrong — it goes to the NEXT HOP.**

```
TCP header  (ports, seq/ack, window, checksum)
  ↓
IP header   (src IP, dst IP = the SERVER, TTL)
  ↓
Ethernet    (src MAC, dst MAC = the NEXT HOP)     ← ARP resolves this
```

Then the Lab 01/02 invariant: **MAC rewritten every hop; IP src/dst constant end-to-end;
TTL −1 per router.** In this specific test both hosts were on `192.168.1.x` — **same subnet**,
so no router: ARP for the server's own MAC, straight through the switch, dst IP and dst MAC
both the server. Cross-subnet is where they diverge (IP = server, MAC = gateway).

---

### PHASE B — Arrival at the server

#### Step B.1 — "NIC receives the frame, kernel decapsulates into Recv-Q; a lost packet makes TCP wait; that's TCP blocking"

**All three essentially right.** Three precisions.

Decapsulation order:
```
L2: dst MAC mine? FCS ok?  → strip → EtherType 0x0800
L3: dst IP mine? checksum? → strip → protocol 6 (TCP)
L4: demux by 4-TUPLE → find socket → checksum → seq ordering → Recv-Q
```

**"tcp driver" → the kernel TCP stack.** The *driver* is the NIC driver at L1/L2.

**"Waits" is sharper than that.** Out-of-order segments that *did* arrive are held in a separate
**out-of-order queue** — present in memory, correct, but **not in Recv-Q**, therefore invisible
to `read()`. The receiver sends **duplicate ACKs**; 3 of them trigger fast retransmit (or RTO
fires). **Recv-Q only ever advances contiguously**, which is why the app can never see a gap.

Also: **"synced" is the handshake** (ISN exchange). This is **ordering**, via seq numbers.

**"TCP blocking" — correct, and its name is TCP-level head-of-line blocking:**

```
Packet1: 1–1000 ✓   Packet2: 1001–2000 LOST   Packet3: 2001–3000 ✓ (arrived!)
Recv-Q:  [1–1000 ✓][ GAP ][2001–3000 HELD HOSTAGE]
```

Under HTTP/2 those held bytes often belong to a *different stream* — but TCP knows nothing about
streams, so stream B waits on stream A's loss. That is the problem QUIC solves with per-stream
ordering. *(Not applicable to this trace: 86 bytes = one segment.)*

#### Step B.2 — "HTTP HoL means a slow response blocks others, because keep-alive lets many requests share the path"

**Keep-alive is the precondition, not the cause.** The cause is HTTP/1.1's rule that a
connection serves **one request→response at a time**; a message is atomic on the wire. Without
keep-alive there'd be no HoL — and you'd pay handshake + TLS + slow start per request instead.

Proof it isn't keep-alive: **pipelining** sends many requests without waiting, yet responses must
return **in order** — HoL remains. Hence it was disabled everywhere.

| | What blocks | Fixed by |
|---|---|---|
| **HTTP-level HoL** | a slow *response* blocks requests behind it on the connection | **HTTP/2** — frames + stream IDs + multiplexing |
| **TCP-level HoL** | one lost *packet* stalls all later bytes, across all streams | **HTTP/3** — QUIC, per-stream ordering |

---

### PHASE C — How the loop finds out (the part with no polling anywhere)

#### Step C.1 — "the loop registers the fd with kqueue: hey kernel, notify me on events on this fd, which represents the accept queue"

**Right, with two refinements.**

1. **It's a specific filter**, not "some event": `EVFILT_READ` (macOS) / `EPOLLIN` (Linux).
2. **The fd is the socket, which *owns* an accept queue.** What matters is that the kernel
   *defines readable differently per socket type*:

```
readable(listening socket)  ≡  accept queue is non-empty
readable(connected socket)  ≡  Recv-Q is non-empty
```

One filter, one syscall, two meanings — which is why no special-casing is needed in the loop.

#### Step C.2 — "how does the kernel know there's an event on this fd, and what does the loop do meanwhile?"

**The kernel doesn't discover the event — it *performs* it.** When a packet arrives the CPU is
already executing kernel code (NIC interrupt → softirq → TCP). The notification is a line in the
same function that does the enqueue:

```c
...complete the handshake / append bytes...
  → add to accept queue  (or Recv-Q)
  → sk->sk_data_ready(sk)          ← THE NOTIFICATION, right here
      → wake_up(&sk->sk_wq->wait)  ← walk the socket's wait queue
          → mark the kqueue/epoll entry ready
          → make the sleeping process RUNNABLE
```

**And the loop does nothing — it is not running.** Measured, with connections open:

```
PID    STAT  %CPU   TIME
95088  S     0.1    0:00.12   →  after 3 more seconds:  0:00.13
```

**10 ms of CPU across 3 seconds**, `STAT=S` — parked on a kernel wait queue, off the run queue,
not scheduled. It cannot check anything because it is not executing.

> **The kernel doesn't watch — it acts, and notifies as part of acting.
> The loop doesn't wait — it's descheduled, and gets woken.**

#### Step C.3 — "kernel network code is running on the CPU, so it knows data is in the NIC, passes it to the accept queue, marks the fd ready and notifies the loop"

**Three corrections.**

1. **The NIC interrupts the CPU** — hardware-initiated. Kernel code runs *because* of the
   interrupt, not before it. *(At high rates Linux switches to NAPI polling to amortise it.)*
2. **It forks by packet type; not everything goes to the accept queue** — and the accept queue
   holds a **connection object**, never application bytes:

```
SYN                    → SYN queue
final ACK of handshake → connection completed → ACCEPT QUEUE → mark LISTENING fd readable
data segment           → demux by 4-tuple → that socket's RECV-Q → mark CONNECTED fd readable
```

3. **So one `curl` wakes the loop twice** — proven by the trace timestamps:

```
2378.576 ms  KERNEL   accept() returned → connected socket fd=12    ← wake #1 (listening fd)
2378.682 ms  KERNEL   Recv-Q drained → 86 raw bytes to user space   ← wake #2 (fd 12)
```

0.1 ms apart, two loop iterations, two fds, two queues. In between, the loop went back to
`kevent()` and was woken again.

#### Step C.4 — "what is kevent?"

**kqueue is BSD/macOS's readiness mechanism; `kevent` is its syscall.** Linux's equivalent is
`epoll`. Confirmed live:

```
loop class     : _UnixSelectorEventLoop
selector class : KqueueSelector        ← macOS default
kqueue fd      : 3                     ← the KQUEUE fd lsof showed
registered fds : [4, 6]                ← 4 = self-pipe, 6 = the listening socket
```

```c
int kq = kqueue();                 // create the kernel object → returns an fd
kevent(kq, changes, nchanges,      // register/modify interest
           events,  nevents,       // AND collect what's ready
           timeout);               // AND sleep until something happens
```

`kevent()` does all three in **one** syscall; Linux splits them (`epoll_ctl` + `epoll_wait`).

```c
struct kevent {
    uintptr_t ident;    // WHAT  — the fd
    int16_t   filter;   // WHICH — EVFILT_READ / EVFILT_WRITE / ...
    uint16_t  flags;    // EV_ADD / EV_DELETE / EV_ONESHOT
    intptr_t  data;     // ON RETURN: how much is ready  ← bytes in Recv-Q,
    void     *udata;    //            or pending connections in the accept queue
};
```

| | `select`/`poll` | `epoll` | `kqueue` |
|---|---|---|---|
| Interest list lives | in **your** process, re-sent every call | in the **kernel**, registered once | in the **kernel**, registered once |
| Cost per call | O(all fds) | **O(ready)** | **O(ready)** |
| fd limit | 1024 (`select`) | none | none |

kqueue also watches files (`EVFILT_VNODE`), processes, signals and timers — hence the generic
name. uvloop bypasses Python's `selectors` and calls kqueue through libuv in C.

#### Step C.5 — "so kqueue is a loop that looks for ready fds and notifies the event loop?"

**No — kqueue is a data structure, not a loop.** No thread, no execution, no scanning.

```
kqueue (fd 3)
├── interest list :  fd 10 → EVFILT_READ, fd 12 → EVFILT_READ, …
└── ready list    :  (empty)     ← things get PUSHED here
```

| Component | Loops? | Does what |
|---|:--:|---|
| NIC | no | raises a hardware **interrupt** |
| Kernel TCP code | no | runs **once per packet**, in interrupt context |
| **kqueue** | **no** | **passive structure** — receives pushes, holds a ready list |
| **Your event loop** | **yes** | the **only** loop in the picture, in user space |

`kevent()` merely reads the ready list and empties it; if it's empty, it sleeps the caller.
**If anything scanned fds, this would just be `select()` with extra steps** — O(N) and burning
CPU. The whole innovation is that *nobody scans*.

> kqueue is a **mailbox with a doorbell**. TCP code drops a note in and rings it.

#### Step C.6 — "then who the hell wakes it, if it's asleep and nothing checks?"

**The hardware.** A packet arriving physically interrupts the CPU.

```
T0   your process: blocked in kevent(), STAT=S, OFF the CPU. Nobody is watching. Correct.
T1   packet lands on the NIC.
T2   NIC raises a hardware interrupt → CPU ABANDONS what it was running   ← forced, by hardware
T3   driver → softirq → IP → TCP        ← running in BORROWED context, not your process
T4   append to Recv-Q → sk_data_ready() → push onto kqueue ready list
       → wake_up() → your process moves from the socket's WAIT QUEUE to the RUN QUEUE
T5   interrupt returns; scheduler runs; your process is runnable
T6   your process resumes INSIDE kevent(), finds the ready list, returns the fds
```

**Your process was never involved in T1–T5** — different execution context, possibly a different
core. Two things to unlearn: *"sleeping" is not waiting-and-checking* (it's parked on a wait
queue, consuming nothing, and cannot wake itself), and *nothing needs to check, because the
packet announces itself*.

> Not a guard patrolling corridors trying doors. A **doorbell wired to your bed.**
> A patrol costs CPU proportional to the number of doors — that's `select()`. A doorbell costs
> nothing until it rings. That's why one thread holds 10,000 connections at 0.1% CPU.

---

### PHASE D — accept()

#### Step D.1 — "the loop wakes, reads the accept queue, creates a pair socket TCP connection, and registers that fd with kqueue too"

**The loop creates nothing.** The kernel already built that connection — the handshake completed
before `accept()` was called. `accept()` **dequeues** an existing connection and returns an fd.

**It is not a "pair."** `socketpair()` is a different thing (two fds in one process, IPC). Here
each side makes its **own** fd independently; the only thing pairing them is the **4-tuple**.

**And two user-space objects are built at this moment:**

```
accept() → fd 12
   ↓
Transport   — asyncio wrapper owning fd 12 (write buffer, pause/resume reading)
Protocol    — a NEW HttpToolsProtocol instance: its own parser, its own buffers
```

Per-connection state lives in the Protocol, which is why one connection's half-parsed request
cannot bleed into another's.

Corrected: *listening fd readable → loop wakes → `accept()` dequeues an already-established
connection → new fd → Transport + fresh Protocol → **register fd 12 with kqueue** → back to sleep.*

#### Step D.2 — "with multiple clients, same approach, a separate socket each"

**Correct.**

```
fd 10u  TCP 127.0.0.1:8040                     (LISTEN)
fd 12u  TCP 127.0.0.1:8040 -> 127.0.0.1:59385  (ESTABLISHED)
fd 13u  TCP 127.0.0.1:8040 -> 127.0.0.1:59384  (ESTABLISHED)
fd 14u  TCP 127.0.0.1:8040 -> 127.0.0.1:59383  (ESTABLISHED)
```

**Four sockets, four fds, ONE port.** The server never allocates a port per client — the
*client* gets an ephemeral port. Connections are identified by the **4-tuple**, and the kernel
demuxes arriving packets by looking it up.

Two refinements:
- **One wake can yield several connections** — the loop calls `accept()` in a bounded loop until
  the queue drains. 500 simultaneous connects ≈ a handful of wake-ups, not 500.
- **Still one thread.** Per connection you pay an fd + kernel buffers + two Python objects; you
  do **not** pay a thread, a ~8 MB stack, or a context switch. Cost is memory, not scheduling.

> Port exhaustion is a **client-side** problem (~28,000 ephemeral ports per destination tuple),
> not a server-side one. A server on one port is bounded by fds and memory.

#### Step D.3 — "with a million requests there'd be a million fds"

**One fd per *concurrent* connection — and concurrent ≠ total.** Little's Law:

```
concurrent connections = arrival rate × connection lifetime
```

| Traffic | Lifetime | Concurrent fds |
|---|---|---:|
| 1M requests/day (≈12 rps), 50 ms each | 50 ms | **~1** |
| 10,000 rps, 50 ms each | 50 ms | **500** |
| 10,000 rps, keep-alive held 60 s | 60 s | **600,000** |
| 1M idle WebSocket clients | hours | **1,000,000** |

Millions of fds come from **long-lived** connections, not high request volume.

Real ceilings on this machine:

```
ulimit -n            : 1048576    ← misleading
kern.maxfilesperproc : 10240      ← the REAL per-process cap
kern.maxfiles        : 30720      ← system-wide
net.inet.tcp.recvspace / sendspace : 131072 each  ← up to 256 KB of kernel buffer per connection
```

**Memory breaks before fd count does** — 100k connections × ~64 KB ≈ 6.4 GB. This is why C10K was
solved (`epoll`/`kqueue` fixed the *CPU* cost of watching) while **C10M is still hard** (nothing
fixed the *memory* cost of holding).

Failure mode: `accept()` → **`EMFILE`**; connections pile in the accept queue; then SYNs are
dropped silently → clients hang. Slow-failure signature, new cause.

#### Step D.4 — "but a million users on different machines means a million fds at once"

**Only if their requests overlap in time** — for request/response HTTP they don't:

```
1M users × 10 req/day = 10M/day ÷ 86,400 s ≈ 116 rps × 50 ms ≈ 6 concurrent
```

**Where it IS true:** (a) **persistent connections** — WebSocket/SSE/long-poll/mobile push, held
whether or not the user is doing anything; a million logged-in chat users *is* a million sockets.
(b) **synchronised demand** — a goal in a live match, a flash sale, a push fan-out.

**And even then, never on one process** — the architecture is **connection fan-in**:

```
1,000,000 clients                         hundreds of origin connections
        │                                            │
        ▼                                            ▼
  ┌───────────┐   pooled, reused       ┌──────────────────┐
  │ edge / LB │ ═══════════════════▶   │ uvicorn workers  │
  └───────────┘                        └──────────────────┘
   holds 1M fds, sharded                 holds ~200 fds
```

The edge tier holds the million (sharded, tuned-down buffers, usually not Python) and multiplexes
onto a small pool of long-lived origin connections. *(WhatsApp's ~2M connections on one server was
famous precisely because it was extraordinary.)*

---

### PHASE E — Bytes into user space

#### Step E.1 — The second wake

```
2378.682 ms  KERNEL   Recv-Q drained → 86 raw bytes handed to user space
2378.701 ms  UVICORN  data_received() called; first line: 'GET /orders/42 HTTP/1.1'
```

1. TCP appends the segment to fd 12's Recv-Q, marks fd 12 readable, wakes the process.
2. `kevent()` returns `[fd 12, EVFILT_READ, data=86]` — `data` says how many bytes are available.
3. The loop maps fd 12 → the Transport's read callback.
4. Transport calls **`recv(12, …)`** — the actual **copy across the kernel/user boundary**.
   Recv-Q is now empty; the bytes exist only as a Python object.
5. Transport **pushes**: `protocol.data_received(b"GET /orders/42 HTTP/1.1\r\n…")`.

> **`data_received()` receives an arbitrary slice of a byte stream — not a request.**
> It could be half a request, one and a half requests, or exactly one. TCP frames nothing.
> This is why the Protocol is per-connection and stateful: it holds a parser that survives
> across calls. Same problem `stage1_server.py` had to solve by hand.

#### Step E.2 — "so until here the data is with the event loop, read from the fd"

**Ownership correction: the data is with the Protocol object, not the loop.**

```
loop          : "fd 12 readable" → look up callback → call it → DONE, moves on
transport     : recv(12) → copies out of Recv-Q into a Python bytes object
protocol #12  : data_received(b"GET …")     ← the data lives HERE
```

Once `data_received()` returns, the loop holds no reference. The bytes belong to that one
connection's protocol instance. Also: the loop is currently *inside* `data_received` — nothing
else on that thread advances until it returns (the mechanism behind the blocking failure mode).

What is held right now is **raw undifferentiated bytes**. No scope, no headers dict, nothing parsed.

---

### PHASE F — From bytes to your application

Source: `uvicorn/protocols/http/httptools_impl.py`.

#### Step F.1 — The parser builds `scope` incrementally

httptools is a **streaming C parser** (Node's HTTP parser). You feed it bytes; it calls back:

```python
on_message_begin()      → self.scope = {"type": "http", "asgi": {...}, ...}
on_url(url)             → stashes the raw URL
on_header(name, value)  → self.headers.append((name.lower(), value))
on_headers_complete()   → self.scope["method"]       = "GET"
                          self.scope["path"]         = "/orders/42"   # percent-decoded
                          self.scope["raw_path"]     = b"/orders/42"
                          self.scope["query_string"] = b""
```

Byte stream → structure. After this, nothing touches raw HTTP text again.

#### Step F.2 — Load shedding happens *before* your app

```python
if self.limit_concurrency is not None and (
    len(self.connections) >= self.limit_concurrency or len(self.tasks) >= self.limit_concurrency
):
    app = service_unavailable      # ← a canned 503, NOT your app
else:
    app = self.app
```

`--limit-concurrency` is implemented by **swapping which ASGI app gets called**. Your code never
runs.

#### Step F.3 — A `RequestResponseCycle` per request, run as a Task

```python
self.cycle = RequestResponseCycle(scope=self.scope, transport=...,
                                  message_event=asyncio.Event(), ...)
task = self.loop.create_task(self.cycle.run_asgi(app))
```

**Your app is not called from `data_received()`.** It is wrapped in an asyncio **Task** and
scheduled; `data_received()` returns immediately and the loop runs the task on a later pass.
(That's why asyncio's slow-callback warning names `RequestResponseCycle.run_asgi()`.)

Inside: `await app(scope, self.receive, self.send)` — three arguments. That is the whole handoff.

#### Step F.4 — The bridge between parser and app is an `asyncio.Event`

Two actors that must be decoupled — the **parser** (driven by the loop whenever bytes arrive) and
your **app** (a Task, awaiting) — connected by one event:

```python
# producer — parser callbacks
def on_body(self, body):
    self.cycle.body += body
    if len(self.cycle.body) > HIGH_WATER_LIMIT:
        self.flow.pause_reading()      # ← BACKPRESSURE
    self.cycle.message_event.set()     # ← wake the app

def on_message_complete(self):
    self.cycle.more_body = False
    self.cycle.message_event.set()

# consumer — what `await receive()` actually runs
async def receive(self):
    self.flow.resume_reading()
    await self.message_event.wait()    # ← parks the coroutine
    self.message_event.clear()
    return {"type": "http.request", "body": bytes(self.body), "more_body": self.more_body}
```

So when you `await receive()` and the body hasn't arrived:

```
coroutine parks on message_event.wait()
  → loop has nothing runnable → back to kevent() → SLEEPS
    → more bytes → data_received → on_body → event.set()
      → coroutine runnable again → resumes with the body
```

**`pause_reading()` is application backpressure reaching TCP:** upload faster than the app
consumes and uvicorn stops reading the socket → Recv-Q fills → the advertised window shrinks →
the sender is throttled. The sliding window from `03-tcp.md`, driven from Python.

#### Step F.5 — `send()` goes back down

```python
await send({"type": "http.response.start", ...})  → serialize status + headers → transport.write() → Send-Q
await send({"type": "http.response.body",  ...})  → transport.write(body)                         → Send-Q
```

#### Step F.6 — Where your application sits

`app` is just the callable uvicorn was handed. FastAPI **is** an ASGI app:

```
uvicorn  →  app(scope, receive, send)
              └─ FastAPI/Starlette: scope["path"] + ["method"] → route match
                                    build a Request over receive
                                    validate/coerce params (pydantic)
                                    → await your_handler(...)     ← YOUR CODE
                                    serialize the return value to JSON
                                    → send(response.start) + send(response.body)
```

Everything between `scope` and your handler is Starlette and pydantic. **uvicorn's job ended at
those three arguments.**

---

### PHASE G — `--workers N`: does any of this change?

#### Step G.1 — "4 workers means 4 event loops?"

**Yes — 4 processes, 4 interpreters, 4 GILs, 4 event loops, 4 kqueues — sharing ONE socket.**

```
lsof -nP -iTCP:8071
Python 43738  3u  IPv4  0x57eddae80b7622d6  TCP 127.0.0.1:8071 (LISTEN)   ← supervisor
Python 43741  3u  IPv4  0x57eddae80b7622d6  TCP 127.0.0.1:8071 (LISTEN)   ← worker
Python 43742  3u  IPv4  0x57eddae80b7622d6  TCP 127.0.0.1:8071 (LISTEN)   ← worker
Python 43743  3u  IPv4  0x57eddae80b7622d6  TCP 127.0.0.1:8071 (LISTEN)   ← worker
Python 43744  3u  IPv4  0x57eddae80b7622d6  TCP 127.0.0.1:8071 (LISTEN)   ← worker
                        └──────────────────┘
                  IDENTICAL DEVICE = literally ONE kernel socket

pid 43741  listen_fd=3u  kqueue_fd=10u      ← its own event loop
pid 43742  listen_fd=3u  kqueue_fd=6u       ← its own event loop
pid 43743  listen_fd=3u  kqueue_fd=6u       ← its own event loop
pid 43744  listen_fd=3u  kqueue_fd=6u       ← its own event loop
```

Distinct loop objects, confirmed by identity:

```
pid=43322 loop=47635890208
pid=43323 loop=30724882464
pid=43325 loop=48004988960
```

**The order is what makes the shared socket possible:**

```
supervisor:  socket() → bind(8071) → listen(backlog)      ← ONE socket, fd 3
             └─ fork/spawn ×4 → children INHERIT fd 3     ← not a copy: the same kernel object
each worker: creates its OWN event loop + kqueue
             registers the inherited fd 3 with its own kqueue
             sleeps in kevent()
```

All four sleep on the **same listening fd**. When a connection lands in the accept queue, the
kernel wakes a worker and whoever's `accept()` wins takes it.

> **The kernel is the load balancer.** No proxy, no round-robin, no coordination between
> workers, no shared state. Just N processes racing on one accept queue.

#### Step G.2 — The distribution is not even

12 requests across 4 workers:

```
7 → pid 43322
4 → pid 43325
1 → pid 43323
0 → pid 43324          ← never served a single request
```

This is the **same law as an L4 load balancer and HTTP/2** (see the building-blocks Chapter 2),
one level down: the kernel hands out a *connection*, and with keep-alive that connection stays
pinned to that worker for its entire life. **Balancing granularity = connection lifetime**, and
`accept()` is the only decision point.

Which is why `--timeout-keep-alive` isn't only a resource knob — it also bounds how long a
worker can stay stuck with a disproportionate share of traffic.

#### Step G.3 — Worker count is a blast-radius decision

Measured: one `/block` (a `time.sleep(3)` inside `async def`) in flight, then 8 probes to a
trivial `/fast`:

```
--- 1 worker ---                      --- 4 workers ---
  probe 1: 2.697330s   ← STALLED        probe 1: 0.000857s
  probe 2: 0.000685s                    probe 2: 0.000520s
  probe 3: 0.000639s                    probe 3: 0.000469s
  probe 4: 0.000491s                    probe 4: 0.000499s
  ...                                   ...  (all 8 unaffected)
```

With one worker the first probe waits out the remaining block. With four, the blocked worker is
one of four and the other three keep serving — **the blast radius of a blocking call drops from
100% to ~1/N.**

That is the honest framing of `--workers`: not only throughput (4 GILs → 4 cores), but
**containment**. It does not *fix* a blocking handler; it caps the damage.

#### Step G.4 — Nothing is shared except the socket

Separate processes, separate memory. This is where bumping `--workers` from 1 to 4 silently
breaks working code:

| You wrote | What actually happens with 4 workers |
|---|---|
| in-process dict cache | **4 caches** — 4× misses, 4× memory, incoherent |
| in-process rate limiter | effective limit is **4×** what you configured |
| WebSocket / SSE connection registry | a broadcast reaches only **1/4** of clients |
| `@app.on_event("startup")` / lifespan | runs **4 times** — 4 migrations, 4 schedulers, 4 cron loops |
| an in-memory job queue or counter | 4 independent ones |

Every one of those has to move to Redis/Postgres, or be pinned to a single designated process.
Nothing errors; the behaviour is just quietly wrong.

#### Step G.5 — Practical notes

- **`--reload` and `--workers` are incompatible** — different process-management strategies.
- **One loop saturates exactly one core** (the GIL). That is the actual reason workers exist;
  rule of thumb workers ≈ cores for mixed workloads.
- **In Kubernetes, the common pattern is 1 worker per container** and let the orchestrator scale.
  Then a wedged worker is a failing readiness probe and a restarted pod — rather than a silent
  1/N degradation that nothing notices.
- **CPU-bound work is still wrong here.** N workers gives N cores, but a CPU-heavy handler still
  blocks its own loop for its whole duration. That work belongs in a queue (see the message-queue
  topic), not in a request handler.

---

## 4. Mental model / analogy

A hotel with **one receptionist** (the single-threaded event loop) and a **doorbell per room**
(kqueue registrations).

- The **front desk bell** is the listening socket — it rings when a *new guest* arrives (accept
  queue), and the receptionist hands them a room (a connected socket with its own fd).
- **Each room's bell** rings when *that guest* has something to say (Recv-Q).
- The receptionist **sleeps** between bells and consumes nothing. They never walk the corridors
  checking rooms — that would be `select()`.
- The bells are wired by the **building** (the kernel), which rings them as a side effect of
  letting people in and delivering their messages. Nobody monitors the bells.
- **If the receptionist gets stuck on one guest** (a blocking call in an `async def`), every
  other bell in the hotel goes unanswered — even though they rang.

## 5. Hands-on (what to show on screen)

Instrumented server — subclasses uvicorn's real `HttpToolsProtocol` and logs every boundary:

```bash
python3 scripts/trace_server.py                     # then, elsewhere:
curl -v http://127.0.0.1:8030/orders/42
```

Captured output — the whole climb, with timestamps:

```
   60.649 ms  UVICORN  lifespan.startup → app is ready to serve
 2378.576 ms  KERNEL   accept() returned → connected socket fd=12  peer=127.0.0.1:59254
 2378.622 ms  UVICORN  protocol instance created for THIS connection (own parser, own buffers)
 2378.682 ms  KERNEL   Recv-Q drained → 86 raw bytes handed to user space
 2378.701 ms  UVICORN  data_received() called; first line: 'GET /orders/42 HTTP/1.1'
 2378.931 ms  PARSER   httptools: request line parsed → /orders/42
 2378.965 ms  PARSER   httptools: all headers parsed (byte stream → structured fields)
 2379.021 ms  PARSER   httptools: message complete → a WHOLE HTTP request now exists
 2379.087 ms  ASGI     app(scope, receive, send) CALLED
 2379.125 ms  APP      handler running — THIS is your code. Everything above was plumbing.
 2379.131 ms  ASGI     send() → http.response.start
 2379.176 ms  ASGI     send() → http.response.body
 2379.198 ms  UVICORN  response written to transport → kernel Send-Q → wire
 2379.406 ms  KERNEL   connection_lost() → FIN seen / socket closed, buffers freed
```

Socket-side observation:

```bash
lsof -nP -iTCP:8030                 # LISTEN before; LISTEN + ESTABLISHED during
netstat -an | grep 8030             # the 4-tuples; Recv-Q / Send-Q columns
lsof -p $(pgrep -f trace_server.py) # the KQUEUE fd — the event loop as a kernel object
ps -o pid,stat,%cpu,time -p $(pgrep -f trace_server.py)   # STAT=S, ~0% CPU while idle
sudo tcpdump -i lo0 -n 'tcp port 8030'                    # the wire half, in parallel
```

**Demo 1 — one port, many connections** (`scripts/` or inline): open 3 concurrent slow requests,
then `lsof` → 1 LISTEN + 3 ESTABLISHED, all on the same port, different client ports.

**Demo 2 — the handshake happens without `accept()`:** a script that calls `listen()` and never
`accept()`s. Clients still connect successfully and their bytes sit in Recv-Q, while the server
process holds only the listening fd. **Proves a wedged app still passes TCP health checks.**

**Demo 3 — blocking the loop:**

```
baseline: /fast alone                              = 0.0008 s
  while 3x /await   in flight → /fast took 0.0007 s   ← unaffected
  while 3x /syncdef in flight → /fast took 0.0010 s   ← unaffected (threadpool)
  while 3x /block   in flight → /fast took 5.7628 s   ← whole server stalled
total wall time for 3 concurrent: /await 2.06s · /syncdef 2.04s · /block 6.06s
```

**Demo 4 — catch it in production:**

```python
loop.set_debug(True)
loop.slow_callback_duration = 0.1
# WARNING:asyncio:Executing <Task ... run_asgi() ...> took 0.505 seconds
```

## 6. Common misconceptions

- **"The listening socket has Send-Q/Recv-Q."** No — it has an **accept queue**. Only *connected*
  sockets have byte buffers.
- **"The accept queue holds data."** It holds **connections**. No application byte ever touches it.
- **"The server opens a new port per client."** No — a new **socket/fd**, same port. Connections
  are distinguished by the **4-tuple**. Port exhaustion is a *client-side* concern.
- **"`accept()` establishes the connection."** No — the kernel already did. `accept()` **dequeues**
  an already-ESTABLISHED connection.
- **"The client and server share a socket pair."** No — each side makes its own fd independently;
  only `socketpair()` makes a real pair (same-machine IPC).
- **"kqueue/epoll is a loop that scans fds."** It is a **passive data structure**. The only loop is
  your event loop, in user space. If anything scanned, this would be `select()`.
- **"Something checks whether data arrived."** Nothing checks. The **NIC interrupts the CPU** and
  the kernel notifies as a side effect of enqueuing.
- **"The event loop polls while sleeping."** It is descheduled — `STAT=S`, off the run queue,
  consuming nothing. It cannot check anything because it is not executing.
- **"`write()` puts bytes on the wire."** It copies them into Send-Q. Returning means nothing
  about delivery.
- **"The kernel parses HTTP."** It does not. The socket API is the boundary; **uvicorn** parses.
- **"`data_received()` gives you a request."** It gives you an arbitrary slice of a byte stream.
- **"uvicorn calls my app from `data_received`."** It creates an asyncio **Task**; the app runs on
  a later loop pass.
- **"`async def` is always faster than `def`."** For blocking work, plain `def` is *safer* —
  FastAPI runs it in a threadpool; a blocking call in `async def` stalls every connection.
- **"`--workers 4` gives one loop shared by 4 threads."** No — **4 processes**, 4 interpreters,
  4 GILs, 4 independent event loops, sharing **one inherited listening socket**.
- **"Workers round-robin requests."** No — they **race** on one accept queue; the kernel wakes
  one. Distribution is uneven, and keep-alive pins a connection to whichever worker won.
- **"More workers fixes a blocking handler."** It caps the blast radius to ~1/N. The blocked
  worker is still fully stalled.
- **"Module-level state is shared across workers."** Nothing is shared but the socket. Caches,
  rate limiters, connection registries and startup hooks are **per process**.
- **"A million users means a million fds."** Only if their connections overlap — persistent
  connections or synchronised demand. Otherwise Little's Law says otherwise.

## 7. Diagrams needed

1. **The two-boundary stack** — kernel / socket API / uvicorn / ASGI / FastAPI / your handler,
   with the packet-lifecycle doc's line marked "this doc starts here."
2. **One port, many sockets** — the `lsof` picture: 1 LISTEN + N ESTABLISHED, 4-tuples annotated.
3. **The wake-up chain** — NIC interrupt → softirq → TCP → `sk_data_ready` → kqueue ready list →
   scheduler run queue → `kevent()` returns. *(The highest-value animation in this doc.)*
4. **Two queues, two meanings of "readable"** — accept queue vs Recv-Q on the same filter.
5. **The two wakes for one `curl`** — timeline with the real 0.1 ms gap.
6. **The `asyncio.Event` bridge** — parser callbacks (producer) ↔ `await receive()` (consumer),
   with `pause_reading()` shown reaching down into TCP flow control.
7. **Blocked loop** — three `/block` requests serialising while `/fast` waits 5.76 s.
8. **`--workers 4`** — one supervisor, one listening socket inherited by four processes, each
   with its own loop/kqueue; arrows showing all four `accept()`-ing on the same queue. Annotate
   the 7/4/1/0 distribution and "nothing shared but the socket."

## 8. Video script outline

- **Hook (0:00)** — "Your FastAPI handler is 3 lines. Here are the ~40 steps that happen before
  it runs — and the one mistake that makes all of them stop."
- **Build** —
  1. Start the server; `lsof` shows **one** socket. Where's the connection? (Phase 0)
  2. `curl` it; `lsof` again — **two**, same port. Kill the "new port per client" idea. (D.2)
  3. The never-`accept()` demo: connections complete anyway → **the kernel does the handshake**,
     and your TCP health check is a lie. (D.1)
  4. Who wakes the sleeping loop? The doorbell, not the patrol. `STAT=S`, 10 ms CPU. (C.2, C.6)
  5. The trace log: two wakes, parse, scope, Task, `app(scope, receive, send)`. (E, F)
- **Payoff** — the blocking demo: one `time.sleep` in an `async def` and an unrelated endpoint
  takes 5.76 s. Everything learned explains exactly why.
- **Recap (3 bullets)** — the kernel does the handshake, not your app · nothing polls; hardware
  interrupts and the kernel notifies · one thread, so every millisecond in your code is a
  millisecond not collecting sockets.

## 9. Brainstorm / open questions

- This is the natural **sequel to the packet-lifecycle capstone** — record it immediately after,
  as "the other half." Strong two-panel visual: left = tcpdump (wire), right = the trace log (app).
- `scripts/trace_server.py` subclasses the real `HttpToolsProtocol`, so the log is genuine
  uvicorn internals, not a mock. Worth saying on camera — it's what makes it credible.
- ~~Open: does `--workers N` change any of this?~~ **Answered — now Phase G.** Measured: 5
  processes sharing one socket (identical device in `lsof`), 4 distinct kqueues, uneven 7/4/1/0
  distribution, and blocking blast radius dropping from 100% to ~1/N. The "nothing shared but the
  socket" table (G.4) is the most immediately useful thing in this doc for real services.
- Phase G ties directly to the building-blocks Chapter 2 law (balancing granularity = connection
  lifetime). Worth teaching them back to back — the same phenomenon at the kernel/worker level and
  at the load-balancer/backend level.
- Unwritten neighbours this doc leans on: `04-sockets/01-sockets.md`, `02-socket-states.md`.
  This doc could seed both.

## 10. References

- `scripts/trace_server.py` (this repo) — the instrumented server used throughout.
- uvicorn source: `uvicorn/protocols/http/httptools_impl.py` — `on_headers_complete`,
  `on_body`, `RequestResponseCycle.receive`.
- ASGI spec: <https://asgi.readthedocs.io/> — `scope` / `receive` / `send`, lifespan protocol.
- `kqueue(2)` / `kevent(2)` man pages; `epoll(7)` on Linux.
- Prereq docs: [[packet-lifecycle-end-to-end]], [[03-tcp]], [[http11-connection-mechanics-hol]].
