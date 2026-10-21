# Troubleshooting

For setup, see the [README](../readme.md).

## First checks

1. Check the proxy:

   ```bash
   curl -s http://127.0.0.1:47123/healthz
   ```

   A healthy proxy returns:

   ```json
   {"ok": true, "service": "ocloxy", "version": "0.1.0", "session_mode": "fixed", "upstream": "https://opencode.ai", "session": "ocloxy-local", "port": 47123}
   ```

2. Check the LaunchAgent:

   ```bash
   launchctl print gui/$(id -u)/com.ocloxy.proxy
   ```

3. Read the log:

   ```bash
   tail -n 50 ~/Library/Logs/ocloxy.log
   ```

The log records the method, path, status, response size, and timing. It does not record headers, API keys, prompts, or response bodies.

## Common issues

| Symptom | Likely cause | Fix |
|---|---|---|
| App cannot connect / connection refused | Proxy is not running, or the app uses the wrong port | Run the health check. Check `launchctl print gui/$(id -u)/com.ocloxy.proxy` and the log. Confirm the app base URL uses `http://127.0.0.1:47123/inference/go/v1`. |
| `401 Unauthorized` | API key missing or wrong | Re-enter your OpenCode API key in the app. |
| `404 Not Found` | Base URL is wrong | Use exactly `http://127.0.0.1:47123/inference/go/v1`. Do not append `/chat/completions`. |
| `400 MissingSessionID` | The app is still calling OpenCode directly | Change the app base URL to the local proxy. |
| `403 path_not_allowed` | The base URL path is not allowed | Use `/inference/go/v1`. If you changed `ALLOWED_PREFIXES`, check the allowed prefixes. Traversal paths are also rejected. |
| `400 invalid_request_body` | Request framing is malformed or ambiguous | Send a valid `Content-Length` or chunked body. Do not send both. |
| `413 request_body_too_large` | The request body exceeded `MAX_BODY_BYTES` | Reduce the request size or raise `MAX_BODY_BYTES` in the plist and reload. |
| `config error` in the log | An environment value failed startup validation | Fix `LISTEN_HOST`, `UPSTREAM_BASE`, `SESSION_MODE`, or another reported value, then reload. |
| `ModelProtocolUnsupported` | The model does not support chat completions | Choose a chat-compatible model. |
| `FreeTierError` or “free tier can only be used from within OpenCode” | The model is restricted to the OpenCode client | Choose another model. |
| `Address already in use` | Another process is using port `47123` | Run `lsof -nP -iTCP:47123 -sTCP:LISTEN`. Change `LISTEN_PORT` in the plist, update the app base URL, and reload. |
| `python3: command not found` or `/usr/bin/env: python3: No such file or directory` | Python is missing or not on the LaunchAgent's `PATH` | See [Python is missing or too old](#python-is-missing-or-too-old). |
| `CERTIFICATE_VERIFY_FAILED` in the log | The Python interpreter cannot validate the upstream certificate | See [Certificate errors](#certificate-errors). |
| LaunchAgent does not start | Invalid plist or not loaded | Run `plutil -lint`, then `launchctl print` and read the log. |
| Plist changes have no effect | launchd cached the old job | Run `launchctl bootout` and then `launchctl bootstrap`. `kickstart -k` only restarts the process. |
| `Broken pipe` or `ConnectionResetError` in the log | The app closed the connection mid-stream | Harmless. |
| `502 proxy_upstream_unreachable` | The proxy cannot reach `https://opencode.ai` | Check your network, DNS, and any VPN or firewall. |
| `504 proxy_timeout` | OpenCode did not respond before `UPSTREAM_TIMEOUT` | Try again. If it keeps happening, increase `UPSTREAM_TIMEOUT` in the plist and reload. |

## Python is missing or too old

Check the version:

```bash
python3 --version
```

Install Python 3.9 or newer from [python.org](https://www.python.org/downloads/macos/) or with Homebrew:

```bash
brew install python
```

The LaunchAgent looks for `python3` in:

```text
/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
```

If your Python is somewhere else, add its folder to the `PATH` value in the plist, then reload the service.

## Certificate errors

Use a Python build with current CA certificates, such as python.org or Homebrew. If you need to point Python at a specific bundle, add `SSL_CERT_FILE` to the plist's `EnvironmentVariables`:

```xml
<key>SSL_CERT_FILE</key>
<string>/path/to/ca-bundle.pem</string>
```

Then reload the service.

## The LaunchAgent is already loaded

Unload it, then load it again:

```bash
launchctl bootout gui/$(id -u)/com.ocloxy.proxy
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ocloxy.proxy.plist
```

Check it:

```bash
curl -s http://127.0.0.1:47123/healthz
```

## Check what is using the port

```bash
lsof -nP -iTCP:47123 -sTCP:LISTEN
```

If another process owns the port, change `LISTEN_PORT` in the plist and update the app base URL.

## Start from a clean load

```bash
launchctl bootout gui/$(id -u)/com.ocloxy.proxy
plutil -lint ~/Library/LaunchAgents/com.ocloxy.proxy.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ocloxy.proxy.plist
```

## Logs

The LaunchAgent writes to:

```text
~/Library/Logs/ocloxy.log
```

Follow the log while you send a test message:

```bash
tail -f ~/Library/Logs/ocloxy.log
```

A successful request looks like:

```text
2026-01-01T12:00:00 POST /inference/go/v1/chat/completions -> 200 1234B 850ms
```

The exact size and timing vary. The log does not contain headers, keys, prompts, or response bodies.
