# Features

OpenSoloMark is a local proxy that lets Markra or SoloMD use OpenCode Go as an OpenAI-compatible provider.

`proxy.py` is the current installed entry point. `ocloxy.py` is the `1.0.0-preview.1` preview with opt-in Derived Session Mode.

## Core proxy

- Adds `x-opencode-session` when the app cannot send custom headers.
- Forwards the request to OpenCode Go over HTTPS.
- Preserves the app's `Authorization` header, body, path, and query.
- Streams upstream responses without buffering the whole response.
- Relays upstream HTTP errors with their status and response body.
- Handles upstream timeouts and unreachable-host errors with JSON errors.
- Ignores client disconnects during streaming instead of crashing.

## Compatibility

- Works with an OpenAI-compatible base URL in Markra or SoloMD.
- Uses `http://127.0.0.1:47123/inference/go/v1` as the recommended base URL.
- Forwards `/models` and `/chat/completions` requests.
- Allows `/inference/` and `/zen/` path families.
- Rejects other paths with HTTP `403 path_not_allowed`.
- Preserves an app-provided `x-opencode-session` value.

## Operations

- Ships with a macOS LaunchAgent for start-at-login and keep-alive.
- Binds to `127.0.0.1` by default.
- Provides a local `GET /healthz` endpoint.
- Supports configuration through the LaunchAgent environment.
- Writes method, path, status, size, and timing to a local log.
- Can be reloaded with `launchctl bootout` and `launchctl bootstrap`.

## Security and privacy

- Does not store the OpenCode API key.
- Does not log headers, API keys, prompts, or response bodies.
- Is not reachable from other machines by default.
- Has no authentication; it is intended for a trusted local Mac.
- Keeps the proxy allowlist narrow instead of acting as a general-purpose relay.

## Documentation and guardrails

- README quick start for installing the proxy and connecting an app.
- Troubleshooting guide with common errors and fixes.
- Configuration guide for ports, paths, timeouts, Python, and certificates.
- How-it-works guide for request flow, allowlist, streaming, and security.
- Contributing guide with PII and secret checks.
- `.gitignore` rules for logs, app data, databases, and credentials.
- Pull-request template with a matching PII and secret checklist.

## Preview

- `ocloxy.py` adds opt-in **Derived Session Mode**.
- Derives a stable per-conversation session ID from the opening messages.
- Honors an app-provided `x-opencode-session` first.
- Falls back to the configured `SESSION_ID` when derivation is not possible.
- Remains stateless and does not log the derived value.
- Is not installed by default; `proxy.py` remains the installed entry point.
- Has standard-library unit tests in `tests/test_ocloxy.py`.

See [Derived Session Mode](docs/derived-session-mode.feature.md) for the design, configuration, and testing details.

## Version status

| Entry point | Status | Version |
|---|---|---|
| `proxy.py` | Current installed entry point | Pre-1.0 |
| `ocloxy.py` | Preview, opt-in | `1.0.0-preview.1` |

`1.0.0-preview.1` is a milestone label for the new preview, not a claim that the preview is ready to replace `proxy.py` by default.
