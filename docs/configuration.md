# Configuration

The defaults work for most setups. To change them, edit the installed plist:

```text
~/Library/LaunchAgents/com.opensolomark.proxy.plist
```

Open it with TextEdit or any text editor. The settings are under `EnvironmentVariables`.

| Variable | Default | Notes |
|---|---|---|
| `LISTEN_HOST` | `127.0.0.1` | Loopback only. Non-loopback values fail at startup. |
| `LISTEN_PORT` | `47123` | If you change it, update the app base URL too. |
| `UPSTREAM_BASE` | `https://opencode.ai` | HTTPS is required unless the host is loopback. Host only; do not add a path. |
| `SESSION_ID` | `opensolomark-local` | Fixed session ID and fallback when derivation is unavailable. |
| `SESSION_MODE` | `fixed` | `fixed` uses `SESSION_ID`; `derive` hashes the conversation opening. |
| `SESSION_DERIVE_INCLUDE_SYSTEM` | `1` | Set to `0` to hash only the first user message. |
| `MAX_BODY_BYTES` | `16777216` | Request body cap, in bytes. The default is 16 MiB. |
| `ALLOWED_PREFIXES` | `/inference/,/zen/` | Comma-separated path prefixes. The root `/` is not allowed. |
| `UPSTREAM_TIMEOUT` | `600` | Seconds to wait for OpenCode. |
| `PATH` | Homebrew and system paths | Where launchd looks for `python3`. |

## Reload after changes

```bash
launchctl bootout gui/$(id -u)/com.opensolomark.proxy
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.opensolomark.proxy.plist
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

The response includes the version, session mode, upstream, fallback session ID, and port.

## Derived Session Mode

Set `SESSION_MODE=derive` to derive a stable per-conversation ID from the opening system and user messages. `SESSION_DERIVE_INCLUDE_SYSTEM=0` limits the hash to the first user message.

`SESSION_ID` remains the fallback. See [Derived Session Mode](derived-session-mode.feature.md) for the algorithm, risks, and testing steps.
