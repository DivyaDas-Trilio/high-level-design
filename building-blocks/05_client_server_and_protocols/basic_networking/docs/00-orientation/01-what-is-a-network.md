# What Is a Network

> **Status:** 🟡 studying
> **Prereqs:** none (course opener)
> **OSI layer / where it lives:** the whole stack in miniature — this topic
> defines the problem every later layer solves.
> **Est. depth:** foundational; sets the central thesis for the course.

## 1. One-liner
A network is a set of **nodes that can address and reach each other over a
shared medium, under a common agreement (protocol)** — it is the *agreement +
addressing*, not the wires.

## 2. The problem it solves
A byte lives in the memory of process A on machine X. We want that exact byte to
appear in the memory of process B on machine Y. The minimum that must be true:

1. **A medium** — something physical that carries a signal between X and Y
   (copper, fiber, radio). Bytes ↔ voltage/light/waves.
2. **Addressing** — Y must be *nameable*, so X can say "this is for Y, not Z."
3. **An agreement (protocol)** — X and Y must agree what the signals *mean*:
   where a message starts/ends, which bits are address vs. payload.

Everything else in the course (IP, TCP, switches, routers) is an *implementation*
of these three ideas.

## 3. Deep dive — the mechanism

### What's a node?
A **node** is *anything on the network that has an address* — can send, receive,
or forward data (laptop, server, phone, router, switch, printer). Term borrowed
from graph theory: a network **is** a graph — **nodes = vertices, links = edges**
(so "N nodes, N² links" = counting vertices and the edges between them).

The twist: a node is **not** "a physical box" — it's a **network interface (NIC)
with an address**, and *the address is bound to the interface, not the machine*.
Consequences:
- **One machine can be several nodes** — Wi-Fi + Ethernet + VPN = three
  interfaces, each with its own address (`ifconfig` / `ip addr`: `lo0`, `en0`,
  `utun3`…).
- **A router is a node with one interface on each network** — that's precisely
  what "belongs to two networks and forwards between them" means.
- **Virtual nodes are real nodes** — a VM/container has a virtual NIC with its
  own MAC/IP; indistinguishable from a physical node.

Two roles: **end nodes (hosts)** originate/consume data (graph leaves);
**intermediate nodes** (router, switch) forward for others (internal vertices)
and usually process only the lower layers — a switch reads MAC, a router reads
IP, neither cares about the payload.

Vocabulary kept straight: **node** (anything addressable) ⊃ **host** (an *end*
node) · **interface** (the attachment point holding the address; a node has ≥1) ·
**endpoint** (the addressed *process* = IP **+ port**, the socket sense). Zoom
levels: machine → interface(s) → address(es) → endpoint(s).

### Why it's hard: the N² problem
Two machines is trivial (one wire). Difficulty appears with **many** nodes.
Wiring every pair directly needs:

```
C(N,2) = N(N-1)/2  ≈  N²/2 links
```
- 10 machines → 45 cables
- 1,000 machines → ~500,000 cables

**Direct connection does not scale.** The entire field answers one question:
*how do N nodes reach each other without N² links?* Two ideas follow.

### Idea (a): shared links + forwarding
Nodes share links; some nodes **forward** traffic for others. That is exactly
what a **switch** (within a network) and a **router** (between networks) are —
forwarding boxes. N nodes now need ~N links to a shared fabric, not N².

### Idea (b): packet switching (the defining choice of the internet)
- **Circuit switching** (old telephone net): reserve a dedicated end-to-end path
  before talking. Guaranteed capacity, but wasteful (idle during pauses) and
  doesn't scale.
- **Packet switching** (the internet): chop the message into **packets**, each
  carrying the destination address; each travels independently; each forwarding
  box decides per-packet where to send it next. Links are shared moment-to-moment
  by everyone (**statistical multiplexing**). Efficient and resilient (packets
  route around dead links).

**Cost of packets:** they can arrive **out of order**, be **duplicated**, or be
**lost**. → *That trade-off is exactly why TCP exists* — it rebuilds a reliable,
ordered byte stream on top of an unreliable packet network.

### A network of networks
A single network (home LAN: laptop, phone, router) = nodes that reach each other
directly. `api.example.com` sits on a *different* network. To interconnect
independent, separately-owned networks with no global authority:
- add a node belonging to **two** networks that forwards between them — a
  **router/gateway**, and
- agree on a **universal** addressing + protocol (**IP**) across all of them.

Result: an **internet** ("inter-network") — a network *of* networks, owned by
no one, cooperating networks speaking IP at the boundaries.

**Course skeleton in one idea:** *local delivery within a network*
(Data Link / MAC / switches) vs. *global delivery across networks*
(Network layer / IP / routers). Most of the course hangs on this split.

## 4. Mental model / analogy
Postal system: houses (nodes) have **addresses**; you don't run a private road to
every house (no N² roads) — you drop a letter into a **shared** system that
**forwards** it hop by hop; each letter (**packet**) carries its own destination
and is handled independently. Different post offices (networks) interconnect via
sorting hubs (routers) under one addressing scheme (IP).

## 5. Hands-on (what to show on screen)
```bash
# Same node — never leaves the machine (loopback). Capture on lo0:
sudo tcpdump -i lo0 -n 'tcp port 8000'
curl http://localhost:8000/

# Different node — crosses networks. Watch the hops it takes to get there:
traceroute example.com        # each line = one forwarding box (router) en route
ping example.com              # round-trip time = distance + hops
dig example.com               # the name → IP (address) lookup that makes it reachable
```
On camera: contrast `localhost` (no medium, no forwarding — a kernel shortcut)
vs. `example.com` (many router hops in `traceroute`).

## 6. Common misconceptions
- **"The network is the cables/router."** No — it's the *agreement + addressing*
  that makes the cables mean something. Wires without a protocol are just noise.
- **"Messages travel as one whole thing."** No — they're split into independent
  **packets** that may take different paths and arrive out of order.
- **"There's one big internet someone owns."** No — it's many independent
  networks cooperating via IP at their boundaries.
- **"A dedicated connection is reserved for my request."** Only conceptually
  (TCP gives that illusion); physically the links are shared per-packet.

## 7. Diagrams needed
1. **N² explosion** — 4 nodes fully meshed, then 10; count the cables blowing up.
   Then the same nodes on a shared switch (~N links). *The core hook.*
2. **Circuit vs. packet switching** — reserved path vs. independent packets
   sharing links (statistical multiplexing).
3. **Network of networks** — two LANs + a router/gateway bridging them under IP;
   label "local delivery" vs. "global delivery."
4. **loopback vs. remote** — `localhost` short-circuit in the kernel vs. a
   multi-hop path to a remote host.

## 8. Video script outline
- **Hook (0:00)** — two identical-looking `requests.get` calls; one crosses the
  planet, one never leaves the machine. What must exist for the first to work?
- **Build** —
  1. Strip to the atom: byte in A's memory → B's memory; the 3 requirements.
  2. Why it's hard: draw the N² explosion → shared links + forwarding.
  3. The design choice: circuit vs. packet switching; the cost (loss/reorder) →
     foreshadow TCP.
  4. Scale it out: network of networks; router/gateway + IP.
- **Payoff** — re-explain the two `requests.get` calls with the new vocabulary
  (loopback vs. multi-hop across networks).
- **Recap (3 bullets)** — network = agreement + addressing (not wires) · can't
  wire N² so we forward packets · the internet is networks-of-networks.

## 9. Brainstorm / open questions
- Central thesis to open the course: *"network = agreement + addressing, not the
  wires."* Powerful unlock, but abstract for episode 1 — confirm it lands.
- Packet-vs-circuit switching: keep in Topic 1 as the "why it's built this way"
  payoff, or spin into its own beat? (Highest-leverage idea, also the deepest.)
- The N² hook (4 → 10 nodes exploding) as the on-camera opener — strong visual.
- Audience = coding background: open from a code symptom (`requests.get` /
  `curl`), then fall to the wire.

## 10. References
- Peterson & Davie, *Computer Networks: A Systems Approach* — Ch. 1 (framing).
- Kurose & Ross, *Computer Networking: A Top-Down Approach* — Ch. 1
  (packet vs. circuit switching, network of networks).
