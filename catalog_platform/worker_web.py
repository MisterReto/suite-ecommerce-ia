"""Free Render web service: public health only, generation stays in RQ children."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
from . import redis_worker


def health_server(ready, port):
    class HealthHandler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def do_GET(self):
            if self.path != "/service-health":
                self.send_error(404)
                return
            body = json.dumps({
                "ok": ready.is_set(), "role": "image-worker", "backend": "rq",
                "version": os.getenv("RENDER_GIT_COMMIT", "local"),
            }).encode()
            self.send_response(200 if ready.is_set() else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            # Do not print arbitrary request paths/headers from the public port.
            pass

    return ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)


def main():
    ready = threading.Event()
    server = health_server(ready, int(os.getenv("PORT", "10000")))
    thread = threading.Thread(target=server.serve_forever, name="worker-health", daemon=True)
    thread.start()
    try:
        # Remain in the main thread so the existing SIGTERM handler stays active.
        redis_worker.main(ready=ready)
    finally:
        ready.clear()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
