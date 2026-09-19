# Progress Tracker

Status legend: 🔲 not started · 🟡 studying · 🎥 ready to record · ✅ recorded

Order follows ROADMAP.md → Order A (spiral). Update after each session.

## Phase 0 — Orientation
| # | Topic | Status | Notes |
|---|-------|--------|-------|
| 1 | What is a network | 🟡 | doc filled; 3 brainstorm Qs open (thesis, packet-vs-circuit placement, N² hook) |
| 2 | OSI vs TCP/IP — the two maps | 🔲 | |

## Phase 1 — Down the stack (bottom-up)
| # | Topic | Status | Notes |
|---|-------|--------|-------|
| 3 | OSI overview / encapsulation | 🟡 | doc filled, grounded in Lab 01/02 traces; 2 brainstorm Qs (L5/L6 treatment, peer-to-peer animation) |
| 4 | Physical layer | 🔲 | |
| 5 | Data link / MAC | 🟡 | traced frame-by-frame in Lab 02 (ARP + MAC + switch-as-L2-forwarder); doc still to write |
| 6a | Network layer: IP & fragmentation | 🔲 | |
| 6b | IP address | 🔲 | |
| 6c | CIDR | 🔲 | |
| 6d | Subnetting | 🔲 | |
| 6e | Router / Switch / Gateway | 🟡 | doc filled from PT lab; debugging story captured. Lab 01 built & working |
| 6f | NAT | 🔲 | |
| 7a | Transport overview | 🟡 | head start (session deep-dive) |
| 7b | Ports | 🟡 | head start |
| 7c | Segmentation | 🟡 | head start |
| 7d | TCP | 🟡 | doc filled: reliability (sync/order/ACK/retransmit/FIN + Content-Length boundary), lifecycle. TODO: flow control, congestion control, state machine, UDP contrast |
| 7e | UDP | 🟡 | doc filled (2 axes: reliability + framing; use cases; QUIC) |
| 8a | Session layer | 🔲 | |
| 8b | Presentation layer | 🔲 | |
| 9a | Application overview | 🔲 | |
| 9b | DNS | 🔲 | |
| 9c | DHCP | 🔲 | |
| 9d | HTTP 1/2/3 | 🟡 | HTTP/1.1 essentials 1-5 done + HTTP/2 frames/streams/multiplexing (live nghttp) + HTTP/3/QUIC (doc: http3-quic.md). Remaining: #6 headers/compression; HTTPS/TLS |
| 9e | HTTPS / TLS / SSL | 🟡 | head start (TLS envelope discussion) |
| 10a | Firewall | 🔲 | |
| 10b | VPN | 🔲 | |

## Phase 2 — Consolidate
| # | Topic | Status | Notes |
|---|-------|--------|-------|
| 11 | TCP/IP model | 🔲 | |
| 12a | Sockets | 🟡 | strong head start (fds, buffers, states) |
| 12b | Socket states | 🟡 | head start |

## Phase 3 — Capstones
| # | Topic | Status | Notes |
|---|-------|--------|-------|
| 13 | Packet lifecycle end-to-end | 🟡 | capstone summary written (Phases A–G: socket/fd/buffers + handshake + per-hop + teardown). Record LAST. |
| 13b | **Request lifecycle in uvicorn** (above the socket) | 🟡 | doc written: `05-packet-lifecycle/uvicorn-request-lifecycle.md` — Phases 0/A–F traced step by step from a live instrumented server (`scripts/trace_server.py`). Covers event loop + kqueue/kevent, who wakes the loop (hardware interrupt), accept-queue vs Recv-Q, one-port-many-sockets, fd/memory limits + Little's Law, httptools → `scope`, `RequestResponseCycle` Task, the `asyncio.Event` bridge, backpressure to TCP. 13 misconceptions harvested. Record right after #13 as "the other half". |
| 14 | Mini project | 🔲 | |

---

### HTTP/1.1 deep-dive (end-to-end + HLD lens) — sub-progress
- [x] 1. Methods + idempotency/safety (doc: http11-methods-idempotency.md; live count demo)
- [x] 2. Status codes (doc: http11-status-codes.md; live families/redirect/304 demos)
- [x] 3. Statelessness→scaling ⭐ (doc: http11-statelessness-scaling.md; live cookie demo)
- [x] 4. Connection mechanics & HoL ⭐ (doc: http11-connection-mechanics-hol.md; live keep-alive/HoL timing + nghttp frame traces; HTTP/2 frames/streams/multiplexing fix)
- [~] 5. Caching ⭐ — TAUGHT (live freshness/max-age, ETag→304, CDN Cache-Control demos); DOC PENDING
- [ ] 6. Body framing + compression + headers
- (also done, out of #-order: HTTP/2 frames/streams/multiplexing, HTTP/3/QUIC — docs written)

### Session log
_Add a line per session: date · topic · what we covered · open questions._

- 2026-08-20 · Course scaffolded (dirs, template, README, ROADMAP, PROGRESS).
- 2026-08-21 · Topic 1 (What is a network) doc filled + "What's a node?" subsection.
- 2026-08-25 · Built Packet Tracer end-to-end lab (PC0—Switch0—Router0—Switch1—PC1);
  debugged to working (root cause: PC0 blank default gateway). Wrote Lab 01 +
  05-router-switch-gateway.md. Next payoff: Simulation-mode packet walk.
- 2026-09-02 · HTTP fundamentals (curl -v + stage1 TODO-7 body-framing bug live).
  Packet-lifecycle capstone written (Phases A–G + receive-side decapsulation +
  socket-boundary/fd-pairing fixes). Descended to Transport/TCP: wrote 03-tcp.md
  (reliability: sync/order/ACK/retransmit, FIN vs Content-Length). Lab 03 written.
- 2026-08-31 · Traced same-network ping (PC0→PC2) frame by frame in Simulation
  mode: ARP request/reply + ICMP request/reply, decoded every field; proved
  switch is a transparent L2 forwarder (Inbound==Outbound). Wrote Lab 02.
  Covered concepts: ARP mechanism, ping=ICMP=L3 (no ports), read-your-layer.
- 2026-09-17/18 · Traced ONE request from curl to the Python handler, step by step, with the
  user stating each step and it being corrected. Built `scripts/trace_server.py` (subclasses the
  real `HttpToolsProtocol`, so the log is genuine uvicorn internals). Live demos captured:
  one-port/many-sockets via lsof; a server that NEVER calls accept() still completing handshakes
  (→ TCP health checks pass on a wedged app); KQUEUE fd visible in lsof; STAT=S and 10ms CPU over
  3s while idle; blocked event loop (/block stalls an unrelated /fast for 5.76s) and
  `loop.slow_callback_duration` catching it. Wrote
  `docs/05-packet-lifecycle/uvicorn-request-lifecycle.md`.
  Biggest corrections made: listening socket has an ACCEPT QUEUE not Send-Q/Recv-Q; the server
  does NOT open a port per client (new socket, same port, 4-tuple distinguishes); kqueue is a
  passive DATA STRUCTURE, not a loop — nothing scans, the NIC interrupts and the kernel notifies
  as a side effect of enqueuing; `accept()` dequeues an already-established connection; it is not
  a socket "pair".
  RESOLVED: `--workers N` → Phase G in the doc (measured with lsof + a 1-vs-4-worker blocking test).
- 2026-09-19 · Wrote the first two Substack posts from the packet-flow material, in `posts/`:
  **01-what-happens-when-you-run-curl.md** (~2,100 words) — URL parse → DNS → socket/connect →
  Send-Q → segmentation → MAC-rewrite/IP-constant routing → decapsulation → 4-tuple demux →
  Recv-Q; built around four misconceptions, with the one-port/many-sockets `lsof` capture and the
  never-`accept()` demo (→ TCP health checks pass on a wedged app) as the two payoff moments.
  **02-how-tcp-fakes-a-reliable-pipe.md** (~2,000 words) — the four guarantees (sync / order /
  no-loss / no-more-coming) each priced with what it costs, head-of-line blocking as the price of
  ordering → why QUIC exists, plus flow control (why writes block) and congestion control
  (slow start: 14.6 KB then doubling, so 100 KB at 200 ms RTT = 600 ms regardless of bandwidth).
  Both end on hooks; **post 3 is already written as material** (who wakes the sleeping event loop
  — hardware interrupt, kqueue as a passive structure) in `05-packet-lifecycle/uvicorn-request-lifecycle.md`.
