"""Serve the local portal from this checkout without stale browser caches."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class PortalHandler(SimpleHTTPRequestHandler):
    server_version = "RetailPulseDev/1.0"

    def send_head(self):
        # Even a previously cached response must be replaced during UI development.
        for header in ("If-Modified-Since", "If-None-Match"):
            if header in self.headers:
                del self.headers[header]
        return super().send_head()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5173)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    handler = partial(PortalHandler, directory=str(root))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"Serving checkout: {root}", flush=True)
        print(
            f"Portal: http://localhost:{args.port}/frontend/dashboard.html?ui=workspace-20261018-ux1",
            flush=True,
        )
        print("Browser caching disabled. Press Ctrl+C to stop.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
