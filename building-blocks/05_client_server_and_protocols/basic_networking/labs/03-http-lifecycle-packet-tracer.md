# Lab 03 — HTTP Lifecycle End to End (Packet Tracer + host tools)

> **Goal:** visualize a full HTTP request lifecycle — ARP → TCP 3-way handshake →
> HTTP GET → HTTP 200 → teardown — on the wire, and pair it with host tools to
> see the socket-state half Packet Tracer can't show.
> **Maps to:** `docs/05-packet-lifecycle/packet-lifecycle-end-to-end.md`,
> `docs/02-osi-model/07-application/02-http-1-2-3.md`, Transport (TCP) topic.
> **Topology:** `PC0 (192.168.1.10) — Switch0 — Router0 — Switch1 — Server0 (192.168.2.10:80)`.

## The honest split: what PT shows vs. doesn't

Packet Tracer is a **network** simulator → it shows the **wire half**, not host
kernel internals.

| Lifecycle phase | In Packet Tracer? | How / which tool |
|---|---|---|
| A server listening | ⚠️ config, not a packet | enable HTTP service (implicit LISTEN) |
| B client socket/connect | ❌ host-internal | (triggers the SYN) |
| C ARP | ✅ | ARP request/reply frames |
| D TCP handshake | ✅ | SYN / SYN-ACK / ACK — read TCP **flags** in PDU |
| E HTTP GET | ✅ | HTTP request packet |
| F HTTP 200 + body | ✅ | HTTP response packet |
| G teardown (FIN) | ✅ | FIN / ACK packets |
| fds, Send-Q / Recv-Q | ❌ | host tools (below) |
| socket states (LISTEN/ESTABLISHED/TIME_WAIT) | ❌ | `netstat` / `ss` on a host |

**Complete picture = hybrid:** Packet Tracer for packets on the wire; a real host
+ `tcpdump`/`netstat`/`lsof` for the socket/buffer/state side.

## Part 1 — Build it (Packet Tracer)

1. Reuse `PC0 — Switch0 — Router0 — Switch1 — …`. **Delete PC1** (or add a device)
   → **End Devices → Server** as `Server0`.
2. **Server0 → Desktop → IP Configuration:** IP `192.168.2.10`, mask
   `255.255.255.0`, gateway `192.168.2.1`.
3. **Server0 → Services tab → HTTP →** ensure **HTTP: On** (serves default
   `index.html`).
4. Confirm PC0 config: `192.168.1.10` / `255.255.255.0` / gw `192.168.1.1`.
5. Quick reachability test (Realtime): from PC0 Web Browser, `http://192.168.2.10`
   should load the page. (If not → revisit gateways, per Lab 01 debugging.)

## Part 2 — Visualize the lifecycle (Simulation)

1. Bottom-right → **Simulation**. **Edit Filters →** show **ARP + TCP + HTTP**
   (add ICMP if you like).
2. `PC0 → Desktop → Web Browser →` URL `http://192.168.2.10` → **Go**.
3. Step with **Capture / Forward**; click each envelope → **PDU Details**.

### What to watch, step by step (Phases C–G)

- **ARP** (Phase C) — PC0 resolves the **gateway's** MAC first (server is
  off-subnet, so ARP targets `192.168.1.1`, not the server).
- **SYN** (Phase D) — PDU → **TCP layer → flags: SYN=1**. Connection being born.
- **SYN-ACK** — flags **SYN=1, ACK=1** (from server).
- **ACK** — flags **ACK=1** → handshake done (ESTABLISHED, implied).
- **HTTP GET** (Phase E) — inspect the **HTTP** layer of the request.
- **HTTP 200** (Phase F) — the response carrying the HTML.
- **FIN / ACK** (Phase G) — teardown.

At each **router** hop, also note **MAC rewrite + TTL−1**; at each **switch**,
Inbound == Outbound. One HTTP run replays every earlier trace, now with a real
TCP handshake + HTTP on top.

### Things to freeze on for video
1. The three handshake packets with their **flag bits** flipping (SYN → SYN,ACK → ACK).
2. The **HTTP** layer appearing only *after* the handshake (data rides an
   established connection).
3. Router hop: MAC rewritten, IP constant, TTL−1.

## Part 3 — The socket-state half (host tools, on your Mac)

Packet Tracer can't show fds/buffers/states. See them against your own server:

```bash
# terminal 1 — watch states flip live:
watch -n 0.3 'netstat -an -p tcp | grep 8000'      # or: while :; do netstat -an -p tcp | grep 8000; sleep 0.3; done

# terminal 2 — the server (a real HTTP-ish server you built):
cd miniapi && python3 stage1_server.py

# terminal 3 — fire a request:
curl http://127.0.0.1:8000/hello

# and, to see the actual packets on loopback:
sudo tcpdump -i lo0 -n 'tcp port 8000'             # handshake → data → FIN
# and the sockets/fds:
lsof -nP -iTCP:8000                                 # listening + connected sockets
```

You'll observe the state machine PT hides:
- `LISTEN` (the server's listening socket, always there),
- a transient `ESTABLISHED` (the connection, while data flows),
- `TIME_WAIT` (~2×MSL after close, holding the 4-tuple).

## Takeaways
1. **PT = wire half, host tools = socket half.** Use both for the full lifecycle.
2. **Data only flows after the handshake** — HTTP layer appears post-ACK.
3. **The handshake births / FIN kills** the connection; you can *see* both as
   packets (PT) and as state transitions (`netstat`).
4. Same per-hop rules as every prior lab: switch forwards by MAC unchanged,
   router rewrites MAC + TTL−1, IP constant end-to-end.
