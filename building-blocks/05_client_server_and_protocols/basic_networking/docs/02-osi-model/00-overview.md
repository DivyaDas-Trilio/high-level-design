# OSI Model — Overview

> **Status:** 🟡 studying
> **Prereqs:** [[01-what-is-a-network]] + the Packet Tracer traces
> (Lab 01/02) — students should have *seen* frames before this abstraction.
> **OSI layer / where it lives:** the whole map.
> **Est. depth:** foundational framework; consolidates the hands-on traces.

## 1. One-liner
The OSI model splits "move a byte from A to B" into **7 layers**, each solving
one sub-problem; data is **encapsulated** (wrapped) going down the sender's stack
and **decapsulated** (unwrapped) going up the receiver's — and each layer
logically talks to its **peer** layer on the other host.

## 2. The problem it solves
"Get a byte from process A to process B across the planet" is too big to design
as one blob — it spans signals, addressing, routing, reliability, encryption,
and app semantics. **Layering = separation of concerns:** each layer does one
job, uses the layer below as a service, and is independently replaceable (swap
Wi-Fi for Ethernet without touching HTTP; swap HTTP for FTP without touching IP).

## 3. Deep dive — the mechanism

### The 7 layers (anchored to what the traces showed)
Top (app) → bottom (wire):

| # | Layer | Job | PDU | Address | Seen as… |
|---|-------|-----|-----|---------|----------|
| 7 | **Application** | app-level protocol | data | — | HTTP `GET /`; ping the tool |
| 6 | **Presentation** | format / encrypt / encode | data | — | TLS, JSON/UTF-8 |
| 5 | **Session** | manage a dialog | data | — | TLS session, conn setup |
| 4 | **Transport** | reliable/ordered, **ports** | segment | port | TCP handshake; *absent in ping* |
| 3 | **Network** | route across networks | packet | IP | the `IP` box (src/dst IP, TTL); ICMP |
| 2 | **Data Link** | local delivery, framing | frame | MAC | the `EthernetII` box (dst/src MAC) |
| 1 | **Physical** | bits as signals | bits | — | PREAMBLE, the green link, the wire |

Mnemonic (bottom-up): **P**lease **D**o **N**ot **T**hrow **S**ausage **P**izza **A**way.

Notice from the traces:
- The **ping frame had L2 + L3 only** (Ethernet + IP + ICMP) — **no L4**, no ports,
  because ICMP lives at L3. The "missing transport layer" was OSI showing a
  protocol that skips a layer.
- An **HTTP frame** adds **L4 (TCP + ports)** and **L7 (HTTP)** — a taller stack.

### Encapsulation ↓ / decapsulation ↑ (the vertical journey)
**Sender — encapsulation (top→down):** each layer wraps the data above with its
own header.
```
L7  [ HTTP GET ]
L4  [ TCP hdr | HTTP GET ]              + ports, seq
L3  [ IP hdr | TCP hdr | HTTP GET ]     + src/dst IP, TTL
L2  [ Eth hdr | IP hdr | ... | FCS ]    + src/dst MAC
L1   101010101…                          bits on the wire
```
**Receiver — decapsulation (bottom→up):** each layer strips its own header and
hands the rest up (L2 checks MAC → L3 checks IP → L4 finds socket by port → L7
app reads data). This is exactly the Outbound (built down) vs Inbound (unwrapped
up) the PDU inspector showed.

### The horizontal view — each layer talks to its peer
Data physically goes **down** PC0's stack and **up** PC2's, but *logically* each
layer acts as if speaking directly to the **same layer** on the other host:
```
PC0                      PC2
L7 HTTP  ⟷ logical ⟷    L7 HTTP     understood app-to-app
L4 TCP   ⟷ logical ⟷    L4 TCP      seq/ack/ports peer-to-peer
L3 IP    ⟷ logical ⟷    L3 IP       src/dst IP host-to-host
L2 Eth   ⟷ logical ⟷    L2 Eth      MACs hop-to-hop
       ↓ actually down then up ↓
```
Each header is a note **only its peer layer reads** — the MAC header between L2
peers, the IP header between L3 peers, the port between L4 peers.

### Where devices operate (the read-your-layer principle)
- **Switch = L2** — reads Ethernet header, forwards by MAC (Inbound==Outbound).
- **Router = L3** — reads IP header, routes, rewrites L2, TTL−1 (Inbound≠Outbound).
- **End hosts = full stack** L1→L7.
A device at layer N reads down to N and leaves N+1 and above **sealed** — which
is why the switch never saw the IP/ICMP it carried, and why a router can't read
your TLS. See [[05-router-switch-gateway]].

### Caveat: reference model vs. reality
OSI is a **reference/teaching model**. The real internet runs the **TCP/IP model**
(4 layers) — merges OSI 5/6/7 into "Application" and 1/2 into "Link". But everyone
*talks* OSI ("Layer 3 problem", "Layer 7 load balancer"). Details: [[tcp-ip-model]]
and the two-maps topic.

## 4. Mental model / analogy
Sending a gift internationally: you box the gift (L7 data), put it in a shipping
carton with a label (L4), the carton in a container with a manifest (L3), loaded
on a truck with a route sheet (L2), driven on roads (L1). Each handler reads only
*their* label; the recipient unboxes in reverse.

## 5. Hands-on (what to show on screen)
- Reuse Lab 02's PDU inspector: point at the stacked boxes and name each layer.
- ICMP frame → "L2 + L3, no L4" ; HTTP frame → "L2+L3+L4+L7" (taller stack).
- Switch Inbound==Outbound (operates at L2) vs router Inbound≠Outbound (L3).
```bash
# On a real host, watch encapsulation live:
sudo tcpdump -i lo0 -nvv 'tcp port 8000'   # see Eth/IP/TCP headers stack up
```

## 6. Common misconceptions
- **"OSI is what the internet runs."** No — it's a *reference* model; TCP/IP is
  what actually runs. OSI is the shared vocabulary.
- **"Every packet uses all 7 layers."** No — ping skips L4–L7; ARP is ~L2.5.
- **"Data moves sideways between hosts at each layer."** Physically it goes down
  then up; the peer-to-peer conversation is *logical*.
- **"Higher layer = more important."** They're a stack of services, not a ranking.

## 7. Diagrams needed
1. **The 7-layer stack** with PDU + address + a real example per layer.
2. **Encapsulation onion** — headers nesting L7→L1 (reuse the trace).
3. **Two stacks, peer-to-peer** — dotted horizontal lines between same layers,
   solid path down-and-up. (High-value animation.)
4. **Device altitude** — switch at L2, router at L3, host full-stack.

## 8. Video script outline
- **Hook (0:00)** — "you've been looking at the OSI model this whole time" —
  the PDU inspector's stacked boxes ARE the layers.
- **Build** — why layer (separation of concerns) → the 7 layers with what we saw
  → encapsulation/decapsulation (the onion) → peer-to-peer logical conversation
  → where switch/router sit.
- **Payoff** — re-explain the ping frame (L2+L3, no L4) and an HTTP frame
  (adds L4+L7) using the model.
- **Recap (3 bullets)** — layering = separation of concerns · encapsulate down /
  decapsulate up · each layer talks to its peer.

## 9. Brainstorm / open questions
- L5/L6 (Session/Presentation) are fuzzy — teach as real layers, or as "OSI says
  they exist; TLS straddles them; TCP/IP merges them"? (Leaning: teach honestly
  as the latter.)
- Peer-to-peer "logical conversation" = strong animation candidate.
- Timing works well *because* students saw frames first (Lab 01/02) — abstraction
  after concrete experience.

## 10. References
- Labs: `labs/01-end-to-end-flow-packet-tracer.md`, `labs/02-same-network-trace.md`
- Tanenbaum, *Computer Networks* — Ch. 1 (the reference model).
- Kurose & Ross — Ch. 1 (layering, encapsulation).
