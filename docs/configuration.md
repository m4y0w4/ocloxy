# Configuration

The defaults work for most setups. To change them, edit the installed plist:

```text
~/Library/LaunchAgents/com.opensolomark.proxy.plist
```

Open it with TextEdit or any text editor. The settings are under `EnvironmentVariables`.

| Variable | Default | Notes |
|---|---|---|
| `LISTEN_HOST` | `127.0.0.1` | Keep this as loopback. Do not expose the proxy to your network. |
| `LISTEN_PORT` | `47123` | If you change it, update the app base URL too. |
| `UPSTREAM_BASE` | `https://opencode.ai` | Host only. Do not add a path. |
| `SESSION_ID` | `opensolomark-local` | Stable identifier sent to OpenCode when the app does not send its own. |
| `ALLOWED_PREFIXES` | `/inference/,/zen/` | Comma-separated path prefixes with trailing slashes. Use `/inference/` to restrict the proxy to Go only. |
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
$HOME/OpenSoloMark/proxy.py
```

If you move the folder, update the `proxy.py` path in `ProgramArguments`, then reload the service. `$HOME` expands to your home directory, so the plist does not contain your username.

## Restrict the proxy to Go only

Set:

```text
ALLOWED_PREFIXES=/inference/
```

The default also allows `/zen/` as an alternate path family. Other paths return `403 path_not_allowed`.

## Manual run

To run the proxy in the foreground for testing:

```bash
LISTEN_PORT=47124 python3 ~/OpenSoloMark/proxy.py
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

The response includes the upstream, session ID, and port the proxy is using.

## Preview: `ocloxy.py`

`ocloxy.py` adds opt-in Derived Session Mode. It uses the same environment variables as `proxy.py`, plus:

| Variable | Default | Notes |
|---|---|---|
| `SESSION_MODE` | `fixed` | `fixed` uses `SESSION_ID`; `derive` hashes the conversation opening. |
| `SESSION_DERIVE_INCLUDE_SYSTEM` | `1` | Set to `0` to hash only the first user message. |

`SESSION_ID` remains the fallback. See [Derived Session Mode](derived-session-mode.feature.md) for the algorithm, risks, and testing steps.

`proxy.py` ignores these variables; they only apply to `ocloxy.py`.
