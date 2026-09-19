"""HoL / keep-alive demo server (HTTP/1.1, port 8010).

  GET /fast   -> instant reply
  GET /slow   -> waits 2s, then replies   (use this to see head-of-line blocking)

Threaded so SEPARATE connections run concurrently, while requests on ONE
connection still serialize (that's the head-of-line blocking you're observing).

Run:   python3 hol_demo_server.py
Stop:  Ctrl-C
"""
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"          # <-- enables keep-alive (persistent conns)

    def log_message(self, *a):             # keep the terminal quiet
        pass

    def do_GET(self):
        if self.path.startswith("/slow"):
            time.sleep(2)                   # simulate a slow endpoint
            body = b"slow done\n"
        else:
            body = b"fast\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("HoL demo server on http://127.0.0.1:8010  (/fast, /slow)")
    ThreadingHTTPServer(("127.0.0.1", 8010), H).serve_forever()
