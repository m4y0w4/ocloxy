## What changed

<!-- Briefly describe the change and why it is needed. -->

## PR checklist

- [ ] I reviewed `git status` and `git diff --cached` before opening this PR.
- [ ] I did not include API keys, tokens, session IDs, passwords, or other credentials.
- [ ] I replaced personal home-directory paths with `~/`.
- [ ] I replaced real hostnames, usernames, email addresses, and account IDs with placeholders such as `example.com`.
- [ ] I did not commit `settings.json`, app databases, `localstorage.sqlite3`, logs, crash reports, network captures, `.env` files, certificates, or private keys.
- [ ] I redacted screenshots and pasted logs before attaching them.
- [ ] If a secret was exposed, I rotated it and cleaned history; I did not rely on deleting it in a later commit.
- [ ] The change is limited to the proxy, LaunchAgent, documentation, or repository housekeeping.

## Testing

<!-- Describe how you verified the change. For example: -->

- [ ] `plutil -lint com.opensolomark.proxy.plist` passes (if the plist changed).
- [ ] I tested `proxy.py` or `ocloxy.py` with a local upstream (if either changed).
- [ ] I updated the README or docs for any user-facing behavior change.
