# Roadmap — how to complete the course

> **ACTIVE PLAN (chosen 2026-08-31): Order C — Top-down.**
> Start at the Application layer (where the student already lives) and descend
> toward the wire. Orders A/B are kept below for reference.

## Order C — Top-down (ACTIVE)

Begin with what's familiar (HTTP/curl) and peel down into the mechanism beneath
each layer. Fits a coding-background student and leverages the earlier deep-dives
on sockets/TCP and the Packet Tracer L2/L3 traces (each descending layer closes a
loop on something already seen).

```
Phase 0 — The map (done, direction-agnostic)
  [x] What is a network      [x] OSI overview

Descend the stack:
  L7  Application   -> overview -> HTTP 1/2/3 -> HTTPS (TLS/SSL) -> DNS -> DHCP
  L5/6 Session/Presentation -> folded into TLS/HTTPS
  L4  Transport     -> ports -> TCP -> UDP -> segmentation   (head start: socket dives)
  L3  Network       -> IP address -> CIDR -> subnetting -> routing -> NAT
  L2  Data Link     -> MAC -> framing -> ARP -> switching     (traced in Lab 02)
  L1  Physical      -> signals, media, encoding

Consolidate & capstone:
  TCP/IP model -> Sockets -> Packet lifecycle (end-to-end) -> Mini project
```

**Note on already-done docs:** Router/Switch/Gateway and Data Link/MAC (Lab 02)
sit at the bottom of the stack — in top-down they come *later*. They're a
"preview from the wire"; deepen & formally place them when descending to L2/L3.

---

## (Reference) Order A / Order B

Two earlier orders. Order A (spiral) was the original recommendation; Order B is
the strict fundamentals-first outline.

---

## Order A — Spiral (recommended for teaching)

**Idea:** give the student the *map* first, then walk the layers **bottom-up**
(wire → app, the direction data is actually built and sent), folding the
"fundamentals" into the layer where they live. Finish with two capstones that
force every piece to connect. This is how the concepts reinforce each other on
camera — each layer earns the next.

### Phase 0 — Orientation (the map) · ~1 session
1. `00-orientation/01-what-is-a-network` — hosts, links, addresses, the core question.
2. `00-orientation/02-osi-vs-tcpip-the-two-maps` — the mental scaffold every later
   lesson hangs on. Teach both models side by side here, once.

### Phase 1 — Down the stack, bottom-up · the bulk of the course
3. `02-osi-model/00-overview` — the 7 layers as one picture; encapsulation.
4. `02-osi-model/01-physical` — signals, bits, what "on the wire" means.
5. `02-osi-model/02-data-link-mac` — frames, MAC addresses, switches (local delivery).
6. **Network layer block** (fundamentals live here):
   - `02-osi-model/03-network-ip-fragmentation`
   - `01-fundamentals/01-ip-address`
   - `01-fundamentals/02-cidr`
   - `01-fundamentals/03-subnetting`
   - `01-fundamentals/05-router-switch-gateway` (routing between networks)
   - `01-fundamentals/04-nat`
7. **Transport layer block:**
   - `02-osi-model/04-transport/00-overview`
   - `.../01-ports` · `.../02-segmentation` · `.../03-tcp` · `.../04-udp`
8. **Session / Presentation:**
   - `02-osi-model/05-session` · `02-osi-model/06-presentation`
   - (TLS/SSL introduced here conceptually; detailed under application/HTTPS)
9. **Application layer block:**
   - `02-osi-model/07-application/00-overview`
   - `.../01-dns` · `.../04-dhcp` (how you even get an address / find one)
   - `.../02-http-1-2-3` · `.../03-https-tls-ssl`
10. **Security devices** (now that layers exist to place them on):
    - `01-fundamentals/07-firewall` · `01-fundamentals/06-vpn`

### Phase 2 — Consolidate · ~2 sessions
11. `03-tcp-ip-model/tcp-ip-model` — re-map the 4-layer model onto everything learned.
12. `04-sockets/01-sockets` + `04-sockets/02-socket-states` — the programmer's
    handle to the stack (you already have a strong head start here).

### Phase 3 — Capstones · the payoff
13. `05-packet-lifecycle/packet-lifecycle-end-to-end` — trace ONE request from
    `curl` keystroke to server and back, naming every layer, header, and device
    it touches. This is the episode that proves the whole course.
14. `06-mini-project/mini-project` — build/observe an end-to-end flow yourself.

---

## Order B — Your original outline (strict top-down)
Fundamentals (IP → CIDR → Subnetting → NAT → devices → VPN → Firewall) →
OSI (Physical → … → Application) → TCP/IP model → Sockets → Packet lifecycle →
Mini project. Perfectly valid; just teaches abstract addressing before the
layer model that explains *where* addressing sits.

---

## Pacing (self-paced — targets, not deadlines)
- **1 topic ≈ 1–2 sessions**: brainstorm → deep-dive doc → hands-on capture →
  script the video.
- Don't record until the doc's **misconceptions** and **hands-on** sections are
  filled — that's the signal you understand it well enough to teach.
- Batch the **diagrams** for a phase together (consistent visual style for videos).
- Revisit `PROGRESS.md` after each topic.

## Your head start (from earlier deep-dives this session)
Transport (TCP, ports, segmentation), Sockets + socket states, and much of the
Packet-lifecycle capstone were already explored in depth. Those docs should be
fast to fill — mostly transcription + diagramming.
