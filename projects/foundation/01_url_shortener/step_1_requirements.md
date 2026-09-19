# Step 1 — Requirements

> The #1 intermediate mistake is jumping to "boxes and arrows". Don't. Every box
> you draw later must trace back to a requirement here.
> **Functional reqs tell you WHAT to build. Non-functional reqs tell you HOW.**

## Functional requirements (what the system DOES)
1. **Shorten** — given a long URL, return a short URL.
2. **Redirect** — given a short URL, redirect to the original long URL.
3. **Custom alias (optional)** — user can pick their own code (`tiny.url/divya`).
4. **Expiration** — links can expire after a TTL.

**Explicitly out of scope** (announcing this is a senior signal — it shows you
control the problem): user accounts, analytics dashboards, link editing.

## Non-functional requirements (the QUALITIES — the architecture comes from here)
1. **High availability** — if down, every link everywhere is dead. → redundancy.
2. **Low latency** — redirects must feel instant (tens of ms). → caching + CDN.
3. **Read-heavy** — far more redirects than creations. → optimize the READ path.
4. **Scalable** — 100Ms of new links, billions of redirects.
5. **Durability** — a link must work for years. Losing a mapping = broken promise.
6. **Unguessable codes** — sequential IDs leak volume + allow enumeration. (mild security)

## The key lesson
Derive architecture *from* non-functional requirements. "Read-heavy + low-latency"
alone already implies a **cache + CDN** before a single box is drawn.

## Self-check
- Can you state functional vs non-functional without looking?
- For each non-functional req, what design element does it imply?
