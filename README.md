# OpenSoloMark

A tiny local proxy that lets **Markra** and **SoloMD** use **OpenCode Go** as an OpenAI-compatible provider.

OpenCode Go requires an `x-opencode-session` header on inference requests. Markra and SoloMD let you set a base URL and an API key, but not custom headers. OpenSoloMark runs on your Mac, adds the header, and forwards the request to OpenCode. Your API key stays in the app.

Tested with Markra 2.13.1 and SoloMD 5.0.3 on macOS.

## Contents

- [What it does](#what-it-does)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Connect Markra](#connect-markra)
- [Connect SoloMD](#connect-solomd)
- [Verify](#verify)
- [Troubleshooting](#troubleshooting)
- [How it works](#how-it-works)
- [Customize](#customize)
- [Security and privacy](#security-and-privacy)
- [Uninstall](#uninstall)
- [Model notes](#model-notes)
- [Before you open a PR](#before-you-open-a-pr)
- [License](#license)
- [Disclaimer](#disclaimer)

## What it does

OpenCode Go is an OpenAI-compatible inference API, but it expects a header called `x-opencode-session` on inference requests. Without it, requests fail with:

```text
400 MissingSessionID
```

Markra and SoloMD can talk to any OpenAI-compatible endpoint, but their settings only expose a base URL and an API key. They have no field for custom headers.

OpenSoloMark is a small proxy that sits between the app and OpenCode:

```text
Markra / SoloMD
      │
      │  http://127.0.0.1:47123/inference/go/v1
      ▼
OpenSoloMark proxy
      │  adds x-opencode-session
      ▼
https://opencode.ai/inference/go/v1
```

The proxy:

- listens on loopback (`127.0.0.1`) by default;
- adds the `x-opencode-session` header if the app did not send one;
- forwards your `Authorization` header, body, and path unchanged;
- streams the response back as it arrives;
- does not store your API key;
- does not log headers or message content.

The files in this repository are:

| File | Purpose |
|---|---|
| `proxy.py` | The local proxy. Python 3.9+, standard library only. |
| `com.opensolomark.proxy.plist` | macOS LaunchAgent that starts the proxy at login and keeps it running. |
| `README.md` | This guide. |
| `LICENSE` | MIT license. |
| `.gitignore` | Keeps local logs, app data, databases, and credentials out of commits. |
| `.github/PULL_REQUEST_TEMPLATE.md` | PII and secret checklist for pull requests. |

## Requirements

- macOS
- Python 3.9 or newer
- An OpenCode API key
- Markra or SoloMD

No `pip install` is needed. The proxy uses only the Python standard library.

Check your Python version:

```bash
python3 --version
```

If it is missing or older than 3.9, install Python from
[python.org](https://www.python.org/downloads/macos/) or with Homebrew:

```bash
brew install python
```

The LaunchAgent looks for `python3` in `/opt/homebrew/bin`, `/usr/local/bin`,
`/usr/bin`, `/bin`, `/usr/sbin`, and `/sbin`. If your Python lives somewhere
else, add its folder to the `PATH` value in the plist (see
[Customize](#customize)).

## Quick start

### 1. Put the folder in your home directory

The LaunchAgent expects the proxy at this exact path:

```text
~/OpenSoloMark/proxy.py
```

If you downloaded a ZIP, rename the extracted folder to `OpenSoloMark` and move
it to your home folder. In Finder, choose **Go → Home** (`Shift` + `Cmd` + `H`)
and put the folder there. The final path is `~/OpenSoloMark/proxy.py`. The plist
uses `$HOME`, so it does not contain your username. If you keep the folder
somewhere else, edit the `proxy.py` path in the plist.

### 2. Install the LaunchAgent

Open **Terminal** (Applications → Utilities → Terminal) and run:

```bash
mkdir -p ~/Library/LaunchAgents
plutil -lint ~/OpenSoloMark/com.opensolomark.proxy.plist
cp ~/OpenSoloMark/com.opensolomark.proxy.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.opensolomark.proxy.plist
```

`plutil -lint` should print `OK`. If the service is already loaded, unload it
first and then load it again:

```bash
launchctl bootout gui/$(id -u)/com.opensolomark.proxy
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.opensolomark.proxy.plist
```

Check that the proxy is running:

```bash
curl -s http://127.0.0.1:47123/healthz
```

A healthy proxy returns:

```json
{"ok": true, "service": "opensolomark", "upstream": "https://opencode.ai", "session": "opensolomark-local", "port": 47123}
```

The proxy starts now and starts again automatically when you log in or reboot.

### 3. Connect the app

Use this base URL in Markra or SoloMD:

```text
http://127.0.0.1:47123/inference/go/v1
```

Use `127.0.0.1`, not `localhost`, and do not add a trailing slash. The app
should append `/chat/completions` or `/models` itself.

Then enter your OpenCode API key and choose a chat-compatible model in the app.
The exact steps are below.

## Connect Markra

1. Open **Markra → Settings → AI Providers**.
2. Add a provider, or edit your existing custom provider.
3. Set the provider type / API style to **OpenAI-compatible**.
4. Set **Name** to `OpenCode Go` (or anything you like).
5. Set **Base URL** to:

   ```text
   http://127.0.0.1:47123/inference/go/v1
   ```

6. Paste your OpenCode API key into the **API key** field.
7. Add the model ID you use in OpenCode. If Markra has a refresh or fetch
   button, use it; the proxy forwards `/models`.
8. Save, select the provider and model, and send a test message.

Menu labels can vary slightly between Markra versions; look for the AI provider
and model settings.

Markra stores the key in its own settings. The proxy never stores it.

## Connect SoloMD

1. Open **SoloMD → Settings → AI**.
2. Enable AI.
3. Set the provider to **OpenAI-compatible** or **Custom**. If your version
   lists an **OpenCode Go** preset, you can use that too.
4. Set **Base URL** to:

   ```text
   http://127.0.0.1:47123/inference/go/v1
   ```

5. Set **Model** to the model ID you use in OpenCode.
6. Paste your OpenCode API key when prompted. SoloMD stores the key in its own
   key file.
7. Save and send a test message.

Menu labels can vary slightly between app versions. Look for the fields named
**Base URL**, **API key**, and **Model**.

## Verify

With the proxy installed:

```bash
curl -s http://127.0.0.1:47123/healthz
```

Then send a short message in Markra or SoloMD. If you get a reply, the setup is
complete.

If it does not work, check the log:

```bash
tail -n 50 ~/Library/Logs/opensolomark.log
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| App cannot connect / connection refused | Proxy is not running, or the app is using the wrong port | Run the health check. Check `launchctl print gui/$(id -u)/com.opensolomark.proxy` and the log. Confirm the app base URL uses port `47123`. |
| `401 Unauthorized` | API key missing or wrong | Re-enter your OpenCode API key in the app. |
| `404 Not Found` | Base URL is wrong | Use exactly `http://127.0.0.1:47123/inference/go/v1`. Do not append `/chat/completions`. |
| `400 MissingSessionID` | The app is still calling OpenCode directly | Change the app base URL to the local proxy. |
| `403 path_not_allowed` | The base URL path is not allowed | Use `/inference/go/v1`. Check `ALLOWED_PREFIXES` if you changed it. |
| `ModelProtocolUnsupported` | The model does not support chat completions | Choose a chat-compatible model. |
| `FreeTierError` or “free tier can only be used from within OpenCode” | The model is restricted to the OpenCode client | Choose another model. |
| `Address already in use` | Another process is using port `47123` | Run `lsof -nP -iTCP:47123 -sTCP:LISTEN`. Change `LISTEN_PORT` in the plist, update the app base URLs, and reload. |
| `python3: command not found` or `/usr/bin/env: python3: No such file or directory` | Python is missing or not on the LaunchAgent's `PATH` | Install Python 3.9+, add its folder to `PATH` in the plist, and reload. |
| `CERTIFICATE_VERIFY_FAILED` in the log | The Python interpreter cannot validate the upstream certificate | Use a Python build with current CA certificates (python.org or Homebrew), or set `SSL_CERT_FILE` in the plist to a current PEM bundle. |
| LaunchAgent does not start | Invalid plist or not loaded | Run `plutil -lint`, then `launchctl print` and read the log. |
| Plist changes have no effect | launchd cached the old job | Run `launchctl bootout` and then `launchctl bootstrap`. `kickstart -k` only restarts the process. |
| `Broken pipe` or `ConnectionResetError` in the log | The app closed the connection mid-stream | Harmless. |

## How it works

The proxy receives a request from the app, such as:

```text
POST http://127.0.0.1:47123/inference/go/v1/chat/completions
```

It forwards the same method, path, query, body, and end-to-end headers to:

```text
https://opencode.ai/inference/go/v1/chat/completions
```

Hop-by-hop headers such as `Connection` and `Transfer-Encoding` are dropped
and regenerated locally.

Before forwarding, it adds:

```text
x-opencode-session: opensolomark-local
```

if the app did not already send that header. It then streams the upstream
response back without buffering the whole thing.

By default, only two path families are allowed:

- `/inference/` — the recommended base, used as `/inference/go/v1/...`
- `/zen/` — an alternate path family, allowed for compatibility

Anything else returns:

```json
{"error": {"type": "path_not_allowed", "message": "..."}}
```

with HTTP status `403`. This keeps the proxy from being used as a
general-purpose relay.

`GET /healthz` is a local health check. It does not call OpenCode.

The proxy binds to `127.0.0.1` only by default. It is not reachable from other
machines on your network.

## Customize

The defaults work for Markra and SoloMD. To change them, edit the installed
plist:

```text
~/Library/LaunchAgents/com.opensolomark.proxy.plist
```

You can open it with TextEdit or any text editor. The settings are under
`EnvironmentVariables`:

| Variable | Default | Notes |
|---|---|---|
| `LISTEN_HOST` | `127.0.0.1` | Keep this as loopback. Do not expose the proxy to your network. |
| `LISTEN_PORT` | `47123` | If you change it, update the base URL in both apps. |
| `UPSTREAM_BASE` | `https://opencode.ai` | Host only. Do not add a path. |
| `SESSION_ID` | `opensolomark-local` | Stable session identifier sent to OpenCode. Both apps can share it. |
| `ALLOWED_PREFIXES` | `/inference/,/zen/` | Comma-separated path prefixes, with trailing slashes. Use `/inference/` to restrict to Go only. |
| `UPSTREAM_TIMEOUT` | `600` | Seconds to wait for OpenCode. |

After editing the plist, reload the service:

```bash
launchctl bootout gui/$(id -u)/com.opensolomark.proxy
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.opensolomark.proxy.plist
```

Check it again:

```bash
curl -s http://127.0.0.1:47123/healthz
```

If you change `LISTEN_PORT`, use the new port in the app base URLs and in the
health check.

If you move the `OpenSoloMark` folder, update the `proxy.py` path in
`ProgramArguments`. The default is:

```text
$HOME/OpenSoloMark/proxy.py
```

### Separate sessions for each app

By default, both apps share one stable session ID. That is fine for normal use.
If you want each app to have its own session, run a second copy of the proxy on
another port with a different `SESSION_ID`:

```text
App A → http://127.0.0.1:47123/inference/go/v1  (session opensolomark-a)
App B → http://127.0.0.1:47124/inference/go/v1  (session opensolomark-b)
```

Use a separate plist with a different `Label`, `LISTEN_PORT`, `SESSION_ID`, and
log path for the second instance.

### Manual run

To run the proxy in the foreground for testing:

```bash
LISTEN_PORT=47124 python3 ~/OpenSoloMark/proxy.py
```

Stop it with `Ctrl` + `C`. The LaunchAgent is the normal way to run it.

## Security and privacy

- By default, the proxy binds to `127.0.0.1` only. It is not accessible from other machines.
- No API key is stored in `proxy.py` or the plist.
- The app sends the `Authorization` header; the proxy forwards it to OpenCode.
  The proxy can see the header in memory while forwarding, but it does not log
  or store it.
- The log contains the method, path, status, response size, and timing. It does
  not contain headers, API keys, prompts, or response bodies.
- The proxy has no authentication. Any local process that knows the port can use
  it. Run it only on a Mac you trust.
- Do not change `LISTEN_HOST` to `0.0.0.0` or expose the port through a tunnel.
- The proxy does not modify your prompts or the model's response. It adds one
  header and relays the request.

## Uninstall

Stop and remove the LaunchAgent:

```bash
launchctl bootout gui/$(id -u)/com.opensolomark.proxy
rm ~/Library/LaunchAgents/com.opensolomark.proxy.plist
```

Then point Markra and SoloMD back to their previous provider. Optionally remove
the proxy files and log:

```bash
rm -rf ~/OpenSoloMark
rm -f ~/Library/Logs/opensolomark.log
```

## Model notes

- The model must support OpenAI-compatible **chat completions**
  (`/chat/completions`). Some models are responses-only and will fail with
  `ModelProtocolUnsupported`.
- Some free-tier models are restricted to the OpenCode client. They fail with
  `FreeTierError` or “free tier can only be used from within OpenCode.” Choose a
  different model.
- Model IDs and availability change. Use the model ID from your OpenCode
  account, and make sure it is a chat model.
- Markra and SoloMD can use different models. Set the model in each app; the
  proxy forwards whatever model ID the app sends.

## Before you open a PR

This project handles API credentials and local app data. Keep personal and
machine-specific information out of commits, PR descriptions, and screenshots.

The repository includes a `.gitignore` for common local artifacts and a PR
template at `.github/PULL_REQUEST_TEMPLATE.md` with a matching checklist. The
`.gitignore` is a guardrail: it prevents untracked files such as logs,
databases, and `.env` files from being staged. It does not inspect file
contents, stop `git add -f`, or remove files that are already tracked.

Before you commit:

1. Review what you are about to commit:

   ```bash
   git status
   git diff --cached
   ```

   `git status --ignored` shows what the rules are catching.

2. Replace personal and machine-specific values:

   - Absolute home-directory paths → `~/`
   - Real API keys or tokens → `<YOUR_OPENCODE_API_KEY>`
   - Real hostnames, usernames, email addresses, and account IDs →
     `example.com` or another clear placeholder

3. Do not commit:

   - `settings.json`, app settings, or `localstorage.sqlite3`
   - `*.log`, crash reports, `.har`, `.pcap`, or other diagnostics
   - `.env` files, private keys, certificates, or provisioning profiles
   - Screenshots or pasted logs containing account names, emails, keys, or
     local paths

4. If you exposed a secret, rotate it and clean the git history. Deleting it in
   a later commit is not enough. Do not paste the secret into a public issue.

The LaunchAgent plist is intentionally tracked. Do not add a blanket `*.plist`
rule to `.gitignore`.

## License

MIT. See [LICENSE](LICENSE).

## Disclaimer

OpenSoloMark is an unofficial community project. It is not affiliated with
OpenCode, Markra, or SoloMD. Use it at your own risk. The software is provided
“as is”, without warranty of any kind.
