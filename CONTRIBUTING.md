# Contributing

This project handles API credentials and local app data. Keep personal and machine-specific information out of commits, PR descriptions, screenshots, and issues.

## Project layout

| Path | Purpose |
|---|---|
| `proxy.py` | The local proxy. Python 3.9+, standard library only. |
| `com.opensolomark.proxy.plist` | macOS LaunchAgent that starts the proxy at login and keeps it running. |
| `README.md` | Quick start and user-facing overview. |
| `docs/troubleshooting.md` | Full troubleshooting reference. |
| `docs/configuration.md` | Environment variables and advanced configuration. |
| `docs/how-it-works.md` | Request flow, path allowlist, and security details. |
| `CONTRIBUTING.md` | This file. |
| `LICENSE` | MIT license. |
| `.gitignore` | Keeps local logs, app data, databases, and credentials out of commits. |
| `.github/PULL_REQUEST_TEMPLATE.md` | PII and secret checklist for pull requests. |

## Before you open a PR

The repository includes a `.gitignore` for common local artifacts and a PR template with a matching checklist. The `.gitignore` is a guardrail: it prevents untracked files such as logs, databases, and `.env` files from being staged. It does not inspect file contents, stop `git add -f`, or remove files that are already tracked.

1. Review what you are about to commit:

   ```bash
   git status
   git diff --cached
   ```

   `git status --ignored` shows what the rules are catching.

2. Replace personal and machine-specific values:

   - Absolute home-directory paths → `~/`
   - Real API keys or tokens → `<YOUR_OPENCODE_API_KEY>`
   - Real hostnames, usernames, email addresses, and account IDs → `example.com` or another clear placeholder

3. Do not commit:

   - `settings.json`, app settings, or `localstorage.sqlite3`
   - `*.log`, crash reports, `.har`, `.pcap`, or other diagnostics
   - `.env` files, private keys, certificates, or provisioning profiles
   - Screenshots or pasted logs containing account names, emails, keys, or local paths

4. If you exposed a secret, rotate it and clean the git history. Deleting it in a later commit is not enough. Do not paste the secret into a public issue.

The LaunchAgent plist is intentionally tracked. Do not add a blanket `*.plist` rule to `.gitignore`.

## Checks

- Run `plutil -lint com.opensolomark.proxy.plist` if the plist changed.
- Test the proxy with a local upstream if `proxy.py` changed.
- Update the README or docs for any user-facing behavior change.
- Open a PR using the repository template.
