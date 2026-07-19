from __future__ import annotations

import socket
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


@dataclass
class OAuthCallback:
    code: str
    state: str


class _OAuthHandler(BaseHTTPRequestHandler):
    result: OAuthCallback | None = None
    error: str | None = None
    expected_state: str = ""

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in ("/callback", "/"):
            self.send_error(404)
            return
        params = parse_qs(parsed.query)
        if "error" in params:
            _OAuthHandler.error = params["error"][0]
            self._respond("Authorization failed. You can close this tab.")
            return
        code = params.get("code", [""])[0]
        state = params.get("state", [""])[0]
        if not code:
            _OAuthHandler.error = "Missing authorization code"
            self._respond("Authorization failed. You can close this tab.")
            return
        if state != _OAuthHandler.expected_state:
            _OAuthHandler.error = "Invalid OAuth state"
            self._respond("Authorization failed. You can close this tab.")
            return
        _OAuthHandler.result = OAuthCallback(code=code, state=state)
        self._respond("QuickLingo connected. You can close this tab.")

    def _respond(self, message: str) -> None:
        body = (
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>QuickLingo</title></head><body><p>{message}</p></body></html>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def pick_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_oauth_callback(
    *,
    expected_state: str,
    port: int,
    timeout: float = 300.0,
) -> OAuthCallback:
    _OAuthHandler.result = None
    _OAuthHandler.error = None
    _OAuthHandler.expected_state = expected_state
    server = HTTPServer(("127.0.0.1", port), _OAuthHandler)
    server.timeout = 1.0

    def serve() -> None:
        while _OAuthHandler.result is None and _OAuthHandler.error is None:
            server.handle_request()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    server.server_close()
    if _OAuthHandler.error:
        raise RuntimeError(_OAuthHandler.error)
    if _OAuthHandler.result is None:
        raise TimeoutError("OAuth authorization timed out")
    return _OAuthHandler.result
