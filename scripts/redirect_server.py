"""Tiny 302 redirector for the KOSPI-WATCHER stable public URL.

Problem: the public app is served over a Cloudflare Quick Tunnel whose URL
changes whenever cloudflared (re)starts, so it can't be bookmarked. We can't put
the multi-page Next.js app on a sub-path of a shared Tailscale Funnel host either
(Tailscale --set-path STRIPS the prefix, which breaks the app's root-absolute
asset/navigation URLs).

Solution: this server returns a 302 redirect to the CURRENT Quick Tunnel URL
(read live from current-url.txt, kept fresh by public-tunnel-daemon.ps1). Mount
it on a Tailscale Funnel sub-path (e.g. .../kospi) to get a STABLE bookmark that
always forwards to the live tunnel. A redirect is a single response, so the
prefix-stripping and root-absolute-asset problems simply don't apply.

Listens on 127.0.0.1:18077. Stateless; never raises out.
"""

from __future__ import annotations

import http.server
import pathlib
import socketserver

PORT = 18077
URL_FILE = pathlib.Path(__file__).resolve().parent / "current-url.txt"


class RedirectHandler(http.server.BaseHTTPRequestHandler):
    def _redirect(self) -> None:
        try:
            target = URL_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            target = ""
        if not target.startswith("https://"):
            self.send_response(503)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"KOSPI-WATCHER tunnel URL not ready yet.")
            return
        self.send_response(302)
        self.send_header("Location", target)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self) -> None:
        self._redirect()

    def do_HEAD(self) -> None:
        self._redirect()

    def log_message(self, *args: object) -> None:  # silence access logs
        pass


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with _Server(("127.0.0.1", PORT), RedirectHandler) as httpd:
        httpd.serve_forever()
