# Compatibility

Ocloxy is only needed when an OpenAI-compatible app cannot send the `x-opencode-session` header required by OpenCode Go. Capabilities differ by app and version.

Last verified: 2026-10-21.

| Client | Version | Direct OpenCode Go support | Ocloxy needed? |
|---|---|---|---|
| [Markra](https://markra.app/) | 2.13.1 | Custom provider headers | No |
| [SoloMD](https://solomd.app/) | 5.0.4 | Built-in OpenCode Go provider returns `400 MissingSessionID`; no custom-header field | Yes |
| Other OpenAI-compatible clients | Varies | Direct if the client can set custom headers | Yes, when it cannot |

## Markra

Markra 2.13.1's provider settings support a JSON custom headers field. According to Markra's documentation, those headers are sent on model-list and chat requests. To use OpenCode Go directly:

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

Markra provider documentation: <https://markra.app/en/docs/settings-providers/>

## SoloMD

SoloMD 5.0.4 lists **OpenCode Go** in its AI provider list, but the built-in provider currently returns:

```text
400 MissingSessionID
```

SoloMD's AI settings expose a custom base URL but not a custom-header field. Use Ocloxy:

| Setting | Value |
|---|---|
| Base URL | `http://127.0.0.1:47123/inference/go/v1` |
| API key | Your OpenCode API key |
| Provider style | OpenAI-compatible or Custom |
| Model | A chat-compatible model ID |

Do not use SoloMD's built-in OpenCode Go provider until it sends the header. The proxy health check should return `ok: true` before you test a chat.

SoloMD AI documentation: <https://solomd.app/docs/ai/>

SoloMD release notes: <https://solomd.app/whats-new/>

## Other clients

If the client supports custom provider headers, set:

```json
{"x-opencode-session":"ocloxy-local"}
```

and point it at `https://opencode.ai/inference/go/v1`.

If it only exposes a base URL and API key, use Ocloxy at `http://127.0.0.1:47123/inference/go/v1`.

## `400 MissingSessionID`

This error means the request reached OpenCode without a usable `x-opencode-session` header.

- **Markra 2.13.1:** add the custom header above, or use Ocloxy.
- **SoloMD 5.0.4:** use Ocloxy; the built-in provider currently fails this check.
- **Ocloxy:** confirm the app base URL is the local proxy URL and that `/healthz` returns `ok: true`.

Versions and provider behavior change. Record the app version and date when updating this table.
