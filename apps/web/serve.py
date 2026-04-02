"""Minimal dev server for the web stub."""

from __future__ import annotations

import http.server
import os
import sys

PORT = int(os.environ.get("WEB_PORT", "5173"))
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    handler = http.server.SimpleHTTPRequestHandler
    handler.directory = DIRECTORY  # type: ignore[attr-defined]
    with http.server.HTTPServer(("127.0.0.1", PORT), handler) as server:
        print(f"Web stub serving at http://127.0.0.1:{PORT}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
