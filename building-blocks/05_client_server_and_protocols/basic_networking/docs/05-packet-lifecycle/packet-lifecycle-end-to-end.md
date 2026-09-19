# Packet Lifecycle — End to End, Source to Destination

> **Status:** 🟡 studying (capstone — synthesizes the whole course)
> **Prereqs:** [[00-overview]] (OSI/encapsulation), [[05-router-switch-gateway]],
> Lab 01/02, and the socket/TCP/fd deep-dives.
> **OSI layer / where it lives:** all of them — this is the whole stack firing.
> **Est. depth:** the payoff episode; ties every layer + sockets + buffers together.

## 1. One-liner
`curl http://server/` = build HTTP text → kernel does the TCP handshake over
routed IP packets → bytes flow through per-connection socket buffers
(Send-Q/Recv-Q) → server app reads, responds → connection tears down; each layer
adds/strips its header, switches forward by MAC, routers by IP.

## 2. The problem it solves (what this topic answers)
"What *actually* happens, end to end, when I run one `curl`?" — socket creation
on both ends, fds, Send-Q/Recv-Q, when the TCP connection is born and destroyed,
and how a packet crosses switches and routers. One coherent story.

## 3. Deep dive — the mechanism

**Legend:** `[user]` user space · `[kernel]` OS kernel · `[wire]` on the network
· `[device]` switch/router.
**Cast:** Client C (`curl`, `192.168.1.10`) · Server S (`192.168.2.10:80`) ·
Router R + two switches between (different networks).

### PHASE A — Server is listening (before the client exists)
1. `[user]` `socket()` → `[kernel]` socket object + **fd 3** (listening socket).
2. `[user]` `bind(fd3, 0.0.0.0:80)` → local addr/port attached.
3. `[user]` `listen(fd3)` → state **LISTEN**; kernel allocates an **accept queue**.
   This socket carries **no data** — it only accepts connections.
4. `[user]` server blocks in `accept()` (or an event loop).

### PHASE B — Client initiates
5. `[user]` curl parses URL → host `192.168.2.10`, **port 80**, path `/`.
   (Name instead of IP → DNS first.)
6. `[user]` `socket()` → **fd 5** (connected socket); kernel assigns an
   **ephemeral source port** (e.g. 49152).
7. `[user]` `connect(fd5, 192.168.2.10:80)` → `[kernel]` drives the handshake.

### PHASE C — Before any packet: L2 delivery setup
8. `[kernel]` **routing decision:** dst off-subnet → send to **default gateway**
   `192.168.1.1`. *Dst IP = server, dst MAC = gateway.*
9. `[kernel]` **ARP** for the gateway's MAC (if not cached).

### PHASE D — TCP 3-way handshake → connection BORN
10. `[wire]` C sends **SYN** (seq=x); C state **SYN_SENT**. Encapsulated
    TCP→IP→Ethernet.
11. `[device]` path **C → Switch0 → Router R → Switch1 → S**. Switches forward by
    MAC unchanged; **R rewrites L2 MACs + TTL−1** (IP constant).
12. `[kernel]` S's listening socket receives SYN → half-open entry, state
    **SYN_RCVD**; replies **SYN-ACK** (seq=y, ack=x+1).
13. `[wire]` C gets SYN-ACK → state **ESTABLISHED**; sends **ACK** (ack=y+1).
14. `[kernel]` S gets ACK → **ESTABLISHED**; `accept()` returns a **new connected
    socket, fd 7** — distinct from listening fd 3.
15. **State now:** both ends have a **connected socket** (C:fd5, S:fd7), each with
    its **own Send-Q / Recv-Q**, identified by the **4-tuple**
    `(1.10:49152, 2.10:80)`. Listening fd 3 keeps waiting.

### PHASE E — HTTP request travels
16. `[user]` curl `write(fd5, "GET / HTTP/1.1\r\nHost:...\r\n\r\n")`.
17. `[kernel]` bytes → C's **Send-Q** → wrapped **TCP→IP→Ethernet** → wire.
    (Bigger than **MTU** ~1500B → TCP **segments** into multiple packets, each
    with a seq number.)
18. `[device]` Switch → **Router (MAC rewrite, TTL−1)** → Switch.
19. `[kernel]` frame at S's NIC → **demultiplex by the 4-tuple** → bytes into
    fd7's **Recv-Q**.
20. `[kernel]` S **ACKs** the data. `[user]` server `read(fd7)` drains the Recv-Q.

### PHASE F — Server processes & responds
21. `[user]` server parses HTTP, builds `HTTP/1.1 200 OK` + headers + body.
22. `[user]` `write(fd7, response)` → `[kernel]` → S's **Send-Q** → wire.
23. `[device/wire]` **reverse path** back to C.
24. `[kernel]` bytes → C's **Recv-Q** (fd5), **reassembled** in order by seq.
    `[user]` curl `read(fd5)` → **prints the HTML**.

### PHASE G — Teardown → connection DIES
25. `[user]` `close(fd)` → `[kernel]` **4-way close**: `FIN → | ← ACK | ← FIN | ACK →`.
26. `[kernel]` states walk **FIN_WAIT_1/2 · CLOSE_WAIT · LAST_ACK**, initiator sits
    in **TIME_WAIT** (~2×MSL), then **CLOSED**.
27. `[kernel]` each **fd** closed; refcount 0 → socket object + Send-Q/Recv-Q
    **freed**; 4-tuple reusable.
28. `[kernel]` S's **listening fd 3 untouched** — keeps accepting. Only the
    per-connection sockets die.

### The socket is the boundary (socket ≠ connection)
Two things people conflate:

**1. Creating a socket does NOT create a TCP connection.**
```
socket()            → allocate endpoint (fd). State CLOSED. NOTHING on the wire.
connect()/accept()  → kernel does routing + ARP + 3-way handshake → connection BORN
```
`socket()` is just the *handle* (like buying a phone); the connection is a later
event (dialing) via `connect()` (client) or `accept()` returning (server). You can
make a socket and never connect it — and UDP sockets have no connection at all.

**2. The kernel handles L4→L1, but NOT L7 — the socket API is the dividing line.**
```
        YOUR CODE (user space)
  L7  Application   curl / web server   ← YOU build HTTP text here
 ─────────────────── socket API ───────────────────  ← THE BOUNDARY (write/read)
  L4  Transport     TCP: handshake, seq/ack, retransmit, flow control  ┐
  L3  Network       IP: addressing, routing decision, TTL, fragment    │ KERNEL
  L2  Data Link     Ethernet framing, ARP, MAC                         │
 ─────────────────── driver ───────────────────
  L1  Physical      NIC turns frames into signals                      ┘ HARDWARE
```
- **Above the socket (L7):** your app. The kernel has no idea what HTTP is — which
  is why `stage1_server.py` had to parse HTTP itself.
- **Below the socket (L4–L2):** the kernel owns it. `write(fd, bytes)` → kernel
  wraps them TCP→IP→Ethernet → NIC (L1) signals the wire. The other end reassembles
  and its app `read()`s them.
- **Mental image:** the socket is a **faucet** — you pour raw bytes in (L7); the
  kernel plumbing (L4→L1) carries them; you supply the water, the kernel is the pipes.

This is why the phase list tags `[user]` (curl / server app = L7) vs `[kernel]`
(TCP/IP/buffers = L4–L2): the socket is the line between those two columns.

### Receive-side: decapsulation, layer by layer
The receiver unwraps **bottom-up** — each layer checks its header, strips it, and
hands the rest up (or drops).

**L2 Data Link — receives the frame:**
1. **Dst MAC == my MAC (or broadcast)?** No → **drop** (NIC ignores frames not for it).
2. **Verify FCS** (CRC). Corrupt → **drop** silently.
3. **Strip** Ethernet header/trailer; read **EtherType** (`0x0800` = IP) → hand up to L3.

**L3 Network (IP) — receives the packet:**
1. **Dst IP == my IP?** Yes → up. (A **router** whose it isn't would **forward** —
   route onward, MAC rewrite, TTL−1. An end host: not-mine → drop.)
2. **Verify** IP checksum; **reassemble fragments** if any.
3. Read **protocol** (`6` = TCP) → strip IP header → hand the segment up to L4.

**L4 Transport (TCP) — receives the segment:**
1. **Demultiplex by the 4-tuple** (dst port + the tuple) → find which socket/fd's Recv-Q.
2. **Verify** TCP checksum.
3. **Sequence numbers** → put bytes in order, detect missing/dup; **send ACK**;
   manage the **window** (flow control).
4. **Strip** TCP header → place in-order bytes into that socket's **Recv-Q**.

**L7 Application:** app `read(fd)` drains the Recv-Q; the server (uvicorn/ASGI)
**parses the HTTP message** and delivers it. Kernel gave a reliable ordered byte
stream; reconstructing the "HTTP message" is the app's job (socket boundary).

> Send-side note: TCP adds **not just ports** but **seq/ack numbers, flags,
> window, checksum** — the seq/ack are what make it *reliable/ordered*. The
> handshake runs at `connect()`, **before** any data; by `write()` time the
> connection is already ESTABLISHED. Segmentation is by **MSS** (≈ MTU − 40).

### Compressed mental model
```
[user]   curl ──write()/read()── fd5 ⇄ 4-tuple ⇄ fd7 ──read()/write()── server app
              │                     │                     │
[kernel] Send-Q/Recv-Q  ── TCP handshake / seq-ack ──  Send-Q/Recv-Q
              │            encapsulate ↓ / decapsulate ↑     │
[wire]        └── Eth│IP│TCP│HTTP ── Switch ── Router ── Switch ──┘
                                     (L2 fwd)  (L3 fwd, MAC rewrite, TTL−1)
```

### The five pinpoints
- **Socket creation:** server `socket→bind→listen` (fd3, LISTEN) once; client
  `socket→connect` (fd5) per request; server `accept` mints **fd7** per connection.
- **fd:** per-process handle → kernel socket object (holds the buffers).
  Listening fd ≠ connected fd.
- **Send-Q / Recv-Q:** kernel buffers **per connected socket**; `write()` fills
  Send-Q, `read()` drains Recv-Q; the wire moves Send-Q(C) → Recv-Q(S).
- **TCP born:** the **3-way handshake** — `accept()` returns only after final ACK.
- **TCP dies:** the **4-way FIN** — fds close, buffers freed, TIME_WAIT → CLOSED.

## 4. Mental model / analogy
A phone call: dial + pick up + "can you hear me?" = handshake (born); the
conversation = data over Send-Q/Recv-Q; "bye"/"bye" both ways = 4-way close
(dies). The post office (routers) relays each sentence hop by hop; you two
(end hosts) are the only ones who understand the words (L7).

## 5. Hands-on (what to show on screen)
```bash
# Watch the whole lifecycle on the wire (handshake → data → FIN):
sudo tcpdump -i lo0 -n 'tcp port 8000'
# then:
curl -v http://127.0.0.1:8000/hello        # (against miniapi/stage1_server.py)

# Watch sockets/fds appear and die:
lsof -nP -iTCP:8000                          # listening + connected sockets
netstat -an -p tcp | grep 8000               # states: LISTEN / ESTABLISHED / TIME_WAIT
```
Packet Tracer: swap a PC for a Server (HTTP on), browse to it in Simulation mode
to see the full ARP → SYN/SYN-ACK/ACK → GET → 200 animation.

## 6. Common misconceptions
- **"One socket handles everything."** No — a **listening** socket accepts; each
  connection gets its own **connected** socket (fd) via `accept()`.
- **"`socket()` opens the connection."** No — `socket()` only makes the endpoint
  (CLOSED); the connection is born later at `connect()`/`accept()` (the handshake).
- **"The client creates a pair of fds (client + server)."** No — each side makes
  its **own** fd independently on its own machine; the **4-tuple/connection** is
  the pairing, not a shared fd. (A real fd pair only comes from `socketpair()`,
  same-machine IPC.)
- **"TCP just adds ports."** No — also **seq/ack numbers, flags, window, checksum**;
  the seq/ack are what make it reliable and ordered.
- **"The kernel handles the whole OSI stack, including HTTP."** No — the kernel
  owns L4→L1; **L7 (HTTP/DNS) is your app.** The socket API is the boundary.
- **"The connection is a physical pipe."** It's an illusion TCP maintains over
  independent, shared, per-packet links.
- **"Data leaves the moment I write()."** No — it enters the **Send-Q**; the
  kernel sends when it can (flow/congestion control).
- **"IP changes as it's routed."** MAC changes per hop; IP src/dst constant; TTL−1.
- **"Closing a connection is instant."** TIME_WAIT holds the 4-tuple ~2×MSL.

## 7. Diagrams needed
1. **The 3-tier model** (user / kernel / wire) with fds, buffers, 4-tuple.
2. **Lifecycle timeline** — handshake → data → teardown, with state labels on
   each side (SYN_SENT … ESTABLISHED … TIME_WAIT … CLOSED).
3. **Per-hop packet** — MAC rewrite each hop, IP constant, TTL−1 (reuse).
4. **Encapsulation onion** (reuse from OSI overview).

## 8. Video script outline
- **Hook (0:00)** — "you type one `curl`. Here is *everything* that happens."
- **Build** — Phase A (server waiting) → B/C (client + ARP) → D (handshake:
  connection born) → E/F (request/response through the buffers) → G (teardown).
- **Payoff** — the compressed mental-model diagram; the 5 pinpoints.
- **Recap (3 bullets)** — listening vs connected socket · handshake births /
  FIN kills the connection · encapsulate down + route by IP + forward by MAC.

## 9. Brainstorm / open questions
- This is the capstone — record it LAST, after every layer has its own episode,
  so each phase can reference a prior video.
- Strong two-panel visual: left = the socket/fd/buffer view (host internals),
  right = the packet-on-the-wire view; play them in sync.
- Live demo idea: `tcpdump` + `netstat` side by side while curling — watch a
  connection go LISTEN → ESTABLISHED → TIME_WAIT in real time.

## 10. References
- Labs: `labs/01-end-to-end-flow-packet-tracer.md`, `labs/02-same-network-trace.md`
- Prior deep-dives (this project's sibling): sockets, fds, Send-Q/Recv-Q, TCP
  states, the ASGI server `miniapi/stage1_server.py`.
- Kurose & Ross — end-to-end principles; Beej's Guide to Network Programming.
