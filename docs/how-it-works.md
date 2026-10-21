# How it works

Ocloxy is a small HTTP proxy that adds the header OpenCode Go expects and forwards the request unchanged.

## Request flow

The app sends an OpenAI-compatible request to the local proxy:

```text
POST http://127.0.0.1:47123/inference/go/v1/chat/completions
```

The proxy forwards the same method, path, query, body, and end-to-end headers to:

```text
https://opencode.ai/inference/go/v1/chat/completions
```

Before forwarding, it:

- adds `x-opencode-session: ocloxy-local` if the app did not send that header;
- can derive a per-conversation session ID when `SESSION_MODE=derive`;
- adds a `User-Agent` if the app did not send one;
- drops hop-by-hop headers such as `Connection` and `Transfer-Encoding`;
- drops `Accept-Encoding`, because the proxy relays decoded bytes.

The upstream response is streamed back as it arrives. If OpenCode sends a `Content-Length`, the proxy forwards it; otherwise the response uses chunked transfer encoding.

Only these response headers are passed back:

- `Content-Type`
- `Retry-After`
- `Request-Id` and `X-Request-Id`
- `OpenAI-Processing-Ms`
- `X-RateLimit-*` and `Anthropic-RateLimit-*`

Everything else is regenerated locally.

## Request safety

- Request bodies are capped by `MAX_BODY_BYTES`, which defaults to 16 MiB.
- Chunked request bodies are decoded and capped at the same limit.
- Malformed framing returns `400 invalid_request_body`; oversized bodies return `413 request_body_too_large`.
- Paths with `..`, encoded traversal, null bytes, or backslashes are rejected.
- Absolute-form request targets are rejected.
- Non-loopback bind addresses and non-HTTPS upstreams outside loopback fail at startup.

## Path allowlist

By default, only two path families are allowed:

- `/inference/` — the recommended base, used as `/inference/go/v1/...`
- `/zen/` — an alternate path family, allowed for compatibility

Anything else returns HTTP `403` with:

```json
{"error": {"type": "path_not_allowed", "message": "..."}}
```

This keeps the proxy from being used as a general-purpose relay.

## Health check

`GET /healthz` is handled locally and does not call OpenCode. It returns:

```json
{"ok": true, "service": "ocloxy", "version": "0.1.0", "session_mode": "fixed", "upstream": "https://opencode.ai", "session": "ocloxy-local", "port": 47123}
```

## Errors

- Upstream HTTP errors are relayed with their status code and response body.
- `502 proxy_upstream_unreachable` means the proxy could not reach the upstream.
- `504 proxy_timeout` means the upstream did not respond before `UPSTREAM_TIMEOUT`.
- `500 proxy_internal` means the proxy hit an unexpected error.
- `400 invalid_request_body` means the request framing was invalid.
- `413 request_body_too_large` means the body exceeded `MAX_BODY_BYTES`.

## Security and privacy

- The proxy binds to loopback only. It refuses non-loopback bind addresses.
- No API key is stored in `ocloxy.py` or the plist. The app sends the `Authorization` header; the proxy forwards it upstream and does not write it to disk.
- The proxy can see headers and request bodies in memory while forwarding them, but it does not log headers, API keys, prompts, or response bodies.
- The log contains the method, path, status, response size, and timing.
- The proxy has no authentication. Any local process that knows the port can use it. Run it only on a Mac you trust.
- Do not expose the port through a tunnel. Remote binding is rejected.
- The proxy does not modify prompts or responses. It adds one header and relays the request.

## Derived session IDs

`ocloxy.py` sends the fixed `SESSION_ID` by default. Set `SESSION_MODE=derive` to derive a stable per-conversation ID from the opening system and user messages. It still preserves an app-provided session header and falls back to `SESSION_ID` when it cannot derive one.
