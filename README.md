# OcLoXy

**An OpenCode Local Proxy**

A local compatibility proxy for OpenAI-compatible clients that cannot send the `x-opencode-session` header required by **OpenCode Go/Zen**. It runs on your Mac, adds the header, and forwards the request to OpenCode. Your API key stays in the app.

**Markra 2.13.1** supports custom provider headers, so it can use OpenCode Go directly and does not need Ocloxy. **SoloMD 5.0.4** lists OpenCode Go as a provider, but it currently returns `400 MissingSessionID` and SoloMD does not expose a custom-header field, so SoloMD still needs Ocloxy.

**Recent additions**

- Verified Markra 2.13.1's direct custom-header path.
- Verified SoloMD 5.0.4 still needs Ocloxy for OpenCode Go.
- Added a compatibility guide for Markra, SoloMD, and other clients.
- Added opt-in **Derived Session Mode** for stable per-conversation session IDs.
- Hardened request handling and network security.
- Added `/healthz`, LaunchAgent logging, and expanded the docs.

Last verified with Markra 2.13.1 and SoloMD 5.0.4 on 2026-10-21.

## Do you need Ocloxy?

| Client | Direct support | Ocloxy needed? |
|---|---|---|
| **Markra 2.13.1** | Custom provider headers | No |
| **SoloMD 5.0.4** | Built-in OpenCode Go provider, but it returns `400 MissingSessionID`; no custom-header field | Yes |
| Another OpenAI-compatible client | Varies; a client that can set custom headers can use OpenCode directly | Yes, when it cannot set headers |

See [Compatibility](docs/COMPATIBILITY.md) for setup details and version notes.

## What it does

Without the header, OpenCode Go returns:

```text
400 MissingSessionID
```

Ocloxy sits between your app and OpenCode:

```text
SoloMD or another client without header support
      │
      │  http://127.0.0.1:47123/inference/go/v1
      ▼
Ocloxy proxy
      │  adds x-opencode-session
      ▼
https://opencode.ai/inference/go/v1
```

It listens on loopback, adds the header if the app did not send one, forwards the request, and streams the response back. It does not store your API key or log headers or message content.

## Requirements

- macOS
- Python 3.9 or newer
- An OpenCode API key
- An OpenAI-compatible client that cannot send `x-opencode-session` directly. This is currently the case for **SoloMD 5.0.4**. **Markra 2.13.1** can send custom headers directly and does not need Ocloxy.

No `pip install` is needed. Check Python with `python3 --version`; if it is missing or older than 3.9, see [Troubleshooting](docs/TROUBLESHOOTING.md#python-is-missing-or-too-old).

## Quick start

If you use **Markra 2.13.1**, skip this installation and use the direct setup in [Markra](#markra).

### 1. Put the folder in your home directory

The LaunchAgent expects:

```text
~/ocloxy/ocloxy.py
```

If you downloaded a ZIP, rename the folder to `ocloxy` and move it to your home folder. If you keep it elsewhere, edit the `ocloxy.py` path in the plist.

### 2. Install the LaunchAgent

```bash
mkdir -p ~/Library/LaunchAgents
plutil -lint ~/ocloxy/com.ocloxy.proxy.plist
cp ~/ocloxy/com.ocloxy.proxy.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ocloxy.proxy.plist
```

`plutil -lint` should print `OK`. If the service is already loaded, see [Troubleshooting](docs/TROUBLESHOOTING.md#the-launchagent-is-already-loaded).

### 3. Check that it is running

```bash
curl -s http://127.0.0.1:47123/healthz
```

A healthy proxy returns:

```json
{"ok": true, "service": "ocloxy", "version": "0.1.0", "session_mode": "fixed", "upstream": "https://opencode.ai", "session": "ocloxy-local", "port": 47123}
```

### 4. Connect your app

These values are for the Ocloxy path:

| Setting | Value |
|---|---|
| Base URL | `http://127.0.0.1:47123/inference/go/v1` |
| API key | Your OpenCode API key |
| Model | A chat-compatible model ID |

Use `127.0.0.1`, not `localhost`, and do not add a trailing slash. The app should append `/chat/completions` or `/models` itself.

| App | Where to configure |
|---|---|
| **Markra** | **Settings → AI Providers**. If you are using Ocloxy, add or edit a provider, set the API style to **OpenAI-compatible**, enter the values above, save, and select the model. Markra 2.13.1 can also use OpenCode directly; see [Markra](#markra). |
| **SoloMD** | **Settings → AI**. Enable AI, choose **OpenAI-compatible** or **Custom**, enter the values above, and save. See [SoloMD](#solomd). |

Send a test message. If it fails, run the health check again and read the log:

```bash
tail -n 50 ~/Library/Logs/ocloxy.log
```

## Markra

Markra 2.13.1 supports custom provider headers, so it does not need Ocloxy. To use OpenCode Go directly:

1. Open **Settings → AI Providers**.
2. Add or edit an OpenAI-compatible provider.
3. Set the base URL to `https://opencode.ai/inference/go/v1`.
4. Enter your OpenCode API key.
5. Set custom headers to:

   ```json
   {"x-opencode-session":"ocloxy-local"}
   ```

6. Choose a chat-compatible model, save, click **Test API**, and send a test message.

Markra's custom-header field is a fixed JSON object. If you need derived per-conversation session IDs, use Ocloxy's Derived Session Mode instead.

## SoloMD

SoloMD 5.0.4 lists **OpenCode Go** in its AI provider list, but the built-in provider currently returns `400 MissingSessionID`, and SoloMD does not expose a custom-header field. Use the Ocloxy values in [Connect your app](#4-connect-your-app) until SoloMD sends the header itself.

The proxy health check should return `ok: true` before you test a chat. If it still fails, see [Troubleshooting](#troubleshooting).

## Other OpenAI-compatible clients

If the client supports custom provider headers, set:

```json
{"x-opencode-session":"ocloxy-local"}
```

and point it at `https://opencode.ai/inference/go/v1`.

If it only exposes a base URL and API key, use Ocloxy at `http://127.0.0.1:47123/inference/go/v1`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| App cannot connect / connection refused | Proxy is not running, or the app uses the wrong port | Run the health check. Check `launchctl print gui/$(id -u)/com.ocloxy.proxy` and the log. Confirm the app base URL uses port `47123`. |
| `401 Unauthorized` | API key missing or wrong | Re-enter your OpenCode API key in the app. |
| `404 Not Found` | Base URL is wrong | Use exactly `http://127.0.0.1:47123/inference/go/v1`. Do not append `/chat/completions`. |
| `400 MissingSessionID` | The request reached OpenCode without a usable `x-opencode-session` header | Markra: add the custom header or use Ocloxy. SoloMD: use Ocloxy. Confirm the Ocloxy base URL and run the health check. See [Compatibility](docs/COMPATIBILITY.md#400-missingsessionid). |
| `ModelProtocolUnsupported` or `FreeTierError` | The model is not chat-compatible or is restricted | Choose a chat-compatible model, and avoid free models restricted to the OpenCode client. |

Full troubleshooting: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## How it works

- The app sends an OpenAI-compatible request to `http://127.0.0.1:47123/inference/go/v1/...`.
- By default, the proxy adds `x-opencode-session: ocloxy-local` if the app did not send one.
- It forwards the method, path, query, body, and end-to-end headers to `https://opencode.ai`.
- It streams the upstream response back without buffering the whole thing.
- Only `/inference/` and `/zen/` are allowed; other paths and traversal attempts return `403 path_not_allowed`.
- `GET /healthz` is a local health check and does not call OpenCode.

The proxy binds to loopback only. It refuses non-loopback bind addresses and requires HTTPS for non-loopback upstreams.

Read more: [docs/HOW-IT-WORKS.md](docs/HOW-IT-WORKS.md).

## Configuration

The defaults work for most setups. The installed plist is:

```text
~/Library/LaunchAgents/com.ocloxy.proxy.plist
```

Common changes are the port (`LISTEN_PORT`), session ID (`SESSION_ID`), and session mode (`SESSION_MODE`). After editing, reload the service:

```bash
launchctl bootout gui/$(id -u)/com.ocloxy.proxy
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ocloxy.proxy.plist
```

All settings, changing ports, moving the folder, and manual runs: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

Derived Session Mode is opt-in via `SESSION_MODE=derive`.

## Security

- The proxy binds to loopback only. It is not accessible from other machines.
- No API key is stored in `ocloxy.py` or the plist. The app sends the `Authorization` header; the proxy forwards it.
- The log contains the method, path, status, response size, and timing. It does not contain headers, API keys, prompts, or response bodies.
- The proxy has no authentication. Any local process that knows the port can use it. Run it only on a Mac you trust.

Security details: [docs/HOW-IT-WORKS.md#security-and-privacy](docs/HOW-IT-WORKS.md#security-and-privacy).

## Uninstall

```bash
launchctl bootout gui/$(id -u)/com.ocloxy.proxy
rm ~/Library/LaunchAgents/com.ocloxy.proxy.plist
```

Then point your app back to its previous provider. Optionally remove the proxy files and log:

```bash
rm -rf ~/ocloxy
rm -f ~/Library/Logs/ocloxy.log
```

## Model notes

- The model must support OpenAI-compatible **chat completions** (`/chat/completions`). Responses-only models fail with `ModelProtocolUnsupported`.
- Some free-tier models are restricted to the OpenCode client. They fail with `FreeTierError` or “free tier can only be used from within OpenCode.” Choose another model.
- Model IDs and availability change. Use a chat-compatible model ID from your OpenCode account.
- The proxy forwards whatever model ID the app sends.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR. The PR template includes the PII and secret checklist.

## Documentation

- [Features](FEATURES.md)
- [Compatibility](docs/COMPATIBILITY.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Configuration](docs/CONFIGURATION.md)
- [How it works](docs/HOW-IT-WORKS.md)
- [Contributing](CONTRIBUTING.md)

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

Ocloxy is an unofficial community project. It is not affiliated with OpenCode, Markra, or SoloMD. Use it at your own risk. The software is provided “as is”, without warranty of any kind.
