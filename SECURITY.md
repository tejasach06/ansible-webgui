# Security Policy

## Reporting a vulnerability

Use GitHub Security Advisories: open the repository Security tab and choose "Report a vulnerability". Do not file public issues for vulnerabilities. Target acknowledgement is 72 hours; target triage is 7 days.

unverified — no maintainer contact email exists in the repo; if a security contact address is desired, substitute it here.

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |

This project is pre-1.0; only the latest `main` receives fixes.

## Security model

- Passwords are hashed with Argon2 in `app/core/security.py`.
- JWTs live in HttpOnly cookies only; never localStorage or URL parameters.
- Mutating requests require `X-Requested-With: XMLHttpRequest` for CSRF protection.
- Live runs require two-person approval.
- Credentials are Fernet-encrypted at rest, decrypted into a `0700` temp dir, and removed in `finally`.
- Runs execute `git archive <sha>`, never the mutable working tree.
- RBAC permissions are defined in `app/core/rbac.py`.

## Hardening before exposure

- Override `JWT_SECRET`, `FERNET_KEY`, `POSTGRES_PASSWORD`, and `BOOTSTRAP_ADMIN_PASSWORD`; shipped defaults in `app/core/config.py` are insecure placeholders.
- Set `COOKIE_SECURE=true` and terminate TLS in front of `web`.
- Do not publish `8000:8000` publicly; only `web` needs exposure.
- Rotate the bootstrap admin password after first login.
- Keep `.env` out of version control.
