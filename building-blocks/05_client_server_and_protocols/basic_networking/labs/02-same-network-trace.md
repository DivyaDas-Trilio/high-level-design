# Lab 02 — Same-Network Delivery, Traced Frame by Frame (Packet Tracer)

> **Goal:** trace a ping between two hosts on the SAME network and see every
> frame — ARP request → ARP reply → ICMP request → ICMP reply — with the switch
> as a pure L2 forwarder (no router involved).
> **Maps to:** `docs/02-osi-model/02-data-link-mac.md`,
> `docs/01-fundamentals/05-router-switch-gateway.md`, `docs/05-packet-lifecycle/`.
> **Topology:** PC0 `192.168.1.10` — Switch0 — PC2 `192.168.1.11` (both /24).
> **Actual MACs from the run:** PC0 = `0030.F294.16B2`, PC2 = `00E0.F9B3.2661`.

## Reset state (Realtime) — so you watch it learn from zero
```
! PC0 Command Prompt:
arp -d ; arp -a           ! expect: no entries
! Switch0 CLI:
enable
clear mac-address-table
show mac-address-table     ! expect: empty
```

## Arm one ping (Simulation)
1. Bottom-right → **Simulation**. **Edit Filters** → only **ICMP** + **ARP**.
2. **Add Simple PDU** tool (closed envelope / `P`) → click **PC0**, then **PC2**.
3. Step with **Capture / Forward**; click each envelope → PDU Details.

## The four frames (what each shows)

### Frame 1 — ARP request (PC0, Outbound)  [find PC2's MAC]
- **Ethernet:** DEST `FFFF.FFFF.FFFF` (broadcast), TYPE `0x0806` (ARP),
  SRC `0030.F294.16B2` (PC0).
- **ARP:** OPCODE `0x0001` (request), SOURCE IP `192.168.1.10`,
  TARGET IP `192.168.1.11`, **TARGET MAC `0000.0000.0000`** (the blank).
- **No IP layer** — Ethernet wraps ARP directly (ARP ≈ "Layer 2.5").
- At **Switch0**: dst = broadcast → **flooded** to PC2 *and* the Router.
- **Router** receives it, TARGET IP ≠ its IP → **discards**. **PC2** matches → replies.

### Frame 2 — ARP reply (PC2 → PC0, unicast)  [the blank gets filled]
- OPCODE flips `0x0001` → **`0x0002`** (reply).
- **TARGET MAC now = PC2's real MAC `00E0.F9B3.2661`** — the answer.
- src/dst swapped; Ethernet dst = PC0's MAC (unicast, not broadcast).
- PC0 caches it: `192.168.1.11 → 00E0.F9B3.2661`.

### Frame 3 — ICMP Echo Request (PC0 → PC2)  [the actual ping]
- **Ethernet:** DEST `00E0.F9B3.2661` (PC2's real MAC now — *unicast*), TYPE `0x0800` (IPv4).
- **IP:** VER 4, IHL 5 (20-byte hdr), TTL `128`, **PRO `0x01` (ICMP)**,
  SRC `192.168.1.10`, DST `192.168.1.11`. *(No TCP/UDP, no ports — ICMP is L3.)*
- **ICMP:** TYPE `0x08` (Echo Request), ID `0x0005`, SEQ `13`.
- At **Switch0**: **Inbound == Outbound** (TTL still 128, MACs unchanged) →
  the switch forwards the frame **completely unchanged**, out only PC2's port
  (unicast — it learned PC2's port from the ARP reply). *This identity is the
  switch's defining behavior.*

### Frame 4 — ICMP Echo Reply (PC2 → PC0)
- ICMP **TYPE flips `0x08` → `0x00`** (Echo Reply); src/dst swapped (1.11→1.10);
  ID/SEQ echoed back unchanged (how PC0 matches it). No new ARP (PC2 already
  knew PC0's MAC). Switch forwards unicast to PC0. Ping success.

## Proof of learning (Realtime, after the trace)
```
! PC0:  arp -a
192.168.1.11   00e0.f9b3.2661   dynamic          ← was empty before
! Switch0:  show mac-address-table
0030.f294.16b2 -> Fa0/?   (PC0)
00e0.f9b3.2661 -> Fa0/?   (PC2)                    ← was empty before
```

## Key takeaways (for the video)
1. **Order:** a host must ARP (find the MAC) *before* it can send the ICMP —
   L3 knows the IP, but L2 delivery needs the MAC. ARP bridges L3→L2.
2. **Broadcast question, unicast answer:** ARP request floods; reply is direct.
3. **Switch = transparent L2 forwarder:** Inbound == Outbound (no MAC rewrite,
   no TTL change). Contrast the router, where Inbound ≠ Outbound.
4. **Read-your-layer:** the switch acts only on the dst MAC; it never reads the
   IP/ICMP it carries (even though PT displays them).
5. **Same-subnet signature:** dst IP and dst MAC both point at the final host
   (no gateway). Cross-subnet, they diverge (IP = server, MAC = router).
