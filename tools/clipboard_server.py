"""
Tiny HTTP server that exposes the Windows clipboard over HTTP.
Run this on the Windows machine where BlueStacks is running (10.0.0.156).

  python clipboard_server.py

Then the Linux bot can call: GET http://10.0.0.156:8765/clipboard
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import win32clipboard


PORT = 8765


class ClipboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/clipboard":
            try:
                win32clipboard.OpenClipboard()
                text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
            except Exception:
                try:
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass
                text = ""

            body = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/clipboard":
            length = int(self.headers.get("Content-Length", 0))
            text = self.rfile.read(length).decode("utf-8")
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
                win32clipboard.CloseClipboard()
                self.send_response(200)
            except Exception:
                try:
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass
                self.send_response(500)
        else:
            self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # silence request logs


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), ClipboardHandler)
    print(f"Clipboard server listening on port {PORT}")
    server.serve_forever()
