# Step 2 — Capacity Estimation (back-of-the-envelope)

> The FAANG differentiator. Don't hand-wave. **Each number eliminates a design option.**
> Method: pick ONE anchor assumption, state it aloud, derive everything from it.

## Anchor assumptions (state these out loud)
- New URLs: **100M/day** (write traffic)
- Read:write ratio: **100:1** → **10B redirects/day** (reads)

## Throughput (QPS) — divide per-day by ~100,000 (86,400 s/day ≈ 10^5)
```
Writes/sec = 100M / 86,400  ≈ 1,160   WPS   (~1.2K)
Reads/sec  = 10B  / 86,400  ≈ 115,700 RPS   (~116K)
```
**Decision forced:** 116K reads/sec cannot hit the DB directly → **cache layer required**.
1.2K writes/sec → a single tuned SQL primary handles writes easily.

## Storage (5-year horizon)
```
Per record ≈ short code (7B) + long URL (~500B) + metadata (~100B) ≈ ~500 B
Per day    = 100M × 500B   = 50 GB/day
5 years    = 50GB × 365 × 5 ≈ 91 TB  (~100 TB)
```
**Decision foreshadowed:** 100TB > one machine → **sharding/partitioning** (deep-dive later).

## Bandwidth
```
Write BW = 1,160  × 500B ≈ 0.6 MB/s   (trivial)
Read  BW = 115,700 × 500B ≈ 58 MB/s    (real, but CDN absorbs most)
```

## Cache memory (80/20 rule: 20% of URLs = 80% of traffic)
```
0.2 × 10B/day × 500B ≈ 1 TB
```
**Decision forced:** cache is a **cluster** (Redis/Memcached), not one box. In practice we
cache the hot *unique* subset, not every request.

## Short-code length (the design-defining calc) — Base62 = [a-z A-Z 0-9], URL-safe
```
62^6 = 56.8B   → ~1.5 yrs at 36.5B/yr   ❌ too short
62^7 = 3.5T    → ~96 yrs                 ✅
```
**Decision forced: 7-character code.** (Base64 has `+` `/` → not URL-safe, so Base62.)

## The key lesson
116K RPS killed "read from DB". 100TB foreshadowed sharding. 62^7 fixed key length.
Numbers without decisions = noise. Always connect each number to the choice it forces.

## Self-check
1. What does 116K RPS force, and why can't the DB serve it directly?
2. If new URLs were 1B/day, which numbers change? Is 7 chars still enough?
3. Why separate availability and latency as distinct non-functional reqs?
