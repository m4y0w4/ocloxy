#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""OpenSoloMark: a local header bridge for OpenCode Go.

OpenCode Go's inference endpoint requires an `x-opencode-session` header.
Some Markdown/notes apps with built-in AI chat only let you set an
OpenAI-compatible base URL and API key, so they cannot send that header
themselves. This proxy listens on localhost, adds the header, and forwards
the request to opencode.ai unchanged.

It uses only the Python standard library. No API key is stored here: the
Authorization header from the app is forwarded as-is.
"""

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

SERVICE = "opensolomark/1.0"

UPSTREAM = os.environ.get("UPSTREAM_BASE", "https://opencode.ai").rstrip("/")
HOST = os.environ.get("LISTEN_HOST", "127.0.0.1")
PORT = int(os.environ.get("LISTEN_PORT", "47123"))
SESSION = os.environ.get("SESSION_ID", "opensolomark-local").strip() or "opensolomark-local"
TIMEOUT = float(os.environ.get("UPSTREAM_TIMEOUT", "600"))


def _allowed_prefixes():
    """Read ALLOWED_PREFIXES as a comma-separated list of path prefixes.

    Prefixes are normalised to end with "/" so that /inference/ does not
    accidentally match a path like /inference-other.
    """
    raw = os.environ.get("ALLOWED_PREFIXES", "/inference/,/zen/")
    prefixes = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if not part.startswith("/"):
            part = "/" + part
        part = part.rstrip("/") + "/"
        prefixes.append(part)
    return tuple(prefixes) or ("/inference/", "/zen/")


ALLOWED_PREFIXES = _allowed_prefixes()

# Never forwarded: framing and connection-level headers, plus encoding
# negotiation (we relay decoded bytes, so upstream must not compress).
REQUEST_STRIP = {
    "host",
    "content-length",
    "connection",
    "keep-alive",
    "proxy-connection",
    "transfer-encoding",
    "te",
    "trailer",
    "upgrade",
    "accept-encoding",
}

# Response headers worth passing back. Everything else (Date, Server,
# Set-Cookie, framing) is regenerated locally.
RESPONSE_KEEP = {
    "content-type",
    "retry-after",
    "request-id",
    "x-request-id",
    "openai-processing-ms",
}
RESPONSE_KEEP_PREFIX = ("x-ratelimit-", "anthropic-ratelimit-")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = SERVICE
    sys_version = ""

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def do_PUT(self):
        self._handle()

    def do_PATCH(self):
        self._handle()

    def do_DELETE(self):
        self._handle()

    def do_OPTIONS(self):
        # Native clients do not need CORS. This just answers a preflight
        # cleanly if one is ever sent.
        self.send_response(204)
        self.send_header("Allow", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _handle(self):
        started = time.monotonic()
        try:
            self._forward(started)
        except (BrokenPipeError, ConnectionResetError):
            # Client hung up mid-stream; nothing useful to say.
            pass
        except Exception as exc:  # noqa: BLE001 - last-resort guard
            self._log(500, 0, started)
            sys.stderr.write("unhandled: %r\n" % (exc,))
            sys.stderr.flush()
            try:
                self._json(
                    500,
                    {"error": {"type": "proxy_internal", "message": str(exc)}},
                    started,
                )
            except Exception:
                pass

    def _forward(self, started):
        parts = urlsplit(self.path)
        path = parts.path or "/"

        if path == "/healthz":
            return self._json(
                200,
                {
                    "ok": True,
                    "service": "opensolomark",
                    "upstream": UPSTREAM,
                    "session": SESSION,
                    "port": PORT,
                },
                started,
            )

        if not path.startswith(ALLOWED_PREFIXES):
            return self._json(
                403,
                {
                    "error": {
                        "type": "path_not_allowed",
                        "message": "Path must start with one of: %s. "
                        "Set the app base URL to http://%s:%d/inference/go/v1"
                        % (", ".join(ALLOWED_PREFIXES), HOST, PORT),
                    }
                },
                started,
            )

        length_header = self.headers.get("Content-Length")
        try:
            length = int(length_header) if length_header else 0
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length > 0 else b""

        headers = {}
        for name, value in self.headers.items():
            if name.lower() in REQUEST_STRIP:
                continue
            headers[name] = value

        present = {name.lower() for name in headers}
        if "x-opencode-session" not in present:
            headers["x-opencode-session"] = SESSION
        if "user-agent" not in present:
            headers["User-Agent"] = "OpenSoloMark/1.0"

        target = UPSTREAM + path + (("?" + parts.query) if parts.query else "")
        request = urllib.request.Request(
            target, data=body, headers=headers, method=self.command
        )

        try:
            response = urllib.request.urlopen(request, timeout=TIMEOUT)
        except urllib.error.HTTPError as exc:
            return self._relay_error(exc, started)
        except socket.timeout:
            return self._json(
                504,
                {"error": {"type": "proxy_timeout", "message": "Upstream timed out."}},
                started,
            )
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            return self._json(
                502,
                {
                    "error": {
                        "type": "proxy_upstream_unreachable",
                        "message": str(reason),
                    }
                },
                started,
            )

        with response:
            upstream_length = response.headers.get("Content-Length")
            chunked = upstream_length is None

            self.send_response(response.status)
            for name, value in response.headers.items():
                lower = name.lower()
                if lower in RESPONSE_KEEP or lower.startswith(RESPONSE_KEEP_PREFIX):
                    self.send_header(name, value)
            if chunked:
                self.send_header("Transfer-Encoding", "chunked")
            else:
                self.send_header("Content-Length", upstream_length)
            self.end_headers()

            sent = 0
            while True:
                # read1() returns whatever has arrived; read(n) would block
                # until n bytes are buffered, which defeats streaming.
                chunk = response.read1(8192)
                if not chunk:
                    break
                if chunked:
                    self.wfile.write(b"%x\r\n" % len(chunk))
                    self.wfile.write(chunk)
                    self.wfile.write(b"\r\n")
                else:
                    self.wfile.write(chunk)
                self.wfile.flush()
                sent += len(chunk)

            if chunked:
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()

        self._log(response.status, sent, started)

    def _relay_error(self, exc, started):
        try:
            payload = exc.read()
        except Exception:
            payload = b""

        self.send_response(exc.code)
        content_type = "application/json"
        if exc.headers is not None:
            content_type = exc.headers.get("Content-Type") or content_type
            for name, value in exc.headers.items():
                lower = name.lower()
                if (
                    lower in ("retry-after", "request-id", "x-request-id")
                    or lower.startswith(RESPONSE_KEEP_PREFIX)
                ):
                    self.send_header(name, value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        self.wfile.flush()
        self._log(exc.code, len(payload), started)

    def _json(self, status, payload, started=None):
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
        self.wfile.flush()
        if started is not None:
            self._log(status, len(encoded), started)

    def _log(self, status, size, started):
        elapsed = (time.monotonic() - started) * 1000
        path = urlsplit(self.path).path
        sys.stderr.write(
            "%s %s %s -> %s %dB %.0fms\n"
            % (
                time.strftime("%Y-%m-%dT%H:%M:%S"),
                self.command,
                path,
                status,
                size,
                elapsed,
            )
        )
        sys.stderr.flush()

    def log_message(self, fmt, *args):
        # Silence the default per-request stderr line; _log covers it.
        pass


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    try:
        server = Server((HOST, PORT), Handler)
    except OSError as exc:
        sys.stderr.write(
            "opensolomark: cannot listen on %s:%d: %s\n" % (HOST, PORT, exc)
        )
        sys.stderr.flush()
        return 1

    sys.stderr.write(
        "opensolomark: http://%s:%d -> %s (session=%s)\n"
        % (HOST, PORT, UPSTREAM, SESSION)
    )
    sys.stderr.flush()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
