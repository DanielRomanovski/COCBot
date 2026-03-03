#!/data/data/com.termux/files/usr/bin/python
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            text = subprocess.check_output(["termux-clipboard-get"], timeout=3).decode().strip()
        except Exception:
            text = ""
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        text = self.rfile.read(length).decode("utf-8")
        try:
            subprocess.run(["termux-clipboard-set", text], timeout=3, check=True)
            self.send_response(200)
        except Exception:
            self.send_response(500)
        self.end_headers()

    def log_message(self, *a): pass

print("Clipboard server listening on port 8765")
HTTPServer(("0.0.0.0", 8765), H).serve_forever()
