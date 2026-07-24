# Security Policy

## Supported version

Security fixes are provided for the latest release.

## Reporting

Please report vulnerabilities privately through GitHub Security Advisories. Do not open a public issue containing credentials, recipient addresses, private dispatches, or exploit details.

## Secret boundaries

- Never commit `.env`, SMTP credentials, provider keys, generated dispatches, audio, JSONL history, ready manifests, or sent receipts.
- GitHub prepare jobs must not receive SMTP secrets. Only the deliver job may receive them.
- Agent subprocesses use an allowlist; `SMTP_*` and `MAIL_TO` are never forwarded.
- Link validation rejects private/local targets and redirects to private addresses.
- Logs must not contain recipients, message bodies, passwords, or tokens.

If a secret is exposed, revoke it first, then remove it from reachable history and audit workflow logs.
