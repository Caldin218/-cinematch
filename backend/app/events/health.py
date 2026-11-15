import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def serve_status(worker, port):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status = worker.status()
            if self.path == "/metrics":
                body = "\n".join(f"{key} {value}" for key, value in status.items()
                                 if key not in {"healthy", "last_error"} and value is not None) + "\n"
                code, content = 200, "text/plain"
            else:
                body = json.dumps(status)
                code, content = (200 if status["healthy"] else 503), "application/json"
            self.send_response(code)
            self.send_header("Content-Type", content)
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
