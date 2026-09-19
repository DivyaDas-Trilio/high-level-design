# What Actually Happens When You Run `curl`

### Your request crosses two machines, four layers, and three queues before your server ever sees it. Here's the whole journey.

---

You type this:

```bash
curl http://192.168.1.41:8000/orders/42
```

and 3 milliseconds later you get JSON back. In between, your request became a byte stream, got copied into kernel memory, was sliced into packets, crossed a physical wire, got reassembled by a different computer, and was handed to a Python function.

Most of us have a vague mental model of this. Mine had at least four things flatly wrong in it, and I only found out by instrumenting a server and watching.

So let's follow one request, end to end. Not the textbook version — the version you can verify on your own machine with `lsof` and `netstat`.

---

## Step 1: curl parses the URL before it does anything else

Before any network activity, curl splits the URL into parts:

```
http://192.168.1.41:8000/orders/42
└─┬──┘  └──────┬─────┘ └─┬─┘└───┬───┘
scheme       host      port   path
```

This matters because the request line and the `Host` header are *derived* from it:

```http
GET /orders/42 HTTP/1.1
Host: 192.168.1.41:8000
User-Agent: curl/8.7.1
Accept: */*

```

That blank line at the end is not decoration. It's the only thing telling the receiver "headers are done." HTTP is a text protocol held together by `\r\n`.

Note: **a plain `curl` has no body.** GET requests don't carry one. You get a body with `-d` or `-F`, and then curl also adds `Content-Length`.

At this point, all of it lives in curl's memory. No socket. No DNS. Nothing on the wire.

## Step 2: DNS — the step you skip when you type an IP

If you'd typed `curl http://api.example.com/`, curl would call `getaddrinfo()` to turn that name into an IP. That can be instant (cached in the OS) or cost several round-trips to different DNS servers (cold, walking root → TLD → authoritative).

We typed a raw IP, so this step vanishes. Worth knowing it's there, because "the API got slow" is sometimes a DNS story and never shows up in your application metrics.

## Step 3: `socket()` creates an endpoint — not a connection

```c
int fd = socket(AF_INET, SOCK_STREAM, 0);
```

This returns a **file descriptor** — a small integer, a handle your process uses to refer to a kernel object.

Here's the first thing I had wrong: **creating a socket does not create a connection.** The socket at this point has no port, no peer, and state `CLOSED`. Nothing has been transmitted. It's a phone that hasn't dialled.

## Step 4: `connect()` — and the kernel does all the work

```c
connect(fd, "192.168.1.41:8000");
```

Now things happen, but **curl doesn't do them.** curl makes one syscall and blocks. The kernel:

1. Picks an **ephemeral port** for your side (something like 59384, from a range of ~28,000).
2. Decides where to send the packet (routing table).
3. If needed, ARPs to find the next hop's MAC address.
4. Runs the **three-way handshake**:

```
client  ──────── SYN ────────▶  server
        ◀────── SYN-ACK ──────
        ──────── ACK ────────▶
```

Only when that finishes does `connect()` return.

This is worth dwelling on. **The handshake is entirely a kernel operation.** Neither application is involved. I'll show you a demo below that proves it, and the implication is genuinely useful in production.

## Step 5: `write()` copies bytes into a queue — it does not send them

```c
write(fd, "GET /orders/42 HTTP/1.1\r\nHost: ...\r\n\r\n", 86);
```

The second thing I had wrong: **this does not put bytes on the wire.** It copies them into a kernel buffer attached to your socket, called the **Send-Q**.

The kernel transmits when it decides to — governed by how much room the receiver advertised (flow control) and how much the network seems able to absorb (congestion control).

So `write()` returning tells you exactly one thing: *the bytes are in the kernel's buffer.* Not delivered. Not acknowledged. Certainly not read by the server. That distinction bites people writing retry logic.

If the Send-Q is full, `write()` blocks until there's room. That's backpressure, and it's the same mechanism as `await writer.drain()` if you write async Python.

## Step 6: TCP slices, IP addresses, Ethernet delivers

Your 86 bytes are a **byte stream** — TCP has no concept of "a request." It slices the stream into segments of at most the **MSS** (typically 1460 bytes), each with a sequence number, and wraps each one:

```
┌─────────────────────────────────────────────┐
│ Ethernet │ IP │ TCP │  GET /orders/42 ...   │
│  header  │hdr │ hdr │      (your bytes)     │
└─────────────────────────────────────────────┘
     ▲        ▲     ▲
     │        │     └── ports, sequence number, ACK, window, checksum
     │        └──────── source IP, destination IP (the SERVER), TTL
     └───────────────── source MAC, destination MAC (the NEXT HOP)
```

Here's the third thing I had wrong: I thought the packet was "sent to the server's NIC." It isn't. It's sent to the **next hop**, and this is the single most important invariant in networking:

> **The MAC address is rewritten at every hop. The IP addresses never change.**

Every router that touches your packet strips the Ethernet header, writes a new one for the *next* hop, decrements the TTL by 1, and forwards it. The IP header — "this is from A, going to B" — stays identical the entire journey.

That's the whole architecture in one sentence: **MAC is local delivery, IP is global delivery.**

*(In our example both machines are on `192.168.1.x` — the same subnet — so there's no router at all. The kernel ARPs for the server's own MAC and the frame goes straight through the switch. Cross-subnet is where they diverge: destination IP = the server, destination MAC = your gateway.)*

## Step 7: Arrival — unwrapping, in reverse

The server's NIC receives the frame and **raises a hardware interrupt**. The CPU drops whatever it was doing and runs kernel code, which unwraps the layers bottom-up:

**Layer 2 (Ethernet):** Is this destination MAC mine? No → drop. Is the checksum valid? No → drop silently. Yes → strip the header, read the EtherType (`0x0800` = IPv4), hand it up.

**Layer 3 (IP):** Is this destination IP mine? Checksum valid? Strip the header, read the protocol field (`6` = TCP), hand it up.

**Layer 4 (TCP):** Now the interesting part.

## Step 8: The 4-tuple — how the kernel knows which socket

The server might have thousands of connections open. How does it know which one these bytes belong to?

Not by port. By the **4-tuple**:

```
(source IP, source port, destination IP, destination port)
```

Every connection has a unique one. The kernel looks it up, finds the matching socket, verifies the TCP checksum, puts the bytes in order by sequence number, and appends them to that socket's **Recv-Q**.

This is where I had my fourth misconception, and it's a common one.

## The misconception: "the server opens a new port for each client"

It doesn't. Watch — one server, three simultaneous clients:

```
$ lsof -nP -iTCP:8040

Python  fd 10u  TCP 127.0.0.1:8040                       (LISTEN)
Python  fd 12u  TCP 127.0.0.1:8040 -> 127.0.0.1:59385    (ESTABLISHED)
Python  fd 13u  TCP 127.0.0.1:8040 -> 127.0.0.1:59384    (ESTABLISHED)
Python  fd 14u  TCP 127.0.0.1:8040 -> 127.0.0.1:59383    (ESTABLISHED)
                          ▲
                   ALL on port 8040
```

**Four sockets. Four file descriptors. One port.**

The server's port never changes. What differs is the *client* side — each `curl` got a different ephemeral port (59383, 59384, 59385), and that's what makes each 4-tuple unique.

This matters enormously for scale. If servers needed a port per client, they'd cap out around 65,000 connections. They don't:

| | Bounded by | Practical limit |
|---|---|---|
| **Server**, one listening port | file descriptors + memory | 10k–1M+ connections |
| **Client**, to one destination | ephemeral port range | ~28,000 |

**Port exhaustion is a client-side problem**, not a server-side one. If you've ever seen a busy API client mysteriously fail to connect while the server looked idle, that's why.

## Two kinds of socket, and why it's not an academic distinction

Look at that `lsof` output again. `fd 10` says `LISTEN`. The others say `ESTABLISHED`. These are fundamentally different objects:

| | Listening socket | Connected socket |
|---|---|---|
| Created by | `socket()` + `bind()` + `listen()` | `accept()` returning |
| Identified by | `IP:port` | the **4-tuple** |
| Holds | an **accept queue** | **Send-Q / Recv-Q** |
| You can | `accept()` on it | `read()` / `write()` on it |
| Carries data? | **never** | yes |
| How many | one | one per client |

The listening socket is a **factory**, not a pipe. It never carries a byte of your request. It receives connections and mints connected sockets.

### The demo that makes this concrete

Here's a server that calls `listen()` and then deliberately **never calls `accept()`** — it just sleeps:

```python
s = socket.socket()
s.bind(("127.0.0.1", 8050))
s.listen(128)
time.sleep(30)          # never accept. do nothing.
```

Now connect three clients and send data:

```
client 1: connect() RETURNED (no error) and sent 27 bytes
client 2: connect() RETURNED (no error) and sent 27 bytes
client 3: connect() RETURNED (no error) and sent 27 bytes

$ netstat -an | grep 8050
tcp4  27  0  127.0.0.1.8050  127.0.0.1.59401   ESTABLISHED
      ▲▲
   27 bytes sitting in Recv-Q

$ lsof -nP -iTCP:8050
Python  3u  TCP 127.0.0.1:8050 (LISTEN)      ← that's ALL the process holds
```

**Three complete TCP connections, with request bytes already buffered — and the application owns exactly one file descriptor.** It has never seen any of them.

This is the proof that the kernel does the handshake. And it has a consequence worth carrying into production:

> **A completely wedged application still accepts TCP connections.**

Block your server's event loop, deadlock your thread pool, whatever — the kernel keeps completing handshakes and buffering request bytes the entire time. So:

- A **TCP health check** (`nc -z`, an L4 load balancer probe, Kubernetes `tcpSocket` readiness) **will pass on a totally dead application.** It's testing the kernel, not your code. This is why health checks need to be HTTP — something only your app can answer.
- From the client's side, the symptom is "connected, then nothing" rather than "connection refused." Which tells you the process is alive and stuck, not gone.

## The three queues

By now we've met all three, and keeping them straight is most of the mental model:

```
                    SERVER

   ┌──────────────────────────────────────┐
   │  Listening socket (fd 10)            │
   │  ┌────────────────────────────────┐  │
   │  │  ACCEPT QUEUE                  │  │  ← holds CONNECTIONS
   │  │  completed handshakes waiting  │  │     (never bytes)
   │  │  for accept()                  │  │
   │  └────────────────────────────────┘  │
   └──────────────────────────────────────┘

   ┌──────────────────────────────────────┐
   │  Connected socket (fd 12)            │
   │  ┌──────────────┐  ┌──────────────┐  │
   │  │   RECV-Q     │  │   SEND-Q     │  │  ← hold BYTES
   │  │ bytes in     │  │ bytes out    │  │
   │  └──────────────┘  └──────────────┘  │
   └──────────────────────────────────────┘
```

The accept queue has a size — it's the `backlog` argument to `listen()`. When it fills up, the kernel **silently drops SYN packets**. No error, no RST. Clients just hang and eventually time out.

Which gives you a diagnostic rule worth memorising:

> **Fast failure = "connection refused" = the host is reachable, nothing is listening on that port.**
> **Slow failure = "connection timed out" = packets are being dropped** — full accept queue, firewall, or bad routing.

The speed of the failure tells you which layer to look at, before you read a single log line.

---

## The picture, end to end

```
YOUR MACHINE                                          SERVER

curl parses URL
     │
     ▼
getaddrinfo()  ──── DNS ────▶
     │
     ▼
socket()  → fd 5, CLOSED
     │
     ▼
connect() ─── SYN ─────────────────────────────────▶ SYN queue
          ◀── SYN-ACK ──────────────────────────────
          ─── ACK ──────────────────────────────────▶ ACCEPT QUEUE
     │                                                    │
     │  (kernel did all of that. curl just blocked.)       │  accept()
     ▼                                                     ▼
write(fd) → SEND-Q                                   connected socket, fd 12
     │
     ▼
 TCP segments (MSS)
 IP addresses (constant end-to-end)
 Ethernet delivers (MAC rewritten per hop)
     │
     ▼
 ─── switch ─── router ─── switch ───────────────▶  NIC → interrupt
                                                         │
                                                    L2: MAC? FCS?
                                                    L3: IP? checksum?
                                                    L4: 4-tuple lookup
                                                         │
                                                         ▼
                                                      RECV-Q
```

And that's where this post stops — because the bytes have arrived, but nothing has *read* them yet.

Two questions remain, and they're the interesting ones:

**How does TCP guarantee those bytes arrive complete, in order, with nothing missing** — over a network that loses, duplicates, and reorders packets freely? That's the next post.

**And how does the server application find out the bytes are there** — given that nothing is polling, and the process is fast asleep? That's the one after.

---

*If you want to reproduce any of this: `lsof -nP -iTCP:PORT` shows the sockets, `netstat -an | grep PORT` shows the 4-tuples and the Recv-Q/Send-Q columns, and `sudo tcpdump -i lo0 -n 'tcp port PORT'` shows the packets. Everything above was captured on a laptop.*
