import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fifa import get_standings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = os.path.join(ROOT, "public")

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # quiet

    def do_GET(self):
        if self.path == "/api/leaderboard" or self.path.startswith("/api/leaderboard?"):
            self.handle_leaderboard()
            return
        self.handle_static()

    def handle_leaderboard(self):
        force = "refresh=1" in self.path
        standings, match_info, error, ts = get_standings(force=force)
        body = json.dumps({
            "players": standings,
            "liveMatches": match_info["liveMatches"],
            "nextMatch": match_info["nextMatch"],
            "lastUpdated": ts,
            "error": error,
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def handle_static(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            path = "/index.html"

        full_path = os.path.normpath(os.path.join(PUBLIC_DIR, path.lstrip("/")))
        if not full_path.startswith(PUBLIC_DIR) or not os.path.isfile(full_path):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        ext = os.path.splitext(full_path)[1]
        content_type = MIME_TYPES.get(ext, "application/octet-stream")

        with open(full_path, "rb") as f:
            body = f.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    port = int(os.environ.get("PORT", "8765"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"World Cup pool app running at http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
