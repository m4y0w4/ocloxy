# Compatibility

Ocloxy is only needed when an OpenAI-compatible app cannot send the `x-opencode-session` header required by OpenCode Go. Capabilities differ by app and version.

Last verified: 2026-10-21.

| Client | Version | Direct OpenCode Go support | Ocloxy needed? |
|---|---|---|---|
| [Markra](https://markra.app/) | 2.13.1 | Custom provider headers | No |
| [SoloMD](https://solomd.app/) | 5.0.4 | Built-in OpenCode Go provider returns `400 MissingSessionID`; no custom-header field | Yes |
| Other OpenAI-compatible clients | Varies | Direct if the client can set custom headers | Yes, when it cannot |

## Session IDs

OpenCode's Go documentation asks clients to send a stable session ID in `x-opencode-session` for each conversation so it can optimize routing and prompt caching. The header is not authentication. The value does not change whether Ocloxy forwards a request; it affects upstream routing and cache behavior.

`ocloxy-local` is only Ocloxy's default value; it is not a required header value. Any stable short ASCII token works, including `your-chosen-id`. Use the same value for every turn in one conversation, and different values for separate conversations, apps, or proxy instances.

A fixed ID is reused for every conversation. It passes the presence check, but it does not give per-conversation routing or cache affinity. For per-conversation IDs, use Ocloxy's `SESSION_MODE=derive` or a client that changes the header per conversation.

Do not generate a new random value for every request. A random value is fine only when it stays fixed for one conversation; per-request randomness defeats routing and prompt-cache affinity. More randomness does not make the proxy work better. A random value per conversation is fine; a random fixed value is no better than any other fixed value except for avoiding accidental collisions.

OpenCode Go session guidance: <https://opencode.ai/docs/go/#where-can-i-use-it>

## Markra

Markra 2.13.1's provider settings support a JSON custom headers field. According to Markra's documentation, those headers are sent on model-list and chat requests. OpenCode asks for a stable session ID per conversation. If you want that instead of Markra's static header, use Ocloxy with `SESSION_MODE=derive` and remove Markra's `x-opencode-session` header; Ocloxy then derives the ID from the conversation opening.

To use OpenCode Go directly:

1. Open **Settings → AI Providers**.
2. Add or edit an OpenAI-compatible provider.
3. Set the base URL to `https://opencode.ai/inference/go/v1`.
4. Enter your OpenCode API key.
5. Set custom headers to:

   ```json
   {"x-opencode-session":"your-chosen-id"}
   ```

   Replace `your-chosen-id` with any stable ASCII token. `ocloxy-local` is only Ocloxy's default, not a required value. Markra's field is static, so one value is used for every conversation.

6. Choose a chat-compatible model, save, click **Test API**, and send a test message.

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

SoloMD cannot set the header, so Ocloxy chooses it. To use a custom fixed value, set `SESSION_ID=your-chosen-id` in the plist. For a stable per-conversation value, set `SESSION_MODE=derive`. See [Session IDs](#session-ids) and [Configuration](CONFIGURATION.md#session-ids).

SoloMD AI documentation: <https://solomd.app/docs/ai/>

SoloMD release notes: <https://solomd.app/whats-new/>

## Other clients

If the client supports custom provider headers, set:

```json
{"x-opencode-session":"your-chosen-id"}
```

Replace `your-chosen-id` with any stable value, then point the client at `https://opencode.ai/inference/go/v1`. See [Session IDs](#session-ids).

If it only exposes a base URL and API key, use Ocloxy at `http://127.0.0.1:47123/inference/go/v1`.

## `400 MissingSessionID`

This error means the request reached OpenCode without a usable `x-opencode-session` header.

- **Markra 2.13.1:** add the custom header above, or use Ocloxy.
- **SoloMD 5.0.4:** use Ocloxy; the built-in provider currently fails this check.
- **Ocloxy:** confirm the app base URL is the local proxy URL and that `/healthz` returns `ok: true`.

Versions and provider behavior change. Record the app version and date when updating this table.
