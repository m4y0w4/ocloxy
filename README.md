# OpenSoloMark

A tiny local proxy that lets **Markra or SoloMD** use **OpenCode Go** as an OpenAI-compatible provider.

OpenCode Go requires an `x-opencode-session` header on inference requests. These apps let you set a base URL and an API key, but not custom headers. OpenSoloMark runs on your Mac, adds the header, and forwards the request to OpenCode. Your API key stays in the app.

Tested with Markra 2.13.1 and SoloMD 5.0.3.

## What it does

Without the header, OpenCode Go returns:

```text
400 MissingSessionID
```

OpenSoloMark sits between your app and OpenCode:

```text
Markra or SoloMD
      │
      │  http://127.0.0.1:47123/inference/go/v1
      ▼
OpenSoloMark proxy
      │  adds x-opencode-session
      ▼
https://opencode.ai/inference/go/v1
```

It listens on loopback, adds the header if the app did not send one, forwards the request, and streams the response back. It does not store your API key or log headers or message content.

## Requirements

- macOS
- Python 3.9 or newer
- An OpenCode API key
- Markra or SoloMD

No `pip install` is needed. Check Python with `python3 --version`; if it is missing or older than 3.9, see [Troubleshooting](docs/troubleshooting.md#python-is-missing-or-too-old).

## Quick start

### 1. Put the folder in your home directory

The LaunchAgent expects:

```text
~/OpenSoloMark/proxy.py
```

If you downloaded a ZIP, rename the folder to `OpenSoloMark` and move it to your home folder. If you keep it elsewhere, edit the `proxy.py` path in the plist.

### 2. Install the LaunchAgent

```bash
mkdir -p ~/Library/LaunchAgents
plutil -lint ~/OpenSoloMark/com.opensolomark.proxy.plist
cp ~/OpenSoloMark/com.opensolomark.proxy.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.opensolomark.proxy.plist
```

`plutil -lint` should print `OK`. If the service is already loaded, see [Troubleshooting](docs/troubleshooting.md#the-launchagent-is-already-loaded).

### 3. Check that it is running

```bash
curl -s http://127.0.0.1:47123/healthz
```

A healthy proxy returns:

```json
{"ok": true, "service": "opensolomark", "upstream": "https://opencode.ai", "session": "opensolomark-local", "port": 47123}
```

### 4. Connect your app

Use these values:

| Setting | Value |
|---|---|
| Base URL | `http://127.0.0.1:47123/inference/go/v1` |
| API key | Your OpenCode API key |
| Model | A chat-compatible model ID |

Use `127.0.0.1`, not `localhost`, and do not add a trailing slash. The app should append `/chat/completions` or `/models` itself.

| App | Where to configure |
|---|---|
| **Markra** | **Settings → AI Providers**. Add or edit a provider, set the API style to **OpenAI-compatible**, enter the values above, save, and select the model. |
| **SoloMD** | **Settings → AI**. Enable AI, choose **OpenAI-compatible** or **Custom**, enter the values above, and save. |

Send a test message. If it fails, run the health check again and read the log:

```bash
tail -n 50 ~/Library/Logs/opensolomark.log
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| App cannot connect / connection refused | Proxy is not running, or the app uses the wrong port | Run the health check. Check `launchctl print gui/$(id -u)/com.opensolomark.proxy` and the log. Confirm the app base URL uses port `47123`. |
| `401 Unauthorized` | API key missing or wrong | Re-enter your OpenCode API key in the app. |
| `404 Not Found` | Base URL is wrong | Use exactly `http://127.0.0.1:47123/inference/go/v1`. Do not append `/chat/completions`. |
| `400 MissingSessionID` | The app is still calling OpenCode directly | Change the app base URL to the local proxy. |
| `ModelProtocolUnsupported` or `FreeTierError` | The model is not chat-compatible or is restricted | Choose a chat-compatible model, and avoid free models restricted to the OpenCode client. |

Full troubleshooting: [docs/troubleshooting.md](docs/troubleshooting.md).

## How it works

- The app sends an OpenAI-compatible request to `http://127.0.0.1:47123/inference/go/v1/...`.
- The proxy adds `x-opencode-session: opensolomark-local` if the app did not send one.
- It forwards the method, path, query, body, and end-to-end headers to `https://opencode.ai`.
- It streams the upstream response back without buffering the whole thing.
- Only `/inference/` and `/zen/` are allowed; other paths return `403 path_not_allowed`.
- `GET /healthz` is a local health check and does not call OpenCode.

The proxy binds to loopback only. It is not reachable from other machines on your network.

Read more: [docs/how-it-works.md](docs/how-it-works.md).

## Configuration

The defaults work for most setups. The installed plist is:

```text
~/Library/LaunchAgents/com.opensolomark.proxy.plist
```

Common changes are the port (`LISTEN_PORT`) and session ID (`SESSION_ID`). After editing, reload the service:

```bash
launchctl bootout gui/$(id -u)/com.opensolomark.proxy
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.opensolomark.proxy.plist
```

All settings, changing ports, moving the folder, and manual runs: [docs/configuration.md](docs/configuration.md).

## Security

- The proxy binds to `127.0.0.1` only. It is not accessible from other machines.
- No API key is stored in `proxy.py` or the plist. The app sends the `Authorization` header; the proxy forwards it.
- The log contains the method, path, status, response size, and timing. It does not contain headers, API keys, prompts, or response bodies.
- The proxy has no authentication. Any local process that knows the port can use it. Run it only on a Mac you trust.

Security details: [docs/how-it-works.md#security-and-privacy](docs/how-it-works.md#security-and-privacy).

## Uninstall

```bash
launchctl bootout gui/$(id -u)/com.opensolomark.proxy
rm ~/Library/LaunchAgents/com.opensolomark.proxy.plist
```

Then point your app back to its previous provider. Optionally remove the proxy files and log:

```bash
rm -rf ~/OpenSoloMark
rm -f ~/Library/Logs/opensolomark.log
```

## Model notes

- The model must support OpenAI-compatible **chat completions** (`/chat/completions`). Responses-only models fail with `ModelProtocolUnsupported`.
- Some free-tier models are restricted to the OpenCode client. They fail with `FreeTierError` or “free tier can only be used from within OpenCode.” Choose another model.
- Model IDs and availability change. Use a chat-compatible model ID from your OpenCode account.
- The proxy forwards whatever model ID the app sends.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR. The PR template includes the PII and secret checklist.

## Documentation

- [Troubleshooting](docs/troubleshooting.md)
- [Configuration](docs/configuration.md)
- [How it works](docs/how-it-works.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

OpenSoloMark is an unofficial community project. It is not affiliated with OpenCode, Markra, or SoloMD. Use it at your own risk. The software is provided “as is”, without warranty of any kind.
