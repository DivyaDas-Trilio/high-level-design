# Basic Networking — Course

A deep, teach-through-video course on networking fundamentals. Goal: understand
each concept down to the mechanism (bytes, fields, state machines, syscalls) so
it can be taught clearly on camera.

## Directory layout

```
basic_networking/
├── README.md            ← you are here (what this is, how to use it)
├── ROADMAP.md           ← the order to learn + record in, with pacing
├── PROGRESS.md          ← per-topic status tracker
├── docs/
│   ├── _TEMPLATE.md     ← teaching template (copy for new topics)
│   ├── 00-orientation/  ← big picture before details
│   ├── 01-fundamentals/ ← IP, CIDR, subnetting, NAT, devices, VPN, firewall
│   ├── 02-osi-model/    ← the 7 layers (transport & application are folders)
│   ├── 03-tcp-ip-model/ ← the 4-layer model, mapped to OSI
│   ├── 04-sockets/      ← sockets + socket states
│   ├── 05-packet-lifecycle/ ← end-to-end capstone (ties every layer together)
│   └── 06-mini-project/ ← build something end to end
├── labs/                ← hands-on experiments (tcpdump captures, scripts' output)
├── diagrams/            ← Excalidraw / SVG assets for videos
└── scripts/             ← runnable demos (Python/bash) used in lessons
```

## How each topic doc works

Every topic file follows `docs/_TEMPLATE.md`:
one-liner → problem it solves → deep-dive mechanism → mental model → hands-on
commands → misconceptions → diagrams needed → **video script outline** →
**brainstorm / open questions** → references.

Fill it top-down while studying. The last two sections (script + brainstorm) are
what turn understanding into a recordable lesson.

## Working rhythm (agreed)

- **Self-paced** — no rushing; depth over coverage.
- **Brainstorm-first** — we discuss and pressure-test a concept before locking it.
- **"Next" is the advance signal** — I only move to the next topic when you say
  **Next**. Otherwise we keep digging / brainstorming the current one.
- **Always dig deeper** — every explanation goes one level below the abstraction.

## Suggested tools for the hands-on sections

`tcpdump` / Wireshark · `dig` / `nslookup` · `curl -v` · `ip` / `ifconfig` ·
`netstat` / `lsof` · `ping` / `traceroute` · `nc` (netcat) · Python `socket`.
```
