# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in apple-a-day, please report it responsibly.

**Email:** daniel@eidosagi.com

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact

We will acknowledge receipt within 48 hours and provide a timeline for a fix.

## Scope

apple-a-day runs diagnostic commands on your local Mac. It does not:
- Send data to any remote server
- Require network access
- Modify system state (checks are read-only)

Security concerns are most likely to involve:
- Command injection via crafted filenames or plist values
- Privilege escalation if `aad fix` is added in the future
- Information disclosure in JSON output (hostnames, paths, service names)
