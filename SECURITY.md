# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

---

## Reporting a Vulnerability

We take the security of **TraceMind** seriously. If you discover a security vulnerability, please do NOT create a public GitHub issue.

Instead, please report security concerns directly by emailing the maintainer at [rishabh211200@users.noreply.github.com](mailto:rishabh211200@users.noreply.github.com) with the subject `[SECURITY] TraceMind Vulnerability Report`.

Please include:
* A description of the vulnerability.
* Steps to reproduce the issue (proof-of-concept script or trace payload).
* Potential impact.

We will acknowledge receipt within 48 hours and coordinate a responsible disclosure and patch.

---

## Security Principles in TraceMind

1. **Synthetic Data Only**: TraceMind is strictly designed with synthetic data generation. Never use real production customer or employee traces.
2. **Credential Safety**: Secrets and API tokens must never be hard-coded. Use environment variables with `.env.example`.
3. **Restricted AI Tooling**: The AI Analyst is restricted to safe, read-only analytical tools and never granted direct database write access or raw SQL execution capabilities.
