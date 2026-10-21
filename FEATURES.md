# Features

Ocloxy is a local compatibility proxy for OpenAI-compatible clients that cannot send the `x-opencode-session` header required by OpenCode Go. It is currently needed for **SoloMD 5.0.4**. **Markra 2.13.1** can send custom provider headers directly and does not need Ocloxy.

`ocloxy.py` is the single proxy, version `0.1.0`. It uses Python 3.9+ and the standard library only.

## Core proxy

- Adds `x-opencode-session` when the app cannot send custom headers.
- Forwards the request to OpenCode Go over HTTPS.
- Preserves the app's `Authorization` header, body, path, and query.
- Streams upstream responses without buffering the whole response.
- Relays upstream HTTP errors with their status and response body.
- Handles upstream timeouts and unreachable-host errors with JSON errors.
- Ignores client disconnects during streaming instead of crashing.

## Compatibility

- Works with **SoloMD 5.0.4**, which cannot set the required header for its built-in OpenCode Go provider.
- Works with any OpenAI-compatible client that only exposes a base URL and API key.
- **Markra 2.13.1** can set custom provider headers directly; Ocloxy is not required there.
- Uses `http://127.0.0.1:47123/inference/go/v1` as the recommended base URL.
- Forwards `/models` and `/chat/completions` requests.
- Allows `/inference/` and `/zen/` path families.
- Rejects other paths and traversal attempts with HTTP `403 path_not_allowed`.
- Preserves an app-provided `x-opencode-session` value.

## Session handling

- Defaults to a fixed `SESSION_ID`; `ocloxy-local` is only the default, and any stable ASCII session ID works.
- Uses one fixed session ID for every conversation by default.
- Supports opt-in `SESSION_MODE=derive` for a stable per-conversation ID.
- Derives the ID from the opening messages without storing conversation state.
- Falls back to `SESSION_ID` when derivation is not possible.
- Can exclude system and developer messages from the hash with `SESSION_DERIVE_INCLUDE_SYSTEM=0`.

## Operations

- Ships with a macOS LaunchAgent for start-at-login and keep-alive.
- Binds to loopback and refuses non-loopback bind addresses.
- Requires HTTPS for non-loopback upstreams.
- Provides a local `GET /healthz` endpoint with the version and session mode.
- Supports configuration through the LaunchAgent environment.
- Writes method, path, status, size, and timing to a local log.
- Can be reloaded with `launchctl bootout` and `launchctl bootstrap`.

## Security and hardening

- Does not store the OpenCode API key.
- Does not log headers, API keys, prompts, or response bodies.
- Limits request bodies to `MAX_BODY_BYTES` (16 MiB by default).
- Decodes chunked request bodies and enforces the same limit.
- Rejects malformed framing, path traversal, null bytes, and backslashes.
- Keeps the proxy allowlist narrow instead of acting as a general-purpose relay.
- Has no authentication; it is intended for a trusted local Mac.

## Documentation and guardrails

- README quick start for installing the proxy and connecting an app.
- Compatibility guide for Markra, SoloMD, and other OpenAI-compatible clients.
- Troubleshooting guide with common errors and fixes.
- Configuration guide for ports, paths, timeouts, limits, Python, and certificates.
- How-it-works guide for request flow, allowlist, streaming, and security.
- Contributing guide with PII and secret checks.
- `.gitignore` rules for logs, app data, databases, and credentials.
- Pull-request template with a matching PII and secret checklist.

## Version status

| Proxy | Status | Version |
|---|---|---|
| `ocloxy.py` | Current | `0.1.0` |

`0.1.0` is an early release. Derived Session Mode remains opt-in until real app traffic confirms that the derived IDs stay stable.
