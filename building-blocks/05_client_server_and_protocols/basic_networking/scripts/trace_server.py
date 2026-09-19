"""Instrumented uvicorn: prints every layer boundary a request crosses.

Run:   python3 trace_server.py
Then:  curl -v http://127.0.0.1:8030/orders/42
"""
import os, time, asyncio
import uvicorn
from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol

T0 = time.perf_counter()
def log(layer, msg):
    ms = (time.perf_counter() - T0) * 1000
    colour = {"KERNEL": "\033[90m", "UVICORN": "\033[36m",
              "PARSER": "\033[33m", "ASGI": "\033[35m", "APP": "\033[32m"}.get(layer, "")
    print(f"{ms:9.3f} ms  {colour}{layer:<8}\033[0m {msg}", flush=True)


class TracingProtocol(HttpToolsProtocol):
    """asyncio calls these; each one is a real boundary in the receive path."""

    def connection_made(self, transport):
        sock = transport.get_extra_info("socket")
        peer = transport.get_extra_info("peername")
        log("KERNEL", f"accept() returned → connected socket fd={sock.fileno()}  peer={peer[0]}:{peer[1]}")
        log("UVICORN", "protocol instance created for THIS connection (own parser, own buffers)")
        super().connection_made(transport)

    def data_received(self, data):
        log("KERNEL", f"Recv-Q drained → {len(data)} raw bytes handed to user space")
        first = data.split(b"\r\n")[0][:60].decode(errors="replace")
        log("UVICORN", f"data_received() called by the event loop; first line: {first!r}")
        super().data_received(data)

    def on_url(self, url):
        log("PARSER", f"httptools: request line parsed → {url.decode()}")
        super().on_url(url)

    def on_headers_complete(self):
        log("PARSER", "httptools: all headers parsed (byte stream → structured fields)")
        super().on_headers_complete()

    def on_body(self, body):
        log("PARSER", f"httptools: body chunk, {len(body)} bytes")
        super().on_body(body)

    def on_message_complete(self):
        log("PARSER", "httptools: message complete → a WHOLE HTTP request now exists")
        super().on_message_complete()

    def connection_lost(self, exc):
        log("KERNEL", "connection_lost() → FIN seen / socket closed, buffers freed")
        super().connection_lost(exc)

    def timeout_keep_alive_handler(self):
        log("UVICORN", "keep-alive timer expired → closing an idle connection")
        super().timeout_keep_alive_handler()


async def app(scope, receive, send):
    """A raw ASGI app so nothing is hidden behind FastAPI."""
    if scope["type"] == "lifespan":
        while True:
            m = await receive()
            if m["type"] == "lifespan.startup":
                log("UVICORN", "lifespan.startup → app is ready to serve")
                await send({"type": "lifespan.startup.complete"})
            elif m["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"}); return

    log("ASGI", f"app(scope, receive, send) CALLED  scope['type']={scope['type']}")
    log("ASGI", f"scope: {scope['method']} {scope['path']}  http_version={scope['http_version']}")
    log("ASGI", f"scope['client']={scope['client']}  scope['server']={scope['server']}")

    body = b""
    while True:
        message = await receive()
        log("ASGI", f"receive() → {message['type']}  body={len(message.get('body', b''))}B "
                    f"more_body={message.get('more_body', False)}")
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break

    log("APP", "handler running — THIS is your code. Everything above was plumbing.")
    payload = b'{"traced": true}'

    log("ASGI", "send() → http.response.start (status + headers)")
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"application/json"),
                            (b"content-length", str(len(payload)).encode())]})
    log("ASGI", "send() → http.response.body (bytes head back down the stack)")
    await send({"type": "http.response.body", "body": payload})
    log("UVICORN", "response written to transport → kernel Send-Q → wire")


if __name__ == "__main__":
    log("KERNEL", f"process starting, pid={os.getpid()}")
    print("-" * 100, flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8030,
                http=TracingProtocol, log_level="error", timeout_keep_alive=5)
