#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""OpenSoloMark: a local header bridge for OpenCode Go.

OpenCode Go's inference endpoint requires an `x-opencode-session` header.
Some Markdown/notes apps with built-in AI chat only let you set an
OpenAI-compatible base URL and API key, so they cannot send that header
themselves. This proxy listens on loopback, adds the header, and forwards
the request to opencode.ai unchanged.

It uses only the Python standard library. No API key is stored here: the
Authorization header from the app is forwarded as-is.
"""

import hashlib
import ipaddress
import json
import os
import posixpath
import socket
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

__version__ = "0.1.0"
SERVICE = "opensolomark/" + __version__

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 47123
DEFAULT_SESSION = "opensolomark-local"
DEFAULT_MAX_BODY = 16 * 1024 * 1024
DEFAULT_PREFIXES = "/inference/,/zen/"

# Defaults; _apply_config() replaces these after startup validation.
UPSTREAM = "https://opencode.ai"
HOST = DEFAULT_HOST
PORT = DEFAULT_PORT
SESSION = DEFAULT_SESSION
SESSION_MODE = "fixed"
SESSION_DERIVE_INCLUDE_SYSTEM = True
TIMEOUT = 600.0
MAX_BODY_BYTES = DEFAULT_MAX_BODY
ALLOWED_PREFIXES = ("/inference/", "/zen/")


class ConfigError(Exception):
    """Raised when an environment setting is invalid."""


class BodyTooLarge(Exception):
    """Raised when a request body exceeds MAX_BODY_BYTES."""


class InvalidBody(Exception):
    """Raised when a request body cannot be read safely."""


def _env_int(name, default, minimum, maximum):
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError("%s must be an integer." % name)
    if value < minimum or value > maximum:
        raise ConfigError(
            "%s must be between %d and %d." % (name, minimum, maximum)
        )
    return value


def _env_float(name, default, minimum, maximum):
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError("%s must be a number." % name)
    if value < minimum or value > maximum:
        raise ConfigError(
            "%s must be between %s and %s." % (name, minimum, maximum)
        )
    return value


def _env_bool(name, default):
    raw = os.environ.get(name, "1" if default else "0").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    raise ConfigError(
        "%s must be one of: 1, 0, true, false, yes, no, on, off." % name
    )


def _is_loopback_host(host):
    host = (host or "").strip().lower()
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _validated_upstream(value):
    value = value.strip().rstrip("/")
    if not value:
        raise ConfigError("UPSTREAM_BASE cannot be empty.")

    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise ConfigError("UPSTREAM_BASE is not a valid URL.") from exc

    if parsed.scheme not in ("http", "https"):
        raise ConfigError("UPSTREAM_BASE must start with http:// or https://.")
    if not parsed.netloc:
        raise ConfigError("UPSTREAM_BASE must include a host.")
    if parsed.username or parsed.password:
        raise ConfigError("UPSTREAM_BASE must not include credentials.")
    if parsed.query or parsed.fragment:
        raise ConfigError("UPSTREAM_BASE must not include a query or fragment.")

    try:
        parsed.port
    except ValueError as exc:
        raise ConfigError("UPSTREAM_BASE has an invalid port.") from exc

    if parsed.scheme == "http" and not _is_loopback_host(parsed.hostname):
        raise ConfigError(
            "UPSTREAM_BASE must use https unless it points at loopback."
        )

    return value


def _parse_allowed_prefixes(raw):
    prefixes = []
    for part in raw.split(","):
        part = unquote(part.strip())
        if not part:
            continue
        if not part.startswith("/"):
            part = "/" + part
        if part == "/":
            raise ConfigError("ALLOWED_PREFIXES cannot include /.")
        if "?" in part or "#" in part or "\x00" in part:
            raise ConfigError("ALLOWED_PREFIXES contains an invalid character.")
        if ".." in part.split("/"):
            raise ConfigError("ALLOWED_PREFIXES cannot include path traversal.")
        part = part.rstrip("/") + "/"
        prefixes.append(part)
    return tuple(prefixes) or ("/inference/", "/zen/")


def _load_config():
    upstream = _validated_upstream(
        os.environ.get("UPSTREAM_BASE", "https://opencode.ai")
    )

    host = os.environ.get("LISTEN_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
    if not _is_loopback_host(host):
        raise ConfigError(
            "LISTEN_HOST must be a loopback address; remote binding is not "
            "supported."
        )

    port = _env_int("LISTEN_PORT", DEFAULT_PORT, 1, 65535)
    session = (
        os.environ.get("SESSION_ID", DEFAULT_SESSION).strip() or DEFAULT_SESSION
    )

    session_mode = os.environ.get("SESSION_MODE", "fixed").strip().lower()
    if session_mode not in ("fixed", "derive"):
        raise ConfigError("SESSION_MODE must be fixed or derive.")

    include_system = _env_bool("SESSION_DERIVE_INCLUDE_SYSTEM", True)
    timeout = _env_float("UPSTREAM_TIMEOUT", 600.0, 0.1, 3600.0)
    max_body_bytes = _env_int(
        "MAX_BODY_BYTES", DEFAULT_MAX_BODY, 1, 256 * 1024 * 1024
    )
    prefixes = _parse_allowed_prefixes(
        os.environ.get("ALLOWED_PREFIXES", DEFAULT_PREFIXES)
    )

    return {
        "upstream": upstream,
        "host": host,
        "port": port,
        "session": session,
        "session_mode": session_mode,
        "include_system": include_system,
        "timeout": timeout,
        "max_body_bytes": max_body_bytes,
        "allowed_prefixes": prefixes,
    }


def _apply_config(config):
    global UPSTREAM, HOST, PORT, SESSION, SESSION_MODE
    global SESSION_DERIVE_INCLUDE_SYSTEM, TIMEOUT, MAX_BODY_BYTES
    global ALLOWED_PREFIXES

    UPSTREAM = config["upstream"]
    HOST = config["host"]
    PORT = config["port"]
    SESSION = config["session"]
    SESSION_MODE = config["session_mode"]
    SESSION_DERIVE_INCLUDE_SYSTEM = config["include_system"]
    TIMEOUT = config["timeout"]
    MAX_BODY_BYTES = config["max_body_bytes"]
    ALLOWED_PREFIXES = config["allowed_prefixes"]


def _normalize_path(raw_path):
    decoded = unquote(raw_path or "/")
    if not decoded.startswith("/"):
        raise ValueError("path must be absolute")
    if "\x00" in decoded or "\\" in decoded:
        raise ValueError("invalid path")
    if ".." in decoded.split("/"):
        raise ValueError("path traversal")
    return posixpath.normpath(decoded) or "/"


def _canonical_content(value):
    """Normalise message content into a stable text representation."""
    if isinstance(value, str):
        text = value.replace("\r\n", "\n").replace("\r", "\n")
        return unicodedata.normalize("NFC", text)

    if isinstance(value, list):
        parts = []
        for part in value:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str):
                text = text.replace("\r\n", "\n").replace("\r", "\n")
                parts.append(unicodedata.normalize("NFC", text))
        return "\n".join(parts)

    if value is None:
        return ""

    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def _derive_session(body):
    """Return an opaque stable ID for the conversation opening in *body*."""
    if not body:
        return None

    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return None

    system_parts = []
    first_user = None

    for message in messages:
        if not isinstance(message, dict):
            continue

        role = message.get("role")

        if role in ("system", "developer") and first_user is None:
            system_parts.append(_canonical_content(message.get("content")))
        elif role == "user":
            first_user = _canonical_content(message.get("content"))
            break

    if not first_user:
        return None

    seed = {"v": 1, "user": first_user}
    if SESSION_DERIVE_INCLUDE_SYSTEM:
        seed["system"] = system_parts

    material = json.dumps(
        seed, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")

    digest = hashlib.sha256(
        b"opensolomark-session-v1\0" + material
    ).hexdigest()

    return "osm-" + digest[:32]


def _session_for_request(body):
    """Pick the outbound session ID for a request without that header."""
    if SESSION_MODE == "derive":
        derived = _derive_session(body)
        if derived:
            return derived
    return SESSION


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

    def _read_chunked_body(self):
        chunks = []
        total = 0

        while True:
            line = self.rfile.readline(65537)
            if not line or len(line) > 65536:
                raise InvalidBody("Malformed chunked request body.")

            size_token = line.split(b";", 1)[0].strip()
            try:
                size = int(size_token, 16)
            except ValueError:
                raise InvalidBody("Malformed chunk size.")

            if size < 0:
                raise InvalidBody("Malformed chunk size.")

            if size == 0:
                for _ in range(100):
                    trailer = self.rfile.readline(65537)
                    if not trailer:
                        break
                    if len(trailer) > 65536:
                        raise InvalidBody("Malformed chunk trailer.")
                    if trailer in (b"\r\n", b"\n"):
                        break
                break

            total += size
            if total > MAX_BODY_BYTES:
                raise BodyTooLarge()

            chunk = self.rfile.read(size)
            if len(chunk) != size:
                raise InvalidBody("Chunked request body ended early.")
            if self.rfile.read(2) != b"\r\n":
                raise InvalidBody("Malformed chunked request body.")
            chunks.append(chunk)

        return b"".join(chunks)

    def _read_request_body(self):
        transfer_encoding = self.headers.get("Transfer-Encoding")
        content_length = self.headers.get("Content-Length")

        if transfer_encoding and content_length:
            raise InvalidBody(
                "Content-Length and Transfer-Encoding cannot both be set."
            )

        if transfer_encoding:
            tokens = [
                token.strip().lower()
                for token in transfer_encoding.split(",")
                if token.strip()
            ]
            if tokens != ["chunked"]:
                raise InvalidBody(
                    "Unsupported Transfer-Encoding; send chunked or "
                    "Content-Length."
                )
            return self._read_chunked_body()

        if content_length is None:
            return b""

        try:
            length = int(content_length)
        except ValueError:
            raise InvalidBody("Content-Length must be an integer.")

        if length < 0:
            raise InvalidBody("Content-Length cannot be negative.")
        if length > MAX_BODY_BYTES:
            raise BodyTooLarge()

        body = self.rfile.read(length)
        if len(body) != length:
            raise InvalidBody("Request body ended early.")
        return body

    def _forward(self, started):
        try:
            parts = urlsplit(self.path)
        except ValueError:
            return self._path_error(started)

        if parts.scheme or parts.netloc:
            return self._path_error(started)

        try:
            path = _normalize_path(parts.path or "/")
        except ValueError:
            return self._path_error(started)

        if path == "/healthz":
            return self._json(
                200,
                {
                    "ok": True,
                    "service": "opensolomark",
                    "version": __version__,
                    "session_mode": SESSION_MODE,
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

        try:
            body = self._read_request_body()
        except BodyTooLarge:
            self.close_connection = True
            return self._json(
                413,
                {
                    "error": {
                        "type": "request_body_too_large",
                        "message": "Request body exceeds MAX_BODY_BYTES.",
                    }
                },
                started,
            )
        except InvalidBody as exc:
            self.close_connection = True
            return self._json(
                400,
                {
                    "error": {
                        "type": "invalid_request_body",
                        "message": str(exc),
                    }
                },
                started,
            )

        headers = {}
        for name, value in self.headers.items():
            if name.lower() in REQUEST_STRIP:
                continue
            headers[name] = value

        present = {name.lower() for name in headers}
        if "x-opencode-session" not in present:
            headers["x-opencode-session"] = _session_for_request(body)
        if "user-agent" not in present:
            headers["User-Agent"] = "OpenSoloMark/" + __version__

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

    def _path_error(self, started):
        return self._json(
            403,
            {
                "error": {
                    "type": "path_not_allowed",
                    "message": "Invalid path. Use one of: %s."
                    % ", ".join(ALLOWED_PREFIXES),
                }
            },
            started,
        )

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

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):
        if ":" in server_address[0]:
            self.address_family = socket.AF_INET6
        super().__init__(server_address, RequestHandlerClass, bind_and_activate)


def main():
    try:
        config = _load_config()
    except ConfigError as exc:
        sys.stderr.write("opensolomark: config error: %s\n" % exc)
        sys.stderr.flush()
        return 2

    _apply_config(config)

    try:
        server = Server((HOST, PORT), Handler)
    except OSError as exc:
        sys.stderr.write(
            "opensolomark: cannot listen on %s:%d: %s\n" % (HOST, PORT, exc)
        )
        sys.stderr.flush()
        return 1

    sys.stderr.write(
        "opensolomark %s: http://%s:%d -> %s (session=%s, mode=%s)\n"
        % (__version__, HOST, PORT, UPSTREAM, SESSION, SESSION_MODE)
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
