# Lab 01 — End-to-End Flow in Cisco Packet Tracer

> **Goal:** build two hosts on two *different* networks, joined by a router, and
> watch a single packet travel source → destination through switches and the
> router — inspecting how it changes at each hop.
> **Maps to:** `docs/05-packet-lifecycle/` (the capstone) and
> `docs/01-fundamentals/05-router-switch-gateway.md`.
> **Time:** ~30–40 min.

## The topology we're building

```
   PC-A                          Router                          PC-B
192.168.1.10/24            (a node in BOTH networks)         192.168.2.10/24
   │                       G0/0 ─┐        ┌─ G0/1                   │
   │                    192.168.1.1     192.168.2.1                 │
 [Switch1] ──────────────────┘            └────────────────── [Switch2]
   Network 1: 192.168.1.0/24              Network 2: 192.168.2.0/24
```

- Two separate networks (subnets): `192.168.1.0/24` and `192.168.2.0/24`.
- The **router** has one interface in each network — it's the only path between them.
- Each PC's **default gateway** = the router's interface *in its own network*.

---

## Step 1 — Place the devices

From the bottom-left device palette:
1. **End Devices → PC:** drop **PC-A** and **PC-B**.
2. **Switches → 2960:** drop **Switch1** and **Switch2**.
3. **Routers → 2911** (has GigabitEthernet0/0 and 0/1; simple naming): drop **Router0**.

## Step 2 — Cable them

Use **Connections** (the lightning-bolt icon) → pick **Copper Straight-Through**
(or the auto "lightning bolt" to let PT choose):

| From | Port | To | Port |
|------|------|----|------|
| PC-A | FastEthernet0 | Switch1 | FastEthernet0/1 |
| Switch1 | GigabitEthernet0/1 | Router0 | GigabitEthernet0/0 |
| Router0 | GigabitEthernet0/1 | Switch2 | GigabitEthernet0/1 |
| Switch2 | FastEthernet0/1 | PC-B | FastEthernet0 |

Link lights start red/amber → turn **green** once interfaces are up (router
interfaces come up after Step 4).

## Step 3 — Configure the PCs

Click **PC-A → Desktop tab → IP Configuration**:
- IP Address: `192.168.1.10`
- Subnet Mask: `255.255.255.0`
- Default Gateway: `192.168.1.1`   ← the router's interface in network 1

Click **PC-B → Desktop → IP Configuration**:
- IP Address: `192.168.2.10`
- Subnet Mask: `255.255.255.0`
- Default Gateway: `192.168.2.1`   ← the router's interface in network 2

## Step 4 — Configure the router (CLI)

Click **Router0 → CLI tab**, press Enter, then type:

```
enable
configure terminal

interface GigabitEthernet0/0
 ip address 192.168.1.1 255.255.255.0
 no shutdown
exit

interface GigabitEthernet0/1
 ip address 192.168.2.1 255.255.255.0
 no shutdown
exit

end
write memory
```

`no shutdown` powers the interface on (that's what turns the links green). No
routing protocol needed — the router now has both networks **directly connected**,
so it already knows how to reach each. Verify:

```
show ip interface brief      # both G0/0 and G0/1 show "up / up"
show ip route                # two "C" (connected) routes: .1.0/24 and .2.0/24
```

## Step 5 — Verify reachability (Realtime mode)

**PC-A → Desktop → Command Prompt:**
```
ping 192.168.2.10
```
First packet may time out (ARP resolving), rest should reply. If it works, you
have end-to-end connectivity across two networks. Also try:
```
tracert 192.168.2.10         # shows the router hop (192.168.2 side) in the path
```

---

## Step 6 — THE PAYOFF: watch it packet-by-packet (Simulation mode)

This is the part to screen-record for the course.

1. Switch to **Simulation** mode (bottom-right, or the stopwatch icon).
2. (Optional) **Edit Filters →** show only **ICMP** and **ARP** to cut noise.
3. On **PC-A → Desktop → Command Prompt**, run `ping 192.168.2.10` once.
4. Use **Capture / Forward** (or the **▶ play** / **Next** buttons) to advance
   **one event at a time** and watch the envelope hop across the topology.
5. **Click the envelope** at each hop → the **PDU Information** window opens with
   an **OSI Model** tab (all 7 layers) and an **Inbound/Outbound PDU Details**
   tab (the actual header bytes).

### What to observe and narrate (the teaching gold)

- **First there's an ARP broadcast.** PC-A knows PC-B's *IP* but not a MAC. Since
  PC-B is on another network, PC-A ARPs for its **gateway** (`192.168.1.1`), not
  PC-B. Watch the ARP frame flood, the router answer, PC-A learn the router's MAC.
- **Layer 2 (MAC) header changes at every hop; Layer 3 (IP) header does NOT.**
  - PC-A → Router: `src MAC = PC-A`, `dst MAC = Router G0/0`. IP: `src 1.10 → dst 2.10`.
  - Router → PC-B: `src MAC = Router G0/1`, `dst MAC = PC-B`. IP: **still** `1.10 → 2.10`.
  - **This is the single most important frame to freeze on camera:** the MAC
    addresses get rewritten by the router (local delivery, hop by hop), while the
    IP src/dst stay constant end-to-end (global delivery, whole journey). It's
    "local vs global delivery" made visible.
- **TTL decrements by 1** at the router (see it in the IP header) — proof the
  router is a real L3 hop.
- **The switches don't change anything** — they just forward the frame to the
  right port based on dst MAC (inspect their MAC tables: `show mac address-table`).

---

## Step 7 (optional) — Make it a real *application* flow (HTTP)

To show the full stack up to Layer 7, swap PC-B for a **Server**:
1. Delete PC-B, drop **End Devices → Server** as **Server0**, same IP setup
   (`192.168.2.10/24`, gw `192.168.2.1`).
2. **Server0 → Services → HTTP:** ensure HTTP service is **On** (it serves a
   default page).
3. **PC-A → Desktop → Web Browser →** go to `http://192.168.2.10`.
4. In Simulation mode you now see the full sequence: **ARP → DNS (if using a
   name) → TCP 3-way handshake (SYN/SYN-ACK/ACK) → HTTP GET → HTTP 200 response**,
   each inspectable layer-by-layer. This is your entire course, animated in one run.

---

## What to record for the videos
1. Topology overview (the two-networks-one-router picture).
2. Simulation of ONE ping: the ARP, then the frame crossing, freezing on the
   **MAC-rewrite-but-IP-constant** frame at the router.
3. The TTL decrement.
4. (Capstone episode) the HTTP run showing handshake + request/response.

## Save
`File → Save As` → keep the `.pkt` file in `labs/` (e.g.
`labs/end-to-end.pkt`) so you can reopen the exact topology for re-takes.
