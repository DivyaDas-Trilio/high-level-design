# Router, Switch, Gateway

> **Status:** 🟡 studying
> **Prereqs:** [[01-what-is-a-network]] (nodes, local vs global delivery)
> **OSI layer / where it lives:** Switch = Layer 2 (Data Link, MAC) ·
> Router = Layer 3 (Network, IP)
> **Est. depth:** core fundamentals; anchors the local-vs-global skeleton.

## 1. One-liner
A **switch** connects hosts *within one* network (forwards by MAC — local
delivery); a **router** connects *different* networks (forwards by IP — global
delivery); the **gateway** is the router interface a host uses as its "door out."

## 2. The problem it solves
- Many hosts in one network can't be wired N² → a **switch** gives them a shared
  local fabric and forwards frames only where needed.
- Separate networks (different subnets, different owners) are **isolated
  islands** → a **router** bridges them, because it's the only device with an
  address (interface) in each.

## 3. Deep dive — the mechanism

### Reference topology (from the Packet Tracer lab)
```
┌─── Network 1: 192.168.1.0/24 ───┐        ┌─── Network 2: 192.168.2.0/24 ───┐

  PC0 ───── Switch0 ───── Router0.Fa0/0 │ Router0.Fa1/0 ───── Switch1 ───── PC1
192.168.1.10          192.168.1.1        192.168.2.1                    192.168.2.10
└──────── one "island" ─────────┘        └──────── other "island" ────────┘
```
The router **straddles both** networks — the only device with a foot in each.
That single fact defines both roles. **Rhythm to see:** switch → router → switch
= *local delivery · cross the boundary · local delivery.*

### The SWITCH — holds ONE network together (local delivery)
- **Layer 2 (Data Link).** Thinks in **frames**, forwards by **MAC**; has no idea
  what an IP is.
- **Job:** connect all devices *within a single network*. Switch0's whole world
  is network 1; Switch1's is network 2.
- **Never crosses networks** — cannot move a packet from `192.168.1.x` to
  `192.168.2.x` (no IP, no routing table, doesn't touch TTL).
- **How it decides:** learns a **MAC→port table** by watching source MACs, then
  forwards each frame only to the destination MAC's port
  (`show mac address-table`). Unknown/broadcast → flood.
- **Scaling role:** the switch is what lets one network hold **many** hosts —
  add PC2, PC3, a printer to Switch0 and they intercommunicate by MAC *without
  bothering the router*. (In the minimal lab topology each switch has only 2
  ports used, so its value isn't obvious — that's why.)

### The ROUTER — connects DIFFERENT networks (global delivery)
- **Layer 3 (Network).** Thinks in **packets**, forwards by **IP**, using its
  **routing table** (`show ip route` → two `C` connected routes:
  `192.168.1.0/24 → Fa0/0`, `192.168.2.0/24 → Fa1/0`).
- **A node with one interface in each network:** `Fa0/0 = 192.168.1.1` (net 1),
  `Fa1/0 = 192.168.2.1` (net 2). That's literally what "connects two networks"
  means — an address on each side.
- **The boundary / the door.** Each host's **default gateway = this router**.
  Without it, the two networks are isolated islands (exactly why cross-network
  ping fails until gateways are correct).
- **What it does to a packet:** look up dest IP in the routing table → **rewrite
  the MAC header** for the next hop → **decrement TTL** → forward. The **IP
  src/dst stay unchanged** end-to-end.

### The GATEWAY — the host's exit
- "Default gateway" = the router interface **in the host's own subnet** that a
  host sends off-network traffic to.
- **Rule (absolute):** a host's gateway MUST be in the host's own subnet — it
  must be reachable directly on the local wire (same-subnet ARP). A gateway in a
  different subnet is unreachable → no way out. See [[03-subnetting]] / [[02-cidr]].

## 4. Packet walk — roles in action (PC0 → PC1)
| Step | Where | Who acts | What happens |
|------|-------|----------|--------------|
| 1 | PC0 | PC0 | Dest `192.168.2.10` is a **different** subnet → send to gateway `192.168.1.1`. Frame: dst **MAC = Router Fa0/0**, dst **IP = 192.168.2.10** |
| 2 | Net 1 | **Switch0** | Forwards frame by MAC to the router's port. *Local delivery.* |
| 3 | Router0 | **Router0** | Dst IP → net 2 on `Fa1/0`. **Rewrites MAC** (src=Fa1/0, dst=PC1), **TTL −1**, sends out Fa1/0. *Crosses the boundary.* |
| 4 | Net 2 | **Switch1** | Forwards frame by MAC to PC1's port. *Local delivery.* |
| 5 | PC1 | PC1 | Receives; reply retraces the path. |

**The invariant to freeze on:** MAC header is **rewritten at each hop** (local),
IP src/dst is **constant end-to-end** (global). TTL −1 per router.

## 5. Hands-on (what to show on screen)
```
! On the router:
show ip interface brief     ! Fa0/0 & Fa1/0 up/up with their IPs
show ip route               ! two "C" (connected) routes = it knows both networks

! On a switch:
show mac address-table      ! the MAC->port map it learned

! On a PC:
ping 192.168.2.10           ! cross-network (uses the gateway/router)
ping 192.168.1.11           ! same-network (switch only, no router)
tracert 192.168.2.10        ! shows the router hop
ipconfig /all               ! confirm IP / mask / default gateway
```

## 6. Common misconceptions
- **"Switch and router are the same / interchangeable."** No — switch = intra-
  network (L2, MAC); router = inter-network (L3, IP). Different layers, different
  jobs.
- **"The switch routes between networks."** Never. A switch stays inside one
  network; only a router crosses subnets.
- **"Ping to the gateway working proves the gateway is set."** FALSE POSITIVE —
  the gateway IP is in your own subnet, reached *directly* without using the
  default-gateway setting. Always test with an **off-subnet** destination.
- **"Any gateway address will do."** No — the gateway must be in the host's own
  subnet, or it's unreachable.
- **"The IP address changes as it's routed."** No — MAC changes per hop; IP src/
  dst stay constant end-to-end.

## 7. Diagrams needed
1. **Two islands + bridge** — the reference topology, each network boxed, router
   straddling both; label Fa0/0 / Fa1/0 with their IPs.
2. **Packet walk** — the 5-step table as an animation: MAC rewritten each hop,
   IP constant, TTL −1 at the router.
3. **Switch scaling** — Switch0 with 1 host vs. with 5 hosts (why the switch
   matters when a network grows).
4. **Layer map** — switch tagged L2/MAC, router tagged L3/IP.

## 8. Video script outline
- **Hook (0:00)** — "same cable colour, same green lights — why can PC0 reach
  the switch instantly but need help to reach the other side?" Two islands.
- **Build** —
  1. See the two networks (subnets) in the topology.
  2. Switch = local fabric, forwards by MAC, never leaves its island; scales hosts.
  3. Router = the only node in both islands; forwards by IP; the gateway/door.
  4. Walk one packet: switch → router → switch; freeze on MAC-rewrite-IP-constant.
- **Payoff** — the debugging story (below) proves every role concretely.
- **Recap (3 bullets)** — switch = intra (L2/MAC) · router = inter (L3/IP) ·
  gateway = your subnet's door, must be in your subnet.

## 9. Brainstorm / open questions
- The minimal lab topology hides the switch's value (2 ports each) — worth a
  second topology with many hosts per switch to make the point on camera.
- Great troubleshooting story to teach (from the lab build):
  1. **Ping outward hop by hop** (gateway → far interface → destination) to
     localize a break.
  2. **Router was perfect** (`show ip route` had both `C` routes) — verify and
     rule it out; don't assume.
  3. **Two traps that fooled us:** (a) *same-subnet gateway ping is a false
     positive* — reaching `192.168.1.1` didn't prove PC0 had a gateway, since
     that IP is local; test with an off-subnet dest. (b) *gateway must be in the
     host's own subnet* — swapped PC1/PC2 gateways broke routing.
  4. **Root cause:** PC0's own **default gateway was blank** — the host we pinged
     *from* was the one missing its door. Off-subnet traffic needs the gateway.
- Foreshadows: ARP (L2↔L3 bridge, Data Link topic), routing-table lookup, TTL.

## 10. References
- Lab: `labs/01-end-to-end-flow-packet-tracer.md`
- Kurose & Ross, *Computer Networking* — link layer (switches) & network layer
  (routers, forwarding).
