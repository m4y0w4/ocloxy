# Configuration

The defaults work for most setups. To change them, edit the installed plist:

```text
~/Library/LaunchAgents/com.ocloxy.proxy.plist
```

Open it with TextEdit or any text editor. The settings are under `EnvironmentVariables`.

| Variable | Default | Notes |
|---|---|---|
| `LISTEN_HOST` | `127.0.0.1` | Loopback only. Non-loopback values fail at startup. |
| `LISTEN_PORT` | `47123` | If you change it, update the app base URL too. |
| `UPSTREAM_BASE` | `https://opencode.ai` | HTTPS is required unless the host is loopback. Host only; do not add a path. |
| `SESSION_ID` | `ocloxy-local` | Fixed session ID and fallback when derivation is unavailable. Any stable ASCII token works; `ocloxy-local` is only the default. |
| `SESSION_MODE` | `fixed` | `fixed` uses `SESSION_ID` for every conversation; `derive` hashes the conversation opening for per-conversation IDs. |
| `SESSION_DERIVE_INCLUDE_SYSTEM` | `1` | Set to `0` to hash only the first user message. |
| `MAX_BODY_BYTES` | `16777216` | Request body cap, in bytes. The default is 16 MiB. |
| `ALLOWED_PREFIXES` | `/inference/,/zen/` | Comma-separated path prefixes. The root `/` is not allowed. |
| `UPSTREAM_TIMEOUT` | `600` | Seconds to wait for OpenCode. |
| `PATH` | Homebrew and system paths | Where launchd looks for `python3`. |

## Reload after changes

```bash
launchctl bootout gui/$(id -u)/com.ocloxy.proxy
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ocloxy.proxy.plist
```

Check it again:

```bash
curl -s http://127.0.0.1:47123/healthz
```

If you changed `LISTEN_PORT`, use the new port in the health check and in the app base URL.

## Change the port

1. Set `LISTEN_PORT` in the plist to the new port.
2. Reload the service.
3. Update the app base URL to `http://127.0.0.1:<port>/inference/go/v1`.
4. Run the health check on the new port.

## Move the proxy folder

The plist starts the proxy with this path:

```text
$HOME/ocloxy/ocloxy.py
```

If you move the folder, update the `ocloxy.py` path in `ProgramArguments`, then reload the service. `$HOME` expands to your home directory, so the plist does not contain your username.

## Restrict the proxy to Go only

Set:

```text
ALLOWED_PREFIXES=/inference/
```

The default also allows `/zen/` as an alternate path family. Other paths and traversal attempts return `403 path_not_allowed`.

## Request limits

`MAX_BODY_BYTES` caps both fixed-length and chunked request bodies. Requests over the limit return `413 request_body_too_large`. Malformed framing returns `400 invalid_request_body`.

## Manual run

To run the proxy in the foreground for testing:

```bash
LISTEN_PORT=47124 python3 ~/ocloxy/ocloxy.py
```

Stop it with `Ctrl` + `C`. The LaunchAgent is the normal way to run the proxy.

When the manual instance is running, use port `47124` in the app base URL:

```text
http://127.0.0.1:47124/inference/go/v1
```

Do not run the manual instance on the same port as the LaunchAgent.

## Python path

The LaunchAgent uses this `PATH`:

```text
/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
```

If `python3` lives somewhere else, add its folder to the `PATH` value in the plist and reload the service.

## Certificate errors

Use a Python build with current CA certificates, such as python.org or Homebrew. If you need a specific bundle, add `SSL_CERT_FILE` to the plist's `EnvironmentVariables`:

```xml
<key>SSL_CERT_FILE</key>
<string>/path/to/ca-bundle.pem</string>
```

Then reload the service.

## Health check

`GET /healthz` is handled locally and does not call OpenCode:

```bash
curl -s http://127.0.0.1:47123/healthz
```

The response includes the version, session mode, upstream, fallback session ID, and port. The `session` value is the configured default, not a required value.

## Session IDs

`x-opencode-session` is a routing and prompt-cache hint, not authentication. OpenCode asks for a stable value for each conversation.

`SESSION_ID` defaults to `ocloxy-local`. It can be any stable short ASCII token, such as `your-chosen-id`; it does not need to be random or secret. In `fixed` mode, one value is used for every conversation.

If you run more than one proxy instance or app with a fixed ID, give each a distinct value; otherwise they can share one upstream session.

Do not generate a new random value for every request. A random value works only when it stays fixed for the conversation; per-request randomness defeats routing and prompt-cache affinity.

If the app sends its own `x-opencode-session` (for example Markra 2.13.1), Ocloxy preserves it and this setting is only the fallback.

## Derived Session Mode

Set `SESSION_MODE=derive` to derive a stable per-conversation ID from the opening system and user messages. `SESSION_DERIVE_INCLUDE_SYSTEM=0` limits the hash to the first user message.

The derived value is deterministic for the same opening, not random per request. `SESSION_ID` remains the fallback.
